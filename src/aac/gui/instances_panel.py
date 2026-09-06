"""인스턴스 목록 패널."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aac.bluestacks import BlueStacksInstance
from aac.gui.workers import ScanWorker

_COLS = ["별명", "key", "실행", "연결", "시리얼", "PID"]


class InstancesPanel(QWidget):
    instance_selected = Signal(object)  # BlueStacksInstance | None
    scan_started = Signal()
    scan_finished = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._instances: list[BlueStacksInstance] = []
        self._worker: ScanWorker | None = None

        self.scan_btn = QPushButton("🔍 스캔")
        self.scan_btn.clicked.connect(self.scan)

        self.table = QTableWidget(0, len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._on_selection)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(self.scan_btn)
        lay.addWidget(self.table)

    # --- 스캔 ------------------------------------------------------
    def scan(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("스캔 중…")
        self.scan_started.emit()
        self._worker = ScanWorker()
        self._worker.done.connect(self._on_scan_done)
        self._worker.failed.connect(self._on_scan_failed)
        self._worker.start()

    def _on_scan_done(self, instances: list) -> None:
        self._instances = instances
        self._populate()
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("🔍 스캔")
        self.scan_finished.emit(instances)

    def _on_scan_failed(self, msg: str) -> None:
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("🔍 스캔 (실패)")
        self.scan_finished.emit([])

    def _populate(self) -> None:
        self.table.setRowCount(len(self._instances))
        for r, i in enumerate(self._instances):
            vals = [
                i.display_name,
                i.key,
                "O" if i.running else "-",
                "O" if i.online else "-",
                i.serial or "",
                str(i.pid or ""),
            ]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(v)
                if c in (2, 3):
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, c, item)

    # --- 선택 ------------------------------------------------------
    def _on_selection(self) -> None:
        self.instance_selected.emit(self.current_instance())

    def current_instance(self) -> BlueStacksInstance | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        idx = rows[0].row()
        if 0 <= idx < len(self._instances):
            return self._instances[idx]
        return None
