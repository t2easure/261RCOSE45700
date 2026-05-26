import psycopg2.extras
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from db.database import _get_connection, save_fashion_report

router = APIRouter(prefix="/fashion-reports", tags=["fashion-reports"])

_gen_status: dict = {"state": "idle", "message": ""}


class GenerateRequest(BaseModel):
    days: int = 30
    start_date: str = None
    end_date: str = None


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


@router.get("/count")
def get_post_count(start_date: str = None, end_date: str = None):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            if start_date and end_date:
                cur.execute(
                    "SELECT COUNT(*) FROM fashion_posts WHERE caption_ai IS NOT NULL AND posted_at >= %s AND posted_at < (%s::date + interval '1 day')",
                    (start_date, end_date),
                )
            else:
                cur.execute("SELECT COUNT(*) FROM fashion_posts WHERE caption_ai IS NOT NULL")
            count = cur.fetchone()[0]
    return {"count": count}


@router.get("")
def list_reports(limit: int = 20):
    return _get_reports(limit=limit)


@router.get("/{report_id}")
def get_report(report_id: int):
    report = _get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다")
    return report


@router.delete("/{report_id}")
def delete_report(report_id: int):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM fashion_reports WHERE id = %s", (report_id,))
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="리포트를 찾을 수 없습니다")
        conn.commit()
    return {"message": "삭제 완료"}


@router.post("/generate")
def generate_report(req: GenerateRequest, background_tasks: BackgroundTasks):
    if _gen_status["state"] == "running":
        return {"message": "리포트 생성이 이미 진행 중입니다."}

    days = req.days
    start_date = req.start_date
    end_date = req.end_date

    def _run():
        from pipeline.multi_agent_pipeline import run_multi_agent_pipeline
        _set("running", "Scout — 데이터 수집 중...")
        try:
            report_id = run_multi_agent_pipeline(days=days, start_date=start_date, end_date=end_date)
            _set("idle", f"리포트 생성 완료 (id={report_id})")
        except Exception as e:
            _set("error", str(e))

    background_tasks.add_task(_run)
    return {"message": "리포트 생성 시작"}
