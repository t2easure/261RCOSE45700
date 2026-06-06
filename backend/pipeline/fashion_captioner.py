import os
import asyncio
import base64
import httpx
import anthropic
import mimetypes
import imghdr
from tqdm.asyncio import tqdm
from pathlib import Path
from dotenv import load_dotenv
import sys

# 환경 변수 로드
load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent))
from db.database import get_uncaptioned_posts, get_all_posts_for_recaption, save_caption, delete_post

# 프로젝트 루트(backend/data) 절대 경로 설정
BASE_DIR = Path(__file__).parent.parent / "data"

CAPTION_PROMPT = """이 이미지를 분석해줘.
다음 중 하나라도 해당하면 SKIP 이라고만 답해:
- 브랜드 로고, 텍스트 배너, 광고 그래픽 (옷이 없는 이미지)
- 남성복, 아동복
- 음식, 풍경, 인테리어 등 패션 무관 이미지

여성 패션 의류 이미지라면 (모델 착용샷 또는 제품 단독컷 모두 포함) 아래 형식으로 작성해줘.
마크다운 기호(#, **, * 등)나 특수문자 없이 일반 텍스트로만 작성해줘.

[스타일] 전체적인 스타일 분위기 (예: 미니멀 캐주얼, 페미닌 로맨틱, 스트리트 캐주얼)
[실루엣] 핏과 실루엣 (예: 오버사이즈, 슬림핏, A라인, 와이드)
[컬러] 주요 색상 (예: 아이보리, 블랙, 베이지, 카키)
[소재] 소재 추정 (예: 코튼, 린넨, 니트, 데님, 시폰)
[아이템] 착용 아이템 목록 (예: 와이드팬츠, 크롭티, 오버사이즈 재킷)
[디테일] 눈에 띄는 디테일 (예: 버튼 디테일, 러플, 절개선, 프린트)
[설명] 위 요소를 종합한 2문장 설명

출력 예시:
[스타일] 미니멀 캐주얼
[실루엣] 오버사이즈
[컬러] 아이보리, 베이지
[소재] 코튼, 린넨
[아이템] 와이드 슬랙스, 크롭 반팔티, 크로스백
[디테일] 톤온톤 배색, 루즈핏
[설명] 기본 아이템들의 톤온톤 조합으로 완성한 미니멀 캐주얼 스타일입니다. 오버사이즈 실루엣과 린넨 소재로 편안하면서도 세련된 여름 룩을 연출했습니다.

출력 예시 2:
[스타일] 페미닌 로맨틱
[실루엣] A라인, 플레어
[컬러] 화이트, 핑크
[소재] 시폰, 레이스
[아이템] 플레어 미디 스커트, 레이스 블라우스, 스트링 백
[디테일] 러플 디테일, 레이스 트리밍
[설명] 시폰 소재의 플레어 스커트와 레이스 블라우스로 완성한 페미닌 로맨틱 스타일입니다. 화이트와 핑크의 배색이 부드럽고 여성스러운 분위기를 연출합니다."""


async def get_image_base64(client, url: str):
    if not url:
        return None, None
        
    if url.startswith('http://') or url.startswith('https://'):
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = await client.get(url, timeout=5.0, headers=headers)
            resp.raise_for_status()
            content_type = resp.headers.get('Content-Type', 'image/jpeg')
            return content_type, base64.b64encode(resp.content).decode('utf-8')
        except Exception as e:
            tqdm.write(f"⚠️ 원격 이미지 다운로드 실패 [{url}]: {e}")
            return None, None
    else:
        try:
            relative_path = url.lstrip('/') 
            file_path = BASE_DIR / relative_path
            
            if not file_path.exists():
                tqdm.write(f"⚠️ 로컬 파일 없음: {file_path}")
                return None, None
                
            content_type, _ = mimetypes.guess_type(str(file_path))
            if not content_type:
                content_type = 'image/jpeg'
                
            with open(file_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                return content_type, encoded_string
                
        except Exception as e:
            tqdm.write(f"⚠️ 로컬 이미지 읽기 실패 [{url}]: {e}")
            return None, None

async def process_post(ant_client, http_client, post, semaphore, retries=3):
    async with semaphore:
        media_type, base64_data = await get_image_base64(http_client, post['image_url'])
        if not base64_data: 
            return False

        # 1. 파일 진짜 포맷 확인 + 8000px 초과 시 리사이즈
        try:
            from PIL import Image
            import io
            raw_data = base64.b64decode(base64_data)
            fmt = imghdr.what(None, h=raw_data)
            if fmt:
                media_type = f"image/{fmt}"
            img = Image.open(io.BytesIO(raw_data))
            w, h = img.size
            if max(w, h) > 7000:
                scale = 7000 / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG")
                base64_data = base64.b64encode(buf.getvalue()).decode()
                media_type = "image/jpeg"
        except:
            pass

        for attempt in range(retries):
            try:
                response = await ant_client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=600,
                    messages=[{"role": "user", "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64_data}},
                        {"type": "text", "text": CAPTION_PROMPT}
                    ]}]
                )
                
                caption = ""
                if isinstance(response.content, list) and response.content:
                    first_block = response.content[0]
                    if hasattr(first_block, 'text'):
                        caption = first_block.text.strip()
                    elif isinstance(first_block, dict):
                        caption = first_block.get('text', '').strip()
                else:
                    caption = getattr(response.content, 'text', str(response.content)).strip()

                if caption.upper().startswith("SKIP"):
                    delete_post(post["id"])
                    tqdm.write(f"🚫 ID #{post['id']} 여성 패션 아님 → 삭제")
                    return False
                    
                save_caption(post["id"], caption)
                return True
                
            except Exception as e:
                err = str(e)
                # 529 Overloaded 에러 나면 대기 후 자동 재시도
                if "Overloaded" in err and attempt < retries - 1:
                    wait_time = (attempt + 1) * 5
                    tqdm.write(f"⚠️ ID #{post['id']} 서버 과부하, {wait_time}초 후 재시도...")
                    await asyncio.sleep(wait_time)
                    continue

                tqdm.write(f"❌ ID #{post['id']} 실패: {e}")
                return False

async def run_captioning(batch_size: int = 200, per_account: int = 50, since: str = None, empty_only: bool = False, recaption_all: bool = False):
    ant_client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    if recaption_all:
        posts = get_all_posts_for_recaption(limit=batch_size, per_account=per_account)
    else:
        posts = get_uncaptioned_posts(limit=batch_size, per_account=per_account, since=since, empty_only=empty_only)
    
    if not posts:
        print("✨ 분석할 이미지가 없습니다.")
        return

    semaphore = asyncio.Semaphore(5)
    
    async with httpx.AsyncClient() as http_client:
        tasks = [process_post(ant_client, http_client, post, semaphore) for post in posts]
        
        print(f"\n🚀 비동기 파이프라인 가동 (타겟: {len(posts)}장)\n")
        results = await tqdm.gather(*tasks)
        
    print(f"\n✅ 완료: {sum(results)}/{len(posts)}개 성공!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--per-account", type=int, default=50)
    parser.add_argument("--since", type=str, default=None)
    parser.add_argument("--all", action="store_true", help="caption_ai 있는 것도 포함해 전체 재캡셔닝")
    args = parser.parse_args()
    asyncio.run(run_captioning(batch_size=args.batch_size, per_account=args.per_account, since=args.since, empty_only=not args.all, recaption_all=args.all))