import os
import anthropic
from fastapi import APIRouter, Query
from sentence_transformers import SentenceTransformer

from db.database import search_fashion_posts

router = APIRouter(prefix="/search", tags=["search"])

_model = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _model


def expand_query(q: str) -> tuple[str, list[str]]:
    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        res = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": f"다음 패션 검색어를 관련 키워드로 확장해줘. 쉼표로 구분해서 한 줄로만 반환해. 검색어: {q}"}]
        )
        expanded = res.content[0].text.strip()
        keywords = [k.strip() for k in expanded.split(",") if k.strip()]
        return expanded, keywords
    except Exception:
        return q, [q]


@router.get("")
def search(
    q: str = Query(..., description="패션 검색어 (자연어 가능)"),
    days: int = Query(60, description="검색 기간 (일)"),
    limit: int = Query(20, description="결과 수"),
):
    expanded_text, keywords = expand_query(q)
    query_embedding = get_model().encode(expanded_text).tolist()
    results = search_fashion_posts(query_embedding, days=days, limit=limit)

    return {
        "query": q,
        "expanded_keywords": keywords,
        "total": len(results),
        "results": [
            {
                "id": r["id"],
                "image_url": r["image_url"],
                "account_name": r["account_name"],
                "source": r["source"],
                "posted_at": str(r["posted_at"]) if r["posted_at"] else None,
                "caption_ai": r["caption_ai"],
                "caption_meta": r.get("caption_meta"),
                "similarity": round(float(r["similarity"]), 4),
            }
            for r in results
        ],
    }
