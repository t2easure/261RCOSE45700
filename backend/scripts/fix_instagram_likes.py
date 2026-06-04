"""
기존 instagram 게시물의 likes만 재수집해서 DB 업데이트 
(모바일 위장 + 5줄 딥스캐닝 + 댓글 오인 방어 + '여러 명' None 처리)
"""
import os
import sys
import asyncio
import re
import json
import platform
import random
from pathlib import Path
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from db.database import _get_connection

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

IS_LINUX = platform.system() == "Linux"
if IS_LINUX:
    from pyvirtualdisplay import Display

def parse_likes(text: str) -> int | None:
    if not text: return None
    text = text.strip().replace(",", "")
    
    # [댓글 방어막] 댓글 관련 텍스트는 좋아요로 파싱하지 않고 무시
    if "댓글" in text or "답글" in text or "comment" in text:
        return None
    
    # 🚨 [수정 완료] "여러 명" 패턴은 15개가 아니라 깔끔하게 None 반환
    if "여러 명" in text or "others" in text:
        return None

    # 문장형 좋아요 파싱
    m = re.search(r"(?:좋아요|likes)\s*([\d.]+)\s*([천만kKmM]?)", text)
    if not m:
        m = re.search(r"([\d.]+)\s*([천만kKmM]?)\s*(?:명이\s*좋아합니다)", text)
        
    if m:
        val = float(m.group(1))
        unit = m.group(2)
        if unit in ("천", "k", "K"):   val *= 1000
        elif unit == "만":              val *= 10000
        elif unit in ("m", "M"):        val *= 1000000
        return int(val)
        
    return None

def get_posts_to_fix() -> list[dict]:
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ON (SPLIT_PART(post_url, '?', 1))
                    id, post_url, likes
                FROM fashion_posts
                WHERE source = 'instagram'
                  AND post_url NOT LIKE '%%?img=%%'
                  AND (likes IS NULL OR likes < 1000)
                ORDER BY SPLIT_PART(post_url, '?', 1), id
            """)
            rows = cur.fetchall()
    return [{"id": r[0], "post_url": r[1], "likes": r[2]} for r in rows]

def update_likes_bulk(updates: list[dict]):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            for u in updates:
                base_url = u["post_url"].split("?")[0]
                cur.execute("""
                    UPDATE fashion_posts
                    SET likes = %s
                    WHERE post_url = %s OR post_url LIKE %s
                """, (u["likes"], base_url, base_url + "?img=%"))
        conn.commit()

async def fetch_likes(page, post_url: str) -> int | None:
    try:
        await page.goto(post_url, wait_until="domcontentloaded", referer="https://www.instagram.com/", timeout=25000)
        await asyncio.sleep(4) 
        
        if "login" in page.url or "accounts" in page.url:
            print(f"    [❌ 세션 아웃] 인스타가 로그인 창으로 튕겨냄", flush=True)
            return None

        try:
            article = page.locator("article").first
            if await article.is_visible(timeout=3000):
                article_text = await article.inner_text(timeout=2000)
                lines = [line.strip() for line in article_text.splitlines() if line.strip()]
                
                for idx, line in enumerate(lines):
                    if line in ("팔로우", "Follow", "팔로잉", "Following"):
                        lookahead_block = lines[idx+1 : idx+8]
                        
                        # 1단계: 블록 전체를 스캔해서 "여러 명"이 있는지 먼저 검사!
                        for block_line in lookahead_block:
                            if "여러 명" in block_line or "others" in block_line:
                                # 🚨 [수정 완료] 15개 적재 로직 버리고 None으로 스킵 처리
                                print(f"    [🎯 숨김 패턴 포착] 블록 내 '여러 명' 발견 ➡️ 수집 불가(None) 스킵", flush=True)
                                return None
                        
                        # 2단계: "여러 명"이 확실히 없을 때만 안심하고 숫자를 찾습니다.
                        for block_line in lookahead_block:
                            target = block_line.replace(",", "")
                            if "댓글" in target or "답글" in target:
                                continue

                            m_unit = re.fullmatch(r"([\d.]+)\s*([천만kKmM])", target)
                            if m_unit:
                                val = float(m_unit.group(1))
                                unit = m_unit.group(2)
                                if unit in ("천", "k", "K"): val *= 1000
                                elif unit == "만": val *= 10000
                                elif unit in ("m", "M"): val *= 1000000
                                return int(val)
                                
                            m_num = re.fullmatch(r"(\d+)", target)
                            if m_num:
                                return int(m_num.group(1))

                # 스캐닝 실패 시 폴백
                for line in lines:
                    res = parse_likes(line)
                    if res is not None:
                        return res
                        
                print(f"    [⚠️ 파싱 빈손] 텍스트: {repr(article_text[:150])}...", flush=True)
        except Exception as e:
            pass
            
    except Exception as e:
        pass
        
    return None

async def run():
    ig_username = os.environ.get("INSTAGRAM_USERNAME")
    ig_password = os.environ.get("INSTAGRAM_PASSWORD")

    posts = get_posts_to_fix()
    print(f"[likes 수정] 대상 게시물: {len(posts)}개 수집 엔진 기동 🚀", flush=True)
    
    if not posts:
        print("🎉 보정할 게시물이 없습니다. (모든 업데이트 완료!)")
        return

    display = None
    if IS_LINUX:
        display = Display(visible=0, size=(1280, 800))
        display.start()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False, 
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            viewport={"width": 390, "height": 844},
            is_mobile=True,
            has_touch=True
        )

        session_path = Path(__file__).parent.parent / "data" / "instagram_session.json"
        if session_path.exists():
            try:
                await context.add_cookies(json.loads(session_path.read_text()))
                print("[로그인] 기존 세션 쿠키 주입 완료", flush=True)
            except Exception:
                pass

        worker_page = await context.new_page()
        await Stealth().apply_stealth_async(worker_page)
        
        print("[로그인] 인스타그램 접속 중...", flush=True)
        await worker_page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded")
        
        is_logged_in = False
        for _ in range(6):
            await asyncio.sleep(1)
            if "login" not in worker_page.url and "instagram.com" in worker_page.url:
                print(f"[로그인] 🎉 자동 로그인 성공!", flush=True)
                is_logged_in = True
                break
            if await worker_page.locator('input[name="username"]').is_visible():
                break

        if not is_logged_in:
            username_input = worker_page.locator('input[name="username"]').first
            if await username_input.is_visible(timeout=3000):
                for sel in ['[data-testid="cookie-policy-manage-dialog-accept-button"]', 'button:has-text("Allow")', 'button:has-text("허용")']:
                    try:
                        btn = worker_page.locator(sel).first
                        if await btn.is_visible(timeout=500):
                            await btn.click()
                            break
                    except: pass
                await username_input.fill(ig_username)
                await asyncio.sleep(0.5)
                await worker_page.locator('input[name="password"]').first.fill(ig_password)
                await asyncio.sleep(0.5)
                await worker_page.keyboard.press("Enter")
                print("[로그인] 자동 타이핑 완료.", flush=True)

            print("[⏳ 대기 시작] 2차 인증 등 확인용 (최대 90초 대기)", flush=True)
            for _ in range(90):
                await asyncio.sleep(1)
                url = worker_page.url
                if "login" not in url and "challenge" not in url and "checkpoint" not in url:
                    print(f"[로그인] 🎉 최종 로그인 확인!", flush=True)
                    is_logged_in = True
                    break

        if is_logged_in:
            session_path.parent.mkdir(parents=True, exist_ok=True)
            session_path.write_text(json.dumps(await context.cookies(), ensure_ascii=False))
        else:
            print("[로그인] ❌ 로그인 실패. 종료합니다.", flush=True)
            await browser.close()
            return

        updates = []
        for i, post in enumerate(posts):
            likes = await fetch_likes(worker_page, post["post_url"])
            
            if likes is not None:
                updates.append({"post_url": post["post_url"], "likes": likes})
                print(f"  [{i+1}/{len(posts)}] 성공! ➡️ 좋아요 {likes}개 (ID: {post['id']})", flush=True)
            else:
                print(f"  [{i+1}/{len(posts)}] 실패 ❌ -> 스킵 ({post['post_url']})", flush=True)

            if len(updates) >= 10:
                update_likes_bulk(updates)
                print(f"  [DB 적재] {len(updates)}건 커밋 완료", flush=True)
                updates = []

            rand_delay = random.uniform(6.0, 13.0)
            print(f"   -> 대기 ({rand_delay:.2f}초)...", flush=True)
            await asyncio.sleep(rand_delay)

            if (i + 1) % 15 == 0:
                print(f"\n[☕ 방화벽 쉼터] 15개 완료! 75초 휴식...", flush=True)
                await asyncio.sleep(75)

        if updates:
            update_likes_bulk(updates)
            print(f"  [DB 적재] 마지막 {len(updates)}건 커밋 완료", flush=True)

        await browser.close()
    if display: display.stop()
    print("\n🎉 [완료] 모바일 위장 + 구조 방어판 likes 보정 작업이 성공적으로 끝났습니다.")

if __name__ == "__main__":
    asyncio.run(run())