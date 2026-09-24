"""슬롯 지정 보드. 끌어다 놓기·번호 선택이 같은 지정 결과를 쓰게 한다.

한 슬롯에는 사진 한 장만 둔다. 같은 칸에 두 장이 들어가면
나중에 넣은 장만 남기고 나머지는 미지정으로 되돌린다.
"""

from __future__ import annotations

from pathlib import Path

UNASSIGNED_HEADER = "미지정"
SLOT_HEADER_PREFIX = "슬롯 "


def slot_header(slot_id: int) -> str:
    return f"{SLOT_HEADER_PREFIX}{int(slot_id)}"


def parse_slot_header(header: str) -> int | None:
    text = (header or "").strip()
    if text == UNASSIGNED_HEADER:
        return None
    if text.startswith(SLOT_HEADER_PREFIX):
        rest = text[len(SLOT_HEADER_PREFIX) :].strip()
        if rest.isdigit():
            return int(rest)
    return None


def uniquify_name(name: str, used: set[str]) -> str:
    if name not in used:
        used.add(name)
        return name
    stem = Path(name).stem
    suffix = Path(name).suffix
    n = 2
    while True:
        candidate = f"{stem}_{n}{suffix}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        n += 1


def prune_slot_map(
    slot_by_name: dict[str, int | None],
    live_names: set[str],
    slot_ids: list[int],
) -> dict[str, int | None]:
    allowed = set(slot_ids)
    cleaned: dict[str, int | None] = {}
    for name, slot_id in slot_by_name.items():
        if name not in live_names:
            continue
        if slot_id is not None and slot_id not in allowed:
            cleaned[name] = None
        else:
            cleaned[name] = slot_id
    return cleaned


def apply_defaults(
    photo_names: list[str],
    slot_by_name: dict[str, int | None],
    slot_count: int,
) -> dict[str, int | None]:
    result = dict(slot_by_name)
    for index, name in enumerate(photo_names):
        if name not in result:
            result[name] = index + 1 if index < slot_count else None
    return result


def board_from_map(
    photo_names: list[str],
    slot_by_name: dict[str, int | None],
    slot_ids: list[int],
) -> list[dict[str, object]]:
    buckets: dict[int | None, list[str]] = {None: []}
    for slot_id in slot_ids:
        buckets[slot_id] = []
    for name in photo_names:
        slot_id = slot_by_name.get(name)
        if slot_id not in buckets:
            buckets[None].append(name)
        else:
            buckets[slot_id].append(name)
    return [
        {"header": UNASSIGNED_HEADER, "items": buckets[None]},
        *[{"header": slot_header(slot_id), "items": buckets[slot_id]} for slot_id in slot_ids],
    ]


def map_from_board(
    containers: list[dict],
    slot_ids: list[int],
) -> tuple[dict[str, int | None], list[str]]:
    """보드 → 사진별 슬롯. 한 칸에 여러 장이면 마지막만 남긴다."""
    allowed = set(slot_ids)
    slot_by_name: dict[str, int | None] = {}
    extras: list[str] = []
    for container in containers or []:
        header = str(container.get("header") or "")
        slot_id = parse_slot_header(header)
        items = [str(item) for item in (container.get("items") or []) if str(item)]
        if slot_id is None:
            for name in items:
                slot_by_name[name] = None
            continue
        if slot_id not in allowed:
            for name in items:
                slot_by_name[name] = None
            continue
        if len(items) <= 1:
            for name in items:
                slot_by_name[name] = slot_id
            continue
        for name in items[:-1]:
            slot_by_name[name] = None
            extras.append(name)
        slot_by_name[items[-1]] = slot_id
    return slot_by_name, extras


def choices_for_photos(
    photo_names: list[str],
    slot_by_name: dict[str, int | None],
) -> list[int | None]:
    return [slot_by_name.get(name) for name in photo_names]


def list_photo_choices(photo_names: list[str], unassigned: str = "미지정") -> list[str]:
    """슬롯 선택 목록. 업로드한 사진을 빠짐없이 넣는다."""
    return [unassigned, *list(photo_names)]


def name_in_slot(slot_by_name: dict[str, int | None], slot_id: int) -> str | None:
    """해당 칸에 들어 있는 사진 이름. 없으면 None."""
    for name, current in slot_by_name.items():
        if current == int(slot_id):
            return name
    return None


def map_from_slot_photos(
    photo_by_slot: dict[int, str | None],
    photo_names: list[str],
    slot_ids: list[int],
) -> dict[str, int | None]:
    """슬롯별 사진 선택 → 사진별 슬롯. 한 사진이 두 칸이면 나중 칸만 남긴다."""
    result = {name: None for name in photo_names}
    for slot_id in slot_ids:
        name = photo_by_slot.get(slot_id)
        if not name or name not in result:
            continue
        result = place_photo(result, name, int(slot_id))
    return result


def place_photo(
    slot_by_name: dict[str, int | None],
    photo_name: str,
    slot_id: int | None,
) -> dict[str, int | None]:
    """사진을 슬롯에 넣는다. 그 칸에 있던 기존 사진은 미지정으로 돌린다."""
    result = dict(slot_by_name)
    if slot_id is not None:
        for name, current in list(result.items()):
            if current == slot_id and name != photo_name:
                result[name] = None
    result[photo_name] = slot_id
    return result
