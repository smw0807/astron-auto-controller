"""StepSpec.params 로부터 속성 편집 폼을 자동 생성."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from aac.config import TEMPLATES_DIR
from aac.flow.model import Step
from aac.flow.registry import ParamSpec, get_step_spec

_KEYCODES = ["BACK", "HOME", "ENTER", "MENU", "APP_SWITCH", "ESCAPE", "DEL", "TAB", "SPACE",
             "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT"]


class ParamForm(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)

        form_host = QWidget()
        self._layout = QFormLayout(form_host)
        self._layout.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(form_host)

        self._note_label = QLabel("메모")
        self._note = QPlainTextEdit()
        self._note.setPlaceholderText("메모")
        self._note.setFixedHeight(48)
        self._note.textChanged.connect(self._commit_note)
        outer.addWidget(self._note_label)
        outer.addWidget(self._note)
        outer.addStretch(1)

        self._step: Step | None = None
        self._widgets: dict[str, QWidget] = {}

    # --- 로드 ----------------------------------------------------
    def set_step(self, step: Step | None, flow_names: list[str] | None = None) -> None:
        self._step = None  # commit 억제
        while self._layout.rowCount():
            self._layout.removeRow(0)
        self._widgets.clear()

        show = step is not None and get_step_spec(step.type) is not None
        self._note_label.setVisible(show)
        self._note.setVisible(show)
        if not show:
            self._note.blockSignals(True)
            self._note.setPlainText("")
            self._note.blockSignals(False)
            return

        spec = get_step_spec(step.type)
        for ps in spec.params:
            val = step.params.get(ps.name, ps.default)
            w = self._make_widget(ps, val, flow_names or [])
            w.setToolTip(ps.help)
            self._widgets[ps.name] = w
            self._layout.addRow(ps.label, w)
        self._note.blockSignals(True)
        self._note.setPlainText(step.note)
        self._note.blockSignals(False)
        self._step = step

    # --- 위젯 생성 ---------------------------------------------
    def _make_widget(self, ps: ParamSpec, val: Any, flow_names: list[str]) -> QWidget:
        commit = self._commit

        if ps.type == "bool":
            w = QCheckBox()
            w.setChecked(bool(val))
            w.toggled.connect(lambda _: commit())
            return w
        if ps.type in ("float", "seconds"):
            w = QDoubleSpinBox()
            w.setDecimals(3)
            w.setRange(-1e6, 1e6)
            w.setSingleStep(0.05 if ps.type == "seconds" else 0.01)
            w.setValue(float(val or 0.0))
            w.valueChanged.connect(lambda _: commit())
            return w
        if ps.type == "int":
            w = QSpinBox()
            w.setRange(-1_000_000, 1_000_000)
            w.setValue(int(val or 0))
            w.valueChanged.connect(lambda _: commit())
            return w
        if ps.type == "keycode":
            w = QComboBox()
            w.setEditable(True)
            w.addItems(_KEYCODES)
            w.setCurrentText(str(val or "BACK"))
            w.currentTextChanged.connect(lambda _: commit())
            return w
        if ps.type == "flow":
            w = QComboBox()
            w.setEditable(True)
            w.addItems([""] + flow_names)
            w.setCurrentText(str(val or ""))
            w.currentTextChanged.connect(lambda _: commit())
            return w
        if ps.type == "template":
            return self._template_widget(str(val or ""), commit)
        # str / region
        w = QLineEdit(str(val or ""))
        w.textChanged.connect(lambda _: commit())
        return w

    def _template_widget(self, val: str, commit) -> QWidget:
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItems([""] + sorted(p.name for p in TEMPLATES_DIR.glob("*.png")))
        combo.setCurrentText(val)
        combo.currentTextChanged.connect(lambda _: commit())
        lay.addWidget(combo, 1)
        box.setProperty("value_widget", combo)
        return box

    # --- 커밋 --------------------------------------------------
    def _widget_value(self, ps: ParamSpec, w: QWidget) -> Any:
        if isinstance(w, QCheckBox):
            return w.isChecked()
        if isinstance(w, QDoubleSpinBox):
            return round(w.value(), 4)
        if isinstance(w, QSpinBox):
            return w.value()
        if isinstance(w, QComboBox):
            return w.currentText()
        if isinstance(w, QLineEdit):
            return w.text()
        vw = w.property("value_widget")
        if isinstance(vw, QComboBox):
            return vw.currentText()
        return None

    def _commit(self) -> None:
        if self._step is None:
            return
        spec = get_step_spec(self._step.type)
        if spec is None:
            return
        for ps in spec.params:
            w = self._widgets.get(ps.name)
            if w is not None:
                self._step.params[ps.name] = self._widget_value(ps, w)
        self.changed.emit()

    def _commit_note(self) -> None:
        if self._step is not None:
            self._step.note = self._note.toPlainText()
            self.changed.emit()
