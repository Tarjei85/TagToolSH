"""
Dark theme stylesheet and UI constants for TagToolSH!.
"""

DARK_THEME_QSS = """
QMainWindow, QDialog {
    background-color: #121316;
    color: #f3f4f6;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    font-size: 13px;
}

QWidget {
    color: #f3f4f6;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    font-size: 13px;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #282a30;
    background-color: #18191d;
    border-radius: 8px;
    top: -1px;
}

QTabBar::tab {
    background: #121316;
    color: #9ca3af;
    padding: 10px 22px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 4px;
    font-weight: 600;
    font-size: 13px;
}

QTabBar::tab:selected {
    background: #18191d;
    color: #ffffff;
    border-bottom: 3px solid #6366f1;
}

QTabBar::tab:hover:!selected {
    background: #1c1d24;
    color: #d1d5db;
}

/* Scroll area (Settings tab) */
QScrollArea {
    background-color: #18191d;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: #18191d;
}

/* Collapsible section header */
QToolButton#sectionHeader {
    background-color: #1e1f25;
    color: #e5e7eb;
    border: 1px solid #2d2f38;
    border-radius: 6px;
    padding: 10px 14px;
    font-weight: 700;
    font-size: 13px;
    text-align: left;
}

QToolButton#sectionHeader:hover {
    background-color: #262832;
    border-color: #3a3d4a;
}

QToolButton#sectionHeader:checked {
    background-color: #232630;
    border-color: #3a3d4a;
    border-bottom-left-radius: 0px;
    border-bottom-right-radius: 0px;
}

/* Collapsible section content */
QFrame#sectionContent {
    background-color: #1a1b21;
    border: 1px solid #2d2f38;
    border-top: none;
    border-bottom-left-radius: 6px;
    border-bottom-right-radius: 6px;
    padding: 4px 0px;
}

/* Group Boxes */
QGroupBox {
    background-color: #1e1f25;
    border: 1px solid #2d2f38;
    border-radius: 8px;
    margin-top: 18px;
    padding: 18px 14px 14px 14px;
    font-weight: bold;
    color: #e5e7eb;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    background-color: #282a34;
    border-radius: 4px;
    color: #a5b4fc;
}

/* Buttons */
QPushButton {
    background-color: #313442;
    color: #f3f4f6;
    border: 1px solid #404456;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #3e4254;
    border-color: #555b73;
}

QPushButton:pressed {
    background-color: #262833;
}

QPushButton:disabled {
    background-color: #1a1b20;
    color: #4b5563;
    border-color: #26272e;
}

QPushButton#primaryButton {
    background-color: #4f46e5;
    border: 1px solid #6366f1;
    color: #ffffff;
    font-size: 14px;
    padding: 10px 20px;
}

QPushButton#primaryButton:hover {
    background-color: #4338ca;
}

QPushButton#successButton {
    background-color: #059669;
    border: 1px solid #10b981;
    color: #ffffff;
    font-size: 14px;
    padding: 10px 20px;
}

QPushButton#successButton:hover {
    background-color: #047857;
}

QPushButton#dangerButton {
    background-color: #dc2626;
    border: 1px solid #ef4444;
    color: #ffffff;
}

QPushButton#dangerButton:hover {
    background-color: #b91c1c;
}

/* Inputs */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
    background-color: #131418;
    color: #f9fafb;
    border: 1px solid #373a46;
    border-radius: 6px;
    padding: 7px 10px;
    selection-background-color: #4f46e5;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {
    border: 1px solid #6366f1;
    background-color: #161820;
}

/* Table */
QTableWidget {
    background-color: #15161a;
    color: #e5e7eb;
    border: 1px solid #282a32;
    border-radius: 6px;
    gridline-color: #22242a;
    selection-background-color: #312e81;
    selection-color: #ffffff;
}

QTableWidget::item {
    padding: 6px;
}

QHeaderView::section {
    background-color: #1c1d23;
    color: #9ca3af;
    padding: 8px 6px;
    border: none;
    border-bottom: 1px solid #2d2f39;
    font-weight: 600;
}

/* Scrollbars */
QScrollBar:vertical {
    background: #121316;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #373a46;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #4b5563;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #121316;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #373a46;
    min-width: 20px;
    border-radius: 5px;
}

/* Checkboxes -- indicator has a hard pixel size so it can never collapse */
QCheckBox {
    spacing: 10px;
    color: #e5e7eb;
    padding: 2px 0px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #4b5563;
    background-color: #18191e;
}

QCheckBox::indicator:hover {
    border-color: #6b7280;
}

QCheckBox::indicator:checked {
    background-color: #4f46e5;
    border-color: #6366f1;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background: #282a34;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #4f46e5;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #e5e7eb;
    border: 2px solid #6366f1;
    width: 16px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 8px;
}

/* Status Bar */
QStatusBar {
    background-color: #121316;
    color: #9ca3af;
    border-top: 1px solid #23252d;
    padding: 4px;
}

QStatusBar QLabel {
    color: #9ca3af;
    padding-left: 6px;
}

/* Labels */
QLabel#headerTitle {
    font-size: 18px;
    font-weight: 700;
    color: #ffffff;
}

QLabel#hintLabel {
    color: #8b93a3;
    font-size: 11px;
    padding-left: 28px;
    margin: 0px 0px 4px 0px;
}

QLabel#settingsFieldLabel {
    color: #d1d5db;
    font-weight: 600;
}

QLabel#copyrightLabel {
    color: #6b7280;
    font-size: 11px;
    padding-right: 8px;
}

QLabel#badgeConnected {
    background-color: #064e3b;
    color: #34d399;
    padding: 4px 10px;
    border-radius: 12px;
    font-weight: 600;
    border: 1px solid #059669;
}

QLabel#badgeDisconnected {
    background-color: #450a0a;
    color: #f87171;
    padding: 4px 10px;
    border-radius: 12px;
    font-weight: 600;
    border: 1px solid #dc2626;
}

QLabel#badgeCardActive {
    background-color: #1e1b4b;
    color: #a5b4fc;
    padding: 4px 10px;
    border-radius: 12px;
    font-weight: 600;
    border: 1px solid #4f46e5;
}

QLabel#badgeCardNone {
    background-color: #1f2937;
    color: #9ca3af;
    padding: 4px 10px;
    border-radius: 12px;
    font-weight: 600;
    border: 1px solid #374151;
}

/* SpinBox buttons */
QSpinBox::up-button, QSpinBox::down-button {
    background-color: #313442;
    border: 1px solid #404456;
    width: 18px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #3e4254;
}
"""
