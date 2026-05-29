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

META_PROMPT = """아래 패션 이미지 캡션에서 검색에 유용한 핵심 키워드를 추출해줘.
스타일, 색상, 소재, 아이템, 실루엣 중심으로 추출하되, 색상과 소재는 유사어도 함께 포함해줘.
예: 베이지 → 베이지, 아이보리, 크림 / 코튼 → 코튼, 면, 캐주얼
쉼표로 구분해서 한 줄로만 반환해. 설명이나 다른 말 없이 키워드만:

캡션: {caption}"""

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

    semaphore = asyncio.Semaphore(15)
    tasks = [process_post(client, post, semaphore) for post in posts]

    print(f"\n🔄 2차 캡셔닝 시작 ({len(posts)}개)\n")
    results = await tqdm.gather(*tasks)
    print(f"\n✅ 완료: {sum(results)}/{len(posts)}개 성공!")

if __name__ == "__main__":
    asyncio.run(run_meta_captioning())
