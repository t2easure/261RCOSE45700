import anthropic
import os
import json

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _translate(title: str, content: str) -> dict:
    """Claude API로 제목·본문을 한국어로 번역. 실패 시 원본 반환."""
    try:
        content_to_translate = content[:500] if content else ""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": f"""당신은 게임 커뮤니티 전문 번역가입니다.
아래 게시글 제목과 본문을 자연스러운 한국어로 번역하세요.
게임 고유 명칭(뎅, 아덴 등 게임 내 재화·지명)은 번역하지 말고 그대로 유지하세요.
반드시 아래 JSON 형식으로만 반환하세요. 다른 말은 하지 마세요.

제목: {title}
본문: {content_to_translate}

{{"translated_title": "여기에 번역된 제목", "translated_content": "여기에 번역된 본문"}}"""
                }
            ]
        )

        result_text = message.content[0].text.strip()
        result = json.loads(result_text)
        return {
            "translated_title": result.get("translated_title", title),
            "translated_content": result.get("translated_content", content)
        }

    except Exception as e:
        print(f"[Translate] API 오류 - 원본 반환: {e}")
        return {
            "translated_title": title,
            "translated_content": content
        }


def translate_posts(posts: list[dict]) -> list[dict]:
    """
    posts 리스트를 받아 translated_title, translated_content 필드를 추가하여 반환.
    인벤 게시글은 번역 없이 원본 복사.
    """
    result = []

    for post in posts:
        post = dict(post)  # 원본 수정 방지
        title = post.get("title") or ""
        content = post.get("content") or ""
        source = post.get("source") or ""

        if source == "inven":
            # 한국어 → 번역 스킵
            post["translated_title"] = title
            post["translated_content"] = content
        else:
            # 영어/중국어 → 한국어 번역
            translated = _translate(title, content)
            post["translated_title"] = translated["translated_title"]
            post["translated_content"] = translated["translated_content"]

        result.append(post)

    print(f"[Translate] {len(result)}개 게시글 처리 완료")
    return result
