from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from db.database import get_posts
from pipeline.filter_agent import filter_posts
from pipeline.translate_agent import translate_posts
from pipeline.classify_agent import classify_posts


def run_pipeline(game: str = None):
    print(f"[Pipeline] 시작 - game={game}")

    posts, total = get_posts(game=game, limit=200)
    print(f"[Pipeline] DB에서 {total}개 게시글 로드")

    filtered = filter_posts(posts)
    translated = translate_posts(filtered)
    classified = classify_posts(translated)

    print(f"[Pipeline] 완료: {len(classified)}개 처리")
    return classified


if __name__ == "__main__":
    result = run_pipeline()
    print(f"파이프라인 완료: {len(result)}개 게시글 처리")
