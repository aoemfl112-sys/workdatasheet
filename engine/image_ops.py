"""이미지 맞춤(contain)과 150dpi 압축."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

CM_PER_INCH = 2.54
DEFAULT_DPI = 150
_EXIF_ORIENTATION = 0x0112


def contain_size(
    image_width_px: int,
    image_height_px: int,
    slot_width_cm: float,
    slot_height_cm: float,
) -> tuple[float, float]:
    """슬롯 안에 비율을 유지한 채 넣을 때 실제 표시 크기(cm)."""
    if image_width_px <= 0 or image_height_px <= 0:
        return slot_width_cm, slot_height_cm
    image_aspect = image_width_px / image_height_px
    slot_aspect = slot_width_cm / slot_height_cm
    if image_aspect > slot_aspect:
        width = slot_width_cm
        height = slot_width_cm / image_aspect
    else:
        height = slot_height_cm
        width = slot_height_cm * image_aspect
    return width, height


def centered_origin(
    slot_x_cm: float,
    slot_y_cm: float,
    slot_width_cm: float,
    slot_height_cm: float,
    dest_width_cm: float,
    dest_height_cm: float,
) -> tuple[float, float]:
    left = slot_x_cm + (slot_width_cm - dest_width_cm) / 2
    top = slot_y_cm + (slot_height_cm - dest_height_cm) / 2
    return left, top


def dpi_pixel_size(width_cm: float, height_cm: float, dpi: int = DEFAULT_DPI) -> tuple[int, int]:
    width_px = max(1, round((width_cm / CM_PER_INCH) * dpi))
    height_px = max(1, round((height_cm / CM_PER_INCH) * dpi))
    return width_px, height_px


def apply_exif_orientation(image: Image.Image) -> Image.Image:
    """카메라/폰이 넣은 회전 정보를 픽셀에 반영해, 파일 탐색기에서 보이는 정방향과 같게 한다."""
    transposed = ImageOps.exif_transpose(image)
    return transposed if transposed is not None else image


def _exif_orientation(image: Image.Image) -> int:
    try:
        value = image.getexif().get(_EXIF_ORIENTATION, 1)
        return int(value or 1)
    except Exception:
        return 1


def load_upright_image(source: str | Path | bytes | BytesIO) -> Image.Image:
    if isinstance(source, (bytes, bytearray)):
        opener: str | Path | BytesIO = BytesIO(source)
    else:
        opener = source
    with Image.open(opener) as opened:
        return apply_exif_orientation(opened).copy()


def _to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image
    if image.mode in ("RGBA", "LA", "P"):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return image.convert("RGB")


def prepare_image(
    path: str | Path,
    dest_width_cm: float,
    dest_height_cm: float,
    compress: bool,
    dpi: int = DEFAULT_DPI,
) -> BytesIO:
    """PPT 삽입용 바이트 스트림을 만든다.

    정방향(EXIF 회전 반영)으로 맞춘 뒤 넣는다.
    compress=False 이고 회전이 없으면 원본 파일을 그대로 넣는다.
    """
    source = Path(path)
    with Image.open(source) as opened:
        needs_rotate = _exif_orientation(opened) not in (0, 1)
        if (not compress) and (not needs_rotate):
            stream = BytesIO(source.read_bytes())
            stream.seek(0)
            return stream
        image = _to_rgb(apply_exif_orientation(opened))
        if compress:
            target_w, target_h = dpi_pixel_size(dest_width_cm, dest_height_cm, dpi)
            if image.width > target_w or image.height > target_h:
                image = image.resize((target_w, target_h), Image.Resampling.LANCZOS)
        stream = BytesIO()
        image.save(stream, format="JPEG", quality=85, dpi=(dpi, dpi), optimize=True)
        stream.seek(0)
        return stream


def image_pixel_size(path: str | Path) -> tuple[int, int]:
    image = load_upright_image(path)
    return image.size
