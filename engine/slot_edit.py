"""미리보기에서 슬롯 위치·크기·개수를 조절한다. 템플릿 JSON 파일은 바꾸지 않는다."""

from __future__ import annotations

import copy
from typing import Any

MAX_SLOTS = 5
MIN_SLOTS = 1
MIN_SIZE_CM = 2.0
NUDGE_CM = 0.2
RESIZE_CM = 0.3
LABEL_HEIGHT_CM = 0.7
OVERLAP_MIN_CM2 = 0.01
SEPARATE_GAP_CM = 0.25
DEFAULT_PHOTO_AREA = {
    "x_cm": 0.30,
    "y_cm": 2.76,
    "width_cm": 22.90,
    "height_cm": 13.55,
}


def clone_slots(layout: dict[str, Any]) -> list[dict[str, Any]]:
    slots = copy.deepcopy(layout.get("slots") or [])
    if not slots:
        raise ValueError("슬롯 정의가 없습니다.")
    return sorted(slots, key=lambda item: int(item["id"]))


def apply_slots(layout: dict[str, Any], slots: list[dict[str, Any]]) -> dict[str, Any]:
    merged = dict(layout)
    merged["slots"] = sorted(copy.deepcopy(slots), key=lambda item: int(item["id"]))
    return merged


def slot_ids_of(slots: list[dict[str, Any]]) -> list[int]:
    return [int(item["id"]) for item in slots]


def photo_area(layout: dict[str, Any]) -> dict[str, float]:
    area = layout.get("photo_area") or {}
    return {
        "x_cm": float(area.get("x_cm", DEFAULT_PHOTO_AREA["x_cm"])),
        "y_cm": float(area.get("y_cm", DEFAULT_PHOTO_AREA["y_cm"])),
        "width_cm": float(area.get("width_cm", DEFAULT_PHOTO_AREA["width_cm"])),
        "height_cm": float(area.get("height_cm", DEFAULT_PHOTO_AREA["height_cm"])),
    }


def attach_label(slot: dict[str, Any], layout: dict[str, Any] | None = None) -> dict[str, Any]:
    """사진 칸을 옮기면 라벨도 같은 너비로 따라가게 한다."""
    result = dict(slot)
    height = float(result.get("label_height_cm") or LABEL_HEIGHT_CM)
    result["label_height_cm"] = height
    result["label_x_cm"] = float(result["x_cm"])
    result["label_width_cm"] = float(result["width_cm"])
    position = str(result.get("label_position") or "bottom")
    if layout:
        area = photo_area(layout)
        limit_top = area["y_cm"]
        limit_bottom = area["y_cm"] + area["height_cm"]
    else:
        limit_top = 0.15
        limit_bottom = float((layout or {}).get("slide_height_cm") or 19.05) - 0.2
    if position == "top":
        label_y = float(result["y_cm"]) - height
        if label_y < limit_top:
            position = "bottom"
            label_y = float(result["y_cm"]) + float(result["height_cm"])
    else:
        label_y = float(result["y_cm"]) + float(result["height_cm"])
        if label_y + height > limit_bottom:
            position = "top"
            label_y = max(limit_top, float(result["y_cm"]) - height)
    result["label_position"] = position
    result["label_y_cm"] = label_y
    return result


def clamp_slot(slot: dict[str, Any], layout: dict[str, Any]) -> dict[str, Any]:
    """작업 도면 밖으로 나가지 않도록 사진 영역 안에 둔다."""
    area = photo_area(layout)
    left = area["x_cm"]
    top = area["y_cm"]
    right = left + area["width_cm"]
    bottom = top + area["height_cm"]
    width = min(max(MIN_SIZE_CM, float(slot["width_cm"])), area["width_cm"])
    height = min(max(MIN_SIZE_CM, float(slot["height_cm"])), area["height_cm"])
    x = min(max(left, float(slot["x_cm"])), right - width)
    y = min(max(top, float(slot["y_cm"])), bottom - height)
    result = dict(slot)
    result["x_cm"] = round(x, 3)
    result["y_cm"] = round(y, 3)
    result["width_cm"] = round(width, 3)
    result["height_cm"] = round(height, 3)
    return attach_label(result, layout)


def nudge_slot(
    slot: dict[str, Any],
    layout: dict[str, Any],
    dx: float = 0.0,
    dy: float = 0.0,
    dw: float = 0.0,
    dh: float = 0.0,
) -> dict[str, Any]:
    moved = dict(slot)
    moved["x_cm"] = float(slot["x_cm"]) + dx
    moved["y_cm"] = float(slot["y_cm"]) + dy
    moved["width_cm"] = float(slot["width_cm"]) + dw
    moved["height_cm"] = float(slot["height_cm"]) + dh
    return clamp_slot(moved, layout)


def _overlap_area(a: dict[str, Any], b: dict[str, Any]) -> float:
    ax1, ay1 = float(a["x_cm"]), float(a["y_cm"])
    ax2, ay2 = ax1 + float(a["width_cm"]), ay1 + float(a["height_cm"])
    bx1, by1 = float(b["x_cm"]), float(b["y_cm"])
    bx2, by2 = bx1 + float(b["width_cm"]), by1 + float(b["height_cm"])
    w = min(ax2, bx2) - max(ax1, bx1)
    h = min(ay2, by2) - max(ay1, by1)
    if w <= 0 or h <= 0:
        return 0.0
    return w * h


def overlap_warnings(slots: list[dict[str, Any]]) -> list[str]:
    messages: list[str] = []
    ordered = list(slots)
    for i, left in enumerate(ordered):
        for right in ordered[i + 1 :]:
            if _overlap_area(left, right) > OVERLAP_MIN_CM2:
                messages.append(
                    f"슬롯 {left['id']}와 슬롯 {right['id']}가 겹칩니다. "
                    "'겹친 칸 밀어 내기'를 누르면 같은 크기로 맞춰 떨어집니다. "
                    "겹친 상태에서는 PPT를 만들지 않습니다."
                )
    return messages


def has_overlap(slots: list[dict[str, Any]]) -> bool:
    return bool(overlap_warnings(slots))


def _adjacent_candidates(
    moving: dict[str, Any],
    stationary: dict[str, Any],
    gap_cm: float,
) -> list[dict[str, float]]:
    sx = float(stationary["x_cm"])
    sy = float(stationary["y_cm"])
    sw = float(stationary["width_cm"])
    sh = float(stationary["height_cm"])
    mw = float(moving["width_cm"])
    mh = float(moving["height_cm"])
    mx = float(moving["x_cm"])
    my = float(moving["y_cm"])
    return [
        {"x_cm": sx + sw + gap_cm, "y_cm": my},
        {"x_cm": sx - mw - gap_cm, "y_cm": my},
        {"x_cm": mx, "y_cm": sy + sh + gap_cm},
        {"x_cm": mx, "y_cm": sy - mh - gap_cm},
    ]


def _place_beside(
    moving: dict[str, Any],
    stationary: dict[str, Any],
    layout: dict[str, Any],
    gap_cm: float,
) -> dict[str, Any]:
    """moving을 stationary 옆·위·아래로 붙인다. 공간이 없으면 겹침이 가장 적은 자리를 고른다."""
    best = clamp_slot(moving, layout)
    best_overlap = _overlap_area(best, stationary)
    best_move = 10**9
    for cand in _adjacent_candidates(moving, stationary, gap_cm):
        trial = dict(moving)
        trial["x_cm"] = cand["x_cm"]
        trial["y_cm"] = cand["y_cm"]
        trial = clamp_slot(trial, layout)
        overlap = _overlap_area(trial, stationary)
        moved = abs(trial["x_cm"] - float(moving["x_cm"])) + abs(
            trial["y_cm"] - float(moving["y_cm"])
        )
        if overlap < best_overlap - 0.01 or (
            abs(overlap - best_overlap) <= 0.01 and moved < best_move
        ):
            best = trial
            best_overlap = overlap
            best_move = moved
    return best


def _grid_shape(count: int) -> tuple[int, int]:
    """칸 수에 맞는 (열, 행). 모든 칸이 같은 크기가 되게 한다."""
    n = max(1, int(count))
    if n == 1:
        return 1, 1
    if n == 2:
        return 2, 1
    if n <= 4:
        return 2, 2
    return 3, 2


def _uniform_cell_size(
    layout: dict[str, Any],
    count: int,
    gap_cm: float,
) -> tuple[float, float]:
    area = photo_area(layout)
    cols, rows = _grid_shape(count)
    width = (area["width_cm"] - gap_cm * (cols - 1)) / cols
    height = (area["height_cm"] - gap_cm * (rows - 1)) / rows
    return (
        max(MIN_SIZE_CM, round(width, 3)),
        max(MIN_SIZE_CM, round(height, 3)),
    )


def _slot_grid_cells(
    layout: dict[str, Any],
    count: int,
    gap_cm: float,
) -> list[dict[str, float]]:
    """작업 도면 안에 같은 크기 칸을 겹치지 않게 놓는 좌표."""
    area = photo_area(layout)
    cols, _rows = _grid_shape(count)
    width, height = _uniform_cell_size(layout, count, gap_cm)
    cells: list[dict[str, float]] = []
    for index in range(max(1, count)):
        row = index // cols
        col = index % cols
        used_in_row = min(cols, max(1, count) - row * cols)
        row_width = used_in_row * width + max(0, used_in_row - 1) * gap_cm
        x0 = area["x_cm"] + max(0.0, (area["width_cm"] - row_width) / 2)
        cells.append(
            {
                "x_cm": round(x0 + col * (width + gap_cm), 3),
                "y_cm": round(area["y_cm"] + row * (height + gap_cm), 3),
                "width_cm": width,
                "height_cm": height,
            }
        )
    return cells


def equalize_slot_sizes(
    slots: list[dict[str, Any]],
    layout: dict[str, Any],
    count: int | None = None,
    gap_cm: float = SEPARATE_GAP_CM,
) -> list[dict[str, Any]]:
    """모든 칸의 사진 크기를 같게 맞춘다. 위치는 칸 중심을 기준으로 유지한다."""
    if not slots:
        return []
    target = max(1, int(count) if count is not None else len(slots))
    width, height = _uniform_cell_size(layout, target, gap_cm)
    result: list[dict[str, Any]] = []
    for item in slots:
        updated = copy.deepcopy(item)
        center_x = float(item["x_cm"]) + float(item["width_cm"]) / 2.0
        center_y = float(item["y_cm"]) + float(item["height_cm"]) / 2.0
        updated["width_cm"] = width
        updated["height_cm"] = height
        updated["x_cm"] = center_x - width / 2.0
        updated["y_cm"] = center_y - height / 2.0
        result.append(clamp_slot(updated, layout))
    return sorted(result, key=lambda item: int(item["id"]))


def pack_equal_grid(
    slots: list[dict[str, Any]],
    layout: dict[str, Any],
    gap_cm: float = SEPARATE_GAP_CM,
) -> list[dict[str, Any]]:
    """같은 크기 칸을 격자 자리에 넣어 겹침을 없앤다."""
    if not slots:
        return []
    cells = _slot_grid_cells(layout, len(slots), gap_cm)
    area = photo_area(layout)
    mid_y = area["y_cm"] + area["height_cm"] / 2.0
    result: list[dict[str, Any]] = []
    ordered = sorted(slots, key=lambda item: int(item["id"]))
    for item, cell in zip(ordered, cells):
        updated = copy.deepcopy(item)
        updated["x_cm"] = cell["x_cm"]
        updated["y_cm"] = cell["y_cm"]
        updated["width_cm"] = cell["width_cm"]
        updated["height_cm"] = cell["height_cm"]
        updated["label_position"] = "top" if cell["y_cm"] >= mid_y - 0.01 else "bottom"
        result.append(clamp_slot(updated, layout))
    return result


def _push_apart(
    slots: list[dict[str, Any]],
    layout: dict[str, Any],
    gap_cm: float,
) -> list[dict[str, Any]]:
    result = [clamp_slot(copy.deepcopy(item), layout) for item in slots]
    for _ in range(8):
        moved = False
        ordered = sorted(range(len(result)), key=lambda idx: int(result[idx]["id"]))
        for a, i in enumerate(ordered):
            for j in ordered[a + 1 :]:
                left = result[i]
                right = result[j]
                if _overlap_area(left, right) <= OVERLAP_MIN_CM2:
                    continue
                placed = _place_beside(right, left, layout, gap_cm)
                if _overlap_area(left, placed) > OVERLAP_MIN_CM2:
                    placed_left = _place_beside(left, placed, layout, gap_cm)
                    if _overlap_area(placed_left, placed) <= OVERLAP_MIN_CM2 or (
                        _overlap_area(placed_left, placed) < _overlap_area(left, placed)
                    ):
                        result[i] = placed_left
                result[j] = placed
                moved = True
        if not moved:
            break
    return result


def separate_overlapping(
    slots: list[dict[str, Any]],
    layout: dict[str, Any],
    gap_cm: float = SEPARATE_GAP_CM,
) -> list[dict[str, Any]]:
    """겹친 칸을 같은 크기로 맞추고 격자 자리에 놓아 겹침을 없앤다."""
    return pack_equal_grid(slots, layout, gap_cm)


def add_slot(layout: dict[str, Any], slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(slots) >= MAX_SLOTS:
        raise ValueError(f"슬롯은 최대 {MAX_SLOTS}개까지 넣을 수 있습니다.")
    next_id = max(int(item["id"]) for item in slots) + 1 if slots else 1
    next_count = len(slots) + 1
    existing = equalize_slot_sizes(slots, layout, count=next_count)
    cells = _slot_grid_cells(layout, next_count, SEPARATE_GAP_CM)

    def score(box: dict[str, float]) -> float:
        return sum(_overlap_area(box, item) for item in existing)

    box = min(cells, key=score)
    created = clamp_slot(
        {
            "id": next_id,
            "name": f"SLOT_{next_id}",
            "x_cm": box["x_cm"],
            "y_cm": box["y_cm"],
            "width_cm": box["width_cm"],
            "height_cm": box["height_cm"],
            "label_position": "bottom",
            "label_height_cm": LABEL_HEIGHT_CM,
        },
        layout,
    )
    return pack_equal_grid([*existing, created], layout)


def set_slot_count(
    layout: dict[str, Any],
    slots: list[dict[str, Any]],
    count: int,
) -> list[dict[str, Any]]:
    """이 페이지의 칸 수를 1~최대값으로 맞춘다. 다른 페이지는 건드리지 않는다."""
    target = max(MIN_SLOTS, min(MAX_SLOTS, int(count)))
    result = [copy.deepcopy(item) for item in slots]
    while len(result) < target:
        result = add_slot(layout, result)
    while len(result) > target:
        result = remove_last_slot(result)
    return result


def remove_last_slot(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(slots) <= MIN_SLOTS:
        raise ValueError("슬롯은 최소 1개는 남겨야 합니다.")
    last_id = max(int(item["id"]) for item in slots)
    return [copy.deepcopy(item) for item in slots if int(item["id"]) != last_id]


def apply_canvas_boxes(
    slots: list[dict[str, Any]],
    boxes: list[dict[str, Any]] | None,
    layout: dict[str, Any],
) -> list[dict[str, Any]]:
    """미리보기에서 끌어 옮긴 칸 좌표를 슬롯에 반영하고 사진 영역 안으로 가둔다."""
    by_id = {int(item["id"]): copy.deepcopy(item) for item in slots}
    for box in boxes or []:
        try:
            slot_id = int(box["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if slot_id not in by_id:
            continue
        updated = dict(by_id[slot_id])
        for key in ("x_cm", "y_cm", "width_cm", "height_cm"):
            if key in box:
                updated[key] = float(box[key])
        by_id[slot_id] = clamp_slot(updated, layout)
    return sorted(by_id.values(), key=lambda item: int(item["id"]))


def geometry_changed(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    tol: float = 0.01,
) -> bool:
    if len(before) != len(after):
        return True
    old_map = {int(item["id"]): item for item in before}
    for item in after:
        slot_id = int(item["id"])
        prev = old_map.get(slot_id)
        if prev is None:
            return True
        for key in ("x_cm", "y_cm", "width_cm", "height_cm"):
            if abs(float(item[key]) - float(prev[key])) > tol:
                return True
    return False
