"""
속성별 트렌드(스타일/실루엣/컬러/소재/아이템/디테일) 상위 키워드를 바탕으로
하나의 코디 예상 이미지를 생성 (Hugging Face Inference API, 무료 토큰 필요)
"""
import hashlib
import os
from pathlib import Path

import httpx

GEN_DIR = Path(__file__).parent.parent / "data" / "images" / "generated"
GEN_DIR.mkdir(parents=True, exist_ok=True)

HF_MODEL = "black-forest-labs/FLUX.1-schnell"
HF_API_URL = f"https://router.huggingface.co/hf-inference/models/{HF_MODEL}"

ATTRIBUTE_LABELS = {
    "스타일": "style",
    "실루엣": "silhouette",
    "컬러": "color",
    "소재": "fabric",
    "아이템": "item",
    "디테일": "detail",
}


def _top(attribute_trends: dict, key: str) -> str | None:
    items = attribute_trends.get(key) or []
    return items[0][0] if items else None


def _build_outfit_prompt(attribute_trends: dict) -> str:
    style = _top(attribute_trends, "스타일")
    silhouette = _top(attribute_trends, "실루엣")
    color = _top(attribute_trends, "컬러")
    fabric = _top(attribute_trends, "소재")
    item = _top(attribute_trends, "아이템")
    detail = _top(attribute_trends, "디테일")

    parts = [
        "flat lay fashion outfit photo, no person, top-down view",
        "a complete coordinated outfit including a top, a bottom (pants or skirt), shoes, and a bag, all items fully visible and not cropped",
    ]
    if item:
        parts.append(f"centerpiece item: {item}")
    if style:
        parts.append(f"overall style: {style}")
    if silhouette:
        parts.append(f"silhouette: {silhouette}")
    if color:
        parts.append(f"dominant color palette: {color}")
    if fabric:
        parts.append(f"fabric: {fabric}")
    if detail:
        parts.append(f"detail accent: {detail}")

    parts.append("neatly arranged on a clean white background, product photography style, soft natural lighting, high quality, photorealistic")
    return ", ".join(p for p in parts if p)


def build_outfit_basis(attribute_trends: dict) -> dict[str, str]:
    """이미지 생성에 사용된 속성별 1위 키워드 (근거 표시용)."""
    return {
        key: top
        for key in ATTRIBUTE_LABELS
        if (top := _top(attribute_trends, key))
    }


def build_outfit_description(attribute_trends: dict) -> str:
    """어떤 키워드 조합으로 이미지를 생성했는지 설명하는 한글 텍스트."""
    basis = build_outfit_basis(attribute_trends)
    if not basis:
        return ""
    parts = [f"{key} 1위 '{value}'" for key, value in basis.items()]
    return "캡셔닝 데이터 기준 " + ", ".join(parts) + "를 조합해 AI가 예상 코디를 생성했습니다."


def generate_outfit_image(attribute_trends: dict) -> str | None:
    """속성별 트렌드 상위 키워드로 코디 이미지를 생성해 로컬에 저장하고 /images/ URL 경로를 반환. 실패 시 None."""
    hf_token = os.environ.get("HF_API_TOKEN")
    if not hf_token:
        print("[ImageGenerator] HF_API_TOKEN이 설정되지 않아 코디 이미지 생성을 건너뜁니다.")
        return None

    prompt = _build_outfit_prompt(attribute_trends)

    filename = f"{hashlib.md5(prompt.encode()).hexdigest()}.jpg"
    filepath = GEN_DIR / filename

    if filepath.exists():
        return f"/images/generated/{filename}"

    try:
        with httpx.Client(timeout=120) as client:
            res = client.post(
                HF_API_URL,
                headers={"Authorization": f"Bearer {hf_token}"},
                json={"inputs": prompt},
            )
            res.raise_for_status()
            content_type = res.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                print(f"[ImageGenerator] 코디 이미지 생성 실패: 예상치 못한 응답 ({content_type}) - {res.text[:200]}")
                return None
            filepath.write_bytes(res.content)
        return f"/images/generated/{filename}"
    except Exception as e:
        print(f"[ImageGenerator] 코디 이미지 생성 실패: {e}")
        return None
