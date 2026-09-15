"""
Tag Studio / Encoder tab.
Allows creating and encoding NFC tags with Spotify URIs, Steam Game IDs,
direct Executable (.exe / .bat / .lnk) actions, and Web links.
Includes an optional per-tag 'kill on removal' flag encoded as a secondary
NDEF record.
"""

import os
import re
from typing import Tuple
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGroupBox, QRadioButton, QButtonGroup, QFileDialog,
    QProgressBar, QFrame, QMessageBox, QApplication, QTabWidget,
    QCheckBox
)
from PySide6.QtCore import Qt, Signal

from ndef_handler import encode_action_to_type2_tlv, parse_action_from_string
from action_executor import ActionExecutor


class WriterTab(QWidget):
    request_queue_write = Signal(bytes)
    request_cancel_write = Signal()

    def __init__(self, action_executor: ActionExecutor, parent=None):
        super().__init__(parent)
        self.executor = action_executor
        self.is_waiting_for_card = False
        self.current_tlv = b""
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        action_group = QGroupBox("1. Select & Configure Action to Encode")
        group_layout = QVBoxLayout(action_group)

        self.action_tabs = QTabWidget()
        self.action_tabs.setStyleSheet("QTabBar::tab { padding: 8px 16px; }")

        self.spotify_widget = self._create_spotify_tab()
        self.action_tabs.addTab(self.spotify_widget, "🎵 Spotify Music")

        self.steam_widget = self._create_steam_tab()
        self.action_tabs.addTab(self.steam_widget, "🎮 Steam Game")

        self.exe_widget = self._create_exe_tab()
        self.action_tabs.addTab(self.exe_widget, "💻 Direct Executable (.exe)")

        self.uri_widget = self._create_uri_tab()
        self.action_tabs.addTab(self.uri_widget, "🌐 Web / Custom URI")

        self.text_widget = self._create_text_tab()
        self.action_tabs.addTab(self.text_widget, "📝 Custom Text")

        group_layout.addWidget(self.action_tabs)
        main_layout.addWidget(action_group)

        write_group = QGroupBox("2. Encode to NFC Tag")
        write_layout = QVBoxLayout(write_group)

        # Per-tag kill-on-removal option
        self.kill_on_removal_cb = QCheckBox(
            "Kill launched process when this tag is removed (writes a 'kill=1' record onto the tag)"
        )
        self.kill_on_removal_cb.setChecked(False)
        self.kill_on_removal_cb.setToolTip(
            "Encodes a secondary NDEF record onto the tag. When this tag is read back "
            "and the global 'Terminate on tag removal' setting is enabled, the launched "
            "process will be killed on removal. Spotify tags are always excluded."
        )
        write_layout.addWidget(self.kill_on_removal_cb)

        self.preview_frame = QFrame()
        self.preview_frame.setStyleSheet("background-color: #15161b; border: 1px solid #282a34; border-radius: 6px; padding: 10px;")
        prev_layout = QVBoxLayout(self.preview_frame)
        self.preview_label = QLabel("Configure an action above, then click 'Write to NFC Tag'.")
        self.preview_label.setStyleSheet("color: #9ca3af; font-family: 'Consolas', monospace;")
        self.preview_label.setWordWrap(True)
        prev_layout.addWidget(self.preview_label)
        write_layout.addWidget(self.preview_frame)

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #15161b;
                border: 1px solid #282a34;
                border-radius: 6px;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
                height: 22px;
            }
            QProgressBar::chunk {
                background-color: #4f46e5;
                border-radius: 5px;
            }
        """)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        write_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("color: #e5e7eb; font-weight: 600;")
        write_layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        self.write_btn = QPushButton("⚡ Write to NFC Tag")
        self.write_btn.setObjectName("successButton")
        self.write_btn.clicked.connect(self._on_write_clicked)
        btn_row.addWidget(self.write_btn)

        self.cancel_btn = QPushButton("Cancel Write")
        self.cancel_btn.setObjectName("dangerButton")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        btn_row.addWidget(self.cancel_btn)

        btn_row.addStretch()
        write_layout.addLayout(btn_row)

        main_layout.addWidget(write_group)

    def _create_spotify_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 14, 10, 10)

        lbl = QLabel("Enter Spotify Track, Album, or Playlist URI / Web Link:")
        lbl.setStyleSheet("color: #d1d5db; font-weight: 600;")
        layout.addWidget(lbl)

        self.spotify_input = QLineEdit()
        self.spotify_input.setPlaceholderText("e.g. spotify:track:7AlmVLuvYCTYRpn9PNoK5z or https://open.spotify.com/playlist/...")
        layout.addWidget(self.spotify_input)

        row = QHBoxLayout()
        test_btn = QPushButton("▶ Test Spotify Link")
        test_btn.clicked.connect(self._test_spotify)
        row.addWidget(test_btn)

        paste_btn = QPushButton("📋 Paste from Clipboard")
        paste_btn.clicked.connect(lambda: self.spotify_input.setText(QApplication.clipboard().text().strip()))
        row.addWidget(paste_btn)

        row.addStretch()
        layout.addLayout(row)

        hint = QLabel("💡 Tip: In Spotify, click '...' on any song or playlist -> Share -> Copy Song Link or Copy Spotify URI.")
        hint.setStyleSheet("color: #6b7280; font-size: 11px; margin-top: 4px;")
        layout.addWidget(hint)

        return w

    def _create_steam_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 14, 10, 10)

        lbl = QLabel("Enter Steam Game App ID or Store Link:")
        lbl.setStyleSheet("color: #d1d5db; font-weight: 600;")
        layout.addWidget(lbl)

        self.steam_input = QLineEdit()
        self.steam_input.setPlaceholderText("e.g. 730 (CS2), 440 (TF2), 1086940 (Baldur's Gate 3), or steam://rungameid/730")
        layout.addWidget(self.steam_input)

        row = QHBoxLayout()
        test_btn = QPushButton("▶ Test Steam Launch")
        test_btn.clicked.connect(self._test_steam)
        row.addWidget(test_btn)

        paste_btn = QPushButton("📋 Paste")
        paste_btn.clicked.connect(lambda: self.steam_input.setText(QApplication.clipboard().text().strip()))
        row.addWidget(paste_btn)

        row.addStretch()
        layout.addLayout(row)

        hint = QLabel("💡 Tip: Find the App ID in any Steam store URL (e.g. store.steampowered.com/app/730 -> 730).")
        hint.setStyleSheet("color: #6b7280; font-size: 11px; margin-top: 4px;")
        layout.addWidget(hint)

        return w

    def _create_exe_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 14, 10, 10)

        lbl = QLabel("Select Executable File (.exe, .bat, .cmd, .lnk):")
        lbl.setStyleSheet("color: #d1d5db; font-weight: 600;")
        layout.addWidget(lbl)

        file_row = QHBoxLayout()
        self.exe_path_input = QLineEdit()
        self.exe_path_input.setPlaceholderText("C:\\Games\\Game.exe or Windows Shortcut (.lnk)")
        file_row.addWidget(self.exe_path_input)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_executable)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        args_lbl = QLabel("Optional Launch Arguments / Parameters:")
        args_lbl.setStyleSheet("color: #9ca3af; font-size: 12px; margin-top: 6px;")
        layout.addWidget(args_lbl)

        self.exe_args_input = QLineEdit()
        self.exe_args_input.setPlaceholderText("e.g. -fullscreen --novid (leave empty if none)")
        layout.addWidget(self.exe_args_input)

        opt_lbl = QLabel("NFC Encoding Format:")
        opt_lbl.setStyleSheet("color: #9ca3af; font-size: 12px; margin-top: 6px;")
        layout.addWidget(opt_lbl)

        format_row = QHBoxLayout()
        self.format_group = QButtonGroup(self)
        self.radio_uri = QRadioButton("Standard NFC URI (file:///C:/...) [Recommended]")
        self.radio_uri.setChecked(True)
        self.radio_text = QRadioButton("Text Path (C:\\...) [Required if using custom arguments]")
        self.format_group.addButton(self.radio_uri)
        self.format_group.addButton(self.radio_text)
        format_row.addWidget(self.radio_uri)
        format_row.addWidget(self.radio_text)
        format_row.addStretch()
        layout.addLayout(format_row)

        test_row = QHBoxLayout()
        test_btn = QPushButton("▶ Test Launch Executable")
        test_btn.clicked.connect(self._test_executable)
        test_row.addWidget(test_btn)
        test_row.addStretch()
        layout.addLayout(test_row)

        return w

    def _create_uri_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 14, 10, 10)

        lbl = QLabel("Enter Web URL or Custom Protocol URI:")
        lbl.setStyleSheet("color: #d1d5db; font-weight: 600;")
        layout.addWidget(lbl)

        self.uri_input = QLineEdit()
        self.uri_input.setPlaceholderText("e.g. https://google.com, discord://..., or epic://...")
        layout.addWidget(self.uri_input)

        row = QHBoxLayout()
        test_btn = QPushButton("▶ Test Open URI")
        test_btn.clicked.connect(self._test_uri)
        row.addWidget(test_btn)
        row.addStretch()
        layout.addLayout(row)

        return w

    def _create_text_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 14, 10, 10)

        lbl = QLabel("Enter Custom Text or Command:")
        lbl.setStyleSheet("color: #d1d5db; font-weight: 600;")
        layout.addWidget(lbl)

        self.custom_text_input = QLineEdit()
        self.custom_text_input.setPlaceholderText("e.g. launch:notepad.exe or arbitrary text")
        layout.addWidget(self.custom_text_input)

        return w

    # -------- Test buttons (never track, never kill) -------- #

    def _test_spotify(self):
        val = self.spotify_input.text().strip()
        if not val:
            QMessageBox.warning(self, "Input Required", "Please enter a Spotify link or URI first.")
            return
        action = parse_action_from_string(val)
        ok, msg = self.executor.execute_action(action, force=True, kill_on_removal=False)
        if not ok:
            QMessageBox.critical(self, "Launch Error", msg)

    def _test_steam(self):
        val = self.steam_input.text().strip()
        if not val:
            QMessageBox.warning(self, "Input Required", "Please enter a Steam Game App ID or URL first.")
            return
        action = parse_action_from_string(f"steam://rungameid/{val}" if val.isdigit() else val)
        ok, msg = self.executor.execute_action(action, force=True, kill_on_removal=False)
        if not ok:
            QMessageBox.critical(self, "Launch Error", msg)

    def _test_executable(self):
        val = self.exe_path_input.text().strip()
        args = self.exe_args_input.text().strip()
        if not val:
            QMessageBox.warning(self, "Input Required", "Please select an executable file first.")
            return
        from ndef_handler import NdefAction
        action = NdefAction("executable", val, args=args, display_name=os.path.basename(val))
        ok, msg = self.executor.execute_action(action, force=True, kill_on_removal=False)
        if not ok:
            QMessageBox.critical(self, "Launch Error", msg)

    def _test_uri(self):
        val = self.uri_input.text().strip()
        if not val:
            QMessageBox.warning(self, "Input Required", "Please enter a URI first.")
            return
        action = parse_action_from_string(val)
        ok, msg = self.executor.execute_action(action, force=True, kill_on_removal=False)
        if not ok:
            QMessageBox.critical(self, "Launch Error", msg)

    def _browse_executable(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Executable or Shortcut",
            "",
            "Executable Files (*.exe *.bat *.cmd *.lnk *.ps1);;All Files (*.*)"
        )
        if path:
            norm_path = os.path.normpath(path)
            self.exe_path_input.setText(norm_path)

    # -------- Write routines -------- #

    def _build_current_payload(self) -> Tuple[str, str, str, bool]:
        idx = self.action_tabs.currentIndex()

        if idx == 0:
            val = self.spotify_input.text().strip()
            if not val:
                raise ValueError("Please provide a Spotify URI or web link.")
            return "spotify", val, "", True

        elif idx == 1:
            val = self.steam_input.text().strip()
            if not val:
                raise ValueError("Please provide a Steam App ID or link.")
            if val.isdigit():
                val = f"steam://rungameid/{val}"
            return "steam", val, "", True

        elif idx == 2:
            path = self.exe_path_input.text().strip()
            args = self.exe_args_input.text().strip()
            if not path:
                raise ValueError("Please select an executable path.")
            use_uri = self.radio_uri.isChecked() and not bool(args)
            return "executable", path, args, use_uri

        elif idx == 3:
            val = self.uri_input.text().strip()
            if not val:
                raise ValueError("Please provide a URL or URI.")
            return "uri", val, "", True

        elif idx == 4:
            val = self.custom_text_input.text().strip()
            if not val:
                raise ValueError("Please enter text content.")
            return "text", val, "", False

        raise ValueError("Unknown action tab")

    def _on_write_clicked(self):
        try:
            action_type, target, args, use_file_uri = self._build_current_payload()

            # Spotify tags never carry the kill flag, even if the user ticked the box
            kill_flag = self.kill_on_removal_cb.isChecked()
            if action_type == "spotify":
                kill_flag = False

            tlv = encode_action_to_type2_tlv(
                action_type, target, args=args,
                use_file_uri=use_file_uri,
                kill_on_removal=kill_flag,
            )
            self.current_tlv = tlv

            self.is_waiting_for_card = True
            self.write_btn.setEnabled(False)
            self.cancel_btn.setVisible(True)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)

            kill_note = "  (+ kill=1 record)" if kill_flag else ""
            self.preview_label.setText(
                f"Payload: {action_type.upper()}\n"
                f"Target:  {target}\n"
                f"Size:    {len(tlv)} bytes ({len(tlv)//4} pages){kill_note}\n"
                f"Compatible: NTAG213 (144B), NTAG215 (504B), NTAG216 (888B)"
            )

            self.status_label.setText("⏳ Waiting for NFC tag on reader... Place your tag on the ACR122U now.")
            self.status_label.setStyleSheet("color: #60a5fa; font-weight: bold;")

            self.request_queue_write.emit(tlv)

        except Exception as e:
            QMessageBox.warning(self, "Invalid Input", str(e))

    def _on_cancel_clicked(self):
        self.is_waiting_for_card = False
        self.write_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Status: Write cancelled.")
        self.status_label.setStyleSheet("color: #9ca3af; font-weight: 600;")
        self.request_cancel_write.emit()

    def set_write_progress(self, msg: str):
        self.status_label.setText(f"⚙️ {msg}")
        self.status_label.setStyleSheet("color: #fbbf24; font-weight: bold;")

    def set_write_completed(self, success: bool, message: str):
        self.is_waiting_for_card = False
        self.write_btn.setEnabled(True)
        self.cancel_btn.setVisible(False)
        self.progress_bar.setVisible(False)

        if success:
            self.status_label.setText(f"✅ {message}")
            self.status_label.setStyleSheet("color: #34d399; font-weight: bold;")
            QMessageBox.information(self, "Encoding Successful", message)
        else:
            self.status_label.setText(f"❌ {message}")
            self.status_label.setStyleSheet("color: #f87171; font-weight: bold;")
            QMessageBox.critical(self, "Encoding Failed", message)