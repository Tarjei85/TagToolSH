"""
Main Application Window for TagToolSH!.
Integrates PySide6 UI with background NFCWorker and ActionExecutor.
"""

import os
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTabWidget, QStatusBar, QMessageBox, QApplication,
    QSystemTrayIcon, QMenu, QPushButton
)
from PySide6.QtCore import Qt, Slot, QEvent, QTimer
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen

from database import DatabaseManager
from action_executor import ActionExecutor
from nfc_reader import NFCWorker
from ndef_handler import NdefAction

from ui.theme import DARK_THEME_QSS
from ui.scanner_tab import ScannerTab
from ui.writer_tab import WriterTab
from ui.library_tab import LibraryTab
from ui.settings_tab import SettingsTab
from ui.info_tab import InfoTab
from ui.bsod_viewer import BsodViewer


APP_TITLE = "TagToolSH!"


def _dynamic_copyright() -> str:
    yy = datetime.now().strftime("%y")
    return f"Copyright 20\u00a9{yy} - Tarjei S. H."


def create_app_icon() -> QIcon:
    import sys

    candidates = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "icon.ico"))
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(here)
    candidates.append(os.path.join(project_root, "app_data", "icon.ico"))
    candidates.append(os.path.join(project_root, "icon.ico"))

    for path in candidates:
        if os.path.exists(path):
            icon = QIcon(path)
            if not icon.isNull():
                return icon

    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    painter.setBrush(QBrush(QColor("#4f46e5")))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)

    painter.setPen(QPen(QColor("#ffffff"), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(14, 18, 36, 26, 4, 4)

    painter.drawArc(24, 24, 14, 14, -45 * 16, 90 * 16)
    painter.drawArc(20, 20, 22, 22, -45 * 16, 90 * 16)

    painter.end()
    return QIcon(pixmap)


class MainWindow(QMainWindow):
    def __init__(self, db: DatabaseManager, start_hidden: bool = False):
        super().__init__()
        self.db = db
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(880, 640)

        self.app_icon = create_app_icon()
        self.setWindowIcon(self.app_icon)

        self._closing_action = None
        self._tray_notified = False
        self._signals_connected = False
        self._start_hidden = start_hidden

        self._active_uid = None
        self._last_action_uid = None
        self._last_action_time = 0.0
        self._last_tag_wanted_kill = False

        debounce_sec = float(self.db.get_setting("debounce_seconds", 2.5))
        self.executor = ActionExecutor(debounce_seconds=debounce_sec)
        self.executor.auto_detect_enabled = self.db.get_setting("auto_detect_enabled", True)
        self.executor.auto_detect_delay_seconds = int(self.db.get_setting("auto_detect_delay_seconds", 15))
        self.executor.set_auto_detect_callback(self._on_auto_detected)
        self.executor.set_log_callback(self._on_detection_log)

        self.worker = NFCWorker()
        self.worker.buzzer_on_tap = self.db.get_setting("buzzer_on_tap", True)
        self.worker.buzzer_on_write = self.db.get_setting("buzzer_on_write", True)

        self.init_ui()
        self._init_tray()
        self.connect_signals()

        self.worker.start()

        if self._start_hidden:
            QTimer.singleShot(0, self.hide)

    def init_ui(self):
        self.setStyleSheet(DARK_THEME_QSS)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)

        header_bar = QHBoxLayout()

        title_lbl = QLabel(f"🏷️ {APP_TITLE}")
        title_lbl.setObjectName("headerTitle")
        header_bar.addWidget(title_lbl)

        header_bar.addStretch()

        self.mode_btn = QPushButton()
        self.mode_btn.setCursor(Qt.PointingHandCursor)
        self.mode_btn.clicked.connect(self._toggle_execution_mode)
        self._update_mode_button()
        header_bar.addWidget(self.mode_btn)

        self.reader_badge = QLabel("Connecting...")
        self.reader_badge.setObjectName("badgeDisconnected")
        header_bar.addWidget(self.reader_badge)

        self.card_badge = QLabel("No Card")
        self.card_badge.setObjectName("badgeCardNone")
        header_bar.addWidget(self.card_badge)

        main_layout.addLayout(header_bar)

        self.tabs = QTabWidget()

        self.scanner_tab = ScannerTab()
        self.tabs.addTab(self.scanner_tab, "📡 Live Scanner & Launcher")

        self.writer_tab = WriterTab(self.executor)
        self.tabs.addTab(self.writer_tab, "✏️ Tag Studio / Writer")

        self.library_tab = LibraryTab(self.db, self.executor)
        self.tabs.addTab(self.library_tab, "📚 Tag Library")

        self.settings_tab = SettingsTab(self.db)
        self.tabs.addTab(self.settings_tab, "⚙️ Settings")

        self.info_tab = InfoTab()
        self.tabs.addTab(self.info_tab, "ℹ️ Info")

        main_layout.addWidget(self.tabs)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready. Listening for NFC reader and tags...")

        self.copyright_lbl = QLabel(_dynamic_copyright())
        self.copyright_lbl.setObjectName("copyrightLabel")
        self.status_bar.addPermanentWidget(self.copyright_lbl)

    def connect_signals(self):
        if self._signals_connected:
            return
        self._signals_connected = True

        self.worker.reader_status_changed.connect(self._on_reader_status)
        self.worker.tag_detected.connect(self._on_tag_detected)
        self.worker.tag_removed.connect(self._on_tag_removed)
        self.worker.write_progress.connect(self.writer_tab.set_write_progress)
        self.worker.write_completed.connect(self.writer_tab.set_write_completed)
        self.worker.log_event.connect(self._on_log_event)

        self.scanner_tab.request_launch.connect(self._on_manual_launch)
        self.scanner_tab.request_save_tag.connect(self._on_save_tag_request)
        self.scanner_tab.request_switch_writer.connect(lambda: self.tabs.setCurrentIndex(1))

        self.writer_tab.request_queue_write.connect(self.worker.queue_write)
        self.writer_tab.request_cancel_write.connect(self.worker.cancel_write)

        self.settings_tab.settings_changed.connect(self._on_settings_updated)
        self.settings_tab.request_test_beep.connect(self.worker.trigger_test_beep)
        self.settings_tab.request_rescan_readers.connect(
            lambda: self.status_bar.showMessage("Rescanning readers...", 3000)
        )

    def _init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.app_icon)
        self.tray_icon.setToolTip(APP_TITLE)

        self.tray_menu = QMenu()

        title_action = self.tray_menu.addAction(f"🏷️ {APP_TITLE}")
        title_action.setEnabled(False)

        self.tray_reader_action = self.tray_menu.addAction("🔴 No Reader Detected")
        self.tray_reader_action.setEnabled(False)

        self.tray_menu.addSeparator()

        open_action = self.tray_menu.addAction("Open Launcher Window")
        open_action.triggered.connect(self.restore_window)

        self.tray_menu.addSeparator()

        exit_action = self.tray_menu.addAction("Exit")
        exit_action.triggered.connect(self.quit_application)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.restore_window()

    def restore_window(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _shutdown_worker(self):
        try:
            self.worker.stop_requested = True
            self.worker.running = False
        except Exception:
            pass

        try:
            if self.worker.isRunning():
                if not self.worker.wait(700):
                    try:
                        self.worker.terminate()
                    except Exception:
                        pass
                    self.worker.wait(500)
        except Exception:
            pass

    def quit_application(self):
        if self._closing_action == "exit":
            return
        self._closing_action = "exit"

        if self.db.get_setting("kill_all_on_shutdown", False):
            try:
                killed, failed = self.executor.kill_all_tracked()
                if killed or failed:
                    print(f"[MainWindow] Exit cleanup: killed={killed}, failed={failed}")
            except Exception:
                pass

        self._shutdown_worker()
        try:
            self.tray_icon.hide()
            self.tray_icon.setContextMenu(None)
        except Exception:
            pass
        QApplication.quit()

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            if self.isMinimized():
                if self.db.get_setting("minimize_to_tray", True):
                    QTimer.singleShot(0, self.hide)
                    if not self._tray_notified:
                        self._tray_notified = True
                        self.tray_icon.showMessage(
                            APP_TITLE,
                            "Running in system tray. Tag taps continue in background.",
                            QSystemTrayIcon.Information,
                            2500
                        )
        super().changeEvent(event)

    def closeEvent(self, event):
        if self._closing_action == "exit":
            self._shutdown_worker()
            try:
                self.tray_icon.hide()
                self.tray_icon.setContextMenu(None)
            except Exception:
                pass
            event.accept()
            QApplication.quit()
            return

        msg = QMessageBox(self)
        msg.setWindowTitle(f"Close {APP_TITLE}?")
        msg.setIcon(QMessageBox.Question)
        msg.setText("Do you want to exit completely or keep running in the system tray?")
        msg.setInformativeText(
            "Minimizing to tray keeps NFC tag detection active in the background.\n"
            "Exiting closes the app and stops all tag handling."
        )

        min_btn = msg.addButton("Minimize to Tray", QMessageBox.AcceptRole)
        exit_btn = msg.addButton("Exit Launcher", QMessageBox.DestructiveRole)
        cancel_btn = msg.addButton("Cancel", QMessageBox.RejectRole)

        msg.setDefaultButton(min_btn)
        msg.exec()

        clicked = msg.clickedButton()

        if clicked is min_btn:
            event.ignore()
            self.hide()
            if not self._tray_notified:
                self._tray_notified = True
                self.tray_icon.showMessage(
                    APP_TITLE,
                    "Running in system tray. Right-click the tray icon to exit.",
                    QSystemTrayIcon.Information,
                    2500
                )
        elif clicked is exit_btn:
            if self.db.get_setting("kill_all_on_shutdown", False):
                try:
                    killed, failed = self.executor.kill_all_tracked()
                    if killed or failed:
                        print(f"[MainWindow] Shutdown cleanup: killed={killed}, failed={failed}")
                except Exception:
                    pass
            self._closing_action = "exit"
            self._shutdown_worker()
            try:
                self.tray_icon.hide()
                self.tray_icon.setContextMenu(None)
            except Exception:
                pass
            event.accept()
            QApplication.quit()
        else:
            event.ignore()

    @Slot(bool, str)
    def _on_reader_status(self, connected: bool, name: str):
        if connected:
            self.reader_badge.setText(f"🟢 {name}")
            self.reader_badge.setObjectName("badgeConnected")
            self.tray_reader_action.setText(f"🟢 {name}")
        else:
            self.reader_badge.setText("🔴 No Reader Detected")
            self.reader_badge.setObjectName("badgeDisconnected")
            self.tray_reader_action.setText("🔴 No Reader Detected")
        self.reader_badge.style().unpolish(self.reader_badge)
        self.reader_badge.style().polish(self.reader_badge)

    def _update_mode_button(self):
        auto = self.db.get_setting("auto_launch", True)
        read_only = self.db.get_setting("read_only_mode", False)

        if read_only:
            self.mode_btn.setText("🔒 Read-Only Mode")
            self.mode_btn.setStyleSheet("""
                QPushButton {
                    background-color: #7f1d1d;
                    color: #fca5a5;
                    border: 1px solid #dc2626;
                    border-radius: 12px;
                    padding: 4px 12px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #991b1b; }
            """)
            self.mode_btn.setToolTip(
                "READ-ONLY: Tag taps will NEVER launch anything.\n"
                "Only tag content is displayed.\n"
                "Click to cycle mode."
            )
        elif auto:
            self.mode_btn.setText("⚡ Execution Mode: Active")
            self.mode_btn.setStyleSheet("""
                QPushButton {
                    background-color: #065f46;
                    color: #34d399;
                    border: 1px solid #059669;
                    border-radius: 12px;
                    padding: 4px 12px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #047857; }
            """)
            self.mode_btn.setToolTip("Action auto-execution is ACTIVE.\nClick to cycle mode.")
        else:
            self.mode_btn.setText("🔍 Inspection Mode (Safe)")
            self.mode_btn.setStyleSheet("""
                QPushButton {
                    background-color: #78350f;
                    color: #fbbf24;
                    border: 1px solid #d97706;
                    border-radius: 12px;
                    padding: 4px 12px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #92400e; }
            """)
            self.mode_btn.setToolTip("Safe Testing Mode: Tag taps only display contents without launching.\nClick to cycle mode.")

    def _toggle_execution_mode(self):
        auto = self.db.get_setting("auto_launch", True)
        read_only = self.db.get_setting("read_only_mode", False)

        if read_only:
            auto, read_only = True, False
            msg = "⚡ Execution Mode ON: Tag taps will launch actions."
        elif auto:
            auto, read_only = False, False
            msg = "🔍 Inspection Mode ON: Tag taps will only preview content."
        else:
            auto, read_only = True, True
            msg = "🔒 Read-Only Mode ON: Tag taps will NEVER launch anything."

        self.db.set_setting("auto_launch", auto)
        self.db.set_setting("read_only_mode", read_only)

        self.settings_tab.auto_launch_cb.setChecked(auto)
        self.settings_tab.read_only_cb.setChecked(read_only)

        self._update_mode_button()
        self.status_bar.showMessage(msg, 4000)

    @Slot(str, str)
    def _on_auto_detected(self, uid: str, process_name: str):
        try:
            self.db.set_auto_detected_process(uid, process_name)
            self.library_tab.refresh_table()
            self.status_bar.showMessage(
                f"🎯 Auto-detected kill target for {uid}: {process_name}", 6000
            )
        except Exception as e:
            print(f"[MainWindow] Failed to persist auto-detected process: {e}")

    def _on_detection_log(self, msg: str):
        """Route executor logs to both the status bar and a debug file."""
        self._on_log_event("info", msg)
        try:
            base = self.db.base_dir
            log_path = os.path.join(base, "app_data", "logs", "autodetect_debug.txt")
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                from datetime import datetime as _dt
                f.write(f"[{_dt.now().strftime('%H:%M:%S')}] {msg}\n")
        except Exception:
            pass

    @Slot(dict)
    def _on_tag_detected(self, info: dict):
        import time as _time
        uid = info.get("uid", "")
        now = _time.time()

        if uid and uid == self._last_action_uid and (now - self._last_action_time) < 2.0:
            return

        if uid and uid == self._active_uid:
            return

        self._last_action_uid = uid
        self._last_action_time = now
        self._active_uid = uid

        self.card_badge.setText(f"🔵 Tag: {uid}")
        self.card_badge.setObjectName("badgeCardActive")
        self.card_badge.style().unpolish(self.card_badge)
        self.card_badge.style().polish(self.card_badge)

        self.executor.on_tag_placed(uid)

        action = None
        effective_kill = False
        custom_mapping = self.db.get_tag_mapping(uid)

        ndef_kill = False
        ndef_action = None
        if info.get("actions"):
            first_act = info["actions"][0]
            ndef_kill = bool(first_act.get("kill_on_removal", False))
            ndef_action = NdefAction(
                action_type=first_act["action_type"],
                target=first_act["target"],
                display_name=first_act["display_name"],
                args=first_act.get("args", ""),
                raw_record=first_act.get("raw_record", ""),
                kill_on_removal=ndef_kill,
            )

        # Auto-create a library stub if the tag asks for kill but has no
        # library entry yet, so auto-detection results have somewhere to go.
        if (
            ndef_kill
            and custom_mapping is None
            and ndef_action is not None
            and ndef_action.action_type != "spotify"
        ):
            stub = {
                "uid": uid,
                "name": ndef_action.display_name or "Auto-detected tag",
                "action_type": ndef_action.action_type,
                "target": ndef_action.target,
                "args": ndef_action.args or "",
                "process_to_kill": "",
                "auto_detected_process": "",
                "kill_on_removal": True,
            }
            try:
                self.db.save_tag_mapping(uid, stub)
                self.library_tab.refresh_table()
                custom_mapping = self.db.get_tag_mapping(uid)
            except Exception as e:
                print(f"[MainWindow] Could not auto-create library stub: {e}")

        stored_auto = ""
        if custom_mapping:
            lib_kill = bool(custom_mapping.get("kill_on_removal", False))
            combined_kill = lib_kill or ndef_kill
            action = NdefAction(
                action_type=custom_mapping.get("action_type", "uri"),
                target=custom_mapping.get("target", ""),
                display_name=custom_mapping.get("name", "Library Action"),
                args=custom_mapping.get("args", ""),
                kill_on_removal=combined_kill,
            )
            if custom_mapping.get("process_to_kill"):
                action.process_to_kill = custom_mapping["process_to_kill"]
            stored_auto = custom_mapping.get("auto_detected_process", "") or ""
            effective_kill = combined_kill
        elif ndef_action is not None:
            action = ndef_action
            effective_kill = ndef_kill

        if not self.db.get_setting("kill_on_removal", False):
            effective_kill = False

        if action is not None and action.action_type == "spotify":
            effective_kill = False

        # Record what the tag wanted for the removal handler.
        self._last_tag_wanted_kill = (
            action is not None
            and action.action_type != "spotify"
            and bool(ndef_kill or (custom_mapping and custom_mapping.get("kill_on_removal", False)))
        )

        auto_launch = self.db.get_setting("auto_launch", True)
        read_only = self.db.get_setting("read_only_mode", False)

        status_text = "Ready"

        if read_only or not auto_launch:
            status_text = "Inspected (Safe Mode)"
            if action:
                ok, msg = self.executor.execute_action(
                    action, uid=uid, force=False, read_only=True, kill_on_removal=False
                )
                self.status_bar.showMessage(f"🔍 {msg}", 5000)
            else:
                self.status_bar.showMessage(f"🔍 Tag inspected: {uid} (no NDEF action)", 4000)
            self.scanner_tab.set_tag_detected(info, action, status_text)
            return

        if action:
            confirm_required = (
                action.action_type == "executable"
                and self.db.get_setting("confirm_exe", False)
            )
            proceed = True
            if confirm_required:
                reply = QMessageBox.question(
                    self,
                    "Execute Application Confirmation",
                    f"NFC tag requested launching executable:\n\n{action.target}\n\nDo you want to run this application?",
                    QMessageBox.Yes | QMessageBox.No
                )
                proceed = (reply == QMessageBox.Yes)

            if proceed:
                ok, msg = self.executor.execute_action(
                    action, uid=uid, read_only=False,
                    kill_on_removal=effective_kill,
                    stored_auto_process=stored_auto,
                )
                if ok:
                    status_text = "Auto-Launched"
                    self.status_bar.showMessage(f"✅ {msg}", 5000)
                    if not self.isVisible():
                        self.tray_icon.showMessage(
                            "NFC Action Triggered",
                            f"Launched: {action.display_name}",
                            QSystemTrayIcon.Information,
                            2000
                        )
                    if custom_mapping:
                        self.db.record_tag_used(uid)
                        self.library_tab.refresh_table()
                else:
                    if "Debounce" in msg:
                        status_text = "Debounced (Held)"
                    else:
                        status_text = f"Failed: {msg}"
                        self.status_bar.showMessage(f"⚠️ {msg}", 5000)
            else:
                status_text = "Execution Skipped by User"

        self.scanner_tab.set_tag_detected(info, action, status_text)

    @Slot(str)
    def _on_tag_removed(self, uid: str):
        if self._active_uid is None:
            return

        self.card_badge.setText("No Card")
        self.card_badge.setObjectName("badgeCardNone")
        self.card_badge.style().unpolish(self.card_badge)
        self.card_badge.style().polish(self.card_badge)

        tag_wanted_kill = self._last_tag_wanted_kill
        self._active_uid = None
        self._last_action_uid = None
        self._last_tag_wanted_kill = False

        had_tracked, _track_msg = self.executor.on_tag_removed(uid)
        self.scanner_tab.set_tag_removed(uid)

        kill_enabled = self.db.get_setting("kill_on_removal", False)

        if not kill_enabled:
            self.executor._clear_tracking(uid)
            self.status_bar.showMessage(f"Tag lifted: {uid}", 3000)
            return

        if not tag_wanted_kill:
            self.executor._clear_tracking(uid)
            self.status_bar.showMessage(f"Tag lifted: {uid}", 3000)
            return

        if had_tracked:
            custom_mapping = self.db.get_tag_mapping(uid)
            custom_proc = custom_mapping.get("process_to_kill") if custom_mapping else None

            ok, msg = self.executor.kill_process_for_tag(uid, custom_proc)
            if ok:
                self.status_bar.showMessage(f"🛑 {msg}", 5000)
            else:
                self.status_bar.showMessage(f"⚠️ Kill failed: {msg}", 5000)

            if not self.isVisible():
                self.tray_icon.showMessage(
                    "Process Terminated",
                    msg,
                    QSystemTrayIcon.Information,
                    2500
                )

            if self.db.get_setting("bsod_on_kill", True):
                self._show_bsod_image()
        else:
            delay = int(self.db.get_setting("auto_detect_delay_seconds", 15))
            self.status_bar.showMessage(
                f"⚠️ Tag requested kill but no target was tracked. "
                f"Keep the tag on the reader for ~{delay} s so auto-detection can finish.",
                8000
            )
            if self.db.get_setting("bsod_on_kill", True):
                self._show_bsod_image()

    def _show_bsod_image(self):
        candidates = [
            os.path.join(self.db.base_dir, "bsod.png"),
            os.path.join(self.db.app_data_dir, "bsod.png"),
            os.path.join(self.db.internal_dir, "bsod.png"),
        ]
        image_path = next((p for p in candidates if os.path.exists(p)), None)

        if not image_path:
            self.status_bar.showMessage(
                "⚠️ bsod.png not found in app folder, app_data/, or bundled assets.",
                5000
            )
            return

        duration_sec = int(self.db.get_setting("bsod_duration_seconds", 60))
        auto_close_ms = max(1000, duration_sec * 1000)

        try:
            BsodViewer.show_fullscreen(image_path, auto_close_ms=auto_close_ms)
        except Exception as e:
            self.status_bar.showMessage(f"⚠️ Could not show bsod.png: {e}", 5000)

    @Slot(object, str)
    def _on_manual_launch(self, action: NdefAction, uid: str):
        ok, msg = self.executor.execute_action(
            action, uid=uid, force=True, read_only=False, kill_on_removal=False
        )
        if ok:
            self.status_bar.showMessage(f"✅ {msg}", 5000)
            if self.db.get_tag_mapping(uid):
                self.db.record_tag_used(uid)
                self.library_tab.refresh_table()
        else:
            QMessageBox.critical(self, "Launch Error", msg)

    @Slot(str, object)
    def _on_save_tag_request(self, uid: str, action: NdefAction):
        self.tabs.setCurrentIndex(2)
        self.library_tab.open_add_dialog_for_tag(uid, action)

    @Slot()
    def _on_settings_updated(self):
        debounce = float(self.db.get_setting("debounce_seconds", 2.5))
        self.executor.debounce_seconds = debounce
        self.executor.auto_detect_enabled = self.db.get_setting("auto_detect_enabled", True)
        self.executor.auto_detect_delay_seconds = int(self.db.get_setting("auto_detect_delay_seconds", 15))
        self.worker.buzzer_on_tap = self.db.get_setting("buzzer_on_tap", True)
        self.worker.buzzer_on_write = self.db.get_setting("buzzer_on_write", True)
        self._update_mode_button()

    @Slot(str, str)
    def _on_log_event(self, level: str, text: str):
        if level == "error":
            self.status_bar.showMessage(f"❌ {text}", 6000)
        elif level == "warning":
            self.status_bar.showMessage(f"⚠️ {text}", 4000)
        elif level == "success":
            self.status_bar.showMessage(f"✅ {text}", 5000)
        else:
            self.status_bar.showMessage(text, 3000)
