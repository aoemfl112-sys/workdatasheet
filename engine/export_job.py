"""업로드된 사진 바이트를 임시 파일로 넘겨 PPT 바이트를 만든다.

임시 폴더는 함수가 끝나면 삭제한다. 사진은 외부 서버로 나가지 않는다.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from engine.slot_edit import apply_slots
from engine.pptx_builder import SlidePage, SlotAssignment, build_pptx


def build_pptx_bytes(
    photos: list[dict],
    choices: list[int | None],
    compress_by_name: dict[str, bool],
    label_by_slot: dict[int, str],
    template_path: str | Path,
    layout_path: str | Path,
    custom_template_bytes: bytes | None = None,
    text_values: dict[str, str] | None = None,
    layout_data: dict | None = None,
) -> bytes:
    if len(photos) != len(choices):
        raise ValueError("사진 수와 슬롯 지정 수가 일치하지 않습니다.")

    assigned_ids = [slot_id for slot_id in choices if slot_id is not None]
    seen: set[int] = set()
    for slot_id in assigned_ids:
        if slot_id in seen:
            raise ValueError(
                f"슬롯 {slot_id}번에 사진이 두 장 이상 지정되었습니다. "
                "한 슬롯에는 사진 한 장만 넣을 수 있습니다."
            )
        seen.add(slot_id)

    if not assigned_ids:
        raise ValueError("배치할 사진이 없습니다. 슬롯을 지정하세요.")

    with tempfile.TemporaryDirectory(prefix="worksheet_") as raw_tmp:
        tmp = Path(raw_tmp)
        assignments: list[SlotAssignment] = []
        for photo, slot_id in zip(photos, choices):
            if slot_id is None:
                continue
            suffix = Path(photo["name"]).suffix or ".jpg"
            image_path = tmp / f"slot_{slot_id}{suffix}"
            image_path.write_bytes(photo["bytes"])
            assignments.append(
                SlotAssignment(
                    slot_id=slot_id,
                    image_path=image_path,
                    compress=bool(compress_by_name.get(photo["name"], False)),
                    label=(label_by_slot.get(slot_id) or "").strip(),
                )
            )

        work_template = Path(template_path)
        if custom_template_bytes:
            work_template = tmp / "template.pptx"
            work_template.write_bytes(custom_template_bytes)

        output_path = tmp / "result.pptx"
        build_pptx(
            work_template,
            layout_path,
            assignments,
            output_path,
            text_values=text_values,
            layout_data=layout_data,
        )
        return output_path.read_bytes()


def build_pptx_bytes_pages(
    photos: list[dict],
    pages: list[dict],
    compress_by_name: dict[str, bool],
    template_path: str | Path,
    layout_path: str | Path,
    custom_template_bytes: bytes | None = None,
    layout_data: dict | None = None,
) -> bytes:
    """페이지별 지정 결과로 여러 장 PPT를 만든다."""
    from engine.pages import exportable_pages

    usable = exportable_pages(pages)
    if not usable:
        raise ValueError("배치할 사진이 없습니다. 슬롯을 지정하세요.")

    by_name = {photo["name"]: photo for photo in photos}
    with tempfile.TemporaryDirectory(prefix="worksheet_") as raw_tmp:
        tmp = Path(raw_tmp)
        slide_pages: list[SlidePage] = []
        for page_index, page in enumerate(usable):
            assignments: list[SlotAssignment] = []
            labels = page.get("labels") or {}
            for name, slot_id in (page.get("slots") or {}).items():
                photo = by_name.get(name)
                if photo is None:
                    raise ValueError(f"페이지에 없는 사진입니다: {name}")
                suffix = Path(photo["name"]).suffix or ".jpg"
                image_path = tmp / f"p{page_index}_slot_{slot_id}{suffix}"
                image_path.write_bytes(photo["bytes"])
                assignments.append(
                    SlotAssignment(
                        slot_id=int(slot_id),
                        image_path=image_path,
                        compress=bool(compress_by_name.get(name, False)),
                        label=(labels.get(slot_id) or labels.get(str(slot_id)) or "").strip(),
                    )
                )
            page_layout = layout_data
            if page.get("working_slots"):
                base = layout_data if layout_data is not None else None
                if base is None:
                    from engine.layout import load_layout

                    base = load_layout(layout_path)
                page_layout = apply_slots(base, page["working_slots"])
            slide_pages.append(
                SlidePage(assignments, dict(page.get("texts") or {}), page_layout)
            )

        work_template = Path(template_path)
        if custom_template_bytes:
            work_template = tmp / "template.pptx"
            work_template.write_bytes(custom_template_bytes)

        output_path = tmp / "result.pptx"
        build_pptx(
            work_template,
            layout_path,
            [],
            output_path,
            pages=slide_pages,
            layout_data=layout_data,
        )
        return output_path.read_bytes()
