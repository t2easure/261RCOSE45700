"""
Playwright 기반 인스타그램 크롤러 (EC2 배포용 Xvfb + 스크린샷 + 고속 정방향 정밀 수집)
"""
import os
import sys
import asyncio
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

# backend 폴더를 루트로 인식하도록 경로 강제 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from pyvirtualdisplay import Display  # 🚨 서버 전용 가상 디스플레이 라이브러리 복원

from db.database import save_fashion_posts, log_crawl, _get_connection
from utils.image_downloader import download_images

ACCOUNTS_PATH = Path(__file__).parent.parent.parent / "config" / "instagram_accounts.json"
SESSION_PATH = Path(__file__).parent.parent / "data" / "instagram_session.json"


def load_accounts() -> tuple[list[str], list[str]]:
    with open(ACCOUNTS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("brands", []), data.get("influencers", [])


def get_existing_instagram_urls() -> set:
    try:
        with _get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT post_url FROM fashion_posts WHERE source = 'instagram'")
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
        print("[Instagram] 로그인 상태 점검을 위해 메인 홈 진입 중...", flush=True)
        await page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5) # 리다이렉트 및 렌더링 대기 시간 확보
        
        username_input = page.locator('input[name="username"]').first
        login_btn_visible = await page.locator('button:has-text("로그인"), a:has-text("로그인")').first.is_visible(timeout=1000)
        
        if not await username_input.is_visible(timeout=1000) and not login_btn_visible:
            if "login" not in page.url:
                print(f"[Instagram] 🎉 자동 로그인 성공 감지! (현재 위치: {page.url})", flush=True)
                return True

        print("[Instagram] 🔒 로그아웃 상태가 확인되었습니다. 로그인 절차를 진행합니다.", flush=True)
        
        for sel in ['[data-testid="cookie-policy-manage-dialog-accept-button"]', 'button:has-text("Allow")', 'button:has-text("허용")']:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=500):
                    await btn.click()
                    break
            except: pass
        
        # 서버용 계정 자동 입력
        await username_input.fill(username)
        await asyncio.sleep(0.5)
        await page.locator('input[name="password"]').first.fill(password)
        await asyncio.sleep(0.5)
        await page.keyboard.press('Enter')
        print("[Instagram] 로그인 정보 제출 완료. 메인 화면 전환 감시 시작...", flush=True)
        
        # 60초 동안 대기하면서 성공 여부 실시간 확인 (서버 백그라운드 매끄러운 바인딩용)
        for second in range(60):
            await asyncio.sleep(1)
            current_url = page.url
            has_input = await page.locator('input[name="username"]').is_visible(timeout=100)
            if not has_input and ("login" not in current_url or "explore" in current_url):
                print(f"[Instagram] 🎉 최종 로그인 성공 확인! (위치: {current_url})", flush=True)
                await asyncio.sleep(3)
                return True
                
        print("[Instagram] ❌ 로그인 제한시간 초과", flush=True)
        return False
    except Exception as e:
        print(f"[Instagram] 로그인 로직 에러: {e}", flush=True)
        return False


async def collect_account(page, username: str, cutoff: datetime, followers: int = 0) -> list[dict]:
    final_posts = []
    print(f" -> [추적] {username} DB 기존 URL 조회 시도...", flush=True)
    existing_urls = await asyncio.get_event_loop().run_in_executor(None, get_existing_instagram_urls)
    
    try:
        await page.goto(f"https://www.instagram.com/{username}/", wait_until="commit", timeout=30000)
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
        print(f" -> [추적] {username} 인스타 페이지 접속 성공!", flush=True)
        await asyncio.sleep(3)

        # 🚨 [Xvfb 전용 디버깅 가드] 세션 튕기면 원인 분석용 스크린샷 찰칵 박아버리기
        if "login" in page.url or "accounts" in page.url:
            print(f"[Instagram] 세션 만료 감지 ({page.url}) → 수집 중단", flush=True)
            await page.screenshot(path=f"debug_banned_{username}.png")
            print(f"[System] 차단 화면 스크린샷 저장 완료: debug_banned_{username}.png", flush=True)
            return final_posts

        try:
            follower_text = await page.locator('a[href*="/followers/"] span, span:has-text("팔로워")').first.inner_text(timeout=3000)
            ft = follower_text.strip().replace(',', '')
            m = re.search(r'([\d.]+)\s*([만천KkMm]?)', ft)
            if m:
                val = float(m.group(1))
                unit = m.group(2).lower()
                if unit == '만': val *= 10000
                elif unit in ('천', 'k'): val *= 1000
                elif unit == 'm': val *= 1000000
                followers = int(val)
        except Exception: pass

        # 1단계: 메인 프로필 피드 고속 스캔 및 매핑
        target_shortcodes = []
        seen_shortcodes = set()
        scroll_count = 0
        max_scrolls = 30
        
        print(f" -> [⚡1단계 고속 스캔] {username} 피드에서 대상 게시물 코드 수집 시작...", flush=True)
        while scroll_count < max_scrolls:
            try:
                anchors = await asyncio.wait_for(
                    page.locator('article a[href*="/p/"]').all(),
                    timeout=15,
                )
            except asyncio.TimeoutError:
                print(f" -> [⚡1단계] {username} 페이지 응답 없음(15초) → 스캔 중단, 지금까지 수집된 {len(target_shortcodes)}개로 진행", flush=True)
                break
            for anchor in anchors:
                href = await anchor.get_attribute('href')
                if not href: continue
                shortcode = href.strip('/').split('/')[-1]
                
                if shortcode not in seen_shortcodes:
                    seen_shortcodes.add(shortcode)
                    if f"https://www.instagram.com/p/{shortcode}/" not in existing_urls:
                        target_shortcodes.append(shortcode)

            await page.evaluate("window.scrollBy(0, 1400)")
            await asyncio.sleep(1.2)
            scroll_count += 1
            
            if len(target_shortcodes) >= 36 or scroll_count >= 18:
                break

        # 2단계: 과거 글부터 정방향 순차 정밀 수집 연산
        target_shortcodes.reverse()
        print(f" -> [🔍2단계 정밀 수집] 총 {len(target_shortcodes)}개 포스트 정방향 개별 상세 파싱 시작...", flush=True)

        for shortcode in target_shortcodes:
            post_url = f"https://www.instagram.com/p/{shortcode}/"
            post_page = None
            try:
                post_page = await page.context.new_page()
                await Stealth().apply_stealth_async(post_page)
                
                try:
                    await post_page.goto(post_url, referer=f"https://www.instagram.com/{username}/", wait_until="domcontentloaded", timeout=20000)
                except Exception:
                    await asyncio.sleep(2)
                    await post_page.goto(post_url, referer=f"https://www.instagram.com/{username}/", wait_until="domcontentloaded", timeout=25000)
                
                try: await post_page.wait_for_selector('img', timeout=4000)
                except: pass
                await asyncio.sleep(1.5)

                posted_at = datetime.now(timezone.utc)
                try:
                    time_el = post_page.locator('time').first
                    dt_str = await time_el.get_attribute('datetime', timeout=2000)
                    if dt_str:
                        from dateutil.parser import parse as parse_dt
                        posted_at = parse_dt(dt_str).astimezone(timezone.utc)
                except Exception: pass

                if posted_at < cutoff:
                    print(f"   -> [필터 차단] {shortcode} ({posted_at.date()}) 글은 4월 14일 이전이므로 수집하지 않음", flush=True)
                    await post_page.close()
                    continue

                carousel_imgs = []
                seen_imgs = set()
                for slide_idx in range(10):
                    img_src = await post_page.evaluate("""
                        () => {
                            const article = document.querySelector('article');
                            const scope = article || document;
                            const imgs = Array.from(scope.querySelectorAll('img'));
                            let best = null, bestSize = 0;
                            for (const img of imgs) {
                                // 프로필 사진 제외 (헤더 영역, alt 텍스트, 또는 작은 원형 이미지)
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
                    if img_src and img_src not in seen_imgs:
                        seen_imgs.add(img_src)
                        carousel_imgs.append(img_src)

                    next_btn = post_page.locator('button[aria-label="다음"], button[aria-label="Next"]').first
                    if await next_btn.is_visible(timeout=400):
                        # 🚨 force=True 처리로 서버 환경 내 가입 유도 팝업 투명 막 강제 격파 클릭
                        await next_btn.click(force=True)
                        await asyncio.sleep(0.7)
                    else:
                        break

                likes = None
                try:
                    # 좋아요 수 전용 셀렉터로 추출 (aria-label 오염 방지)
                    like_selectors = [
                        'section span[class*="like"]',
                        'a[href*="liked_by"] span',
                        'span[class*="_aacl"]:has-text("좋아요")',
                    ]
                    for sel in like_selectors:
                        try:
                            el = post_page.locator(sel).first
                            if await el.is_visible(timeout=800):
                                txt = await el.inner_text(timeout=800)
                                m = re.search(r"([\d,]+)", txt.replace(",", ""))
                                if m:
                                    likes = int(m.group(1).replace(",", ""))
                                    break
                        except Exception:
                            continue

                    # 셀렉터 실패 시 section 영역 텍스트에서 재시도
                    if likes is None:
                        section_text = await post_page.locator("section").last.inner_text(timeout=3000)
                        like_patterns = [
                            r"좋아요\s*([\d,]+)\s*개",
                            r"([\d,]+)\s*명이\s*좋아합니다",
                            r"외\s*([\d,]+)\s*명",
                            r"([\d,]+)\s*likes",
                            r"and\s*([\d,]+)\s*others",
                        ]
                        for pat in like_patterns:
                            m = re.search(pat, section_text)
                            if m:
                                likes = int(m.group(1).replace(",", ""))
                                break
                except Exception: pass

                await post_page.close()

                if carousel_imgs:
                    for idx, ci in enumerate(carousel_imgs):
                        slide_url = post_url if idx == 0 else f"{post_url}?img={idx+1}"
                        final_posts.append({
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
                    print(f"   -> [정밀 수집 완료] {shortcode} ({posted_at.date()}) | 하트: {likes}개 | 사진: {len(carousel_imgs)}장 획득!", flush=True)

            except Exception as detail_err:
                print(f"[Instagram] {shortcode} 정밀 파싱 실패 스킵: {detail_err}", flush=True)
                if post_page: await post_page.close()
                
            await asyncio.sleep(2)

    except Exception as e:
        print(f"[Instagram] @{username} 메인 프로세스 오류: {e}", flush=True)

    return final_posts


async def run_instagram_playwright(ig_username: str = None, ig_password: str = None) -> int:
    import os
    ig_username = ig_username or os.environ.get("INSTAGRAM_USERNAME")
    ig_password = ig_password or os.environ.get("INSTAGRAM_PASSWORD")

    brands, influencers = load_accounts()
    cutoff = datetime(2026, 4, 14, tzinfo=timezone.utc)
    print(f"[Instagram] 🔥 EC2 서버 사양 하이브리드 고속 엔진 기동 (기준일: {cutoff.strftime('%Y-%m-%d')} 이후) 🔥", flush=True)
    total = 0

    # 🚨 [가상 디스플레이 구동] 서버용 백엔드 Xvfb 결계 시작
    print("[System] 가상 디스플레이(Xvfb) 시작...", flush=True)
    display = Display(visible=0, size=(1280, 800))
    display.start()
    
    try:
        async with async_playwright() as p:
            # 🚨 headless=True 로 가상 디스플레이 백그라운드 메모리 극대화 가동
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--js-flags=--max-old-space-size=1024",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )

            login_page = await context.new_page()
            await Stealth().apply_stealth_async(login_page)

            session_loaded = await load_session(context)
            logged_in = await login(login_page, ig_username, ig_password)
            if not logged_in:
                await browser.close()
                return 0
            if not session_loaded:
                await save_session(context)
            
            await login_page.close()

            for username in brands + influencers:
                print(f"\n==========================================")
                print(f"[Instagram] 타겟 계정 분석 시작: @{username}")
                print(f"==========================================\n", flush=True)
                
                user_page = await context.new_page()
                await Stealth().apply_stealth_async(user_page)
                
                posts = []
                try:
                    posts = await asyncio.wait_for(
                        collect_account(user_page, username, cutoff=cutoff),
                        timeout=900,
                    )
                except asyncio.TimeoutError:
                    print(f"[Instagram] @{username} 처리 제한시간(900초) 초과 → 건너뜀", flush=True)
                    try:
                        await user_page.screenshot(path=f"debug_timeout_{username}.png")
                        print(f"[System] 타임아웃 화면 스크린샷 저장: debug_timeout_{username}.png", flush=True)
                    except Exception:
                        pass
                except Exception as e:
                    print(f"[Instagram] @{username} 에러 발생: {e}", flush=True)
                finally:
                    try:
                        await asyncio.wait_for(user_page.close(), timeout=15)
                    except Exception:
                        pass
                
                if posts:
                    print(f"\n📦 RDS 데이터베이스 적재 및 고화질 이미지 다운로드 중...", flush=True)
                    await asyncio.get_event_loop().run_in_executor(None, download_images, posts)
                    saved = save_fashion_posts(posts)
                    log_crawl(source="instagram", game="fashion", status="success", count=saved)
                    print(f"[Instagram] @{username}: 총 {saved}개 데이터 (정방향 날짜순) 저장 완료! ✅\n", flush=True)
                    total += saved
                
                await asyncio.sleep(5)

            await browser.close()

    finally:
        # 🚨 [자원 회수] 가상 디스플레이 안전 종료 보호망
        display.stop()
        print("[System] 가상 디스플레이 종료 완료", flush=True)

    print(f"\n🎉 [Instagram] EC2 서버 크롤링 대성공! 총 {total}개 적재 완료 🎉", flush=True)
    return total

if __name__ == "__main__":
    asyncio.run(run_instagram_playwright())