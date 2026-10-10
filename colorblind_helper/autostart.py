"""Run-at-login registration for Windows (registry), macOS (LaunchAgent) and
Linux (XDG autostart)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_ID = "ColorblindHelper"
MAC_LABEL = "io.github.xilla420.colorblindhelper"
STARTUP_FLAG = "--autostart"


def launch_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, STARTUP_FLAG]
    exe = Path(sys.executable)
    if sys.platform == "win32":  # pythonw.exe avoids a console window
        pyw = exe.with_name("pythonw.exe")
        if pyw.exists():
            exe = pyw
    main = Path(__file__).resolve().parent.parent / "main.py"
    return [str(exe), str(main), STARTUP_FLAG]


def _quote(cmd: list[str]) -> str:
    return " ".join(f'"{c}"' if " " in c or not c.startswith("-") else c for c in cmd)


# ---------------------------------------------------------------- Windows
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _win_get() -> str | None:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            return winreg.QueryValueEx(k, APP_ID)[0]
    except OSError:
        return None


def _win_set(enabled: bool) -> None:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, APP_ID, 0, winreg.REG_SZ, _quote(launch_command()))
        else:
            try:
                winreg.DeleteValue(k, APP_ID)
            except FileNotFoundError:
                pass


# ---------------------------------------------------------------- macOS
def _mac_plist() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{MAC_LABEL}.plist"


def _mac_set(enabled: bool) -> None:
    import plistlib
    path = _mac_plist()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as fh:
            plistlib.dump({"Label": MAC_LABEL, "ProgramArguments": launch_command(),
                           "RunAtLoad": True, "ProcessType": "Interactive"}, fh)
    elif path.exists():
        path.unlink()


# ---------------------------------------------------------------- Linux
def _xdg_file() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "autostart" / "colorblind-helper.desktop"


def _xdg_set(enabled: bool) -> None:
    path = _xdg_file()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[Desktop Entry]\nType=Application\nName=Colorblind Helper\n"
                        f"Exec={_quote(launch_command())}\nX-GNOME-Autostart-enabled=true\n",
                        encoding="utf-8")
    elif path.exists():
        path.unlink()


# ---------------------------------------------------------------- public API
def is_enabled() -> bool:
    if sys.platform == "win32":
        return _win_get() is not None
    if sys.platform == "darwin":
        return _mac_plist().exists()
    return _xdg_file().exists()


def set_enabled(enabled: bool) -> None:
    """Registers (or refreshes) / removes the login item. Raises OSError on failure."""
    if sys.platform == "win32":
        _win_set(enabled)
    elif sys.platform == "darwin":
        _mac_set(enabled)
    else:
        _xdg_set(enabled)
