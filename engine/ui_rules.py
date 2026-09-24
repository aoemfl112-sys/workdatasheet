"""화면에서 쓰는 슬롯 지정·파일 형식 검사 (Streamlit 없이 테스트 가능)."""

from __future__ import annotations

from collections import Counter

ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png"}


def is_allowed_image_name(name: str) -> bool:
    lower = name.lower()
    return any(lower.endswith(ext) for ext in ALLOWED_IMAGE_EXT)


def default_slot_choice(photo_index: int, slot_count: int) -> int | None:
    """업로드 순서대로 1, 2, 3… 을 초깃값으로 준다. 슬롯을 넘으면 미지정."""
    if photo_index < slot_count:
        return photo_index + 1
    return None


def validate_slot_choices(
    choices: list[int | None],
    slot_ids: list[int],
) -> list[str]:
    """사진별 슬롯 지정 결과를 안내 문구로 돌려준다. 비어 있으면 문제 없음."""
    messages: list[str] = []
    slot_count = len(slot_ids)
    n_photos = len(choices)

    if n_photos > slot_count:
        messages.append(
            f"사진 {n_photos}장 / 슬롯 {slot_count}개입니다. "
            "슬롯에 넣지 않은 사진은 배치되지 않습니다."
        )
    elif 0 < n_photos < slot_count:
        messages.append(
            f"사진 {n_photos}장 / 슬롯 {slot_count}개입니다. "
            "비어 있는 슬롯은 배경만 유지됩니다."
        )

    unnamed = [i + 1 for i, slot in enumerate(choices) if slot is None]
    if unnamed:
        if len(unnamed) == 1:
            messages.append(f"{unnamed[0]}번째 사진의 슬롯이 지정되지 않았습니다.")
        else:
            joined = ", ".join(str(i) for i in unnamed)
            messages.append(f"슬롯이 지정되지 않은 사진이 있습니다: {joined}번째")

    assigned = [slot for slot in choices if slot is not None]
    counts = Counter(assigned)
    for slot_id, count in sorted(counts.items()):
        if count > 1:
            messages.append(
                f"슬롯 {slot_id}번에 사진이 {count}장 지정되었습니다. "
                "한 슬롯에는 사진 한 장만 넣을 수 있습니다."
            )
        if slot_id not in slot_ids:
            messages.append(f"슬롯 {slot_id}번은 이 템플릿에 없습니다.")

    return messages


def blocking_errors(choices: list[int | None], slot_ids: list[int]) -> list[str]:
    """생성을 막아야 하는 오류. 장수 불일치·미지정은 경고만 하고 생성은 허용한다."""
    messages: list[str] = []
    assigned = [slot for slot in choices if slot is not None]
    if choices and not assigned:
        messages.append("배치할 사진이 없습니다. 슬롯을 지정하세요.")
    counts = Counter(assigned)
    for slot_id, count in sorted(counts.items()):
        if count > 1:
            messages.append(
                f"슬롯 {slot_id}번에 사진이 {count}장 지정되었습니다. "
                "한 슬롯에는 사진 한 장만 넣을 수 있습니다."
            )
        if slot_id not in slot_ids:
            messages.append(f"슬롯 {slot_id}번은 이 템플릿에 없습니다.")
    return messages
