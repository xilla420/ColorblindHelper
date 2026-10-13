"""Renders docs/social-preview.png (1280x640, GitHub/Open Graph card) and
docs/img/hero.jpg (landing-page hero) from the bundled paintings."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
if sys.platform != "win32":  # the offscreen platform has no fonts on Windows
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from colorblind_helper.colors import color_info  # noqa: E402
from colorblind_helper.icon import icon_pixmap  # noqa: E402
from colorblind_helper.overlay import OverlayRenderer  # noqa: E402
from colorblind_helper.paintings import cover_image  # noqa: E402
from colorblind_helper.settings import Settings  # noqa: E402
from colorblind_helper.themes import serif  # noqa: E402


def social(path: str) -> None:
    W, H = 1280, 640
    img = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    p.drawImage(QRectF(0, 0, W, H), cover_image("starry", W, H, 1.05))
    g = QLinearGradient(0, 0, W, 0)
    for stop, a in ((0, 0.94), (0.5, 0.78), (0.78, 0.25), (1, 0.1)):
        c = QColor("#0b1630")
        c.setAlphaF(a)
        g.setColorAt(stop, c)
    p.fillRect(img.rect(), g)

    p.drawPixmap(72, 92, icon_pixmap(112))
    p.setPen(QColor("#f6edcf"))
    p.setFont(serif(54, bold=True))
    p.drawText(QRectF(72, 222, 760, 90), Qt.AlignmentFlag.AlignLeft, "Colorblind Helper")
    p.setFont(serif(27, italic=True))
    p.setPen(QColor("#f2c94c"))
    p.drawText(QRectF(74, 312, 760, 50), Qt.AlignmentFlag.AlignLeft,
               "Name any colour on your screen.")
    f = p.font()
    f.setFamily("Segoe UI")
    f.setItalic(False)
    f.setPointSizeF(17)
    p.setFont(f)
    p.setPen(QColor("#d4dbee"))
    p.drawText(QRectF(76, 378, 720, 120), Qt.TextFlag.TextWordWrap,
               "Colour picker overlay for colour-blind people & artists.\n"
               "Protanopia · Deuteranopia · Tritanopia simulation\n"
               "Free & open source · Windows & macOS")

    s = Settings()
    s.descriptive_mode = True
    s.scale = 1.25
    s.sim_achroma = False
    r = OverlayRenderer(s)
    size = r.layout(color_info((220, 20, 60)))
    p.save()
    p.translate(W - size.width() - 56, H - size.height() - 64)
    r.paint(p, 0.0)
    p.restore()
    p.end()
    img.save(path)


def overlay_tiles(folder: str) -> None:
    """Each overlay theme sitting on its own painting, for the landing page."""
    samples = [("starry", (242, 201, 76)), ("sunflowers", (169, 86, 26)),
               ("irises", (155, 140, 240)), ("almond", (201, 120, 127))]
    for key, rgb in samples:
        W, H = 560, 360
        img = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.drawImage(QRectF(0, 0, W, H), cover_image(key, W, H, 1.2))
        p.fillRect(img.rect(), QColor(0, 0, 0, 40))
        s = Settings()
        s.descriptive_mode = True
        s.overlay_theme = key
        s.sim_achroma = False
        r = OverlayRenderer(s)
        size = r.layout(color_info(rgb))
        p.translate((W - size.width()) / 2, (H - size.height()) / 2)
        r.paint(p, 0.0)
        p.end()
        img.save(os.path.join(folder, f"overlay-{key}.jpg"), "JPG", 84)


def hero(path: str) -> None:
    img = cover_image("starry", 1800, 760, 1.0)
    img.save(path, "JPG", 82)


if __name__ == "__main__":
    app = QApplication([])
    os.makedirs(os.path.join(ROOT, "docs", "img"), exist_ok=True)
    social(os.path.join(ROOT, "docs", "social-preview.png"))
    hero(os.path.join(ROOT, "docs", "img", "hero.jpg"))
    QImage(os.path.join(ROOT, "docs", "social-preview.png")).save(
        os.path.join(ROOT, "docs", "social-preview.jpg"), "JPG", 88)  # GitHub limit: 1 MB
    for key in ("sunflowers", "almond", "irises", "cafe", "portrait"):
        cover_image(key, 640, 420).save(os.path.join(ROOT, "docs", "img", f"{key}.jpg"), "JPG", 80)
    overlay_tiles(os.path.join(ROOT, "docs", "img"))
    from colorblind_helper.paintings import simulated_image
    for kind in (None, "protan", "deutan", "tritan", "achroma"):
        simulated_image("portrait", kind, 420, 300).save(
            os.path.join(ROOT, "docs", "img", f"portrait-{kind or 'typical'}.jpg"), "JPG", 82)
    print("ok")
