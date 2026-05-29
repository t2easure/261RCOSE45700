"""
최근 N개 게시물에 대해 1차 캡셔닝 → 2차 메타 캡셔닝 → 임베딩 순서로 실행.
Usage: python run_recent.py [N=30]
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from db.database import _get_connection


def get_recent_uncaptioned(limit: int):
    """캡셔닝 안 된 게시물 중 가장 최근 N개 반환"""
    import psycopg2.extras
    conn = _get_connection()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT id, image_url, account_name, source
               FROM fashion_posts
               WHERE (caption_ai IS NULL OR caption_ai = '') AND image_url IS NOT NULL
               ORDER BY posted_at DESC NULLS LAST, id DESC
               LIMIT %s""",
            (limit,)
        )
        return [dict(r) for r in cur.fetchall()]


async def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 30

    posts = get_recent_uncaptioned(limit)
    print(f"1차 캡셔닝 대상: {len(posts)}개")

    if not posts:
        print("✅ 캡셔닝할 게시물 없음")
        return

    import pipeline.fashion_captioner as fc
    original = fc.get_uncaptioned_posts
    ids = {p['id'] for p in posts}

    def _get_recent(limit=None, per_account=None, since=None, empty_only=False):
        return posts

    fc.get_uncaptioned_posts = _get_recent
    await fc.run_captioning(batch_size=len(posts), per_account=len(posts))
    fc.get_uncaptioned_posts = original
    print("✅ 1차 캡셔닝 완료")

    from pipeline.meta_captioner import run_meta_captioning
    from pipeline.embedder import run_embedding

    print("\n📝 2차 메타 캡셔닝 시작...")
    await run_meta_captioning(batch_size=len(posts) + 10)
    print("✅ 2차 캡셔닝 완료")

    print("\n🔢 임베딩 시작...")
    embedded = run_embedding(batch_size=len(posts) + 10)
    print(f"✅ 임베딩 완료 ({embedded}개)")


if __name__ == "__main__":
    asyncio.run(main())
