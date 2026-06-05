import hashlib
import httpx
from pathlib import Path
from db.database import _get_connection

IMAGES_DIR = Path(__file__).parent.parent / "data" / "images"
if not IMAGES_DIR.exists():
    IMAGES_DIR = Path(__file__).parent / "backend" / "data" / "images"

with _get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT image_url, account_name FROM fashion_posts WHERE source='instagram'")
        rows = cur.fetchall()

fixed = 0
expired = 0
for url, account in rows:
    md5 = hashlib.md5(url.encode()).hexdigest()
    fpath = IMAGES_DIR / account / f"{md5}.jpg"
    if fpath.exists() and fpath.stat().st_size < 10000:
        try:
            r = httpx.get(url, timeout=15, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            if len(r.content) > 10000:
                fpath.write_bytes(r.content)
                fixed += 1
                print(f"완료: {account}/{md5}.jpg ({len(r.content)}b)")
            else:
                expired += 1
                print(f"만료: {url[:80]}")
        except Exception as e:
            print(f"실패: {e}")

print(f"\n재다운로드 완료: {fixed}개 / 만료(재시도불가): {expired}개")
