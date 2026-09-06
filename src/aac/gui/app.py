"""메인 윈도우."""
from __future__ import annotations

import sys

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStyle,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from aac.adb import AdbClient, Device
from aac.bluestacks import BlueStacksInstance
from aac.config import SETTINGS
from aac.gui.capture_view import CaptureView
from aac.gui.dashboard import Dashboard
from aac.gui.flow_editor import FlowEditor
from aac.gui.instances_panel import InstancesPanel
from aac.gui.template_panel import TemplatePanel
from aac.gui.workers import ScreenshotThread
from aac.runner import RunnerManager
from aac.vision.template import save_crop


class CapturePage(QWidget):
    """인스턴스 목록 + 라이브 스크린샷 + 좌표/템플릿 도구."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current: BlueStacksInstance | None = None
        self._shot: ScreenshotThread | None = None
        self._device: Device | None = None
        self._last_norm: tuple[float, float] | None = None
        self._last_region: tuple[float, float, float, float] | None = None
        self._last_frame: np.ndarray | None = None

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

        # 템플릿 저장 행
        self.tpl_name = QLineEdit()
        self.tpl_name.setPlaceholderText("템플릿 이름 (예: btn_auto_hunt)")
        self.save_tpl_btn = QPushButton("드래그한 영역 → 템플릿 저장")
        self.save_tpl_btn.setEnabled(False)
        self.save_tpl_btn.clicked.connect(self._save_template)
        tpl_row = QHBoxLayout()
        tpl_row.addWidget(self.tpl_name, 1)
        tpl_row.addWidget(self.save_tpl_btn)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setFixedHeight(110)

        center = QWidget()
        clay = QVBoxLayout(center)
        clay.setContentsMargins(4, 4, 4, 4)
        clay.addWidget(self.view, 1)
        clay.addLayout(ctl)
        clay.addLayout(tpl_row)
        clay.addWidget(QLabel("로그"))
        clay.addWidget(self.log)

        self.templates = TemplatePanel()
        self.templates.match_tested.connect(self._on_match_tested)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.instances)
        splitter.addWidget(center)
        splitter.addWidget(self.templates)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([330, 720, 230])

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
    def _set_frame(self, img: np.ndarray) -> None:
        self._last_frame = img
        self.view.set_frame(img)
        self.templates.set_frame(img)

    def _grab_once(self) -> None:
        if self._device is None:
            return
        img = self._device.screenshot()
        if img is not None:
            self._set_frame(img)
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
        self._shot.frame.connect(self._set_frame)
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
        self._last_region = (x, y, w, h)
        self.coord_lbl.setText(f"영역: {x:.4f},{y:.4f} {w:.4f}x{h:.4f}")
        self.save_tpl_btn.setEnabled(self._last_frame is not None)
        self._log(f"영역 선택 → ocr_region 파라미터: {x:.4f},{y:.4f},{w:.4f},{h:.4f}")

    def _save_template(self) -> None:
        if self._last_frame is None or self._last_region is None:
            return
        name = self.tpl_name.text().strip()
        if not name:
            name, ok = QInputDialog.getText(self, "템플릿 이름", "파일명:")
            if not ok or not name.strip():
                return
            name = name.strip()
        try:
            out = save_crop(self._last_frame, self._last_region, name)
        except ValueError as exc:
            QMessageBox.warning(self, "저장 실패", str(exc))
            return
        self.templates.refresh()
        self._log(f"템플릿 저장: {out.name}")

    def _on_match_tested(self, found: bool, cx: float, cy: float, score: float) -> None:
        self.view.show_marker(cx, cy, f"{score:.2f}", found)
        self._log(f"매칭 테스트: {'발견' if found else '미발견'} score={score:.3f} @({cx:.3f},{cy:.3f})")

    def shutdown(self) -> None:
        self._stop_live()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Astron Auto Controller")
        self.resize(1320, 800)

        self.runner = RunnerManager(self)
        self.runner.notify.connect(self._on_notify)

        self.capture_page = CapturePage()
        self.flow_page = FlowEditor()
        self.dashboard = Dashboard(self.runner)

        self.capture_page.instances.scan_finished.connect(self._on_scan_finished)

        tabs = QTabWidget()
        tabs.addTab(self.capture_page, "인스턴스 / 캡처")
        tabs.addTab(self.flow_page, "플로우")
        tabs.addTab(self.dashboard, "대시보드")
        self.setCentralWidget(tabs)

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.tray.setToolTip("Astron Auto Controller")
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

        self.dashboard.scheduler.start()
        self.statusBar().showMessage("준비됨")
        self.capture_page.instances.scan()

    def _on_scan_finished(self, instances: list) -> None:
        self.flow_page.set_instances(instances)
        self.dashboard.set_instances(instances)
        self.statusBar().showMessage(f"인스턴스 {len(instances)}개")

    def _on_notify(self, key: str, title: str, message: str, level: str) -> None:
        if not SETTINGS.notifications_enabled:
            return
        icon = {
            "error": QSystemTrayIcon.Critical,
            "warn": QSystemTrayIcon.Warning,
        }.get(level, QSystemTrayIcon.Information)
        st = self.runner.state(key)
        prefix = st.display_name or key
        self.tray.showMessage(f"[{prefix}] {title}", message, icon, 6000)

    def closeEvent(self, event) -> None:
        self.capture_page.shutdown()
        self.flow_page.shutdown()
        self.dashboard.shutdown()
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
