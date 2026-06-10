"""
속성별 트렌드(스타일/실루엣/컬러/소재/아이템/디테일) 상위 키워드를 바탕으로
하나의 코디 예상 이미지를 생성 (Pollinations.ai, 무료/API 키 불필요)
"""
import hashlib
import urllib.parse
from pathlib import Path

import httpx

GEN_DIR = Path(__file__).parent.parent / "data" / "images" / "generated"
GEN_DIR.mkdir(parents=True, exist_ok=True)

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"

ATTRIBUTE_LABELS = {
    "스타일": "style",
    "실루엣": "silhouette",
    "컬러": "color",
    "소재": "fabric",
    "아이템": "item",
    "디테일": "detail",
}


def _build_outfit_prompt(attribute_trends: dict) -> str:
    parts = ["professional fashion editorial photo, women's outfit"]

    for key, label in ATTRIBUTE_LABELS.items():
        items = attribute_trends.get(key) or []
        if items:
            top_keyword = items[0][0]
            parts.append(f"{label}: {top_keyword}")

    parts.append("clean studio background, full body, high quality, photorealistic")
    return ", ".join(p for p in parts if p)


def generate_outfit_image(attribute_trends: dict, width: int = 768, height: int = 1024) -> str | None:
    """속성별 트렌드 상위 키워드로 코디 이미지를 생성해 로컬에 저장하고 /images/ URL 경로를 반환. 실패 시 None."""
    prompt = _build_outfit_prompt(attribute_trends)

    seed = int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16) % 1_000_000
    filename = f"{hashlib.md5(prompt.encode()).hexdigest()}.jpg"
    filepath = GEN_DIR / filename

    if filepath.exists():
        return f"/images/generated/{filename}"

    encoded = urllib.parse.quote(prompt)
    url = POLLINATIONS_URL.format(prompt=encoded)
    params = {"width": width, "height": height, "nologo": "true", "seed": seed, "model": "flux"}

    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            res = client.get(url, params=params)
            res.raise_for_status()
            filepath.write_bytes(res.content)
        return f"/images/generated/{filename}"
    except Exception as e:
        print(f"[ImageGenerator] 코디 이미지 생성 실패: {e}")
        return None
