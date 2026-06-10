"""
특정 post ID 목록을 post_url로 재스크래핑.
프로필 사진이 아닌 '게시물 본문 이미지'를 고르기 위해
naturalWidth가 가장 큰 cdninstagram/fbcdn 이미지를 선택한다.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from db.database import _get_connection
from utils.image_downloader import download_image

DATA_DIR = Path(__file__).parent.parent / "data" / "images"

# check_duplicate_images.py 결과에서 추출한 잘못 채워진 인스타그램 포스트 ID
TARGET_IDS = [
    8037, 8035, 8036, 8031, 8038, 8034, 8033,           # ch_amii
    8101, 8122, 8114, 8120, 8127, 8128, 8102,           # heejaeholic
    8125, 8116,                                          # heejaeholic
    8151, 8150,                                          # jupppal
    8007, 8013, 8014, 8017, 8012, 8019, 8011, 8008, 8015,  # nayoungkeem
    7919, 7904, 7913, 7907,                              # suesasha
    7971, 7967, 7956, 7975, 7981, 7970, 7987, 7968, 7961, 7965, 7958, 7991, 7962, 7977, 7988,  # yoonmida
]


def get_posts(ids: list[int]) -> list[dict]:
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, post_url, account_name FROM fashion_posts WHERE id = ANY(%s)",
                (ids,),
            )
            return [{"id": r[0], "post_url": r[1], "account_name": r[2]} for r in cur.fetchall()]


def update_image_url(post_id: int, new_url: str):
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE fashion_posts SET image_url = %s WHERE id = %s", (new_url, post_id))
        conn.commit()


async def get_post_image_src(page) -> str | None:
    """cdninstagram/fbcdn 이미지 중 naturalWidth가 가장 큰 것을 반환.

    로그인 월이 뜨는 경우 <article> 태그 자체가 없으므로 article 한정 없이
    전체 img에서 찾되, 프로필/댓글 아바타(150x150)나 추천 게시물(480x640)보다
    큰 이미지(가장 큰 것 = 본문 이미지)를 선택한다.
    """
    return await page.evaluate("""
        () => {
            const imgs = Array.from(document.querySelectorAll('img'))
                .filter(img => /cdninstagram|fbcdn/.test(img.src));
            if (imgs.length === 0) return null;
            imgs.sort((a, b) => (b.naturalWidth * b.naturalHeight) - (a.naturalWidth * a.naturalHeight));
            return imgs[0].src;
        }
    """)


async def main():
    posts = get_posts(TARGET_IDS)
    print(f"대상 {len(posts)}개 포스트 재스크래핑 시작\n")

    from playwright.async_api import async_playwright

    ok = fail = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for i, post in enumerate(posts):
            print(f"[{i+1}/{len(posts)}] ID #{post['id']} ({post['account_name']})", end=" ... ")
            if not post["post_url"]:
                print("post_url 없음 ✗")
                fail += 1
                continue
            try:
                page = await browser.new_page()
                await page.goto(post["post_url"], timeout=20000)
                await page.wait_for_timeout(3000)
                src = await get_post_image_src(page)
                await page.close()

                if not src:
                    print("이미지 못찾음 ✗")
                    fail += 1
                    continue

                path = download_image(src, post["account_name"] or "unknown")
                if path:
                    rel = Path(path).relative_to(DATA_DIR)
                    update_image_url(post["id"], f"/images/{rel.as_posix()}")
                    print("✓")
                    ok += 1
                else:
                    print("다운로드 실패 ✗")
                    fail += 1
            except Exception as e:
                print(f"오류 ✗ ({e})")
                fail += 1
        await browser.close()

    print(f"\n완료: ✓ {ok}개 성공, ✗ {fail}개 실패")


if __name__ == "__main__":
    asyncio.run(main())
