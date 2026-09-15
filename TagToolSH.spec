# TagToolSH.spec
# PyInstaller spec for TagToolSH!.
# Build with:  pyinstaller --noconfirm "TagToolSH.spec"
#
# Notes:
#   - Every path in this file must use forward slashes. Windows backslashes
#     in Python string literals will be interpreted as escape sequences
#     (e.g. "\b" becomes backspace) and corrupt the path.
#   - The 'name' fields determine the output .exe and folder name.
#   - 'icon' must point to a real .ico file with multiple resolution layers.

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('app_data/bsod.png', '.'),
        ('app_data/icon.ico', '.'),
    ],
    hiddenimports=[
        'smartcard',
        'ndeflib',
        'psutil',
        'psutil._common',
        'psutil._psutil_windows',
        'psutil._pswindows',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtNetwork',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'matplotlib',
        'numpy',
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TagToolSH',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_data/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TagToolSH',
)
