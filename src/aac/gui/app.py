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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from aac.adb import AdbClient, Device
from aac.bluestacks import BlueStacksInstance
from aac.gui.capture_view import CaptureView
from aac.gui.flow_editor import FlowEditor
from aac.gui.instances_panel import InstancesPanel
from aac.gui.workers import ScreenshotThread


class CapturePage(QWidget):
    """인스턴스 목록 + 라이브 스크린샷 + 좌표 도구."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current: BlueStacksInstance | None = None
        self._shot: ScreenshotThread | None = None
        self._device: Device | None = None
        self._last_norm: tuple[float, float] | None = None

        self.instances = InstancesPanel()
        self.instances.instance_selected.connect(self._on_instance_selected)

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
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 800])

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(splitter)

    # --- 로그 ---
    def _log(self, msg: str) -> None:
        self.log.appendPlainText(msg)

    # --- 선택 ---
    def _on_instance_selected(self, inst: BlueStacksInstance | None) -> None:
        self._stop_live()
        self._current = inst
        self._device = None
        if inst is None or not inst.online or not inst.serial:
            self.view.clear_frame()
            return
        self._device = Device(serial=inst.serial, client=AdbClient())
        self._device.connect()
        self._log(f"선택: {inst.label} ({inst.serial}) size={self._device.size}")
        self._grab_once()

    # --- 캡처 ---
    def _grab_once(self) -> None:
        if self._device is None:
            return
        img = self._device.screenshot()
        if img is not None:
            self.view.set_frame(img)
        else:
            self._log("스크린샷 실패")

    def _toggle_live(self, on: bool) -> None:
        self._start_live() if on else self._stop_live()

    def _start_live(self) -> None:
        if self._current is None or not self._current.serial:
            self.live_chk.setChecked(False)
            return
        self._stop_live()
        self._shot = ScreenshotThread(self._current.serial, self.interval_spin.value())
        self._shot.frame.connect(self.view.set_frame)
        self._shot.error.connect(self._log)
        self._shot.start()

    def _stop_live(self) -> None:
        if self._shot is not None:
            self._shot.stop()
            self._shot.wait(2000)
            self._shot = None

    def _on_interval_changed(self, ms: int) -> None:
        if self._shot is not None:
            self._shot.set_interval(ms)

    # --- 좌표/탭 ---
    def _on_view_clicked(self, nx: float, ny: float) -> None:
        self._last_norm = (nx, ny)
        px = None
        if self._device is not None:
            px = self._device.to_px(nx, ny)
        self.coord_lbl.setText(
            f"좌표: n=({nx:.4f}, {ny:.4f})" + (f"  px={px}" if px else "")
        )
        self.tap_btn.setEnabled(self._device is not None)

    def _tap_last(self) -> None:
        if self._device is None or self._last_norm is None:
            return
        self._device.tap(*self._last_norm)
        self._log(f"탭 {self._last_norm} -> px {self._device.to_px(*self._last_norm)}")

    def _on_region_selected(self, x: float, y: float, w: float, h: float) -> None:
        self.coord_lbl.setText(f"영역: {x:.4f},{y:.4f} {w:.4f}x{h:.4f}")
        self._log(f"영역: region 파라미터에 붙여넣기 → {x:.4f},{y:.4f},{w:.4f},{h:.4f}")

    def shutdown(self) -> None:
        self._stop_live()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Astron Auto Controller")
        self.resize(1240, 760)

        self.capture_page = CapturePage()
        self.flow_page = FlowEditor()

        # 스캔 결과를 플로우 탭의 대상 인스턴스 목록에 반영
        self.capture_page.instances.scan_finished.connect(self.flow_page.set_instances)

        tabs = QTabWidget()
        tabs.addTab(self.capture_page, "인스턴스 / 캡처")
        tabs.addTab(self.flow_page, "플로우")
        self.setCentralWidget(tabs)

        self.statusBar().showMessage("준비됨")
        self.capture_page.instances.scan()

    def closeEvent(self, event) -> None:
        self.capture_page.shutdown()
        self.flow_page.shutdown()
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
