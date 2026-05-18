import asyncio
from fastapi import APIRouter, BackgroundTasks

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

_status: dict = {"state": "idle", "message": ""}


def _set(state: str, message: str):
    _status["state"] = state
    _status["message"] = message


@router.get("/status")
def get_status():
    return _status


@router.post("/caption")
def run_caption(background_tasks: BackgroundTasks, batch_size: int = 50):
    if _status["state"] == "running":
        return {"message": "파이프라인이 이미 실행 중입니다."}

    def _run():
        from pipeline.fashion_captioner import run_captioning
        _set("running", "1차 캡셔닝 중...")
        try:
            asyncio.run(run_captioning(batch_size=batch_size))
            _set("idle", f"1차 캡셔닝 완료 (batch_size={batch_size})")
        except Exception as e:
            _set("error", str(e))

    background_tasks.add_task(_run)
    return {"message": f"1차 캡셔닝 시작 (batch_size={batch_size})"}


@router.post("/meta")
def run_meta(background_tasks: BackgroundTasks, batch_size: int = 100):
    if _status["state"] == "running":
        return {"message": "파이프라인이 이미 실행 중입니다."}

    def _run():
        from pipeline.meta_captioner import run_meta_captioning
        _set("running", "2차 메타 캡셔닝 중...")
        try:
            asyncio.run(run_meta_captioning(batch_size=batch_size))
            _set("idle", f"2차 메타 캡셔닝 완료 (batch_size={batch_size})")
        except Exception as e:
            _set("error", str(e))

    background_tasks.add_task(_run)
    return {"message": f"2차 메타 캡셔닝 시작 (batch_size={batch_size})"}


@router.post("/embed")
def run_embed(background_tasks: BackgroundTasks, batch_size: int = 200):
    if _status["state"] == "running":
        return {"message": "파이프라인이 이미 실행 중입니다."}

    def _run():
        from pipeline.embedder import run_embedding
        _set("running", "임베딩 생성 중...")
        try:
            count = run_embedding(batch_size=batch_size)
            _set("idle", f"임베딩 완료 ({count}개)")
        except Exception as e:
            _set("error", str(e))

    background_tasks.add_task(_run)
    return {"message": f"임베딩 시작 (batch_size={batch_size})"}
