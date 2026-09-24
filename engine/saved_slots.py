"""조절한 슬롯 배치를 이 PC 폴더에만 저장한다. 공유 서버에는 올리지 않는다."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def saved_dir(root: str | Path) -> Path:
    folder = Path(root) / "saved_layouts"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def safe_layout_stem(raw: str) -> str:
    text = (raw or "").strip()
    text = text.replace("\\", " ").replace("/", " ")
    text = _INVALID.sub(" ", text)
    text = " ".join(text.split())
    if text.lower().endswith(".json"):
        text = text[:-5].rstrip()
    text = text.rstrip(". ")
    if not text:
        text = datetime.now().strftime("배치_%Y%m%d_%H%M")
    return text[:60]


def list_saved(root: str | Path) -> list[dict[str, Any]]:
    folder = saved_dir(root)
    items: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        slots = data.get("slots") or []
        items.append(
            {
                "path": path,
                "name": str(data.get("name") or path.stem),
                "layout_id": str(data.get("layout_id") or ""),
                "slot_count": len(slots),
                "filename": path.name,
            }
        )
    return items


def save_slots(
    root: str | Path,
    name: str,
    layout_id: str,
    slots: list[dict[str, Any]],
) -> Path:
    if not slots:
        raise ValueError("저장할 슬롯이 없습니다.")
    stem = safe_layout_stem(name)
    path = saved_dir(root) / f"{stem}.json"
    payload = {
        "name": stem,
        "layout_id": layout_id,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "slots": slots,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_slots(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    slots = data.get("slots") or []
    if not slots:
        raise ValueError("저장 파일에 슬롯이 없습니다.")
    cleaned = []
    for item in slots:
        slot_id = int(item["id"])
        cleaned.append(
            {
                **item,
                "id": slot_id,
                "name": str(item.get("name") or f"SLOT_{slot_id}"),
                "x_cm": float(item["x_cm"]),
                "y_cm": float(item["y_cm"]),
                "width_cm": float(item["width_cm"]),
                "height_cm": float(item["height_cm"]),
            }
        )
    data["slots"] = cleaned
    return data


def delete_saved(path: str | Path) -> None:
    target = Path(path)
    if target.exists():
        target.unlink()
