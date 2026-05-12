import os

import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

VALID_CATEGORIES = {"핵/봇", "업데이트", "시세/거래", "여론"}
DEFAULT_CATEGORY = "여론"


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
- 핵/봇: 불법 프로그램, 자동사냥봇, 매크로, 치트툴 관련
- 업데이트: 패치, 밸런스 변경, 버그 수정, 신규 콘텐츠 관련
- 시세/거래: 게임 내 재화 시세, 거래소, 작업장 관련
- 여론: 유저 이탈, 게임 평가, 운영사 비판, 커뮤니티 감정

제목: {title}
본문: {content_preview}

카테고리 이름만 반환하세요. (핵/봇, 업데이트, 시세/거래, 여론 중 하나)"""
                }
            ],
        )

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
