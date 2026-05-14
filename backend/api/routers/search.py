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


@router.get("")
def search(
    q: str = Query(..., description="패션 키워드 (예: 컴포트 클래식)"),
    days: int = Query(60, description="검색 기간 (일)"),
    limit: int = Query(20, description="결과 수"),
):
    query_embedding = get_model().encode(q).tolist()
    results = search_fashion_posts(query_embedding, days=days, limit=limit)

    return {
        "query": q,
        "total": len(results),
        "results": [
            {
                "id": r["id"],
                "image_url": r["image_url"],
                "account_name": r["account_name"],
                "source": r["source"],
                "posted_at": str(r["posted_at"]) if r["posted_at"] else None,
                "caption_ai": r["caption_ai"],
                "similarity": round(float(r["similarity"]), 4),
            }
            for r in results
        ],
    }
