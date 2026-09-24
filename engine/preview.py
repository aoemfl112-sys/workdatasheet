"""지정 결과를 슬라이드 비율로 그려 미리보기를 만든다."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from engine.image_ops import contain_size, centered_origin, load_upright_image


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("malgun.ttf", "Malgun Gothic", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _open_rgb(blob: bytes) -> Image.Image:
    copied = load_upright_image(blob)
    if copied.mode in ("RGBA", "LA", "P"):
        copied = copied.convert("RGBA")
        background = Image.new("RGB", copied.size, (255, 255, 255))
        background.paste(copied, mask=copied.split()[-1])
        return background
    return copied.convert("RGB")


def render_layout_preview(
    layout: dict,
    photos_by_slot: dict[int, bytes],
    labels: dict[int, str] | None = None,
    text_values: dict[str, str] | None = None,
    width_px: int = 960,
    highlight_slot: int | None = None,
) -> bytes:
    """JSON 좌표 비율로 슬롯 박스를 그리고, 지정된 사진을 칸 안에 넣는다."""
    slide_w = float(layout["slide_width_cm"])
    slide_h = float(layout["slide_height_cm"])
    if slide_w <= 0 or slide_h <= 0:
        raise ValueError("슬라이드 크기가 올바르지 않습니다.")
    scale = width_px / slide_w
    height_px = max(1, round(slide_h * scale))
    canvas = Image.new("RGB", (width_px, height_px), (248, 250, 252))
    draw = ImageDraw.Draw(canvas)

    photo_area = layout.get("photo_area") or {}
    right_x = float(photo_area.get("x_cm", 0) + photo_area.get("width_cm", 0)) if photo_area else 23.3
    if right_x > 0:
        rx = round(right_x * scale)
        draw.rectangle((rx, 0, width_px, height_px), fill=(226, 232, 240))
        header = "우측 표 (직접 작성)"
        draw.text((rx + 8, 10), header, fill=(71, 85, 105), font=_font(14))
        y_text = 32
        note_font = _font(12)
        for field in layout.get("text_fields") or []:
            label = str(field.get("label") or "").strip()
            value = (text_values or {}).get(str(field.get("id") or ""), "")
            snippet = " ".join((value or "").split())
            if not snippet:
                line = f"{label}: (비움)"
            else:
                line = f"{label}: {snippet[:42]}"
            draw.text((rx + 8, y_text), line, fill=(51, 65, 85), font=note_font)
            y_text += 18
            if y_text > height_px - 24:
                break

    title_font = _font(15)
    small_font = _font(13)
    for slot in layout.get("slots") or []:
        slot_id = int(slot["id"])
        x = round(float(slot["x_cm"]) * scale)
        y = round(float(slot["y_cm"]) * scale)
        w = max(8, round(float(slot["width_cm"]) * scale))
        h = max(8, round(float(slot["height_cm"]) * scale))
        selected = highlight_slot is not None and slot_id == int(highlight_slot)
        outline = (234, 88, 12) if selected else (37, 99, 235)
        fill = (255, 237, 213) if selected else (219, 234, 254)
        draw.rectangle((x, y, x + w, y + h), outline=outline, width=4 if selected else 2, fill=fill)
        blob = photos_by_slot.get(slot_id)
        if blob:
            photo = _open_rgb(blob)
            dest_w_cm, dest_h_cm = contain_size(
                photo.width, photo.height, float(slot["width_cm"]), float(slot["height_cm"])
            )
            left_cm, top_cm = centered_origin(
                float(slot["x_cm"]),
                float(slot["y_cm"]),
                float(slot["width_cm"]),
                float(slot["height_cm"]),
                dest_w_cm,
                dest_h_cm,
            )
            dest_w = max(1, round(dest_w_cm * scale))
            dest_h = max(1, round(dest_h_cm * scale))
            fitted = photo.resize((dest_w, dest_h), Image.Resampling.LANCZOS)
            canvas.paste(fitted, (round(left_cm * scale), round(top_cm * scale)))
        caption = f"슬롯 {slot_id}"
        label = (labels or {}).get(slot_id, "").strip()
        if label:
            caption = f"{caption} · {label}"
        draw.rectangle((x, y, x + w, y + 22), fill=outline)
        draw.text((x + 6, y + 3), caption, fill=(255, 255, 255), font=title_font)
        if blob is None:
            draw.text((x + 8, y + h // 2 - 8), "비어 있음", fill=(100, 116, 139), font=small_font)

    stream = BytesIO()
    canvas.save(stream, format="PNG")
    return stream.getvalue()
