"""Small custom widgets for the settings window: toggle switch, theme cards,
hotkey recorder, animated banner with live overlay preview, CVD palette strips."""
from __future__ import annotations

from PySide6.QtCore import (Property, QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize,
                            Qt, QTimer, Signal)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from .colors import CVD_LABELS, color_info, simulate_cvd
from .overlay import OverlayRenderer, anim_time
from .themes import Theme, get_theme, paint_decor, paint_theme_background

_active: list[Theme] = [get_theme("starry")]


def active_theme() -> Theme:
    return _active[0]


def set_active_theme(t: Theme) -> None:
    _active[0] = t


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


def row(title: str, control: QWidget | None = None, desc: str = "") -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 8, 0, 8)
    lay.setSpacing(12)
    texts = QVBoxLayout()
    texts.setSpacing(1)
    t = QLabel(title)
    texts.addWidget(t)
    if desc:
        d = QLabel(desc)
        d.setObjectName("desc")
        d.setWordWrap(True)
        f = d.font()
        f.setPointSizeF(f.pointSizeF() * 0.88)
        d.setFont(f)
        texts.addWidget(d)
    lay.addLayout(texts, 1)
    if control is not None:
        lay.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
    return w


def section(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("section")
    return lbl


# --------------------------------------------------------------------------- toggle switch

class ToggleSwitch(QAbstractButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def sizeHint(self) -> QSize:
        return QSize(40, 22)

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
        track = QColor(
            int(off.red() + (on.red() - off.red()) * self._pos),
            int(off.green() + (on.green() - off.green()) * self._pos),
            int(off.blue() + (on.blue() - off.blue()) * self._pos))
        if not self.isEnabled():
            track.setAlpha(110)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * self._pos
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawEllipse(QRectF(x, r.top() + 4, d, d))
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))
        p.end()


# --------------------------------------------------------------------------- theme card

class ThemeCard(QAbstractButton):
    """Mini painted preview of a theme. Use inside a QButtonGroup."""

    def __init__(self, key: str, label: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key = key
        self.label = label
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(112, 76)
        self._hover = False

    def enterEvent(self, e) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, e) -> None:
        self._hover = False
        self.update()

    def paintEvent(self, _e) -> None:
        ui = active_theme()
        t = get_theme(self.key) if self.label is None else ui
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(2, 2, self.width() - 4, self.height() - 4)
        path = QPainterPath()
        path.addRoundedRect(r, 10, 10)
        p.fillPath(path, QColor(t.bg))
        p.save()
        p.setClipPath(path)
        paint_decor(p, r, t, anim_time() * 0.6, intensity=0.9, seed=sum(map(ord, t.key)))
        # mini window: surface strip + accent pill
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.surface))
        p.drawRoundedRect(QRectF(r.left() + 8, r.top() + 8, r.width() * 0.5, 22), 6, 6)
        p.setBrush(QColor(t.accent))
        p.drawRoundedRect(QRectF(r.left() + 13, r.top() + 13, 12, 12), 3, 3)
        p.setBrush(QColor(t.subtext))
        p.drawRoundedRect(QRectF(r.left() + 29, r.top() + 15, r.width() * 0.5 - 28, 3), 1.5, 1.5)
        p.setBrush(QColor(t.border))
        p.drawRoundedRect(QRectF(r.left() + 29, r.top() + 21, r.width() * 0.3 - 28, 3), 1.5, 1.5)
        p.restore()

        name = self.label or t.name
        f = QFont(self.font())
        f.setPointSizeF(8.5)
        f.setBold(True)
        p.setFont(f)
        fm = QFontMetrics(f)
        text_rect = QRectF(r.left() + 8, r.bottom() - fm.height() - 6, r.width() - 16, fm.height())
        p.setPen(QColor(t.text))
        p.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   fm.elidedText(name, Qt.TextElideMode.ElideRight, int(text_rect.width())))

        if self.isChecked():
            p.setPen(QPen(QColor(ui.accent), 2.5))
        elif self._hover:
            p.setPen(QPen(QColor(ui.subtext), 1.5))
        else:
            p.setPen(QPen(QColor(ui.border), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 10, 10)
        if self.isChecked():
            c = QPointF(r.right() - 11, r.top() + 11)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(ui.accent))
            p.drawEllipse(c, 8, 8)
            p.setPen(QPen(QColor(ui.accent_text), 2, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            check = QPainterPath(QPointF(c.x() - 3.5, c.y()))
            check.lineTo(c.x() - 1, c.y() + 2.5)
            check.lineTo(c.x() + 3.5, c.y() - 2.5)
            p.drawPath(check)
        p.end()


# --------------------------------------------------------------------------- hotkey recorder

_MOD_NAMES = [(Qt.KeyboardModifier.ControlModifier, "<ctrl>", "Ctrl"),
              (Qt.KeyboardModifier.AltModifier, "<alt>", "Alt"),
              (Qt.KeyboardModifier.ShiftModifier, "<shift>", "Shift"),
              (Qt.KeyboardModifier.MetaModifier, "<cmd>", "Win/Cmd")]
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
        if self._recording:
            self.setText("Press keys…")
            self.setObjectName("primary")
        else:
            self.setText(pretty_hotkey(self._combo))
            self.setObjectName("")
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
        parts = [pyn for mod, pyn, _ in _MOD_NAMES if e.modifiers() & mod]
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


# --------------------------------------------------------------------------- live preview + banner

class LivePreview(QWidget):
    """Renders the real overlay for the colour currently under the cursor."""

    def __init__(self, settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.renderer = OverlayRenderer(settings)
        self.info = color_info((245, 197, 66))
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
        self.renderer.paint(p, anim_time() if self.settings.decorations else 0.0)
        p.end()


class Banner(QWidget):
    """Animated themed header: app title on the left, live overlay preview on the right."""

    def __init__(self, settings, title: str, subtitle: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setMinimumHeight(118)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self._title, self._subtitle = title, subtitle
        lay = QHBoxLayout(self)
        lay.setContentsMargins(22, 14, 18, 14)
        lay.addStretch(1)  # title text is painted directly (cheaper than styled labels)
        self.preview = LivePreview(settings)
        lay.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignVCenter)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._frame)
        self._timer.start(66)  # ~15 fps is plenty for slow ambient motion

    def set_page(self, title: str, subtitle: str) -> None:
        self._title, self._subtitle = title, subtitle
        self.update()

    def _frame(self) -> None:
        # Only animate while the window is focused: keeps background CPU near zero.
        if self.isVisible() and self.settings.decorations and self.window().isActiveWindow():
            self.update()
            self.preview.update()

    def paintEvent(self, _e) -> None:
        t = active_theme()
        p = QPainter(self)
        r = QRectF(self.rect())
        paint_theme_background(p, r, t)
        if self.settings.decorations:
            paint_decor(p, r, t, anim_time(), intensity=1.0, seed=11)
        p.setPen(QPen(QColor(t.border), 1))
        p.drawLine(r.bottomLeft(), r.bottomRight())

        text_w = self.preview.x() - 22 - 16
        tf = QFont(self.font())
        tf.setPointSizeF(15)
        tf.setBold(True)
        sf = QFont(self.font())
        sf.setPointSizeF(self.font().pointSizeF() * 0.95)
        tfm, sfm = QFontMetrics(tf), QFontMetrics(sf)
        sub_rect = sfm.boundingRect(0, 0, text_w, 200, Qt.TextFlag.TextWordWrap, self._subtitle)
        total = tfm.height() + 4 + sub_rect.height()
        y = (self.height() - total) / 2
        p.setFont(tf)
        p.setPen(QColor(t.text))
        p.drawText(QRectF(22, y, text_w, tfm.height()), Qt.AlignmentFlag.AlignLeft, self._title)
        p.setFont(sf)
        p.setPen(QColor(t.subtext))
        p.drawText(QRectF(22, y + tfm.height() + 4, text_w, sub_rect.height()),
                   Qt.TextFlag.TextWordWrap, self._subtitle)
        p.end()


class CvdStrip(QWidget):
    """A row of colour chips as they appear for one vision type (or normal vision)."""
    PALETTE = [(230, 57, 70), (244, 140, 6), (255, 209, 102), (88, 204, 2), (6, 214, 160),
               (17, 138, 178), (58, 80, 230), (155, 93, 229), (241, 91, 181), (140, 90, 50)]

    def __init__(self, kind: str | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.extra: tuple[int, int, int] | None = None
        self.setFixedHeight(18)
        self.setMinimumWidth(180)

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


__all__ = ["ToggleSwitch", "ThemeCard", "HotkeyRecorder", "LivePreview", "Banner", "CvdStrip",
           "card", "row", "section", "active_theme", "set_active_theme", "CVD_LABELS"]
