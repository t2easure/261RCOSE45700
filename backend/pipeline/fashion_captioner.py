import os
import asyncio
import base64
import httpx
import anthropic
from tqdm.asyncio import tqdm
from pathlib import Path
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv(Path(__file__).parent.parent / ".env")
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from db.database import get_uncaptioned_posts, save_caption

CAPTION_PROMPT = """이 패션 이미지를 분석해줘.
만약 이미지가 20대 여성 패션(여성 의류, 여성 코디, 여성 룩북 등)이 아니라면 SKIP 이라고만 답해.
남성복, 아동복, 패션과 무관한 이미지(음식, 풍경, 인테리어 등)도 SKIP.
여성 패션이 맞다면 실루엣, 소재, 컬러, 스타일, 아이템을 포함해 3~4문장의 전문 용어로 한국어 캡션을 작성해줘.
마크다운 기호(#, **, * 등)나 특수문자 없이 일반 텍스트로만 작성해줘."""

async def get_image_base64(client, url: str):
    try:
        # H&M 차단 방지를 위해 헤더 추가
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = await client.get(url, timeout=15.0, headers=headers)
        resp.raise_for_status()
        content_type = resp.headers.get('Content-Type', 'image/jpeg')
        return content_type, base64.b64encode(resp.content).decode('utf-8')
    except: return None, None

async def process_post(ant_client, http_client, post, semaphore):
    async with semaphore:
        media_type, base64_data = await get_image_base64(http_client, post['image_url'])
        if not base64_data: return False

        try:
            response = await ant_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64_data}},
                    {"type": "text", "text": CAPTION_PROMPT}
                ]}]
            )
            caption = response.content[0].text.strip()
            if caption.upper().startswith("SKIP"):
                from db.database import delete_post
                delete_post(post["id"])
                tqdm.write(f"🚫 ID #{post['id']} 여성 패션 아님 → 삭제")
                return False
            save_caption(post["id"], caption)
            return True
        except Exception as e:
            # 에러 발생 시 진행률 바를 방해하지 않고 로그 출력
            tqdm.write(f"❌ ID #{post['id']} 실패: {e}")
            return False

async def run_captioning(batch_size: int = 50, per_account: int = 50, since: str = None):
    ant_client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    posts = get_uncaptioned_posts(limit=batch_size, per_account=per_account, since=since)
    
    if not posts:
        print("✨ 분석할 이미지가 없습니다.")
        return

    # 동시 실행 개수를 5개 정도로 살짝 낮췄습니다 (교수님 키니까 안전하게!)
    semaphore = asyncio.Semaphore(5)
    
    async with httpx.AsyncClient() as http_client:
        tasks = [process_post(ant_client, http_client, post, semaphore) for post in posts]
        
        print(f"\n🚀 비동기 파이프라인 가동 (타겟: {len(posts)}장)\n")
        results = await tqdm.gather(*tasks)
        
    print(f"\n✅ 완료: {sum(results)}/{len(posts)}개 성공!")

if __name__ == "__main__":
    asyncio.run(run_captioning())