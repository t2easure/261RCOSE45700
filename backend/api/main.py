from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta

from db.database import init_db, get_fashion_posts_all, get_fashion_stats, _get_connection
from api.routers import search, fashion_reports, pipeline, crawl, config_manager

app = FastAPI(title="CRAI API")

scheduler = BackgroundScheduler(timezone="Asia/Seoul")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
    allow_methods=["*"],
    allow_headers=["*"],
)


IMAGES_DIR = Path(__file__).parent.parent / "data" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")


def _run_weekly_report():
    from pipeline.multi_agent_pipeline import run_multi_agent_pipeline
    end = datetime.now().date()
    start = end - timedelta(days=7)
    print(f"[Scheduler] 주간 리포트 생성: {start} ~ {end}")
    run_multi_agent_pipeline(days=7, start_date=str(start), end_date=str(end))

def _run_monthly_report():
    from pipeline.multi_agent_pipeline import run_multi_agent_pipeline
    end = datetime.now().date()
    start = end - timedelta(days=30)
    print(f"[Scheduler] 월간 리포트 생성: {start} ~ {end}")
    run_multi_agent_pipeline(days=30, start_date=str(start), end_date=str(end))

@app.on_event("startup")
def startup():
    init_db()
    # 매주 월요일 새벽 3시 주간 리포트
    scheduler.add_job(_run_weekly_report, CronTrigger(day_of_week="mon", hour=3, minute=0), id="weekly_report", replace_existing=True)
    # 매월 1일 새벽 4시 월간 리포트
    scheduler.add_job(_run_monthly_report, CronTrigger(day=1, hour=4, minute=0), id="monthly_report", replace_existing=True)
    scheduler.start()
    print("[Scheduler] 스케줄러 시작 — 주간 리포트 월요일 03:00 / 월간 리포트 1일 04:00")


@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()


app.include_router(search.router)
app.include_router(fashion_reports.router)
app.include_router(pipeline.router)
app.include_router(crawl.router)
app.include_router(config_manager.router)


@app.get("/stats")
def stats():
    data = get_fashion_stats()
    # 캡셔닝 완료 수 추가
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fashion_posts WHERE caption_ai IS NOT NULL AND caption_ai != ''")
            data["captioned"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM fashion_posts WHERE caption_meta IS NOT NULL")
            data["meta_captioned"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM fashion_posts WHERE embedding IS NOT NULL")
            data["embedded"] = cur.fetchone()[0]
    return data


@app.get("/keywords")
def top_keywords(limit: int = 10):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT caption_meta FROM fashion_posts WHERE caption_meta IS NOT NULL")
            rows = cur.fetchall()
    from collections import Counter
    counter = Counter()
    for (meta,) in rows:
        for kw in [k.strip() for k in meta.split(",") if k.strip()]:
            counter[kw] += 1
    return [kw for kw, _ in counter.most_common(limit)]


@app.get("/posts/by-ids")
def posts_by_ids(ids: str):
    id_list = [int(i) for i in ids.split(",") if i.strip().isdigit()]
    if not id_list:
        return []
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, image_url, account_name FROM fashion_posts WHERE id = ANY(%s)",
                (id_list,)
            )
            rows = cur.fetchall()
    return [{"id": r[0], "image_url": r[1], "account_name": r[2]} for r in rows]


@app.get("/posts")
def posts(source: str = None, limit: int = 50, offset: int = 0):
    rows = get_fashion_posts_all(limit=limit, offset=offset, source=source)
    return {
        "total": len(rows),
        "items": [
            {
                "id": r["id"],
                "image_url": r["image_url"],
                "account_name": r["account_name"],
                "source": r["source"],
                "posted_at": str(r["posted_at"]) if r["posted_at"] else None,
                "caption_ai": r["caption_ai"],
                "caption_meta": r.get("caption_meta"),
            }
            for r in rows
        ],
    }
