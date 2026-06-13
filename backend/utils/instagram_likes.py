"""
인스타그램 게시물 좋아요 수 파싱 공용 로직
(모바일 위장 + 줄 단위 딥스캐닝 + 댓글 오인 방어 + '여러 명' None 처리)
"""
import re


def parse_likes_line(text: str) -> int | None:
    if not text:
        return None
    text = text.strip().replace(",", "")

    # [댓글 방어막] 댓글 관련 텍스트는 좋아요로 파싱하지 않고 무시
    if "댓글" in text or "답글" in text or "comment" in text:
        return None

    # "여러 명"/"others" 패턴은 좋아요 수를 알 수 없으므로 None 반환
    if "여러 명" in text or "others" in text:
        return None

    m = re.search(r"(?:좋아요|likes)\s*([\d.]+)\s*([천만kKmM]?)", text)
    if not m:
        m = re.search(r"([\d.]+)\s*([천만kKmM]?)\s*(?:명이\s*좋아합니다)", text)

    if m:
        val = float(m.group(1))
        unit = m.group(2)
        if unit in ("천", "k", "K"):
            val *= 1000
        elif unit == "만":
            val *= 10000
        elif unit in ("m", "M"):
            val *= 1000000
        return int(val)

    return None


async def fetch_likes_from_post_page(post_page) -> int | None:
    """게시물 상세 페이지(post_page)에서 좋아요 수를 줄 단위로 정밀 추출."""
    try:
        article = post_page.locator("article").first
        if not await article.is_visible(timeout=3000):
            return None

        article_text = await article.inner_text(timeout=2000)
        lines = [line.strip() for line in article_text.splitlines() if line.strip()]

        for idx, line in enumerate(lines):
            if line in ("팔로우", "Follow", "팔로잉", "Following"):
                lookahead_block = lines[idx + 1: idx + 8]

                # 1단계: 블록 전체를 스캔해서 "여러 명"이 있는지 먼저 검사
                for block_line in lookahead_block:
                    if "여러 명" in block_line or "others" in block_line:
                        return None

                # 2단계: "여러 명"이 없을 때만 숫자를 찾음
                for block_line in lookahead_block:
                    target = block_line.replace(",", "")
                    if "댓글" in target or "답글" in target:
                        continue

                    m_unit = re.fullmatch(r"([\d.]+)\s*([천만kKmM])", target)
                    if m_unit:
                        val = float(m_unit.group(1))
                        unit = m_unit.group(2)
                        if unit in ("천", "k", "K"):
                            val *= 1000
                        elif unit == "만":
                            val *= 10000
                        elif unit in ("m", "M"):
                            val *= 1000000
                        return int(val)

                    m_num = re.fullmatch(r"(\d+)", target)
                    if m_num:
                        return int(m_num.group(1))

        # 스캐닝 실패 시 폴백
        for line in lines:
            res = parse_likes_line(line)
            if res is not None:
                return res

    except Exception:
        pass

    return None
