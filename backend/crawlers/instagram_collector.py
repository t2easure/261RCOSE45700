import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import instaloader

from db.database import save_fashion_posts, log_crawl
from utils.image_downloader import download_images

ACCOUNTS_PATH = Path(__file__).parent.parent.parent / "config" / "instagram_accounts.json"


def load_accounts() -> tuple[list[str], list[str]]:
    with open(ACCOUNTS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("brands", []), data.get("influencers", [])


def collect_account(loader: instaloader.Instaloader, username: str, days: int = 60) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
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


def run_instagram_collector(days: int = 30) -> int:
    loader = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        compress_json=False,
        quiet=True,
    )
    try:
        loader.load_session_from_file("tjduswl8@gmail.com")
        print("[Instagram] 세션 로드 성공")
    except Exception as e:
        print(f"[Instagram] 세션 로드 실패 (비로그인 진행): {e}")
    brands, influencers = load_accounts()
    total = 0

    for username in brands:
        print(f"[Instagram] 수집 시작: @{username}")
        posts = collect_account(loader, username, days=30)
        if posts:
            download_images(posts)
            saved = save_fashion_posts(posts)
            log_crawl(source="instagram", game="fashion", status="success", count=saved)
            print(f"[Instagram] @{username}: {saved}개 저장")
            total += saved
        time.sleep(10)

    for username in influencers:
        print(f"[Instagram] 수집 시작: @{username}")
        posts = collect_account(loader, username, days=60)
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
    run_instagram_collector(days=60)
