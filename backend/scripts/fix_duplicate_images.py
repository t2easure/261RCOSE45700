"""
같은 계정에서 image_url이 중복된 게시물(프로필 사진 오수집)을 찾아
재크롤링 후 DB image_url + 로컬 이미지 업데이트
"""
import os
import sys
import asyncio
import re
import json
import hashlib
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import platform
import httpx
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from db.database import _get_connection

IS_LINUX = platform.system() == "Linux"
if IS_LINUX:
    from pyvirtualdisplay import Display

DATA_DIR = Path(__file__).parent.parent / "data" / "images"
SESSION_PATH = Path(__file__).parent.parent / "data" / "instagram_session.json"


def get_duplicate_image_posts() -> list[dict]:
    """로컬 이미지 파일 MD5 기준으로 중복 파일을 찾아 DB 레코드 반환"""
    import hashlib

    # 계정별 폴더에서 MD5 중복 파일 탐색
    duplicate_filenames: set[str] = set()
    for account_dir in DATA_DIR.iterdir():
        if not account_dir.is_dir():
            continue
        hashes: dict[str, list[str]] = {}
        for f in account_dir.glob("*.jpg"):
            h = hashlib.md5(f.read_bytes()).hexdigest()
            hashes.setdefault(h, []).append(f.name)
        for files in hashes.values():
            if len(files) > 1:
                # 가장 많이 중복된 이미지 = 프로필 사진. 전부 재크롤링 대상
                for fname in files:
                    duplicate_filenames.add(f"/images/{account_dir.name}/{fname}")

    if not duplicate_filenames:
        return []

    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, post_url, image_url, account_name
                FROM fashion_posts
                WHERE source = 'instagram'
                  AND image_url = ANY(%s)
                ORDER BY account_name, post_url
            """, (list(duplicate_filenames),))
            rows = cur.fetchall()
    return [{"id": r[0], "post_url": r[1], "image_url": r[2], "account_name": r[3]} for r in rows]


def update_image_url(post_id: int, new_image_url: str):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE fashion_posts SET image_url = %s WHERE id = %s",
                (new_image_url, post_id)
            )
        conn.commit()


def save_image(image_url: str, account_name: str) -> str | None:
    save_dir = DATA_DIR / account_name
    save_dir.mkdir(parents=True, exist_ok=True)
    ext = image_url.split("?")[0].split(".")[-1]
    if ext.lower() not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"
    filename = hashlib.md5(image_url.encode()).hexdigest() + f".{ext}"
    filepath = save_dir / filename
    if filepath.exists():
        rel = filepath.relative_to(DATA_DIR)
        return f"/images/{rel.as_posix()}"
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            res = client.get(image_url, headers={"User-Agent": "Mozilla/5.0"})
            res.raise_for_status()
            filepath.write_bytes(res.content)
        rel = filepath.relative_to(DATA_DIR)
        return f"/images/{rel.as_posix()}"
    except Exception as e:
        print(f"  [이미지 저장 실패] {e}", flush=True)
        return None


async def fetch_post_image(context, post_url: str, account_name: str) -> str | None:
    """게시물 URL에서 올바른 이미지 URL 추출 (article 범위, 헤더 제외)"""
    post_page = None
    try:
        shortcode = post_url.rstrip("/").split("/")[-1].split("?")[0]
        img_idx = 0
        if "?img=" in post_url:
            img_idx = int(post_url.split("?img=")[-1]) - 1

        base_url = post_url.split("?")[0]
        post_page = await context.new_page()
        await Stealth().apply_stealth_async(post_page)
        await post_page.goto(
            base_url,
            referer=f"https://www.instagram.com/{account_name}/",
            wait_until="domcontentloaded",
            timeout=20000
        )
        try:
            await post_page.wait_for_selector('article img', timeout=5000)
        except Exception:
            pass
        await asyncio.sleep(1.5)

        # img_idx번째 슬라이드로 이동
        for _ in range(img_idx):
            next_btn = post_page.locator('button[aria-label="다음"], button[aria-label="Next"]').first
            if await next_btn.is_visible(timeout=400):
                await next_btn.click(force=True)
                await asyncio.sleep(0.7)
            else:
                break

        img_src = await post_page.evaluate("""
            () => {
                const article = document.querySelector('article');
                const scope = article || document;
                const imgs = Array.from(scope.querySelectorAll('img'));
                let best = null, bestSize = 0;
                for (const img of imgs) {
                    if (img.closest('header')) continue;
                    const w = img.naturalWidth || img.clientWidth || 0;
                    const h = img.naturalHeight || img.clientHeight || 0;
                    if (w > 200 && h > 200 && w * h > bestSize) {
                        bestSize = w * h;
                        best = img.src || img.currentSrc;
                    }
                }
                return best;
            }
        """)
        return img_src

    except Exception as e:
        print(f"  [오류] {post_url}: {e}", flush=True)
        return None
    finally:
        if post_page:
            await post_page.close()


async def run():
    ig_username = os.environ.get("INSTAGRAM_USERNAME")
    ig_password = os.environ.get("INSTAGRAM_PASSWORD")

    posts = get_duplicate_image_posts()
    print(f"[중복 이미지 수정] 대상 게시물: {len(posts)}개", flush=True)
    if not posts:
        print("중복 없음. 종료.", flush=True)
        return

    # 계정별로 그룹핑해서 출력
    from collections import Counter
    acc_counts = Counter(p["account_name"] for p in posts)
    for acc, cnt in acc_counts.most_common():
        print(f"  {acc}: {cnt}개", flush=True)

    display = None
    if IS_LINUX:
        display = Display(visible=0, size=(1280, 800))
        display.start()

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox", "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage", "--disable-gpu",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )

            # 세션 로드
            if SESSION_PATH.exists():
                try:
                    cookies = json.loads(SESSION_PATH.read_text())
                    await context.add_cookies(cookies)
                    print("[로그인] 세션 쿠키 로드 성공", flush=True)
                except Exception as e:
                    print(f"[로그인] 세션 로드 실패: {e}", flush=True)

            login_page = await context.new_page()
            await Stealth().apply_stealth_async(login_page)
            await login_page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)

            username_input = login_page.locator('input[name="username"]').first
            if await username_input.is_visible(timeout=2000):
                print("[로그인] 로그인 중...", flush=True)
                await username_input.fill(ig_username)
                await login_page.locator('input[name="password"]').first.fill(ig_password)
                await login_page.keyboard.press("Enter")
                for _ in range(30):
                    await asyncio.sleep(1)
                    if "login" not in login_page.url and not await username_input.is_visible(timeout=300):
                        break
                SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
                SESSION_PATH.write_text(json.dumps(await context.cookies(), ensure_ascii=False))

            print(f"[로그인] 완료 ({login_page.url})", flush=True)
            await login_page.close()

            for i, post in enumerate(posts):
                img_src = await fetch_post_image(context, post["post_url"], post["account_name"])

                if img_src and img_src != post["image_url"]:
                    local_path = save_image(img_src, post["account_name"])
                    if local_path:
                        update_image_url(post["id"], local_path)
                        print(f"  [{i+1}/{len(posts)}] {post['post_url']} → 이미지 교체 완료", flush=True)
                    else:
                        print(f"  [{i+1}/{len(posts)}] {post['post_url']} → 이미지 저장 실패", flush=True)
                else:
                    print(f"  [{i+1}/{len(posts)}] {post['post_url']} → 파싱 실패 또는 동일 이미지, 스킵", flush=True)

                await asyncio.sleep(2)

            await browser.close()
            print(f"\n[완료] 이미지 수정 완료!", flush=True)

    finally:
        if display:
            display.stop()


if __name__ == "__main__":
    asyncio.run(run())
