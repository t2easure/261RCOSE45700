import os
import base64
import anthropic
from fastapi import APIRouter, Query, UploadFile, File, Form
from typing import List

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


def _apply_text_override(caption: str, text_query: str) -> str:
    """캡션에 텍스트 지시를 반영해 속성을 치환/병합한 새 캡션 생성.
    예: 캡션이 '레드 컬러 드레스'이고 text_query가 '블랙 컬러로 해당 옷 종류'면
    실루엣/소재/스타일은 유지하고 컬러만 블랙으로 바꾼 캡션을 반환."""
    try:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        res = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": (
                f"아래는 패션 이미지 설명이야:\n{caption}\n\n"
                f"사용자가 다음 조건을 추가로 요청했어: \"{text_query}\"\n"
                "이 조건이 기존 설명의 속성(컬러/소재/스타일 등)과 충돌하면 조건을 우선해서 "
                "해당 속성을 덮어쓰고, 나머지(실루엣/아이템 종류 등)는 그대로 유지해서 "
                "하나의 자연스러운 패션 설명 문장으로 다시 작성해줘. 설명 없이 결과 문장만 출력해."
            )}]
        )
        return res.content[0].text.strip()
    except Exception:
        return f"{caption} {text_query}"


@router.post("/image")
async def search_by_image(file: UploadFile = File(...), q: str = Form(None)):
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

    # CLIP 이미지 임베딩 + AI 캡션 임베딩(기존 방식) + 텍스트 쿼리(선택) 가중 결합
    text_query = (q or "").strip()
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
            if not isinstance(emb, torch.Tensor):
                emb = emb.image_embeds if hasattr(emb, "image_embeds") else emb.pooler_output
            emb = emb / emb.norm(dim=-1, keepdim=True)
        img_emb = emb[0]

        if text_query:
            merged_caption = _apply_text_override(caption, text_query)
            merged_emb_list = get_query_embedding(merged_caption)
            merged_emb = torch.tensor(merged_emb_list, dtype=img_emb.dtype) if merged_emb_list else None
            combined = 0.25 * img_emb + 0.75 * merged_emb if merged_emb is not None else img_emb
        else:
            # 원본 CLIP 이미지 임베딩은 포즈·배경·조명 같은 시각 잡음을 같이 담아 색상/스타일
            # 매칭이 흐려짐. AI 캡션 텍스트 임베딩만 쓰는 쪽이 의미적으로 더 정확함.
            caption_emb_list = get_query_embedding(caption)
            caption_emb = torch.tensor(caption_emb_list, dtype=img_emb.dtype) if caption_emb_list else None
            combined = caption_emb if caption_emb is not None else img_emb

        combined = combined / combined.norm()
        query_embedding = combined.tolist()
    except Exception:
        query_embedding = get_query_embedding(f"{caption} {text_query}".strip())

    results = search_fashion_posts(query_embedding, days=0, limit=50)

    return {
        "caption": caption,
        "text_query": text_query or None,
        "total": len(results),
        "results": [
            {
                "id": r["id"],
                "image_url": r["image_url"],
                "post_url": r.get("post_url"),
                "account_name": r["account_name"],
                "source": r["source"],
                "posted_at": str(r["posted_at"]) if r["posted_at"] else None,
                "caption_ai": r["caption_ai"],
                "similarity": round(float(r["similarity"]), 4),
            }
            for r in results
        ],
    }


@router.post("/images")
async def search_by_multiple_images(files: List[UploadFile] = File(...), q: str = Form(None)):
    """여러 이미지의 CLIP 임베딩 평균(+텍스트 가중 결합)으로 유사 이미지 검색."""
    from PIL import Image
    import io
    import torch
    from pipeline.embedder import get_model

    model, processor = get_model()
    embeddings = []
    file_contents: list[tuple[bytes, str]] = []

    for file in files:
        content = await file.read()
        file_contents.append((content, file.content_type or "image/jpeg"))
        try:
            img = Image.open(io.BytesIO(content)).convert("RGB")
            inputs = processor(images=img, return_tensors="pt")
            with torch.no_grad():
                emb = model.get_image_features(**inputs)
                if not isinstance(emb, torch.Tensor):
                    emb = emb.image_embeds if hasattr(emb, "image_embeds") else emb.pooler_output
                emb = emb / emb.norm(dim=-1, keepdim=True)
            embeddings.append(emb[0])
        except Exception:
            continue

    if not embeddings:
        return {"total": 0, "results": []}

    avg_emb = torch.stack(embeddings).mean(dim=0)
    avg_emb = avg_emb / avg_emb.norm()

    text_query = (q or "").strip()
    if text_query:
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        content_blocks: list[dict] = []
        for content, media_type in file_contents[:5]:
            b64 = base64.b64encode(content).decode("utf-8")
            content_blocks.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}})
        content_blocks.append({"type": "text", "text": "이 패션 이미지들을 분석하여 실루엣, 소재, 컬러, 스타일, 아이템을 포함해 한국어로 간결하게 설명해줘. 3문장 이내."})
        res = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=300, messages=[{"role": "user", "content": content_blocks}])
        caption = res.content[0].text.strip()
        merged_caption = _apply_text_override(caption, text_query)
        merged_emb_list = get_query_embedding(merged_caption)
        if merged_emb_list:
            merged_emb = torch.tensor(merged_emb_list, dtype=avg_emb.dtype)
            combined = 0.25 * avg_emb + 0.75 * merged_emb
            combined = combined / combined.norm()
            query_embedding = combined.tolist()
        else:
            query_embedding = avg_emb.tolist()
    else:
        query_embedding = avg_emb.tolist()

    results = search_fashion_posts(query_embedding, days=0, limit=50)

    return {
        "image_count": len(embeddings),
        "text_query": text_query or None,
        "total": len(results),
        "results": [
            {
                "id": r["id"],
                "image_url": r["image_url"],
                "post_url": r.get("post_url"),
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
                "post_url": r.get("post_url"),
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
