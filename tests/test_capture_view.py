"""Regression checks for selection overlays on centered capture previews."""
import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import numpy as np
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from aac.gui.capture_view import CaptureView


class CaptureViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_drag_overlay_and_region_match_with_preview_margins(self):
        # Horizontal margins, vertical margins, and no margins; both drag directions.
        for frame_width, frame_height in ((400, 400), (800, 200), (800, 600)):
            for reverse in (False, True):
                with self.subTest(frame=(frame_width, frame_height), reverse=reverse):
                    view = CaptureView()
                    view.resize(800, 600)
                    view.set_frame(np.zeros((frame_height, frame_width, 3), np.uint8))
                    regions = []
                    view.region_selected.connect(lambda *region: regions.append(region))
                    displayed = view._displayed_rect()
                    local_start = QPoint(displayed.width() // 4, displayed.height() // 4)
                    local_end = QPoint(displayed.width() // 2, displayed.height() // 2)
                    start = displayed.topLeft() + local_start
                    end = displayed.topLeft() + local_end
                    if reverse:
                        start, end = end, start
                    for kind, pos, button, buttons in (
                        (QEvent.MouseButtonPress, start, Qt.LeftButton, Qt.LeftButton),
                        (QEvent.MouseMove, end, Qt.NoButton, Qt.LeftButton),
                        (QEvent.MouseButtonRelease, end, Qt.LeftButton, Qt.NoButton),
                    ):
                        event = QMouseEvent(kind, QPointF(pos), QPointF(pos), button,
                                            buttons, Qt.NoModifier)
                        QApplication.sendEvent(view, event)

                    self.assertEqual(len(regions), 1)
                    np.testing.assert_allclose(regions[0], (0.25, 0.25, 0.25, 0.25))
                    rendered = view.pixmap().toImage()
                    yellow = [
                        (x, y)
                        for y in range(rendered.height())
                        for x in range(rendered.width())
                        if rendered.pixelColor(x, y) == Qt.yellow
                    ]
                    self.assertTrue(yellow, "Selection border must be visible")
                    xs, ys = zip(*yellow)
                    for actual, expected in zip(
                        (min(xs), min(ys), max(xs), max(ys)),
                        (local_start.x(), local_start.y(), local_end.x(), local_end.y()),
                    ):
                        self.assertLessEqual(abs(actual - expected), 2)
                    view.close()


if __name__ == "__main__":
    unittest.main()
