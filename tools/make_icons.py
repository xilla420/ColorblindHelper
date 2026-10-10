"""Exports the in-code app icon to assets/icon.png and assets/icon.ico (needs Pillow)."""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from colorblind_helper.icon import icon_pixmap  # noqa: E402


def main() -> None:
    _app = QGuiApplication([])
    out = os.path.join(ROOT, "assets")
    os.makedirs(out, exist_ok=True)
    images = []
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        icon_pixmap(size).save(buf, "PNG")
        images.append(Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA"))
    icon_pixmap(1024).save(os.path.join(out, "icon.png"))
    big = images[-1]
    big.save(os.path.join(out, "icon.ico"), sizes=[im.size for im in images],
             append_images=images[:-1])
    print("wrote", out)


if __name__ == "__main__":
    main()
