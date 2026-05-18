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
    return {**state, "data_count": count, "posts": posts}


def should_continue_scout(state: CRAIState) -> str:
    if state["data_count"] < 50:
        if state["retry_count"] >= 3:
            print("⚠️ [Scout] 재시도 초과, 데이터 부족 상태로 진행")
            return "vision"
        print(f"⚠️ [Scout] 데이터 부족 ({state['data_count']}개), 재시도...")
        return "retry"
    return "vision"
