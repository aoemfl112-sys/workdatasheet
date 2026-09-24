"""실행 환경. NAS·클라우드에서는 이 PC 전용 열기 기능을 끈다."""

from __future__ import annotations

import os
from pathlib import Path

# nas_upload 폴더에만 들어 있는 표시 파일. 환경변수 없이 실행해도 서버 모드가 된다.
_SERVER_MARKER = Path(__file__).resolve().parent.parent / "SERVER_MODE"


def is_server_mode() -> bool:
    """NAS Docker / Streamlit Cloud / 수동 서버 실행이면 True."""
    flag = os.environ.get("WORKSHEET_SERVER", "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True

    # Streamlit Community Cloud
    runtime = os.environ.get("STREAMLIT_RUNTIME_ENV", "").strip().lower()
    if runtime in {"cloud", "streamlit_cloud"}:
        return True
    if os.environ.get("STREAMLIT_SHARING_MODE", "").strip():
        return True

    return _SERVER_MARKER.is_file()
