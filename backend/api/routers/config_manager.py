import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/config", tags=["config"])

INSTAGRAM_PATH = Path(__file__).parent.parent.parent.parent / "config" / "instagram_accounts.json"
BRAND_PATH = Path(__file__).parent.parent.parent.parent / "config" / "brand_urls.json"


def read_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Instagram 계정 ──────────────────────────────────────────

@router.get("/instagram")
def get_instagram():
    return read_json(INSTAGRAM_PATH)


class AccountBody(BaseModel):
    username: str
    type: str  # "brands" | "influencers"


@router.post("/instagram")
def add_instagram(body: AccountBody):
    data = read_json(INSTAGRAM_PATH)
    key = body.type
    if key not in ("brands", "influencers"):
        raise HTTPException(400, "type은 brands 또는 influencers")
    if body.username in data[key]:
        raise HTTPException(400, "이미 존재하는 계정")
    data[key].append(body.username)
    write_json(INSTAGRAM_PATH, data)
    return data


@router.delete("/instagram/{account_type}/{username}")
def delete_instagram(account_type: str, username: str):
    data = read_json(INSTAGRAM_PATH)
    if account_type not in ("brands", "influencers"):
        raise HTTPException(400, "type은 brands 또는 influencers")
    if username not in data[account_type]:
        raise HTTPException(404, "계정 없음")
    data[account_type].remove(username)
    write_json(INSTAGRAM_PATH, data)
    return data


# ── 브랜드 URL ──────────────────────────────────────────────

@router.get("/brands")
def get_brands():
    return read_json(BRAND_PATH)


class BrandBody(BaseModel):
    key: str
    url: str


@router.post("/brands")
def add_brand(body: BrandBody):
    data = read_json(BRAND_PATH)
    if body.key in data:
        raise HTTPException(400, "이미 존재하는 키")
    data[body.key] = body.url
    write_json(BRAND_PATH, data)
    return data


@router.delete("/brands/{key}")
def delete_brand(key: str):
    data = read_json(BRAND_PATH)
    if key not in data:
        raise HTTPException(404, "브랜드 없음")
    del data[key]
    write_json(BRAND_PATH, data)
    return data
