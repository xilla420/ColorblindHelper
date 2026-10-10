"""Resizes downloaded Van Gogh scans into assets/paintings/<key>.jpg and prints a
dominant-colour palette for each (used to design the matching themes).

Usage: python -P tools/prepare_paintings.py <folder with <key>.jpg scans>
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "paintings")
MAX_SIDE = 1400


def main(src: str) -> None:
    os.makedirs(OUT, exist_ok=True)
    for name in sorted(os.listdir(src)):
        if not name.lower().endswith(".jpg"):
            continue
        key = os.path.splitext(name)[0]
        with Image.open(os.path.join(src, name)) as im:
            im = im.convert("RGB")
            im.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
            dst = os.path.join(OUT, f"{key}.jpg")
            im.save(dst, "JPEG", quality=86, optimize=True, progressive=True)
            q = im.resize((160, 160)).quantize(colors=8, method=Image.Quantize.MEDIANCUT)
            pal = q.getpalette()[:24]
            counts = sorted(q.getcolors(), reverse=True)
            swatches = ["#{:02x}{:02x}{:02x}".format(*pal[i * 3:i * 3 + 3]) for _, i in counts]
            print(f"{key:11} {im.size[0]}x{im.size[1]} {os.path.getsize(dst) // 1024:4} KB  "
                  + " ".join(swatches))


if __name__ == "__main__":
    main(sys.argv[1])
