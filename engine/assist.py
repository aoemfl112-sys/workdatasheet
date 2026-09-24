"""참고용 보조 정보. 압축·라벨의 최종 결정은 항상 사람이 한다.

기본은 로컬 휴리스틱만 사용한다(사진이 밖으로 나가지 않음).
Gemini는 GEMINI_API_KEY 가 있고 사용자가 동의한 경우에만 호출한다.
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import ImageFilter, ImageStat

from engine.image_ops import load_upright_image

READABILITY_WARNING = (
    "화면 캡처나 글자가 많은 사진으로 보입니다. "
    "150dpi 압축 시 텍스트가 흐려질 수 있습니다. 압축 여부는 직접 고르세요."
)


def compress_warning(image_bytes: bytes) -> str | None:
    """로컬에서만 판독성 힌트를 준다. 외부 API를 쓰지 않는다."""
    gray = load_upright_image(image_bytes).convert("L")
    gray.thumbnail((160, 120))
    hist = gray.histogram()
    total = gray.size[0] * gray.size[1]
    if total <= 0:
        return None
    ends = sum(hist[:18]) + sum(hist[-18:])
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_mean = ImageStat.Stat(edges).mean[0]
    # 양 끝 톤(검정/흰)이 많고 경계가 뚜렷하면 캡처·문자 화면일 가능성이 큼
    if ends / total >= 0.32 and edge_mean >= 12:
        return READABILITY_WARNING
    return None


def gemini_available() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def suggest_labels_with_gemini(images: list[tuple[str, bytes]]) -> dict[str, str]:
    """사진별 라벨 초안. 키가 없거나 라이브러리가 없으면 빈 dict.

    반환값은 참고용이며 자동으로 확정하지 않는다.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or not images:
        return {}
    try:
        from google import genai
    except ImportError:
        return {}

    client = genai.Client(api_key=api_key)
    drafts: dict[str, str] = {}
    for name, blob in images:
        prompt = (
            "이 사진은 산업 시험절차서의 한 칸 설명용이다. "
            "슬롯 라벨로 쓸 짧은 한글 또는 영어 문구를 8단어 이내로 하나만 답하라. "
            "설명 문장이나 따옴표는 넣지 마라."
        )
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    prompt,
                    {"inline_data": {"mime_type": _mime(name), "data": blob}},
                ],
            )
            text = (response.text or "").strip().splitlines()[0].strip(" \"'")
            if text:
                drafts[name] = text[:40]
        except Exception:
            continue
    return drafts


def _mime(name: str) -> str:
    suffix = Path(name).suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    return "image/png"
