import anthropic
import os

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _is_lineage_related(title: str, content: str) -> bool:
    """Claude API를 호출해 리니지 관련 게시글인지 판단. True면 관련 있음."""
    try:
        content_preview = content[:300] if content else ""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[
                {
                    "role": "user",
                    "content": f"""당신은 리니지 게임 커뮤니티 분석가입니다.
아래 게시글이 리니지 게임(리니지 클래식·리마스터·2·M·2M·W)과 관련된 내용인지 판단하세요.
리니지OS(안드로이드 운영체제), 혈통(일반적 의미) 등 게임과 무관한 내용은 제외하세요.

제목: {title}
본문: {content_preview}

관련 있으면 "yes", 없으면 "no"만 반환하세요."""
                }
            ]
        )

        result = message.content[0].text.strip().lower()
        return result == "yes"

    except Exception as e:
        print(f"[Filter] API 오류 - 해당 게시글 포함 처리: {e}")
        return True


def filter_posts(posts: list[dict]) -> list[dict]:
    """
    posts 리스트를 받아 리니지 무관 게시글을 제거한 리스트 반환.
    """
    filtered = []

    for post in posts:
        title = post.get("title") or ""
        content = post.get("content") or ""

        if not title or len(content) < 10:
            continue

        if _is_lineage_related(title, content):
            filtered.append(post)

    print(f"[Filter] 총 {len(posts)}개 중 {len(filtered)}개 통과")
    return filtered
