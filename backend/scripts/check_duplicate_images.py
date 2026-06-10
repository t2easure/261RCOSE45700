"""
재스크래핑 후 중복된 image_url(=프로필 사진 오인식 가능성)을 가진 포스트 탐색.
"""
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import _get_connection


def main():
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, image_url, account_name, post_url
                FROM fashion_posts
                WHERE image_url LIKE '/images/%'
                ORDER BY account_name, image_url
            """)
            rows = cur.fetchall()

    by_url = defaultdict(list)
    for (id_, image_url, account_name, post_url) in rows:
        by_url[image_url].append({"id": id_, "account_name": account_name, "post_url": post_url})

    dups = {url: posts for url, posts in by_url.items() if len(posts) > 1}

    print(f"총 {len(by_url)}개 고유 image_url, 그중 {len(dups)}개가 중복됨\n")
    total_dup_posts = 0
    for url, posts in dups.items():
        print(f"{url}  ({len(posts)}개 포스트 공유)")
        for p in posts:
            print(f"    ID #{p['id']} ({p['account_name']}) - {p['post_url']}")
        total_dup_posts += len(posts)
        print()

    print(f"중복에 연루된 포스트 총 {total_dup_posts}개")


if __name__ == "__main__":
    main()
