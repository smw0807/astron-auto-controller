"""FlowEngine 을 QThread 로 감싼 실행기."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from aac.adb import AdbClient, Device
from aac.flow import Flow, FlowEngine, StopToken


class RunnerThread(QThread):
    log = Signal(str)
    iteration = Signal(int)       # 반복 시작 시 회차(1-base)
    notify = Signal(str, str, str)  # title, message, level
    finished_ok = Signal(bool)

    def __init__(self, serial: str, flow: Flow, repeat: int = 1,
                 interval_s: float = 15.0, parent=None):
        super().__init__(parent)
        self._serial = serial
        self._flow = flow
        self._repeat = repeat          # < 0 이면 무한
        self._interval = interval_s
        self._stop = StopToken()

    def stop(self) -> None:
        self._stop.stop()

    @property
    def stopping(self) -> bool:
        return self._stop.stopped

    def run(self) -> None:
        dev = Device(serial=self._serial, client=AdbClient())
        dev.connect()
        ok = True
        n = 0
        while not self._stop.stopped and (self._repeat < 0 or n < self._repeat):
            n += 1
            self.iteration.emit(n)
            if self._repeat != 1:
                tag = "무한" if self._repeat < 0 else f"{n}/{self._repeat}"
                self.log.emit(f"─── 반복 {tag} ───")
            ok = FlowEngine(
                dev, self.log.emit, self._stop,
                notify=lambda t, m, lv: self.notify.emit(t, m, lv),
            ).run(self._flow)
            if self._stop.stopped:
                break
            if self._repeat < 0 or n < self._repeat:
                self._stop.sleep(self._interval)
        self.finished_ok.emit(ok)
