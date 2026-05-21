import os
import asyncio
import anthropic
from tqdm.asyncio import tqdm
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from db.database import get_uncaptioned_meta_posts, save_caption_meta

META_PROMPT = """아래 패션 캡션에서 핵심 키워드만 추출해서 쉼표로 구분해줘.
실루엣, 소재, 컬러, 스타일, 아이템 카테고리 위주로, 일반인도 이해할 수 있는 단어로.
5~8개 이내로 짧게.

캡션: {caption}

예시 출력: 오버사이즈, 린넨, 베이지, 캐주얼, 셔츠, 아이보포인트"""

async def process_post(client, post, semaphore):
    async with semaphore:
        try:
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=100,
                messages=[{"role": "user", "content": META_PROMPT.format(caption=post["caption_ai"])}]
            )
            meta = response.content[0].text.strip()
            save_caption_meta(post["id"], meta)
            return True
        except Exception as e:
            tqdm.write(f"✗ ID #{post['id']} 실패: {e}")
            return False

async def run_meta_captioning(batch_size: int = 10000, since: str = None):
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    posts = get_uncaptioned_meta_posts(limit=batch_size, since=since)

    if not posts:
        print("✨ 처리할 포스트가 없습니다.")
        return

    semaphore = asyncio.Semaphore(5)
    tasks = [process_post(client, post, semaphore) for post in posts]

    print(f"\n🔄 2차 캡셔닝 시작 ({len(posts)}개)\n")
    results = await tqdm.gather(*tasks)
    print(f"\n✅ 완료: {sum(results)}/{len(posts)}개 성공!")

if __name__ == "__main__":
    asyncio.run(run_meta_captioning())
