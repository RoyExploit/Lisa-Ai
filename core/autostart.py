"""
core/autostart.py
=================

Controls whether Lisa AI launches automatically when Windows starts, by
toggling the current user's HKCU "Run" registry entry.

Uses a tiny marker inside the app data folder (written by the app at startup)
as the *source of truth* for the enabled/disabled state, and mirrors that into
the Windows Run key. This keeps the toggle working even before the EXE path is
known, and the registry write/read is best-effort (never raises).

Works both when running from source and from the packaged EXE: the Run entry
points at whichever LisaAI.exe launched it (resolved at enable time and cached).
"""

from __future__ import annotations

import os
import sys

APP_NAME = "LisaAI"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _state_file() -> str:
    """Where the persisted autostart preference lives (next to the app)."""
    try:
        from core import user_paths

        base = user_paths.config_dir()
    except Exception:
        base = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "LisaAI"
        )
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass
    return os.path.join(base, "autostart.flag")


def _target_command() -> str:
    """The command Windows should run at startup."""
    if getattr(sys, "frozen", False):
        # PyInstaller one-file EXE.
        exe = os.path.abspath(sys.executable)
    else:
        # Running from source: point at the venv python + main.py.
        exe = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else "main.py"
        py = os.path.abspath(sys.executable)
        if exe.lower().endswith(".py"):
            return f'"{py}" "{exe}"'
    return f'"{exe}"'


def is_enabled() -> bool:
    """True if the user has opted into launch-on-boot (source of truth = flag)."""
    return os.path.exists(_state_file())


def _set_run_key(enable: bool) -> None:
    """Add or remove the HKCU Run entry. Best-effort, never raises."""
    try:
        import winreg

        if enable:
            try:
                winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY)
            except Exception:
                pass
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
            )
            with key:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _target_command())
        else:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
            )
            with key:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
    except Exception:
        # Non-Windows or no permission: silently ignore.
        pass


def set_enabled(enabled: bool) -> bool:
    """Persist the preference and sync the Windows Run key. Returns new state."""
    flag = _state_file()
    try:
        if enabled:
            with open(flag, "w", encoding="utf-8") as fh:
                fh.write("1")
        else:
            if os.path.exists(flag):
                os.remove(flag)
    except Exception:
        pass
    _set_run_key(bool(enabled))
    return is_enabled()


def toggle() -> bool:
    """Flip the current state and return the new value."""
    return set_enabled(not is_enabled())
