import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import instaloader

from db.database import save_fashion_posts, log_crawl, _get_connection
from utils.image_downloader import download_images

ACCOUNTS_PATH = Path(__file__).parent.parent.parent / "config" / "instagram_accounts.json"


def load_accounts() -> tuple[list[str], list[str]]:
    with open(ACCOUNTS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("brands", []), data.get("influencers", [])


def get_last_crawl_time() -> datetime:
    try:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT run_at FROM crawl_logs WHERE status='success' ORDER BY run_at DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    from dateutil.parser import parse
                    from datetime import timedelta
                    KST = timezone(timedelta(hours=9))
                    dt = parse(str(row[0]))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=KST)
                    return dt.astimezone(timezone.utc)
    except Exception:
        pass
    return datetime.now(timezone.utc) - timedelta(days=7)


def collect_account(loader: instaloader.Instaloader, username: str, cutoff: datetime = None) -> list[dict]:
    if cutoff is None:
        cutoff = get_last_crawl_time()
    posts = []

    try:
        profile = instaloader.Profile.from_username(loader.context, username)
        for post in profile.get_posts():
            if post.date_utc.replace(tzinfo=timezone.utc) < cutoff:
                break
            if not post.url:
                continue
            posts.append({
                "source": "instagram",
                "account_name": username,
                "post_url": f"https://www.instagram.com/p/{post.shortcode}/",
                "image_url": post.url,
                "caption": post.caption or "",
                "likes": post.likes,
                "comments": post.comments,
                "followers": profile.followers,
                "posted_at": post.date_utc,
            })
            print(f"[Instagram] @{username} 수집: {post.shortcode} ({post.date_utc.date()}) 좋아요 {post.likes}")
            time.sleep(3)  # rate limit 대응
    except Exception as e:
        print(f"[Instagram] {username} 수집 실패: {e}")
        log_crawl(source="instagram", game="fashion", status="error", error_msg=str(e))
        return []

    return posts


def run_instagram_collector() -> int:
    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        compress_json=False,
        quiet=True,
    )
    try:
        loader.load_session_from_file("tieusian_freaky")
        print("[Instagram] 세션 로드 성공")
    except Exception as e:
        print(f"[Instagram] 세션 로드 실패 (비로그인 진행): {e}")
    brands, influencers = load_accounts()
    cutoff = get_last_crawl_time()
    print(f"[Instagram] 마지막 크롤링 기준: {cutoff.strftime('%Y-%m-%d %H:%M')} 이후 수집")
    total = 0

    for username in brands + influencers:
        print(f"[Instagram] 수집 시작: @{username}")
        posts = collect_account(loader, username, cutoff=cutoff)
        if posts:
            download_images(posts)
            saved = save_fashion_posts(posts)
            log_crawl(source="instagram", game="fashion", status="success", count=saved)
            print(f"[Instagram] @{username}: {saved}개 저장")
            total += saved
        time.sleep(10)

    print(f"[Instagram] 전체 완료: {total}개 저장")
    return total


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        from dateutil.parser import parse as parse_date
        override = parse_date(sys.argv[1]).replace(tzinfo=timezone.utc)
        print(f"[Instagram] 날짜 오버라이드: {override}")
        brands, influencers = load_accounts()
        loader = instaloader.Instaloader(download_pictures=False, download_videos=False,
                                         download_video_thumbnails=False, compress_json=False, quiet=True)
        try:
            loader.load_session_from_file("tieusian_freaky")
        except Exception as e:
            print(f"[Instagram] 세션 로드 실패: {e}")
        total = 0
        import time as _time
        for username in brands + influencers:
            print(f"[Instagram] 수집 시작: @{username}")
            posts = collect_account(loader, username, cutoff=override)
            if posts:
                from utils.image_downloader import download_images
                download_images(posts)
                from db.database import save_fashion_posts, log_crawl
                saved = save_fashion_posts(posts)
                log_crawl(source="instagram", game="fashion", status="success", count=saved)
                print(f"[Instagram] @{username}: {saved}개 저장")
                total += saved
            _time.sleep(10)
        print(f"[Instagram] 전체 완료: {total}개 저장")
    else:
        run_instagram_collector()
