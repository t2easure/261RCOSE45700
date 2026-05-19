from typing import TypedDict, Optional
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class CRAIState(TypedDict):
    # Scout
    data_count: int
    retry_count: int
    posts: list[dict]

    # Vision
    captioning_done: bool

    # Report
    trend_titles: list[str]
    summary: str
    top_keywords: list[str]
    style_trends: list[dict]

    # Critic
    validation_passed: bool
    report_id: Optional[int]
    error_messages: list[str]


import psycopg2.extras
from db.database import _get_connection


def scout_node(state: CRAIState) -> CRAIState:
    print(f"🔍 [Scout] DB 데이터 확인 중... (시도 {state['retry_count'] + 1}회)")
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fashion_posts WHERE caption_ai IS NOT NULL")
            count = cur.fetchone()[0]
            cur.execute(
                "SELECT id, caption_ai, account_name FROM fashion_posts WHERE caption_ai IS NOT NULL ORDER BY collected_at DESC LIMIT 200"
            )
            posts = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]

    print(f"🔍 [Scout] 캡션 완료 포스트: {count}개")
    return {**state, "data_count": count, "posts": posts, "retry_count": state["retry_count"] + 1}


def should_continue_scout(state: CRAIState) -> str:
    if state["data_count"] < 50:
        if state["retry_count"] >= 3:
            print("⚠️ [Scout] 재시도 초과, 데이터 부족 상태로 진행")
            return "vision"
        print(f"⚠️ [Scout] 데이터 부족 ({state['data_count']}개), 재시도...")
        return "retry"
    return "vision"


import asyncio
from pipeline.fashion_captioner import run_captioning


def vision_node(state: CRAIState) -> CRAIState:
    print("👁️ [Vision] 캡셔닝 안 된 이미지 처리 중...")
    asyncio.run(run_captioning(batch_size=50))
    return {**state, "captioning_done": True}


import os
import json
import random
import re
import anthropic
from datetime import datetime, timezone, timedelta
from langgraph.graph import StateGraph, END
from db.database import save_fashion_report


PLANNER_PROMPT = """당신은 수석 패션 MD 에이전트입니다.
지금은 2026년이며, 분석 데이터는 모두 2026년 최신 데이터입니다.
{count}개의 데이터를 분석하여 핵심 트렌드 제목 5개를 JSON으로 응답하세요.

[데이터]
{captions}

[JSON 양식]
{{
  "summary": "2026년 시즌 전체 요약 (3줄)",
  "top_keywords": ["키워드1", "키워드2"],
  "trend_titles": ["트렌드1", "트렌드2", "트렌드3", "트렌드4", "트렌드5"]
}}"""

WRITER_PROMPT = """당신은 패션 리포트 작가 에이전트입니다.
트렌드 제목에 대해 2~3문장 분석을 작성하고, 대표 이미지 ID 2개를 매칭하세요.

[트렌드 제목]: {title}
[참고 데이터]: {captions}

[JSON 양식]
{{
  "title": "{title}",
  "content": "트렌드 상세 설명",
  "representative_ids": [ID1, ID2]
}}"""


def safe_json_parse(text):
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        raise ValueError("JSON을 찾을 수 없습니다.")
    return json.loads(re.sub(r'[\x00-\x1F\x7F]', '', match.group(0)))


def couture_md_node(state: CRAIState) -> CRAIState:
    print("🎨 [Couture MD] 트렌드 리포트 생성 중...")
    posts = state["posts"]
    if len(posts) > 200:
        posts = random.sample(posts, 200)

    captions_text = "\n".join([f"ID:{p['id']}|{p['caption_ai']}" for p in posts])
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    try:
        plan_res = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content": PLANNER_PROMPT.format(count=len(posts), captions=captions_text)}]
        )
        plan_data = safe_json_parse(plan_res.content[0].text)
        print(f"✅ [Planner] {len(plan_data['trend_titles'])}개 트렌드 선정")

        final_trends = []
        for title in plan_data["trend_titles"]:
            print(f"✍️ [Writer] '{title}' 분석 중...")
            writer_res = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                messages=[{"role": "user", "content": WRITER_PROMPT.format(title=title, captions=captions_text)}]
            )
            final_trends.append(safe_json_parse(writer_res.content[0].text))

        return {
            **state,
            "summary": plan_data["summary"],
            "top_keywords": plan_data["top_keywords"],
            "trend_titles": plan_data["trend_titles"],
            "style_trends": final_trends,
        }
    except Exception as e:
        return {**state, "error_messages": state["error_messages"] + [str(e)]}


def critic_node(state: CRAIState) -> CRAIState:
    print("🔎 [Critic] 리포트 검증 중...")
    errors = []

    if not state.get("summary"):
        errors.append("summary 없음")
    if len(state.get("trend_titles", [])) < 5:
        errors.append(f"트렌드 {len(state.get('trend_titles', []))}개 (5개 필요)")
    if len(state.get("style_trends", [])) < 5:
        errors.append("style_trends 부족")

    if errors:
        print(f"❌ [Critic] 검증 실패: {errors}")
        return {**state, "validation_passed": False, "error_messages": state["error_messages"] + errors}

    print("✅ [Critic] 검증 통과!")
    return {**state, "validation_passed": True}


def should_continue_critic(state: CRAIState) -> str:
    if not state["validation_passed"]:
        if len(state["error_messages"]) >= 3:
            print("⚠️ [Critic] 재시도 초과, 강제 저장")
            return "save"
        return "retry_report"
    return "save"


def save_node(state: CRAIState) -> CRAIState:
    print("💾 [Save] 리포트 저장 중...")
    report_id = save_fashion_report(
        summary=state["summary"],
        top_keywords=state["top_keywords"],
        style_trends=state["style_trends"],
        post_count=state["data_count"],
    )
    print(f"✨ [Save] 리포트 저장 완료! (ID: {report_id})")
    return {**state, "report_id": report_id}


def build_graph():
    graph = StateGraph(CRAIState)

    graph.add_node("scout", scout_node)
    graph.add_node("vision", vision_node)
    graph.add_node("couture_md", couture_md_node)
    graph.add_node("critic", critic_node)
    graph.add_node("save", save_node)

    graph.set_entry_point("scout")

    graph.add_conditional_edges("scout", should_continue_scout, {
        "vision": "vision",
        "retry": "scout",
    })
    graph.add_edge("vision", "couture_md")
    graph.add_edge("couture_md", "critic")
    graph.add_conditional_edges("critic", should_continue_critic, {
        "save": "save",
        "retry_report": "couture_md",
    })
    graph.add_edge("save", END)

    return graph.compile()


def run_langgraph_pipeline():
    app = build_graph()
    initial_state: CRAIState = {
        "data_count": 0,
        "retry_count": 0,
        "posts": [],
        "captioning_done": False,
        "trend_titles": [],
        "summary": "",
        "top_keywords": [],
        "style_trends": [],
        "validation_passed": False,
        "report_id": None,
        "error_messages": [],
    }
    result = app.invoke(initial_state)
    return result["report_id"]


if __name__ == "__main__":
    run_langgraph_pipeline()
