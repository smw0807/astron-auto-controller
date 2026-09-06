"""백그라운드 작업용 QThread 래퍼."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QThread, Signal

from aac.adb import AdbClient, Device
from aac.bluestacks import scan_instances


class ScanWorker(QThread):
    done = Signal(list)  # list[BlueStacksInstance]
    failed = Signal(str)

    def run(self) -> None:
        try:
            self.done.emit(scan_instances())
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(repr(exc))


class ScreenshotThread(QThread):
    """단일 인스턴스의 스크린샷을 주기적으로 찍어 프레임을 방출."""

    frame = Signal(object)  # np.ndarray (BGR)
    error = Signal(str)

    def __init__(self, serial: str, interval_ms: int = 1000, parent=None):
        super().__init__(parent)
        self._serial = serial
        self._interval_ms = max(200, interval_ms)
        self._stop = False
        self._device: Device | None = None

    def set_interval(self, ms: int) -> None:
        self._interval_ms = max(200, ms)

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        self._device = Device(serial=self._serial, client=AdbClient())
        self._device.connect()
        while not self._stop:
            t0 = self._elapsed_ms()
            try:
                img = self._device.screenshot()
                if img is not None:
                    self.frame.emit(img)
                else:
                    self.error.emit("스크린샷 없음")
            except Exception as exc:  # noqa: BLE001
                self.error.emit(repr(exc))
            spent = self._elapsed_ms() - t0
            wait = max(0, self._interval_ms - spent)
            # 잘게 쪼개 sleep 하며 중단 확인
            slept = 0
            while slept < wait and not self._stop:
                self.msleep(min(50, wait - slept))
                slept += 50

    @staticmethod
    def _elapsed_ms() -> int:
        import time

        return int(time.monotonic() * 1000)


def grab_once(serial: str) -> np.ndarray | None:
    dev = Device(serial=serial, client=AdbClient())
    dev.connect()
    return dev.screenshot()
