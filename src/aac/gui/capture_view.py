"""라이브 스크린샷 뷰. 클릭 시 정규화 좌표 방출, 드래그로 영역 선택(템플릿 크롭용)."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy


def bgr_to_qpixmap(img: np.ndarray) -> QPixmap:
    h, w = img.shape[:2]
    rgb = np.ascontiguousarray(img[:, :, ::-1])
    qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


class CaptureView(QLabel):
    # 정규화 좌표 (0~1)
    clicked = Signal(float, float)
    # 정규화 사각형 (x, y, w, h)
    region_selected = Signal(float, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(320, 180)
        self.setStyleSheet("background:#111;color:#888;")
        self.setText("인스턴스를 선택하세요")
        self._src_size: tuple[int, int] = (0, 0)  # (w, h) 원본
        self._pix: QPixmap | None = None
        self._drag_start: QPoint | None = None
        self._drag_rect: QRect | None = None
        self._last_click_norm: tuple[float, float] | None = None

    # --- 프레임 갱신 --------------------------------------------------
    def set_frame(self, img: np.ndarray) -> None:
        self._src_size = (img.shape[1], img.shape[0])
        self._pix = bgr_to_qpixmap(img)
        self._render()

    def clear_frame(self) -> None:
        self._pix = None
        self._src_size = (0, 0)
        self.setText("인스턴스를 선택하세요")

    def _render(self) -> None:
        if self._pix is None:
            return
        scaled = self._pix.scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        canvas = QPixmap(scaled.size())
        canvas.fill(Qt.transparent)
        p = QPainter(canvas)
        p.drawPixmap(0, 0, scaled)
        if self._drag_rect is not None:
            p.setPen(QPen(Qt.yellow, 2, Qt.DashLine))
            p.drawRect(self._drag_rect)
        if self._last_click_norm is not None:
            cx = self._last_click_norm[0] * scaled.width()
            cy = self._last_click_norm[1] * scaled.height()
            p.setPen(QPen(Qt.red, 2))
            p.drawLine(cx - 8, cy, cx + 8, cy)
            p.drawLine(cx, cy - 8, cx, cy + 8)
        p.end()
        self.setPixmap(canvas)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render()

    # --- 좌표 매핑 --------------------------------------------------
    def _displayed_rect(self) -> QRect:
        """QLabel 내부에서 실제 이미지가 그려지는 영역."""
        if self._pix is None:
            return QRect()
        scaled = self._pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        return QRect(x, y, scaled.width(), scaled.height())

    def _to_norm(self, pos: QPoint) -> tuple[float, float] | None:
        rect = self._displayed_rect()
        if rect.width() == 0 or not rect.contains(pos):
            return None
        nx = (pos.x() - rect.x()) / rect.width()
        ny = (pos.y() - rect.y()) / rect.height()
        return (min(max(nx, 0.0), 1.0), min(max(ny, 0.0), 1.0))

    # --- 마우스 -----------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._pix is None:
            return
        if event.button() == Qt.LeftButton:
            self._drag_start = event.pos()
            self._drag_rect = None

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is not None:
            self._drag_rect = QRect(self._drag_start, event.pos()).normalized()
            # 표시 영역으로 클램프
            self._drag_rect = self._drag_rect.intersected(self._displayed_rect())
            self._render()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is None:
            return
        start = self._drag_start
        end = event.pos()
        self._drag_start = None
        moved = (abs(end.x() - start.x()) + abs(end.y() - start.y())) > 6

        if not moved:
            norm = self._to_norm(end)
            if norm:
                self._last_click_norm = norm
                self._drag_rect = None
                self._render()
                self.clicked.emit(*norm)
            return

        n1 = self._to_norm(start)
        n2 = self._to_norm(end)
        if n1 and n2:
            x = min(n1[0], n2[0])
            y = min(n1[1], n2[1])
            w = abs(n1[0] - n2[0])
            h = abs(n1[1] - n2[1])
            if w > 0.005 and h > 0.005:
                self.region_selected.emit(x, y, w, h)
        self._render()

    # --- 조회 ------------------------------------------------------
    @property
    def source_size(self) -> tuple[int, int]:
        return self._src_size
