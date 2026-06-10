"""
중복 콘텐츠(placeholder로 덮어써진) 이미지를 가진 게시물을 다시 크롤링하여
원본 이미지로 복구하는 스크립트.

대상: 같은 계정 내에서 image 파일 콘텐츠(MD5)가 동일한 게시물 그룹
(서로 다른 post_url/날짜인데 파일만 깨진 placeholder로 동일한 경우)

각 대상 게시물에 대해:
 1. post_url로 재방문 (캐러셀 슬라이드면 ?img=N 만큼 다음 버튼 클릭)
 2. 실제 이미지 src 추출 후 새로 다운로드
 3. fashion_posts.image_url 갱신, caption_ai/caption_meta/embedding 초기화
    (다음 캡셔닝/임베딩 파이프라인에서 재생성되도록)
"""
import asyncio
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from db.database import _get_connection, _image_content_hash, _local_image_path
from utils.image_downloader import download_image

SESSION_PATH = Path(__file__).parent.parent / "data" / "instagram_session.json"


async def load_session(context) -> bool:
    if not SESSION_PATH.exists():
        return False
    try:
        cookies = json.loads(SESSION_PATH.read_text())
        await context.add_cookies(cookies)
        print("[Instagram] 세션 로드 성공", flush=True)
        return True
    except Exception as e:
        print(f"[Instagram] 세션 로드 실패: {e}", flush=True)
        return False


async def login(page, username: str, password: str) -> bool:
    try:
        print("[Instagram] 로그인 상태 점검을 위해 메인 홈 진입 중...", flush=True)
        await page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)

        username_input = page.locator('input[name="username"]').first
        login_btn_visible = await page.locator('button:has-text("로그인"), a:has-text("로그인")').first.is_visible(timeout=1000)

        if not await username_input.is_visible(timeout=1000) and not login_btn_visible:
            if "login" not in page.url:
                print(f"[Instagram] 자동 로그인 성공 감지! (현재 위치: {page.url})", flush=True)
                return True

        print("[Instagram] 로그아웃 상태 확인됨. 로그인 절차 진행.", flush=True)

        for sel in ['[data-testid="cookie-policy-manage-dialog-accept-button"]', 'button:has-text("Allow")', 'button:has-text("허용")']:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=500):
                    await btn.click()
                    break
            except Exception:
                pass

        await username_input.fill(username)
        await asyncio.sleep(0.5)
        await page.locator('input[name="password"]').first.fill(password)
        await asyncio.sleep(0.5)
        await page.keyboard.press('Enter')
        print("[Instagram] 로그인 정보 제출 완료. 메인 화면 전환 감시 시작...", flush=True)

        for _ in range(60):
            await asyncio.sleep(1)
            current_url = page.url
            has_input = await page.locator('input[name="username"]').is_visible(timeout=100)
            if not has_input and ("login" not in current_url or "explore" in current_url):
                print(f"[Instagram] 최종 로그인 성공 확인! (위치: {current_url})", flush=True)
                await asyncio.sleep(3)
                return True

        print("[Instagram] 로그인 제한시간 초과", flush=True)
        return False
    except Exception as e:
        print(f"[Instagram] 로그인 로직 에러: {e}", flush=True)
        return False


def find_corrupted_groups() -> list[dict]:
    """계정 내 콘텐츠 해시가 동일한 게시물 그룹(2개 이상)을 찾아 대상 목록 반환."""
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, account_name, post_url, image_url
                FROM fashion_posts
                WHERE source = 'instagram' AND image_url LIKE '/images/%'
            """)
            rows = cur.fetchall()

    by_hash: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        post_id, account, post_url, image_url = r[0], r[1], r[2], r[3]
        path = _local_image_path(image_url)
        if path is None or not path.exists():
            continue
        h = _image_content_hash(str(path), path.stat().st_mtime)
        if not h:
            continue
        by_hash[(account, h)].append({
            "id": post_id, "account_name": account,
            "post_url": post_url, "image_url": image_url,
        })

    targets = []
    for (account, h), group in by_hash.items():
        if len(group) > 1:
            targets.extend(group)
    return targets


async def fetch_real_image_src(page, base_post_url: str, slide_idx: int) -> str | None:
    try:
        await page.goto(base_post_url, wait_until="domcontentloaded", timeout=25000)
    except Exception:
        await asyncio.sleep(2)
        try:
            await page.goto(base_post_url, wait_until="domcontentloaded", timeout=25000)
        except Exception:
            return None

    try:
        await page.wait_for_selector('img', timeout=5000)
    except Exception:
        pass
    await asyncio.sleep(1.5)

    for _ in range(slide_idx):
        next_btn = page.locator('button[aria-label="다음"], button[aria-label="Next"]').first
        try:
            if await next_btn.is_visible(timeout=1000):
                await next_btn.click(force=True)
                await asyncio.sleep(0.7)
            else:
                break
        except Exception:
            break

    img_src = await page.evaluate("""
        () => {
            const article = document.querySelector('article');
            const scope = article || document;
            const imgs = Array.from(scope.querySelectorAll('img'));
            let best = null, bestSize = 0;
            for (const img of imgs) {
                const alt = (img.alt || '').toLowerCase();
                const isAvatar = img.closest('header') ||
                                 alt.includes('프로필 사진') || alt.includes('profile picture') ||
                                 (img.closest('a[href*="/p/"]') === null && img.width < 60);
                if (isAvatar) continue;
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


def update_post_image(post_id: int, new_image_url: str) -> None:
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE fashion_posts
                SET image_url = %s, caption_ai = NULL, caption_meta = NULL, embedding = NULL
                WHERE id = %s
                """,
                (new_image_url, post_id),
            )


async def main():
    targets = find_corrupted_groups()
    print(f"[복구 대상] {len(targets)}건", flush=True)
    for t in targets:
        print(f"  - id={t['id']} @{t['account_name']} {t['post_url']}", flush=True)

    if not targets:
        return

    ig_username = os.environ.get("INSTAGRAM_USERNAME")
    ig_password = os.environ.get("INSTAGRAM_PASSWORD")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )

        session_loaded = await load_session(context)
        if session_loaded:
            logged_in = True
        else:
            login_page = await context.new_page()
            await Stealth().apply_stealth_async(login_page)
            logged_in = await login(login_page, ig_username, ig_password)
            await login_page.close()
        if not logged_in:
            print("[복구 실패] 인스타그램 로그인 실패", flush=True)
            await browser.close()
            return

        fixed, failed = 0, 0
        for t in targets:
            post_url = t["post_url"]
            if "?img=" in post_url:
                base_url, suffix = post_url.split("?img=")
                slide_idx = int(suffix) - 1
            else:
                base_url, slide_idx = post_url, 0

            page = await context.new_page()
            await Stealth().apply_stealth_async(page)
            try:
                img_src = await asyncio.wait_for(fetch_real_image_src(page, base_url, slide_idx), timeout=60)
                if not img_src:
                    print(f"  [실패] id={t['id']} 이미지 추출 실패", flush=True)
                    failed += 1
                    continue

                local_path = download_image(img_src, t["account_name"])
                if not local_path:
                    print(f"  [실패] id={t['id']} 다운로드 실패", flush=True)
                    failed += 1
                    continue

                from utils.image_downloader import DATA_DIR as IMG_DATA_DIR
                rel = Path(local_path).relative_to(IMG_DATA_DIR)
                new_image_url = f"/images/{rel.as_posix()}"

                update_post_image(t["id"], new_image_url)
                print(f"  [복구] id={t['id']} -> {new_image_url}", flush=True)
                fixed += 1
            except asyncio.TimeoutError:
                print(f"  [실패] id={t['id']} 타임아웃(60초) - 건너뜀", flush=True)
                failed += 1
            except Exception as e:
                print(f"  [에러] id={t['id']}: {e}", flush=True)
                failed += 1
            finally:
                try:
                    await asyncio.wait_for(page.close(), timeout=10)
                except Exception:
                    pass
                await asyncio.sleep(2)

        await browser.close()

    print(f"\n[완료] 복구 {fixed}건 / 실패 {failed}건", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
