import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg2
import psycopg2.extras

from db.preprocess import preprocess
from utils.config import DATA_DIR, DATABASE_URL


def _get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL 환경변수가 설정되지 않았습니다.")
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def init_db() -> None:
    """DB 및 테이블 초기화. 없으면 생성."""
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS posts (
                    id SERIAL PRIMARY KEY,
                    url TEXT UNIQUE,
                    title TEXT,
                    content TEXT,
                    author TEXT,
                    date TEXT,
                    game TEXT,
                    source TEXT,
                    keyword TEXT,
                    views TEXT,
                    recommend TEXT,
                    raw TEXT,
                    created_at TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS crawl_logs (
                    id SERIAL PRIMARY KEY,
                    run_at TEXT,
                    source TEXT,
                    game TEXT,
                    status TEXT,
                    count INTEGER,
                    error_msg TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS trend_reports (
                    id SERIAL PRIMARY KEY,
                    created_at TEXT,
                    game TEXT,
                    period_start TEXT,
                    period_end TEXT,
                    summary TEXT,
                    category_filter TEXT,
                    category_translation TEXT,
                    category_classification TEXT,
                    category_analysis TEXT,
                    full_report TEXT,
                    keywords TEXT,
                    trend_level TEXT,
                    post_count INTEGER
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS report_posts (
                    id SERIAL PRIMARY KEY,
                    report_id INTEGER NOT NULL REFERENCES trend_reports(id) ON DELETE CASCADE,
                    post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                    evidence_role TEXT,
                    created_at TEXT,
                    UNIQUE (report_id, post_id)
                )
                """
            )
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS fashion_posts (
                    id SERIAL PRIMARY KEY,
                    source VARCHAR(20),
                    account_name VARCHAR(100),
                    post_url TEXT UNIQUE,
                    image_url TEXT,
                    caption TEXT,
                    likes INTEGER,
                    posted_at TIMESTAMP,
                    collected_at TIMESTAMP DEFAULT NOW(),
                    caption_ai TEXT,
                    caption_meta TEXT,
                    meta_at TIMESTAMP,
                    captioned_at TIMESTAMP,
                    embedding vector(384)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS fashion_reports (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT NOW(),
                    period_start TEXT,
                    period_end TEXT,
                    summary TEXT,
                    top_keywords TEXT,
                    style_trends TEXT,
                    brand_comparison TEXT,
                    full_report TEXT,
                    post_count INTEGER,
                    source_accounts TEXT
                )
                """
            )
        conn.commit()


def save_fashion_posts(items: list[dict]) -> int:
    """패션 포스팅 저장. 중복 post_url은 skip. 저장된 건수 반환."""
    if not items:
        return 0

    inserted = 0
    with _get_connection() as conn:
        with conn.cursor() as cur:
            for item in items:
                cur.execute(
                    """
                    INSERT INTO fashion_posts
                        (source, account_name, post_url, image_url, caption, likes, posted_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (post_url) DO NOTHING
                    """,
                    (
                        item.get("source"),
                        item.get("account_name"),
                        item.get("post_url"),
                        item.get("image_url"),
                        item.get("caption"),
                        item.get("likes"),
                        item.get("posted_at"),
                    ),
                )
                if cur.rowcount > 0:
                    inserted += 1
        conn.commit()
    return inserted


def get_uncaptioned_posts(limit: int = 100) -> list[dict]:
    """caption_ai 없는 패션 포스팅 조회."""
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, image_url, account_name, source
                FROM fashion_posts
                WHERE caption_ai IS NULL AND image_url IS NOT NULL
                LIMIT %s
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def save_caption(post_id: int, caption_ai: str) -> None:
    """AI 캡션 저장."""
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE fashion_posts
                SET caption_ai = %s, captioned_at = NOW()
                WHERE id = %s
                """,
                (caption_ai, post_id),
            )
        conn.commit()


def save_embedding(post_id: int, embedding: list[float]) -> None:
    """임베딩 벡터 저장."""
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE fashion_posts SET embedding = %s WHERE id = %s",
                (embedding, post_id),
            )
        conn.commit()


def get_fashion_posts_all(limit: int = 50, offset: int = 0, source: str = None) -> list[dict]:
    """전체 패션 포스팅 조회. 최신 수집순 정렬."""
    where = "WHERE TRUE"
    params: list[Any] = []
    if source:
        where += " AND source = %s"
        params.append(source)
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT id, image_url, account_name, source, posted_at, caption_ai, collected_at
                FROM fashion_posts
                {where}
                ORDER BY collected_at DESC NULLS LAST
                LIMIT %s OFFSET %s
                """,
                params + [limit, offset],
            )
            return [dict(r) for r in cur.fetchall()]


def get_fashion_stats() -> dict:
    """fashion_posts 기반 통계."""
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM fashion_posts")
            total = cur.fetchone()["cnt"]
            cur.execute("SELECT source, COUNT(*) AS cnt FROM fashion_posts GROUP BY source")
            by_source = {r["source"]: r["cnt"] for r in cur.fetchall()}
            cur.execute(
                "SELECT run_at FROM crawl_logs WHERE status = 'success' ORDER BY run_at DESC LIMIT 1"
            )
            last_run_row = cur.fetchone()
    return {
        "total": total,
        "bySource": by_source,
        "lastRun": last_run_row["run_at"] if last_run_row else None,
    }


def search_fashion_posts(query_embedding: list[float], days: int = 60, limit: int = 20) -> list[dict]:
    """벡터 유사도 기반 패션 이미지 검색."""
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, image_url, account_name, source, posted_at, caption_ai,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM fashion_posts
                WHERE posted_at >= NOW() - INTERVAL '%s days'
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (query_embedding, days, query_embedding, limit),
            )
            return [dict(row) for row in cur.fetchall()]


def save_posts(items: list[dict]) -> int:
    """아이템 리스트 저장. 중복 url은 skip. 저장된 건수 반환."""
    if not items:
        return 0

    items = preprocess(items)
    if not items:
        return 0

    now_utc = datetime.now(timezone.utc).isoformat()
    inserted = 0

    with _get_connection() as conn:
        with conn.cursor() as cur:
            for item in items:
                cur.execute(
                    """
                    INSERT INTO posts (
                        url, title, content, author, date, game, source,
                        keyword, views, recommend, raw, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO NOTHING
                    """,
                    (
                        item.get("url"),
                        item.get("title"),
                        item.get("content") or item.get("body") or item.get("description"),
                        item.get("author") or item.get("username"),
                        item.get("date") or item.get("publishDate") or item.get("createdAt"),
                        item.get("game"),
                        item.get("source"),
                        item.get("keyword"),
                        item.get("views") or item.get("view"),
                        item.get("recommend") or item.get("upvotes"),
                        json.dumps(item, ensure_ascii=False),
                        now_utc,
                    ),
                )
                if cur.rowcount > 0:
                    inserted += 1
        conn.commit()

    return inserted


def get_posts(
    game: str = None,
    source: str = None,
    since: str = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """
    조건별 posts 조회. (total, paginated rows) 반환.
    """
    where = "WHERE TRUE"
    params: list[Any] = []

    if game:
        where += " AND game = %s"
        params.append(game)
    if source:
        where += " AND source = %s"
        params.append(source)
    if since:
        where += " AND created_at >= %s"
        params.append(since)

    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT COUNT(*) AS cnt FROM posts {where}", params)
            total = cur.fetchone()["cnt"]

            cur.execute(
                f"SELECT * FROM posts {where} ORDER BY date DESC NULLS LAST LIMIT %s OFFSET %s",
                params + [limit, offset],
            )
            rows = [dict(row) for row in cur.fetchall()]

    return rows, total


def get_stats() -> dict:
    """게임별/소스별 수집 건수 반환."""
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT game, COUNT(*) AS cnt FROM posts GROUP BY game")
            by_game_rows = cur.fetchall()

            cur.execute("SELECT source, COUNT(*) AS cnt FROM posts GROUP BY source")
            by_source_rows = cur.fetchall()

            cur.execute("SELECT COUNT(*) AS cnt FROM posts")
            total_row = cur.fetchone()

            cur.execute("SELECT run_at FROM crawl_logs WHERE status = 'success' ORDER BY run_at DESC LIMIT 1")
            last_run_row = cur.fetchone()

    return {
        "by_game": {row["game"]: row["cnt"] for row in by_game_rows if row["game"]},
        "by_source": {row["source"]: row["cnt"] for row in by_source_rows if row["source"]},
        "total": total_row["cnt"] if total_row else 0,
        "last_run": last_run_row["run_at"] if last_run_row else None,
    }


def get_timeline(days: int = 14) -> list[dict]:
    """최근 N일간 날짜별 소스별 수집 건수 반환."""
    threshold = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    LEFT(created_at, 10) AS date,
                    source,
                    COUNT(*) AS cnt
                FROM posts
                WHERE created_at >= %s AND source IS NOT NULL
                GROUP BY LEFT(created_at, 10), source
                ORDER BY date ASC
                """,
                (threshold,),
            )
            return [dict(row) for row in cur.fetchall()]


def delete_expired_posts(days: int = 30) -> int:
    """created_at 기준 days일 이상 지난 posts 삭제. 삭제된 건수 반환."""
    threshold = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM posts WHERE created_at < %s", (threshold,))
            deleted = cur.rowcount
        conn.commit()

    return deleted


def delete_expired_json_files(days: int = 30) -> int:
    """
    data/{플랫폼}/{game}/ 디렉토리의 JSON 파일 중
    파일명 날짜(YYYY-MM-DD) 기준 days일 이상 지난 파일 삭제.
    삭제된 파일 수 반환.
    """
    threshold_date = (datetime.now() - timedelta(days=days)).date()
    removed = 0

    for platform in ("reddit", "bilibili", "inven"):
        platform_dir = os.path.abspath(os.path.join(DATA_DIR, platform))
        if not os.path.isdir(platform_dir):
            continue

        for game in os.listdir(platform_dir):
            game_dir = os.path.join(platform_dir, game)
            if not os.path.isdir(game_dir):
                continue

            for filename in os.listdir(game_dir):
                if not filename.endswith(".json"):
                    continue

                date_prefix = filename[:10]
                try:
                    file_date = datetime.strptime(date_prefix, "%Y-%m-%d").date()
                except ValueError:
                    continue

                if file_date < threshold_date:
                    os.remove(os.path.join(game_dir, filename))
                    removed += 1

    return removed


def log_crawl(
    source: str,
    game: str,
    status: str,
    count: int = 0,
    error_msg: str = None,
) -> None:
    """크롤링 실행 결과를 crawl_logs 테이블에 기록."""
    run_at = datetime.now(timezone.utc).isoformat()
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO crawl_logs (run_at, source, game, status, count, error_msg)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (run_at, source, game, status, count, error_msg),
            )
        conn.commit()


def get_crawl_logs(limit: int = 50) -> list[dict]:
    """최근 crawl_logs 조회. 최신순 정렬."""
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, run_at, source, game, status, count, error_msg
                FROM crawl_logs
                ORDER BY run_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]


def save_report(report: dict) -> int:
    """보고서 저장. 저장된 id 반환."""
    now_utc = datetime.now(timezone.utc).isoformat()
    keywords = report.get("keywords")
    if isinstance(keywords, list):
        keywords = ",".join(keywords)
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO trend_reports (
                    created_at, game, period_start, period_end,
                    summary, category_filter, category_translation,
                    category_classification, category_analysis, full_report,
                    keywords, trend_level, post_count
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    now_utc,
                    report.get("game"),
                    report.get("period_start"),
                    report.get("period_end"),
                    report.get("summary"),
                    report.get("category_filter"),
                    report.get("category_translation"),
                    report.get("category_classification"),
                    report.get("category_analysis"),
                    report.get("full_report"),
                    keywords,
                    report.get("trend_level"),
                    report.get("post_count"),
                ),
            )
            report_id = cur.fetchone()[0]
        conn.commit()
    return report_id


def get_reports(game: str = None, limit: int = 20) -> list[dict]:
    """보고서 목록 조회. 최신순."""
    query = "SELECT * FROM trend_reports WHERE TRUE"
    params: list[Any] = []
    if game:
        query += " AND game = %s"
        params.append(game)
    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            rows = [dict(row) for row in cur.fetchall()]
            for r in rows:
                if r.get("keywords"):
                    r["keywords"] = r["keywords"].split(",")
                else:
                    r["keywords"] = []
            return rows


def get_report(report_id: int) -> dict | None:
    """보고서 단건 조회."""
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM trend_reports WHERE id = %s", (report_id,))
            row = cur.fetchone()
            if not row:
                return None
            r = dict(row)
            r["keywords"] = r["keywords"].split(",") if r.get("keywords") else []
            return r


def delete_report(report_id: int) -> bool:
    """보고서 삭제. 삭제 성공 여부 반환."""
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM trend_reports WHERE id = %s", (report_id,))
            deleted = cur.rowcount > 0
        conn.commit()
    return deleted


def get_uncaptioned_meta_posts(limit: int = 100) -> list[dict]:
    """caption_ai는 있는데 caption_meta가 없는 포스트 조회."""
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, caption_ai, image_url, account_name
                FROM fashion_posts
                WHERE caption_ai IS NOT NULL AND caption_meta IS NULL
                LIMIT %s
                """,
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]


def save_caption_meta(post_id: int, meta: str) -> None:
    """2차 캡셔닝 결과 저장."""
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE fashion_posts SET caption_meta = %s, meta_at = NOW() WHERE id = %s",
                (meta, post_id),
            )
        conn.commit()
