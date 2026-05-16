import asyncio
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

from crawlers.instagram_collector import run_instagram_collector
from crawlers.brand_scraper import run_brand_scraper
from pipeline.fashion_captioner import run_captioning
from pipeline.embedder import run_embedding
from pipeline.report_generator import run_report_generator


def run_fashion_pipeline(days: int = 60, generate_report: bool = True):
    start = time.time()
    print("=" * 50)
    print("[Pipeline] 패션 파이프라인 시작")
    print("=" * 50)

    # 1. 수집
    print("\n[Step 1] 인스타그램 수집")
    instagram_count = run_instagram_collector(days=days)

    print("\n[Step 2] 브랜드 룩북 수집")
    brand_count = asyncio.run(run_brand_scraper())

    print(f"\n수집 완료: 인스타 {instagram_count}개 + 브랜드 {brand_count}개")

    # 2. 캡셔닝
    print("\n[Step 3] Claude Vision 캡셔닝")
    captioned = asyncio.run(run_captioning(batch_size=100))

    # 3. 임베딩
    print("\n[Step 4] 임베딩 생성")
    embedded = run_embedding(batch_size=200)

    # 4. 리포트 생성
    if generate_report:
        print("\n[Step 5] 트렌드 리포트 생성")
        report_id = run_report_generator(days=14)
        print(f"리포트 ID: {report_id}")

    elapsed = time.time() - start
    print("\n" + "=" * 50)
    print(f"[Pipeline] 완료 | 소요시간: {elapsed:.1f}초")
    print("=" * 50)


if __name__ == "__main__":
    run_fashion_pipeline(days=60)
