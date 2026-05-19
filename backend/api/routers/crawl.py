import asyncio
from fastapi import APIRouter, BackgroundTasks
import psycopg2.extras

from db.database import _get_connection

router = APIRouter(tags=["crawl"])

_crawl_status: dict = {"state": "idle", "message": ""}


def _set(state: str, message: str):
    _crawl_status["state"] = state
    _crawl_status["message"] = message


@router.get("/logs")
def get_logs(limit: int = 20):
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM crawl_logs ORDER BY run_at DESC LIMIT %s",
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]


@router.post("/crawl")
def run_crawl(background_tasks: BackgroundTasks):
    if _crawl_status["state"] == "running":
        return {"success": False, "message": "크롤링이 이미 실행 중입니다."}

    def _run():
        from crawlers.brand_scraper import run_brand_scraper
        from crawlers.instagram_collector import run_instagram_collector
        from datetime import datetime, timezone
        _set("running", "브랜드 스크래핑 중...")
        try:
            asyncio.run(run_brand_scraper())
            _set("running", "Instagram 수집 중...")
            run_instagram_collector()
            _set("idle", "크롤링 완료")
            # 완료 로그 저장
            now = datetime.now(timezone.utc).isoformat()
            with _get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO crawl_logs (run_at, source, status, count) VALUES (%s, %s, %s, %s)",
                        (now, "pipeline", "success", 0),
                    )
                conn.commit()
        except Exception as e:
            _set("error", str(e))
            now = datetime.now(timezone.utc).isoformat()
            with _get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO crawl_logs (run_at, source, status, error_msg) VALUES (%s, %s, %s, %s)",
                        (now, "pipeline", "error", str(e)),
                    )
                conn.commit()

    background_tasks.add_task(_run)
    return {"success": True, "message": "크롤링 시작"}
