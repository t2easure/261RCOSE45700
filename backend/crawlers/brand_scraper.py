import asyncio
import json
import re
import sys
import io
from pathlib import Path
from datetime import datetime, timezone

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.database import save_fashion_posts, log_crawl

URLS_PATH = Path(__file__).parent.parent.parent / "config" / "brand_urls.json"

# 브랜드별 상품 이미지 CSS 셀렉터 (없으면 전체 img 태그 파싱)
BRAND_SELECTORS = {
    "hm":     "img[src*='hm.com']",
    "asos":   "img[src*='asos']",
    "uniqlo": "img[src*='uniqlo']",
    "cos":    "img[src*='cos']",
    "arket":  "img[src*='arket']",
}

NOISE_PATTERNS = [
    'icon', 'logo', 'svg', 'pixel', 'tracking', 'placeholder', 'spacer',
    'flags/', '/flag/', 'payment', 'visa', 'mastercard', 'paypal', 'amex',
    'american-express', '/card', 'badge', 'social/', 'rating', 'star',
    'arrow', 'button', 'sprite', 'ui/', 'cms/', 'favicon',
]


def load_brand_urls() -> dict:
    with open(URLS_PATH, encoding="utf-8") as f:
        return json.load(f)


def normalize_url(src: str, base_url: str) -> str | None:
    if not src or src.startswith('data:'):
        return None
    if src.startswith('//'):
        return 'https:' + src
    if src.startswith('/'):
        domain = re.match(r'https?://[^/]+', base_url)
        return domain.group(0) + src if domain else None
    if src.startswith('http'):
        return src
    return None


def is_fashion_image(url: str) -> bool:
    u = url.lower()
    
    # 1. 노이즈 패턴 제외
    if any(p in u for p in NOISE_PATTERNS):
        return False
        
    # 2. H&M 이미지 URL 패턴 유연하게 확장 (hmgoepprod 또는 hm.com 포함)
    if 'hmgoepprod' in u or 'hm.com' in u:
        return True
        
    # 3. 기본 확장자 체크
    if not any(ext in u for ext in ['.jpg', '.jpeg', '.png', '.webp']):
        return False
        
    # 4. 해상도 필터링
    m = re.search(r'[?&]w=(\d+)', url)
    if m and int(m.group(1)) < 200:
        return False
        
    return True


async def scrape_brand(brand: str, url: str) -> list[dict]:
    now = datetime.now(timezone.utc)
    posts = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )
        page = await context.new_page()

        try:
            await Stealth().apply_stealth_async(page)
            print(f"[{brand}] 페이지 접속 중...")
            
            # 페이지 로드 타임아웃을 넉넉히 주고 대기합니다.
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(3)

            # --- (쿠키 동의 클릭 및 스크롤 로직은 기존과 동일하게 유지) ---
            for selector in ['#onetrust-accept-btn-handler', '[id*="accept"]', '[class*="accept-cookie"]']:
                try:
                    btn = page.locator(selector).first
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        await asyncio.sleep(1)
                        break
                except Exception:
                    pass

            print(f"[{brand}] 지연 로딩 트리거를 위한 스크롤 시작...")
            for i in range(5):
                await page.evaluate("window.scrollBy(0, window.innerHeight * 1.2)")
                await asyncio.sleep(1.5)

            raw_urls: list[str] = await page.evaluate("""
                () => {
                    const imgs = Array.from(document.querySelectorAll('img, picture source'));
                    const urls = new Set();
                    imgs.forEach(el => {
                        if (el.tagName === 'IMG') {
                            if (el.src) urls.add(el.src);
                            if (el.currentSrc) urls.add(el.currentSrc);
                            ['data-src','data-lazy-src','data-original'].forEach(attr => {
                                const v = el.getAttribute(attr);
                                if (v) urls.add(v);
                            });
                        }
                        if (el.srcset) {
                            el.srcset.split(',').forEach(s => {
                                const u = s.trim().split(' ')[0];
                                if (u) urls.add(u);
                            });
                        }
                    });
                    return Array.from(urls);
                }
            """)

            print(f"[{brand}] 이미지 URL {len(raw_urls)}개 발견")

            seen = set()
            for src in raw_urls:
                norm = normalize_url(src, url)
                if not norm or norm in seen:
                    continue
                seen.add(norm)
                
                if not is_fashion_image(norm):
                    continue
                    
                posts.append({
                    "source": "lookbook",
                    "account_name": brand,
                    "post_url": f"{url}#{hash(norm) % 999999}",
                    "image_url": norm,
                    "caption": "",
                    "likes": None,
                    "posted_at": now,
                })

            print(f"[Brand] {brand}: 필터 후 {len(posts)}개 이미지 수집 완료")

        except Exception as e:
            print(f"[Brand] {brand} 오류: {e}")
            log_crawl(source="lookbook", game="fashion", status="error", error_msg=str(e))
        finally:
            await browser.close()

    return posts[:50]


async def run_brand_scraper() -> int:
    brand_urls = load_brand_urls()
    total = 0

    for brand, url in brand_urls.items():
        print(f"[Brand] 수집 시작: {brand}")
        posts = await scrape_brand(brand, url)
        if posts:
            saved = save_fashion_posts(posts)
            log_crawl(source="lookbook", game="fashion", status="success", count=saved)
            print(f"[Brand] {brand}: {saved}개 저장")
            total += saved
        else:
            print(f"[Brand] {brand}: 이미지 없음")

    print(f"[Brand] 전체 완료: {total}개 저장")
    return total


if __name__ == "__main__":
    asyncio.run(run_brand_scraper())
