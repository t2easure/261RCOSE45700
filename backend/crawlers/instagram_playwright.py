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
from pyvirtualdisplay import Display

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
        print(f"[Instagram] 기존 URL 조회 실패: {e}", flush=True)
        return set()

async def save_session(context):
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    cookies = await context.cookies()
    SESSION_PATH.write_text(json.dumps(cookies, ensure_ascii=False))
    print("[Instagram] 세션 저장 완료", flush=True)


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
        await page.goto("https://www.instagram.com/accounts/login/", wait_until="commit", timeout=30000)
        await page.wait_for_load_state("domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

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
        print(f"[Instagram] 로그인 버튼 클릭: {clicked}", flush=True)

        # 최대 30초 대기
        for _ in range(15):
            await asyncio.sleep(2)
            print(f"[Instagram] 현재 URL: {page.url}", flush=True)
            if "login" not in page.url and "instagram.com" in page.url:
                print("[Instagram] 로그인 성공", flush=True)
                return True

        print(f"[Instagram] 로그인 실패: {page.url}", flush=True)
        return False
    except Exception as e:
        print(f"[Instagram] 로그인 에러: {e}", flush=True)
        return False


async def collect_account(page, username: str, cutoff: datetime, followers: int = 0) -> list[dict]:
    """특정 계정의 프로필 페이지에서 게시물 데이터를 수집하는 핵심 함수"""
    posts = []
    
    print(f" -> [추적 3-1] {username} DB 기존 URL 조회 시도...", flush=True)
    existing_urls = await asyncio.get_event_loop().run_in_executor(None, get_existing_instagram_urls)
    
    print(f" -> [추적 3-2] {username} DB 조회 완료! 인스타 페이지 접속 시도...", flush=True)
    try:
        await page.goto(f"https://www.instagram.com/{username}/", wait_until="commit", timeout=30000)
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
        print(f" -> [추적 3-3] {username} 인스타 페이지 접속 성공!", flush=True)
        await asyncio.sleep(3)

        if "login" in page.url or "accounts" in page.url:
            print(f"[Instagram] 세션 만료 감지 ({page.url}) → 수집 중단", flush=True)
            return posts

        # 팔로워 수 파싱
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
        empty_scrolls = 0
        max_empty_scrolls = 3

        print(f" -> [추적 3-4] {username} 피드 스크롤 및 수집 시작...", flush=True)
        try:
            await page.wait_for_selector('a[href*="/p/"]', timeout=10000)
        except Exception:
            print(f"[Instagram] @{username} 포스트 그리드 로드 실패 → 스킵", flush=True)
            return posts

        while scroll_count < max_scrolls:
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
                    print(f"[Instagram] {shortcode} 이미 저장됨 → 스킵", flush=True)
                    continue

                # 게시물 상세 페이지 접속
                post_page = None
                try:
                    post_page = await page.context.new_page()
                    await post_page.goto(f"https://www.instagram.com/p/{shortcode}/", wait_until="commit", timeout=20000)
                    await asyncio.sleep(1.5)

                    # 날짜 파싱
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
                        scroll_count = max_scrolls
                        break

                    # 캐러셀 이미지 수집
                    carousel_imgs = []
                    try:
                        seen_imgs = set()
                        for slide_idx in range(10):
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

                            next_btn = post_page.locator('button[aria-label="다음"], button[aria-label="Next"]').first
                            if await next_btn.is_visible(timeout=200):
                                await next_btn.click()
                                await asyncio.sleep(0.5)
                            else:
                                break
                    except Exception:
                        pass

                    # 좋아요 파싱
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
                    except Exception:
                        pass

                    if likes is None:
                        likes = None

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
                        print(f"[Instagram] @{username} 수집: {shortcode} ({posted_at.date()}) 이미지 {len(carousel_imgs)}장", flush=True)

                except Exception as e:
                    print(f"[Instagram] {shortcode} 상세 수집 실패: {e}", flush=True)
                    if post_page:
                        await post_page.close()

            if not new_found:
                empty_scrolls += 1
                if empty_scrolls >= max_empty_scrolls:
                    break

            await page.evaluate("window.scrollBy(0, 1200)")
            await asyncio.sleep(2)
            scroll_count += 1

    except Exception as e:
        print(f"[Instagram] @{username} 프로필 내부 에러: {e}", flush=True)

    return posts


async def run_instagram_playwright(ig_username: str = None, ig_password: str = None) -> int:
    import os
    ig_username = ig_username or os.environ.get("INSTAGRAM_USERNAME")
    ig_password = ig_password or os.environ.get("INSTAGRAM_PASSWORD")

    brands, influencers = load_accounts()
    cutoff = get_last_crawl_time()
    print(f"[Instagram] 마지막 크롤링 기준: {cutoff.strftime('%Y-%m-%d %H:%M')} 이후 수집", flush=True)
    total = 0

    print("[System] 가상 디스플레이(Xvfb) 시작...", flush=True)
    display = Display(visible=0, size=(1280, 800))
    display.start()
    try:
      async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--js-flags=--max-old-space-size=1024",  # Chromium JS 엔진 메모리 제한
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )

        # 1. 초기 세션 주입용 임시 페이지 열기
        login_page = await context.new_page()
        await Stealth().apply_stealth_async(login_page)

        session_loaded = await load_session(context)
        if not session_loaded:
            if not ig_username or not ig_password:
                print("[Instagram] 세션 없음, 환경변수 INSTAGRAM_USERNAME/INSTAGRAM_PASSWORD 필요", flush=True)
                await browser.close()
                return 0
            logged_in = await login(login_page, ig_username, ig_password)
            if not logged_in:
                await browser.close()
                return 0
            await save_session(context)
        
        # 로그인/세션 로드가 끝났으므로 임시 페이지는 닫아줌 (메모리 절약)
        await login_page.close()

        # 2. 메인 수집 루프 시작
        for username in brands + influencers:
            print(f"[Instagram] 수집 시작: @{username}", flush=True)
            
            print(f" -> [추적 1] {username} 전용 깨끗한 새 탭 생성 시도...", flush=True)
            user_page = await context.new_page()
            await Stealth().apply_stealth_async(user_page)
            
            print(f" -> [추적 2] {username} collect_account 진입 대기 (제한시간 2분)...", flush=True)
            posts = []
            try:
                # 계정당 무한 대기를 방지하기 위해 2분(120초) 타임아웃 설정
                posts = await asyncio.wait_for(
                    collect_account(user_page, username, cutoff=cutoff),
                    timeout=120,
                )
            except asyncio.TimeoutError:
                print(f"[Instagram] @{username} 타임아웃 (2분 초과) → 스킵 및 강제 캡처", flush=True)
                try:
                    await user_page.screenshot(path=f"timeout_ec2_{username}.png")
                    html_content = await user_page.content()
                    with open(f"timeout_ec2_{username}.html", "w", encoding="utf-8") as f:
                        f.write(html_content)
                except Exception as cap_err:
                    print(f"[Instagram] 타임아웃 캡처 실패: {cap_err}", flush=True)
            except Exception as e:
                print(f"[Instagram] @{username} 처리 중 예외 발생: {e}", flush=True)
            finally:
                # 메모리 누수를 막기 위해 계정당 수집이 끝나면 무조건 탭을 닫음
                print(f" -> [추적 4] {username} 탭 강제 종료 및 메모리 해제", flush=True)
                await user_page.close()
            
            # 수집된 데이터가 있으면 DB 및 이미지 다운로드 진행
            if posts:
                await asyncio.get_event_loop().run_in_executor(None, download_images, posts)
                saved = save_fashion_posts(posts)
                log_crawl(source="instagram", game="fashion", status="success", count=saved)
                print(f"[Instagram] @{username}: {saved}개 저장 완료", flush=True)
                total += saved
            
            await asyncio.sleep(10)

        await browser.close()

    finally:
        display.stop()
        print("[System] 가상 디스플레이 종료", flush=True)

    print(f"[Instagram] 전체 완료: 총 {total}개 저장", flush=True)
    return total


if __name__ == "__main__":
    asyncio.run(run_instagram_playwright())