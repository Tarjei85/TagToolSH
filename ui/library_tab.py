"""
Tag Library / UID Mapping manager tab.
Allows mapping specific NFC Tag UIDs to custom actions.
Shows both manual process_to_kill overrides and auto-detected process names.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QLineEdit, QComboBox, QFileDialog, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from database import DatabaseManager
from action_executor import ActionExecutor
from ndef_handler import NdefAction


class TagEditDialog(QDialog):
    def __init__(self, parent=None, uid: str = "", tag_data: dict = None):
        super().__init__(parent)
        self.setWindowTitle("Configure Tag Action Mapping")
        self.setMinimumWidth(480)
        self.tag_data = tag_data or {}
        self.uid = uid or self.tag_data.get("uid", "")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Tag UID:"))
        self.uid_input = QLineEdit(self.uid)
        self.uid_input.setPlaceholderText("e.g. 53:EE:33:19:64:00:01")
        layout.addWidget(self.uid_input)

        layout.addWidget(QLabel("Tag Friendly Name / Label:"))
        self.name_input = QLineEdit(self.tag_data.get("name", ""))
        self.name_input.setPlaceholderText("e.g. Living Room Spotify Tag, Cyberpunk 2077")
        layout.addWidget(self.name_input)

        layout.addWidget(QLabel("Action Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Spotify", "Steam", "Executable", "Web URI", "Command"])
        current_type = self.tag_data.get("action_type", "Spotify").capitalize()
        idx = self.type_combo.findText(current_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addWidget(self.type_combo)

        layout.addWidget(QLabel("Target (URI, App ID, or File Path):"))
        target_row = QHBoxLayout()
        self.target_input = QLineEdit(self.tag_data.get("target", ""))
        target_row.addWidget(self.target_input)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_file)
        target_row.addWidget(self.browse_btn)
        layout.addLayout(target_row)

        self.args_label = QLabel("Optional Arguments:")
        layout.addWidget(self.args_label)
        self.args_input = QLineEdit(self.tag_data.get("args", ""))
        layout.addWidget(self.args_input)

        # Manual override
        layout.addWidget(QLabel("Manual process name to kill on card removal (optional):"))
        self.kill_input = QLineEdit(self.tag_data.get("process_to_kill", ""))
        self.kill_input.setPlaceholderText(
            "e.g. cs2.exe — leave blank to auto-detect, or 'none' to disable tracking"
        )
        layout.addWidget(self.kill_input)

        # Auto-detected (read-only display)
        auto_val = self.tag_data.get("auto_detected_process", "") or "(none yet)"
        auto_lbl = QLabel(f"Auto-detected process: {auto_val}")
        auto_lbl.setStyleSheet("color: #9ca3af; font-size: 11px;")
        layout.addWidget(auto_lbl)

        self.kill_on_removal_cb = QCheckBox(
            "Kill launched process when this tag is removed"
        )
        self.kill_on_removal_cb.setChecked(bool(self.tag_data.get("kill_on_removal", False)))
        self.kill_on_removal_cb.setToolTip(
            "When enabled and the global 'Terminate on tag removal' setting is on, "
            "lifting this tag kills the process it launched. Spotify tags are always excluded."
        )
        layout.addWidget(self.kill_on_removal_cb)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._validate_and_accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        self._on_type_changed()

    def _on_type_changed(self):
        t = self.type_combo.currentText()
        is_exe = (t == "Executable")
        self.browse_btn.setVisible(is_exe)
        self.args_label.setVisible(is_exe or t == "Command")
        self.args_input.setVisible(is_exe or t == "Command")

        if t == "Spotify":
            self.target_input.setPlaceholderText("spotify:playlist:... or https://open.spotify.com/...")
        elif t == "Steam":
            self.target_input.setPlaceholderText("Steam App ID (e.g. 730) or steam://rungameid/730")
        elif t == "Executable":
            self.target_input.setPlaceholderText("C:\\Games\\game.exe")
        elif t == "Web URI":
            self.target_input.setPlaceholderText("https://...")
        elif t == "Command":
            self.target_input.setPlaceholderText("cmd.exe or command string")

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Executable",
            "",
            "Executable Files (*.exe *.bat *.cmd *.lnk *.ps1);;All Files (*.*)"
        )
        if path:
            norm_path = os.path.normpath(path)
            self.target_input.setText(norm_path)
            if not self.kill_input.text().strip():
                self.kill_input.setText(os.path.basename(norm_path))

    def _validate_and_accept(self):
        uid = self.uid_input.text().strip()
        target = self.target_input.text().strip()

        if not uid:
            QMessageBox.warning(self, "Validation Error", "Tag UID is required.")
            return
        if not target:
            QMessageBox.warning(self, "Validation Error", "Target is required.")
            return

        self.accept()

    def get_result(self) -> dict:
        result = {
            "uid": self.uid_input.text().strip().upper(),
            "name": self.name_input.text().strip() or "Unnamed Tag",
            "action_type": self.type_combo.currentText().lower().replace("web ", ""),
            "target": self.target_input.text().strip(),
            "args": self.args_input.text().strip(),
            "process_to_kill": self.kill_input.text().strip(),
            "kill_on_removal": self.kill_on_removal_cb.isChecked(),
        }
        # Preserve auto_detected_process across edits
        if "auto_detected_process" in self.tag_data:
            result["auto_detected_process"] = self.tag_data["auto_detected_process"]
        return result


class LibraryTab(QWidget):
    def __init__(self, db: DatabaseManager, executor: ActionExecutor, parent=None):
        super().__init__(parent)
        self.db = db
        self.executor = executor
        self.init_ui()
        self.refresh_table()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        desc = QLabel(
            "The Tag Library allows you to assign custom actions to any NFC Tag UID.\n"
            "Works for write-protected tags, hotel cards, key fobs, or custom shortcuts."
        )
        desc.setObjectName("hintLabel")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Tag Name", "UID", "Type", "Target", "Args", "Kill", "Auto-Detected", "Last Used"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("➕ Add Tag Mapping")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self._on_add_clicked)
        btn_row.addWidget(add_btn)

        edit_btn = QPushButton("✏️ Edit Selected")
        edit_btn.clicked.connect(self._on_edit_clicked)
        btn_row.addWidget(edit_btn)

        del_btn = QPushButton("🗑️ Delete Selected")
        del_btn.setObjectName("dangerButton")
        del_btn.clicked.connect(self._on_delete_clicked)
        btn_row.addWidget(del_btn)

        btn_row.addSpacing(20)

        test_btn = QPushButton("▶ Test Selected Action")
        test_btn.clicked.connect(self._on_test_clicked)
        btn_row.addWidget(test_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    def refresh_table(self):
        tags = self.db.get_all_tags()
        self.table.setRowCount(0)

        for uid, data in tags.items():
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(data.get("name", "Unnamed")))
            self.table.setItem(row, 1, QTableWidgetItem(uid))
            self.table.setItem(row, 2, QTableWidgetItem(data.get("action_type", "").upper()))
            self.table.setItem(row, 3, QTableWidgetItem(data.get("target", "")))
            self.table.setItem(row, 4, QTableWidgetItem(data.get("args", "")))

            kill_item = QTableWidgetItem("✓" if data.get("kill_on_removal") else "—")
            if data.get("kill_on_removal"):
                kill_item.setForeground(QColor("#34d399"))
            self.table.setItem(row, 5, kill_item)

            manual = data.get("process_to_kill", "") or ""
            auto = data.get("auto_detected_process", "") or ""
            if manual.lower() in ("none", "off", "disable", "disabled"):
                auto_disp = "(disabled)"
                auto_color = "#9ca3af"
            elif manual:
                auto_disp = manual + " (manual)"
                auto_color = "#fbbf24"
            elif auto:
                auto_disp = auto
                auto_color = "#34d399"
            else:
                auto_disp = "—"
                auto_color = "#9ca3af"

            auto_item = QTableWidgetItem(auto_disp)
            auto_item.setForeground(QColor(auto_color))
            self.table.setItem(row, 6, auto_item)

            last_used = data.get("last_used", "Never")
            if "T" in last_used:
                last_used = last_used.split("T")[0] + " " + last_used.split("T")[1][:5]
            self.table.setItem(row, 7, QTableWidgetItem(last_used))

    def _on_add_clicked(self):
        dlg = TagEditDialog(self)
        if dlg.exec():
            res = dlg.get_result()
            self.db.save_tag_mapping(res["uid"], res)
            self.refresh_table()

    def open_add_dialog_for_tag(self, uid: str, action: NdefAction = None):
        default_data = {}
        if action:
            default_data = {
                "name": action.display_name,
                "action_type": action.action_type,
                "target": action.target,
                "args": action.args,
                "kill_on_removal": getattr(action, "kill_on_removal", False),
            }
        dlg = TagEditDialog(self, uid=uid, tag_data=default_data)
        if dlg.exec():
            res = dlg.get_result()
            self.db.save_tag_mapping(res["uid"], res)
            self.refresh_table()

    def _on_edit_clicked(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Select Tag", "Please select a tag from the table to edit.")
            return

        uid = self.table.item(row, 1).text()
        tag_data = self.db.get_tag_mapping(uid)
        if not tag_data:
            return

        dlg = TagEditDialog(self, uid=uid, tag_data=tag_data)
        if dlg.exec():
            res = dlg.get_result()
            self.db.save_tag_mapping(res["uid"], res)
            self.refresh_table()

    def _on_delete_clicked(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Select Tag", "Please select a tag from the table to delete.")
            return

        uid = self.table.item(row, 1).text()
        name = self.table.item(row, 0).text()

        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete mapping for '{name}' ({uid})?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.db.delete_tag_mapping(uid)
            self.refresh_table()

    def _on_test_clicked(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Select Tag", "Please select a tag to test.")
            return

        uid = self.table.item(row, 1).text()
        data = self.db.get_tag_mapping(uid)
        if not data:
            return

        action = NdefAction(
            action_type=data.get("action_type", "uri"),
            target=data.get("target", ""),
            display_name=data.get("name", ""),
            args=data.get("args", ""),
            kill_on_removal=bool(data.get("kill_on_removal", False)),
        )
        ok, msg = self.executor.execute_action(action, force=True, kill_on_removal=False)
        if not ok:
            QMessageBox.critical(self, "Execution Failed", msg)
        else:
            self.db.record_tag_used(uid)
            self.refresh_table()
