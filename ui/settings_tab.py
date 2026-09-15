"""
Settings tab for TagToolSH!.

Each logical group is a collapsible section inside a vertically scrollable
area. Sliders and spinboxes ignore wheel events until the user has actually
clicked inside them, so scrolling the tab never changes values by accident.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QSlider, QMessageBox, QSpinBox,
    QScrollArea, QFrame, QToolButton, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QEvent, QObject

from database import DatabaseManager


# ------------------------------------------------------------------ #
#  Wheel-safe widgets
#
#  These widgets only respond to mouse-wheel events after the user has
#  clicked inside them (including the +/- buttons and the internal text
#  field). Qt auto-focuses the first widget in a view on show, which
#  makes hasFocus() alone unreliable, and clicks on child widgets do not
#  reach the spinbox's own event() handler. We therefore install an event
#  filter on the widget AND all its children so any click anywhere inside
#  the widget flips the "_user_engaged" flag.
# ------------------------------------------------------------------ #
class _WheelGuardEventFilter(QObject):
    """Event filter that sets the owner widget's _user_engaged flag on any click."""
    def __init__(self, owner):
        super().__init__(owner)
        self._owner = owner

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            self._owner._user_engaged = True
        return False  # never consume; let the child handle it normally


class _WheelGuardMixin:
    """
    Mixin for QSlider / QSpinBox that only allows wheel adjustments after
    the user has clicked somewhere inside the widget.
    """
    def _init_wheel_guard(self):
        self._user_engaged = False
        self._wheel_guard_filter = _WheelGuardEventFilter(self)
        self.installEventFilter(self._wheel_guard_filter)
        for child in self.findChildren(QObject):
            child.installEventFilter(self._wheel_guard_filter)

    def focusOutEvent(self, event):
        self._user_engaged = False
        super().focusOutEvent(event)

    def wheelEvent(self, event):
        if getattr(self, "_user_engaged", False) and self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class NoWheelSlider(_WheelGuardMixin, QSlider):
    """Slider that ignores wheel events until the user clicks inside it."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_wheel_guard()


class NoWheelSpinBox(_WheelGuardMixin, QSpinBox):
    """SpinBox that ignores wheel events until the user clicks inside it."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_wheel_guard()


# ------------------------------------------------------------------ #
#  Collapsible section
# ------------------------------------------------------------------ #
class CollapsibleSection(QWidget):
    """
    A titled section that can be expanded/collapsed by clicking its header.
    """

    def __init__(self, title: str, expanded: bool = True, parent=None):
        super().__init__(parent)
        self._expanded = expanded

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header_btn = QToolButton()
        self.header_btn.setObjectName("sectionHeader")
        self.header_btn.setText(title)
        self.header_btn.setCheckable(True)
        self.header_btn.setChecked(expanded)
        self.header_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.header_btn.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.header_btn.setCursor(Qt.PointingHandCursor)
        self.header_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.header_btn.clicked.connect(self._toggle)
        outer.addWidget(self.header_btn)

        self.content = QFrame()
        self.content.setObjectName("sectionContent")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(18, 12, 18, 16)
        self.content_layout.setSpacing(10)
        self.content.setVisible(expanded)
        outer.addWidget(self.content)

    def _toggle(self):
        self._expanded = not self._expanded
        self.header_btn.setArrowType(Qt.DownArrow if self._expanded else Qt.RightArrow)
        self.content.setVisible(self._expanded)

    def add_widget(self, w: QWidget):
        self.content_layout.addWidget(w)

    def add_layout(self, l):
        self.content_layout.addLayout(l)

    def add_spacing(self, px: int):
        self.content_layout.addSpacing(px)


# ------------------------------------------------------------------ #
#  Settings tab
# ------------------------------------------------------------------ #
class SettingsTab(QWidget):
    settings_changed = Signal()
    request_test_beep = Signal()
    request_rescan_readers = Signal()

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.init_ui()

    # ---------------- helpers ---------------- #

    def _make_checkbox(self, text: str, checked: bool, connect=None) -> QCheckBox:
        cb = QCheckBox(text)
        cb.setChecked(checked)
        cb.setMinimumHeight(26)
        if connect is None:
            cb.toggled.connect(self._save_settings)
        else:
            cb.toggled.connect(connect)
        return cb

    def _make_hint(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("hintLabel")
        lbl.setWordWrap(True)
        lbl.setMinimumHeight(28)
        return lbl

    def _make_field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("settingsFieldLabel")
        return lbl

    # ---------------- UI ---------------- #

    def init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)

        outer = QVBoxLayout(container)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)

        # ============================================================
        #  Action Execution Behavior
        # ============================================================
        self.exec_section = CollapsibleSection("Action Execution Behavior", expanded=True)
        outer.addWidget(self.exec_section)

        self.auto_launch_cb = self._make_checkbox(
            "Enable Action Execution on Tag Tap",
            self.db.get_setting("auto_launch", True),
        )
        self.exec_section.add_widget(self.auto_launch_cb)
        self.exec_section.add_widget(self._make_hint(
            "💡 Uncheck to enter Inspection / Safe Mode (inspect tag data without launching anything)."
        ))

        self.read_only_cb = self._make_checkbox(
            "Read-Only Mode: never launch anything, only display tag content",
            self.db.get_setting("read_only_mode", False),
        )
        self.exec_section.add_widget(self.read_only_cb)
        self.exec_section.add_widget(self._make_hint(
            "💡 Strongest safety mode. Ideal while encoding and verifying tags in Tag Studio."
        ))

        self.confirm_exe_cb = self._make_checkbox(
            "Ask for confirmation before launching .exe executable files",
            self.db.get_setting("confirm_exe", False),
        )
        self.exec_section.add_widget(self.confirm_exe_cb)

        self.kill_removal_cb = self._make_checkbox(
            "Terminate application on tag removal (taskkill /F /IM <process> /T)",
            self.db.get_setting("kill_on_removal", False),
        )
        self.exec_section.add_widget(self.kill_removal_cb)
        self.exec_section.add_widget(self._make_hint(
            "💡 Closes the .exe launched by the tag when you lift the card. Spotify tags are always excluded."
        ))

        self.kill_all_shutdown_cb = self._make_checkbox(
            "Also terminate all tag-launched processes when the app exits",
            self.db.get_setting("kill_all_on_shutdown", False),
        )
        self.exec_section.add_widget(self.kill_all_shutdown_cb)
        self.exec_section.add_widget(self._make_hint(
            "💡 Only affects processes the app itself launched. Manually-opened apps are never touched."
        ))

        self.exec_section.add_spacing(6)

        debounce_val = float(self.db.get_setting("debounce_seconds", 2.5))
        self.debounce_lbl = self._make_field_label(
            f"Tag Debounce / Hold Cooldown: {debounce_val:.1f} seconds"
        )
        self.exec_section.add_widget(self.debounce_lbl)
        self.exec_section.add_widget(self._make_hint(
            "Prevents repeated launches while the tag rests on the ACR122U reader."
        ))
        self.debounce_slider = NoWheelSlider(Qt.Horizontal)
        self.debounce_slider.setRange(10, 100)
        self.debounce_slider.setValue(int(debounce_val * 10))
        self.debounce_slider.setMinimumHeight(26)
        self.debounce_slider.valueChanged.connect(self._on_debounce_changed)
        self.exec_section.add_widget(self.debounce_slider)

        # ============================================================
        #  Launcher Auto-Detection
        # ============================================================
        self.detect_section = CollapsibleSection("Launcher Auto-Detection", expanded=True)
        outer.addWidget(self.detect_section)

        self.auto_detect_cb = self._make_checkbox(
            "Auto-detect game process for Steam / Epic / URI launcher tags",
            self.db.get_setting("auto_detect_enabled", True),
        )
        self.detect_section.add_widget(self.auto_detect_cb)
        self.detect_section.add_widget(self._make_hint(
            "💡 Snapshots running processes before and after launch, then stores the "
            "detected game executable back to the Tag Library. Spotify is always excluded."
        ))

        self.detect_section.add_spacing(4)

        detect_delay_row = QHBoxLayout()
        detect_delay_row.setSpacing(10)
        detect_delay_row.addWidget(self._make_field_label("Auto-detection delay:"))
        self.detect_delay_spin = NoWheelSpinBox()
        self.detect_delay_spin.setRange(3, 120)
        self.detect_delay_spin.setSuffix(" seconds")
        self.detect_delay_spin.setValue(int(self.db.get_setting("auto_detect_delay_seconds", 15)))
        self.detect_delay_spin.setMinimumWidth(140)
        self.detect_delay_spin.setMinimumHeight(28)
        self.detect_delay_spin.valueChanged.connect(self._on_detect_delay_changed)
        detect_delay_row.addWidget(self.detect_delay_spin)
        detect_delay_row.addStretch()
        self.detect_section.add_layout(detect_delay_row)

        self.detect_section.add_widget(self._make_hint(
            "How long to wait after launching before comparing process lists. "
            "15 seconds works well for most Steam and Epic games."
        ))

        # ============================================================
        #  BSOD Effect
        # ============================================================
        self.bsod_section = CollapsibleSection("BSOD Effect (Easter Egg)", expanded=True)
        outer.addWidget(self.bsod_section)

        self.bsod_on_kill_cb = self._make_checkbox(
            "Show bsod.png fullscreen after a successful tag-removal process kill",
            self.db.get_setting("bsod_on_kill", True),
        )
        self.bsod_section.add_widget(self.bsod_on_kill_cb)
        self.bsod_section.add_widget(self._make_hint(
            "💡 Any key or mouse click dismisses it."
        ))

        self.bsod_section.add_spacing(4)

        bsod_dur_row = QHBoxLayout()
        bsod_dur_row.setSpacing(10)
        bsod_dur_row.addWidget(self._make_field_label("Auto-close after:"))
        self.bsod_dur_spin = NoWheelSpinBox()
        self.bsod_dur_spin.setRange(1, 3600)
        self.bsod_dur_spin.setSuffix(" seconds")
        self.bsod_dur_spin.setValue(int(self.db.get_setting("bsod_duration_seconds", 60)))
        self.bsod_dur_spin.setMinimumWidth(140)
        self.bsod_dur_spin.setMinimumHeight(28)
        self.bsod_dur_spin.valueChanged.connect(self._on_bsod_dur_changed)
        bsod_dur_row.addWidget(self.bsod_dur_spin)
        bsod_dur_row.addStretch()
        self.bsod_section.add_layout(bsod_dur_row)

        # ============================================================
        #  ACR122U Hardware Feedback
        # ============================================================
        self.hw_section = CollapsibleSection("ACR122U Hardware Feedback", expanded=True)
        outer.addWidget(self.hw_section)

        self.buzzer_tap_cb = self._make_checkbox(
            "Sound hardware buzzer beep when an NFC tag is tapped",
            self.db.get_setting("buzzer_on_tap", True),
        )
        self.hw_section.add_widget(self.buzzer_tap_cb)

        self.buzzer_write_cb = self._make_checkbox(
            "Sound hardware buzzer beep when tag writing succeeds",
            self.db.get_setting("buzzer_on_write", True),
        )
        self.hw_section.add_widget(self.buzzer_write_cb)

        self.hw_section.add_spacing(4)

        hw_btn_row = QHBoxLayout()
        hw_btn_row.setSpacing(10)
        test_beep_btn = QPushButton("🔔 Test Reader Buzzer")
        test_beep_btn.setMinimumHeight(30)
        test_beep_btn.clicked.connect(self.request_test_beep.emit)
        hw_btn_row.addWidget(test_beep_btn)

        rescan_btn = QPushButton("🔄 Rescan PC/SC Readers")
        rescan_btn.setMinimumHeight(30)
        rescan_btn.clicked.connect(self.request_rescan_readers.emit)
        hw_btn_row.addWidget(rescan_btn)

        hw_btn_row.addStretch()
        self.hw_section.add_layout(hw_btn_row)

        # ============================================================
        #  System Tray & Windows Startup
        # ============================================================
        self.tray_section = CollapsibleSection("System Tray & Windows Startup", expanded=True)
        outer.addWidget(self.tray_section)

        self.minimize_tray_cb = self._make_checkbox(
            "Minimize application to system tray when minimized or closed",
            self.db.get_setting("minimize_to_tray", True),
        )
        self.tray_section.add_widget(self.minimize_tray_cb)

        self.start_maximized_cb = self._make_checkbox(
            "Start with the main window maximized",
            self.db.get_setting("start_maximized", True),
        )
        self.tray_section.add_widget(self.start_maximized_cb)

        from autostart import is_autostart_enabled
        self.autostart_cb = QCheckBox(
            "Launch automatically on Windows startup (runs minimized in tray)"
        )
        self.autostart_cb.setChecked(is_autostart_enabled())
        self.autostart_cb.setMinimumHeight(26)
        self.autostart_cb.toggled.connect(self._on_autostart_toggled)
        self.tray_section.add_widget(self.autostart_cb)
        self.tray_section.add_widget(self._make_hint(
            "💡 When running in system tray, tag taps and launches continue in the background."
        ))

        outer.addStretch()

    # ---------------- Signal handlers ---------------- #

    def _on_debounce_changed(self, val: int):
        sec = val / 10.0
        self.debounce_lbl.setText(f"Tag Debounce / Hold Cooldown: {sec:.1f} seconds")
        self.db.set_setting("debounce_seconds", sec)
        self.settings_changed.emit()

    def _on_detect_delay_changed(self, val: int):
        self.db.set_setting("auto_detect_delay_seconds", int(val))
        self.settings_changed.emit()

    def _on_bsod_dur_changed(self, val: int):
        self.db.set_setting("bsod_duration_seconds", int(val))
        self.settings_changed.emit()

    def _on_autostart_toggled(self, checked: bool):
        from autostart import set_autostart
        ok = set_autostart(checked, start_minimized=True)
        self.db.set_setting("launch_on_boot", checked)
        if not ok:
            QMessageBox.warning(
                self,
                "Autostart Error",
                "Could not update Windows registry startup entry."
            )

    def _save_settings(self):
        self.db.set_setting("auto_launch", self.auto_launch_cb.isChecked())
        self.db.set_setting("read_only_mode", self.read_only_cb.isChecked())
        self.db.set_setting("confirm_exe", self.confirm_exe_cb.isChecked())
        self.db.set_setting("kill_on_removal", self.kill_removal_cb.isChecked())
        self.db.set_setting("kill_all_on_shutdown", self.kill_all_shutdown_cb.isChecked())
        self.db.set_setting("auto_detect_enabled", self.auto_detect_cb.isChecked())
        self.db.set_setting("bsod_on_kill", self.bsod_on_kill_cb.isChecked())
        self.db.set_setting("buzzer_on_tap", self.buzzer_tap_cb.isChecked())
        self.db.set_setting("buzzer_on_write", self.buzzer_write_cb.isChecked())
        self.db.set_setting("minimize_to_tray", self.minimize_tray_cb.isChecked())
        self.db.set_setting("start_maximized", self.start_maximized_cb.isChecked())
        self.settings_changed.emit()
