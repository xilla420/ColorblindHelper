"""The settings window: sidebar navigation, animated themed banner with a live
overlay preview, and card-based pages. Every control applies immediately."""
from __future__ import annotations

import os

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (QButtonGroup, QFontComboBox, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QPushButton, QScrollArea, QSlider, QSpinBox,
                               QStackedWidget, QVBoxLayout, QWidget)

from . import __version__
from .colors import CVD_LABELS
from .icon import app_icon, icon_pixmap
from .settings import Settings, settings_path
from .themes import MATCH, THEMES, get_theme, palette_for, window_stylesheet
from .widgets import (Banner, CvdStrip, HotkeyRecorder, ThemeCard, ToggleSwitch, card, row,
                      section, set_active_theme)

REPO_URL = "https://github.com/xilla420/ColorblindHelper"

_CVD_DESC = {
    "protan": "Weak or missing red cones · about 1% of men",
    "deutan": "Weak or missing green cones · most common, about 5% of men",
    "tritan": "Weak or missing blue cones · rare",
    "achroma": "Sees brightness only, no hue · very rare",
}

PAGES = [
    ("appearance", "\U0001F3A8   Appearance", "Appearance",
     "Pick a look for this window and for the floating overlay."),
    ("overlay", "\U0001F50D   Overlay", "Overlay",
     "What the colour card shows, and how it follows you around."),
    ("vision", "\U0001F453   Vision", "Colour vision",
     "Choose which colour-blind simulations appear in descriptive mode."),
    ("shortcuts", "⌨️   Shortcuts", "Shortcuts",
     "Global hotkeys that work from any app."),
    ("general", "⚙️   General", "General",
     "Startup, sampling and everything else."),
]


class SettingsWindow(QWidget):
    changed = Signal()
    quitRequested = Signal()

    def __init__(self, settings: Settings, hotkeys_available: bool) -> None:
        super().__init__(None)
        self.settings = settings
        self._hotkeys_available = hotkeys_available
        self._refreshers: list = []
        self._strips: list[CvdStrip] = []

        self.setObjectName("SettingsRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle("Colorblind Helper")
        self.setWindowIcon(app_icon())
        self.resize(780, 580)
        self.setMinimumSize(700, 480)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._sidebar())

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.banner = Banner(settings, PAGES[0][2], PAGES[0][3])
        right.addWidget(self.banner)
        self.stack = QStackedWidget()
        for key, *_ in PAGES:
            self.stack.addWidget(self._scroll(getattr(self, f"_page_{key}")()))
        right.addWidget(self.stack, 1)
        root.addLayout(right, 1)

        self._nav_buttons[0].setChecked(True)
        self.apply_theme()
        self.refresh()

    # ------------------------------------------------------------------ chrome
    def _sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(184)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(12, 16, 12, 14)
        lay.setSpacing(4)

        brand = QHBoxLayout()
        logo = QLabel()
        dpr = max(1.0, self.devicePixelRatioF())
        pm = icon_pixmap(int(38 * dpr))
        pm.setDevicePixelRatio(dpr)
        logo.setPixmap(pm)
        brand.addWidget(logo)
        name = QLabel("Colorblind\nHelper")
        name.setObjectName("appName")
        brand.addWidget(name, 1)
        lay.addLayout(brand)
        lay.addSpacing(14)

        group = QButtonGroup(self)
        group.setExclusive(True)
        self._nav_buttons: list[QPushButton] = []
        for i, (_, label, title, subtitle) in enumerate(PAGES):
            b = QPushButton(label)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=i, t=title, s=subtitle: self._go(i, t, s))
            group.addButton(b)
            lay.addWidget(b)
            self._nav_buttons.append(b)
        lay.addStretch(1)

        ver = QLabel(f"v{__version__}")
        ver.setObjectName("muted")
        lay.addWidget(ver)
        quit_btn = QPushButton("Quit app")
        quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quit_btn.clicked.connect(self.quitRequested.emit)
        lay.addWidget(quit_btn)
        return side

    def _scroll(self, page: QWidget) -> QScrollArea:
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setWidget(page)
        return sa

    def _page(self) -> tuple[QWidget, QVBoxLayout]:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(22, 14, 22, 22)
        lay.setSpacing(8)
        return w, lay

    def _go(self, index: int, title: str, subtitle: str) -> None:
        self.stack.setCurrentIndex(index)
        self.banner.set_page(title, subtitle)

    def show_page(self, key: str) -> None:
        for i, (k, _, title, subtitle) in enumerate(PAGES):
            if k == key:
                self._nav_buttons[i].setChecked(True)
                self._go(i, title, subtitle)

    # ------------------------------------------------------------------ pages
    def _page_appearance(self) -> QWidget:
        w, lay = self._page()
        lay.addWidget(section("App theme"))
        lay.addWidget(self._theme_grid("ui_theme", list(THEMES)))
        lay.addSpacing(6)
        lay.addWidget(section("Overlay theme"))
        lay.addWidget(self._theme_grid("overlay_theme", [MATCH, *THEMES]))
        lay.addSpacing(6)
        lay.addWidget(section("Style"))
        lay.addWidget(card(
            row("Animated decorations", self._toggle("decorations"),
                "Twinkling stars, drifting petals and friends."),
            row("Opacity", self._slider("opacity", 25, 100, 100, "{}%")),
            row("Size", self._slider("scale", 50, 300, 100, "{}%")),
            row("Swatch size", self._slider("swatch_size", 16, 96, 1, "{} px")),
            row("Corner roundness", self._slider("corner_radius", 0, 24, 1, "{} px")),
            row("Font", self._font_picker("font_family")),
        ))
        lay.addStretch(1)
        return w

    def _page_overlay(self) -> QWidget:
        w, lay = self._page()
        lay.addWidget(section("Behaviour"))
        offsets = QWidget()
        ol = QHBoxLayout(offsets)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.addWidget(QLabel("X"))
        ol.addWidget(self._spin("offset_x", -300, 300, " px"))
        ol.addSpacing(6)
        ol.addWidget(QLabel("Y"))
        ol.addWidget(self._spin("offset_y", -300, 300, " px"))
        lay.addWidget(card(
            row("Follow the cursor", self._toggle("attach_to_cursor"),
                "Off: drag the card anywhere and it stays put."),
            row("Distance from cursor", offsets),
            row("Descriptive mode", self._toggle("descriptive_mode"),
                "Detailed info. Also: double-click the card or Ctrl+Shift+D."),
        ))
        lay.addWidget(section("Compact mode shows"))
        lay.addWidget(card(
            row("HEX code", self._toggle("show_hex")),
            row("Closest colour name", self._toggle("show_name")),
            row("RGB values", self._toggle("show_rgb")),
            row("Uppercase HEX", self._toggle("uppercase_hex"), "#FFAA00 instead of #ffaa00"),
        ))
        lay.addWidget(section("Descriptive mode also shows"))
        lay.addWidget(card(
            row("Plain-language description", self._toggle("show_description"),
                "e.g. “Light muted teal”"),
            row("HSL", self._toggle("show_hsl")),
            row("HSV", self._toggle("show_hsv")),
            row("CMYK", self._toggle("show_cmyk")),
            row("Contrast on white / black", self._toggle("show_contrast")),
        ))
        lay.addStretch(1)
        return w

    def _page_vision(self) -> QWidget:
        w, lay = self._page()
        lay.addWidget(card(
            row("Show simulations", self._toggle("show_simulations"),
                "How the colour under the cursor looks with each vision type. "
                "Shown in descriptive mode."),
        ))
        lay.addWidget(section("Vision types"))
        rows = [self._cvd_row(None, "Typical vision", "Reference — the last chip is the "
                                                       "colour under your cursor", None)]
        for kind, label in CVD_LABELS.items():
            rows.append(self._cvd_row(kind, label, _CVD_DESC[kind], f"sim_{kind}"))
        self._sim_card = card(*rows[1:])
        lay.addWidget(card(rows[0]))
        lay.addWidget(self._sim_card)
        self._refreshers.append(
            lambda: self._sim_card.setEnabled(self.settings.show_simulations))
        lay.addStretch(1)
        return w

    def _cvd_row(self, kind, title, desc, attr) -> QWidget:
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 8)
        v.setSpacing(0)
        v.addWidget(row(title, self._toggle(attr) if attr else None, desc))
        strip = CvdStrip(kind)
        self._strips.append(strip)
        v.addWidget(strip)
        return box

    def _page_shortcuts(self) -> QWidget:
        w, lay = self._page()
        lay.addWidget(card(row("Global hotkeys", self._toggle("hotkeys_enabled"),
                               "Click a shortcut, then press the new keys. "
                               "Backspace clears, Esc cancels.")))
        self._hotkey_card = card(
            row("Copy HEX", self._hotkey("hotkey_copy_hex")),
            row("Freeze / unfreeze colour", self._hotkey("hotkey_freeze")),
            row("Follow cursor on / off", self._hotkey("hotkey_toggle_attach")),
            row("Descriptive mode on / off", self._hotkey("hotkey_toggle_descriptive")),
            row("Show / hide overlay", self._hotkey("hotkey_toggle_visible")),
        )
        lay.addWidget(self._hotkey_card)
        self._refreshers.append(
            lambda: self._hotkey_card.setEnabled(self.settings.hotkeys_enabled))
        if not self._hotkeys_available:
            warn = QLabel("Global hotkeys need the ‘pynput’ package: pip install pynput")
            warn.setObjectName("desc")
            lay.addWidget(warn)
        lay.addWidget(section("When the overlay is focused"))
        tips = QLabel("C copy · Space freeze · D descriptive · A follow cursor "
                      "· Esc hide · scroll to resize · right-click for menu")
        tips.setObjectName("desc")
        tips.setWordWrap(True)
        lay.addWidget(card(tips))
        lay.addStretch(1)
        return w

    def _page_general(self) -> QWidget:
        w, lay = self._page()
        lay.addWidget(section("System"))
        lay.addWidget(card(
            row("Run at startup", self._toggle("run_at_startup"),
                "Start quietly in the tray when you sign in."),
        ))
        lay.addWidget(section("Sampling"))
        lay.addWidget(card(
            row("Sample area", self._segmented("sample_size", [("1×1", 1), ("3×3", 3),
                                                               ("5×5", 5)]),
                "Averaging smooths anti-aliased text and gradients."),
            row("Refresh every", self._slider("update_interval_ms", 10, 200, 1, "{} ms"),
                "Lower feels snappier, higher saves battery."),
        ))
        lay.addWidget(section("Maintenance"))
        reset = QPushButton("Reset everything")
        reset.clicked.connect(self._reset)
        folder = QPushButton("Open folder")
        folder.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl.fromLocalFile(os.path.dirname(settings_path()))))
        lay.addWidget(card(
            row("Settings file", folder, os.path.normpath(settings_path())),
            row("Restore defaults", reset, "Themes, fields and hotkeys go back to default."),
        ))
        lay.addWidget(section("About"))
        gh = QPushButton("GitHub ↗")
        gh.setObjectName("link")
        gh.setCursor(Qt.CursorShape.PointingHandCursor)
        gh.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        lay.addWidget(card(row(f"Colorblind Helper {__version__}", gh,
                               "Made with ♥ so every colour has a name.")))
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------------ bound controls
    def _set(self, attr: str, value) -> None:
        if getattr(self.settings, attr) != value:
            setattr(self.settings, attr, value)
            self.changed.emit()

    def _toggle(self, attr: str) -> ToggleSwitch:
        sw = ToggleSwitch()
        sw.toggled.connect(lambda v, a=attr: self._set(a, bool(v)))

        def refresh(sw=sw, a=attr):
            sw.blockSignals(True)
            sw.setChecked(bool(getattr(self.settings, a)))
            sw.blockSignals(False)
        self._refreshers.append(refresh)
        return sw

    def _slider(self, attr: str, lo: int, hi: int, factor: int, fmt: str) -> QWidget:
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(lo, hi)
        sl.setFixedWidth(170)
        lbl = QLabel()
        lbl.setObjectName("muted")
        lbl.setMinimumWidth(52)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        is_float = isinstance(getattr(self.settings, attr), float)

        def on_change(v: int) -> None:
            lbl.setText(fmt.format(v))
            self._set(attr, round(v / factor, 2) if is_float else int(v))

        sl.valueChanged.connect(on_change)

        def refresh():
            v = int(round(getattr(self.settings, attr) * factor))
            sl.blockSignals(True)
            sl.setValue(v)
            sl.blockSignals(False)
            lbl.setText(fmt.format(v))
        self._refreshers.append(refresh)
        lay.addWidget(sl)
        lay.addWidget(lbl)
        return box

    def _spin(self, attr: str, lo: int, hi: int, suffix: str) -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(lo, hi)
        sp.setSuffix(suffix)
        sp.setFixedWidth(84)
        sp.valueChanged.connect(lambda v, a=attr: self._set(a, int(v)))

        def refresh():
            sp.blockSignals(True)
            sp.setValue(int(getattr(self.settings, attr)))
            sp.blockSignals(False)
        self._refreshers.append(refresh)
        return sp

    def _segmented(self, attr: str, options: list[tuple[str, object]]) -> QWidget:
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        group = QButtonGroup(box)
        buttons = []
        for i, (label, value) in enumerate(options):
            b = QPushButton(label)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            first, last = i == 0, i == len(options) - 1
            b.setStyleSheet(
                "QPushButton#seg {"
                + (" border-top-left-radius: 8px; border-bottom-left-radius: 8px;" if first else "")
                + (" border-top-right-radius: 8px; border-bottom-right-radius: 8px;" if last else "")
                + "}")
            b.clicked.connect(lambda _=False, v=value: self._set(attr, v))
            group.addButton(b)
            lay.addWidget(b)
            buttons.append((b, value))

        def refresh():
            for b, v in buttons:
                b.setChecked(getattr(self.settings, attr) == v)
        self._refreshers.append(refresh)
        return box

    def _theme_grid(self, attr: str, keys: list[str]) -> QWidget:
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        group = QButtonGroup(box)
        group.setExclusive(True)
        cards: list[ThemeCard] = []
        for i, key in enumerate(keys):
            c = ThemeCard(key, "Match app" if key == MATCH else None)
            c.clicked.connect(lambda _=False, k=key: self._set(attr, k))
            group.addButton(c)
            grid.addWidget(c, i // 4, i % 4)
            cards.append(c)
        grid.setColumnStretch(4, 1)

        def refresh():
            for c in cards:
                c.setChecked(getattr(self.settings, attr) == c.key)
                c.update()
        self._refreshers.append(refresh)
        return box

    def _font_picker(self, attr: str) -> QWidget:
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        fc = QFontComboBox()
        fc.setFixedWidth(170)
        fc.currentFontChanged.connect(lambda f: self._set(attr, f.family()))
        default = QPushButton("Default")
        default.clicked.connect(lambda: (self._set(attr, ""), self.refresh()))
        lay.addWidget(fc)
        lay.addWidget(default)

        def refresh():
            fc.blockSignals(True)
            value = getattr(self.settings, attr)
            fc.setCurrentFont(QFont(value) if value else QFont())
            fc.blockSignals(False)
        self._refreshers.append(refresh)
        return box

    def _hotkey(self, attr: str) -> HotkeyRecorder:
        rec = HotkeyRecorder()
        rec.hotkeyChanged.connect(lambda combo, a=attr: self._set(a, combo))
        self._refreshers.append(lambda: rec.setCombo(getattr(self.settings, attr)))
        return rec

    # ------------------------------------------------------------------ sync
    def refresh(self) -> None:
        for fn in self._refreshers:
            fn()
        self.banner.preview.relayout()
        self.banner.preview.update()

    def apply_theme(self) -> None:
        t = get_theme(self.settings.ui_theme)
        set_active_theme(t)
        self.setPalette(palette_for(t))
        self.setStyleSheet(window_stylesheet(t))
        for w in self.findChildren(QWidget):
            w.update()
        self.update()

    def set_live_color(self, info) -> None:
        self.banner.preview.set_info(info)
        if info is not None:
            for s in self._strips:
                s.set_extra(info.rgb)

    def _reset(self) -> None:
        self.settings.reset()
        self.changed.emit()
        self.refresh()

    def closeEvent(self, e) -> None:
        self.hide()
        e.ignore()

    def sizeHint(self) -> QSize:
        return QSize(780, 580)
