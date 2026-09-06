"""템플릿(버튼/아이콘 크롭) 매칭. 멀티스케일 + 정규화 좌표 반환."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from aac.config import SETTINGS, TEMPLATES_DIR


@dataclass
class MatchResult:
    found: bool
    score: float
    # 매칭 중심의 정규화 좌표 (0~1)
    cx: float = 0.0
    cy: float = 0.0
    # 픽셀 바운딩 박스
    box: tuple[int, int, int, int] = (0, 0, 0, 0)


def list_templates() -> list[str]:
    return sorted(p.name for p in TEMPLATES_DIR.glob("*.png"))


def save_crop(
    frame_bgr: np.ndarray,
    region_norm: tuple[float, float, float, float],
    name: str,
) -> Path:
    """정규화 영역(x, y, w, h)을 잘라 templates/<name>.png 로 저장."""
    h, w = frame_bgr.shape[:2]
    rx, ry, rw, rh = region_norm
    x1 = max(0, int(rx * w))
    y1 = max(0, int(ry * h))
    x2 = min(w, int((rx + rw) * w))
    y2 = min(h, int((ry + rh) * h))
    if x2 - x1 < 4 or y2 - y1 < 4:
        raise ValueError("영역이 너무 작습니다")
    crop = frame_bgr[y1:y2, x1:x2]
    safe = "".join(c for c in name if c.isalnum() or c in " _-()").strip() or "template"
    if not safe.endswith(".png"):
        safe += ".png"
    out = TEMPLATES_DIR / safe
    cv2.imwrite(str(out), crop)
    return out


def load_template(name_or_path: str) -> np.ndarray:
    p = Path(name_or_path)
    if not p.is_absolute() and not p.exists():
        p = TEMPLATES_DIR / name_or_path
    if p.suffix == "":
        p = p.with_suffix(".png")
    img = cv2.imread(str(p), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"템플릿을 찾을 수 없음: {p}")
    return img


def find_template(
    screen: np.ndarray,
    template: np.ndarray | str,
    *,
    threshold: float | None = None,
    scales: tuple[float, ...] = (1.0, 0.9, 1.1, 0.8, 1.2, 0.75, 1.35),
) -> MatchResult:
    if isinstance(template, str):
        template = load_template(template)
    thr = SETTINGS.template_match_threshold if threshold is None else threshold

    sh, sw = screen.shape[:2]
    best: MatchResult = MatchResult(found=False, score=0.0)

    th0, tw0 = template.shape[:2]
    for scale in scales:
        tw, th = int(tw0 * scale), int(th0 * scale)
        if tw < 8 or th < 8 or tw > sw or th > sh:
            continue
        resized = cv2.resize(template, (tw, th), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(screen, resized, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val > best.score:
            x, y = max_loc
            cx = (x + tw / 2) / sw
            cy = (y + th / 2) / sh
            best = MatchResult(
                found=max_val >= thr,
                score=float(max_val),
                cx=float(cx),
                cy=float(cy),
                box=(x, y, tw, th),
            )
        if best.found and best.score > 0.97:
            break
    return best
