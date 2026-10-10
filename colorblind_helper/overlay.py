"""The always-on-top overlay that shows the color under the cursor, and the
renderer it shares with the live preview in the settings window."""
from __future__ import annotations

import sys
import time

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QColor, QCursor, QFont, QFontDatabase, QFontMetrics, QGuiApplication,
                           QPainter, QPainterPath, QPen)
from PySide6.QtWidgets import QWidget

from .colors import CVD_LABELS, ColorInfo, color_info
from .pixel import PixelReader
from .settings import Settings
from .themes import Theme, overlay_theme, paint_decor

RGB = tuple[int, int, int]
_T0 = time.monotonic()


def anim_time() -> float:
    return time.monotonic() - _T0


class OverlayRenderer:
    """Lays out and paints the overlay card. Stateless apart from the last layout."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ops: list[tuple] = []
        self.size = QSize(10, 10)
        self.swatch_rect = QRectF()

    @property
    def theme(self) -> Theme:
        return overlay_theme(self.settings)

    # ------------------------------------------------------------------ fonts / rows
    def _fonts(self) -> tuple[QFont, QFont, QFont, QFont, QFont]:
        s = self.settings
        base_pt = 10.0 * s.scale
        family = s.font_family or QFont().family()
        mono_family = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()

        def make(fam: str, mult: float, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
            f = QFont(fam)
            f.setPointSizeF(base_pt * mult)
            f.setWeight(weight)
            return f

        return (make(family, 1.2, QFont.Weight.Bold), make(family, 1.0),
                make(mono_family, 0.95), make(mono_family, 1.25, QFont.Weight.Bold),
                make(family, 0.8, QFont.Weight.DemiBold))

    def _text_rows(self, info: ColorInfo, fonts) -> list[tuple[QFont, str, str]]:
        """Rows of (font, role, text). role: 'fg' | 'dim'."""
        s = self.settings
        title, body, mono, mono_big, _ = fonts
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
                             f"Contrast  white {info.contrast_white:.1f}:1"
                             f"   black {info.contrast_black:.1f}:1"))
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

    # ------------------------------------------------------------------ layout
    def layout(self, info: ColorInfo | None, frozen: bool = False) -> QSize:
        s = self.settings
        sc = s.scale
        pad = round(12 * sc)
        gap = round(10 * sc)
        line_gap = round(3 * sc)
        fonts = self._fonts()
        title, body, mono, mono_big, small = fonts
        ops: list[tuple] = []

        if info is None:
            fm = QFontMetrics(body)
            text = "Hover over any colour…"
            ops.append(("text", QPointF(pad, pad + fm.ascent()), body, "dim", text))
            self.ops = ops
            self.swatch_rect = QRectF()
            self.size = QSize(pad + fm.horizontalAdvance(text) + pad, pad + fm.height() + pad)
            return self.size

        rows = self._text_rows(info, fonts)
        metrics = [QFontMetrics(f) for f, _, _ in rows]
        text_w = max(fm.horizontalAdvance(t) for fm, (_, _, t) in zip(metrics, rows))
        text_h = sum(fm.height() for fm in metrics) + line_gap * (len(rows) - 1)
        swatch = round(s.swatch_size * sc)
        block_h = max(swatch, text_h)

        width = pad + swatch + gap + text_w + pad
        height = pad + block_h

        self.swatch_rect = QRectF(pad, pad + (block_h - swatch) / 2, swatch, swatch)
        ops.append(("swatch", self.swatch_rect, info.rgb, True))
        y = pad + (block_h - text_h) / 2
        tx = pad + swatch + gap
        for fm, (font, role, text) in zip(metrics, rows):
            ops.append(("text", QPointF(tx, y + fm.ascent()), font, role, text))
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
                label = CVD_LABELS[kind].split(" (")[0]
                lw = QFontMetrics(small).horizontalAdvance(label)
                ops.append(("swatch", QRectF(pad, height, sw, sw), rgb, False))
                ops.append(("text", QPointF(pad + sw + gap * 0.8, height + fm.ascent()), small,
                            "dim", label))
                col2 = pad + sw + gap * 0.8 + max(lw, QFontMetrics(small).horizontalAdvance(
                    "Achromat")) + gap
                ops.append(("text", QPointF(col2, height + fm.ascent()), body, "fg", desc))
                width = max(width, col2 + fm.horizontalAdvance(desc) + pad)
                height += sw + line_gap
            height -= line_gap

        if frozen:
            fm = QFontMetrics(small)
            height += gap
            text = "❄  Frozen"
            pill = QRectF(pad, height, fm.horizontalAdvance(text) + 16 * sc, fm.height() + 6 * sc)
            ops.append(("pill", pill, small, text))
            height += pill.height()

        height += pad
        self.ops = ops
        self.size = QSize(round(width), round(height))
        return self.size

    # ------------------------------------------------------------------ painting
    def paint(self, p: QPainter, now: float, copied: float = 0.0) -> None:
        """`copied` in 0..1 fades the "copied" check badge over the swatch."""
        s = self.settings
        t = self.theme
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        radius = s.corner_radius * s.scale
        rect = QRectF(0, 0, self.size.width(), self.size.height()).adjusted(0.5, 0.5, -0.5, -0.5)
        panel = QPainterPath()
        panel.addRoundedRect(rect, radius, radius)
        p.fillPath(panel, t.c("surface", 246))
        if s.decorations:
            p.save()
            p.setClipPath(panel)
            paint_decor(p, rect, t, now, intensity=0.4)  # subtle: text must stay readable
            p.restore()
        p.setPen(QPen(t.c("border"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(panel)

        fg, dim = t.c("text"), t.c("subtext")
        for op in self.ops:
            kind = op[0]
            if kind == "swatch":
                _, r, rgb, main = op
                rr = 6 * s.scale if main else 3 * s.scale
                p.setPen(QPen(t.c("border"), 2 if main else 1))
                p.setBrush(QColor(*rgb))
                p.drawRoundedRect(r, rr, rr)
                # inner hairline so the swatch edge is visible on any background
                p.setPen(QPen(QColor(0, 0, 0, 40) if not t.dark else QColor(255, 255, 255, 40), 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(r.adjusted(1.5, 1.5, -1.5, -1.5), rr - 1, rr - 1)
            elif kind == "text":
                _, pos, font, role, text = op
                p.setFont(font)
                p.setPen(fg if role == "fg" else dim)
                p.drawText(pos, text)
            elif kind == "sep":
                _, y = op
                p.setPen(QPen(t.c("border"), 1))
                p.drawLine(QPointF(rect.left() + 10, y), QPointF(rect.right() - 10, y))
            elif kind == "pill":
                _, r, font, text = op
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(t.c("accent"))
                p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
                p.setFont(font)
                p.setPen(t.c("accent_text"))
                p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)

        if copied > 0 and not self.swatch_rect.isNull():
            r = self.swatch_rect
            d = max(14.0, r.width() * 0.55)
            c = QPointF(r.right() - d * 0.25, r.bottom() - d * 0.25)
            p.setOpacity(min(1.0, copied * 2))
            p.setPen(QPen(t.c("surface"), 2))
            p.setBrush(t.c("accent"))
            p.drawEllipse(c, d / 2, d / 2)
            pen = QPen(t.c("accent_text"), max(2.0, d * 0.12), Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            path = QPainterPath(QPointF(c.x() - d * 0.2, c.y()))
            path.lineTo(c.x() - d * 0.04, c.y() + d * 0.16)
            path.lineTo(c.x() + d * 0.22, c.y() - d * 0.14)
            p.drawPath(path)
            p.setOpacity(1.0)


class OverlayWindow(QWidget):
    contextMenuRequested = Signal(QPoint)
    toggleDescriptiveRequested = Signal()
    toggleAttachRequested = Signal()
    toggleFreezeRequested = Signal()
    copyRequested = Signal()
    hideRequested = Signal()
    quitRequested = Signal()
    settingsChanged = Signal()   # overlay edited settings itself (drag position, wheel scale)
    colorChanged = Signal(object)  # ColorInfo

    def __init__(self, settings: Settings, reader: PixelReader) -> None:
        super().__init__(None)
        self.settings = settings
        self.reader = reader
        self.renderer = OverlayRenderer(settings)
        self.info: ColorInfo | None = None
        self.frozen = False
        self._last_rgb: RGB | None = None
        self._drag_offset: QPoint | None = None
        self._copied_at = -10.0
        self._last_pos = QPoint(-1, -1)
        self._last_sample = -10.0
        self._last_paint = -10.0

        self.setWindowTitle("Colorblind Helper overlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        if sys.platform == "darwin":
            self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
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

    def flash_copied(self) -> None:
        self._copied_at = anim_time()
        self.update()

    # ------------------------------------------------------------------ polling
    def _tick(self) -> None:
        s = self.settings
        if not self.isVisible():
            return
        cur = QCursor.pos()
        now = anim_time()
        moved = cur != self._last_pos
        self._last_pos = cur
        if s.attach_to_cursor and moved:
            self._place_near(cur)
        # Decorations animate at ~12 fps; the copy badge fades smoothly.
        animating = (now - self._copied_at < 1.3) or (
            s.decorations and now - self._last_paint >= 0.08)
        skip_sample = (self.frozen or (not s.attach_to_cursor and (
            self._drag_offset is not None or self.frameGeometry().contains(cur))))
        # Reading the screen is the expensive part (~4 ms through the compositor):
        # sample every tick while the mouse moves, ~4x/s while it rests.
        if not skip_sample and (moved or now - self._last_sample >= 0.25):
            self._last_sample = now
            rgb = self.reader.read_at_cursor(s.sample_size)
            if rgb is not None and rgb != self._last_rgb:
                self._last_rgb = rgb
                self.info = color_info(rgb)
                self._relayout()
                if s.attach_to_cursor:  # size may have changed near a screen edge
                    self._place_near(cur)
                self.colorChanged.emit(self.info)
                animating = True
        if animating:
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
        # Keep it on a connected screen (monitors may have changed since last run).
        if QGuiApplication.screenAt(QPoint(s.free_x + 10, s.free_y + 10)) is None:
            avail = self._screen_for(QCursor.pos())
            s.free_x, s.free_y = avail.right() - self.width() - 40, avail.top() + 40
        self.move(s.free_x, s.free_y)

    def _relayout(self) -> None:
        size = self.renderer.layout(self.info, self.frozen)
        if size != self.size():
            self.setFixedSize(size)

    # ------------------------------------------------------------------ painting
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        self._last_paint = anim_time()
        since = anim_time() - self._copied_at
        copied = max(0.0, 1.0 - since / 1.2) if since >= 0 else 0.0
        self.renderer.paint(p, anim_time() if self.settings.decorations else 0.0, copied)
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
