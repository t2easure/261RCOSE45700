import asyncio
import json
import re
import sys
import io
import hashlib
import httpx
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path(__file__).parent.parent / "data" / "images"


def download_image(url: str, brand: str) -> str:
    """이미지 다운로드 후 로컬 경로 반환. 실패 시 원본 URL 반환."""
    try:
        h = hashlib.md5(url.encode()).hexdigest()
        save_dir = DATA_DIR / brand
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"{h}.jpg"
        if save_path.exists():
            return f"/images/{brand}/{h}.jpg"
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            r = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and len(r.content) > 1000:
                save_path.write_bytes(r.content)
                return f"/images/{brand}/{h}.jpg"
    except Exception:
        pass
    return url

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

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
    'arrow', 'button', 'sprite', 'ui/', 'favicon',

    # 유니클로 노이즈
    'swatch', 'color-chip', '/banner', 'campaign', 'collab', '/chip/', 'width=36',
    'peanuts', 'snoopy', 'miffy', 'sanrio', 'monchhichi', 'graphic-t',
    'lifewear-for-a', 'sustainability', 'anniversary',

    # H&M 노이즈
    'category-banner', 'editorial',

    # SPAO, Topten, Zara 공통 UI 및 배너 노이즈 추가 (핵심)
    'bt_', 'btn_', 'top_cart', 'top_wish', 'top_search', 'top_mypage',
    'q_r_bt', 'q_r_top', 'quick_today', 'no-bg-btn', 'view_sns',
    'transparent-background', 'introapp_floating', 'site-brand', 'bt_ftc'
]

# 브랜드별 상품 URL 패턴 (리스팅에서 상품 링크만 필터링)
BRAND_PRODUCT_URL_PATTERNS = {
    "spao":    ["/i/item"],
    "topten":  ["/product", "/goods", "itemNo=", "goodsNo="],
    "hm":      ["/productpage.", "/product.", "ladies/", "men/"],
    "zara":    ["-p"],
    "uniqlo":  ["/ko/ko/products/", "E4"],
}

# 브랜드별 CDN 키워드 화이트리스트 — 없으면 모든 도메인 허용
BRAND_CDN = {
    "hm": ["hmgoepprod", "hm.com"],
    "uniqlo": ["uniqlo.com"],
    "spao": ["spao.com", "poxo.com", "elandrs.com"],  # 스파오 이미지 서버
    "topten": ["goodwearmall.com"],            # 탑텐(신성통상) 전용몰 서버
    "musinsa": ["musinsa.com", "msscdn.net"],  # 무신사 서버 (musinsa_standard)
    "zara": ["zara.net", "zara.com"],          # 자라 서버
}


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


def get_brand_key(brand: str) -> str:
    return brand.split("_")[0]


def is_fashion_image(url: str, brand_key: str) -> bool:
    u = url.lower()

    # 1. 노이즈 패턴 제외
    if any(p in u for p in NOISE_PATTERNS):
        return False

    # 2. 브랜드 CDN 화이트리스트 — 해당 브랜드 CDN 이미지만 허용
    cdn_keywords = BRAND_CDN.get(brand_key)
    if cdn_keywords and not any(kw in u for kw in cdn_keywords):
        return False

    # 3. 이미지 확장자 체크
    if not any(ext in u for ext in ['.jpg', '.jpeg', '.png', '.webp', 'format=webp']):
        return False

    # 4. 소형 이미지 제거 (imwidth 기준)
    m = re.search(r'[?&]imwidth=(\d+)', url)
    if m and int(m.group(1)) < 600:
        return False

    # 5. 소형 이미지 제거 (w= 기준)
    m2 = re.search(r'[?&]w=(\d+)', url)
    if m2 and int(m2.group(1)) < 300:
        return False

    return True


def get_existing_urls(brand: str) -> set:
    """price가 이미 채워진 post_url만 반환 (price 없으면 재수집 대상)"""
    from db.database import _get_connection
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT post_url FROM fashion_posts WHERE account_name = %s AND price IS NOT NULL",
                (brand,)
            )
            return {row[0] for row in cur.fetchall() if row[0]}


async def fetch_product_detail(context, product_url: str) -> dict:
    """상품 상세 페이지에서 이미지 URL + 가격 + 소재 추출."""
    result = {"image_url": None, "price": None, "material_info": None}
    page = None
    try:
        page = await context.new_page()
        await page.goto(product_url, wait_until="domcontentloaded", timeout=10000)
        await asyncio.sleep(2)
        data = await page.evaluate("""
            () => {
                // 메인 이미지: 가장 큰 img 찾기
                let bestImg = null, bestSize = 0;
                document.querySelectorAll('img').forEach(img => {
                    const size = (img.naturalWidth || img.width || 0) * (img.naturalHeight || img.height || 0);
                    if (size > bestSize) {
                        bestSize = size;
                        let url = img.src || img.currentSrc;
                        if (img.srcset) {
                            const parts = img.srcset.split(',');
                            const last = parts[parts.length - 1].trim().split(' ')[0];
                            if (last) url = last;
                        }
                        bestImg = url || null;
                    }
                });

                // 가격: JSON-LD 우선, 없으면 텍스트에서 추출
                let price = null;
                try {
                    const lds = document.querySelectorAll('script[type="application/ld+json"]');
                    for (const ld of lds) {
                        const data = JSON.parse(ld.textContent);
                        const offers = data.offers || (data['@graph'] && data['@graph'].find(x => x.offers)?.offers);
                        if (offers) {
                            const p = parseFloat((Array.isArray(offers) ? offers[0] : offers).price);
                            if (p >= 5000) { price = Math.round(p); break; }
                        }
                    }
                } catch(e) {}
                if (!price) {
                    const priceMatches = [...document.body.textContent.matchAll(/₩\s*([0-9,]{4,})|([0-9,]{4,})\s*원/g)];
                    const prices = priceMatches
                        .map(m => parseInt((m[1]||m[2]).replace(/,/g, '')))
                        .filter(v => v >= 5000 && v <= 2000000);
                    if (prices.length) price = Math.max(...prices);
                }

                // 소재 (색상/사이즈 정보 제외, 실제 원단 정보만)
                let material = null;
                const matKeywords = ['혼용률', '소재', '재질', '원단', 'Material', 'Fabric', 'Composition'];
                const excludeKeywords = ['색상', '사이즈', 'Color', 'Size', '컬러', '배송'];
                const els = Array.from(document.querySelectorAll('th, td, dt, dd'));
                for (const el of els) {
                    const text = el.textContent.trim();
                    if (matKeywords.some(k => text === k || text.startsWith(k + ':')) &&
                        !excludeKeywords.some(k => text.includes(k))) {
                        const next = el.nextElementSibling;
                        const val = next ? next.textContent.trim() : '';
                        // 실제 소재 정보: 퍼센트(%) 또는 소재명 포함
                        if (val && (val.includes('%') || val.match(/면|폴리|나일론|레이온|아크릴|울|린넨|코튼|모달|텐셀|비스코스/))) {
                            material = val;
                            break;
                        }
                    }
                }

                return { image_url: bestImg, price, material_info: material };
            }
        """)
        result.update(data)
    except Exception as e:
        print(f"[Detail] {product_url} 오류: {e}")
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass
    return result


async def scrape_brand(brand: str, url: str) -> list[dict]:
    brand_key = get_brand_key(brand)
    now = datetime.now(timezone.utc)
    posts = []
    existing_urls = get_existing_urls(brand)

    async with async_playwright() as p:
        import os
        force_headless = os.environ.get("HEADLESS", "true").lower() != "false"
        headless = True if force_headless else (brand_key not in ("hm", "zara"))
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
            await page.goto(url, wait_until="domcontentloaded", timeout=90000)
            await asyncio.sleep(5)

            # 쿠키 동의 클릭 (최초 1회만)
            for selector in ['#onetrust-accept-btn-handler', '[id*="accept"]', '[class*="accept-cookie"]']:
                try:
                    btn = page.locator(selector).first
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        await asyncio.sleep(1)
                        break
                except Exception:
                    pass

            current_page = 1
            max_pages = 1000
            seen_urls_global = set() # 전체 페이지에 걸쳐 중복 수집을 막기 위한 세트

            while current_page <= max_pages:
                print(f"[{brand}] --- {current_page} 페이지 수집 시작 ---")

                # 1. 지연 로딩 트리거를 위한 스크롤 (자라/H&M은 무한 스크롤)
                if "zara" in brand:
                    print(f"[{brand}] 무한 스크롤 시작 (바닥에 도달할 때까지)...")
                    last_height = await page.evaluate("document.body.scrollHeight")

                    while True:
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await asyncio.sleep(2.5)
                        new_height = await page.evaluate("document.body.scrollHeight")
                        if new_height == last_height:
                            await asyncio.sleep(1.5)
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            new_height = await page.evaluate("document.body.scrollHeight")
                            if new_height == last_height:
                                print(f"[{brand}] 최하단 바닥에 도달했습니다. 무한 스크롤 종료!")
                                break
                        last_height = new_height
                elif "hm" in brand:
                    print(f"[{brand}] 무한 스크롤 시작 (바닥에 도달할 때까지)...")
                    last_height = await page.evaluate("document.body.scrollHeight")
                    while True:
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await asyncio.sleep(2)
                        new_height = await page.evaluate("document.body.scrollHeight")
                        if new_height == last_height:
                            await asyncio.sleep(1.5)
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            new_height = await page.evaluate("document.body.scrollHeight")
                            if new_height == last_height:
                                print(f"[{brand}] 최하단 바닥에 도달했습니다.")
                                break
                        last_height = new_height
                else:
                    # 유니클로, 스파오, 탑텐 같은 일반 페이징 사이트는 기존처럼 5번만 슬쩍 내리기
                    for i in range(5):
                        await page.evaluate("window.scrollBy(0, window.innerHeight * 1.2)")
                        await asyncio.sleep(1.5)

                # 2. H&M: 리스팅 페이지에서 직접 {img, price, href} 추출
                if brand_key == "hm":
                    hm_cards = await page.evaluate("""
                        () => {
                            const results = [];
                            document.querySelectorAll('img').forEach(img => {
                                let src = img.src || img.currentSrc || '';
                                if (img.srcset) {
                                    const parts = img.srcset.split(',');
                                    const last = parts[parts.length-1].trim().split(' ')[0];
                                    if (last) src = last;
                                }
                                if (!src || src.startsWith('data:')) return;
                                // 부모 a 태그 찾기
                                let el = img;
                                let href = null;
                                while (el && el !== document.body) {
                                    if (el.tagName === 'A' && el.href) { href = el.href; break; }
                                    el = el.parentElement;
                                }
                                // 가격: 이미지 근처 텍스트에서
                                let price = null;
                                const container = img.closest('li, article, [class*="product"], [class*="card"]');
                                if (container) {
                                    const priceMatch = container.textContent.match(/₩\s*([0-9,]{4,})|([0-9,]{4,})\s*원/);
                                    if (priceMatch) {
                                        const v = parseInt((priceMatch[1] || priceMatch[2]).replace(/,/g,''));
                                        if (v >= 5000) price = v;
                                    }
                                }
                                results.push({ img: src, href, price });
                            });
                            return results;
                        }
                    """)
                    print(f"[{brand}] hm_cards 원본: {len(hm_cards)}개")
                    for card in hm_cards[:50]:
                        img_url = card.get("img")
                        product_url = card.get("href") or url
                        price = card.get("price")
                        if not img_url:
                            continue
                        norm = normalize_url(img_url, url)
                        if not norm or not is_fashion_image(norm, brand_key):
                            continue
                        if norm in existing_urls or norm in seen_urls_global:
                            continue
                        seen_urls_global.add(norm)
                        local_url = await asyncio.get_event_loop().run_in_executor(None, download_image, norm, brand)
                        posts.append({
                            "source": "lookbook",
                            "account_name": brand,
                            "post_url": product_url,
                            "image_url": local_url,
                            "caption": "",
                            "likes": None,
                            "posted_at": now,
                            "price": price,
                            "material_info": None,
                        })
                    print(f"[{brand}] 리스팅 수집: {len(posts)}개")
                    break

                # 2. 상품 상세 URL 수집 (리스팅 페이지에서 href만 추출)
                all_hrefs: list[str] = await page.evaluate("""
                    () => {
                        const hrefs = new Set();
                        document.querySelectorAll('a[href]').forEach(a => {
                            const h = a.href;
                            if (h && h.startsWith('http') && !h.includes('#') &&
                                !h.match(/\.(jpg|jpeg|png|webp|gif|svg|css|js)$/i)) {
                                hrefs.add(h);
                            }
                        });
                        return Array.from(hrefs);
                    }
                """)
                # 브랜드별 상품 URL 패턴으로 필터링
                patterns = BRAND_PRODUCT_URL_PATTERNS.get(brand_key, [])
                if patterns:
                    raw_hrefs = [h for h in all_hrefs if any(p in h for p in patterns)]
                else:
                    raw_hrefs = all_hrefs

                # Zara: -p숫자.html 형식만 상품 URL로 인정
                if brand_key == "zara":
                    raw_hrefs = [h for h in raw_hrefs if re.search(r'-p\d+\.html', h)]

                # 유니클로: colorDisplayCode 색상 변형 중복 제거 (상품 ID 기준 1개만)
                if brand_key == "uniqlo":
                    seen_products = {}
                    for h in raw_hrefs:
                        base = re.sub(r'[?&]colorDisplayCode=[^&]*', '', h).rstrip('?&')
                        if base not in seen_products:
                            seen_products[base] = h
                    raw_hrefs = list(seen_products.values())
                print(f"[{brand}] 수집된 상품 URL 수: {len(raw_hrefs)}개 (전체 링크: {len(all_hrefs)}개)")

                # 3. 이미 수집된 URL 제외 + 중복 제거
                new_hrefs = [h for h in raw_hrefs if h not in seen_urls_global and h not in existing_urls]
                for h in new_hrefs:
                    seen_urls_global.add(h)

                page_post_count = len(new_hrefs)
                print(f"[{brand}] {current_page} 페이지: 신규 {page_post_count}개 (누적: {len(seen_urls_global)}개)")

                # early stop: 신규가 없으면 중단
                if page_post_count == 0 and current_page > 1:
                    print(f"[{brand}] 신규 URL 없음 → 중단")
                    break

                # 4. 상세 페이지 방문 (이미지 + 가격 + 소재)
                sem = asyncio.Semaphore(5)
                async def _visit(product_url):
                    async with sem:
                        detail = await fetch_product_detail(context, product_url)
                        img_url = detail.get("image_url")
                        if not img_url:
                            return
                        norm = normalize_url(img_url, product_url)
                        if not norm or not norm.startswith("http"):
                            return
                        # 상세 페이지는 CDN 체크 없이 확장자만 확인
                        if not any(ext in norm.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                            return
                        if any(p in norm.lower() for p in NOISE_PATTERNS):
                            return
                        local_url = await asyncio.get_event_loop().run_in_executor(None, download_image, norm, brand)
                        posts.append({
                            "source": "lookbook",
                            "account_name": brand,
                            "post_url": product_url,
                            "image_url": local_url,
                            "caption": "",
                            "likes": None,
                            "posted_at": now,
                            "price": detail.get("price"),
                            "material_info": detail.get("material_info"),
                        })

                # 무한스크롤 브랜드(zara, hm)는 페이지당 100개, 나머지는 전체
                visit_limit = 100 if brand_key in ("zara", "hm") else len(new_hrefs)
                await asyncio.gather(*[_visit(h) for h in new_hrefs[:visit_limit]])
                print(f"[{brand}] {current_page} 페이지 상세 수집 완료 (누적: {len(posts)}개)")

                # 4. 다음 페이지로 이동
                if current_page >= max_pages:
                    print(f"[{brand}] 설정한 최대 페이지({max_pages})에 도달했습니다.")
                    break

                next_btn_selectors = [
                    # H&M
                    '[data-elid="pagination-next-page-button"]',
                    'button:has-text("다음 페이지 보기")',

                    # 무신사, 스파오, 탑텐 등에서 자주 쓰이는 페이징 형태
                    'a.next', 'a.btn_next', 'a.page-next', 'a.paging_next',
                    'button.next', '.pagination-next', '.page-next',

                    # 화살표 이미지를 버튼으로 쓰는 경우 (한국 쇼핑몰 단골 패턴)
                    'a:has(img[alt*="다음"])', 'a:has(img[alt*="next"])',
                    '[aria-label="Next"]', '[title="Next"]','a[href*="page="] img[src*="next"]',
                    '.pagination a.next', '.paging-btn.btn.next',
                    '[class*="Pagination"] button:last-child',
                    'a.fa-angle-right',

                    # 텍스트 형태
                    'a:has-text(">")', 'button:has-text("더보기")', 'a:has-text("더보기")'

                    'a:has-text("더보기")',

                    # 스파오 전용 다음 버튼 선택자
                    'a:has(img[src*="btn_page_next"])',
                    'a:has(img[src*="next"])'
                ]

                clicked = False
                for selector in next_btn_selectors:
                    try:
                        next_btn = page.locator(selector).first
                        # 버튼이 화면에 보이고, 비활성화(disabled) 상태가 아닐 때 클릭
                        if await next_btn.is_visible(timeout=1000) and not await next_btn.is_disabled():
                            await next_btn.click()

                            # 네트워크 통신이 어느 정도 잠잠해질 때까지 대기 (페이지 이동 로딩 대기)
                            try:
                                await page.wait_for_load_state("networkidle", timeout=10000)
                            except:
                                pass # 타임아웃 나도 스크립트 멈추지 않고 계속 진행

                            await asyncio.sleep(3) # 추가 안전 대기
                            clicked = True
                            break
                    except Exception:
                        continue # 이 선택자가 아니면 다음 선택자로 넘어감

                # 어떤 버튼으로도 클릭하지 못했다면 마지막 페이지로 간주하고 종료
                if not clicked:
                    print(f"[{brand}] 더 이상 '다음' 버튼을 찾을 수 없습니다. (마지막 페이지)")
                    break

                current_page += 1

            print(f"[Brand] {brand}: 총 {current_page}페이지 탐색, 최종 {len(posts)}개 이미지 수집 완료")

        except Exception as e:
            # ... 기존 에러 처리 로직 ...
            print(f"[Brand] {brand} 오류: {e}")
            log_crawl(source="lookbook", game="fashion", status="error", error_msg=str(e))
        finally:
            await browser.close()

    return posts


async def run_brand_scraper(_status_callback=None) -> int:
    brand_urls = load_brand_urls()
    total = 0

    # 로컬 db 디렉토리 설정 및 자동 생성 (현재 실행 중인 CRAI 폴더 기준)
    local_db_dir = Path("db")
    local_db_dir.mkdir(parents=True, exist_ok=True)

    for brand, url in brand_urls.items():
        print(f"[Brand] 수집 시작: {brand}")
        if _status_callback:
            _status_callback("running", f"브랜드 스크래핑 중: {brand}")
        posts = await scrape_brand(brand, url)

        if posts:
            saved = save_fashion_posts(posts)
            log_crawl(source="lookbook", game="fashion", status="success", count=saved)
            print(f"[Brand] {brand}: {saved}개 실제 RDS 저장 완료")

            # 2. 💡 로컬 db 디렉토리에 브랜드별 JSON 파일로 저장
            local_posts = []
            for p in posts:
                p_copy = p.copy()
                # datetime 객체는 JSON으로 바로 저장 안 되므로 문자열로 변환
                if hasattr(p_copy['posted_at'], 'isoformat'):
                    p_copy['posted_at'] = p_copy['posted_at'].isoformat()
                local_posts.append(p_copy)

            local_file_path = local_db_dir / f"{brand}.json"
            with open(local_file_path, "w", encoding="utf-8") as f:
                json.dump(local_posts, f, ensure_ascii=False, indent=2)
            print(f"[Local] {brand}: {len(local_posts)}개 로컬 db 저장 완료 ({local_file_path})")

            total += saved
        else:
            print(f"[Brand] {brand}: 이미지 없음")

    print(f"[Brand] 전체 완료: 총 {total}개 데이터 RDS 및 로컬 DB 저장 완료!")
    return total


if __name__ == "__main__":
    asyncio.run(run_brand_scraper())
