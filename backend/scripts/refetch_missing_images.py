"""
누락/만료된 이미지를 재다운로드하는 스크립트.

동작:
1. DB에서 image_url이 http로 시작하는 포스트 → 직접 재다운로드 시도
2. image_url이 /images/로 시작하지만 파일이 없는 포스트 → post_url로 playwright 재스크래핑
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from db.database import _get_connection
from utils.image_downloader import download_image

DATA_DIR = Path(__file__).parent.parent / "data" / "images"


def get_broken_posts() -> list[dict]:
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, image_url, post_url, account_name
                FROM fashion_posts
                WHERE image_url IS NOT NULL
                ORDER BY id
            """)
            rows = cur.fetchall()

    broken = []
    for (id_, image_url, post_url, account_name) in rows:
        if image_url.startswith("http"):
            broken.append({"id": id_, "image_url": image_url, "post_url": post_url, "account_name": account_name, "type": "http"})
        elif image_url.startswith("/images/"):
            local_path = DATA_DIR / image_url[len("/images/"):]
            if not local_path.exists():
                broken.append({"id": id_, "image_url": image_url, "post_url": post_url, "account_name": account_name, "type": "missing_local"})

    return broken


def update_image_url(post_id: int, new_url: str):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE fashion_posts SET image_url = %s WHERE id = %s", (new_url, post_id))
        conn.commit()


def try_redownload_http(post: dict) -> bool:
    """http URL에서 직접 재다운로드."""
    path = download_image(post["image_url"], post["account_name"] or "unknown")
    if path:
        rel = Path(path).relative_to(DATA_DIR)
        update_image_url(post["id"], f"/images/{rel.as_posix()}")
        return True
    return False


async def try_rescrape_playwright(post: dict) -> str | None:
    """post_url로 playwright 재스크래핑해서 새 이미지 URL 반환."""
    if not post.get("post_url"):
        return None
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(post["post_url"], timeout=15000)
            await page.wait_for_timeout(3000)

            # 인스타 포스트 본문 이미지: naturalWidth가 가장 큰 이미지를 선택 (프로필 사진 제외)
            # 로그인 월에서는 <article> 태그가 없을 수 있으므로 article 한정하지 않음
            src = await page.evaluate("""
                () => {
                    const imgs = Array.from(document.querySelectorAll('img'))
                        .filter(img => /cdninstagram|fbcdn/.test(img.src));
                    if (imgs.length === 0) return null;
                    imgs.sort((a, b) => (b.naturalWidth * b.naturalHeight) - (a.naturalWidth * a.naturalHeight));
                    return imgs[0].src;
                }
            """)
            await browser.close()
            return src
    except Exception as e:
        print(f"  playwright 실패: {e}")
        return None


async def main():
    print("🔍 broken 이미지 탐색 중...")
    broken = get_broken_posts()
    print(f"  → {len(broken)}개 발견\n")

    http_posts = [p for p in broken if p["type"] == "http"]
    missing_posts = [p for p in broken if p["type"] == "missing_local"]

    print(f"[1] http URL 직접 재다운로드: {len(http_posts)}개")
    ok = fail = 0
    for post in http_posts:
        if try_redownload_http(post):
            ok += 1
        else:
            fail += 1
    print(f"  ✓ {ok}개 성공, ✗ {fail}개 실패\n")

    print(f"[2] 로컬 파일 누락 → playwright 재스크래핑: {len(missing_posts)}개")
    ok = fail = 0
    for i, post in enumerate(missing_posts):
        print(f"  [{i+1}/{len(missing_posts)}] ID #{post['id']} ({post['account_name']})", end=" ... ")
        new_src = await try_rescrape_playwright(post)
        if new_src:
            path = download_image(new_src, post["account_name"] or "unknown")
            if path:
                rel = Path(path).relative_to(DATA_DIR)
                update_image_url(post["id"], f"/images/{rel.as_posix()}")
                print("✓")
                ok += 1
                continue
        print("✗")
        fail += 1

    print(f"\n완료: ✓ {ok}개 복구, ✗ {fail}개 실패")


if __name__ == "__main__":
    asyncio.run(main())
