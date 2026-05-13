from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

import json
import time
from datetime import datetime, timezone, timedelta

from db.database import get_posts
from pipeline.filter_agent import filter_posts
from pipeline.translate_agent import translate_posts
from pipeline.classify_agent import classify_posts

RESULTS_DIR = Path(__file__).parent.parent / "data" / "results"


def save_results(data: list[dict]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = RESULTS_DIR / f"pipeline_{timestamp}.json"

    serializable = []
    for post in data:
        row = {}
        for k, v in post.items():
            row[k] = str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
        serializable.append(row)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)

    print(f"[Pipeline] 결과 저장: {output_path}")
    return output_path


def run_pipeline(game: str = None, hours: int = None):
    print(f"[Pipeline] 시작 - game={game}, hours={hours}")

    start = time.time()

    since = None
    if hours:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    posts, total = get_posts(game=game, since=since, limit=500)
    print(f"[Pipeline] DB에서 {total}개 게시글 로드")

    filtered = filter_posts(posts)
    translated = translate_posts(filtered)
    classified = classify_posts(translated)

    save_results(classified)
    elapsed = time.time() - start
    print(f"[Pipeline] 완료: {len(classified)}개 처리 | 소요시간: {elapsed:.1f}초")
    return classified


if __name__ == "__main__":
    result = run_pipeline(hours=24)
    print(f"파이프라인 완료: {len(result)}개 게시글 처리")
