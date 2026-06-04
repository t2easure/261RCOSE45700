"""
Playwright 기반 인스타그램 크롤러 (로컬 PC 최종 마스터 버전 - 날짜 정렬 추가)
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
        await asyncio.sleep(4) 
        
        username_input = page.locator('input[name="username"]').first
        
        if not await username_input.is_visible(timeout=3000):
            if "login" not in page.url:
                print(f"[Instagram] 자동 로그인 상태 감지 완료! (현재 위치: {page.url})", flush=True)
                return True

        print("[Instagram] 로그아웃 상태가 확인되었습니다. 로그인을 시도합니다.", flush=True)
        
        for sel in ['[data-testid="cookie-policy-manage-dialog-accept-button"]', 'button:has-text("Allow")', 'button:has-text("허용")']:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=500):
                    await btn.click()
                    break
            except: pass
        
        await username_input.fill(username)
        await asyncio.sleep(0.5)
        await page.locator('input[name="password"]').first.fill(password)
        await asyncio.sleep(0.5)
        await page.keyboard.press('Enter')
        print("[Instagram] 로그인 정보 제출 완료. 메인 화면 전환 감시 시작...", flush=True)
        
        for _ in range(40):
            await asyncio.sleep(1)
            current_url = page.url
            if ("login" not in current_url and "instagram.com" in current_url) or "explore" in current_url:
                print(f"[Instagram] 로그인 완료 성공! (최종 위치: {current_url})", flush=True)
                await asyncio.sleep(2)
                return True
                
        print("[Instagram] 로그인 제한시간 초과", flush=True)
        return False
    except Exception as e:
        print(f"[Instagram] 로그인 로직 에러: {e}", flush=True)
        return False


async def collect_account(page, username: str, cutoff: datetime, followers: int = 0) -> list[dict]:
    posts = []
    print(f" -> [추적] {username} DB 기존 URL 조회 시도...", flush=True)
    existing_urls = await asyncio.get_event_loop().run_in_executor(None, get_existing_instagram_urls)
    
    try:
        await page.goto(f"https://www.instagram.com/{username}/", wait_until="commit", timeout=30000)
        await page.wait_for_load_state("domcontentloaded", timeout=15000)
        print(f" -> [추적] {username} 인스타 페이지 접속 성공!", flush=True)
        await asyncio.sleep(3)

        if "login" in page.url or "accounts" in page.url:
            print(f"[Instagram] 세션 만료 감지 ({page.url}) → 수집 중단", flush=True)
            return posts

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
        except Exception:
            pass

        seen = set()
        scroll_count = 0
        max_scrolls = 15 # 날짜가 깊으므로 스크롤 한도를 조금 늘림
        empty_scrolls = 0
        max_empty_scrolls = 3

        print(f" -> [스캔] {username} 피드 상단부터 역순 탐색하며 4월 14일 경계선 추적 시작...", flush=True)
        while scroll_count < max_scrolls:
            anchors = await page.locator('a[href*="/p/"]').all()
            new_found = False

            for idx, anchor in enumerate(anchors):
                href = await anchor.get_attribute('href')
                if not href or href in seen:
                    continue
                seen.add(href)
                shortcode = href.strip('/').split('/')[-1]
                post_url = f"https://www.instagram.com/p/{shortcode}/"

                if post_url in existing_urls:
                    continue

                post_page = None
                try:
                    post_page = await page.context.new_page()
                    await Stealth().apply_stealth_async(post_page)
                    
                    try:
                        await post_page.goto(post_url, referer=f"https://www.instagram.com/{username}/", wait_until="domcontentloaded", timeout=20000)
                    except Exception:
                        await asyncio.sleep(3)
                        await post_page.goto(post_url, referer=f"https://www.instagram.com/{username}/", wait_until="domcontentloaded", timeout=30000)
                    
                    try:
                        await post_page.wait_for_selector('img', timeout=5000)
                    except:
                        pass
                    await asyncio.sleep(2)

                    posted_at = datetime.now(timezone.utc)
                    try:
                        time_el = post_page.locator('time').first
                        dt_str = await time_el.get_attribute('datetime', timeout=3000)
                        if dt_str:
                            from dateutil.parser import parse as parse_dt
                            posted_at = parse_dt(dt_str).astimezone(timezone.utc)
                    except Exception:
                        pass

                    # 🚨 [수정] 날짜가 정상적으로 파싱되었고, 진짜로 4월 14일보다 과거일 때만 멈춤
                    # 만약 첫 번째 글이거나 날짜가 꼬인 경우를 대비해, 최소 3개 이상 보관했을 때만 멈추도록 안전장치 추가
                    if posted_at < cutoff and len(posts) > 3:
                        print(f"   -> [스캔 완료] {shortcode} 게시일({posted_at.date()})이 기준일보다 과거이므로 탐색 종료!", flush=True)
                        await post_page.close()
                        scroll_count = max_scrolls
                        break
                    elif posted_at < cutoff:
                        # 아직 수집된 글이 없는데 과거 날짜가 나왔다면, 파싱 에러일 수 있으니 중단하지 않고 계속 진행
                        print(f"   -> [주의] {shortcode} ({posted_at.date()}) 기준일 미달이나 탐색 유지를 위해 계속 스캔", flush=True)

                    carousel_imgs = []
                    try:
                        seen_imgs = set()
                        for slide_idx in range(10):
                            img_src = await post_page.evaluate("""
                                () => {
                                    const imgs = Array.from(document.querySelectorAll('img'));
                                    let best = null, bestSize = 0;
                                    for (const img of imgs) {
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
                            if await next_btn.is_visible(timeout=500):
                                await next_btn.click(force=True)
                                await asyncio.sleep(0.8)
                            else:
                                break
                    except Exception:
                        pass

                    likes = None
                    try:
                        article_text = await post_page.locator("main, article").first.inner_text(timeout=5000)
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
                        print(f"   [임시 보관] {shortcode} ({posted_at.date()}) 발견 - 정렬 대기 중", flush=True)

                except Exception as e:
                    print(f"[Instagram] {shortcode} 상세 수집 중 에러: {e}", flush=True)
                    if post_page: await post_page.close()
                
                await asyncio.sleep(1)

            if not new_found:
                empty_scrolls += 1
                if empty_scrolls >= max_empty_scrolls: break

            await page.evaluate("window.scrollBy(0, 1200)")
            await asyncio.sleep(2)
            scroll_count += 1

    except Exception as e:
        print(f"[Instagram] @{username} 프로필 메인 처리 에러: {e}", flush=True)

    return posts


async def run_instagram_playwright(ig_username: str = None, ig_password: str = None) -> int:
    import os
    # 🚨 본인 인스타 정보 입력 확인
    ig_username = ig_username or "tieusian_freaky"
    ig_password = ig_password or "tjduswl123!"

    brands, influencers = load_accounts()
    cutoff = datetime(2026, 4, 14, tzinfo=timezone.utc)
    total = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
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
            print(f"[Instagram] 타겟 계정 스캔 시작: @{username}")
            print(f"==========================================\n", flush=True)
            
            user_page = await context.new_page()
            await Stealth().apply_stealth_async(user_page)
            
            posts = []
            try:
                posts = await asyncio.wait_for(
                    collect_account(user_page, username, cutoff=cutoff),
                    timeout=600,
                )
            except asyncio.TimeoutError:
                print(f"[Instagram] @{username} 10분 타임아웃 초과 스킵", flush=True)
            except Exception as e:
                print(f"[Instagram] @{username} 에러: {e}", flush=True)
            finally:
                await user_page.close()
            
            # 🚨 [유저 요청 해결] 수집된 데이터가 존재하면 정렬을 실행합니다.
            if posts:
                # posted_at 오름차순 정렬 (옛날 날짜 -> 최신 날짜순)
                posts.sort(key=lambda x: x["posted_at"])
                
                print(f"\n[정렬 완료] @{username} 수집본을 4월 14일부터 순차 정렬했습니다.", flush=True)
                print(f"[순방향 저장] 4월->6월 데이터 로컬 저장 및 DB 업로드 시작...", flush=True)
                
                # 순서대로 정렬된 데이터를 로그에 찍어주기
                for p in posts:
                    if "?img=" not in p["post_url"]: # 첫 슬라이드 로그만 출력하여 깔끔하게 정리
                        print(f"   -> [순차 적재] 날짜: {p['posted_at'].date()} | 링크: {p['post_url']}", flush=True)
                
                # 정렬된 배열 순서 그대로 사진 저장 및 DB 처리 진행
                await asyncio.get_event_loop().run_in_executor(None, download_images, posts)
                saved = save_fashion_posts(posts)
                log_crawl(source="instagram", game="fashion", status="success", count=saved)
                print(f"[Instagram] @{username}: 총 {saved}개 연대기 순 저장 완료!\n", flush=True)
                total += saved
            
            await asyncio.sleep(5)

        await browser.close()

    print(f"\n[Instagram] 로컬 수집 완료: 총 {total}개 정방향 저장 성공", flush=True)
    return total

if __name__ == "__main__":
    asyncio.run(run_instagram_playwright())