import os
import base64
import anthropic
from fastapi import APIRouter, Query, UploadFile, File

from db.database import search_fashion_posts, get_fashion_accounts

router = APIRouter(prefix="/search", tags=["search"])


def get_query_embedding(text: str) -> list[float]:
    """한국어 → 영어 번역 후 CLIP 텍스트 임베딩"""
    from pipeline.embedder import embed_text
    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        res = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": f"Translate this Korean fashion query to English (concise, keywords only): {text}"}]
        )
        english = res.content[0].text.strip()
    except Exception:
        english = text
    return embed_text(english)


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


@router.post("/image")
async def search_by_image(file: UploadFile = File(...)):
    content = await file.read()
    media_type = file.content_type or "image/jpeg"
    b64 = base64.b64encode(content).decode("utf-8")

    # Claude로 캡션 생성 (화면 표시용)
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    res = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
            {"type": "text", "text": "이 패션 이미지를 분석하여 실루엣, 소재, 컬러, 스타일, 아이템을 포함해 한국어로 간결하게 설명해줘. 3문장 이내. 마크다운 기호나 특수문자 없이 일반 텍스트로만 작성해줘."},
        ]}]
    )
    caption = res.content[0].text.strip()

    # CLIP 이미지 임베딩으로 검색
    try:
        from PIL import Image
        import io
        import torch
        from pipeline.embedder import get_model
        model, processor = get_model()
        img = Image.open(io.BytesIO(content)).convert("RGB")
        inputs = processor(images=img, return_tensors="pt")
        with torch.no_grad():
            emb = model.get_image_features(**inputs)
            emb = emb / emb.norm(dim=-1, keepdim=True)
        query_embedding = emb[0].tolist()
    except Exception:
        query_embedding = get_query_embedding(caption)

    results = search_fashion_posts(query_embedding, days=0, limit=50)

    return {
        "caption": caption,
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
    query_embedding = get_query_embedding(q)  # 원본 쿼리로 임베딩 (확장 텍스트는 키워드 검색에만 사용)

    sources_list = [s.strip() for s in sources.split(",")] if sources else None
    accounts_list = [a.strip() for a in accounts.split(",")] if accounts else None

    results = search_fashion_posts(
        query_embedding, days=days, limit=limit,
        sources=sources_list, accounts=accounts_list,
        keywords=keywords,
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
