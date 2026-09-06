"""다중 인스턴스 대시보드: 인스턴스별 플로우 배정 + 시작/정지 + 통합 로그."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from aac.config import SETTINGS
from aac.flow import Flow
from aac.runner import RunnerManager, Scheduler

_COLS = ["별명", "key", "온라인", "플로우", "상태", "반복", "설정", ""]


class Dashboard(QWidget):
    def __init__(self, manager: RunnerManager, parent=None):
        super().__init__(parent)
        self.mgr = manager
        self.mgr.status_changed.connect(self._refresh_row)
        self.mgr.log.connect(self._on_log)
        self._row_by_key: dict[str, int] = {}

        # --- 상단 컨트롤 ---
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(3, 3600)
        self.interval_spin.setValue(int(SETTINGS.watch_interval_sec))
        self.interval_spin.setSuffix(" s")
        self.interval_spin.valueChanged.connect(self._save_interval)
        self.start_all_btn = QPushButton("전체 시작")
        self.start_all_btn.clicked.connect(
            lambda: self.mgr.start_all(float(self.interval_spin.value()))
        )
        self.stop_all_btn = QPushButton("전체 정지")
        self.stop_all_btn.clicked.connect(self.mgr.stop_all)
        self.reload_flows_btn = QPushButton("플로우 목록 새로고침")
        self.reload_flows_btn.clicked.connect(self._reload_flow_combos)

        self.notif_chk = QCheckBox("데스크톱 알림")
        self.notif_chk.setChecked(SETTINGS.notifications_enabled)
        self.notif_chk.toggled.connect(self._save_notif)

        top = QHBoxLayout()
        top.addWidget(QLabel("감시 간격"))
        top.addWidget(self.interval_spin)
        top.addWidget(self.start_all_btn)
        top.addWidget(self.stop_all_btn)
        top.addStretch(1)
        top.addWidget(self.notif_chk)
        top.addWidget(self.reload_flows_btn)

        # --- 스케줄러 행 ---
        self.sched_chk = QCheckBox("스케줄 사용")
        self.sched_chk.setChecked(SETTINGS.schedule_enabled)
        self.sched_chk.toggled.connect(self._save_sched)
        self.active_hours_edit = QLineEdit(SETTINGS.active_hours)
        self.active_hours_edit.setPlaceholderText("활성시간 09:00-23:30")
        self.active_hours_edit.setFixedWidth(140)
        self.active_hours_edit.editingFinished.connect(self._save_sched)
        self.daily_edit = QLineEdit(SETTINGS.daily_restart_time)
        self.daily_edit.setPlaceholderText("일일재시작 06:00")
        self.daily_edit.setFixedWidth(110)
        self.daily_edit.editingFinished.connect(self._save_sched)
        self.periodic_spin = QSpinBox()
        self.periodic_spin.setRange(0, 1440)
        self.periodic_spin.setValue(SETTINGS.periodic_restart_min)
        self.periodic_spin.setSuffix(" 분마다 재시작")
        self.periodic_spin.setSpecialValueText("주기재시작 끔")
        self.periodic_spin.valueChanged.connect(self._save_sched)

        sched = QHBoxLayout()
        sched.addWidget(self.sched_chk)
        sched.addWidget(self.active_hours_edit)
        sched.addWidget(self.daily_edit)
        sched.addWidget(self.periodic_spin)
        sched.addStretch(1)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)

        # --- 테이블 ---
        self.table = QTableWidget(0, len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.Stretch)

        # --- 로그 ---
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(4000)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addLayout(top)
        lay.addLayout(sched)
        lay.addWidget(line)
        lay.addWidget(self.table, 2)
        lay.addWidget(QLabel("통합 로그"))
        lay.addWidget(self.log, 1)

        # 스케줄러 (MainWindow 가 start() 호출)
        self.scheduler = Scheduler(self.mgr, self)
        self.scheduler.log.connect(lambda m: self.log.appendPlainText(m))

    # --- 외부에서 인스턴스 주입 -----------------------------
    def set_instances(self, instances: list) -> None:
        self.mgr.update_instances(instances)
        self._rebuild_table()

    # --- 테이블 --------------------------------------------
    def _flow_names(self) -> list[str]:
        return [""] + Flow.list_saved()

    def _rebuild_table(self) -> None:
        states = sorted(self.mgr.all_states(), key=lambda s: (not s.online, s.key))
        self.table.setRowCount(len(states))
        self._row_by_key.clear()
        for r, st in enumerate(states):
            self._row_by_key[st.key] = r
            self._set(r, 0, st.display_name)
            self._set(r, 1, st.key)
            self._set(r, 2, "O" if st.online else "-", center=True)

            combo = QComboBox()
            combo.addItems(self._flow_names())
            combo.setCurrentText(st.flow_name)
            combo.currentTextChanged.connect(
                lambda name, k=st.key: self.mgr.assign(k, name)
            )
            self.table.setCellWidget(r, 3, combo)

            self._set(r, 4, st.status, center=True)
            self._set(r, 5, str(st.iterations), center=True)

            cfg = QPushButton("⚙")
            cfg.setFixedWidth(34)
            cfg.clicked.connect(lambda _=False, k=st.key: self._edit_instance(k))
            self.table.setCellWidget(r, 6, cfg)

            btn = QPushButton("시작")
            btn.clicked.connect(lambda _=False, k=st.key: self._toggle(k))
            self.table.setCellWidget(r, 7, btn)
            self._refresh_row(st.key)

    def _set(self, r: int, c: int, text: str, center: bool = False) -> None:
        it = QTableWidgetItem(text)
        if center:
            it.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(r, c, it)

    def _toggle(self, key: str) -> None:
        if self.mgr.is_running(key):
            self.mgr.stop(key)
        else:
            self.mgr.start(key, float(self.interval_spin.value()))

    def _edit_instance(self, key: str) -> None:
        from PySide6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QFormLayout,
            QLineEdit,
        )

        from aac.vision.template import list_templates

        st = self.mgr.state(key)
        cur_vars = dict(SETTINGS.instance_vars.get(key, {}))
        dlg = QDialog(self)
        dlg.setWindowTitle(f"인스턴스 설정 — {st.display_name or key}")
        form = QFormLayout(dlg)

        tp = QComboBox()
        tp.setEditable(True)
        tp.addItems([""] + list_templates())
        tp.setCurrentText(cur_vars.get("tp_target", ""))
        form.addRow("tp_target (텔레포트 대상 템플릿)", tp)

        extra = QLineEdit(
            ",".join(f"{k}={v}" for k, v in cur_vars.items() if k != "tp_target")
        )
        extra.setPlaceholderText("추가변수  name=value,name2=value2")
        form.addRow("추가 변수", extra)

        iv = QDoubleSpinBox()
        iv.setRange(0, 3600)
        iv.setSuffix(" s (0=기본)")
        iv.setValue(SETTINGS.instance_intervals.get(key, 0.0))
        form.addRow("감시 간격 override", iv)

        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec() != QDialog.Accepted:
            return

        new_vars: dict[str, str] = {}
        if tp.currentText().strip():
            new_vars["tp_target"] = tp.currentText().strip()
        for pair in extra.text().split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                new_vars[k.strip()] = v.strip()
        if new_vars:
            SETTINGS.instance_vars[key] = new_vars
        else:
            SETTINGS.instance_vars.pop(key, None)
        if iv.value() > 0:
            SETTINGS.instance_intervals[key] = iv.value()
        else:
            SETTINGS.instance_intervals.pop(key, None)
        SETTINGS.save()
        self.log.appendPlainText(f"[{st.display_name or key}] 설정 저장: {new_vars}")

    def _refresh_row(self, key: str) -> None:
        r = self._row_by_key.get(key)
        if r is None:
            return
        st = self.mgr.state(key)
        if self.table.item(r, 4):
            self.table.item(r, 4).setText(st.status)
        if self.table.item(r, 5):
            self.table.item(r, 5).setText(str(st.iterations))
        btn = self.table.cellWidget(r, 7)
        if isinstance(btn, QPushButton):
            running = self.mgr.is_running(key)
            btn.setText("정지" if running else "시작")

    def _reload_flow_combos(self) -> None:
        names = self._flow_names()
        for r in range(self.table.rowCount()):
            combo = self.table.cellWidget(r, 3)
            if isinstance(combo, QComboBox):
                cur = combo.currentText()
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(names)
                combo.setCurrentText(cur)
                combo.blockSignals(False)

    # --- 로그 --------------------------------------------
    def _on_log(self, key: str, msg: str) -> None:
        st = self.mgr.state(key)
        name = st.display_name or st.key
        self.log.appendPlainText(f"[{name}] {msg}")

    def _save_interval(self, v: int) -> None:
        SETTINGS.watch_interval_sec = float(v)
        SETTINGS.save()

    def _save_notif(self, on: bool) -> None:
        SETTINGS.notifications_enabled = on
        SETTINGS.save()

    def _save_sched(self, *_) -> None:
        SETTINGS.schedule_enabled = self.sched_chk.isChecked()
        SETTINGS.active_hours = self.active_hours_edit.text().strip()
        SETTINGS.daily_restart_time = self.daily_edit.text().strip()
        SETTINGS.periodic_restart_min = self.periodic_spin.value()
        SETTINGS.save()
        self.scheduler.tick()

    def shutdown(self) -> None:
        self.scheduler.stop()
        self.mgr.shutdown()
