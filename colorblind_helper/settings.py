"""Persistent user settings (JSON in the platform config directory)."""
from __future__ import annotations

import dataclasses
import json
import os
from dataclasses import dataclass, field, fields

from PySide6.QtCore import QStandardPaths

APP_NAME = "ColorblindHelper"


@dataclass
class Settings:
    # Overlay placement
    attach_to_cursor: bool = True
    offset_x: int = 24
    offset_y: int = 24
    free_x: int = -1          # remembered position when not attached (-1 = unset)
    free_y: int = -1

    # Appearance
    descriptive_mode: bool = False
    opacity: float = 0.94
    scale: float = 1.0
    theme: str = "dark"       # "dark" | "light"
    swatch_size: int = 36
    font_family: str = ""     # "" = system default
    corner_radius: int = 10

    # Sampling
    sample_size: int = 1      # 1, 3 or 5 (NxN average)
    update_interval_ms: int = 40
    uppercase_hex: bool = True

    # Fields
    show_hex: bool = True
    show_rgb: bool = True
    show_name: bool = True
    show_description: bool = True
    show_hsl: bool = True
    show_hsv: bool = False
    show_cmyk: bool = False
    show_contrast: bool = False
    show_simulations: bool = True
    sim_protan: bool = True
    sim_deutan: bool = True
    sim_tritan: bool = True
    sim_achroma: bool = False

    def enabled_simulations(self) -> list[str]:
        return [k for k in ("protan", "deutan", "tritan", "achroma")
                if getattr(self, f"sim_{k}")]

    # Global hotkeys (pynput syntax). Empty string disables that hotkey.
    hotkeys_enabled: bool = True
    hotkey_copy_hex: str = "<ctrl>+<shift>+c"
    hotkey_freeze: str = "<ctrl>+<shift>+f"
    hotkey_toggle_attach: str = "<ctrl>+<shift>+a"
    hotkey_toggle_descriptive: str = "<ctrl>+<shift>+d"
    hotkey_toggle_visible: str = "<ctrl>+<shift>+h"

    first_run: bool = True

    # ---------------------------------------------------------------- helpers
    def hotkey_map(self) -> dict[str, str]:
        return {
            "copy_hex": self.hotkey_copy_hex,
            "freeze": self.hotkey_freeze,
            "toggle_attach": self.hotkey_toggle_attach,
            "toggle_descriptive": self.hotkey_toggle_descriptive,
            "toggle_visible": self.hotkey_toggle_visible,
        }

    def reset(self) -> None:
        for f in fields(Settings):
            if f.name in ("free_x", "free_y", "first_run"):
                continue
            setattr(self, f.name, f.default)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def update_from(self, data: dict) -> None:
        known = {f.name: f.type for f in fields(Settings)}
        for k, v in data.items():
            if k in known:
                setattr(self, k, v)


def settings_path() -> str:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    if not base:
        base = os.path.join(os.path.expanduser("~"), "." + APP_NAME.lower())
    return os.path.join(base, "settings.json")


def load_settings() -> Settings:
    s = Settings()
    path = settings_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            s.update_from(json.load(fh))
    except (OSError, ValueError):
        pass
    return s


def save_settings(s: Settings) -> None:
    path = settings_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(s.to_dict(), fh, indent=2)
    except OSError:
        pass
