"""메인 윈도우."""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from aac.adb import AdbClient, Device
from aac.bluestacks import BlueStacksInstance
from aac.gui.capture_view import CaptureView
from aac.gui.instances_panel import InstancesPanel
from aac.gui.workers import ScreenshotThread


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Astron Auto Controller")
        self.resize(1180, 720)

        self._current: BlueStacksInstance | None = None
        self._shot: ScreenshotThread | None = None
        self._device: Device | None = None

        # --- 좌: 인스턴스 패널 ---
        self.instances = InstancesPanel()
        self.instances.instance_selected.connect(self._on_instance_selected)

        # --- 우: 캡처 + 컨트롤 ---
        self.view = CaptureView()
        self.view.clicked.connect(self._on_view_clicked)
        self.view.region_selected.connect(self._on_region_selected)

        self.live_chk = QCheckBox("라이브")
        self.live_chk.toggled.connect(self._toggle_live)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(200, 10000)
        self.interval_spin.setSingleStep(100)
        self.interval_spin.setValue(1000)
        self.interval_spin.setSuffix(" ms")
        self.interval_spin.valueChanged.connect(self._on_interval_changed)
        self.refresh_btn = QPushButton("1회 캡처")
        self.refresh_btn.clicked.connect(self._grab_once)

        self.coord_lbl = QLabel("좌표: -")
        self.coord_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.tap_btn = QPushButton("이 좌표 탭")
        self.tap_btn.setEnabled(False)
        self.tap_btn.clicked.connect(self._tap_last)
        self._last_norm: tuple[float, float] | None = None

        ctl = QHBoxLayout()
        ctl.addWidget(self.live_chk)
        ctl.addWidget(QLabel("주기"))
        ctl.addWidget(self.interval_spin)
        ctl.addWidget(self.refresh_btn)
        ctl.addStretch(1)
        ctl.addWidget(self.coord_lbl)
        ctl.addWidget(self.tap_btn)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setFixedHeight(120)

        right = QWidget()
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(4, 4, 4, 4)
        rlay.addWidget(self.view, 1)
        rlay.addLayout(ctl)
        rlay.addWidget(QLabel("로그"))
        rlay.addWidget(self.log)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.instances)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 800])
        self.setCentralWidget(splitter)

        self.statusBar().showMessage("준비됨 — [스캔] 을 눌러 인스턴스를 조회하세요")
        self.instances.scan()

    # --- 로그 ------------------------------------------------------
    def _log(self, msg: str) -> None:
        self.log.appendPlainText(msg)

    # --- 인스턴스 선택 --------------------------------------------
    def _on_instance_selected(self, inst: BlueStacksInstance | None) -> None:
        self._stop_live()
        self._current = inst
        self._device = None
        if inst is None or not inst.online or not inst.serial:
            self.view.clear_frame()
            self.statusBar().showMessage("온라인 인스턴스가 아닙니다")
            return
        self._device = Device(serial=inst.serial, client=AdbClient())
        self._device.connect()
        self.statusBar().showMessage(
            f"{inst.label}  serial={inst.serial}  size={self._device.size}"
        )
        self._log(f"선택: {inst.label} ({inst.serial})")
        self._grab_once()

    # --- 캡처 ------------------------------------------------------
    def _grab_once(self) -> None:
        if self._device is None:
            return
        img = self._device.screenshot()
        if img is not None:
            self.view.set_frame(img)
        else:
            self._log("스크린샷 실패")

    def _toggle_live(self, on: bool) -> None:
        if on:
            self._start_live()
        else:
            self._stop_live()

    def _start_live(self) -> None:
        if self._current is None or not self._current.serial:
            self.live_chk.setChecked(False)
            return
        self._stop_live()
        self._shot = ScreenshotThread(self._current.serial, self.interval_spin.value())
        self._shot.frame.connect(self.view.set_frame)
        self._shot.error.connect(self._log)
        self._shot.start()
        self._log("라이브 시작")

    def _stop_live(self) -> None:
        if self._shot is not None:
            self._shot.stop()
            self._shot.wait(2000)
            self._shot = None

    def _on_interval_changed(self, ms: int) -> None:
        if self._shot is not None:
            self._shot.set_interval(ms)

    # --- 좌표 / 탭 -----------------------------------------------
    def _on_view_clicked(self, nx: float, ny: float) -> None:
        self._last_norm = (nx, ny)
        px = py = None
        if self._device is not None:
            px, py = self._device.to_px(nx, ny)
        self.coord_lbl.setText(
            f"좌표: n=({nx:.4f}, {ny:.4f})" + (f"  px=({px}, {py})" if px is not None else "")
        )
        self.tap_btn.setEnabled(self._device is not None)

    def _tap_last(self) -> None:
        if self._device is None or self._last_norm is None:
            return
        self._device.tap(*self._last_norm)
        self._log(f"탭 {self._last_norm} -> px {self._device.to_px(*self._last_norm)}")

    def _on_region_selected(self, x: float, y: float, w: float, h: float) -> None:
        self.coord_lbl.setText(f"영역: x={x:.4f} y={y:.4f} w={w:.4f} h={h:.4f}")
        self._log(f"영역 선택 (템플릿 크롭 예정): {x:.4f},{y:.4f} {w:.4f}x{h:.4f}")

    # --- 종료 -----------------------------------------------------
    def closeEvent(self, event) -> None:
        self._stop_live()
        super().closeEvent(event)


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
