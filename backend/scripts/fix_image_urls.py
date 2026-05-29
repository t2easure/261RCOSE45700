"""기존 CDN image_url을 로컬 /images/ URL로 업데이트 (없으면 재다운로드 시도)"""
import hashlib
import httpx
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import _get_connection

DATA_DIR = Path(__file__).parent.parent / "data" / "images"


def get_local_path(image_url: str, account_name: str) -> Path:
    ext = image_url.split("?")[0].split(".")[-1]
    if ext.lower() not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"
    filename = hashlib.md5(image_url.encode()).hexdigest() + f".{ext}"
    return DATA_DIR / account_name / filename


def try_download(image_url: str, filepath: Path) -> bool:
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            res = client.get(image_url, headers={"User-Agent": "Mozilla/5.0"})
            if res.status_code == 200:
                filepath.write_bytes(res.content)
                return True
    except Exception:
        pass
    return False


def run():
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, image_url, account_name FROM fashion_posts WHERE image_url NOT LIKE '/images/%'")
            rows = cur.fetchall()

        print(f"CDN URL 포스트 {len(rows)}개 처리 중...")
        updated = skipped = failed = 0

        for post_id, image_url, account_name in rows:
            filepath = get_local_path(image_url, account_name)

            if not filepath.exists():
                success = try_download(image_url, filepath)
                if not success:
                    failed += 1
                    continue

            rel = filepath.relative_to(DATA_DIR)
            local_url = f"/images/{rel.as_posix()}"
            with conn.cursor() as cur:
                cur.execute("UPDATE fashion_posts SET image_url = %s WHERE id = %s", (local_url, post_id))
            updated += 1

            if updated % 50 == 0:
                conn.commit()
                print(f"  {updated}개 완료...")

        conn.commit()
        print(f"\n✅ 완료: {updated}개 업데이트, {failed}개 만료(스킵)")


if __name__ == "__main__":
    run()
