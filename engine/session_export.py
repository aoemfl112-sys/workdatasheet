"""생성 결과의 파일 이름과 세션 이력. 디스크에 사진을 남기지 않는다."""

from __future__ import annotations

import re
from datetime import datetime

DEFAULT_DOWNLOAD_NAME = "작업지도서_사진배치.pptx"
MAX_HISTORY = 5
_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_download_name(raw: str, fallback: str = DEFAULT_DOWNLOAD_NAME) -> str:
    """Windows에서 쓸 수 있는 .pptx 파일 이름을 만든다."""
    text = (raw or "").strip()
    text = text.replace("\\", " ").replace("/", " ")
    text = _INVALID_CHARS.sub(" ", text)
    text = " ".join(text.split())
    if text.lower().endswith(".pptx"):
        text = text[:-5].rstrip()
    text = text.rstrip(". ")
    if not text:
        return fallback
    if len(text) > 80:
        text = text[:80].rstrip()
    return f"{text}.pptx"


def suggested_filename(pages: list[dict]) -> str:
    """첫 페이지 시험 제목이 있으면 그걸 파일 이름으로 쓴다."""
    for page in pages or []:
        title = str((page.get("texts") or {}).get("test_title") or "").strip()
        if title:
            return safe_download_name(title)
    return DEFAULT_DOWNLOAD_NAME


def make_history_item(
    data: bytes,
    filename: str,
    slide_count: int,
    photo_count: int,
    created_at: datetime | None = None,
) -> dict:
    when = created_at or datetime.now()
    return {
        "id": when.strftime("%Y%m%d%H%M%S%f"),
        "filename": safe_download_name(filename),
        "bytes": data,
        "slide_count": int(slide_count),
        "photo_count": int(photo_count),
        "created_at": when.strftime("%Y-%m-%d %H:%M:%S"),
    }


def push_history(items: list[dict] | None, item: dict, limit: int = MAX_HISTORY) -> list[dict]:
    """최신 항목을 앞에 두고, 개수를 제한한다. 디스크에는 쓰지 않는다."""
    existing = list(items or [])
    new_id = item.get("id")
    kept = [old for old in existing if old.get("id") != new_id]
    return [item, *kept][: max(1, limit)]
