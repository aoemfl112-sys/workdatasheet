"""템플릿 좌표 JSON 로더."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_layout(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    slots = data.get("slots") or []
    if not slots:
        raise ValueError(f"슬롯 정의가 없습니다: {path}")
    ids = [slot["id"] for slot in slots]
    if len(ids) != len(set(ids)):
        raise ValueError("슬롯 id 가 중복됩니다.")
    return data


def slot_by_id(layout: dict[str, Any], slot_id: int) -> dict[str, Any]:
    for slot in layout["slots"]:
        if int(slot["id"]) == int(slot_id):
            return slot
    raise KeyError(f"슬롯 id {slot_id} 를 찾을 수 없습니다.")


def list_layouts(config_dir: str | Path) -> list[dict[str, Any]]:
    """config/layout_type_*.json 을 읽어 내장 템플릿 목록을 만든다."""
    folder = Path(config_dir)
    items: list[dict[str, Any]] = []
    for path in sorted(folder.glob("layout_type_*.json")):
        data = load_layout(path)
        items.append(
            {
                "id": data.get("template_name") or path.stem,
                "display_name": data.get("display_name") or path.stem,
                "path": path,
                "template_file": data.get("template_file") or "",
                "slot_count": len(data["slots"]),
                "layout": data,
            }
        )
    if not items:
        raise FileNotFoundError(f"레이아웃 JSON이 없습니다: {folder}")
    items.sort(
        key=lambda item: (
            int((item["layout"] or {}).get("list_order") or 99),
            int(item["slot_count"]),
            str(item["id"]),
        )
    )
    return items
