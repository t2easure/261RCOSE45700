import asyncio
import threading
from fastapi import APIRouter, BackgroundTasks
import psycopg2.extras

from db.database import _get_connection

router = APIRouter(tags=["crawl"])

_crawl_status: dict = {"state": "idle", "message": ""}
_stop_event = threading.Event()


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
        import threading
        from crawlers.brand_scraper import run_brand_scraper
        from datetime import datetime, timezone
        _set("running", "브랜드 스크래핑 중...")
        try:
            result = []
            def _scrape():
                import asyncio
                import sys
                if sys.platform == 'win32':
                    loop = asyncio.ProactorEventLoop()
                else:
                    loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(run_brand_scraper(_status_callback=_set))
                loop.close()
            t = threading.Thread(target=_scrape)
            t.start()
            t.join()
            _set("running", "Instagram 수집 중...")
            from crawlers.instagram_playwright import run_instagram_playwright
            _ig_loop = asyncio.new_event_loop()
            _ig_loop.run_until_complete(run_instagram_playwright())
            _ig_loop.close()
            _set("running", "캡셔닝(1차) 중...")
            from pipeline.fashion_captioner import run_captioning
            loop2 = asyncio.new_event_loop()
            loop2.run_until_complete(run_captioning(batch_size=200, per_account=50))
            loop2.close()
            _set("running", "메타 태그 추출(2차) 중...")
            from pipeline.meta_captioner import run_meta_captioning
            loop3 = asyncio.new_event_loop()
            loop3.run_until_complete(run_meta_captioning(batch_size=200))
            loop3.close()
            _set("running", "임베딩 중...")
            from pipeline.embedder import run_embedding
            loop4 = asyncio.new_event_loop()
            loop4.run_until_complete(run_embedding(batch_size=200))
            loop4.close()
            _set("idle", "크롤링 + 파이프라인 완료")
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

    _stop_event.clear()
    background_tasks.add_task(_run)
    return {"success": True, "message": "크롤링 시작"}


@router.post("/crawl/stop")
def stop_crawl():
    _stop_event.set()
    _set("idle", "크롤링 중단됨")
    return {"success": True, "message": "중단 신호 전송됨"}


@router.post("/crawl/set-cutoff")
def set_crawl_cutoff(body: dict):
    """인스타그램 수집 기준일 설정 (crawl_logs에 success 항목 삽입)"""
    from datetime import datetime, timezone
    cutoff_str = body.get("cutoff")
    if not cutoff_str:
        return {"success": False, "message": "cutoff 날짜가 필요합니다"}
    try:
        cutoff = datetime.fromisoformat(cutoff_str).replace(tzinfo=timezone.utc)
        with _get_connection() as conn:
            with conn.cursor() as cur:
                # 지정 날짜보다 최신인 success 로그를 모두 삭제하고 새 기준일 삽입
                cur.execute("DELETE FROM crawl_logs WHERE status='success' AND run_at > %s", (cutoff,))
                cur.execute(
                    "INSERT INTO crawl_logs (run_at, source, status) VALUES (%s, %s, %s)",
                    (cutoff, "crawl", "success"),
                )
            conn.commit()
        return {"success": True, "message": f"기준일 설정: {cutoff_str}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
