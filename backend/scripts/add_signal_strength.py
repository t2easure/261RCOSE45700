"""
기존 fashion_reports의 trend_clusters에 signal_strength, top_influencers, material_dist 후처리 추가
실행: cd backend && python -m scripts.add_signal_strength
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from db.database import _get_connection

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

BRAND_ACCOUNTS = {"hm_women", "spao_women", "topten_women", "uniqlo_women", "zara_women",
                  "hm", "zara", "spao", "topten", "uniqlo"}


def calc_signal_strength(cluster: dict, lead_signals: list, period_brand_ratio: float = 0.0) -> float:
    volume_score = min(cluster.get("post_count", 0) / 50 * 3, 3.0)
    eng_score = min(cluster.get("avg_engagement_rate", 0) / 0.02 * 3, 3.0)
    brand_ratio = cluster.get("brand_ratio", period_brand_ratio)
    brand_score = round((1 - brand_ratio) * 2, 4)
    lead_score = 0.0
    for sig in lead_signals:
        if sig.get("trend_name") == cluster.get("trend_name"):
            days = sig.get("days_ahead")
            lead_score = 2.0 if days is None else min(days / 30 * 2, 2.0)
            break
    return round(volume_score + eng_score + brand_score + lead_score, 2)


def classify_signal(score: float, brand_ratio: float = 0.0, has_brand_ratio: bool = False) -> str:
    if has_brand_ratio and brand_ratio > 0.4: return "saturated"
    if score >= 8:   return "opportunity"
    elif score >= 5: return "growing"
    elif score >= 3: return "moderate"
    else:            return "weak"


def calc_cluster_brand_ratio(cluster: dict, period_posts: list[dict]) -> float:
    """클러스터 트렌드명 키워드로 관련 포스트를 찾아 브랜드 비율 근사"""
    trend_name = cluster.get("trend_name", "")
    keywords = [w for w in trend_name.split() if len(w) >= 2]
    if not keywords:
        return round(sum(1 for p in period_posts if p.get("account_name") in BRAND_ACCOUNTS) / max(len(period_posts), 1), 4)

    matched = [p for p in period_posts
               if any(kw in (p.get("caption_ai") or "") for kw in keywords)]
    if not matched:
        matched = period_posts  # 매칭 없으면 전체 근사
    brand_count = sum(1 for p in matched if p.get("account_name") in BRAND_ACCOUNTS)
    return round(brand_count / max(len(matched), 1), 4)


def get_period_posts(period_start: str, period_end: str) -> list[dict]:
    """리포트 기간의 fashion_posts 조회"""
    if not period_start or not period_end:
        return []
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT account_name, caption_ai, likes, comments, followers, image_url
                FROM fashion_posts
                WHERE caption_ai IS NOT NULL
                  AND posted_at >= %s AND posted_at < (%s::date + interval '1 day')
                LIMIT 2000
            """, (period_start, period_end))
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


def calc_top_influencers(posts: list[dict]) -> list[dict]:
    scored = {}
    for p in posts:
        acc = p["account_name"]
        if acc in BRAND_ACCOUNTS:
            continue
        followers = p.get("followers") or 0
        if followers < 100:
            continue
        rate = ((p.get("likes") or 0) + (p.get("comments") or 0)) / followers
        if acc not in scored or rate > scored[acc]["engagement_rate"]:
            scored[acc] = {
                "account_name": acc,
                "followers": followers,
                "engagement_rate": round(rate, 4),
                "image_url": p.get("image_url", ""),
            }
    return sorted(scored.values(), key=lambda x: x["engagement_rate"], reverse=True)[:3]


def calc_material_dist(posts: list[dict]) -> list[dict]:
    mat_count: dict = {}
    for p in posts:
        cap = (p.get("caption_ai") or "").lower()
        for mat, kws in MATERIAL_MAP.items():
            if any(k in cap for k in kws):
                mat_count[mat] = mat_count.get(mat, 0) + 1
    total = sum(mat_count.values()) or 1
    return [{"material": m, "pct": round(c / total * 100)}
            for m, c in sorted(mat_count.items(), key=lambda x: -x[1])]


def main():
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, trend_clusters, lead_signals, period_start, period_end
                FROM fashion_reports ORDER BY id
            """)
            rows = cur.fetchall()

    print(f"총 {len(rows)}개 리포트 처리 시작...")

    updated = 0
    for report_id, raw_clusters, raw_leads, period_start, period_end in rows:
        if not raw_clusters:
            print(f"  [#{report_id}] trend_clusters 없음, 스킵")
            continue

        clusters = raw_clusters if isinstance(raw_clusters, list) else json.loads(raw_clusters)
        leads = raw_leads if isinstance(raw_leads, list) else (json.loads(raw_leads) if raw_leads else [])

        # 기간별 포스트 조회
        ps = str(period_start)[:10] if period_start else None
        pe = str(period_end)[:10] if period_end else None
        period_posts = get_period_posts(ps, pe) if ps and pe else []

        top_influencers = calc_top_influencers(period_posts) if period_posts else []
        material_dist = calc_material_dist(period_posts) if period_posts else []

        # 기간 전체 브랜드 비율 (클러스터별 brand_ratio 없는 기존 리포트용 근사값)
        brand_count = sum(1 for p in period_posts if p.get("account_name") in BRAND_ACCOUNTS)
        period_brand_ratio = round(brand_count / max(len(period_posts), 1), 4)

        for c in clusters:
            # 클러스터별 brand_ratio 계산 (없으면 트렌드명 키워드 매칭으로 근사)
            if "brand_ratio" not in c:
                c["brand_ratio"] = calc_cluster_brand_ratio(c, period_posts) if period_posts else period_brand_ratio
            score = calc_signal_strength(c, leads, period_brand_ratio)
            c["signal_strength"] = score
            c["signal_label"] = classify_signal(score, c["brand_ratio"], has_brand_ratio=True)
            # 기존 리포트는 클러스터별 데이터 없으므로 전체 기간 데이터로 근사
            if "top_influencers" not in c:
                c["top_influencers"] = top_influencers
            if "material_dist" not in c:
                c["material_dist"] = material_dist

        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE fashion_reports SET trend_clusters = %s WHERE id = %s",
                    (json.dumps(clusters, ensure_ascii=False), report_id)
                )
            conn.commit()

        scores = [c["signal_strength"] for c in clusters]
        print(f"  [#{report_id}] {ps}~{pe} | 클러스터 {len(clusters)}개 | 신호강도: {scores} | 인플루언서: {len(top_influencers)}명 | 소재: {len(material_dist)}종")
        updated += 1

    print(f"\n완료! {updated}개 리포트 업데이트됨")


if __name__ == "__main__":
    main()
