"""Themes for the settings UI and the overlay. Seven are drawn from Van Gogh
paintings (palette sampled from the canvas); two are neutral "studio" themes."""
from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPalette, QPen


@dataclass(frozen=True)
class Theme:
    key: str
    name: str
    dark: bool
    painting: str | None  # key in paintings.PAINTINGS, None = plain canvas
    bg: str
    surface: str
    surface_alt: str
    border: str
    text: str
    subtext: str
    accent: str
    accent_text: str
    accent2: str

    def c(self, attr: str, alpha: int | None = None) -> QColor:
        col = QColor(getattr(self, attr))
        if alpha is not None:
            col.setAlpha(alpha)
        return col

    def rgba(self, attr: str, alpha: float) -> str:
        col = QColor(getattr(self, attr))
        return f"rgba({col.red()}, {col.green()}, {col.blue()}, {alpha:.2f})"


THEMES: dict[str, Theme] = {t.key: t for t in (
    Theme("starry", "Starry Night", True, "starry",
          bg="#0b1630", surface="#12224a", surface_alt="#1a3062", border="#2c4880",
          text="#f6edcf", subtext="#b3c1df", accent="#f2c94c", accent_text="#13162b",
          accent2="#7fa7d9"),
    Theme("cafe", "Café Terrace", True, "cafe",
          bg="#11182b", surface="#1a233d", surface_alt="#25304e", border="#3a4669",
          text="#fbefc8", subtext="#bdbccb", accent="#f0a92e", accent_text="#1b1405",
          accent2="#7d9ad6"),
    Theme("irises", "Irises", True, "irises",
          bg="#141f1b", surface="#1c2b25", surface_alt="#263a31", border="#3a5246",
          text="#eef2e8", subtext="#aabdae", accent="#9b8cf0", accent_text="#ffffff",
          accent2="#e3913a"),
    Theme("sunflowers", "Sunflowers", False, "sunflowers",
          bg="#f4e3a3", surface="#fbf2cf", surface_alt="#f1dc8e", border="#d9b956",
          text="#34260b", subtext="#6b5224", accent="#a9561a", accent_text="#ffffff",
          accent2="#4c7a36"),
    Theme("almond", "Blossom", False, "almond",
          bg="#dfecea", surface="#f6fbfa", surface_alt="#d3e6e3", border="#acccc8",
          text="#173230", subtext="#4a6b67", accent="#2f7f7e", accent_text="#ffffff",
          accent2="#c9787f"),
    Theme("wheatfield", "Wheat Field", False, "wheatfield",
          bg="#e4ecf0", surface="#f8fafb", surface_alt="#d9e5eb", border="#b9ccd7",
          text="#1d2a29", subtext="#526664", accent="#8a6312", accent_text="#ffffff",
          accent2="#2f5a3a"),
    Theme("bedroom", "Bedroom", False, "bedroom",
          bg="#e7ebf3", surface="#fbfbfd", surface_alt="#dde3ef", border="#c1cbdf",
          text="#212a3d", subtext="#58627e", accent="#3b5ea6", accent_text="#ffffff",
          accent2="#c9a227"),
    Theme("charcoal", "Charcoal", True, None,
          bg="#171615", surface="#211f1d", surface_alt="#2b2926", border="#3d3a36",
          text="#efece6", subtext="#a8a39a", accent="#d9a441", accent_text="#1a1406",
          accent2="#8fb3c9"),
    Theme("linen", "Linen", False, None,
          bg="#f2eee5", surface="#fcfaf5", surface_alt="#ebe4d6", border="#d8cfbd",
          text="#2b261e", subtext="#6a6253", accent="#9c4f2e", accent_text="#ffffff",
          accent2="#3e6b75"),
)}

DEFAULT_UI_THEME = "starry"
MATCH = "match"
_LEGACY = {"sakura": "almond", "matcha": "wheatfield", "midnight": "charcoal",
           "daylight": "linen"}


def migrate_key(key: str) -> str:
    return _LEGACY.get(key, key)


def get_theme(key: str) -> Theme:
    return THEMES.get(migrate_key(key)) or THEMES[DEFAULT_UI_THEME]


def overlay_theme(settings) -> Theme:
    key = settings.ui_theme if settings.overlay_theme == MATCH else settings.overlay_theme
    return get_theme(key)


# --------------------------------------------------------------------------- typography

_SERIF_CANDIDATES = ("Georgia", "Palatino Linotype", "Palatino", "Book Antiqua",
                     "Times New Roman")


@lru_cache(maxsize=1)
def serif_family() -> str:
    from PySide6.QtGui import QFontDatabase
    families = set(QFontDatabase.families())
    for fam in _SERIF_CANDIDATES:
        if fam in families:
            return fam
    f = QFont()
    f.setStyleHint(QFont.StyleHint.Serif)
    return f.defaultFamily()


def serif(point_size: float, bold: bool = False, italic: bool = False) -> QFont:
    f = QFont(serif_family())
    f.setPointSizeF(point_size)
    f.setBold(bold)
    f.setItalic(italic)
    return f


# --------------------------------------------------------------------------- canvas texture

@lru_cache(maxsize=4)
def canvas_texture(dark: bool, size: int = 160) -> QImage:
    """A tileable linen-canvas weave, drawn once."""
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    rnd = random.Random(42)
    base = 255 if dark else 0
    for i in range(0, size, 2):
        a = rnd.randint(6, 16)
        p.setPen(QPen(QColor(base, base, base, a), 1))
        p.drawLine(0, i, size, i)
        a = rnd.randint(5, 13)
        p.setPen(QPen(QColor(base, base, base, a), 1))
        p.drawLine(i, 0, i, size)
    for _ in range(size * 3):  # slubs in the thread
        x, y = rnd.randrange(size), rnd.randrange(size)
        p.setPen(QPen(QColor(base, base, base, rnd.randint(8, 22)), 1))
        p.drawLine(x, y, x + rnd.randint(1, 4), y)
    p.end()
    return img


def paint_canvas(p: QPainter, rect: QRectF, t: Theme) -> None:
    p.fillRect(rect, QColor(t.bg))
    p.save()
    p.setOpacity(0.9)
    p.drawTiledPixmap(rect.toRect(), _texture_pixmap(t.dark))
    p.restore()


@lru_cache(maxsize=4)
def _texture_pixmap(dark: bool):
    from PySide6.QtGui import QPixmap
    return QPixmap.fromImage(canvas_texture(dark))


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
    p.setColor(role.LinkVisited, QColor(t.accent))
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
    QMenu::item:disabled {{ color: {t.subtext}; font-family: "{serif_family()}"; font-style: italic; }}
    QMenu::separator {{ height: 1px; background: {t.border}; margin: 5px 8px; }}
    QMenu::indicator {{ width: 14px; height: 14px; left: 6px; }}
    QToolTip {{
        background: {t.surface}; color: {t.text}; border: 1px solid {t.border};
        border-radius: 6px; padding: 4px 8px;
    }}
    """


def window_stylesheet(t: Theme) -> str:
    serif_fam = serif_family()
    return f"""
    #SettingsRoot QLabel {{ color: {t.text}; background: transparent; }}
    #SettingsRoot QLabel#desc, #SettingsRoot QLabel#muted {{ color: {t.subtext}; }}
    #SettingsRoot QLabel#section {{
        color: {t.text}; font-family: "{serif_fam}"; font-style: italic; font-size: 11.5pt;
        padding: 6px 2px 0 2px;
    }}
    #SettingsRoot QLabel#appName {{ font-family: "{serif_fam}"; font-size: 13pt; font-weight: 700; }}
    #SettingsRoot QLabel#quote {{
        color: {t.text}; font-family: "{serif_fam}"; font-style: italic; font-size: 9.5pt;
    }}
    #SettingsRoot QLabel#caption {{
        color: {t.subtext}; font-family: "{serif_fam}"; font-style: italic;
    }}
    #Card {{
        background: {t.rgba("surface", 0.90)}; border: 1px solid {t.rgba("border", 0.9)};
        border-radius: 14px;
    }}
    #Card QLabel {{ background: transparent; }}
    #RowDivider {{ background: {t.border}; max-height: 1px; min-height: 1px; border: none; }}
    QScrollArea, QScrollArea > QWidget > QWidget, QStackedWidget {{
        background: transparent; border: none;
    }}
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
        background: transparent; border: none; border-radius: 10px; text-align: left;
        padding: 8px 12px; color: {t.text}; font-weight: 500;
    }}
    QPushButton#nav:hover {{ background: {t.rgba("surface_alt", 0.75)}; }}
    QPushButton#nav:checked {{ background: {t.accent}; color: {t.accent_text}; font-weight: 600; }}
    QPushButton#seg {{ border-radius: 0; padding: 5px 12px; }}
    QPushButton#seg:checked {{
        background: {t.accent}; color: {t.accent_text}; border-color: {t.accent};
        font-weight: 600;
    }}
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
