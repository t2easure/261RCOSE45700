from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import init_db, get_fashion_posts_all, get_fashion_stats, _get_connection
from api.routers import search, fashion_reports, pipeline

app = FastAPI(title="CRAI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


app.include_router(search.router)
app.include_router(fashion_reports.router)
app.include_router(pipeline.router)


@app.get("/stats")
def stats():
    data = get_fashion_stats()
    # 캡셔닝 완료 수 추가
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fashion_posts WHERE caption_ai IS NOT NULL")
            data["captioned"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM fashion_posts WHERE caption_meta IS NOT NULL")
            data["meta_captioned"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM fashion_posts WHERE embedding IS NOT NULL")
            data["embedded"] = cur.fetchone()[0]
    return data


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
