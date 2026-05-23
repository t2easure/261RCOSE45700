from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import init_db, get_fashion_posts_all, get_fashion_stats, _get_connection
from api.routers import search, fashion_reports, pipeline, crawl, config_manager

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
app.include_router(crawl.router)
app.include_router(config_manager.router)


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
