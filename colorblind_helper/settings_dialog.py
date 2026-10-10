"""Settings window. Every control applies immediately and emits `changed`."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFontComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QSlider, QSpinBox, QTabWidget,
                               QVBoxLayout, QWidget)

from .colors import CVD_LABELS
from .settings import Settings


class SettingsDialog(QDialog):
    changed = Signal()
    resetRequested = Signal()

    def __init__(self, settings: Settings, hotkeys_available: bool, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._hotkeys_available = hotkeys_available
        self._widgets: dict[str, QWidget] = {}
        self.setWindowTitle("Colorblind Helper — Settings")
        self.setMinimumWidth(440)

        tabs = QTabWidget(self)
        tabs.addTab(self._overlay_tab(), "Overlay")
        tabs.addTab(self._fields_tab(), "Fields")
        tabs.addTab(self._sampling_tab(), "Sampling")
        tabs.addTab(self._hotkeys_tab(), "Hotkeys")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        reset = QPushButton("Reset to defaults")
        reset.clicked.connect(self._reset)
        buttons.addButton(reset, QDialogButtonBox.ButtonRole.ResetRole)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)
        self.refresh()

    # ------------------------------------------------------------------ tabs
    def _overlay_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)

        pos = QGroupBox("Position")
        form = QFormLayout(pos)
        form.addRow(self._check("attach_to_cursor",
                                "Attach overlay to cursor (click-through, follows the mouse)"))
        form.addRow("Offset from cursor X", self._spin("offset_x", -400, 400, " px"))
        form.addRow("Offset from cursor Y", self._spin("offset_y", -400, 400, " px"))
        hint = QLabel("When not attached, drag the overlay anywhere; it stays where you put it.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray")
        form.addRow(hint)
        outer.addWidget(pos)

        look = QGroupBox("Appearance")
        form = QFormLayout(look)
        form.addRow(self._check("descriptive_mode", "Descriptive mode (detailed colour info)"))
        form.addRow("Theme", self._combo("theme", [("Dark", "dark"), ("Light", "light")]))
        form.addRow("Opacity", self._slider("opacity", 15, 100, 100.0))
        form.addRow("Size (scale)", self._dspin("scale", 0.5, 3.0, 0.1))
        form.addRow("Swatch size", self._spin("swatch_size", 12, 120, " px"))
        form.addRow("Corner radius", self._spin("corner_radius", 0, 30, " px"))
        form.addRow("Font", self._font("font_family"))
        outer.addWidget(look)
        outer.addStretch(1)
        return w

    def _fields_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)

        compact = QGroupBox("Compact mode shows")
        form = QVBoxLayout(compact)
        form.addWidget(self._check("show_hex", "HEX code"))
        form.addWidget(self._check("show_name", "Closest colour name"))
        form.addWidget(self._check("show_rgb", "RGB values"))
        outer.addWidget(compact)

        desc = QGroupBox("Descriptive mode additionally shows")
        form = QVBoxLayout(desc)
        form.addWidget(self._check("show_description", "Plain-language description"))
        form.addWidget(self._check("show_hsl", "HSL"))
        form.addWidget(self._check("show_hsv", "HSV"))
        form.addWidget(self._check("show_cmyk", "CMYK"))
        form.addWidget(self._check("show_contrast", "Contrast ratio on white / black"))
        form.addWidget(self._check("show_simulations",
                                   "How the colour looks with colour-blind vision:"))
        sims = QWidget()
        sims_lay = QVBoxLayout(sims)
        sims_lay.setContentsMargins(24, 0, 0, 0)
        for kind, label in CVD_LABELS.items():
            sims_lay.addWidget(self._check(f"sim_{kind}", label))
        form.addWidget(sims)
        self._widgets["show_simulations"].toggled.connect(sims.setEnabled)
        self._sims_box = sims
        outer.addWidget(desc)

        outer.addWidget(self._check("uppercase_hex", "Uppercase HEX (#FFAA00 instead of #ffaa00)"))
        outer.addStretch(1)
        return w

    def _sampling_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.addRow("Sample area", self._combo("sample_size", [("1×1 pixel", 1),
                                                                ("3×3 average", 3),
                                                                ("5×5 average", 5)]))
        form.addRow("Update interval", self._spin("update_interval_ms", 10, 500, " ms"))
        hint = QLabel("Averaging helps on anti-aliased text and gradients. "
                      "A shorter interval feels snappier but uses a little more CPU.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray")
        form.addRow(hint)
        return w

    def _hotkeys_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.addRow(self._check("hotkeys_enabled", "Enable global hotkeys"))
        form.addRow("Copy HEX", self._line("hotkey_copy_hex"))
        form.addRow("Freeze / unfreeze", self._line("hotkey_freeze"))
        form.addRow("Attach / detach from cursor", self._line("hotkey_toggle_attach"))
        form.addRow("Toggle descriptive mode", self._line("hotkey_toggle_descriptive"))
        form.addRow("Show / hide overlay", self._line("hotkey_toggle_visible"))
        if self._hotkeys_available:
            txt = ("Syntax: <ctrl>+<shift>+c, <alt>+x, <cmd>+<shift>+k …  Leave empty to "
                   "disable one. On macOS, grant Accessibility / Input Monitoring to the app.")
        else:
            txt = ("The 'pynput' package is not installed, so global hotkeys are unavailable. "
                   "Install it with:  pip install pynput\n"
                   "Shortcuts still work while the overlay is focused (click it first): "
                   "C copy, Space freeze, D descriptive, A attach, Esc hide, Ctrl+Q quit.")
        hint = QLabel(txt)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray")
        form.addRow(hint)
        return w

    # ------------------------------------------------------------------ bound widgets
    def _set(self, attr: str, value) -> None:
        if getattr(self.settings, attr) != value:
            setattr(self.settings, attr, value)
            self.changed.emit()

    def _check(self, attr: str, label: str) -> QCheckBox:
        cb = QCheckBox(label)
        cb.toggled.connect(lambda v, a=attr: self._set(a, bool(v)))
        self._widgets[attr] = cb
        return cb

    def _spin(self, attr: str, lo: int, hi: int, suffix: str = "") -> QSpinBox:
        sp = QSpinBox()
        sp.setRange(lo, hi)
        sp.setSuffix(suffix)
        sp.valueChanged.connect(lambda v, a=attr: self._set(a, int(v)))
        self._widgets[attr] = sp
        return sp

    def _dspin(self, attr: str, lo: float, hi: float, step: float) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(lo, hi)
        sp.setSingleStep(step)
        sp.setDecimals(2)
        sp.valueChanged.connect(lambda v, a=attr: self._set(a, round(float(v), 2)))
        self._widgets[attr] = sp
        return sp

    def _slider(self, attr: str, lo: int, hi: int, divisor: float) -> QWidget:
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(lo, hi)
        lbl = QLabel()
        lbl.setMinimumWidth(40)

        def on_change(v: int) -> None:
            lbl.setText(f"{v}%")
            self._set(attr, v / divisor)

        sl.valueChanged.connect(on_change)
        lay.addWidget(sl, 1)
        lay.addWidget(lbl)
        sl._divisor = divisor  # type: ignore[attr-defined]
        sl._label = lbl        # type: ignore[attr-defined]
        self._widgets[attr] = sl
        return box

    def _combo(self, attr: str, items: list[tuple[str, object]]) -> QComboBox:
        cb = QComboBox()
        for label, value in items:
            cb.addItem(label, value)
        cb.currentIndexChanged.connect(lambda i, a=attr, c=cb: self._set(a, c.itemData(i)))
        self._widgets[attr] = cb
        return cb

    def _line(self, attr: str) -> QLineEdit:
        le = QLineEdit()
        le.editingFinished.connect(lambda a=attr, l=le: self._set(a, l.text().strip()))
        self._widgets[attr] = le
        return le

    def _font(self, attr: str) -> QWidget:
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        fc = QFontComboBox()
        fc.currentFontChanged.connect(lambda f, a=attr: self._set(a, f.family()))
        default = QPushButton("Default")
        default.clicked.connect(lambda: (self._set(attr, ""), self.refresh()))
        lay.addWidget(fc, 1)
        lay.addWidget(default)
        self._widgets[attr] = fc
        return box

    # ------------------------------------------------------------------ sync
    def refresh(self) -> None:
        """Push current settings into the widgets without re-emitting `changed`."""
        s = self.settings
        for attr, w in self._widgets.items():
            value = getattr(s, attr)
            w.blockSignals(True)
            try:
                if isinstance(w, QCheckBox):
                    w.setChecked(bool(value))
                elif isinstance(w, QFontComboBox):
                    w.setCurrentFont(QFont(value) if value else QFont())
                elif isinstance(w, QComboBox):
                    idx = w.findData(value)
                    w.setCurrentIndex(max(0, idx))
                elif isinstance(w, QSlider):
                    v = int(round(value * w._divisor))  # type: ignore[attr-defined]
                    w.setValue(v)
                    w._label.setText(f"{v}%")           # type: ignore[attr-defined]
                elif isinstance(w, QDoubleSpinBox):
                    w.setValue(float(value))
                elif isinstance(w, QSpinBox):
                    w.setValue(int(value))
                elif isinstance(w, QLineEdit):
                    w.setText(str(value))
            finally:
                w.blockSignals(False)
        self._sims_box.setEnabled(s.show_simulations)

    def _reset(self) -> None:
        self.settings.reset()
        self.refresh()
        self.changed.emit()
