import psycopg2
import psycopg2.extras
from sentence_transformers import SentenceTransformer

from db.database import _get_connection, save_embedding

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_model = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"[Embedder] 모델 로딩: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def get_unembedded_posts(limit: int = 10000, since: str = None) -> list[dict]:
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if since:
                cur.execute(
                    """
                    SELECT id, caption_ai
                    FROM fashion_posts
                    WHERE caption_ai IS NOT NULL AND embedding IS NULL
                      AND collected_at >= %s
                    LIMIT %s
                    """,
                    (since, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id, caption_ai
                    FROM fashion_posts
                    WHERE caption_ai IS NOT NULL AND embedding IS NULL
                    LIMIT %s
                    """,
                    (limit,),
                )
            return [dict(row) for row in cur.fetchall()]


def run_embedding(batch_size: int = 10000, since: str = None) -> int:
    model = get_model()
    posts = get_unembedded_posts(limit=batch_size, since=since)

    if not posts:
        print("[Embedder] 임베딩할 데이터 없음")
        return 0

    texts = [p["caption_ai"] for p in posts]
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=128)

    success = 0
    for post, emb in zip(posts, embeddings):
        try:
            save_embedding(post["id"], emb.tolist())
            success += 1
        except Exception as e:
            print(f"[Embedder] #{post['id']} 실패: {e}")

    print(f"[Embedder] 완료: {success}/{len(posts)}개")
    return success


if __name__ == "__main__":
    run_embedding()
