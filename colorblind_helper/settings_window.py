"""The settings window, styled like a small gallery: a painted backdrop, a
drifting painting banner with a museum label, and card-based pages."""
from __future__ import annotations

import os

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFileDialog, QFontComboBox, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QSlider, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from . import __version__
from .colors import CVD_LABELS
from .icon import app_icon, icon_pixmap
from .paintings import PAINTINGS, QUOTES, blurred_image, cover_image
from .settings import Settings, settings_path
from .themes import MATCH, THEMES, get_theme, paint_canvas, palette_for, window_stylesheet
from .widgets import (Banner, CvdStrip, HotkeyRecorder, PaintedPanel, PaintingThumb,
                      PaletteGrid, ThemeCard, ToggleSwitch, card, row, section,
                      set_active_theme)

REPO_URL = "https://github.com/xilla420/ColorblindHelper"

_CVD_DESC = {
    "protan": "Weak or missing red cones · about 1% of men",
    "deutan": "Weak or missing green cones · the most common, about 5% of men",
    "tritan": "Weak or missing blue cones · rare",
    "achroma": "Sees light and shade only · very rare",
}

PAGES = [
    ("appearance", "\U0001F5BC️   Appearance", "Appearance",
     "Choose a painting to live in — for this window and for the overlay."),
    ("overlay", "\U0001F50D   Overlay", "The overlay",
     "What the colour card shows, and how it follows your brush."),
    ("vision", "\U0001F441️   Vision", "Through other eyes",
     "How colours — and Van Gogh — look with each kind of colour vision."),
    ("palette", "\U0001F3A8   Palette", "Your palette",
     "Every colour you copy is kept here, ready to reuse."),
    ("shortcuts", "⌨️   Shortcuts", "Shortcuts",
     "Global hotkeys that work from any app, mid-stroke."),
    ("general", "⚙️   General", "General",
     "Startup, sampling, and the paintings behind the app."),
]


class SettingsWindow(QWidget):
    changed = Signal()
    quitRequested = Signal()
    copyRequested = Signal(str)       # hex from the palette page
    paletteChanged = Signal()

    def __init__(self, settings: Settings, hotkeys_available: bool) -> None:
        super().__init__(None)
        self.settings = settings
        self._hotkeys_available = hotkeys_available
        self._refreshers: list = []
        self._strips: list[CvdStrip] = []
        self._thumbs: list[PaintingThumb] = []

        self.setObjectName("SettingsRoot")
        self.setWindowTitle("Colorblind Helper")
        self.setWindowIcon(app_icon())
        self.resize(880, 650)
        self.setMinimumSize(830, 540)

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

    # ------------------------------------------------------------------ backdrop
    def paintEvent(self, _e) -> None:
        t = get_theme(self.settings.ui_theme)
        p = QPainter(self)
        r = QRectF(self.rect())
        if t.painting:
            dpr = max(1.0, self.devicePixelRatioF())
            p.drawImage(r, blurred_image(t.painting, int(r.width() * dpr / 3) + 1,
                                         int(r.height() * dpr / 3) + 1))
            tint = QColor(t.bg)
            tint.setAlphaF(0.88)
            p.fillRect(r, tint)
        else:
            paint_canvas(p, r, t)
        p.end()

    # ------------------------------------------------------------------ chrome
    def _sidebar(self) -> QWidget:
        side = PaintedPanel(tint_alpha=0.80, border_right=True)
        side.setFixedWidth(196)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(12, 18, 12, 14)
        lay.setSpacing(4)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        dpr = max(1.0, self.devicePixelRatioF())
        pm = icon_pixmap(int(40 * dpr))
        pm.setDevicePixelRatio(dpr)
        logo.setPixmap(pm)
        brand.addWidget(logo)
        name = QLabel("Colorblind\nHelper")
        name.setObjectName("appName")
        brand.addWidget(name, 1)
        lay.addLayout(brand)
        lay.addSpacing(16)

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

        self._quote = QLabel()
        self._quote.setObjectName("quote")
        self._quote.setWordWrap(True)
        self._quote_src = QLabel()
        self._quote_src.setObjectName("caption")
        self._quote_src.setWordWrap(True)
        lay.addWidget(self._quote)
        lay.addWidget(self._quote_src)
        lay.addSpacing(10)
        self._quote_idx = -1
        self._next_quote()
        timer = QTimer(self)
        timer.timeout.connect(self._next_quote)
        timer.start(30000)

        bottom = QHBoxLayout()
        ver = QLabel(f"v{__version__}")
        ver.setObjectName("muted")
        bottom.addWidget(ver)
        bottom.addStretch(1)
        quit_btn = QPushButton("Quit")
        quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quit_btn.clicked.connect(self.quitRequested.emit)
        bottom.addWidget(quit_btn)
        lay.addLayout(bottom)
        return side

    def _next_quote(self) -> None:
        self._quote_idx = (self._quote_idx + 1) % len(QUOTES)
        text, src = QUOTES[self._quote_idx]
        self._quote.setText(f"“{text}”")
        self._quote_src.setText(f"— Vincent, {src}")

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
        lay.setContentsMargins(24, 14, 24, 24)
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
        lay.addWidget(section("Window"))
        lay.addWidget(self._theme_grid("ui_theme", list(THEMES)))
        lay.addSpacing(4)
        lay.addWidget(section("Overlay"))
        lay.addWidget(self._theme_grid("overlay_theme", [MATCH, *THEMES]))
        lay.addSpacing(4)
        lay.addWidget(section("Finish"))
        lay.addWidget(card(
            row("Painted textures & motion", self._toggle("decorations"),
                "A wash of the painting behind the overlay, and the banner’s slow drift."),
            row("Opacity", self._slider("opacity", 25, 100, 100, "{}%")),
            row("Size", self._slider("scale", 50, 300, 100, "{}%")),
            row("Swatch size", self._slider("swatch_size", 16, 96, 1, "{} px")),
            row("Corner roundness", self._slider("corner_radius", 0, 24, 1, "{} px")),
            row("Font", self._font_picker("font_family"),
                "Default uses a serif for colour names, like a museum label."),
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
                "Off: drag the card anywhere on your canvas and it stays put."),
            row("Distance from cursor", offsets),
            row("Descriptive mode", self._toggle("descriptive_mode"),
                "The full story of a colour. Also: double-click the card or Ctrl+Shift+D."),
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
            row("Show simulations on the overlay", self._toggle("show_simulations"),
                "In descriptive mode, see how the colour under your cursor reads for each "
                "vision type you switch on below."),
        ))
        note = QLabel("Below, Vincent’s 1887 self-portrait — red beard against a green "
                      "ground — as each eye might see it. Some have wondered whether he "
                      "saw colour differently himself: an intriguing, unproven idea.")
        note.setObjectName("caption")
        note.setWordWrap(True)
        lay.addWidget(note)
        rows = [self._cvd_row(None, "Typical colour vision",
                              "The last chip is the colour under your cursor.", None)]
        for kind, label in CVD_LABELS.items():
            rows.append(self._cvd_row(kind, label, _CVD_DESC[kind], f"sim_{kind}"))
        lay.addWidget(card(rows[0]))
        self._sim_card = card(*rows[1:])
        lay.addWidget(self._sim_card)
        self._refreshers.append(
            lambda: self._sim_card.setEnabled(self.settings.show_simulations))
        lay.addStretch(1)
        return w

    def _cvd_row(self, kind, title, desc, attr) -> QWidget:
        thumb = PaintingThumb(kind)
        self._thumbs.append(thumb)
        strip = CvdStrip(kind)
        self._strips.append(strip)
        return row(title, self._toggle(attr) if attr else None, desc, leading=thumb, below=strip)

    def _page_palette(self) -> QWidget:
        w, lay = self._page()
        self._palette_grid = PaletteGrid()
        self._palette_grid.copyRequested.connect(self.copyRequested.emit)
        self._palette_grid.removeRequested.connect(self._remove_color)
        copy_all = QPushButton("Copy all")
        copy_all.clicked.connect(lambda: QApplication.clipboard().setText(
            "\n".join(self.settings.palette)))
        export = QPushButton("Export for GIMP / Krita…")
        export.clicked.connect(self._export_palette)
        clear = QPushButton("Clear")
        clear.clicked.connect(self._clear_palette)
        actions = QWidget()
        al = QHBoxLayout(actions)
        al.setContentsMargins(0, 0, 0, 0)
        al.addWidget(copy_all)
        al.addWidget(export)
        al.addStretch(1)
        al.addWidget(clear)
        holder = QWidget()
        hl = QVBoxLayout(holder)
        hl.setContentsMargins(0, 4, 0, 4)
        hl.addWidget(self._palette_grid)
        lay.addWidget(card(holder))
        lay.addWidget(actions)
        hint = QLabel("Click a dab to copy it · right-click to remove · newest first, "
                      "up to 40 colours")
        hint.setObjectName("caption")
        lay.addWidget(hint)
        self._refreshers.append(lambda: self._palette_grid.set_colors(self.settings.palette))
        lay.addStretch(1)
        return w

    def _page_shortcuts(self) -> QWidget:
        w, lay = self._page()
        lay.addWidget(card(row("Global hotkeys", self._toggle("hotkeys_enabled"),
                               "Click a shortcut, then press the new keys. "
                               "Backspace clears, Esc cancels.")))
        self._hotkey_card = card(
            row("Copy HEX (and add to palette)", self._hotkey("hotkey_copy_hex")),
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
                "Averaging smooths over brushstrokes, anti-aliasing and gradients."),
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
            row("Restore defaults", reset, "Themes, fields and hotkeys. Your palette is kept."),
        ))
        lay.addWidget(section("About"))
        lay.addWidget(card(self._about()))
        lay.addStretch(1)
        return w

    def _about(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 10, 0, 10)
        lay.setSpacing(16)
        portrait = QLabel()
        dpr = max(1.0, self.devicePixelRatioF())
        img = cover_image("portrait", int(96 * dpr), int(122 * dpr))
        from PySide6.QtGui import QPixmap
        pm = QPixmap(int(96 * dpr), int(122 * dpr))
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, pm.width(), pm.height()), 10 * dpr, 10 * dpr)
        p.setClipPath(path)
        p.drawImage(0, 0, img)
        p.end()
        pm.setDevicePixelRatio(dpr)
        portrait.setPixmap(pm)
        portrait.setToolTip("Vincent van Gogh, Self-Portrait, 1887 — Art Institute of Chicago")
        lay.addWidget(portrait, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(4)
        title = QLabel(f"Colorblind Helper {__version__}")
        title.setObjectName("appName")
        text.addWidget(title)
        blurb = QLabel("For colour-blind artists, with love from Vincent’s palette. "
                       "Every colour deserves a name.")
        blurb.setObjectName("caption")
        blurb.setWordWrap(True)
        text.addWidget(blurb)
        links = "<br>".join(
            f'<a href="{pt.source}">{pt.title}</a> ({pt.year}), {pt.collection}'
            for pt in PAINTINGS.values())
        credits = QLabel(f"<span style='font-size:8pt'>Paintings by Vincent van Gogh, public "
                         f"domain; scans via Wikimedia Commons.<br>{links}</span>")
        credits.setObjectName("desc")
        credits.setTextFormat(Qt.TextFormat.RichText)
        credits.setOpenExternalLinks(True)
        credits.setWordWrap(True)
        text.addWidget(credits)
        gh = QPushButton("Source on GitHub ↗")
        gh.setObjectName("link")
        gh.setCursor(Qt.CursorShape.PointingHandCursor)
        gh.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        text.addWidget(gh, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addLayout(text, 1)
        return w

    # ------------------------------------------------------------------ palette actions
    def _remove_color(self, hx: str) -> None:
        if hx in self.settings.palette:
            self.settings.palette.remove(hx)
            self.paletteChanged.emit()

    def _clear_palette(self) -> None:
        self.settings.palette.clear()
        self.paletteChanged.emit()

    def _export_palette(self) -> None:
        if not self.settings.palette:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export palette", "Colorblind Helper.gpl",
                                              "GIMP palette (*.gpl)")
        if not path:
            return
        from .colors import color_info
        lines = ["GIMP Palette", "Name: Colorblind Helper", "Columns: 8", "#"]
        for hx in self.settings.palette:
            rgb = tuple(int(hx[i:i + 2], 16) for i in (1, 3, 5))
            lines.append(f"{rgb[0]:3d} {rgb[1]:3d} {rgb[2]:3d}\t{color_info(rgb).name} {hx}")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

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
            c = ThemeCard(key)
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
        for th in self._thumbs:
            th.set_painting("portrait")
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
        return QSize(880, 650)
