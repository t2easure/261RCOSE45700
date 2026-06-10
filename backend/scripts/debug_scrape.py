import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


async def main():
    from playwright.async_api import async_playwright
    from db.database import _get_connection

    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT post_url FROM fashion_posts WHERE id = 8034")
            url = cur.fetchone()[0]

    print(f"URL: {url}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
        await page.goto(url, timeout=20000)
        await page.wait_for_timeout(4000)

        title = await page.title()
        print(f"Title: {title}")

        # 로그인 월 체크
        login_text = await page.evaluate("() => document.body.innerText.slice(0, 500)")
        print(f"Body text (first 500 chars):\n{login_text}\n")

        # 모든 img 태그 src
        imgs = await page.evaluate("""
            () => Array.from(document.querySelectorAll('img')).map(img => ({
                src: img.src.slice(0, 100),
                w: img.naturalWidth,
                h: img.naturalHeight
            }))
        """)
        print(f"이미지 {len(imgs)}개:")
        for img in imgs:
            print(f"  {img['w']}x{img['h']}  {img['src']}")

        await page.screenshot(path="debug_screenshot.png")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
