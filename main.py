"""
Main application entry point for TagToolSH!.
Handles both script mode (portable Python + app_data/libs) and frozen
PyInstaller builds.

Frozen builds:
  - The interpreter and dependencies are bundled inside the .exe.
  - User data (config.json, tags_db.json, logs) lives in an app_data folder
    next to the .exe so it persists across runs.
  - Bundled assets like bsod.png and icon.ico live inside sys._MEIPASS.
"""

import sys
import os
import subprocess
import importlib
import traceback
from datetime import datetime

APP_TITLE = "TagToolSH!"

# ------------------------------------------------------------------ #
#  Paths -- different for frozen vs script mode
# ------------------------------------------------------------------ #
IS_FROZEN = getattr(sys, "frozen", False)

if IS_FROZEN:
    INTERNAL_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    BASE_DIR = os.path.dirname(sys.executable)
else:
    INTERNAL_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = INTERNAL_DIR

APP_DATA_DIR = os.path.join(BASE_DIR, "app_data")
LIBS_DIR = os.path.join(APP_DATA_DIR, "libs")
LOG_DIR = os.path.join(APP_DATA_DIR, "logs")

os.makedirs(APP_DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

if not IS_FROZEN:
    os.makedirs(LIBS_DIR, exist_ok=True)
    if LIBS_DIR not in sys.path:
        sys.path.insert(0, LIBS_DIR)
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)

LOG_FILE = os.path.join(LOG_DIR, "launcher.log")


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        if sys.stdout is not None and sys.stdout.isatty():
            print(line)
    except Exception:
        pass


# ------------------------------------------------------------------ #
#  Dependency bootstrap (script mode only)
# ------------------------------------------------------------------ #
def ensure_portable_dependencies():
    required = {
        "PySide6": "PySide6>=6.6.0",
        "smartcard": "pyscard>=2.0.0",
        "ndef": "ndeflib>=0.3.3",
        "psutil": "psutil>=5.9.0",
    }

    missing = []
    for module_name, pip_spec in required.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(pip_spec)

    if not missing:
        log("All dependencies present.")
        return

    log("=" * 60)
    log(f"Missing dependencies: {missing}")
    log(f"Installing into: {LIBS_DIR}")
    log("=" * 60)

    try:
        import pip  # noqa: F401
    except ImportError:
        try:
            subprocess.check_call(
                [sys.executable, "-m", "ensurepip", "--upgrade"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    cmd = [
        sys.executable, "-m", "pip", "install",
        "--target", LIBS_DIR,
        "--upgrade",
        "--disable-pip-version-check",
        *missing,
    ]

    try:
        log(f"Running: {' '.join(cmd)}")
        subprocess.check_call(cmd)
        log("Dependencies installed successfully.")
        importlib.invalidate_caches()
    except Exception as err:
        log(f"ERROR installing dependencies: {err}")
        log(traceback.format_exc())
        try:
            with open(os.path.join(APP_DATA_DIR, "INSTALL_FAILED.txt"), "w", encoding="utf-8") as f:
                f.write(
                    "Dependency installation failed.\n\n"
                    "Common causes:\n"
                    "  1. No internet connection on first run.\n"
                    "  2. A firewall or proxy is blocking pip.\n"
                    "  3. Embedded Python is present but pip wasn't bootstrapped.\n\n"
                    "Manual command:\n"
                    f'  "{sys.executable}" -m pip install --target "{LIBS_DIR}" '
                    "PySide6 pyscard ndeflib psutil\n"
                )
        except Exception:
            pass
        sys.exit(1)


if not IS_FROZEN:
    try:
        ensure_portable_dependencies()
    except SystemExit:
        raise
    except Exception as e:
        log(f"Fatal error during dependency bootstrap: {e}")
        log(traceback.format_exc())
        sys.exit(1)


# ------------------------------------------------------------------ #
#  Qt imports
# ------------------------------------------------------------------ #
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from database import DatabaseManager
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName("Tarjei S. H.")
    app.setQuitOnLastWindowClosed(False)

    db = DatabaseManager(base_dir=BASE_DIR, internal_dir=INTERNAL_DIR)

    # Startup arguments:
    #   --minimized / --tray / --hidden : start in system tray (no window)
    start_minimized = any(
        arg in sys.argv for arg in ("--minimized", "--tray", "--hidden", "--no-window")
    )

    window = MainWindow(db, start_hidden=start_minimized)

    if not start_minimized:
        if db.get_setting("start_maximized", True):
            window.showMaximized()
        else:
            window.show()
    else:
        log("Started minimized to system tray.")

    rc = app.exec()

    # Force the OS to terminate the process. This bypasses Python's normal
    # shutdown sequence, which can hang if the NFC worker thread is stuck
    # inside a blocking PC/SC call. By this point, config and logs are saved.
    log(f"Qt event loop exited (rc={rc}). Forcing process termination.")
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(rc if isinstance(rc, int) else 0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"Fatal error in main: {e}")
        log(traceback.format_exc())
        sys.exit(1)
