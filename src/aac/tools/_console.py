"""콘솔 출력을 UTF-8 로 강제 (Windows cp949 콘솔에서 이모지/한글 깨짐·크래시 방지)."""
from __future__ import annotations

import sys


def setup() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass
