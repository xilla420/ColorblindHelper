"""Custom widgets for the settings window: toggle switch, painting theme cards,
hotkey recorder, the gallery banner with a live overlay preview, painted panels,
colour-vision painting thumbnails and the artist's palette."""
from __future__ import annotations

import math

from PySide6.QtCore import (Property, QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize,
                            Qt, QTimer, Signal)
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QFontMetrics, QLinearGradient,
                           QPainter, QPainterPath, QPen)
from PySide6.QtWidgets import (QAbstractButton, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QMenu, QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from .colors import color_info, simulate_cvd
from .overlay import OverlayRenderer, anim_time
from .paintings import (GALLERY, PAINTINGS, blurred_image, cover_image, simulated_image,
                        to_pixmap)
from .themes import MATCH, Theme, get_theme, paint_canvas, serif, serif_family

_active: list[Theme] = [get_theme("starry")]


def active_theme() -> Theme:
    return _active[0]


def set_active_theme(t: Theme) -> None:
    _active[0] = t


def _dpr(w: QWidget) -> float:
    return max(1.0, w.devicePixelRatioF())


# --------------------------------------------------------------------------- layout helpers

def card(*rows: QWidget, spacing: int = 0) -> QFrame:
    """A rounded card holding rows separated by hairlines."""
    frame = QFrame()
    frame.setObjectName("Card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(14, 6, 14, 6)
    lay.setSpacing(spacing)
    for i, r in enumerate(rows):
        if i:
            div = QFrame()
            div.setObjectName("RowDivider")
            lay.addWidget(div)
        lay.addWidget(r)
    return frame


def row(title: str, control: QWidget | None = None, desc: str = "",
        leading: QWidget | None = None, below: QWidget | None = None) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 8, 0, 8)
    lay.setSpacing(12)
    if leading is not None:
        lay.addWidget(leading, 0, Qt.AlignmentFlag.AlignVCenter)
    texts = QVBoxLayout()
    texts.setSpacing(2)
    texts.addWidget(QLabel(title))
    if desc:
        d = QLabel(desc)
        d.setObjectName("desc")
        d.setWordWrap(True)
        f = d.font()
        f.setPointSizeF(f.pointSizeF() * 0.88)
        d.setFont(f)
        texts.addWidget(d)
    if below is not None:
        texts.addSpacing(4)
        texts.addWidget(below)
    lay.addLayout(texts, 1)
    if control is not None:
        lay.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
    return w


def section(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("section")
    return lbl


def _rounded(r: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(r, radius, radius)
    return path


# --------------------------------------------------------------------------- toggle switch

class ToggleSwitch(QAbstractButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def sizeHint(self) -> QSize:
        return QSize(42, 22)

    def _get_knob(self) -> float:
        return self._pos

    def _set_knob(self, v: float) -> None:
        self._pos = v
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def setChecked(self, checked: bool) -> None:  # noqa: N802 - Qt API
        super().setChecked(checked)
        if self.signalsBlocked():  # programmatic refresh: jump without animating
            self._anim.stop()
            self._pos = 1.0 if checked else 0.0
            self.update()

    def paintEvent(self, _e) -> None:
        t = active_theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        off, on = QColor(t.border), QColor(t.accent)
        k = self._pos
        track = QColor(int(off.red() + (on.red() - off.red()) * k),
                       int(off.green() + (on.green() - off.green()) * k),
                       int(off.blue() + (on.blue() - off.blue()) * k))
        if not self.isEnabled():
            track.setAlpha(110)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * k
        p.setBrush(QColor(0, 0, 0, 45))
        p.drawEllipse(QRectF(x, r.top() + 4, d, d))
        p.setBrush(QColor("#fffdf6"))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))
        p.end()


# --------------------------------------------------------------------------- theme card

class ThemeCard(QAbstractButton):
    """A small framed painting (or canvas swatch) for picking a theme."""

    def __init__(self, key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key = key
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(128, 88)
        self._hover = False
        theme = get_theme(key) if key != MATCH else None
        if theme is not None:
            p = PAINTINGS.get(theme.painting) if theme.painting else None
            self.setToolTip(f"{p.title}, {p.year} — {p.collection}" if p else theme.name)
        else:
            self.setToolTip("Use the same theme as this window")

    def enterEvent(self, e) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, e) -> None:
        self._hover = False
        self.update()

    def paintEvent(self, _e) -> None:
        ui = active_theme()
        t = ui if self.key == MATCH else get_theme(self.key)
        name = "Match window" if self.key == MATCH else t.name
        dpr = _dpr(self)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        r = QRectF(2, 2, self.width() - 4, self.height() - 4)
        clip = _rounded(r, 10)
        p.save()
        p.setClipPath(clip)
        if t.painting:
            p.drawImage(r, cover_image(t.painting, int(r.width() * dpr), int(r.height() * dpr),
                                       1.15 if self._hover else 1.0))
        else:
            paint_canvas(p, r, t)
            for i, attr in enumerate(("surface", "accent", "accent2", "text")):
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(getattr(t, attr)))
                p.drawEllipse(QPointF(r.left() + 20 + i * 22, r.top() + 24), 9, 9)
        g = QLinearGradient(r.left(), r.bottom() - 40, r.left(), r.bottom())
        g.setColorAt(0, QColor(0, 0, 0, 0))
        g.setColorAt(1, QColor(0, 0, 0, 185))
        p.fillRect(r, g)
        p.restore()

        f = serif(9.5, bold=True)
        p.setFont(f)
        fm = QFontMetrics(f)
        text_rect = QRectF(r.left() + 8, r.bottom() - fm.height() - 5, r.width() - 16,
                           fm.height())
        p.setPen(QColor(255, 250, 235))
        p.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   fm.elidedText(name, Qt.TextElideMode.ElideRight, int(text_rect.width())))

        if self.isChecked():
            p.setPen(QPen(QColor(ui.accent), 3))
        elif self._hover:
            p.setPen(QPen(QColor(ui.subtext), 1.5))
        else:
            p.setPen(QPen(QColor(ui.border), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 10, 10)
        if self.isChecked():
            c = QPointF(r.right() - 12, r.top() + 12)
            p.setPen(QPen(QColor(255, 255, 255, 200), 1.5))
            p.setBrush(QColor(ui.accent))
            p.drawEllipse(c, 9, 9)
            p.setPen(QPen(QColor(ui.accent_text), 2, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            check = QPainterPath(QPointF(c.x() - 4, c.y()))
            check.lineTo(c.x() - 1, c.y() + 3)
            check.lineTo(c.x() + 4, c.y() - 3)
            p.drawPath(check)
        p.end()


# --------------------------------------------------------------------------- hotkey recorder

_MOD_NAMES = [(Qt.KeyboardModifier.ControlModifier, "<ctrl>"),
              (Qt.KeyboardModifier.AltModifier, "<alt>"),
              (Qt.KeyboardModifier.ShiftModifier, "<shift>"),
              (Qt.KeyboardModifier.MetaModifier, "<cmd>")]
_SPECIAL = {Qt.Key.Key_Space: "<space>", Qt.Key.Key_Tab: "<tab>", Qt.Key.Key_Home: "<home>",
            Qt.Key.Key_End: "<end>", Qt.Key.Key_PageUp: "<page_up>",
            Qt.Key.Key_PageDown: "<page_down>", Qt.Key.Key_Insert: "<insert>",
            Qt.Key.Key_Delete: "<delete>", Qt.Key.Key_Up: "<up>", Qt.Key.Key_Down: "<down>",
            Qt.Key.Key_Left: "<left>", Qt.Key.Key_Right: "<right>"}
_MODIFIER_KEYS = {Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta,
                  Qt.Key.Key_AltGr, Qt.Key.Key_CapsLock}


def pretty_hotkey(combo: str) -> str:
    if not combo:
        return "Not set"
    names = {"<ctrl>": "Ctrl", "<alt>": "Alt", "<shift>": "Shift", "<cmd>": "Win/Cmd"}
    parts = []
    for part in combo.split("+"):
        part = part.strip()
        if part in names:
            parts.append(names[part])
        elif part.startswith("<") and part.endswith(">"):
            parts.append(part[1:-1].replace("_", " ").title())
        else:
            parts.append(part.upper())
    return " + ".join(parts)


class HotkeyRecorder(QPushButton):
    """Click, then press a key combination. Esc cancels, Backspace clears."""
    hotkeyChanged = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._combo = ""
        self._recording = False
        self.setMinimumWidth(150)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.clicked.connect(self._start)
        self._refresh()

    def combo(self) -> str:
        return self._combo

    def setCombo(self, combo: str) -> None:  # noqa: N802
        self._combo = combo
        self._refresh()

    def _refresh(self) -> None:
        self.setText("Press keys…" if self._recording else pretty_hotkey(self._combo))
        self.setObjectName("primary" if self._recording else "")
        self.style().unpolish(self)
        self.style().polish(self)

    def _start(self) -> None:
        self._recording = True
        self._refresh()
        self.grabKeyboard()

    def _stop(self) -> None:
        self._recording = False
        self.releaseKeyboard()
        self._refresh()

    def focusOutEvent(self, e) -> None:
        if self._recording:
            self._stop()
        super().focusOutEvent(e)

    def keyPressEvent(self, e) -> None:
        if not self._recording:
            return super().keyPressEvent(e)
        key = e.key()
        if key in _MODIFIER_KEYS:
            return
        if key == Qt.Key.Key_Escape:
            self._stop()
            return
        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete) and not e.modifiers():
            self._combo = ""
            self._stop()
            self.hotkeyChanged.emit("")
            return
        parts = [pyn for mod, pyn in _MOD_NAMES if e.modifiers() & mod]
        if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
            parts.append(f"<f{key - Qt.Key.Key_F1 + 1}>")
        elif key in _SPECIAL:
            parts.append(_SPECIAL[key])
        elif 0x20 < key < 0x7F:
            parts.append(chr(key).lower())
        else:
            return
        if len(parts) < 2 and not parts[-1].startswith("<f"):
            self.setText("Add Ctrl / Alt / Shift…")
            return
        self._combo = "+".join(parts)
        self._stop()
        self.hotkeyChanged.emit(self._combo)


# --------------------------------------------------------------------------- painted surfaces

class PaintedPanel(QFrame):
    """Background panel: the theme's painting, softly blurred under a tint."""

    def __init__(self, tint_alpha: float = 0.84, border_right: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tint_alpha = tint_alpha
        self.border_right = border_right
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    def paintEvent(self, _e) -> None:
        t = active_theme()
        p = QPainter(self)
        r = QRectF(self.rect())
        if t.painting:
            dpr = _dpr(self)
            p.drawImage(r, blurred_image(t.painting, int(r.width() * dpr / 2) + 1,
                                         int(r.height() * dpr / 2) + 1))
            tint = QColor(t.surface)
            tint.setAlphaF(self.tint_alpha)
            p.fillRect(r, tint)
        else:
            paint_canvas(p, r, t)
        if self.border_right:
            p.setPen(QPen(QColor(t.border), 1))
            p.drawLine(r.topRight() - QPointF(0.5, 0), r.bottomRight() - QPointF(0.5, 0))
        p.end()


class LivePreview(QWidget):
    """Renders the real overlay for the colour currently under the cursor."""

    def __init__(self, settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.renderer = OverlayRenderer(settings)
        self.info = color_info((242, 201, 76))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.relayout()

    def set_info(self, info) -> None:
        if info is not None and info != self.info:
            self.info = info
            self.relayout()
            self.update()

    def relayout(self) -> None:
        size = self.renderer.layout(self.info)
        if size != self.size():
            self.setFixedSize(size)
            self.updateGeometry()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setOpacity(max(0.15, min(1.0, self.settings.opacity)))
        self.renderer.paint(p, 0.0)
        p.end()


class Banner(QWidget):
    """The gallery banner: the theme's painting drifting slowly (Ken Burns), a
    museum-label caption, the page title, and the live overlay preview."""

    HOLD, FADE = 16.0, 1.6  # gallery rotation for the plain studio themes

    def __init__(self, settings, title: str, subtitle: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setFixedHeight(156)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self._title, self._subtitle = title, subtitle
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 16, 18, 30)
        lay.addStretch(1)
        self.preview = LivePreview(settings)
        lay.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignVCenter)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._frame)
        self._timer.start(66)

    def set_page(self, title: str, subtitle: str) -> None:
        self._title, self._subtitle = title, subtitle
        self.update()

    def _frame(self) -> None:
        # Only move while the window is focused: keeps background CPU near zero.
        if self.isVisible() and self.settings.decorations and self.window().isActiveWindow():
            self.update()

    def current_painting(self, now: float) -> tuple[str, str | None, float]:
        """(painting, next painting or None, crossfade 0..1)."""
        t = active_theme()
        if t.painting:
            return t.painting, None, 0.0
        cycle = self.HOLD + self.FADE
        idx = int(now // cycle) % len(GALLERY)
        phase = now % cycle
        fade = max(0.0, (phase - self.HOLD) / self.FADE)
        nxt = GALLERY[(idx + 1) % len(GALLERY)] if fade > 0 else None
        return GALLERY[idx], nxt, fade

    def _draw_painting(self, p: QPainter, key: str, r: QRectF, now: float) -> None:
        dpr = _dpr(self)
        base = cover_image(key, int(r.width() * dpr * 1.15), int(r.height() * dpr * 1.15))
        if self.settings.decorations:
            zoom = 1.09 + 0.05 * math.sin(now * 0.045)
            px = 0.5 + 0.45 * math.sin(now * 0.031)
            py = 0.5 + 0.45 * math.cos(now * 0.023)
        else:
            zoom, px, py = 1.0, 0.5, 0.5
        sw, sh = base.width() / zoom, base.height() / zoom
        src = QRectF((base.width() - sw) * px, (base.height() - sh) * py, sw, sh)
        p.drawImage(r, base, src)

    def paintEvent(self, _e) -> None:
        t = active_theme()
        now = anim_time() if self.settings.decorations else 0.0
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(self.rect())
        key, nxt, fade = self.current_painting(now)
        self._draw_painting(p, key, r, now)
        if nxt:
            p.setOpacity(fade)
            self._draw_painting(p, nxt, r, now)
            p.setOpacity(1.0)

        # Scrims: tinted on the left for the title, darker at the bottom for the caption.
        g = QLinearGradient(r.left(), 0, r.right(), 0)
        bg = QColor(t.bg)
        for stop, alpha in ((0.0, 0.93), (0.38, 0.72), (0.7, 0.12), (1.0, 0.0)):
            c = QColor(bg)
            c.setAlphaF(alpha)
            g.setColorAt(stop, c)
        p.fillRect(r, g)
        g2 = QLinearGradient(0, r.bottom() - 34, 0, r.bottom())
        g2.setColorAt(0, QColor(0, 0, 0, 0))
        g2.setColorAt(1, QColor(0, 0, 0, 120))
        p.fillRect(r, g2)

        # Title + subtitle (painted: cheaper than styled labels at 15 fps).
        text_w = self.preview.x() - 24 - 16
        tf = serif(20, bold=True)
        sf = QFont(self.font())
        sf.setPointSizeF(self.font().pointSizeF() * 0.95)
        tfm, sfm = QFontMetrics(tf), QFontMetrics(sf)
        sub_rect = sfm.boundingRect(0, 0, text_w, 200, Qt.TextFlag.TextWordWrap, self._subtitle)
        total = tfm.height() + 2 + sub_rect.height()
        y = (r.height() - 20 - total) / 2
        p.setFont(tf)
        p.setPen(QColor(t.text))
        p.drawText(QRectF(24, y, text_w, tfm.height()), Qt.AlignmentFlag.AlignLeft, self._title)
        p.setFont(sf)
        p.setPen(QColor(t.subtext))
        p.drawText(QRectF(24, y + tfm.height() + 2, text_w, sub_rect.height()),
                   Qt.TextFlag.TextWordWrap, self._subtitle)

        # Museum label, bottom right.
        painting = PAINTINGS[nxt if fade > 0.5 else key]
        cf = serif(8.5, italic=True)
        cfm = QFontMetrics(cf)
        cap = painting.caption
        cw = cfm.horizontalAdvance(cap) + 18
        cap_rect = QRectF(r.right() - cw - 12, r.bottom() - cfm.height() - 12, cw,
                          cfm.height() + 6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 120))
        p.drawRoundedRect(cap_rect, cap_rect.height() / 2, cap_rect.height() / 2)
        p.setFont(cf)
        p.setPen(QColor(255, 248, 230))
        p.drawText(cap_rect, Qt.AlignmentFlag.AlignCenter, cap)

        p.setPen(QPen(QColor(t.border), 1))
        p.drawLine(r.bottomLeft() - QPointF(0, 0.5), r.bottomRight() - QPointF(0, 0.5))
        p.end()


# --------------------------------------------------------------------------- vision widgets

class CvdStrip(QWidget):
    """A row of colour chips as they appear for one vision type (or typical vision)."""
    PALETTE = [(230, 57, 70), (244, 140, 6), (255, 209, 102), (88, 204, 2), (6, 214, 160),
               (17, 138, 178), (58, 80, 230), (155, 93, 229), (241, 91, 181), (140, 90, 50)]

    def __init__(self, kind: str | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.extra: tuple[int, int, int] | None = None
        self.setFixedHeight(16)
        self.setMinimumWidth(160)

    def set_extra(self, rgb) -> None:
        self.extra = rgb
        self.update()

    def paintEvent(self, _e) -> None:
        t = active_theme()
        colors = list(self.PALETTE)
        if self.extra is not None:
            colors.append(self.extra)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        n = len(colors)
        gap = 3
        w = (self.width() - gap * (n - 1)) / n
        for i, rgb in enumerate(colors):
            if self.kind:
                rgb = simulate_cvd(rgb, self.kind)
            r = QRectF(i * (w + gap), 1, w, self.height() - 2)
            is_extra = self.extra is not None and i == n - 1
            p.setPen(QPen(QColor(t.accent), 2) if is_extra else Qt.PenStyle.NoPen)
            p.setBrush(QColor(*rgb))
            p.drawRoundedRect(r, 4, 4)
        p.end()


class PaintingThumb(QWidget):
    """A painting as seen with one colour-vision type. Rendered lazily, then cached."""

    def __init__(self, kind: str | None, w: int = 132, h: int = 88,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(w, h)
        self._key: str | None = None
        self._img = None

    def set_painting(self, key: str) -> None:
        if key != self._key:
            self._key = key
            self._img = None
            self.update()
            QTimer.singleShot(0, self._render)

    def _render(self) -> None:
        if self._key and self._img is None and self.isVisible():
            dpr = _dpr(self)
            self._img = simulated_image(self._key, self.kind, int(self.width() * dpr),
                                        int(self.height() * dpr))
            self.update()

    def showEvent(self, e) -> None:
        super().showEvent(e)
        QTimer.singleShot(0, self._render)

    def paintEvent(self, _e) -> None:
        t = active_theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        clip = _rounded(r, 8)
        p.setClipPath(clip)
        if self._img is not None:
            p.drawImage(r, self._img)
        else:
            p.fillRect(r, QColor(t.surface_alt))
        p.setClipping(False)
        p.setPen(QPen(QColor(t.border), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(clip)
        p.end()


# --------------------------------------------------------------------------- the palette

class SwatchTile(QAbstractButton):
    """One colour on the artist's palette. Click copies, right-click removes."""
    removeRequested = Signal(str)

    def __init__(self, hex_code: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.hex = hex_code
        self.info = color_info(tuple(int(hex_code[i:i + 2], 16) for i in (1, 3, 5)))
        self.setFixedSize(76, 84)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{self.info.name} — {self.info.description}\n"
                        "Click to copy · right-click to remove")
        self._hover = False

    def enterEvent(self, e) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, e) -> None:
        self._hover = False
        self.update()

    def contextMenuEvent(self, e) -> None:
        menu = QMenu(self)
        menu.addAction("Remove from palette", lambda: self.removeRequested.emit(self.hex))
        menu.exec(e.globalPos())

    def paintEvent(self, _e) -> None:
        t = active_theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # A paint dab: a soft blob with an irregular edge.
        dab = QRectF(8, 4, self.width() - 16, self.width() - 16)
        c = dab.center()
        path = QPainterPath()
        seed = sum(self.info.rgb)
        for i in range(25):
            a = i / 24 * math.tau
            wobble = 1 + 0.06 * math.sin(a * 3 + seed) + 0.04 * math.sin(a * 5 + seed * 0.7)
            pt = QPointF(c.x() + math.cos(a) * dab.width() / 2 * wobble,
                         c.y() + math.sin(a) * dab.height() / 2 * wobble)
            path.moveTo(pt) if i == 0 else path.lineTo(pt)
        path.closeSubpath()
        p.setPen(QPen(QColor(t.accent) if self._hover else QColor(t.border), 2 if self._hover else 1))
        p.setBrush(QColor(*self.info.rgb))
        p.drawPath(path)
        f = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        f.setPointSizeF(8)
        p.setFont(f)
        p.setPen(QColor(t.text))
        p.drawText(QRectF(0, self.height() - 18, self.width(), 16), Qt.AlignmentFlag.AlignCenter,
                   self.hex)
        p.end()


class PaletteGrid(QWidget):
    copyRequested = Signal(str)
    removeRequested = Signal(str)
    COLUMNS = 6

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 6, 0, 6)
        self._grid.setSpacing(4)
        self._colors: list[str] = []
        self._empty = QLabel("Your palette is empty. Copy a colour (Ctrl+Shift+C, or C on the "
                             "overlay) and it lands here, like paint squeezed onto a palette.")
        self._empty.setObjectName("caption")
        self._empty.setWordWrap(True)

    def set_colors(self, colors: list[str]) -> None:
        if colors == self._colors:
            return
        self._colors = list(colors)
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget() is not None and item.widget() is not self._empty:
                item.widget().deleteLater()
        if not colors:
            self._grid.addWidget(self._empty, 0, 0)
            self._empty.show()
            return
        self._empty.hide()
        for i, hx in enumerate(colors):
            tile = SwatchTile(hx)
            tile.clicked.connect(lambda _=False, h=hx: self.copyRequested.emit(h))
            tile.removeRequested.connect(self.removeRequested.emit)
            self._grid.addWidget(tile, i // self.COLUMNS, i % self.COLUMNS)
        self._grid.setColumnStretch(self.COLUMNS, 1)


__all__ = ["ToggleSwitch", "ThemeCard", "HotkeyRecorder", "LivePreview", "Banner", "CvdStrip",
           "PaintingThumb", "PaintedPanel", "PaletteGrid", "card", "row", "section",
           "active_theme", "set_active_theme", "serif_family"]
