import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from db.database import _get_connection


def count_empty():
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM fashion_posts WHERE caption_ai IS NULL OR caption_ai = ''")
    return cur.fetchone()[0]

def count_no_meta():
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM fashion_posts WHERE caption_ai IS NOT NULL AND caption_ai != '' AND caption_meta IS NULL")
    return cur.fetchone()[0]

def count_no_embed():
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM fashion_posts WHERE caption_ai IS NOT NULL AND caption_ai != '' AND embedding IS NULL")
    return cur.fetchone()[0]


async def step1_caption():
    from pipeline.fashion_captioner import run_captioning
    while True:
        remaining = count_empty()
        if remaining == 0:
            print("✅ 1차 캡셔닝 완료 (대상 없음)")
            break
        print(f"\n🖼  1차 캡셔닝 시작 — 대상 {remaining}개")
        await run_captioning(batch_size=remaining, per_account=remaining)
        after = count_empty()
        if after == 0:
            print("✅ 1차 캡셔닝 완료")
            break
        print(f"⏳ 아직 {after}개 남음, 이어서 실행...")


async def step2_meta():
    from pipeline.meta_captioner import run_meta_captioning
    remaining = count_no_meta()
    if remaining == 0:
        print("✅ 2차 메타 캡셔닝 완료 (대상 없음)")
        return
    print(f"\n📝 2차 메타 캡셔닝 시작 — 대상 {remaining}개")
    await run_meta_captioning(batch_size=remaining + 10)
    print("✅ 2차 메타 캡셔닝 완료")


def step3_embed():
    from pipeline.embedder import run_embedding
    remaining = count_no_embed()
    if remaining == 0:
        print("✅ 임베딩 완료 (대상 없음)")
        return
    print(f"\n🔢 임베딩 시작 — 대상 {remaining}개")
    count = run_embedding(batch_size=remaining + 10)
    print(f"✅ 임베딩 완료 ({count}개)")


async def main():
    print("=" * 50)
    print("🚀 2차 캡셔닝 + 임베딩 시작")
    print("=" * 50)
    await step2_meta()
    step3_embed()
    print("\n🎉 완료!")


if __name__ == "__main__":
    asyncio.run(main())
