"""
Fullscreen "BSOD" image viewer.
Displays an image fullscreen, always-on-top, borderless, on top of all windows.
Any key-press or mouse-click closes it. Also auto-closes after a safety timeout.
"""

import os
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication


class BsodViewer(QWidget):
    """
    Fullscreen borderless always-on-top image viewer.
    Closes on any key press or mouse click, plus a safety auto-close timer.
    """

    _instance: Optional["BsodViewer"] = None

    def __init__(self, image_path: str, auto_close_ms: int = 60000):
        super().__init__(None)

        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("System Message")
        self.setCursor(Qt.BlankCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #000000; color: #ffffff; font-size: 24px;")
        layout.addWidget(self.image_label)

        self._original_pixmap = QPixmap(image_path)
        self._image_path = image_path

        if self._original_pixmap.isNull():
            self.image_label.setText(f"(could not load image: {image_path})")

        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self.close)
        if auto_close_ms > 0:
            self._auto_close_timer.start(auto_close_ms)

    @classmethod
    def show_fullscreen(cls, image_path: str, auto_close_ms: int = 60000) -> "BsodViewer":
        if cls._instance is not None:
            try:
                cls._instance.close()
            except Exception:
                pass
            cls._instance = None

        viewer = cls(image_path, auto_close_ms=auto_close_ms)
        cls._instance = viewer

        screen = QApplication.primaryScreen()
        if screen:
            viewer.setGeometry(screen.geometry())

        viewer.setWindowState(viewer.windowState() | Qt.WindowFullScreen)
        viewer.show()
        viewer.raise_()
        viewer.activateWindow()

        def _reassert():
            try:
                if viewer.isVisible():
                    viewer.setWindowState(viewer.windowState() | Qt.WindowFullScreen)
                    viewer.raise_()
                    viewer.activateWindow()
            except RuntimeError:
                pass

        QTimer.singleShot(100, _reassert)
        QTimer.singleShot(500, _reassert)

        return viewer

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled_pixmap()

    def showEvent(self, event):
        super().showEvent(event)
        self._update_scaled_pixmap()

    def _update_scaled_pixmap(self):
        if self._original_pixmap.isNull():
            return
        scaled = self._original_pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def keyPressEvent(self, event: QKeyEvent):
        self.close()

    def mousePressEvent(self, event: QMouseEvent):
        self.close()

    def wheelEvent(self, event):
        self.close()

    def closeEvent(self, event):
        if BsodViewer._instance is self:
            BsodViewer._instance = None
        super().closeEvent(event)