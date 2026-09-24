"""미리보기에서 슬롯을 끌어 옮기고 모서리로 크기를 조절한다."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

from streamlit.components.v1 import declare_component

from engine.image_ops import load_upright_image
from engine.slot_edit import MIN_SIZE_CM, photo_area
from engine.text_fields import fields_from_layout

_FRONTEND = Path(__file__).resolve().parent / "slot_canvas_frontend"
_component = None


def _canvas_component():
    global _component
    if _component is None:
        _component = declare_component("slot_canvas", path=str(_FRONTEND))
    return _component


def photo_data_url(blob: bytes, max_px: int = 320) -> str:
    image = load_upright_image(blob).convert("RGB")
    image.thumbnail((max_px, max_px))
    stream = BytesIO()
    image.save(stream, format="JPEG", quality=70)
    encoded = base64.b64encode(stream.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def build_canvas_payload(
    layout: dict,
    slots: list[dict],
    photos_by_slot: dict[int, bytes],
    labels: dict[int, str] | None = None,
    text_values: dict[str, str] | None = None,
    selected_id: int | None = None,
) -> dict:
    area = photo_area(layout)
    slot_items = []
    for slot in slots:
        slot_id = int(slot["id"])
        blob = photos_by_slot.get(slot_id)
        caption = f"슬롯 {slot_id}"
        label = (labels or {}).get(slot_id)
        if label is None:
            label = (labels or {}).get(str(slot_id), "")
        if isinstance(label, str) and label.strip():
            caption = f"{caption} · {label.strip()}"
        item = {
            "id": slot_id,
            "x_cm": float(slot["x_cm"]),
            "y_cm": float(slot["y_cm"]),
            "width_cm": float(slot["width_cm"]),
            "height_cm": float(slot["height_cm"]),
            "caption": caption,
            "empty": blob is None,
        }
        if blob:
            item["photo"] = photo_data_url(blob)
        slot_items.append(item)

    right_lines = []
    values = text_values or {}
    for field in fields_from_layout(layout):
        snippet = " ".join(str(values.get(field["id"]) or "").split())
        if not snippet:
            right_lines.append(f"{field['label']}: (비움)")
        else:
            right_lines.append(f"{field['label']}: {snippet[:42]}")

    return {
        "slide_width_cm": float(layout["slide_width_cm"]),
        "slide_height_cm": float(layout["slide_height_cm"]),
        "photo_area": area,
        "min_size_cm": MIN_SIZE_CM,
        "selected_id": int(selected_id) if selected_id is not None else (slot_items[0]["id"] if slot_items else 1),
        "slots": slot_items,
        "right_title": "우측 표 (직접 작성)",
        "right_lines": right_lines,
    }


def render_slot_canvas(
    payload: dict,
    *,
    key: str,
):
    return _canvas_component()(payload=payload, default=None, key=key)
