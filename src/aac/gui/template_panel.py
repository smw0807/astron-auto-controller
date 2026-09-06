"""템플릿 목록 패널: 썸네일 보기 / 삭제 / 현재 화면에서 매칭 테스트."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from aac.config import TEMPLATES_DIR
from aac.vision.template import find_template, list_templates


class TemplatePanel(QWidget):
    # 매칭 결과를 캡처 뷰에 표시하도록 (found, cx, cy, score) 방출
    match_tested = Signal(bool, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frame: np.ndarray | None = None

        self.list = QListWidget()
        self.list.setIconSize(QSize(96, 54))
        self.list.itemDoubleClicked.connect(lambda _: self.test_match())

        self.test_btn = QPushButton("현재 화면에서 매칭 테스트")
        self.test_btn.clicked.connect(self.test_match)
        self.del_btn = QPushButton("삭제")
        self.del_btn.clicked.connect(self._delete)
        self.reload_btn = QPushButton("↻")
        self.reload_btn.setFixedWidth(28)
        self.reload_btn.clicked.connect(self.refresh)

        row = QHBoxLayout()
        row.addWidget(self.test_btn)
        row.addWidget(self.del_btn)
        row.addWidget(self.reload_btn)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.addWidget(QLabel("템플릿 (templates/)"))
        lay.addWidget(self.list, 1)
        lay.addLayout(row)
        self.refresh()

    def set_frame(self, frame: np.ndarray | None) -> None:
        self._frame = frame

    def refresh(self) -> None:
        self.list.clear()
        for name in list_templates():
            it = QListWidgetItem(name)
            px = QPixmap(str(TEMPLATES_DIR / name))
            if not px.isNull():
                it.setIcon(QIcon(px))
            self.list.addItem(it)

    def current_name(self) -> str | None:
        it = self.list.currentItem()
        return it.text() if it else None

    def test_match(self) -> None:
        name = self.current_name()
        if not name:
            return
        if self._frame is None:
            QMessageBox.information(self, "안내", "먼저 캡처 화면이 있어야 합니다")
            return
        m = find_template(self._frame, name)
        self.match_tested.emit(m.found, m.cx, m.cy, m.score)

    def _delete(self) -> None:
        name = self.current_name()
        if not name:
            return
        if QMessageBox.question(self, "삭제", f"'{name}' 삭제?") != QMessageBox.Yes:
            return
        (TEMPLATES_DIR / name).unlink(missing_ok=True)
        self.refresh()
