"""Van Gogh paintings bundled with the app (public domain; scans via Wikimedia
Commons) and the image helpers that crop, blur and colour-vision-simulate them."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

from .colors import _CVD_MATRICES, linear_to_srgb, srgb_to_linear


@dataclass(frozen=True)
class Painting:
    key: str
    title: str
    year: int
    collection: str
    source: str               # Wikimedia Commons file page
    focus: tuple[float, float]  # where to centre crops (0..1)

    @property
    def caption(self) -> str:
        return f"{self.title} · Vincent van Gogh, {self.year}"


_C = "https://commons.wikimedia.org/wiki/File:"
PAINTINGS: dict[str, Painting] = {p.key: p for p in (
    Painting("starry", "The Starry Night", 1889, "Museum of Modern Art, New York",
             _C + "Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg", (0.42, 0.30)),
    Painting("sunflowers", "Sunflowers", 1888, "National Gallery, London",
             _C + "Vincent_Willem_van_Gogh_127.jpg", (0.5, 0.38)),
    Painting("almond", "Almond Blossom", 1890, "Van Gogh Museum, Amsterdam",
             _C + "Vincent_van_Gogh_-_Almond_blossom_-_Google_Art_Project.jpg", (0.5, 0.42)),
    Painting("irises", "Irises", 1889, "J. Paul Getty Museum, Los Angeles",
             _C + "Irises-Vincent_van_Gogh.jpg", (0.5, 0.45)),
    Painting("cafe", "Café Terrace at Night", 1888, "Kröller-Müller Museum, Otterlo",
             _C + "Vincent_Willem_van_Gogh_-_Cafe_Terrace_at_Night_(Yorck).jpg", (0.5, 0.3)),
    Painting("wheatfield", "Wheat Field with Cypresses", 1889,
             "Metropolitan Museum of Art, New York",
             _C + "Vincent_van_Gogh_-_Wheat_Field_with_Cypresses_-_Google_Art_Project.jpg",
             (0.5, 0.35)),
    Painting("bedroom", "The Bedroom", 1888, "Van Gogh Museum, Amsterdam",
             _C + "Vincent_van_Gogh_-_De_slaapkamer_-_Google_Art_Project.jpg", (0.5, 0.5)),
    Painting("portrait", "Self-Portrait", 1887, "Art Institute of Chicago",
             _C + "Vincent_van_Gogh_-_Self-Portrait_-_Google_Art_Project_(454045).jpg",
             (0.5, 0.36)),
)}
GALLERY = [k for k in PAINTINGS if k != "portrait"]

QUOTES = [
    ("The sight of the stars always makes me dream.", "letter to Theo, 1888"),
    ("Colour expresses something in itself.", "letter to Theo, 1885"),
    ("Great things are done by a series of small things brought together.",
     "letter to Theo, 1882"),
    ("What would life be if we had no courage to attempt anything?", "letter to Theo, 1881"),
]


def asset_path(*parts: str) -> str:
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))
    return os.path.join(base, "assets", *parts)


@lru_cache(maxsize=16)
def painting_image(key: str) -> QImage:
    img = QImage(asset_path("paintings", f"{key}.jpg"))
    if img.isNull():  # missing asset: a flat swatch keeps the UI working
        img = QImage(64, 64, QImage.Format.Format_RGB32)
        img.fill(QColor("#555555"))
    return img


def _cover_rect(src: QSize, target_w: float, target_h: float,
                focus: tuple[float, float], zoom: float = 1.0) -> QRectF:
    """Source rect that covers target aspect ratio, centred on `focus`."""
    sw, sh = src.width(), src.height()
    ta = target_w / max(1.0, target_h)
    if sw / sh > ta:
        h = sh / zoom
        w = h * ta
    else:
        w = sw / zoom
        h = w / ta
    x = min(max(0.0, sw * focus[0] - w / 2), sw - w)
    y = min(max(0.0, sh * focus[1] - h / 2), sh - h)
    return QRectF(x, y, w, h)


@lru_cache(maxsize=64)
def cover_image(key: str, w: int, h: int, zoom: float = 1.0) -> QImage:
    """Painting cropped to w×h around its focus point (cached)."""
    src = painting_image(key)
    p = PAINTINGS.get(key)
    rect = _cover_rect(src.size(), w, h, p.focus if p else (0.5, 0.5), zoom)
    return src.copy(rect.toRect()).scaled(
        max(1, w), max(1, h), Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation)


@lru_cache(maxsize=16)
def blurred_image(key: str, w: int, h: int) -> QImage:
    """Soft, out-of-focus version of the painting, for backgrounds."""
    small = cover_image(key, max(8, w // 18), max(8, h // 18))
    small = small.scaled(max(8, w // 6), max(8, h // 6), Qt.AspectRatioMode.IgnoreAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    return small.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)


def draw_cover(p: QPainter, target: QRectF, key: str, zoom: float = 1.0,
               pan: tuple[float, float] = (0.0, 0.0)) -> None:
    """Draws the painting covering `target`; `pan` shifts the crop (-1..1) for Ken Burns."""
    src = painting_image(key)
    painting = PAINTINGS.get(key)
    fx, fy = painting.focus if painting else (0.5, 0.5)
    rect = _cover_rect(src.size(), target.width(), target.height(),
                       (fx + pan[0] * 0.08, fy + pan[1] * 0.08), zoom)
    p.drawImage(target, src, rect)


# --------------------------------------------------------------------------- CVD on images

_TO_LIN = [srgb_to_linear(i / 255.0) for i in range(256)]
_LUT_N = 2048
_FROM_LIN = [int(round(linear_to_srgb(i / (_LUT_N - 1)) * 255)) for i in range(_LUT_N)]


@lru_cache(maxsize=48)
def simulated_image(key: str, kind: str | None, w: int, h: int) -> QImage:
    """The painting as seen with a colour-vision type (None = typical vision)."""
    img = cover_image(key, w, h).convertToFormat(QImage.Format.Format_RGB888)
    if kind is None:
        return img
    bpl = img.bytesPerLine()
    data = bytes(img.constBits())
    out = bytearray(data)
    lin, back, top = _TO_LIN, _FROM_LIN, _LUT_N - 1
    if kind == "achroma":
        m = ((0.2126, 0.7152, 0.0722),) * 3
    else:
        m = _CVD_MATRICES[kind]
    (a0, a1, a2), (b0, b1, b2), (c0, c1, c2) = m
    for y in range(img.height()):
        row = y * bpl
        for i in range(row, row + 3 * img.width(), 3):
            r, g, b = lin[data[i]], lin[data[i + 1]], lin[data[i + 2]]
            out[i] = back[min(top, max(0, int((a0 * r + a1 * g + a2 * b) * top)))]
            out[i + 1] = back[min(top, max(0, int((b0 * r + b1 * g + b2 * b) * top)))]
            out[i + 2] = back[min(top, max(0, int((c0 * r + c1 * g + c2 * b) * top)))]
    return QImage(bytes(out), img.width(), img.height(), bpl,
                  QImage.Format.Format_RGB888).copy()


def to_pixmap(img: QImage, dpr: float) -> QPixmap:
    pm = QPixmap.fromImage(img)
    pm.setDevicePixelRatio(dpr)
    return pm
