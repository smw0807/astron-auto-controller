"""OCR 래퍼 (RapidOCR). 선택 의존성 — 미설치 시 ImportError."""
from __future__ import annotations

import re
import threading

import numpy as np

_engine = None
_lock = threading.Lock()


def _get_engine():
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                from rapidocr_onnxruntime import RapidOCR

                _engine = RapidOCR()
    return _engine


def read_text(image_bgr: np.ndarray, *, digits_only: bool = False) -> str:
    if image_bgr is None or image_bgr.size == 0:
        return ""
    engine = _get_engine()
    result, _ = engine(image_bgr)
    if not result:
        return ""
    text = " ".join(item[1] for item in result).strip()
    if digits_only:
        digits = re.sub(r"[^0-9]", "", text)
        return digits
    return text


def read_int(image_bgr: np.ndarray, default: int = 0) -> int:
    s = read_text(image_bgr, digits_only=True)
    try:
        return int(s)
    except ValueError:
        return default
