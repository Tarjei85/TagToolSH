"""
Scanner and Live Action Launcher tab.
Displays real-time card tap information, detected NDEF action, manual execution button,
and live tap history log.
"""

from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont

from ndef_handler import NdefAction


class ScannerTab(QWidget):
    # Signal to request manual launch or tab switch
    request_launch = Signal(object, str)      # (NdefAction, uid)
    request_save_tag = Signal(str, object)    # (uid, NdefAction)
    request_switch_writer = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_tag_info = None
        self.current_action = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # 1. Card Tap Overview Card
        card_group = QGroupBox("Active NFC Tag Status")
        card_layout = QVBoxLayout(card_group)

        # Top row: Status pill + UID + Type
        top_row = QHBoxLayout()

        self.status_pill = QLabel("Waiting for NFC Tag...")
        self.status_pill.setObjectName("badgeCardNone")
        top_row.addWidget(self.status_pill)

        self.uid_label = QLabel("UID: --:--:--:--")
        self.uid_label.setStyleSheet("font-weight: 700; font-size: 15px; color: #f3f4f6; margin-left: 10px;")
        top_row.addWidget(self.uid_label)

        self.copy_uid_btn = QPushButton("Copy UID")
        self.copy_uid_btn.setMaximumWidth(90)
        self.copy_uid_btn.clicked.connect(self._copy_uid)
        self.copy_uid_btn.setEnabled(False)
        top_row.addWidget(self.copy_uid_btn)

        top_row.addStretch()

        self.type_label = QLabel("Type: None")
        self.type_label.setStyleSheet("color: #9ca3af; font-size: 13px;")
        top_row.addWidget(self.type_label)

        card_layout.addLayout(top_row)

        # Action Display Frame
        self.action_frame = QFrame()
        self.action_frame.setStyleSheet("""
            QFrame {
                background-color: #15161b;
                border: 1px solid #282a34;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        action_layout = QVBoxLayout(self.action_frame)

        # Badge and Title
        act_header = QHBoxLayout()
        self.action_badge = QLabel("NO ACTION")
        self.action_badge.setStyleSheet("background-color: #374151; color: #d1d5db; padding: 4px 10px; border-radius: 6px; font-weight: bold;")
        act_header.addWidget(self.action_badge)

        self.action_title = QLabel("Tap an NFC card or tag on the ACR122U reader")
        self.action_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #e5e7eb; margin-left: 8px;")
        act_header.addWidget(self.action_title)
        act_header.addStretch()
        action_layout.addLayout(act_header)

        # Target link / path display
        self.action_target = QLabel("No action payload detected yet.")
        self.action_target.setStyleSheet("color: #9ca3af; font-family: 'Consolas', monospace; font-size: 12px; margin-top: 4px;")
        self.action_target.setWordWrap(True)
        action_layout.addWidget(self.action_target)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 8, 0, 0)

        self.launch_btn = QPushButton("▶ Launch Action Now")
        self.launch_btn.setObjectName("primaryButton")
        self.launch_btn.setEnabled(False)
        self.launch_btn.clicked.connect(self._on_launch_clicked)
        btn_row.addWidget(self.launch_btn)

        self.save_tag_btn = QPushButton("⭐ Save to Tag Library")
        self.save_tag_btn.setEnabled(False)
        self.save_tag_btn.clicked.connect(self._on_save_clicked)
        btn_row.addWidget(self.save_tag_btn)

        self.write_tag_btn = QPushButton("✏️ Encode / Overwrite Tag")
        self.write_tag_btn.setEnabled(False)
        self.write_tag_btn.clicked.connect(self.request_switch_writer.emit)
        btn_row.addWidget(self.write_tag_btn)

        btn_row.addStretch()
        action_layout.addLayout(btn_row)

        card_layout.addWidget(self.action_frame)
        main_layout.addWidget(card_group)

        # 2. Tap Activity Log Group
        log_group = QGroupBox("Recent NFC Card Activity Log")
        log_layout = QVBoxLayout(log_group)

        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(["Timestamp", "Tag UID", "Tag Type", "Action / Target", "Status"])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.history_table.verticalHeader().setVisible(False)
        log_layout.addWidget(self.history_table)

        tbl_btn_row = QHBoxLayout()
        clear_log_btn = QPushButton("Clear Activity Log")
        clear_log_btn.setMaximumWidth(140)
        clear_log_btn.clicked.connect(self.clear_history)
        tbl_btn_row.addWidget(clear_log_btn)
        tbl_btn_row.addStretch()
        log_layout.addLayout(tbl_btn_row)

        main_layout.addWidget(log_group)

    def set_tag_detected(self, info: dict, action: NdefAction, execution_status: str):
        """Updates UI when a tag is detected and decoded."""
        self.current_tag_info = info
        self.current_action = action

        uid = info.get("uid", "Unknown")
        tag_type = info.get("tag_type", "NFC Tag")
        capacity = info.get("capacity_bytes", 0)

        # Update status pill
        self.status_pill.setText("Card Present")
        self.status_pill.setObjectName("badgeCardActive")
        self.status_pill.style().unpolish(self.status_pill)
        self.status_pill.style().polish(self.status_pill)

        self.uid_label.setText(f"UID: {uid}")
        self.copy_uid_btn.setEnabled(True)
        self.type_label.setText(f"Type: {tag_type} ({capacity}B)")

        self.save_tag_btn.setEnabled(True)
        self.write_tag_btn.setEnabled(True)

        if action:
            self.launch_btn.setEnabled(True)
            badge_text = action.action_type.upper()
            color = "#4f46e5"

            if action.action_type == "spotify":
                badge_text = "🎵 SPOTIFY"
                color = "#10b981"
            elif action.action_type == "steam":
                badge_text = "🎮 STEAM GAME"
                color = "#3b82f6"
            elif action.action_type == "executable":
                badge_text = "💻 EXECUTABLE (.EXE)"
                color = "#8b5cf6"
            elif action.action_type in ("uri", "url"):
                badge_text = "🌐 WEB LINK"
                color = "#f59e0b"

            self.action_badge.setText(badge_text)
            self.action_badge.setStyleSheet(f"background-color: {color}; color: #ffffff; padding: 4px 10px; border-radius: 6px; font-weight: bold;")
            self.action_title.setText(action.display_name)
            target_desc = action.target
            if action.args:
                target_desc += f"  (Args: {action.args})"
            self.action_target.setText(target_desc)

        else:
            self.launch_btn.setEnabled(False)
            self.action_badge.setText("BLANK / NO NDEF")
            self.action_badge.setStyleSheet("background-color: #374151; color: #9ca3af; padding: 4px 10px; border-radius: 6px; font-weight: bold;")
            self.action_title.setText("NFC Tag detected, but contains no NDEF actions")
            self.action_target.setText("You can encode this tag in the 'Tag Studio' tab or assign a custom action in 'Tag Library'.")

        # Add to history table
        self._add_history_row(uid, tag_type, action, execution_status)

    def set_tag_removed(self, uid: str):
        """Updates UI when a tag is lifted from the reader."""
        self.status_pill.setText("Waiting for NFC Tag...")
        self.status_pill.setObjectName("badgeCardNone")
        self.status_pill.style().unpolish(self.status_pill)
        self.status_pill.style().polish(self.status_pill)

    def _copy_uid(self):
        if self.current_tag_info:
            uid = self.current_tag_info.get("uid", "")
            QApplication.clipboard().setText(uid)

    def _on_launch_clicked(self):
        if self.current_action and self.current_tag_info:
            uid = self.current_tag_info.get("uid", "")
            self.request_launch.emit(self.current_action, uid)

    def _on_save_clicked(self):
        if self.current_tag_info:
            uid = self.current_tag_info.get("uid", "")
            self.request_save_tag.emit(uid, self.current_action)

    def _add_history_row(self, uid: str, tag_type: str, action: NdefAction, status: str):
        now = datetime.now().strftime("%H:%M:%S")
        row = self.history_table.rowCount()
        self.history_table.insertRow(row)

        target_desc = action.target if action else "No NDEF Action"
        if action and action.args:
            target_desc += f" [{action.args}]"

        self.history_table.setItem(row, 0, QTableWidgetItem(now))
        self.history_table.setItem(row, 1, QTableWidgetItem(uid))
        self.history_table.setItem(row, 2, QTableWidgetItem(tag_type))
        self.history_table.setItem(row, 3, QTableWidgetItem(target_desc))

        status_item = QTableWidgetItem(status)
        if "Launch" in status or "OK" in status:
            status_item.setForeground(QColor("#34d399"))
        elif "Debounce" in status:
            status_item.setForeground(QColor("#9ca3af"))
        elif "Error" in status or "Failed" in status:
            status_item.setForeground(QColor("#f87171"))
        self.history_table.setItem(row, 4, status_item)

        self.history_table.scrollToBottom()

    def clear_history(self):
        self.history_table.setRowCount(0)
