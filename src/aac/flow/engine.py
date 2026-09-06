"""플로우 실행 엔진 (동기, 백그라운드 스레드에서 구동).

- 스텝 사이/대기 중 StopToken 을 확인해 즉시 중단 가능.
- 스크린샷은 짧게 캐시해 연속 매칭 비용을 줄인다.
"""
from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

import numpy as np

from aac.adb import Device
from aac.config import CAPTURES_DIR, SETTINGS, TEMPLATES_DIR
from aac.flow.model import Flow, Step
from aac.flow.registry import get_step_spec
from aac.vision.template import find_template

LogFn = Callable[[str], None]

# Android KEYCODE 별칭
_KEYCODES = {
    "BACK": 4, "HOME": 3, "ENTER": 66, "MENU": 82, "APP_SWITCH": 187,
    "ESCAPE": 111, "DEL": 67, "TAB": 61, "SPACE": 62,
    "DPAD_UP": 19, "DPAD_DOWN": 20, "DPAD_LEFT": 21, "DPAD_RIGHT": 22,
}


class StopToken:
    """협조적 취소 토큰."""

    def __init__(self):
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    @property
    def stopped(self) -> bool:
        return self._stopped

    def sleep(self, seconds: float) -> None:
        """중단 신호를 확인하며 잘게 나눠 잔다."""
        end = time.monotonic() + max(0.0, seconds)
        while not self._stopped and time.monotonic() < end:
            time.sleep(min(0.05, end - time.monotonic()))


class Outcome(Enum):
    CONTINUE = auto()
    BREAK = auto()  # 루프 탈출
    STOP = auto()   # 플로우 전체 중단 (취소/치명적 실패)


@dataclass
class RunContext:
    device: Device
    log: LogFn
    stop: StopToken
    templates_dir: Path = TEMPLATES_DIR
    threshold: float = field(default_factory=lambda: SETTINGS.template_match_threshold)
    vars: dict[str, object] = field(default_factory=dict)
    depth: int = 0
    _frame: np.ndarray | None = None
    _frame_ts: float = 0.0
    frame_ttl: float = 0.4  # 초

    def screenshot(self, fresh: bool = False) -> np.ndarray | None:
        now = time.monotonic()
        if not fresh and self._frame is not None and (now - self._frame_ts) < self.frame_ttl:
            return self._frame
        img = self.device.screenshot()
        if img is not None:
            self._frame = img
            self._frame_ts = now
        return img

    def invalidate_frame(self) -> None:
        self._frame = None


class FlowEngine:
    def __init__(self, device: Device, log: LogFn, stop: StopToken | None = None):
        self.ctx = RunContext(device=device, log=log, stop=stop or StopToken())
        self._call_stack: list[str] = []

    # --- 진입점 -------------------------------------------------
    def run(self, flow: Flow) -> bool:
        self._log(f"=== 플로우 시작: {flow.name} ===")
        t0 = time.monotonic()
        try:
            outcome = self._exec_steps(flow.steps)
        except Exception as exc:  # noqa: BLE001
            self._log(f"[예외] {exc!r}")
            return False
        dt = time.monotonic() - t0
        if self.ctx.stop.stopped:
            self._log(f"=== 중단됨 ({dt:.1f}s) ===")
            return False
        ok = outcome != Outcome.STOP
        self._log(f"=== 플로우 종료: {'성공' if ok else '실패'} ({dt:.1f}s) ===")
        return ok

    # --- 블록 실행 ---------------------------------------------
    def _exec_steps(self, steps: list[Step]) -> Outcome:
        for step in steps:
            if self.ctx.stop.stopped:
                return Outcome.STOP
            if not step.enabled:
                continue
            outcome = self._exec_step(step)
            if outcome != Outcome.CONTINUE:
                return outcome
        return Outcome.CONTINUE

    def _exec_step(self, step: Step) -> Outcome:
        spec = get_step_spec(step.type)
        params = {**(spec.default_params() if spec else {}), **step.params}
        handler = _EXECUTORS.get(step.type)
        if handler is None:
            self._log(f"[무시] 알 수 없는 스텝: {step.type}")
            return Outcome.CONTINUE
        label = spec.summary(params) if spec else step.type
        self._log(f"{'  ' * self.ctx.depth}▶ {label}")
        return handler(self, step, params)

    # --- 유틸 -------------------------------------------------
    def _log(self, msg: str) -> None:
        self.ctx.log(msg)

    def _match(self, template: str, threshold: float):
        img = self.ctx.screenshot()
        if img is None:
            return None
        try:
            return find_template(img, template, threshold=threshold)
        except FileNotFoundError as exc:
            self._log(f"[템플릿 없음] {exc}")
            return None


# ============================================================
# 스텝 실행기
# ============================================================
def _tap(engine: FlowEngine, step: Step, p: dict) -> Outcome:
    ctx = engine.ctx
    tpl = (p.get("template") or "").strip()
    if tpl:
        m = engine._match(tpl, float(p.get("threshold", ctx.threshold)))
        if not m or not m.found:
            engine._log(f"  템플릿 '{tpl}' 못 찾음 → 탭 생략")
            return Outcome.CONTINUE
        x, y = m.cx, m.cy
    else:
        x, y = float(p["x"]), float(p["y"])
    j = float(p.get("jitter", 0.0) or 0.0)
    if j:
        x += random.uniform(-j, j)
        y += random.uniform(-j, j)
    x = min(max(x, 0.0), 1.0)
    y = min(max(y, 0.0), 1.0)
    ctx.device.tap(x, y)
    ctx.invalidate_frame()
    ctx.stop.sleep(int(p.get("after_ms", 0)) / 1000)
    return Outcome.CONTINUE


def _tap_template(engine: FlowEngine, step: Step, p: dict) -> Outcome:
    ctx = engine.ctx
    tpl = (p.get("template") or "").strip()
    thr = float(p.get("threshold", ctx.threshold))
    timeout = float(p.get("timeout", 5.0))
    poll = int(p.get("poll_ms", 700)) / 1000
    end = time.monotonic() + timeout
    while not ctx.stop.stopped:
        ctx.invalidate_frame()
        m = engine._match(tpl, thr)
        if m and m.found:
            ctx.device.tap(m.cx, m.cy)
            ctx.invalidate_frame()
            ctx.stop.sleep(int(p.get("after_ms", 0)) / 1000)
            return Outcome.CONTINUE
        if time.monotonic() >= end:
            break
        ctx.stop.sleep(poll)
    if ctx.stop.stopped:
        return Outcome.STOP
    engine._log(f"  [타임아웃] 템플릿 '{tpl}'")
    return Outcome.STOP if p.get("required", True) else Outcome.CONTINUE


def _swipe(engine: FlowEngine, step: Step, p: dict) -> Outcome:
    engine.ctx.device.swipe(
        float(p["x1"]), float(p["y1"]), float(p["x2"]), float(p["y2"]),
        int(p.get("duration_ms", 400)),
    )
    engine.ctx.invalidate_frame()
    return Outcome.CONTINUE


def _key(engine: FlowEngine, step: Step, p: dict) -> Outcome:
    kc = p.get("keycode", "BACK")
    code = _KEYCODES.get(str(kc).upper(), kc)
    engine.ctx.device.key(code)
    engine.ctx.invalidate_frame()
    return Outcome.CONTINUE


def _text(engine: FlowEngine, step: Step, p: dict) -> Outcome:
    engine.ctx.device.text(str(p.get("value", "")))
    return Outcome.CONTINUE


def _wait(engine: FlowEngine, step: Step, p: dict) -> Outcome:
    engine.ctx.stop.sleep(float(p.get("seconds", 1.0)))
    return Outcome.STOP if engine.ctx.stop.stopped else Outcome.CONTINUE


def _wait_template(engine: FlowEngine, step: Step, p: dict) -> Outcome:
    ctx = engine.ctx
    tpl = (p.get("template") or "").strip()
    thr = float(p.get("threshold", ctx.threshold))
    timeout = float(p.get("timeout", 15.0))
    poll = int(p.get("poll_ms", 800)) / 1000
    end = time.monotonic() + timeout
    while not ctx.stop.stopped:
        ctx.invalidate_frame()
        m = engine._match(tpl, thr)
        if m and m.found:
            return Outcome.CONTINUE
        if time.monotonic() >= end:
            break
        ctx.stop.sleep(poll)
    if ctx.stop.stopped:
        return Outcome.STOP
    engine._log(f"  [타임아웃] 템플릿 대기 '{tpl}'")
    return Outcome.STOP if p.get("required", True) else Outcome.CONTINUE


def _if_template(engine: FlowEngine, step: Step, p: dict) -> Outcome:
    ctx = engine.ctx
    tpl = (p.get("template") or "").strip()
    thr = float(p.get("threshold", ctx.threshold))
    ctx.invalidate_frame()
    m = engine._match(tpl, thr)
    present = bool(m and m.found)
    if p.get("negate", False):
        present = not present
    engine._log(f"    조건 = {present}")
    ctx.depth += 1
    try:
        if present:
            return engine._exec_steps(step.children)
        return engine._exec_steps(step.else_children)
    finally:
        ctx.depth -= 1


def _loop(engine: FlowEngine, step: Step, p: dict) -> Outcome:
    ctx = engine.ctx
    count = int(p.get("count", 1))
    ctx.depth += 1
    try:
        for i in range(count):
            if ctx.stop.stopped:
                return Outcome.STOP
            ctx.vars["_i"] = i
            out = engine._exec_steps(step.children)
            if out == Outcome.BREAK:
                break
            if out == Outcome.STOP:
                return Outcome.STOP
    finally:
        ctx.depth -= 1
    return Outcome.CONTINUE


def _repeat_until_template(engine: FlowEngine, step: Step, p: dict) -> Outcome:
    ctx = engine.ctx
    tpl = (p.get("template") or "").strip()
    thr = float(p.get("threshold", ctx.threshold))
    max_it = int(p.get("max_iterations", 20))
    iter_wait = int(p.get("iter_wait_ms", 1000)) / 1000
    ctx.depth += 1
    try:
        for i in range(max_it):
            if ctx.stop.stopped:
                return Outcome.STOP
            ctx.invalidate_frame()
            m = engine._match(tpl, thr)
            if m and m.found:
                engine._log(f"    종료 템플릿 발견 (반복 {i})")
                return Outcome.CONTINUE
            out = engine._exec_steps(step.children)
            if out == Outcome.STOP:
                return Outcome.STOP
            if out == Outcome.BREAK:
                return Outcome.CONTINUE
            ctx.stop.sleep(iter_wait)
        engine._log(f"    [최대 반복 도달] '{tpl}' 미발견")
    finally:
        ctx.depth -= 1
    return Outcome.CONTINUE


def _call_flow(engine: FlowEngine, step: Step, p: dict) -> Outcome:
    name = (p.get("flow") or "").strip()
    if not name:
        return Outcome.CONTINUE
    if name in engine._call_stack:
        engine._log(f"  [순환 호출 차단] {name}")
        return Outcome.CONTINUE
    try:
        sub = Flow.load_by_name(name)
    except (FileNotFoundError, ValueError) as exc:
        engine._log(f"  [플로우 로드 실패] {name}: {exc}")
        return Outcome.STOP
    engine._call_stack.append(name)
    engine.ctx.depth += 1
    try:
        return engine._exec_steps(sub.steps)
    finally:
        engine.ctx.depth -= 1
        engine._call_stack.pop()


def _launch_app(engine: FlowEngine, step: Step, p: dict) -> Outcome:
    pkg = (p.get("package") or "").strip()
    if not pkg:
        return Outcome.CONTINUE
    engine.ctx.device.launch_app(pkg, (p.get("activity") or "").strip() or None)
    engine.ctx.invalidate_frame()
    engine.ctx.stop.sleep(float(p.get("wait_s", 8.0)))
    return Outcome.STOP if engine.ctx.stop.stopped else Outcome.CONTINUE


def _stop_app(engine: FlowEngine, step: Step, p: dict) -> Outcome:
    pkg = (p.get("package") or "").strip()
    if pkg:
        engine.ctx.device.force_stop(pkg)
    return Outcome.CONTINUE


def _ocr_region(engine: FlowEngine, step: Step, p: dict) -> Outcome:
    ctx = engine.ctx
    img = ctx.screenshot(fresh=True)
    if img is None:
        return Outcome.CONTINUE
    try:
        rx, ry, rw, rh = (float(v) for v in str(p.get("region", "0,0,0.2,0.1")).split(","))
    except ValueError:
        engine._log("  [OCR] region 형식 오류 (x,y,w,h)")
        return Outcome.CONTINUE
    h, w = img.shape[:2]
    crop = img[int(ry * h):int((ry + rh) * h), int(rx * w):int((rx + rw) * w)]
    try:
        from aac.vision.ocr import read_text
    except Exception:  # noqa: BLE001
        engine._log("  [OCR] rapidocr 미설치 (pip install -e \".[ocr]\")")
        return Outcome.CONTINUE
    text = read_text(crop, digits_only=bool(p.get("digits_only", True)))
    var = (p.get("var") or "ocr").strip()
    ctx.vars[var] = text
    engine._log(f"  OCR ${var} = '{text}'")
    return Outcome.CONTINUE


def _screenshot(engine: FlowEngine, step: Step, p: dict) -> Outcome:
    img = engine.ctx.screenshot(fresh=True)
    if img is None:
        return Outcome.CONTINUE
    import cv2

    label = (p.get("label") or "shot").strip()
    out = CAPTURES_DIR / f"{label}_{int(time.time())}.png"
    cv2.imwrite(str(out), img)
    engine._log(f"  저장: {out.name}")
    return Outcome.CONTINUE


def _log_step(engine: FlowEngine, step: Step, p: dict) -> Outcome:
    engine._log(f"  {p.get('message', '')}")
    return Outcome.CONTINUE


_EXECUTORS: dict[str, Callable[[FlowEngine, Step, dict], Outcome]] = {
    "tap": _tap,
    "tap_template": _tap_template,
    "swipe": _swipe,
    "key": _key,
    "text": _text,
    "wait": _wait,
    "wait_template": _wait_template,
    "if_template": _if_template,
    "loop": _loop,
    "repeat_until_template": _repeat_until_template,
    "call_flow": _call_flow,
    "launch_app": _launch_app,
    "stop_app": _stop_app,
    "ocr_region": _ocr_region,
    "screenshot": _screenshot,
    "log": _log_step,
}
