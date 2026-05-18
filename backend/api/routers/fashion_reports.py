import psycopg2.extras
from fastapi import APIRouter, HTTPException, BackgroundTasks

from db.database import _get_connection, save_fashion_report

router = APIRouter(prefix="/fashion-reports", tags=["fashion-reports"])

_gen_status: dict = {"state": "idle", "message": ""}


def _set(state: str, message: str):
    _gen_status["state"] = state
    _gen_status["message"] = message


def _get_reports(limit: int = 20) -> list[dict]:
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM fashion_reports ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]


def _get_report(report_id: int) -> dict | None:
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM fashion_reports WHERE id = %s", (report_id,))
            row = cur.fetchone()
            return dict(row) if row else None


@router.get("/generate/status")
def generate_status():
    return _gen_status


@router.get("")
def list_reports(limit: int = 20):
    return _get_reports(limit=limit)


@router.get("/{report_id}")
def get_report(report_id: int):
    report = _get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다")
    return report


@router.post("/generate")
def generate_report(background_tasks: BackgroundTasks):
    if _gen_status["state"] == "running":
        return {"message": "리포트 생성이 이미 진행 중입니다."}

    def _run():
        from pipeline.langgraph_pipeline import scout_node, couture_md_node, CRAIState
        _set("running", "Scout — 데이터 확인 중...")
        try:
            state: CRAIState = {
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
            state = scout_node(state)
            _set("running", f"Couture MD — 트렌드 분석 중... ({state['data_count']}개 포스트)")
            state = couture_md_node(state)

            if state["error_messages"]:
                _set("error", state["error_messages"][-1])
                return

            report_id = save_fashion_report(
                summary=state["summary"],
                top_keywords=state["top_keywords"],
                style_trends=state["style_trends"],
                post_count=state["data_count"],
            )
            _set("idle", f"리포트 생성 완료 (id={report_id})")
        except Exception as e:
            _set("error", str(e))

    background_tasks.add_task(_run)
    return {"message": "리포트 생성 시작"}
