import psycopg2
import psycopg2.extras
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from db.database import _get_connection, save_embedding

MODEL_NAME = "openai/clip-vit-base-patch32"
DATA_DIR = Path(__file__).parent.parent / "data" / "images"

_model = None
_processor = None


def get_model():
    global _model, _processor
    if _model is None:
        from transformers import CLIPModel, CLIPProcessor
        print(f"[Embedder] CLIP 모델 로딩: {MODEL_NAME}")
        _model = CLIPModel.from_pretrained(MODEL_NAME)
        _processor = CLIPProcessor.from_pretrained(MODEL_NAME)
        _model.eval()
    return _model, _processor


def embed_image(image_url: str) -> list[float] | None:
    """로컬 이미지 → CLIP 이미지 임베딩"""
    try:
        from PIL import Image
        import torch
        model, processor = get_model()

        if image_url.startswith("/images/"):
            rel = image_url[len("/images/"):]
            path = DATA_DIR / rel
        else:
            return None

        if not path.exists():
            return None

        img = Image.open(path).convert("RGB")
        inputs = processor(images=img, return_tensors="pt")
        with torch.no_grad():
            emb = model.get_image_features(**inputs)
            if not isinstance(emb, torch.Tensor):
                emb = emb.image_embeds if hasattr(emb, 'image_embeds') else emb.pooler_output
            emb = torch.nn.functional.normalize(emb, dim=-1)
        return emb[0].tolist()
    except Exception as e:
        print(f"[Embedder] 이미지 임베딩 실패 {image_url}: {e}")
        return None


def embed_text(text: str) -> list[float] | None:
    """텍스트 → CLIP 텍스트 임베딩"""
    try:
        import torch
        model, processor = get_model()
        inputs = processor(text=[text[:77]], return_tensors="pt", truncation=True)
        with torch.no_grad():
            emb = model.get_text_features(**inputs)
            if not isinstance(emb, torch.Tensor):
                emb = emb.text_embeds if hasattr(emb, 'text_embeds') else emb.pooler_output
            emb = torch.nn.functional.normalize(emb, dim=-1)
        return emb[0].tolist()
    except Exception as e:
        print(f"[Embedder] 텍스트 임베딩 실패: {e}")
        return None


def get_unembedded_posts(limit: int = 10000, since: str = None) -> list[dict]:
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if since:
                cur.execute(
                    """SELECT id, image_url, caption_ai FROM fashion_posts
                       WHERE caption_ai IS NOT NULL AND embedding IS NULL
                         AND collected_at >= %s LIMIT %s""",
                    (since, limit),
                )
            else:
                cur.execute(
                    """SELECT id, image_url, caption_ai FROM fashion_posts
                       WHERE caption_ai IS NOT NULL AND embedding IS NULL
                       LIMIT %s""",
                    (limit,),
                )
            return [dict(row) for row in cur.fetchall()]


def run_embedding(batch_size: int = 10000, since: str = None) -> int:
    posts = get_unembedded_posts(limit=batch_size, since=since)

    if not posts:
        print("[Embedder] 임베딩할 데이터 없음")
        return 0

    success = 0
    for post in posts:
        emb = embed_image(post["image_url"])
        if emb is None:
            emb = embed_text(post["caption_ai"] or "")
        if emb is None:
            continue
        try:
            save_embedding(post["id"], emb)
            success += 1
        except Exception as e:
            print(f"[Embedder] #{post['id']} 실패: {e}")

    print(f"[Embedder] 완료: {success}/{len(posts)}개")

    # 메모리 해제
    global _model, _processor
    _model = None
    _processor = None
    import gc
    gc.collect()

    return success


if __name__ == "__main__":
    run_embedding()
