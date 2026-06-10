"""
CRAI 멀티에이전트 리포트 파이프라인

Scout → Orchestrator ──┬── TrendAgent (K-means 클러스터링 + 트렌드명)
                       ├── EngagementAgent (engagement 상위 10)
                       └── LeadIndexAgent (인플루언서 선행 지수)
                       ↓
                    Critic → Save
"""
import os
import json
import re
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import TypedDict, Optional

import anthropic
from langgraph.graph import StateGraph, END

from db.database import _get_connection, save_fashion_report

ACCOUNTS_PATH = Path(__file__).parent.parent.parent / "config" / "instagram_accounts.json"

_progress_cb = None

def set_progress_callback(cb):
    global _progress_cb
    _progress_cb = cb

def _progress(msg: str):
    if _progress_cb:
        _progress_cb("running", msg)
    print(msg)


def _load_account_sets() -> tuple[set, set]:
    with open(ACCOUNTS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return set(data.get("brands", [])), set(data.get("influencers", []))


# ── State ──────────────────────────────────────────────────────────────────

class CRAIState(TypedDict):
    days: int
    start_date: Optional[str]
    end_date: Optional[str]
    posts: list[dict]
    trend_clusters: list[dict]   # 1페이지
    engagement_top: list[dict]   # 3페이지
    lead_signals: list[dict]     # 2페이지
    summary: str
    top_keywords: list[str]
    style_trends: list[dict]     # 기존 호환용
    attribute_trends: dict       # 속성별 트렌드 (스타일/실루엣/컬러/소재/아이템/디테일)
    validation_passed: bool
    report_id: Optional[int]
    error_messages: list[str]


# ── Scout Agent ─────────────────────────────────────────────────────────────

def scout_agent(state: CRAIState) -> CRAIState:
    start_date = state.get("start_date")
    end_date = state.get("end_date")

    if start_date and end_date:
        _progress(f"[1/4] 데이터 수집 중... ({start_date} ~ {end_date})")
        date_filter = f"AND posted_at >= '{start_date}' AND posted_at < ('{end_date}'::date + interval '1 day')"
    else:
        days = state.get("days", 30)
        _progress(f"[1/4] 데이터 수집 중... (최근 {days}일)")
        date_filter = "" if days == 0 else f"AND collected_at >= NOW() - ('{days} days')::interval"

    sql = f"""
        SELECT id, account_name, source, image_url, caption_ai,
               likes, comments, followers, posted_at,
               embedding::text
        FROM fashion_posts
        WHERE caption_ai IS NOT NULL AND embedding IS NOT NULL {date_filter}
          AND length(caption_ai) > 20
          AND caption_ai NOT ILIKE '%패션 이미지가 아닌%'
          AND caption_ai NOT ILIKE '%죄송%'
          AND caption_ai NOT ILIKE '%SKIP%'
          AND caption_ai NOT ILIKE '%이미지입니다%'
        ORDER BY posted_at DESC
        LIMIT 1000
    """
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()

    posts = []
    for row in rows:
        p = dict(zip(cols, row))
        raw = p.pop("embedding", None)
        if raw:
            p["embedding"] = np.array(json.loads(raw), dtype=np.float32)
        posts.append(p)

    print(f"🔍 [Scout] {len(posts)}개 포스트 로딩 완료")
    return {**state, "posts": posts}


# ── Trend Agent (1페이지) ────────────────────────────────────────────────────

def _trend_agent(posts: list[dict], client: anthropic.Anthropic) -> dict:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import normalize

    brands, _ = _load_account_sets()

    embeddings = np.stack([p["embedding"] for p in posts])
    embeddings = normalize(embeddings)

    k = min(5, len(posts))
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(embeddings)
    centers = km.cluster_centers_

    clusters = []
    for i in range(k):
        idxs = np.where(labels == i)[0]
        cluster_posts = [posts[j] for j in idxs]

        # 중심 가장 가까운 포스트 3개 → 대표 이미지
        dists = np.linalg.norm(embeddings[idxs] - centers[i], axis=1)
        top3_local = np.argsort(dists)[:3]
        representative = [cluster_posts[j] for j in top3_local]

        # 브랜드/인플루언서 분류
        has_brand = any(p["account_name"] in brands for p in cluster_posts)
        is_leading = not has_brand  # 인플루언서만 있으면 선행 트렌드

        # 캡션 샘플로 트렌드명 생성
        sample_captions = "\n".join([p["caption_ai"] for p in cluster_posts[:10] if p.get("caption_ai")])
        name_res = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=30,
            messages=[{"role": "user", "content": (
                f"아래 패션 이미지 설명들의 공통 스타일을 한국어 명사형 3~5단어로만 답해. 예시: '빈티지 데님 캐주얼', '시크 오피스 룩', '러블리 플로럴 원피스'. 단어만 출력, 설명 금지. 모든 트렌드명이 같은 단어로 시작하지 않도록 해:\n{sample_captions[:600]}"
            )}]
        )
        desc_res = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{"role": "user", "content": (
                f"아래 패션 이미지 설명들의 공통 스타일을 MD(머천다이저) 관점에서 2문장으로 설명해. 마크다운 없이 평문으로, 50자 이내로 간결하게:\n{sample_captions[:600]}"
            )}]
        )
        raw_name = name_res.content[0].text.strip().split("\n")[0].lstrip("#1234567890. ").strip()
        BAD_PREFIXES = ("죄송", "제공", "패션", "공통", "MD", "아래", "다음", "분석", "스타일명", "이름")
        trend_name = raw_name[:30] if raw_name and len(raw_name) < 30 and not any(raw_name.startswith(p) for p in BAD_PREFIXES) else f"트렌드 {i+1}"
        short_res = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            messages=[{"role": "user", "content": (
                f"'{trend_name}' 트렌드를 1~2단어 한국어 키워드로 압축해. 예시: '오버사이즈', '미니멀 캐주얼'. 단어만 출력:"
            )}]
        )
        raw_short = short_res.content[0].text.strip().split("\n")[0].strip()
        short_name = raw_short[:10] if raw_short and len(raw_short) <= 10 and not any(raw_short.startswith(p) for p in BAD_PREFIXES) else None
        cluster_description = re.sub(r'[\*\#\_\-]+', '', desc_res.content[0].text.strip()).strip()

        influencer_posts = [p for p in cluster_posts if p["account_name"] not in brands and (p.get("followers") or 0) >= 100]
        brand_posts = [p for p in cluster_posts if p["account_name"] in brands or p.get("source") == "lookbook"]
        brand_ratio = round(len(brand_posts) / max(len(cluster_posts), 1), 4)
        if influencer_posts:
            avg_engagement = np.mean([
                ((p.get("likes") or 0) + (p.get("comments") or 0)) / (p.get("followers") or 1)
                for p in influencer_posts
            ])
        else:
            avg_engagement = 0.0

        # 인플루언서 TOP 3 (브랜드 제외, engagement 기준)
        scored_inf = sorted(influencer_posts, key=lambda p: ((p.get("likes") or 0) + (p.get("comments") or 0)) / max(p.get("followers") or 1, 1), reverse=True)
        seen_accounts = set()
        top_influencers = []
        for p in scored_inf:
            if p["account_name"] not in seen_accounts:
                seen_accounts.add(p["account_name"])
                rate = ((p.get("likes") or 0) + (p.get("comments") or 0)) / max(p.get("followers") or 1, 1)
                top_influencers.append({
                    "account_name": p["account_name"],
                    "followers": p.get("followers", 0),
                    "engagement_rate": round(rate, 4),
                    "image_url": p.get("image_url", ""),
                })
            if len(top_influencers) >= 3:
                break

        # 소재 분포 (caption_ai 키워드 추출)
        MATERIAL_MAP = {
            "린넨": ["린넨", "linen"],
            "코튼": ["코튼", "면", "cotton"],
            "실크": ["실크", "새틴", "silk", "satin"],
            "니트": ["니트", "울", "knit", "wool"],
            "데님": ["데님", "청", "denim"],
            "피혁": ["가죽", "레더", "leather"],
            "쉬폰": ["쉬폰", "chiffon"],
            "기능성": ["스트레치", "방수", "쿨", "기능성"],
        }
        mat_count: dict = {}
        for p in cluster_posts:
            cap = (p.get("caption_ai") or "").lower()
            for mat, kws in MATERIAL_MAP.items():
                if any(k in cap for k in kws):
                    mat_count[mat] = mat_count.get(mat, 0) + 1
        total_mat = sum(mat_count.values()) or 1
        material_dist = [{"material": m, "pct": round(c / total_mat * 100)} for m, c in sorted(mat_count.items(), key=lambda x: -x[1])]

        # 브랜드 포스트 평균 가격
        brand_prices = [p["price"] for p in brand_posts if p.get("price") and p["price"] > 0]
        avg_price = round(np.mean(brand_prices)) if brand_prices else None

        clusters.append({
            "trend_name": trend_name,
            "short_name": short_name,
            "description": cluster_description,
            "post_count": len(cluster_posts),
            "is_leading": is_leading,
            "avg_engagement_rate": round(float(avg_engagement), 4),
            "brand_ratio": brand_ratio,
            "avg_price": avg_price,
            "representative_ids": [p["id"] for p in representative],
            "representative_images": [p["image_url"] for p in representative],
            "top_influencers": top_influencers,
            "material_dist": material_dist,
        })
        print(f"✅ [TrendAgent] 클러스터 {i+1}: {trend_name} ({'🔥선행' if is_leading else '✅확산'})")

    # 전체 요약도 생성
    trend_names = [c["trend_name"] for c in clusters]
    sum_res = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": (
            f"다음 패션 트렌드들을 MD(머천다이저) 관점에서 분석해줘: {', '.join(trend_names)}\n\n"
            "한 줄에 한 가지 인사이트씩, 4~5개의 짧은 문장으로 작성해줘. "
            "각 문장은 1줄 개행으로 구분하고, 번호나 마크다운 기호(#, *, -, 1) 등) 없이 평문으로만 작성해줘. "
            "각 문장은 완결된 한 문장으로, 트렌드명/공통 컬러·소재/MD 시사점 등 서로 다른 관점을 다뤄줘."
        )}]
    )
    summary = sum_res.content[0].text.strip()

    return {"clusters": clusters, "summary": summary, "top_keywords": trend_names}


# ── Attribute Trends Agent (속성별 트렌드) ───────────────────────────────────

ATTRIBUTE_KEYS = ["스타일", "실루엣", "컬러", "소재", "아이템", "디테일"]


def _attribute_trends_agent(posts: list[dict]) -> dict:
    counts: dict = {key: {} for key in ATTRIBUTE_KEYS}
    for p in posts:
        cap = p.get("caption_ai") or ""
        for key in ATTRIBUTE_KEYS:
            m = re.search(rf"\[{key}\]\s*(.+)", cap)
            if not m:
                continue
            line = m.group(1).split("\n")[0]
            for item in line.split(","):
                item = item.strip().strip(".")
                if item:
                    counts[key][item] = counts[key].get(item, 0) + 1

    result = {key: sorted(c.items(), key=lambda x: -x[1])[:5] for key, c in counts.items()}
    total = sum(len(v) for v in result.values())
    print(f"✅ [AttributeTrendsAgent] {total}개 키워드 집계")
    return result


# ── Engagement Agent (3페이지) ───────────────────────────────────────────────

def _engagement_agent(posts: list[dict]) -> list[dict]:
    scored = []
    for p in posts:
        followers = p.get("followers") or 0
        if followers < 100:
            continue
        rate = ((p.get("likes") or 0) + (p.get("comments") or 0)) / followers
        scored.append({**p, "engagement_rate": round(rate, 4)})

    top10 = sorted(scored, key=lambda x: x["engagement_rate"], reverse=True)[:10]
    result = [{
        "id": p["id"],
        "account_name": p["account_name"],
        "image_url": p["image_url"],
        "caption_ai": p["caption_ai"],
        "posted_at": str(p["posted_at"]) if p.get("posted_at") else None,
        "likes": p.get("likes", 0),
        "comments": p.get("comments", 0),
        "followers": p.get("followers", 0),
        "engagement_rate": p["engagement_rate"],
    } for p in top10]
    print(f"✅ [EngagementAgent] 상위 {len(result)}개 선정")
    return result


# ── Lead Index Agent (2페이지) ───────────────────────────────────────────────

def _lead_index_agent(posts: list[dict], trend_clusters: list[dict]) -> list[dict]:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import normalize

    brands, _ = _load_account_sets()

    embeddings = np.stack([p["embedding"] for p in posts])
    embeddings = normalize(embeddings)
    k = len(trend_clusters)
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(embeddings)

    signals = []
    for i, cluster in enumerate(trend_clusters):
        idxs = np.where(labels == i)[0]
        cluster_posts = [posts[j] for j in idxs]

        influencer_posts = [p for p in cluster_posts if p["account_name"] not in brands and p.get("posted_at")]
        brand_posts = [p for p in cluster_posts if (p["account_name"] in brands or p.get("source") == "lookbook") and p.get("posted_at")]

        if not influencer_posts:
            continue

        first_influencer = min(influencer_posts, key=lambda p: p["posted_at"])

        if not brand_posts:
            signals.append({
                "trend_name": cluster["trend_name"],
                "status": "브랜드 미출현",
                "days_ahead": None,
                "first_influencer_at": str(first_influencer["posted_at"]),
                "first_influencer": first_influencer["account_name"],
                "representative_image": first_influencer["image_url"],
                "representative_id": first_influencer["id"],
            })
        else:
            first_brand = min(brand_posts, key=lambda p: p["posted_at"])
            diff = (first_brand["posted_at"] - first_influencer["posted_at"]).days
            if diff > 0:
                signals.append({
                    "trend_name": cluster["trend_name"],
                    "status": f"인플루언서 {diff}일 선행",
                    "days_ahead": diff,
                    "first_influencer_at": str(first_influencer["posted_at"]),
                    "first_influencer": first_influencer["account_name"],
                    "first_brand_at": str(first_brand["posted_at"]),
                    "first_brand": first_brand["account_name"],
                    "representative_image": first_influencer["image_url"],
                    "representative_id": first_influencer["id"],
                })

    signals.sort(key=lambda x: x.get("days_ahead") or 9999, reverse=True)
    print(f"✅ [LeadIndexAgent] {len(signals)}개 선행 시그널 감지")
    return signals


# ── Orchestrator Node ────────────────────────────────────────────────────────

def orchestrator_node(state: CRAIState) -> CRAIState:
    _progress("[2/4] 트렌드 클러스터링 + 참여율 분석 중...")
    posts = state["posts"]
    if not posts:
        return {**state, "error_messages": state["error_messages"] + ["포스트 없음"]}

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    trend_result, engagement_result = None, None
    errors = []

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(_trend_agent, posts, client): "trend",
            executor.submit(_engagement_agent, posts): "engagement",
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                if key == "trend":
                    trend_result = future.result()
                else:
                    engagement_result = future.result()
            except Exception as e:
                errors.append(f"{key}: {e}")
                print(f"❌ [{key}Agent] 오류: {e}")

    if not trend_result:
        return {**state, "error_messages": state["error_messages"] + errors}

    trend_clusters = trend_result["clusters"]
    lead_signals = _lead_index_agent(posts, trend_clusters)
    attribute_trends = _attribute_trends_agent(posts)

    # signal_strength 계산
    def _calc_signal(cluster, signals):
        # 볼륨: 브랜드+인플루언서 전체 게시물 수 (0~3)
        volume_score = min(cluster.get("post_count", 0) / 50 * 3, 3.0)
        # 참여율: 인플루언서 avg engagement (0~3)
        eng_score = min(cluster.get("avg_engagement_rate", 0) / 0.02 * 3, 3.0)
        # 브랜드 미채택: 브랜드 비율 낮을수록 초기 트렌드 (0~2)
        brand_ratio = cluster.get("brand_ratio", 0)
        brand_score = round((1 - brand_ratio) * 2, 4)
        # 선행성: 인플루언서가 브랜드보다 먼저 올린 일수 (0~2)
        lead_score = 0.0
        for sig in signals:
            if sig.get("trend_name") == cluster.get("trend_name"):
                days = sig.get("days_ahead")
                lead_score = 2.0 if days is None else min(days / 30 * 2, 2.0)
                break
        total = round(volume_score + eng_score + brand_score + lead_score, 2)
        label = "opportunity" if total >= 8 else "growing" if total >= 5 else "saturated" if total >= 3 else "weak"
        return total, label

    for c in trend_clusters:
        score, label = _calc_signal(c, lead_signals)
        c["signal_strength"] = score
        c["signal_label"] = label

    # 기존 style_trends 호환
    style_trends = [{
        "title": c["trend_name"],
        "content": f"게시물 {c['post_count']}개, 평균 engagement {c['avg_engagement_rate']:.1%}",
        "representative_ids": c["representative_ids"],
    } for c in trend_clusters]

    return {
        **state,
        "trend_clusters": trend_clusters,
        "engagement_top": engagement_result or [],
        "lead_signals": lead_signals,
        "attribute_trends": attribute_trends,
        "summary": trend_result["summary"],
        "top_keywords": trend_result["top_keywords"],
        "style_trends": style_trends,
        "error_messages": state["error_messages"] + errors,
    }


# ── Critic Node ──────────────────────────────────────────────────────────────

def critic_node(state: CRAIState) -> CRAIState:
    _progress("[3/4] 결과 검증 중...")
    errors = []
    if not state.get("summary"):
        errors.append("summary 없음")
    if not state.get("trend_clusters"):
        errors.append("trend_clusters 없음")
    if errors:
        print(f"❌ [Critic] 실패: {errors}")
        return {**state, "validation_passed": False, "error_messages": state["error_messages"] + errors}
    print("✅ [Critic] 통과")
    return {**state, "validation_passed": True}


def should_continue_critic(state: CRAIState) -> str:
    if not state["validation_passed"] and len(state["error_messages"]) < 3:
        return "retry"
    return "save"


# ── Save Node ────────────────────────────────────────────────────────────────

def save_node(state: CRAIState) -> CRAIState:
    _progress("[4/4] 리포트 저장 중...")
    report_id = save_fashion_report(
        summary=state["summary"],
        top_keywords=state["top_keywords"],
        style_trends=state["style_trends"],
        post_count=len(state["posts"]),
        days=state["days"],
        start_date=state.get("start_date"),
        end_date=state.get("end_date"),
        trend_clusters=state["trend_clusters"],
        engagement_top=state["engagement_top"],
        lead_signals=state["lead_signals"],
        attribute_trends=state.get("attribute_trends"),
    )
    print(f"✨ [Save] 완료 (ID: {report_id})")
    return {**state, "report_id": report_id}


# ── Graph ────────────────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(CRAIState)
    graph.add_node("scout", scout_agent)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("critic", critic_node)
    graph.add_node("save", save_node)

    graph.set_entry_point("scout")
    graph.add_edge("scout", "orchestrator")
    graph.add_edge("orchestrator", "critic")
    graph.add_conditional_edges("critic", should_continue_critic, {
        "save": "save",
        "retry": "orchestrator",
    })
    graph.add_edge("save", END)
    return graph.compile()


def run_multi_agent_pipeline(days: int = 30, start_date: str = None, end_date: str = None, status_callback=None) -> Optional[int]:
    if status_callback:
        set_progress_callback(status_callback)
    app = build_graph()
    initial: CRAIState = {
        "days": days,
        "start_date": start_date,
        "end_date": end_date,
        "posts": [],
        "trend_clusters": [],
        "engagement_top": [],
        "lead_signals": [],
        "summary": "",
        "top_keywords": [],
        "style_trends": [],
        "attribute_trends": {},
        "validation_passed": False,
        "report_id": None,
        "error_messages": [],
    }
    result = app.invoke(initial)
    return result["report_id"]


if __name__ == "__main__":
    run_multi_agent_pipeline()
