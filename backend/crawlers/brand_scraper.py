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
from utils.image_downloader import download_images

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

# 브랜드별 CDN 키워드 화이트리스트 — 없으면 모든 도메인 허용
BRAND_CDN = {
    "hm": ["hmgoepprod", "hm.com"],
    "uniqlo": ["uniqlo.com"],
    "spao": ["spao.com", "poxo.com"],          # 스파오 이미지 서버
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


async def scrape_brand(brand: str, url: str) -> list[dict]:
    brand_key = get_brand_key(brand)
    now = datetime.now(timezone.utc)
    posts = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
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
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(3)

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
            max_pages = 16  # 최대 수집할 페이지 수 설정 (끝까지 가려면 아주 큰 숫자로 둬도 됩니다)
            seen_urls_global = set() # 전체 페이지에 걸쳐 중복 수집을 막기 위한 세트

            while current_page <= max_pages:
                print(f"[{brand}] --- {current_page} 페이지 수집 시작 ---")

                # 1. 지연 로딩 트리거를 위한 스크롤
                scroll_count = 50 if brand in ["zara_women", "musinsa_standard_women"] else 5  
                for i in range(scroll_count):
                    await page.evaluate("window.scrollBy(0, window.innerHeight * 1.2)")
                    await asyncio.sleep(2.5)
                
                # 1. 지연 로딩 트리거를 위한 스크롤 (자라는 끝날 때까지 무한 스크롤)
                if "zara" in brand:
                    print(f"[{brand}] 무한 스크롤 시작 (바닥에 도달할 때까지)...")
                    last_height = await page.evaluate("document.body.scrollHeight")
                    
                    while True:
                        # 1. 페이지의 최하단으로 스크롤 이동
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        # 새로운 상품 이미지가 로딩될 시간을 넉넉히 대기
                        await asyncio.sleep(2.5)
                        
                        # 2. 스크롤 후의 새로운 페이지 높이 측정
                        new_height = await page.evaluate("document.body.scrollHeight")
                        
                        # 이전 높이와 스크롤 후 높이가 같다면 더 이상 내려갈 곳이 없다는 뜻
                        if new_height == last_height:
                            # 인터넷이 잠깐 느려서 안 불려온 걸 수도 있으니, 1.5초 더 쉬고 한 번만 더 확인해보기 (방어 코드)
                            await asyncio.sleep(1.5)
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            new_height = await page.evaluate("document.body.scrollHeight")
                            
                            if new_height == last_height:
                                print(f"[{brand}] 최하단 바닥에 도달했습니다. 무한 스크롤 종료!")
                                break
                                
                        last_height = new_height
                else:
                    # 유니클로, 스파오, 탑텐 같은 일반 페이징 사이트는 기존처럼 5번만 슬쩍 내리기
                    for i in range(5):
                        await page.evaluate("window.scrollBy(0, window.innerHeight * 1.2)")
                        await asyncio.sleep(1.5)

                # 2. 이미지 추출 (이전 답변에서 개선한 자바스크립트 로직 그대로 사용)
                raw_urls: list[str] = await page.evaluate("""
                    () => {
                        const imgs = Array.from(document.querySelectorAll('img'));
                        const urls = new Set();
                        imgs.forEach(el => {
                            if ((el.naturalWidth > 0 && el.naturalWidth < 150) || 
                                (el.width > 0 && el.width < 150)) {
                                return;
                            }
                            let url = el.src || el.currentSrc;
                            if (!url) {
                                ['data-src', 'data-lazy-src', 'data-original'].forEach(attr => {
                                    const v = el.getAttribute(attr);
                                    if (v) url = v;
                                });
                            }
                            if (el.srcset) {
                                const sources = el.srcset.split(',');
                                const lastSource = sources[sources.length - 1].trim().split(' ');
                                if (lastSource) url = lastSource;
                            }
                            if (url) urls.add(url);
                        });
                        return Array.from(urls);
                    }
                """)

                print(f"[{brand}] 화면에서 긁어온 원본 URL 개수: {len(raw_urls)}개")
                if brand == 'topten_women' and len(raw_urls) > 0:
                    print(f"[DEBUG] 탑텐 원본 샘플: {raw_urls[:3]}")

                # 3. 데이터 정제 및 리스트에 추가
                page_post_count = 0
                for src in raw_urls:
                    # 💡 추가된 방어 코드: src가 문자열(str)이 아니면 무시하고 넘어감
                    if not isinstance(src, str):
                        continue
                        
                    norm = normalize_url(src, url)
                    # 이미 수집한 URL이거나 노이즈 이미지면 패스
                    if not norm or norm in seen_urls_global or not is_fashion_image(norm, brand_key):
                        if brand in ['topten_women', 'musinsa_standard_women'] and page_post_count == 0:
                            print(f"[DEBUG] {brand} 필터에 막혀 버려짐: {norm}")
                        continue
                    
                    seen_urls_global.add(norm)
                    page_post_count += 1
                    
                    posts.append({
                        "source": "lookbook",
                        "account_name": brand,
                        "post_url": f"{page.url}#{hash(norm) % 999999}", 
                        "image_url": norm,
                        "caption": "",
                        "likes": None,
                        "posted_at": now,
                    })

                print(f"[{brand}] {current_page} 페이지: {page_post_count}개 추가됨 (누적: {len(posts)}개)")
                
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


async def run_brand_scraper() -> int:
    brand_urls = load_brand_urls()
    total = 0
    
    # 로컬 db 디렉토리 설정 및 자동 생성 (현재 실행 중인 CRAI 폴더 기준)
    local_db_dir = Path("db")
    local_db_dir.mkdir(parents=True, exist_ok=True)

    for brand, url in brand_urls.items():
        print(f"[Brand] 수집 시작: {brand}")
        posts = await scrape_brand(brand, url)
        if posts:
            download_images(posts)
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
