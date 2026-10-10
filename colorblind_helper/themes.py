"""Themes for the settings UI and the overlay, plus the animated decorations
("Starry Night" swirls, sunflowers, sakura petals, soft bokeh)."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QLinearGradient, QPainter, QPainterPath, QPalette, QPen,
                           QRadialGradient)


@dataclass(frozen=True)
class Theme:
    key: str
    name: str
    tagline: str
    dark: bool
    bg: str
    surface: str
    surface_alt: str
    border: str
    text: str
    subtext: str
    accent: str
    accent_text: str
    accent2: str
    decor: str  # "bokeh" | "starry" | "sunflowers" | "petals"

    def c(self, attr: str, alpha: int | None = None) -> QColor:
        col = QColor(getattr(self, attr))
        if alpha is not None:
            col.setAlpha(alpha)
        return col


THEMES: dict[str, Theme] = {t.key: t for t in (
    Theme("starry", "Starry Night", "Van Gogh, 1889", True,
          bg="#0c1834", surface="#13264f", surface_alt="#1b3466", border="#2b4a85",
          text="#f7eed0", subtext="#aebedf", accent="#f5c542", accent_text="#1a1b2e",
          accent2="#7fb3e6", decor="starry"),
    Theme("sunflowers", "Sunflowers", "Van Gogh, 1888", False,
          bg="#f5e2a0", surface="#fbf1cb", surface_alt="#f2dc95", border="#dcbd62",
          text="#3a2a0e", subtext="#73592b", accent="#c46f1b", accent_text="#ffffff",
          accent2="#4d7a38", decor="sunflowers"),
    Theme("sakura", "Sakura", "soft & cute", False,
          bg="#fff3f6", surface="#ffffff", surface_alt="#ffe6ee", border="#f6cbd9",
          text="#47283a", subtext="#94667c", accent="#e8648f", accent_text="#ffffff",
          accent2="#a98cf0", decor="petals"),
    Theme("matcha", "Matcha", "calm & fresh", False,
          bg="#eff5ea", surface="#fbfdf8", surface_alt="#e3eed9", border="#cfdfc1",
          text="#26351f", subtext="#62735a", accent="#4f9a3a", accent_text="#ffffff",
          accent2="#d99a3e", decor="bokeh"),
    Theme("midnight", "Midnight", "easy on the eyes", True,
          bg="#14151b", surface="#1d1f28", surface_alt="#262935", border="#343849",
          text="#eceef6", subtext="#9ba1b6", accent="#9282f8", accent_text="#ffffff",
          accent2="#5ec8e5", decor="bokeh"),
    Theme("daylight", "Daylight", "crisp & clean", False,
          bg="#f3f4f8", surface="#ffffff", surface_alt="#eceef4", border="#dcdfe8",
          text="#1d2130", subtext="#636a7e", accent="#4b67e8", accent_text="#ffffff",
          accent2="#14b0a0", decor="bokeh"),
)}

DEFAULT_UI_THEME = "starry"
MATCH = "match"


def get_theme(key: str) -> Theme:
    return THEMES.get(key) or THEMES[DEFAULT_UI_THEME]


def overlay_theme(settings) -> Theme:
    key = settings.ui_theme if settings.overlay_theme == MATCH else settings.overlay_theme
    return get_theme(key)


# --------------------------------------------------------------------------- Qt styling

def palette_for(t: Theme) -> QPalette:
    p = QPalette()
    role = QPalette.ColorRole
    p.setColor(role.Window, QColor(t.bg))
    p.setColor(role.WindowText, QColor(t.text))
    p.setColor(role.Base, QColor(t.surface))
    p.setColor(role.AlternateBase, QColor(t.surface_alt))
    p.setColor(role.Text, QColor(t.text))
    p.setColor(role.Button, QColor(t.surface_alt))
    p.setColor(role.ButtonText, QColor(t.text))
    p.setColor(role.Highlight, QColor(t.accent))
    p.setColor(role.HighlightedText, QColor(t.accent_text))
    p.setColor(role.ToolTipBase, QColor(t.surface))
    p.setColor(role.ToolTipText, QColor(t.text))
    p.setColor(role.PlaceholderText, QColor(t.subtext))
    p.setColor(role.Link, QColor(t.accent))
    p.setColor(QPalette.ColorGroup.Disabled, role.Text, QColor(t.subtext))
    p.setColor(QPalette.ColorGroup.Disabled, role.WindowText, QColor(t.subtext))
    p.setColor(QPalette.ColorGroup.Disabled, role.ButtonText, QColor(t.subtext))
    return p


def menu_stylesheet(t: Theme) -> str:
    return f"""
    QMenu {{
        background: {t.surface}; color: {t.text}; border: 1px solid {t.border};
        border-radius: 10px; padding: 6px;
    }}
    QMenu::item {{ padding: 6px 22px 6px 26px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {t.surface_alt}; }}
    QMenu::item:disabled {{ color: {t.subtext}; }}
    QMenu::separator {{ height: 1px; background: {t.border}; margin: 5px 8px; }}
    QMenu::indicator {{ width: 14px; height: 14px; left: 6px; }}
    QToolTip {{
        background: {t.surface}; color: {t.text}; border: 1px solid {t.border};
        border-radius: 6px; padding: 4px 8px;
    }}
    """


def window_stylesheet(t: Theme) -> str:
    return f"""
    #SettingsRoot {{ background: {t.bg}; }}
    #SettingsRoot QLabel {{ color: {t.text}; background: transparent; }}
    #SettingsRoot QLabel#desc, #SettingsRoot QLabel#muted {{ color: {t.subtext}; }}
    #SettingsRoot QLabel#section {{
        color: {t.subtext}; font-weight: 600; letter-spacing: 1px; font-size: 8pt;
        padding: 4px 2px 0 2px;
    }}
    #SettingsRoot QLabel#pageTitle {{ font-size: 15pt; font-weight: 700; }}
    #SettingsRoot QLabel#appName {{ font-size: 11pt; font-weight: 700; }}
    #Sidebar {{ background: {t.surface}; border-right: 1px solid {t.border}; }}
    #Card {{
        background: {t.surface}; border: 1px solid {t.border}; border-radius: 12px;
    }}
    #Card QLabel {{ background: transparent; }}
    #RowDivider {{ background: {t.border}; max-height: 1px; min-height: 1px; border: none; }}
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {t.border}; border-radius: 3px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {t.subtext}; }}
    QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
        height: 0; background: none;
    }}
    QPushButton {{
        background: {t.surface_alt}; color: {t.text}; border: 1px solid {t.border};
        border-radius: 8px; padding: 5px 12px;
    }}
    QPushButton:hover {{ border-color: {t.accent}; }}
    QPushButton:pressed {{ background: {t.border}; }}
    QPushButton#primary {{
        background: {t.accent}; color: {t.accent_text}; border: none; font-weight: 600;
    }}
    QPushButton#nav {{
        background: transparent; border: none; border-radius: 9px; text-align: left;
        padding: 8px 12px; color: {t.subtext}; font-weight: 500;
    }}
    QPushButton#nav:hover {{ background: {t.surface_alt}; color: {t.text}; }}
    QPushButton#nav:checked {{ background: {t.accent}; color: {t.accent_text}; font-weight: 600; }}
    QPushButton#seg {{ border-radius: 0; padding: 5px 12px; }}
    QPushButton#seg:checked {{
        background: {t.accent}; color: {t.accent_text}; border-color: {t.accent};
        font-weight: 600;
    }}
    QPushButton#segFirst {{ border-top-right-radius: 0; border-bottom-right-radius: 0; }}
    QPushButton#link {{
        background: transparent; border: none; color: {t.accent}; padding: 2px; font-weight: 600;
    }}
    QComboBox, QFontComboBox, QSpinBox, QLineEdit {{
        background: {t.surface_alt}; color: {t.text}; border: 1px solid {t.border};
        border-radius: 8px; padding: 4px 8px; min-height: 20px;
        selection-background-color: {t.accent}; selection-color: {t.accent_text};
    }}
    QComboBox:hover, QSpinBox:hover {{ border-color: {t.accent}; }}
    QComboBox::drop-down {{ border: none; width: 18px; }}
    QComboBox QAbstractItemView {{
        background: {t.surface}; color: {t.text}; border: 1px solid {t.border};
        selection-background-color: {t.surface_alt}; selection-color: {t.text}; outline: none;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 14px; border: none; }}
    QSlider::groove:horizontal {{ height: 6px; background: {t.surface_alt}; border-radius: 3px; }}
    QSlider::sub-page:horizontal {{ background: {t.accent}; border-radius: 3px; }}
    QSlider::handle:horizontal {{
        background: {t.surface}; border: 2px solid {t.accent}; width: 12px; height: 12px;
        margin: -5px 0; border-radius: 8px;
    }}
    """ + menu_stylesheet(t)


# --------------------------------------------------------------------------- decorations

@lru_cache(maxsize=64)
def _seeded_points(seed: int, n: int) -> tuple[tuple[float, float, float, float], ...]:
    """n pseudo-random (x, y, size, phase) tuples in unit space, stable per seed."""
    rnd = random.Random(seed)
    return tuple((rnd.random(), rnd.random(), rnd.random(), rnd.random() * math.tau)
                 for _ in range(n))


def paint_decor(p: QPainter, rect: QRectF, t: Theme, time: float, intensity: float = 1.0,
                seed: int = 7) -> None:
    """Paints the theme's decoration inside `rect` (caller clips). `time` in seconds."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    {"starry": _paint_starry, "sunflowers": _paint_sunflowers,
     "petals": _paint_petals}.get(t.decor, _paint_bokeh)(p, rect, t, time, intensity, seed)
    p.restore()


@lru_cache(maxsize=8)
def _spiral(band: int) -> QPainterPath:
    """Unit Archimedean spiral (radius ~1), built once and transformed when drawn."""
    path = QPainterPath()
    steps = 48
    for s in range(steps + 1):
        a = s / steps * math.tau * 1.4
        rr = (0.25 + 0.75 * s / steps) - band * 0.12
        pt = QPointF(math.cos(a) * rr, math.sin(a) * rr)
        path.moveTo(pt) if s == 0 else path.lineTo(pt)
    return path


def _paint_starry(p: QPainter, r: QRectF, t: Theme, time: float, k: float, seed: int) -> None:
    w, h = r.width(), r.height()
    # Brush-stroke swirls (Archimedean spirals) drifting slowly.
    swirl_col = t.c("accent2")
    p.setBrush(Qt.BrushStyle.NoBrush)
    for i, (ux, uy, us, ph) in enumerate(_seeded_points(seed, 3)):
        cx = r.left() + w * (0.15 + 0.7 * ux)
        cy = r.top() + h * (0.2 + 0.6 * uy)
        radius = min(w, h) * (0.35 + 0.35 * us)
        rot = ph + time * (0.12 if i % 2 else -0.1)
        for band in range(3):
            swirl_col.setAlpha(int((46 - band * 12) * k))
            pen = QPen(swirl_col, max(1.5, min(w, h) * 0.02), Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.save()
            p.translate(cx, cy)
            p.scale(radius, radius * 0.75)
            p.rotate(math.degrees(rot))
            p.drawPath(_spiral(band))
            p.restore()
    # Twinkling stars with a glow halo.
    p.setPen(Qt.PenStyle.NoPen)
    for ux, uy, us, ph in _seeded_points(seed + 1, 9):
        x, y = r.left() + w * ux, r.top() + h * uy
        size = 1.6 + us * 3.2
        tw = 0.55 + 0.45 * math.sin(time * (1.4 + us) + ph)
        glow = QRadialGradient(QPointF(x, y), size * 3.5)
        gc = t.c("accent", int(120 * tw * k))
        glow.setColorAt(0.0, gc)
        gc.setAlpha(0)
        glow.setColorAt(1.0, gc)
        p.setBrush(glow)
        p.drawEllipse(QPointF(x, y), size * 3.5, size * 3.5)
        p.setBrush(t.c("accent", int(230 * tw * k)))
        p.drawEllipse(QPointF(x, y), size * 0.6, size * 0.6)
    # Crescent moon.
    mx, my, mr = r.right() - min(w, h) * 0.16, r.top() + min(w, h) * 0.2, min(w, h) * 0.075
    if mr > 3:
        moon = QPainterPath()
        moon.addEllipse(QPointF(mx, my), mr, mr)
        cut = QPainterPath()
        cut.addEllipse(QPointF(mx + mr * 0.45, my - mr * 0.25), mr * 0.85, mr * 0.85)
        p.setBrush(t.c("accent", int(200 * k)))
        p.drawPath(moon.subtracted(cut))


def _sunflower(p: QPainter, c: QPointF, radius: float, rot: float, t: Theme, alpha: int) -> None:
    p.save()
    p.translate(c)
    p.rotate(math.degrees(rot))
    petal = t.c("accent", alpha)
    petal_hi = QColor("#f4b81d")
    petal_hi.setAlpha(alpha)
    p.setPen(Qt.PenStyle.NoPen)
    for i in range(14):
        p.save()
        p.rotate(i * 360 / 14)
        p.setBrush(petal_hi if i % 2 else petal)
        p.drawEllipse(QRectF(radius * 0.35, -radius * 0.16, radius * 0.7, radius * 0.32))
        p.restore()
    center = QColor("#6b3e12")
    center.setAlpha(alpha)
    p.setBrush(center)
    p.drawEllipse(QPointF(0, 0), radius * 0.4, radius * 0.4)
    p.restore()


def _paint_sunflowers(p: QPainter, r: QRectF, t: Theme, time: float, k: float, seed: int) -> None:
    w, h = r.width(), r.height()
    for ux, uy, us, ph in _seeded_points(seed + 2, 4):
        c = QPointF(r.left() + w * ux, r.top() + h * (0.1 + 0.85 * uy))
        radius = min(w, h) * (0.12 + 0.14 * us)
        _sunflower(p, c, radius, ph + time * 0.15 * (1 if us > 0.5 else -1), t, int(70 * k))


def _paint_petals(p: QPainter, r: QRectF, t: Theme, time: float, k: float, seed: int) -> None:
    w, h = r.width(), r.height()
    p.setPen(Qt.PenStyle.NoPen)
    for i, (ux, uy, us, ph) in enumerate(_seeded_points(seed + 3, 12)):
        speed = 0.04 + 0.05 * us
        y = r.top() + ((uy + time * speed) % 1.15 - 0.075) * h
        x = r.left() + (ux * w + math.sin(time * 0.8 + ph) * w * 0.03)
        size = min(w, h) * (0.035 + 0.04 * us)
        p.save()
        p.translate(x, y)
        p.rotate(math.degrees(ph + time * (0.6 + us)))
        col = t.c("accent" if i % 3 else "accent2", int((70 + 60 * us) * k))
        p.setBrush(col)
        path = QPainterPath()
        path.moveTo(0, -size)
        path.cubicTo(size * 0.9, -size * 0.6, size * 0.6, size * 0.7, 0, size)
        path.cubicTo(-size * 0.6, size * 0.7, -size * 0.9, -size * 0.6, 0, -size)
        p.drawPath(path)
        p.restore()


def _paint_bokeh(p: QPainter, r: QRectF, t: Theme, time: float, k: float, seed: int) -> None:
    w, h = r.width(), r.height()
    p.setPen(Qt.PenStyle.NoPen)
    for i, (ux, uy, us, ph) in enumerate(_seeded_points(seed + 4, 7)):
        x = r.left() + w * ux + math.sin(time * 0.3 + ph) * w * 0.04
        y = r.top() + h * uy + math.cos(time * 0.25 + ph) * h * 0.06
        radius = min(w, h) * (0.12 + 0.25 * us)
        g = QRadialGradient(QPointF(x, y), radius)
        col = t.c("accent" if i % 2 else "accent2", int(55 * k))
        g.setColorAt(0, col)
        col.setAlpha(0)
        g.setColorAt(1, col)
        p.setBrush(g)
        p.drawEllipse(QPointF(x, y), radius, radius)


def paint_theme_background(p: QPainter, rect: QRectF, t: Theme) -> None:
    g = QLinearGradient(rect.topLeft(), rect.bottomRight())
    g.setColorAt(0, QColor(t.surface))
    g.setColorAt(1, QColor(t.surface_alt))
    p.fillRect(rect, g)
