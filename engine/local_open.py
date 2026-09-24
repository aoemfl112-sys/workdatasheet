"""생성한 PPT를 이 PC에서 저장하고 연다. 외부 서버로 올리지 않는다."""

from __future__ import annotations

import os
from pathlib import Path


def save_pptx_file(data: bytes, filename: str, folder: str | Path) -> Path:
    if not data:
        raise ValueError("저장할 PPT가 없습니다.")
    dest = Path(folder)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / filename
    path.write_bytes(data)
    return path


def open_local_file(path: str | Path) -> Path:
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"파일이 없습니다: {target.name}")
    os.startfile(str(target.resolve()))  # Windows 기본 앱으로 연다
    return target
