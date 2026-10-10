"""The always-on-top overlay that shows the color under the cursor."""
from __future__ import annotations

import sys
from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QFontMetrics, QGuiApplication,
                           QPainter, QPen, QCursor)
from PySide6.QtWidgets import QWidget

from .colors import CVD_LABELS, ColorInfo, color_info
from .pixel import PixelReader
from .settings import Settings

RGB = tuple[int, int, int]


@dataclass
class _Theme:
    panel: QColor
    border: QColor
    fg: QColor
    dim: QColor
    separator: QColor


_THEMES = {
    "dark": _Theme(QColor(24, 24, 28, 236), QColor(255, 255, 255, 38), QColor(245, 245, 245),
                   QColor(185, 185, 192), QColor(255, 255, 255, 30)),
    "light": _Theme(QColor(250, 250, 250, 242), QColor(0, 0, 0, 40), QColor(25, 25, 25),
                    QColor(95, 95, 100), QColor(0, 0, 0, 28)),
}


class OverlayWindow(QWidget):
    contextMenuRequested = Signal(QPoint)
    toggleDescriptiveRequested = Signal()
    toggleAttachRequested = Signal()
    toggleFreezeRequested = Signal()
    copyRequested = Signal()
    hideRequested = Signal()
    quitRequested = Signal()
    settingsChanged = Signal()   # overlay edited settings itself (drag position, wheel scale)

    def __init__(self, settings: Settings, reader: PixelReader) -> None:
        super().__init__(None)
        self.settings = settings
        self.reader = reader
        self.info: ColorInfo | None = None
        self.frozen = False
        self._last_rgb: RGB | None = None
        self._drag_offset: QPoint | None = None
        self._ops: list[tuple] = []
        self._shown_once = False

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        if sys.platform == "darwin":
            self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.apply_settings()
        self._timer.start()

    # ------------------------------------------------------------------ settings
    def apply_settings(self) -> None:
        s = self.settings
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                 | Qt.WindowType.Tool)
        if s.attach_to_cursor:
            flags |= (Qt.WindowType.WindowTransparentForInput
                      | Qt.WindowType.WindowDoesNotAcceptFocus)
        visible = self.isVisible()
        if flags != self.windowFlags():
            self.setWindowFlags(flags)
            if visible:
                self.show()
        self.setWindowOpacity(max(0.15, min(1.0, s.opacity)))
        self._timer.setInterval(max(10, int(s.update_interval_ms)))
        self._relayout()
        if not s.attach_to_cursor:
            self._place_free()
        self.update()

    def set_frozen(self, frozen: bool) -> None:
        self.frozen = frozen
        self._relayout()
        self.update()

    # ------------------------------------------------------------------ polling
    def _tick(self) -> None:
        s = self.settings
        cur = QCursor.pos()
        if s.attach_to_cursor:
            self._place_near(cur)
        elif self._drag_offset is not None or self.frameGeometry().contains(cur):
            return  # don't sample our own pixels
        if self.frozen:
            return
        rgb = self.reader.read_at_cursor(s.sample_size)
        if rgb is None or rgb == self._last_rgb:
            return
        self._last_rgb = rgb
        self.info = color_info(rgb)
        self._relayout()
        self.update()

    def _screen_for(self, pos: QPoint) -> QRect:
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        return screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)

    def _place_near(self, cur: QPoint) -> None:
        s = self.settings
        w, h = self.width(), self.height()
        avail = self._screen_for(cur)
        x = cur.x() + s.offset_x
        y = cur.y() + s.offset_y
        if x + w > avail.right():
            x = cur.x() - abs(s.offset_x) - w
        if y + h > avail.bottom():
            y = cur.y() - abs(s.offset_y) - h
        x = max(avail.left(), x)
        y = max(avail.top(), y)
        if QRect(x, y, w, h).contains(cur):
            # Never sit under the cursor: we would sample ourselves.
            x = cur.x() + 12 if cur.x() + 12 + w <= avail.right() else cur.x() - 12 - w
            y = cur.y() + 12 if cur.y() + 12 + h <= avail.bottom() else cur.y() - 12 - h
        if x != self.x() or y != self.y():
            self.move(x, y)

    def _place_free(self) -> None:
        s = self.settings
        if s.free_x < 0 or s.free_y < 0:
            avail = self._screen_for(QCursor.pos())
            s.free_x = avail.right() - self.width() - 40
            s.free_y = avail.top() + 40
        self.move(s.free_x, s.free_y)

    # ------------------------------------------------------------------ layout
    def _fonts(self) -> tuple[QFont, QFont, QFont, QFont]:
        s = self.settings
        base_pt = 10.0 * s.scale
        family = s.font_family or QFont().family()
        mono_family = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
        title = QFont(family)
        title.setPointSizeF(base_pt * 1.2)
        title.setBold(True)
        body = QFont(family)
        body.setPointSizeF(base_pt)
        mono = QFont(mono_family)
        mono.setPointSizeF(base_pt)
        mono_big = QFont(mono_family)
        mono_big.setPointSizeF(base_pt * 1.25)
        mono_big.setBold(True)
        return title, body, mono, mono_big

    def _text_rows(self, info: ColorInfo, fonts) -> list[tuple[QFont, str, str]]:
        """Rows of (font, role, text) for the main block. role: 'fg' | 'dim'."""
        s = self.settings
        title, body, mono, mono_big = fonts
        rows: list[tuple[QFont, str, str]] = []
        hexs = info.hex(s.uppercase_hex)
        r, g, b = info.rgb
        name = info.name if info.name_is_exact else f"≈ {info.name}"

        if s.descriptive_mode:
            if s.show_name:
                rows.append((title, "fg", name))
            if s.show_description:
                rows.append((body, "fg", info.description))
            line = []
            if s.show_hex:
                line.append(hexs)
            if s.show_rgb:
                line.append(f"rgb({r}, {g}, {b})")
            if line:
                rows.append((mono, "dim", "   ".join(line)))
            h, sat, l = info.hsl
            hv, sv, vv = info.hsv
            line = []
            if s.show_hsl:
                line.append(f"HSL {h:.0f}° {sat*100:.0f}% {l*100:.0f}%")
            if s.show_hsv:
                line.append(f"HSV {hv:.0f}° {sv*100:.0f}% {vv*100:.0f}%")
            if line:
                rows.append((mono, "dim", "   ".join(line)))
            if s.show_cmyk:
                c, m, y, k = info.cmyk
                rows.append((mono, "dim", f"CMYK {c*100:.0f} {m*100:.0f} {y*100:.0f} {k*100:.0f}"))
            if s.show_contrast:
                rows.append((mono, "dim",
                             f"Contrast  on white {info.contrast_white:.1f}:1"
                             f"   on black {info.contrast_black:.1f}:1"))
        else:
            if s.show_hex:
                rows.append((mono_big, "fg", hexs))
            if s.show_name:
                rows.append((body, "fg", name))
            if s.show_rgb:
                rows.append((mono, "dim", f"rgb({r}, {g}, {b})"))
        if not rows:
            rows.append((body, "fg", hexs))
        return rows

    def _relayout(self) -> None:
        s = self.settings
        sc = s.scale
        theme = _THEMES.get(s.theme, _THEMES["dark"])
        pad = round(12 * sc)
        gap = round(9 * sc)
        line_gap = round(3 * sc)
        fonts = self._fonts()
        title, body, mono, mono_big = fonts
        ops: list[tuple] = []

        if self.info is None:
            fm = QFontMetrics(body)
            text = "Move the cursor over a color…"
            w = pad + fm.horizontalAdvance(text) + pad
            h = pad + fm.height() + pad
            ops.append(("text", QPointF(pad, pad + fm.ascent()), body, theme.dim, text))
            self._ops = ops
            self._apply_size(QSize(w, h))
            return

        info = self.info
        rows = self._text_rows(info, fonts)
        metrics = [QFontMetrics(f) for f, _, _ in rows]
        text_w = max(fm.horizontalAdvance(t) for fm, (_, _, t) in zip(metrics, rows))
        text_h = sum(fm.height() for fm in metrics) + line_gap * (len(rows) - 1)
        swatch = round(s.swatch_size * sc)
        block_h = max(swatch, text_h)

        width = pad + swatch + gap + text_w + pad
        height = pad + block_h

        ops.append(("swatch", QRectF(pad, pad + (block_h - swatch) / 2, swatch, swatch), info.rgb))
        y = pad + (block_h - text_h) / 2
        tx = pad + swatch + gap
        for fm, (font, role, text) in zip(metrics, rows):
            color = theme.fg if role == "fg" else theme.dim
            ops.append(("text", QPointF(tx, y + fm.ascent()), font, color, text))
            y += fm.height() + line_gap

        enabled = s.enabled_simulations()
        sims = [sim for sim in info.simulations if sim[0] in enabled]
        if s.descriptive_mode and s.show_simulations and sims:
            fm = QFontMetrics(body)
            sw = fm.height()
            height += gap
            ops.append(("sep", height))
            height += gap
            for kind, rgb, desc in sims:
                label = CVD_LABELS[kind]
                text = f"{label}:  {desc}"
                ops.append(("swatch", QRectF(pad, height, sw, sw), rgb))
                ops.append(("text", QPointF(pad + sw + gap, height + fm.ascent()), body, theme.fg,
                            text))
                width = max(width, pad + sw + gap + fm.horizontalAdvance(text) + pad)
                height += sw + line_gap
            height -= line_gap

        if self.frozen:
            fm = QFontMetrics(mono)
            height += gap
            text = "FROZEN"
            ops.append(("text", QPointF(pad, height + fm.ascent()), mono, theme.dim, text))
            height += fm.height()

        height += pad
        self._ops = ops
        self._apply_size(QSize(round(width), round(height)))

    def _apply_size(self, size: QSize) -> None:
        if size != self.size():
            self.resize(size)
            self.setFixedSize(size)

    # ------------------------------------------------------------------ painting
    def paintEvent(self, _event) -> None:
        s = self.settings
        theme = _THEMES.get(s.theme, _THEMES["dark"])
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        radius = s.corner_radius * s.scale
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(theme.border, 1))
        p.setBrush(theme.panel)
        p.drawRoundedRect(rect, radius, radius)

        for op in self._ops:
            kind = op[0]
            if kind == "swatch":
                _, r, rgb = op
                p.setPen(QPen(theme.border, 1))
                p.setBrush(QColor(*rgb))
                p.drawRoundedRect(r, 4 * s.scale, 4 * s.scale)
            elif kind == "text":
                _, pos, font, color, text = op
                p.setFont(font)
                p.setPen(color)
                p.drawText(pos, text)
            elif kind == "sep":
                _, y = op
                p.setPen(QPen(theme.separator, 1))
                p.drawLine(QPointF(rect.left() + 8, y), QPointF(rect.right() - 8, y))
        p.end()

    # ------------------------------------------------------------------ interaction (free mode)
    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and not self.settings.attach_to_cursor:
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:
        if self._drag_offset is not None:
            self.move(e.globalPosition().toPoint() - self._drag_offset)
            e.accept()
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        if self._drag_offset is not None:
            self._drag_offset = None
            self.settings.free_x = self.x()
            self.settings.free_y = self.y()
            self.settingsChanged.emit()
            e.accept()
        else:
            super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self.toggleDescriptiveRequested.emit()
            e.accept()

    def contextMenuEvent(self, e) -> None:
        self.contextMenuRequested.emit(e.globalPos())
        e.accept()

    def wheelEvent(self, e) -> None:
        step = 0.1 if e.angleDelta().y() > 0 else -0.1
        self.settings.scale = round(max(0.5, min(3.0, self.settings.scale + step)), 2)
        self._relayout()
        self.update()
        self.settingsChanged.emit()
        e.accept()

    def keyPressEvent(self, e) -> None:
        key = e.key()
        mods = e.modifiers()
        if key == Qt.Key.Key_C:  # plain C or Ctrl+C
            self.copyRequested.emit()
        elif key in (Qt.Key.Key_Space, Qt.Key.Key_F):
            self.toggleFreezeRequested.emit()
        elif key == Qt.Key.Key_D:
            self.toggleDescriptiveRequested.emit()
        elif key == Qt.Key.Key_A:
            self.toggleAttachRequested.emit()
        elif key == Qt.Key.Key_Escape:
            self.hideRequested.emit()
        elif key == Qt.Key.Key_Q and (mods & Qt.KeyboardModifier.ControlModifier):
            self.quitRequested.emit()
        else:
            super().keyPressEvent(e)
