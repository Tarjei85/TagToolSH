"""
Windows startup (autostart on boot) manager for NFC Card Launcher.
Uses HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run registry key.
"""

import os
import sys
import winreg

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "ACR122U_NFC_Launcher"


def is_autostart_enabled() -> bool:
    """Checks if autostart on Windows boot is currently registered in HKCU."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(val)
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"[Autostart] Query error: {e}")
        return False


def set_autostart(enable: bool, start_minimized: bool = True) -> bool:
    """
    Enables or disables launch on Windows startup.
    Uses pythonw.exe if available so no terminal window flashes on boot.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                main_script = os.path.join(base_dir, "main.py")

                # Prefer pythonw.exe so execution is headless on Windows boot
                py_dir = os.path.dirname(sys.executable)
                pythonw = os.path.join(py_dir, "pythonw.exe")
                exe_to_use = pythonw if os.path.exists(pythonw) else sys.executable

                cmd = f'"{exe_to_use}" "{main_script}"'
                if start_minimized:
                    cmd += " --minimized"

                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                print(f"[Autostart] Enabled: {cmd}")
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                    print("[Autostart] Disabled")
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        print(f"[Autostart] Error updating registry: {e}")
        return False
