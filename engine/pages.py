"""여러 장 배치. 업로드 순서대로 페이지를 나누고, 한 사진은 한 장에만 둔다."""

from __future__ import annotations

import copy
import math
from collections import Counter


def page_count_for(photo_count: int, slot_count: int) -> int:
    if photo_count <= 0:
        return 1
    if slot_count <= 0:
        return 1
    return max(1, math.ceil(photo_count / slot_count))


def default_pages(photo_names: list[str], slot_ids: list[int]) -> list[dict[str, int]]:
    """업로드 순서대로 슬롯을 채운 뒤 다음 장으로 넘긴다."""
    n_slots = len(slot_ids)
    if n_slots <= 0:
        return [{}]
    if not photo_names:
        return [{}]
    pages: list[dict[str, int]] = []
    for start in range(0, len(photo_names), n_slots):
        chunk = photo_names[start : start + n_slots]
        mapping: dict[str, int] = {}
        for index, name in enumerate(chunk):
            mapping[name] = slot_ids[index]
        pages.append(mapping)
    return pages


def _slot_ids_of(slots: list[dict] | None) -> list[int]:
    return [int(item["id"]) for item in slots or []]


def page_slot_ids(page: dict, fallback_ids: list[int]) -> list[int]:
    ids = _slot_ids_of(page.get("working_slots"))
    return ids or list(fallback_ids)


def empty_page(working_slots: list[dict] | None = None) -> dict:
    return {
        "slots": {},
        "labels": {},
        "texts": {},
        "working_slots": copy.deepcopy(working_slots or []),
    }


def wrap_pages(
    slot_maps: list[dict[str, int]],
    working_slots: list[dict] | None = None,
) -> list[dict]:
    template = copy.deepcopy(working_slots or [])
    return [
        {
            "slots": dict(item),
            "labels": {},
            "texts": {},
            "working_slots": copy.deepcopy(template),
        }
        for item in slot_maps
    ]


def assigned_names(pages: list[dict]) -> set[str]:
    names: set[str] = set()
    for page in pages:
        names.update((page.get("slots") or {}).keys())
    return names


def location_of(pages: list[dict]) -> dict[str, tuple[int, int]]:
    """사진 이름 → (페이지 번호 0부터, 슬롯)."""
    found: dict[str, tuple[int, int]] = {}
    for index, page in enumerate(pages):
        for name, slot_id in (page.get("slots") or {}).items():
            found[name] = (index, int(slot_id))
    return found


def prune_pages(
    pages: list[dict],
    live_names: set[str],
    slot_ids: list[int],
) -> list[dict]:
    cleaned: list[dict] = []
    for page in pages or []:
        allowed = set(page_slot_ids(page, slot_ids))
        slots = {}
        for name, slot_id in (page.get("slots") or {}).items():
            if name not in live_names:
                continue
            if slot_id not in allowed:
                continue
            slots[name] = int(slot_id)
        labels = dict(page.get("labels") or {})
        labels = {key: value for key, value in labels.items() if int(key) in allowed}
        cleaned.append(
            {
                "slots": slots,
                "labels": labels,
                "texts": dict(page.get("texts") or {}),
                "working_slots": copy.deepcopy(page.get("working_slots") or []),
            }
        )
    return cleaned or [empty_page()]


def absorb_new_photos(
    pages: list[dict],
    photo_names: list[str],
    slot_ids: list[int],
    working_slots: list[dict] | None = None,
) -> list[dict]:
    """새로 올라온 사진만 빈 칸·새 장에 넣는다. 이미 지정한 장은 유지한다."""
    result = [dict(page) for page in pages] or [empty_page(working_slots)]
    for page in result:
        page["slots"] = dict(page.get("slots") or {})
        page["labels"] = dict(page.get("labels") or {})
        page["texts"] = dict(page.get("texts") or {})
        if not page.get("working_slots") and working_slots:
            page["working_slots"] = copy.deepcopy(working_slots)
        else:
            page["working_slots"] = copy.deepcopy(page.get("working_slots") or [])
    taken = assigned_names(result)
    leftovers = [name for name in photo_names if name not in taken]
    if not leftovers:
        return result
    last = result[-1]
    last_ids = page_slot_ids(last, slot_ids)
    if not last_ids:
        return result
    packed = default_pages(leftovers, last_ids)
    used_slots = set(last["slots"].values())
    free = [sid for sid in last_ids if sid not in used_slots]
    first_map = packed[0]
    movable = list(first_map.items())
    while movable and free:
        name, _old_slot = movable.pop(0)
        last["slots"][name] = free.pop(0)
    rest_names = [name for name, _slot in movable]
    for extra in packed[1:]:
        rest_names.extend(extra.keys())
    extra_slots = working_slots if working_slots else last.get("working_slots")
    extra_ids = _slot_ids_of(extra_slots) or slot_ids
    if rest_names:
        result.extend(wrap_pages(default_pages(rest_names, extra_ids), extra_slots))
    return result


def sync_pages(
    pages: list[dict] | None,
    photo_names: list[str],
    slot_ids: list[int],
    reset: bool,
    working_slots: list[dict] | None = None,
) -> list[dict]:
    if reset or not pages:
        return wrap_pages(default_pages(photo_names, slot_ids), working_slots)
    pruned = prune_pages(pages, set(photo_names), slot_ids)
    return absorb_new_photos(pruned, photo_names, slot_ids, working_slots)


def names_for_board(
    photo_names: list[str],
    pages: list[dict],
    page_index: int,
) -> list[str]:
    elsewhere: set[str] = set()
    for index, page in enumerate(pages):
        if index == page_index:
            continue
        elsewhere.update((page.get("slots") or {}).keys())
    return [name for name in photo_names if name not in elsewhere]


def slot_map_for_board(
    board_names: list[str],
    pages: list[dict],
    page_index: int,
) -> dict[str, int | None]:
    current = dict((pages[page_index].get("slots") or {}) if pages else {})
    return {name: current.get(name) for name in board_names}


def apply_board_to_page(
    pages: list[dict],
    page_index: int,
    new_map: dict[str, int | None],
) -> list[dict]:
    result = [dict(page) for page in pages]
    for page in result:
        page["slots"] = dict(page.get("slots") or {})
        page["labels"] = dict(page.get("labels") or {})
        page["texts"] = dict(page.get("texts") or {})
        page["working_slots"] = copy.deepcopy(page.get("working_slots") or [])
    assigned = {name: int(slot) for name, slot in new_map.items() if slot is not None}
    result[page_index]["slots"] = assigned
    taken = set(assigned)
    for index, page in enumerate(result):
        if index == page_index:
            continue
        page["slots"] = {n: s for n, s in page["slots"].items() if n not in taken}
    return result


def _label_of(labels: dict, slot_id: int) -> str:
    if slot_id in labels:
        return str(labels[slot_id] or "")
    if str(slot_id) in labels:
        return str(labels[str(slot_id)] or "")
    for key, value in labels.items():
        try:
            if int(key) == int(slot_id):
                return str(value or "")
        except (TypeError, ValueError):
            continue
    return ""


def _copy_pages(pages: list[dict]) -> list[dict]:
    result = [dict(page) for page in pages]
    for page in result:
        page["slots"] = dict(page.get("slots") or {})
        page["labels"] = dict(page.get("labels") or {})
        page["texts"] = dict(page.get("texts") or {})
        page["working_slots"] = copy.deepcopy(page.get("working_slots") or [])
    return result


def _empty_slot_ids(page: dict, preferred: list[int] | None = None) -> list[int]:
    used = {int(slot_id) for slot_id in (page.get("slots") or {}).values()}
    if preferred:
        return [int(slot_id) for slot_id in preferred if int(slot_id) not in used]
    return [slot_id for slot_id in page_slot_ids(page, []) if slot_id not in used]


def _pull_into(current: dict, nxt: dict, free: list[int]) -> None:
    incoming = sorted(
        nxt["slots"].items(),
        key=lambda item: (int(item[1]), str(item[0])),
    )
    remaining = list(free)
    moved: set[str] = set()
    for name, old_slot in incoming:
        if not remaining:
            break
        new_slot = remaining.pop(0)
        current["slots"][name] = new_slot
        label = _label_of(nxt["labels"], int(old_slot))
        if label:
            current["labels"][new_slot] = label
        moved.add(name)
    nxt["slots"] = {name: slot for name, slot in nxt["slots"].items() if name not in moved}


def pull_photos_from_next_page(
    pages: list[dict],
    page_index: int,
    target_slot_ids: list[int],
) -> list[dict]:
    """다음 페이지에서 한 장씩 당겨 빈 칸을 채운다. 그 뒤 페이지도 같은 방식으로 이어 당긴다."""
    result = _copy_pages(pages)
    if page_index < 0 or page_index >= len(result) - 1 or not target_slot_ids:
        return result
    for index in range(page_index, len(result) - 1):
        preferred = target_slot_ids if index == page_index else None
        free = _empty_slot_ids(result[index], preferred)
        if not free:
            break
        _pull_into(result[index], result[index + 1], free)
    return result


def exportable_pages(pages: list[dict]) -> list[dict]:
    return [page for page in pages if page.get("slots")]


def validate_pages(
    photo_names: list[str],
    pages: list[dict],
    slot_ids: list[int],
) -> list[str]:
    messages: list[str] = []
    loc = location_of(pages)
    unnamed = [name for name in photo_names if name not in loc]
    if unnamed:
        messages.append(
            f"슬롯에 넣지 않은 사진 {len(unnamed)}장은 PPT에 들어가지 않습니다."
        )
    empty = [i + 1 for i, page in enumerate(pages) if not page.get("slots")]
    if empty:
        messages.append(
            "사진이 없는 페이지가 있습니다: "
            + ", ".join(str(n) for n in empty)
            + ". 생성 시 이 장은 건너뜁니다."
        )
    for index, page in enumerate(pages):
        allowed = set(page_slot_ids(page, slot_ids))
        slots = list((page.get("slots") or {}).values())
        counts = Counter(slots)
        for slot_id, count in sorted(counts.items()):
            if count > 1:
                messages.append(
                    f"{index + 1}페이지 슬롯 {slot_id}번에 사진이 {count}장입니다. "
                    "한 칸에는 한 장만 넣을 수 있습니다."
                )
            if slot_id not in allowed:
                messages.append(f"{index + 1}페이지 슬롯 {slot_id}번은 이 페이지 칸에 없습니다.")
    return messages


def blocking_page_errors(
    photo_names: list[str],
    pages: list[dict],
    slot_ids: list[int],
) -> list[str]:
    messages: list[str] = []
    if photo_names and not exportable_pages(pages):
        messages.append("배치할 사진이 없습니다. 슬롯을 지정하세요.")
    loc_names: list[str] = []
    for index, page in enumerate(pages):
        allowed = set(page_slot_ids(page, slot_ids))
        slots = list((page.get("slots") or {}).values())
        counts = Counter(slots)
        for slot_id, count in sorted(counts.items()):
            if count > 1:
                messages.append(
                    f"{index + 1}페이지 슬롯 {slot_id}번에 사진이 {count}장입니다. "
                    "한 칸에는 한 장만 넣을 수 있습니다."
                )
            if slot_id not in allowed:
                messages.append(f"{index + 1}페이지 슬롯 {slot_id}번은 이 페이지 칸에 없습니다.")
        loc_names.extend((page.get("slots") or {}).keys())
    dup = [name for name, n in Counter(loc_names).items() if n > 1]
    if dup:
        messages.append(
            "같은 사진이 여러 장에 들어가 있습니다: " + ", ".join(dup)
        )
    return messages


def copy_page_wording(source: dict, dest: dict) -> dict:
    """이전 페이지의 라벨·우측 표만 복사한다. 사진 배치와 칸 수는 그대로 둔다."""
    result = {
        "slots": dict(dest.get("slots") or {}),
        "labels": dict(source.get("labels") or {}),
        "texts": dict(source.get("texts") or {}),
        "working_slots": copy.deepcopy(dest.get("working_slots") or []),
    }
    return result
