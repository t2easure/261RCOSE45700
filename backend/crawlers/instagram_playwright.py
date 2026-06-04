"""
Playwright 기반 인스타그램 크롤러
instaloader 대신 실제 브라우저로 로그인 후 프로필 페이지에서 이미지 수집
"""
import asyncio
import json
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from db.database import save_fashion_posts, log_crawl, _get_connection
from utils.image_downloader import download_images

ACCOUNTS_PATH = Path(__file__).parent.parent.parent / "config" / "instagram_accounts.json"
SESSION_PATH = Path(__file__).parent.parent / "data" / "instagram_session.json"


def load_accounts() -> tuple[list[str], list[str]]:
    with open(ACCOUNTS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("brands", []), data.get("influencers", [])


def get_last_crawl_time() -> datetime:
    try:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT run_at FROM crawl_logs WHERE status='success' AND source='instagram' ORDER BY run_at DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    from dateutil.parser import parse
                    KST = timezone(timedelta(hours=9))
                    dt = parse(str(row[0]))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=KST)
                    return dt.astimezone(timezone.utc)
    except Exception:
        pass
    return datetime.now(timezone.utc) - timedelta(days=7)

def get_existing_instagram_urls() -> set:
    """DB에 이미 저장된 Instagram post_url 목록 조회"""
    try:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT post_url
                    FROM fashion_posts
                    WHERE source = 'instagram'
                """)
                return {row[0] for row in cur.fetchall() if row[0]}
    except Exception as e:
        print(f"[Instagram] 기존 URL 조회 실패: {e}")
        return set()

async def save_session(context):
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    cookies = await context.cookies()
    SESSION_PATH.write_text(json.dumps(cookies, ensure_ascii=False))
    print("[Instagram] 세션 저장 완료")


async def load_session(context) -> bool:
    if not SESSION_PATH.exists():
        return False
    try:
        cookies = json.loads(SESSION_PATH.read_text())
        await context.add_cookies(cookies)
        print("[Instagram] 세션 로드 성공")
        return True
    except Exception as e:
        print(f"[Instagram] 세션 로드 실패: {e}")
        return False


async def login(page, username: str, password: str) -> bool:
    try:
        await page.goto("https://www.instagram.com/accounts/login/", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # 쿠키 동의
        for sel in ['[data-testid="cookie-policy-manage-dialog-accept-button"]', 'button:has-text("Allow")', 'button:has-text("허용")']:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await asyncio.sleep(1)
                    break
            except Exception:
                pass

        await page.fill('input[name="username"]', username)
        await asyncio.sleep(1)
        await page.fill('input[name="password"]', password)
        await asyncio.sleep(1)

        # JS로 강제 클릭
        clicked = await page.evaluate("""
            () => {
                const btn = document.querySelector('button[type="submit"]');
                if (btn) { btn.click(); return true; }
                return false;
            }
        """)
        if not clicked:
            await page.keyboard.press('Enter')
        print(f"[Instagram] 로그인 버튼 클릭: {clicked}")

        # 최대 30초 대기 (2단계 인증이나 보안 확인 수동 처리 시간)
        for _ in range(15):
            await asyncio.sleep(2)
            print(f"[Instagram] 현재 URL: {page.url}")
            if "login" not in page.url and "instagram.com" in page.url:
                print("[Instagram] 로그인 성공")
                return True

        print(f"[Instagram] 로그인 실패: {page.url}")
        return False
    except Exception as e:
        print(f"[Instagram] 로그인 에러: {e}")
        return False


async def collect_account(page, username: str, cutoff: datetime, followers: int = 0) -> list[dict]:
    posts = []
    existing_urls = get_existing_instagram_urls()

    try:
        await page.goto(f"https://www.instagram.com/{username}/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # 팔로워 수 파싱 (만/천 단위 처리)
        try:
            follower_text = await page.locator('a[href*="/followers/"] span, span:has-text("팔로워")').first.inner_text(timeout=3000)
            ft = follower_text.strip().replace(',', '')
            m = re.search(r'([\d.]+)\s*([만천KkMm]?)', ft)
            if m:
                val = float(m.group(1))
                unit = m.group(2).lower()
                if unit in ('만',):
                    val *= 10000
                elif unit in ('천', 'k'):
                    val *= 1000
                elif unit == 'm':
                    val *= 1000000
                followers = int(val)
        except Exception:
            pass

        # 게시물 이미지 수집 (스크롤)
        seen = set()
        scroll_count = 0
        max_scrolls = 10

        while scroll_count < max_scrolls:
            # 현재 페이지의 게시물 링크 수집
            anchors = await page.locator('a[href*="/p/"]').all()
            new_found = False

            for anchor in anchors:
                href = await anchor.get_attribute('href')
                if not href or href in seen:
                    continue
                seen.add(href)
                shortcode = href.strip('/').split('/')[-1]
                post_url = f"https://www.instagram.com/p/{shortcode}/"

                if post_url in existing_urls:
                    print(f"[Instagram] {shortcode} 이미 저장됨 → 스킵")
                    continue

                # 게시물 페이지 접속해서 이미지 URL 및 날짜 가져오기
                try:
                    post_page = await page.context.new_page()
                    await post_page.goto(f"https://www.instagram.com/p/{shortcode}/", wait_until="domcontentloaded", timeout=20000)
                    await asyncio.sleep(1.5)

                    # 날짜
                    posted_at = datetime.now(timezone.utc)
                    try:
                        time_el = post_page.locator('time').first
                        dt_str = await time_el.get_attribute('datetime', timeout=3000)
                        if dt_str:
                            from dateutil.parser import parse as parse_dt
                            posted_at = parse_dt(dt_str).astimezone(timezone.utc)
                    except Exception:
                        pass

                    if posted_at < cutoff:
                        await post_page.close()
                        scroll_count = max_scrolls  # 조기 종료
                        break

                    # 캐러셀 이미지 전체 수집
                    carousel_imgs = []
                    try:
                        seen_imgs = set()
                        for slide_idx in range(10):  # 최대 10장
                            img_src = await post_page.evaluate("""
                                () => {
                                    const imgs = Array.from(document.querySelectorAll('article img'));
                                    let best = null, bestSize = 0;
                                    for (const img of imgs) {
                                        const w = img.naturalWidth || img.width || 0;
                                        const h = img.naturalHeight || img.height || 0;
                                        if (w > 100 && h > 100 && w * h > bestSize) {
                                            bestSize = w * h; best = img.src || img.currentSrc;
                                        }
                                    }
                                    return best;
                                }
                            """)
                            if img_src and img_src not in seen_imgs:
                                seen_imgs.add(img_src)
                                carousel_imgs.append(img_src)

                            # 다음 슬라이드 버튼 클릭
                            next_btn = post_page.locator('button[aria-label="다음"], button[aria-label="Next"]').first
                            if await next_btn.is_visible(timeout=200):
                                await next_btn.click()
                                await asyncio.sleep(0.5)
                            else:
                                break
                    except Exception:
                        pass

                    img_url = carousel_imgs[0] if carousel_imgs else None

                    # 좋아요
                    likes = None
                    try:
                        article_text = await post_page.locator("article").inner_text(timeout=5000)

                        like_patterns = [
                            r"좋아요\s*([\d,]+)\s*개",
                            r"([\d,]+)\s*명이\s*좋아합니다",
                            r"([\d,]+)\s*likes",
                            r"Liked by .* and ([\d,]+) others",
                            r"and\s*([\d,]+)\s*others",
                            r"외\s*([\d,]+)\s*명",
                        ]

                        for pat in like_patterns:
                            m = re.search(pat, article_text)
                            if m:
                                likes = int(m.group(1).replace(",", ""))
                                break

                        if likes is None:
                            lines = [line.strip() for line in article_text.splitlines() if line.strip()]

                            def parse_count(text: str):
                                text = text.replace(",", "").strip()
                                m = re.match(r"^(\d+(?:\.\d+)?)([KkMm]?)$", text)
                                if not m:
                                    return None

                                value = float(m.group(1))
                                suffix = m.group(2).lower()

                                if suffix == "k":
                                    value *= 1000
                                elif suffix == "m":
                                    value *= 1000000

                                return int(value)

                            # 모바일 Instagram 게시물 텍스트에서:
                            # username / • / Follow / (협업계정 optional) / likes / comments / username / caption ...
                            for i, line in enumerate(lines):
                                if line == "Follow":
                                    numeric_candidates = []

                                    # Follow 이후 몇 줄 안에서 숫자 후보 수집
                                    for next_line in lines[i + 1:i + 8]:
                                        parsed = parse_count(next_line)
                                        if parsed is not None:
                                            numeric_candidates.append(parsed)

                                    # 보통 첫 번째 숫자 = 좋아요, 두 번째 숫자 = 댓글 수
                                    # 단, 숫자가 하나뿐이고 바로 "Liked by ... and others" 형태면 좋아요 숨김일 가능성이 큼
                                    if len(numeric_candidates) >= 2:
                                        likes = numeric_candidates[0]
                                    elif len(numeric_candidates) == 1:
                                        # 좋아요 수가 명확히 하나만 보이는 케이스를 허용하되,
                                        # "Liked by ... and others"만 있는 숨김 케이스는 제외
                                        joined_after_follow = "\n".join(lines[i + 1:i + 8])
                                        if "Liked by" not in joined_after_follow:
                                            likes = numeric_candidates[0]

                                    break

                        if likes is None:
                            print(f"[Instagram DEBUG] {shortcode} 좋아요 파싱 실패 또는 숨김")
                            print(article_text[:800])

                    except Exception as e:
                        print(f"[Instagram DEBUG] {shortcode} 좋아요 영역 읽기 실패: {e}")

                    if likes is None:
                        likes = -1

                    await post_page.close()

                    if carousel_imgs:
                        for idx, ci in enumerate(carousel_imgs):
                            slide_url = post_url if idx == 0 else f"{post_url}?img={idx+1}"
                            posts.append({
                                "source": "instagram",
                                "account_name": username,
                                "post_url": slide_url,
                                "image_url": ci,
                                "caption": "",
                                "likes": likes,
                                "comments": 0,
                                "followers": followers,
                                "posted_at": posted_at,
                            })
                        new_found = True
                        print(f"[Instagram] @{username} 수집: {shortcode} ({posted_at.date()}) 이미지 {len(carousel_imgs)}장")

                except Exception as e:
                    print(f"[Instagram] {shortcode} 수집 실패: {e}")
                    try:
                        await post_page.close()
                    except Exception:
                        pass

            if not new_found:
                break

            await page.evaluate("window.scrollBy(0, 1200)")
            await asyncio.sleep(2)
            scroll_count += 1

    except Exception as e:
        print(f"[Instagram] @{username} 프로필 접속 실패: {e}")

    return posts


async def run_instagram_playwright(ig_username: str = None, ig_password: str = None) -> int:
    import os
    ig_username = ig_username or os.environ.get("INSTAGRAM_USERNAME")
    ig_password = ig_password or os.environ.get("INSTAGRAM_PASSWORD")

    brands, influencers = load_accounts()
    cutoff = get_last_crawl_time()
    print(f"[Instagram] 마지막 크롤링 기준: {cutoff.strftime('%Y-%m-%d %H:%M')} 이후 수집")
    total = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
            ),
            viewport={"width": 390, "height": 844},
        )

        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        # 세션 로드 or 로그인
        session_loaded = await load_session(context)
        if not session_loaded:
            if not ig_username or not ig_password:
                print("[Instagram] 세션 없음, 환경변수 INSTAGRAM_USERNAME/INSTAGRAM_PASSWORD 필요")
                await browser.close()
                return 0
            logged_in = await login(page, ig_username, ig_password)
            if not logged_in:
                await browser.close()
                return 0
            await save_session(context)

        for username in brands + influencers:
            print(f"[Instagram] 수집 시작: @{username}")
            posts = await collect_account(page, username, cutoff=cutoff)
            if posts:
                download_images(posts)
                saved = save_fashion_posts(posts)
                log_crawl(source="instagram", game="fashion", status="success", count=saved)
                print(f"[Instagram] @{username}: {saved}개 저장")
                total += saved
            await asyncio.sleep(5)

        await browser.close()

    print(f"[Instagram] 전체 완료: {total}개 저장")
    return total


if __name__ == "__main__":
    asyncio.run(run_instagram_playwright())
