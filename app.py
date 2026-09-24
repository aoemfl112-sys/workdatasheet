"""작업지도서 사진 배치 — Streamlit 화면.

업로드 · 슬롯 지정 · 라벨 후 PPT를 만들어 다운로드한다.
기본 처리는 이 PC에서만 이루어지며, 생성에 쓴 임시 파일은 바로 삭제한다.
"""

from __future__ import annotations

import hashlib
import traceback
from pathlib import Path

import streamlit as st

from engine.assist import gemini_available, suggest_labels_with_gemini
from engine.board import (
    UNASSIGNED_HEADER,
    board_from_map,
    list_photo_choices,
    map_from_board,
    map_from_slot_photos,
    name_in_slot,
    uniquify_name,
)
from engine.export_job import build_pptx_bytes_pages
from engine.layout import list_layouts
from engine.pages import (
    apply_board_to_page,
    blocking_page_errors,
    copy_page_wording,
    empty_page,
    exportable_pages,
    location_of,
    names_for_board,
    pull_photos_from_next_page,
    slot_map_for_board,
    sync_pages,
    validate_pages,
)
from engine.local_open import open_local_file, save_pptx_file
from engine.runtime import is_server_mode
from engine.saved_slots import delete_saved, list_saved, load_slots, save_slots
from engine.slot_canvas import build_canvas_payload, render_slot_canvas
from engine.slot_edit import (
    MAX_SLOTS,
    MIN_SLOTS,
    add_slot,
    apply_canvas_boxes,
    apply_slots,
    clamp_slot,
    clone_slots,
    geometry_changed,
    has_overlap,
    overlap_warnings,
    remove_last_slot,
    separate_overlapping,
    set_slot_count,
    slot_ids_of,
)
from engine.session_export import (
    DEFAULT_DOWNLOAD_NAME,
    MAX_HISTORY,
    make_history_item,
    push_history,
    safe_download_name,
    suggested_filename,
)
from engine.text_fields import fields_from_layout, nonempty_values
from engine.ui_rules import is_allowed_image_name

ROOT = Path(__file__).resolve().parent
UNASSIGNED = "미지정"
MODE_SLOT = "슬롯에서 사진 선택"
MODE_BOARD = "끌어다 놓기"

BOARD_STYLE = """
.sortable-component.vertical {
    align-items: stretch;
    background: transparent;
}
.sortable-container {
    background-color: #f1f5f4;
    border: 1px solid #cbd5d1;
    border-radius: 10px;
    min-width: 160px;
    margin: 4px;
}
.sortable-container-header {
    font-weight: 700;
    padding: 8px 10px;
    background: #0f766e;
    color: #fff;
    border-radius: 10px 10px 0 0;
}
.sortable-container-body {
    min-height: 96px;
    background: #ffffff;
}
.sortable-item, .sortable-item:hover {
    background-color: #0f766e;
    color: #fff;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
}
"""

APP_CSS = """
<style>
@import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");
html, body, [class*="css"] {
    font-family: Pretendard, "Malgun Gothic", sans-serif;
}
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 3rem;
    max-width: 1400px;
}
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }

.app-hero {
    background: linear-gradient(135deg, #134e4a 0%, #0f766e 58%, #1d4e89 100%);
    color: #fff;
    border-radius: 16px;
    padding: 18px 22px 16px 22px;
    margin-bottom: 14px;
    box-shadow: 0 10px 28px rgba(15, 118, 110, 0.22);
}
.app-hero h1 {
    font-size: 1.55rem;
    margin: 0 0 4px 0;
    letter-spacing: -0.02em;
}
.app-hero p {
    margin: 0;
    opacity: 0.92;
    font-size: 0.95rem;
}
.step-card {
    background: #fff;
    border: 1px solid #d7e0dc;
    border-radius: 14px;
    padding: 4px 4px 8px 4px;
    margin-bottom: 10px;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.step-label {
    display: inline-block;
    background: #ccfbf1;
    color: #115e59;
    font-weight: 700;
    font-size: 0.78rem;
    padding: 3px 9px;
    border-radius: 999px;
    margin: 8px 0 2px 8px;
}
.status-ok { color: #047857; font-weight: 700; }
.status-wait { color: #b45309; font-weight: 700; }
.status-bad { color: #b91c1c; font-weight: 700; }
div[data-testid="stMetric"] {
    background: #fff;
    border: 1px solid #d7e0dc;
    border-radius: 12px;
    padding: 8px 10px;
}
div.stButton > button {
    min-height: 2.6rem;
    font-weight: 700;
    border-radius: 10px;
}
div.stDownloadButton > button {
    min-height: 2.6rem;
    font-weight: 700;
    border-radius: 10px;
}
.thumb-place {
    font-size: 0.78rem;
    color: #0f766e;
    font-weight: 700;
}
.ppt-bar {
    background: #f0fdfa;
    border: 1px solid #99f6e4;
    border-radius: 14px;
    padding: 4px 8px 12px 8px;
    margin: 8px 0 14px 0;
}
</style>
"""


def _init_state() -> None:
    defaults = {
        "custom_template": None,
        "pptx_bytes": None,
        "pptx_error": None,
        "pptx_trace": None,
        "board_epoch": 0,
        "pages": [],
        "page_index": 0,
        "pages_layout_id": "",
        "pptx_history": [],
        "download_name": DEFAULT_DOWNLOAD_NAME,
        "last_result": None,
        "working_slots": [],
        "working_slots_layout_id": "",
        "slot_canvas_seq": 0,
        "slot_canvas_key": "",
        "last_pptx_path": "",
        "pptx_open_error": None,
        "layout_save_notice": "",
        "pending_page_index": None,
        "pending_photo_key_sync": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _slots_geom_sig(slots: list[dict]) -> str:
    parts = []
    for item in sorted(slots, key=lambda slot: int(slot["id"])):
        parts.append(
            f"{item['id']}:{round(float(item['x_cm']), 2)}:{round(float(item['y_cm']), 2)}:"
            f"{round(float(item['width_cm']), 2)}:{round(float(item['height_cm']), 2)}"
        )
    return hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()[:8]


def _sync_photo_pick_keys(layout_id: str, page_index: int) -> None:
    """목록 선택칸을 실제 배치와 같게 맞춘다. 다음 페이지 값이 되돌아오지 않게 한다."""
    if page_index < 0 or page_index >= len(st.session_state.pages):
        return
    page = st.session_state.pages[page_index]
    slot_map = page.get("slots") or {}
    ids = slot_ids_of(page.get("working_slots") or [])
    if not ids:
        ids = sorted({int(slot_id) for slot_id in slot_map.values()})
    for slot_id in ids:
        st.session_state[f"{layout_id}_p{page_index}_slotphoto_{int(slot_id)}"] = (
            name_in_slot(slot_map, int(slot_id)) or UNASSIGNED
        )


def _fill_new_slots_from_next_page(
    layout_id: str,
    page_index: int,
    added_ids: list[int],
) -> None:
    if not added_ids:
        return
    st.session_state.pages = pull_photos_from_next_page(
        st.session_state.pages, page_index, added_ids
    )
    pending = list(range(page_index, len(st.session_state.pages)))
    st.session_state.pending_photo_key_sync = pending


def _names_sig(names: list[str]) -> str:
    joined = "|".join(names)
    return hashlib.md5(joined.encode("utf-8")).hexdigest()[:10]


def _sort_items(containers: list[dict], key: str):
    from streamlit_sortables import sort_items

    return sort_items(
        containers,
        multi_containers=True,
        direction="vertical",
        custom_style=BOARD_STYLE,
        key=key,
    )


def _ensure_working_slots(layout_id: str, base_layout: dict) -> list[dict]:
    if st.session_state.working_slots_layout_id != layout_id or not st.session_state.working_slots:
        st.session_state.working_slots = clone_slots(base_layout)
        st.session_state.working_slots_layout_id = layout_id
        st.session_state.slot_canvas_seq = 0
        st.session_state.slot_canvas_key = ""
    return st.session_state.working_slots


def _ensure_page_slots(page: dict, base_layout: dict) -> list[dict]:
    if not page.get("working_slots"):
        page["working_slots"] = clone_slots(base_layout)
    return page["working_slots"]


def _apply_page_slots(page_index: int, slots: list[dict]) -> None:
    allowed = set(slot_ids_of(slots))
    page = st.session_state.pages[page_index]
    page["working_slots"] = slots
    page["slots"] = {
        name: int(slot_id)
        for name, slot_id in (page.get("slots") or {}).items()
        if int(slot_id) in allowed
    }
    kept_labels = {}
    for key, value in (page.get("labels") or {}).items():
        try:
            if int(key) in allowed:
                kept_labels[key] = value
        except (TypeError, ValueError):
            continue
    page["labels"] = kept_labels
    st.session_state.pages[page_index] = page
    st.session_state.working_slots = slots


def _render_slot_editor(
    layout_id: str,
    base_layout: dict,
    *,
    page_index: int,
    photos_by_slot: dict[int, bytes],
    labels: dict,
    text_values: dict,
) -> None:
    """미리보기에서 칸을 끌어 옮기고 모서리로 크기를 조절한다."""
    slots = st.session_state.working_slots
    ids = slot_ids_of(slots)
    selected_id = st.session_state.get("slot_canvas_selected")
    if selected_id not in ids:
        selected_id = ids[0] if ids else 1

    overlap_msgs = overlap_warnings(st.session_state.working_slots)
    if overlap_msgs:
        for msg in overlap_msgs:
            st.error(msg)

    layout = apply_slots(base_layout, st.session_state.working_slots)
    payload = build_canvas_payload(
        layout,
        st.session_state.working_slots,
        photos_by_slot,
        labels=labels,
        text_values=text_values,
        selected_id=selected_id,
    )
    canvas_key = (
        f"slot_canvas_{layout_id}_p{page_index}_{len(ids)}_"
        f"{st.session_state.board_epoch}_{_slots_geom_sig(slots)}"
    )
    if st.session_state.slot_canvas_key != canvas_key:
        st.session_state.slot_canvas_key = canvas_key
        st.session_state.slot_canvas_seq = 0
    result = render_slot_canvas(payload, key=canvas_key)
    if isinstance(result, dict) and result.get("type") == "commit":
        seq = int(result.get("seq") or 0)
        if seq > int(st.session_state.slot_canvas_seq or 0):
            st.session_state.slot_canvas_seq = seq
            updated = apply_canvas_boxes(
                st.session_state.working_slots,
                result.get("slots"),
                base_layout,
            )
            changed = geometry_changed(st.session_state.working_slots, updated)
            # 밀어 내기로 맞춘 배치를 미리보기의 이전 좌표가 다시 덮지 않게 한다.
            if changed and not (
                has_overlap(updated) and not has_overlap(st.session_state.working_slots)
            ):
                _apply_page_slots(page_index, updated)
                try:
                    picked_id = int(result.get("selected_id"))
                except (TypeError, ValueError):
                    picked_id = None
                if picked_id in slot_ids_of(updated):
                    st.session_state.slot_canvas_selected = picked_id
                st.rerun()
            else:
                try:
                    picked_id = int(result.get("selected_id"))
                except (TypeError, ValueError):
                    picked_id = None
                if picked_id in ids:
                    st.session_state.slot_canvas_selected = picked_id

    add_col, del_col, reset_col, sep_col = st.columns(4)
    with add_col:
        if st.button("칸 추가", disabled=len(ids) >= MAX_SLOTS, key=f"add_slot_btn_{page_index}", use_container_width=True):
            old_ids = set(ids)
            added_slots = add_slot(base_layout, slots)
            _apply_page_slots(page_index, added_slots)
            added_ids = [slot_id for slot_id in slot_ids_of(added_slots) if slot_id not in old_ids]
            _fill_new_slots_from_next_page(layout_id, page_index, added_ids)
            st.session_state.board_epoch = int(st.session_state.board_epoch) + 1
            st.rerun()
    with del_col:
        if st.button("칸 삭제", disabled=len(ids) <= MIN_SLOTS, key=f"del_slot_btn_{page_index}", use_container_width=True):
            _apply_page_slots(page_index, remove_last_slot(slots))
            st.session_state.board_epoch = int(st.session_state.board_epoch) + 1
            st.rerun()
    with reset_col:
        if st.button("원래 위치로", key=f"reset_slot_btn_{page_index}", use_container_width=True):
            _apply_page_slots(page_index, clone_slots(base_layout))
            st.session_state.board_epoch = int(st.session_state.board_epoch) + 1
            st.rerun()
    with sep_col:
        if st.button("겹친 칸 밀어 내기", key=f"separate_slots_btn_{page_index}", use_container_width=True):
            _apply_page_slots(
                page_index,
                separate_overlapping(st.session_state.working_slots, base_layout),
            )
            st.session_state.board_epoch = int(st.session_state.board_epoch) + 1
            st.rerun()
    st.caption(f"이 페이지만 {len(ids)}칸 · 최대 {MAX_SLOTS}칸. 칸을 끌어 옮기고, 주황 점으로 크기를 바꿉니다. 칸을 추가하면 다음 페이지 사진이 한 장씩 앞으로 당겨집니다.")

    with st.expander("이 PC에 배치 저장 · 불러오기"):
        if st.session_state.get("layout_save_notice"):
            st.success(st.session_state.layout_save_notice)
            st.session_state.layout_save_notice = ""
        saved_items = list_saved(ROOT)
        save_name_key = f"save_layout_name_{layout_id}"
        if save_name_key not in st.session_state:
            st.session_state[save_name_key] = "현장_배치"
        save_col, load_col, del_col = st.columns([2, 2, 1])
        with save_col:
            save_name = st.text_input("저장 이름", key=save_name_key)
            if st.button("지금 배치 저장", key="save_slots_btn", use_container_width=True):
                path = save_slots(
                    ROOT,
                    save_name,
                    layout_id,
                    st.session_state.working_slots,
                )
                st.session_state.layout_save_notice = f"저장했습니다: {path.name}"
                st.rerun()
        with load_col:
            if saved_items:
                saved_captions = [
                    f"{item['name']} ({item['slot_count']}칸)"
                    for item in saved_items
                ]
                picked = st.selectbox(
                    "저장된 배치", saved_captions, key=f"load_layout_pick_{layout_id}"
                )
                chosen = saved_items[saved_captions.index(picked)]
                if st.button("불러오기", key="load_slots_btn", use_container_width=True):
                    loaded = load_slots(chosen["path"])
                    _apply_page_slots(
                        page_index,
                        [clamp_slot(item, base_layout) for item in loaded["slots"]],
                    )
                    st.session_state.board_epoch = int(st.session_state.board_epoch) + 1
                    st.rerun()
            else:
                st.caption("저장된 배치가 없습니다.")
        with del_col:
            st.write("")
            st.write("")
            if saved_items and st.button("삭제", key="delete_slots_btn", use_container_width=True):
                saved_captions = [
                    f"{item['name']} ({item['slot_count']}칸)"
                    for item in saved_items
                ]
                picked = st.session_state.get(f"load_layout_pick_{layout_id}")
                if picked in saved_captions:
                    delete_saved(saved_items[saved_captions.index(picked)]["path"])
                    st.rerun()


def _current_page() -> dict:
    pages = st.session_state.pages
    index = int(st.session_state.page_index)
    if not pages:
        st.session_state.pages = [empty_page()]
        pages = st.session_state.pages
    if index < 0 or index >= len(pages):
        st.session_state.page_index = 0
        index = 0
    return pages[index]


def _render_history(*, skip_newest: bool = False) -> None:
    items = list(st.session_state.pptx_history)
    if skip_newest and items:
        items = items[1:]
    if not items:
        if st.session_state.pptx_history:
            st.caption(f"이번 세션 생성 기록은 최대 {MAX_HISTORY}개까지 메모리에만 둡니다.")
        return
    st.markdown("**이전에 만든 PPT** (브라우저를 닫으면 사라집니다. 디스크에는 남기지 않습니다.)")
    for item in items:
        label = (
            f"{item['created_at']} · {item['filename']} · "
            f"{item['slide_count']}장 · 사진 {item['photo_count']}장"
        )
        st.download_button(
            label=f"다시 받기: {item['filename']}",
            data=item["bytes"],
            file_name=item["filename"],
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            key=f"hist_dl_{item['id']}",
            help=label,
        )
    if st.button("생성 목록 비우기", key="clear_history"):
        st.session_state.pptx_history = []
        st.rerun()


def _page_status(photo_names: list[str], slot_ids: list[int]) -> tuple[list[str], list[str]]:
    warnings = validate_pages(photo_names, st.session_state.pages, slot_ids)
    blockers = blocking_page_errors(photo_names, st.session_state.pages, slot_ids)
    overlap_pages = [
        str(index + 1)
        for index, page in enumerate(st.session_state.pages)
        if has_overlap(page.get("working_slots") or [])
    ]
    if overlap_pages:
        blockers.append(
            f"{', '.join(overlap_pages)}페이지 칸이 겹쳐 있습니다. "
            "'겹친 칸 밀어 내기'를 누른 뒤 만드세요."
        )
    return warnings, blockers


def _render_ppt_bar(
    *,
    photos: list[dict],
    base_layout: dict,
    template_path: Path,
    layout_path,
    usable_count: int,
    blockers: list[str],
    warnings: list[str],
) -> None:
    """PPT 만들기·받기를 작업 화면 위에 둔다."""
    st.markdown('<span class="step-label">PPT 만들기</span>', unsafe_allow_html=True)
    if blockers:
        for msg in blockers:
            st.error(msg)
    elif warnings:
        for msg in warnings:
            st.warning(msg)
    else:
        st.success(f"준비됐습니다. PPT {usable_count}장을 만들 수 있습니다.")

    suggested = suggested_filename(st.session_state.pages)
    if "download_name_input" not in st.session_state:
        st.session_state.download_name_input = suggested.replace(".pptx", "")
    server_mode = is_server_mode()
    name_col, opt_col, btn_col = st.columns([2.2, 1.4, 1.4])
    with name_col:
        save_stem = st.text_input(
            "저장 파일 이름",
            key="download_name_input",
            help="비우면 기본 이름을 씁니다. 시험 제목을 적어두면 그걸 초안으로 쓸 수 있습니다.",
        )
    download_name = safe_download_name(save_stem, DEFAULT_DOWNLOAD_NAME)
    with opt_col:
        st.caption(f"받게 될 파일: `{download_name}`")
        if not server_mode:
            if "open_after_generate" not in st.session_state:
                st.session_state.open_after_generate = False
            st.checkbox("생성 후 이 PC에서 열기", key="open_after_generate")
    with btn_col:
        st.write("")
        generate = st.button(
            "PPT 만들기",
            type="primary",
            disabled=bool(blockers),
            use_container_width=True,
        )
    if generate:
        try:
            with st.spinner("PPT를 만드는 중입니다."):
                custom = st.session_state.custom_template
                export_pages = []
                for page in st.session_state.pages:
                    export_pages.append(
                        {
                            "slots": dict(page.get("slots") or {}),
                            "labels": dict(page.get("labels") or {}),
                            "texts": nonempty_values(page.get("texts") or {}),
                            "working_slots": list(page.get("working_slots") or []),
                        }
                    )
                data = build_pptx_bytes_pages(
                    photos=photos,
                    pages=export_pages,
                    compress_by_name={},
                    template_path=template_path,
                    layout_path=layout_path,
                    custom_template_bytes=None if custom is None else custom["bytes"],
                    layout_data=apply_slots(base_layout, st.session_state.working_slots),
                )
            st.session_state.pptx_bytes = data
            st.session_state.download_name = download_name
            local_path = save_pptx_file(data, download_name, ROOT / "output")
            st.session_state.last_pptx_path = str(local_path)
            photo_count = sum(len(p.get("slots") or {}) for p in export_pages)
            slide_count = len(exportable_pages(export_pages))
            st.session_state.pptx_history = push_history(
                st.session_state.pptx_history,
                make_history_item(data, download_name, slide_count, photo_count),
                limit=MAX_HISTORY,
            )
            st.session_state.last_result = {
                "filename": download_name,
                "slide_count": slide_count,
                "photo_count": photo_count,
                "bytes": len(data),
                "path": str(local_path),
            }
            st.session_state.pptx_error = None
            st.session_state.pptx_trace = None
            st.session_state.pptx_open_error = None
            if (not server_mode) and st.session_state.get("open_after_generate"):
                try:
                    open_local_file(local_path)
                except OSError as exc:
                    st.session_state.pptx_open_error = str(exc)
        except Exception as exc:
            st.session_state.pptx_error = str(exc)
            st.session_state.pptx_trace = traceback.format_exc()
            st.session_state.pptx_bytes = None
            st.session_state.last_result = None

    if st.session_state.pptx_error:
        st.error("PPT를 만들지 못했습니다. 입력값은 그대로 있습니다. " + st.session_state.pptx_error)
        if st.session_state.pptx_trace:
            with st.expander("오류 상세"):
                st.code(st.session_state.pptx_trace)

    if st.session_state.pptx_bytes:
        result = st.session_state.get("last_result") or {}
        st.success("PPT가 준비되었습니다. 바로 받으세요.")
        if st.session_state.get("pptx_open_error"):
            st.warning(
                "PPT는 만들었지만 자동으로 열지 못했습니다. "
                + str(st.session_state.pptx_open_error)
            )
        dl_col, open_col, m1, m2 = st.columns([1.4, 1.2, 1, 1])
        with dl_col:
            st.download_button(
                label="PPT 받기",
                data=st.session_state.pptx_bytes,
                file_name=st.session_state.get("download_name") or DEFAULT_DOWNLOAD_NAME,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                type="primary",
                key="latest_dl",
                use_container_width=True,
            )
        with open_col:
            if not server_mode and st.button("이 PC에서 PPT 열기", key="open_ppt_btn", use_container_width=True):
                try:
                    path_text = st.session_state.get("last_pptx_path")
                    path = Path(path_text) if path_text else None
                    if path is None or not path.exists():
                        path = save_pptx_file(
                            st.session_state.pptx_bytes,
                            st.session_state.get("download_name") or DEFAULT_DOWNLOAD_NAME,
                            ROOT / "output",
                        )
                        st.session_state.last_pptx_path = str(path)
                    open_local_file(path)
                    st.success("이 PC에서 PPT를 열었습니다.")
                except Exception as exc:
                    st.error("파일을 열지 못했습니다. 다운로드 버튼으로 받으세요. " + str(exc))
        m1.metric("슬라이드", f"{result.get('slide_count', '-')}장")
        m2.metric("배치 사진", f"{result.get('photo_count', '-')}장")


def main() -> None:
    st.set_page_config(
        page_title="작업지도서 사진 배치",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _init_state()
    st.markdown(APP_CSS, unsafe_allow_html=True)
    catalogs = list_layouts(ROOT / "config")
    catalog_labels = [f"{c['display_name']} ({c['slot_count']}칸)" for c in catalogs]

    if is_server_mode():
        hero_note = "사진 올리고 칸에 넣은 뒤, PPT 만들기만 누르면 됩니다. 완성 파일은 다운로드로 받으세요."
    else:
        hero_note = "사진 올리고 칸에 넣은 뒤, PPT 만들기만 누르면 됩니다. 파일은 이 컴퓨터 안에서만 처리합니다."
    st.markdown(
        '<div class="app-hero"><h1>작업지도서 사진 배치</h1>'
        f"<p>{hero_note}</p></div>",
        unsafe_allow_html=True,
    )
    with st.sidebar:
        st.markdown("### 오늘 할 일")
        st.markdown(
            "1. **양식**과 **사진**을 올립니다.\n"
            "2. 위쪽 **PPT 만들기**로 파일을 받습니다.\n"
            "3. 미리보기에서 칸·사진을 맞춥니다.\n\n"
            "페이지마다 1칸~5칸까지 고를 수 있습니다. (4칸·5칸 포함)"
        )
        st.caption("한 칸에는 사진 한 장만, 한 사진은 한 쪽에만 들어갑니다.")
        with st.expander("다른 PPT 양식 쓰기"):
            uploaded_tpl = st.file_uploader("PPT 템플릿 (.pptx)", type=["pptx"], key="tpl_file")
            if uploaded_tpl is not None:
                st.session_state.custom_template = {
                    "name": uploaded_tpl.name,
                    "bytes": uploaded_tpl.getvalue(),
                }
                st.caption(f"사용: {uploaded_tpl.name}")
            else:
                st.session_state.custom_template = None
                st.caption("비워 두면 위 양식을 씁니다.")

    top_left, top_right = st.columns([1, 1.2])
    with top_left:
        st.markdown('<span class="step-label">1 양식</span>', unsafe_allow_html=True)
        picked = st.selectbox("칸 배치", catalog_labels, key="layout_pick")
    with top_right:
        st.markdown('<span class="step-label">2 사진</span>', unsafe_allow_html=True)
        files = st.file_uploader(
            "JPG / PNG 여러 장 한꺼번에",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="photo_files",
        )
    catalog = catalogs[catalog_labels.index(picked)]
    base_layout = catalog["layout"]
    layout_id = str(catalog["id"])
    layout_path = catalog["path"]
    template_path = ROOT / catalog["template_file"]
    _ensure_working_slots(layout_id, base_layout)
    layout = apply_slots(base_layout, st.session_state.working_slots)
    slot_ids = slot_ids_of(layout["slots"])
    st.caption(f"선택 양식: {catalog['display_name']}")
    if not template_path.exists() and st.session_state.custom_template is None:
        st.error(f"템플릿 파일이 없습니다: {template_path}")
        return

    photos: list[dict] = []
    rejected: list[str] = []
    used_names: set[str] = set()
    if files:
        for item in files:
            if not is_allowed_image_name(item.name):
                rejected.append(item.name)
                continue
            photos.append(
                {
                    "name": uniquify_name(item.name, used_names),
                    "bytes": item.getvalue(),
                }
            )
    if rejected:
        st.error("지원하지 않는 형식입니다: " + ", ".join(rejected))

    photo_names = [p["name"] for p in photos]
    layout_changed = st.session_state.pages_layout_id != layout_id
    base_slots = clone_slots(base_layout)
    st.session_state.pages = sync_pages(
        st.session_state.pages,
        photo_names,
        slot_ids_of(base_slots),
        reset=layout_changed,
        working_slots=base_slots,
    )
    st.session_state.pages_layout_id = layout_id
    for page in st.session_state.pages:
        _ensure_page_slots(page, base_layout)
    if st.session_state.page_index >= len(st.session_state.pages):
        st.session_state.page_index = 0

    if not photos:
        st.info("사진을 올리면 칸 넣기와 미리보기가 여기에 나타납니다.")
        _render_history()
        return

    pending = st.session_state.pop("pending_page_index", None)
    if pending is not None:
        st.session_state.page_index = max(
            0, min(int(pending), len(st.session_state.pages) - 1)
        )
        st.session_state.page_pick_num = int(st.session_state.page_index) + 1

    page_numbers = list(range(1, len(st.session_state.pages) + 1))
    nav_left, nav_add, nav_del, nav_count = st.columns([2.2, 0.8, 0.9, 2.1])
    with nav_left:
        picked_page = st.radio(
            "페이지",
            page_numbers,
            index=int(st.session_state.page_index),
            horizontal=True,
            format_func=str,
            key="page_pick_num",
        )
        st.session_state.page_index = page_numbers.index(int(picked_page))
    with nav_add:
        st.write("")
        if st.button("쪽 추가", use_container_width=True):
            current_slots = _ensure_page_slots(
                st.session_state.pages[st.session_state.page_index], base_layout
            )
            st.session_state.pages.append(empty_page(current_slots))
            st.session_state.pending_page_index = len(st.session_state.pages) - 1
            st.rerun()
    with nav_del:
        st.write("")
        if st.button("이 쪽 삭제", disabled=len(st.session_state.pages) <= 1, use_container_width=True):
            del st.session_state.pages[st.session_state.page_index]
            st.session_state.pending_page_index = min(
                st.session_state.page_index, len(st.session_state.pages) - 1
            )
            st.rerun()

    page_index = int(st.session_state.page_index)
    st.session_state.working_slots = _ensure_page_slots(
        st.session_state.pages[page_index], base_layout
    )
    slot_ids = slot_ids_of(st.session_state.working_slots)
    layout = apply_slots(base_layout, st.session_state.working_slots)

    count_key = f"page_slot_count_{layout_id}_{page_index}"
    if st.session_state.get(count_key) != len(slot_ids):
        st.session_state[count_key] = len(slot_ids)
    with nav_count:
        picked_count = st.radio(
            "이 페이지 칸 수",
            list(range(MIN_SLOTS, MAX_SLOTS + 1)),
            horizontal=True,
            key=count_key,
            help="선택한 페이지만 칸 개수가 바뀝니다. 다른 페이지는 그대로입니다.",
        )
    if int(picked_count) != len(slot_ids):
        old_ids = set(slot_ids)
        new_slots = set_slot_count(
            base_layout, st.session_state.working_slots, int(picked_count)
        )
        _apply_page_slots(page_index, new_slots)
        added_ids = [slot_id for slot_id in slot_ids_of(new_slots) if slot_id not in old_ids]
        _fill_new_slots_from_next_page(layout_id, page_index, added_ids)
        st.session_state.board_epoch = int(st.session_state.board_epoch) + 1
        st.rerun()
    usable_count = len(exportable_pages(st.session_state.pages))
    loc_now = location_of(st.session_state.pages)
    unassigned_n = sum(1 for name in photo_names if name not in loc_now)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("올린 사진", f"{len(photos)}장")
    m2.metric("전체 쪽", f"{len(st.session_state.pages)}쪽")
    m3.metric("미지정", f"{unassigned_n}장")
    m4.metric("PPT에 들어갈 쪽", f"{usable_count}쪽")

    warnings, blockers = _page_status(photo_names, slot_ids)
    _render_ppt_bar(
        photos=photos,
        base_layout=base_layout,
        template_path=template_path,
        layout_path=layout_path,
        usable_count=usable_count,
        blockers=blockers,
        warnings=warnings,
    )

    if st.session_state.get("assign_mode") not in (MODE_SLOT, MODE_BOARD):
        st.session_state.assign_mode = MODE_SLOT

    pending_keys = st.session_state.pop("pending_photo_key_sync", None)
    if pending_keys:
        for idx in pending_keys:
            _sync_photo_pick_keys(layout_id, int(idx))

    work_preview, work_photos = st.columns([7, 5], gap="large")
    with work_photos:
        st.markdown('<span class="step-label">3 칸에 사진 넣기</span>', unsafe_allow_html=True)
        with st.expander("파일 이름으로 끌어다 놓기"):
            assign_mode = st.radio(
                "넣는 방법",
                [MODE_SLOT, MODE_BOARD],
                horizontal=True,
                key="assign_mode",
            )
        assign_mode = st.session_state.assign_mode
        board_names = names_for_board(photo_names, st.session_state.pages, page_index)
        if assign_mode == MODE_BOARD:
            elsewhere = [name for name in photo_names if name not in board_names]
            if elsewhere:
                st.caption("다른 쪽에 있는 사진: " + ", ".join(elsewhere))
            st.caption("파일 이름을 칸으로 끌어다 놓습니다.")
            slot_map = slot_map_for_board(board_names, st.session_state.pages, page_index)
            containers = board_from_map(board_names, slot_map, slot_ids)
            board_key = (
                f"board_{layout_id}_p{page_index}_{st.session_state.board_epoch}_"
                f"{_names_sig(board_names)}_{len(slot_ids)}"
            )
            sorted_board = _sort_items(containers, board_key)
            new_map, extras = map_from_board(sorted_board, slot_ids)
            st.session_state.pages = apply_board_to_page(
                st.session_state.pages, page_index, new_map
            )
            if extras:
                st.info(
                    "한 칸에는 사진 한 장만 들어갑니다. "
                    "나중에 놓은 장만 남겼습니다: "
                    + ", ".join(extras)
                )
                st.session_state.board_epoch = int(st.session_state.board_epoch) + 1
                st.rerun()
        else:
            loc = location_of(st.session_state.pages)
            slot_map = slot_map_for_board(photo_names, st.session_state.pages, page_index)
            photo_options = list_photo_choices(photo_names, UNASSIGNED)

            def _photo_label(name: str) -> str:
                if name == UNASSIGNED:
                    return UNASSIGNED
                if name in loc:
                    pg, slot = loc[name]
                    if pg != page_index:
                        return f"{name}  ({pg + 1}쪽 슬롯 {slot})"
                return name

            bytes_lookup = {p["name"]: p["bytes"] for p in photos}
            photo_by_slot: dict[int, str | None] = {}
            with st.expander("칸별로 목록에서 고르기"):
                for slot_id in slot_ids:
                    pick_key = f"{layout_id}_p{page_index}_slotphoto_{slot_id}"
                    current_name = name_in_slot(slot_map, slot_id)
                    if pick_key not in st.session_state or st.session_state[pick_key] not in photo_options:
                        st.session_state[pick_key] = current_name or UNASSIGNED
                    chosen_now = st.session_state[pick_key]
                    col_img, col_sel = st.columns([1, 4], vertical_alignment="center")
                    with col_img:
                        if chosen_now != UNASSIGNED and chosen_now in bytes_lookup:
                            st.image(bytes_lookup[chosen_now], width=72)
                        else:
                            st.caption("없음")
                    with col_sel:
                        selected_name = st.selectbox(
                            f"슬롯 {slot_id} 사진",
                            photo_options,
                            format_func=_photo_label,
                            key=pick_key,
                        )
                    photo_by_slot[slot_id] = None if selected_name == UNASSIGNED else selected_name
            if not photo_by_slot:
                for slot_id in slot_ids:
                    pick_key = f"{layout_id}_p{page_index}_slotphoto_{slot_id}"
                    current_name = name_in_slot(slot_map, slot_id)
                    if pick_key not in st.session_state or st.session_state[pick_key] not in photo_options:
                        st.session_state[pick_key] = current_name or UNASSIGNED
                    chosen_now = st.session_state[pick_key]
                    photo_by_slot[slot_id] = None if chosen_now == UNASSIGNED else chosen_now

            st.markdown("**넣을 칸을 고른 뒤, 사진을 누르세요.**")
            target_key = f"thumb_target_{layout_id}_{page_index}"
            if target_key not in st.session_state or st.session_state[target_key] not in slot_ids:
                st.session_state[target_key] = slot_ids[0]
            target_slot = st.radio(
                "넣을 칸",
                slot_ids,
                format_func=lambda item: f"슬롯 {item}",
                horizontal=True,
                key=target_key,
            )
            loc_thumbs = location_of(st.session_state.pages)
            thumb_cols = st.columns(2)
            clicked_name = None
            for index, photo in enumerate(photos):
                with thumb_cols[index % 2]:
                    st.image(photo["bytes"], width="stretch")
                    place = "아직 안 넣음"
                    if photo["name"] in loc_thumbs:
                        pg, slot = loc_thumbs[photo["name"]]
                        place = f"{pg + 1}쪽 · 슬롯 {slot}"
                    short = photo["name"] if len(photo["name"]) <= 18 else photo["name"][:16] + "…"
                    st.caption(f"{short}")
                    st.markdown(f'<div class="thumb-place">{place}</div>', unsafe_allow_html=True)
                    if st.button(
                        "이 칸에 넣기",
                        type="primary",
                        key=f"thumb_put_{layout_id}_p{page_index}_{index}",
                        use_container_width=True,
                    ):
                        clicked_name = photo["name"]
            if clicked_name:
                photo_by_slot[int(target_slot)] = clicked_name

            new_map = map_from_slot_photos(photo_by_slot, photo_names, slot_ids)
            st.session_state.pages = apply_board_to_page(
                st.session_state.pages, page_index, new_map
            )
            steal = False
            for slot_id in slot_ids:
                pick_key = f"{layout_id}_p{page_index}_slotphoto_{slot_id}"
                expected = name_in_slot(new_map, slot_id) or UNASSIGNED
                if pick_key not in st.session_state:
                    st.session_state[pick_key] = expected
                elif st.session_state[pick_key] != expected:
                    st.session_state[pick_key] = expected
                    steal = True
            if steal:
                st.info("한 사진은 한 칸에만 들어갑니다. 나중에 고른 칸만 남겼습니다.")
                st.rerun()

    current = _current_page()
    loc = location_of(st.session_state.pages)
    bytes_by_name = {p["name"]: p["bytes"] for p in photos}
    photos_by_slot = {
        slot_id: bytes_by_name[name]
        for name, slot_id in (current.get("slots") or {}).items()
        if name in bytes_by_name
    }
    with work_preview:
        st.markdown('<span class="step-label">4 미리보기 · 칸 옮기기</span>', unsafe_allow_html=True)
        _render_slot_editor(
            layout_id,
            base_layout,
            page_index=page_index,
            photos_by_slot=photos_by_slot,
            labels=current.get("labels") or {},
            text_values=current.get("texts") or {},
        )

    with st.expander("이 쪽 문구 (라벨 · 우측 표)", expanded=False):
        if page_index > 0:
            if st.button("이전 쪽 문구만 복사"):
                prev = st.session_state.pages[page_index - 1]
                copied = copy_page_wording(prev, current)
                st.session_state.pages[page_index] = copied
                for slot_id in slot_ids:
                    st.session_state[f"{layout_id}_p{page_index}_label_{slot_id}"] = (
                        copied.get("labels") or {}
                    ).get(slot_id, "")
                for field in fields_from_layout(layout):
                    st.session_state[f"{layout_id}_p{page_index}_text_{field['id']}"] = (
                        copied.get("texts") or {}
                    ).get(field["id"], "")
                st.rerun()
            st.caption("사진 위치는 그대로 두고 글만 가져옵니다.")

        st.markdown("**사진 아래 라벨**")
        label_cols = st.columns(len(slot_ids))
        labels = dict(current.get("labels") or {})
        for col, slot_id in zip(label_cols, slot_ids):
            with col:
                label_key = f"{layout_id}_p{page_index}_label_{slot_id}"
                if label_key not in st.session_state:
                    st.session_state[label_key] = labels.get(slot_id, "")
                labels[slot_id] = st.text_input(
                    f"슬롯 {slot_id}",
                    key=label_key,
                    placeholder="예: DTG SIMULATOR",
                )
        current["labels"] = labels

        st.markdown("**우측 표**")
        text_fields = fields_from_layout(layout)
        texts = dict(current.get("texts") or {})
        for field in text_fields:
            field_key = f"{layout_id}_p{page_index}_text_{field['id']}"
            if field_key not in st.session_state:
                st.session_state[field_key] = texts.get(field["id"], "")
            if field["widget"] == "text_area":
                typed = st.text_area(
                    field["label"],
                    key=field_key,
                    placeholder=field["placeholder"],
                    height=90,
                )
            else:
                typed = st.text_input(
                    field["label"],
                    key=field_key,
                    placeholder=field["placeholder"],
                )
            texts[field["id"]] = typed
        current["texts"] = texts
        if not text_fields:
            st.caption("이 양식에는 우측 표 칸이 없습니다.")

        with st.expander("라벨 초안 받기 (선택)"):
            if "gemini_consent" not in st.session_state:
                st.session_state.gemini_consent = False
            consent = st.checkbox(
                "사진을 Google로 보내 라벨 초안만 받습니다. 최종 문구는 직접 고칩니다.",
                key="gemini_consent",
            )
            can_gemini = gemini_available() and consent
            if st.button("라벨 초안 받기", disabled=not can_gemini):
                assigned = [
                    (name, bytes_by_name[name])
                    for name, _slot in (current.get("slots") or {}).items()
                    if name in bytes_by_name
                ]
                drafts = suggest_labels_with_gemini(assigned)
                if not drafts:
                    st.warning("초안을 받지 못했습니다. API 키와 네트워크를 확인하세요.")
                else:
                    for name, slot_id in (current.get("slots") or {}).items():
                        draft = drafts.get(name)
                        if not draft:
                            continue
                        st.session_state[f"{layout_id}_p{page_index}_label_{slot_id}"] = draft
                        current["labels"][slot_id] = draft
                    st.rerun()
            if not gemini_available():
                st.caption("Gemini 키가 없으면 꺼져 있습니다.")

    loc = location_of(st.session_state.pages)
    with st.expander("지정 요약 표"):
        rows = []
        for photo in photos:
            name = photo["name"]
            if name in loc:
                pg, slot = loc[name]
                page_labels_map = (st.session_state.pages[pg].get("labels") or {})
                rows.append(
                    {
                        "사진": name,
                        "페이지": pg + 1,
                        "슬롯": slot,
                        "라벨": page_labels_map.get(slot, ""),
                    }
                )
            else:
                rows.append(
                    {
                        "사진": name,
                        "페이지": "-",
                        "슬롯": "미지정",
                        "라벨": "",
                    }
                )
        st.dataframe(rows, hide_index=True, width="stretch")

    _render_history(skip_newest=bool(st.session_state.pptx_bytes))


if __name__ == "__main__":
    main()
