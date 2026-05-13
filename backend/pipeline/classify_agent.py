import os
import time

import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

VALID_CATEGORIES = {"핵/봇", "업데이트", "시세/거래", "운영 비판", "커뮤니티"}
DEFAULT_CATEGORY = "커뮤니티"


def _classify(title: str, content: str) -> str:
    """Claude API로 게시글 카테고리 분류. 실패 시 기본값 '여론' 반환."""
    try:
        content_preview = content[:300] if content else ""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=20,
            messages=[
                {
                    "role": "user",
                    "content": f"""당신은 리니지 게임 커뮤니티 분석 전문가입니다.
아래 게시글을 읽고 4개 카테고리 중 하나로 분류하세요.

카테고리:
- 핵/봇: 불법 프로그램·자동사냥봇·매크로·치트툴 사용·유포·제보
- 업데이트: 운영사가 배포한 패치·밸런스 변경·버그 수정·신규 콘텐츠에 대한 반응. "이번 패치", "업데이트 이후", "롤백" 등 운영사 행동 언급이 있어야 함
- 시세/거래: 게임 내 재화(뎅·아덴 등) 시세 변동·거래소·작업장·아이템 거래 이슈. 단순 아이템 질문 제외
- 운영 비판: 운영사(NC) 정책·행태·서비스 비판, 유저 이탈·게임 존폐 우려, 고객지원 불만, 과금 정책 비판
- 커뮤니티: 위 4개에 해당하지 않는 모든 것. 게임플레이 질문·공략·잡담·자랑·일반 감상

판단 순서: 핵/봇 → 업데이트 → 시세/거래 → 운영 비판 → 커뮤니티 순으로 확인.

제목: {title}
본문: {content_preview}

카테고리 이름만 반환하세요. (핵/봇, 업데이트, 시세/거래, 운영 비판, 커뮤니티 중 하나)"""
                }
            ],
        )

        time.sleep(0.3)
        result = message.content[0].text.strip()

        if result not in VALID_CATEGORIES:
            print(f"[Classify] 알 수 없는 카테고리 '{result}' → 기본값 '{DEFAULT_CATEGORY}' 처리")
            return DEFAULT_CATEGORY

        return result

    except Exception as e:
        print(f"[Classify] API 오류 - 기본값 '{DEFAULT_CATEGORY}' 반환: {e}")
        return DEFAULT_CATEGORY


def classify_posts(posts: list[dict]) -> list[dict]:
    """posts 리스트를 받아 category 필드를 추가하여 반환.
    각 게시글을 핵/봇·업데이트·시세/거래·여론 중 하나로 분류.
    """
    result = []

    for post in posts:
        post = dict(post)
        title = post.get("translated_title") or post.get("title") or ""
        content = post.get("translated_content") or post.get("content") or ""

        post["category"] = _classify(title, content)
        result.append(post)

    print(f"[Classify] {len(result)}개 게시글 분류 완료")
    return result
