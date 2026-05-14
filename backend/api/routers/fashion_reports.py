import psycopg2.extras
from fastapi import APIRouter, HTTPException, BackgroundTasks

from db.database import _get_connection
from pipeline.report_generator import run_report_generator

router = APIRouter(prefix="/fashion-reports", tags=["fashion-reports"])


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
def generate_report(background_tasks: BackgroundTasks, days: int = 14):
    background_tasks.add_task(run_report_generator, days=days)
    return {"message": f"리포트 생성 시작 (최근 {days}일 데이터)"}
