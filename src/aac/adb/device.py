"""단일 BlueStacks 인스턴스에 대한 입력/캡처 래퍼."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

import numpy as np

from aac.adb.client import AdbClient, AdbResult

_WM_SIZE_RE = re.compile(r"(\d+)x(\d+)")


@dataclass
class Device:
    serial: str  # 예: "127.0.0.1:55873"
    client: AdbClient
    _size: tuple[int, int] | None = None

    # --- 연결 -----------------------------------------------------------
    def connect(self) -> bool:
        res = self.client.connect(self.serial)
        return isinstance(res, AdbResult) and ("connected" in res.stdout or "already" in res.stdout)

    def is_online(self) -> bool:
        return self.serial in self.client.devices()

    # --- 화면 크기 -----------------------------------------------------
    @property
    def size(self) -> tuple[int, int]:
        if self._size is None:
            self._size = self._query_size()
        return self._size

    def _query_size(self) -> tuple[int, int]:
        res = self.client.run(["shell", "wm", "size"], serial=self.serial)
        if isinstance(res, AdbResult) and res.ok:
            # "Physical size: 1600x900" / "Override size: 900x1600"
            matches = _WM_SIZE_RE.findall(res.stdout)
            if matches:
                w, h = matches[-1]
                return int(w), int(h)
        return (1600, 900)

    def refresh_size(self) -> tuple[int, int]:
        self._size = self._query_size()
        return self._size

    # --- 좌표 변환 (정규화 0~1 -> 픽셀) --------------------------------
    def to_px(self, nx: float, ny: float) -> tuple[int, int]:
        w, h = self.size
        return round(nx * w), round(ny * h)

    # --- 입력 ---------------------------------------------------------
    def tap(self, x: float, y: float, *, normalized: bool = True) -> None:
        px, py = self.to_px(x, y) if normalized else (int(x), int(y))
        self.client.run(["shell", "input", "tap", str(px), str(py)], serial=self.serial)

    def swipe(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        duration_ms: int = 300,
        *,
        normalized: bool = True,
    ) -> None:
        if normalized:
            px1, py1 = self.to_px(x1, y1)
            px2, py2 = self.to_px(x2, y2)
        else:
            px1, py1, px2, py2 = map(int, (x1, y1, x2, y2))
        self.client.run(
            ["shell", "input", "swipe", str(px1), str(py1), str(px2), str(py2), str(duration_ms)],
            serial=self.serial,
        )

    def key(self, keycode: int | str) -> None:
        self.client.run(["shell", "input", "keyevent", str(keycode)], serial=self.serial)

    def text(self, value: str) -> None:
        escaped = value.replace(" ", "%s")
        self.client.run(["shell", "input", "text", escaped], serial=self.serial)

    def back(self) -> None:
        self.key(4)

    # --- 앱 제어 ----------------------------------------------------
    def launch_app(self, package: str, activity: str | None = None) -> None:
        if activity:
            comp = f"{package}/{activity}"
            self.client.run(["shell", "am", "start", "-n", comp], serial=self.serial, timeout=20)
        else:
            self.client.run(
                ["shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"],
                serial=self.serial,
                timeout=20,
            )

    def force_stop(self, package: str) -> None:
        self.client.run(["shell", "am", "force-stop", package], serial=self.serial)

    def current_app(self) -> str | None:
        res = self.client.run(
            ["shell", "dumpsys", "window", "displays"], serial=self.serial, timeout=10
        )
        if isinstance(res, AdbResult) and res.ok:
            m = re.search(r"mCurrentFocus=.*\s([\w.]+)/([\w.]+)", res.stdout)
            if m:
                return m.group(1)
        return None

    # --- 화면 캡처 -------------------------------------------------
    def screencap_png(self) -> bytes:
        data = self.client.run(["exec-out", "screencap", "-p"], serial=self.serial, binary=True)
        return data if isinstance(data, bytes) else b""

    def screenshot(self) -> np.ndarray | None:
        """BGR ndarray 반환. 실패 시 None."""
        import cv2

        raw = self.screencap_png()
        if not raw:
            return None
        arr = np.frombuffer(raw, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img

    # --- 편의 -----------------------------------------------------
    def wait(self, seconds: float) -> None:
        time.sleep(seconds)
