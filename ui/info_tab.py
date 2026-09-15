"""
Info tab. Displays runtime, driver, storage, and hardware capability details.
"""

import sys
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QLabel
from PySide6.QtCore import Qt


class InfoTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        about_group = QGroupBox("About TagToolSH!")
        about_layout = QVBoxLayout(about_group)
        about_layout.setSpacing(6)
        about_layout.addWidget(QLabel(
            "TagToolSH! is a portable ACR122U NFC action launcher and tag studio.\n"
            "It reads and writes NFC tags, launches games and applications,\n"
            "and can terminate launched processes when a tag is removed."
        ))
        layout.addWidget(about_group)

        sys_group = QGroupBox("System & Hardware Information")
        sys_layout = QVBoxLayout(sys_group)
        sys_layout.setSpacing(6)

        py_ver = f"Python {sys.version.split()[0]}"
        frozen = getattr(sys, "frozen", False)
        mode = "Frozen build (bundled interpreter)" if frozen else "Script mode (portable Python)"
        sys_layout.addWidget(QLabel(f"• Runtime: {py_ver} — {mode}"))
        sys_layout.addWidget(QLabel("• Smart Card Driver: Microsoft PC/SC (winscard.dll)"))
        sys_layout.addWidget(QLabel("• Portable Data & Libs: app_data/ (self-contained)"))
        sys_layout.addWidget(QLabel("• Supported NFC Tags: Type 2 (NTAG213, NTAG215, NTAG216, MIFARE Ultralight)"))
        sys_layout.addWidget(QLabel("• Supported RFID Cards: Any ISO 14443-A card / fob (via Tag Library UID)"))

        layout.addWidget(sys_group)

        feat_group = QGroupBox("Feature Summary")
        feat_layout = QVBoxLayout(feat_group)
        feat_layout.setSpacing(6)
        feat_layout.addWidget(QLabel("• Per-tag kill-on-removal via secondary NDEF 'kill=1' record"))
        feat_layout.addWidget(QLabel("• Manual or auto-detected kill target per tag"))
        feat_layout.addWidget(QLabel("• Spotify tags are always excluded from taskkill"))
        feat_layout.addWidget(QLabel("• BSOD fullscreen image on successful kill (toggleable)"))
        feat_layout.addWidget(QLabel("• Three-way mode: Execution / Inspection / Read-Only"))
        feat_layout.addWidget(QLabel("• System tray operation with hidden startup"))
        layout.addWidget(feat_group)

        layout.addStretch()
