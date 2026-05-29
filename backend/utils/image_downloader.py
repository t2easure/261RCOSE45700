import hashlib
from pathlib import Path

import httpx

DATA_DIR = Path(__file__).parent.parent.parent / "backend" / "data" / "images"


def download_image(image_url: str, account_name: str) -> str | None:
    """이미지 URL을 로컬에 저장. 저장된 경로 반환, 실패 시 None."""
    save_dir = DATA_DIR / account_name
    save_dir.mkdir(parents=True, exist_ok=True)

    ext = image_url.split("?")[0].split(".")[-1]
    if ext.lower() not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"
    filename = hashlib.md5(image_url.encode()).hexdigest() + f".{ext}"
    filepath = save_dir / filename

    if filepath.exists():
        return str(filepath)

    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            res = client.get(image_url, headers={"User-Agent": "Mozilla/5.0"})
            res.raise_for_status()
            filepath.write_bytes(res.content)
        return str(filepath)
    except Exception as e:
        print(f"[이미지 다운로드 실패] {image_url}: {e}")
        return None


def download_images(posts: list[dict]) -> None:
    """posts 리스트의 image_url을 account_name별 폴더에 저장하고 image_url을 로컬 경로로 교체."""
    for post in posts:
        url = post.get("image_url")
        account = post.get("account_name", "unknown")
        if url:
            path = download_image(url, account)
            if path:
                # DATA_DIR 기준 상대 경로를 /images/ URL로 변환
                rel = Path(path).relative_to(DATA_DIR)
                post["image_url"] = f"/images/{rel.as_posix()}"
