import os
import anthropic
from fastapi import APIRouter, Query
from sentence_transformers import SentenceTransformer

from db.database import search_fashion_posts, get_fashion_accounts

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


@router.get("/accounts")
def list_accounts():
    return get_fashion_accounts()


@router.get("")
def search(
    q: str = Query(..., description="패션 검색어 (자연어 가능)"),
    days: int = Query(60, description="검색 기간 (일)"),
    limit: int = Query(50, description="결과 수"),
    sources: str = Query(None, description="소스 필터 (쉼표 구분, 예: instagram,lookbook)"),
    accounts: str = Query(None, description="계정 필터 (쉼표 구분)"),
):
    expanded_text, keywords = expand_query(q)
    query_embedding = get_model().encode(expanded_text).tolist()

    sources_list = [s.strip() for s in sources.split(",")] if sources else None
    accounts_list = [a.strip() for a in accounts.split(",")] if accounts else None

    results = search_fashion_posts(
        query_embedding, days=days, limit=limit,
        sources=sources_list, accounts=accounts_list,
    )

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
