"""간단한 스케줄러: 활성 시간대 / 주기 재시작 / 일일 재시작.

30초마다 tick 하며 정책을 RunnerManager 에 적용한다.
"""
from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

from aac.config import SETTINGS
from aac.runner.manager import RunnerManager

_TICK_MS = 30_000


def _parse_hhmm(s: str) -> tuple[int, int] | None:
    try:
        h, m = s.strip().split(":")
        return int(h), int(m)
    except (ValueError, AttributeError):
        return None


def _in_window(now: datetime, window: str) -> bool | None:
    """"HH:MM-HH:MM" 안에 있는지. 자정 넘김 지원. 형식 오류면 None."""
    try:
        a, b = window.split("-")
    except ValueError:
        return None
    pa, pb = _parse_hhmm(a), _parse_hhmm(b)
    if not pa or not pb:
        return None
    cur = now.hour * 60 + now.minute
    start = pa[0] * 60 + pa[1]
    end = pb[0] * 60 + pb[1]
    if start <= end:
        return start <= cur < end
    return cur >= start or cur < end  # 자정 넘김


class Scheduler(QObject):
    log = Signal(str)

    def __init__(self, manager: RunnerManager, parent=None):
        super().__init__(parent)
        self.mgr = manager
        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self.tick)
        self._last_periodic = time.monotonic()
        self._last_daily_date = None

    def start(self) -> None:
        self._timer.start()
        self.tick()

    def stop(self) -> None:
        self._timer.stop()

    # --- 정책 적용 -------------------------------------------
    def tick(self) -> None:
        if not SETTINGS.schedule_enabled:
            return
        now = datetime.now()  # noqa: DTZ005 — 로컬 벽시계 기준

        # 1) 활성 시간대
        if SETTINGS.active_hours.strip():
            inside = _in_window(now, SETTINGS.active_hours)
            if inside is False:
                if any(self.mgr.is_running(s.key) for s in self.mgr.all_states()):
                    self.log.emit(f"[스케줄] 활성 시간대 아님 → 전체 정지 ({SETTINGS.active_hours})")
                    self.mgr.stop_all()
                return  # 시간대 밖이면 나머지 정책 스킵
            if inside is True:
                started = [
                    s.key for s in self.mgr.all_states()
                    if s.flow_name and s.online and not self.mgr.is_running(s.key)
                ]
                if started:
                    self.log.emit(f"[스케줄] 활성 시간대 → 시작 {', '.join(started)}")
                    for k in started:
                        self.mgr.start(k)

        # 2) 일일 재시작 (지정 시각부터 5분 이내, 하루 1회)
        drt = _parse_hhmm(SETTINGS.daily_restart_time)
        cur_min = now.hour * 60 + now.minute
        if (
            drt
            and self._last_daily_date != now.date()
            and 0 <= cur_min - (drt[0] * 60 + drt[1]) < 5
        ):
            self._last_daily_date = now.date()
            self.log.emit(f"[스케줄] 일일 재시작 {SETTINGS.daily_restart_time}")
            self._restart_running()

        # 3) 주기 재시작
        if (
            SETTINGS.periodic_restart_min > 0
            and time.monotonic() - self._last_periodic >= SETTINGS.periodic_restart_min * 60
        ):
            self._last_periodic = time.monotonic()
            self.log.emit(f"[스케줄] 주기 재시작 ({SETTINGS.periodic_restart_min}분)")
            self._restart_running()

    def _restart_running(self) -> None:
        running = [s.key for s in self.mgr.all_states() if self.mgr.is_running(s.key)]
        self.mgr.stop_all()
        QTimer.singleShot(8000, lambda: [self.mgr.start(k) for k in running])
