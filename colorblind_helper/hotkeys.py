"""Optional global hotkeys via pynput. Degrades gracefully when pynput is missing."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


def pynput_available() -> bool:
    try:
        import pynput  # noqa: F401
        return True
    except Exception:
        return False


class HotkeyManager(QObject):
    triggered = Signal(str)   # action name, emitted from the listener thread (queued to main)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._listener = None
        self._current: tuple | None = None

    def apply(self, enabled: bool, mapping: dict[str, str]) -> None:
        key = (enabled, tuple(sorted(mapping.items())))
        if key == self._current:
            return
        self.stop()
        self._current = key
        if not enabled:
            return
        try:
            from pynput import keyboard
        except Exception:
            self.error.emit("Global hotkeys need the 'pynput' package (pip install pynput).")
            return

        combos = {}
        for action, combo in mapping.items():
            combo = combo.strip()
            if combo:
                combos[combo] = (lambda a=action: self.triggered.emit(a))
        if not combos:
            return
        try:
            self._listener = keyboard.GlobalHotKeys(combos)
            self._listener.daemon = True
            self._listener.start()
        except Exception as exc:  # bad combo syntax, missing OS permission, ...
            self._listener = None
            self.error.emit(f"Could not register global hotkeys: {exc}")

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
