"""The app icon, drawn in code so tray, window and installer icons always match."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QConicalGradient, QIcon, QLinearGradient, QPainter,
                           QPainterPath, QPixmap, QRadialGradient)


def paint_icon(p: QPainter, size: float) -> None:
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    s = size
    m = s * 0.04
    tile = QRectF(m, m, s - 2 * m, s - 2 * m)

    # Night-sky squircle.
    bg = QLinearGradient(tile.topLeft(), tile.bottomRight())
    bg.setColorAt(0, QColor("#24477f"))
    bg.setColorAt(1, QColor("#0c1834"))
    path = QPainterPath()
    path.addRoundedRect(tile, s * 0.24, s * 0.24)
    p.fillPath(path, bg)

    # Colour-wheel ring (a soft iris).
    c = tile.center()
    outer = s * 0.33
    ring = QPainterPath()
    ring.addEllipse(c, outer, outer)
    hole = QPainterPath()
    hole.addEllipse(c, outer * 0.56, outer * 0.56)
    wheel = QConicalGradient(c, 90)
    for i, col in enumerate(("#ff5a5f", "#ffb340", "#ffe14d", "#58d68d", "#4fc3f7",
                             "#7e7bff", "#e76fd8", "#ff5a5f")):
        wheel.setColorAt(i / 7, QColor(col))
    p.fillPath(ring.subtracted(hole), wheel)

    # Pupil with a highlight -> reads as an eye.
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#0c1834"))
    p.drawEllipse(c, outer * 0.42, outer * 0.42)
    p.setBrush(QColor(255, 255, 255, 235))
    p.drawEllipse(QPointF(c.x() - outer * 0.14, c.y() - outer * 0.16), outer * 0.13, outer * 0.13)

    # Golden star, top right.
    star_c = QPointF(tile.right() - s * 0.17, tile.top() + s * 0.17)
    glow = QRadialGradient(star_c, s * 0.12)
    glow.setColorAt(0, QColor(245, 197, 66, 170))
    glow.setColorAt(1, QColor(245, 197, 66, 0))
    p.setBrush(glow)
    p.drawEllipse(star_c, s * 0.12, s * 0.12)
    star = QPainterPath()
    r1, r2 = s * 0.075, s * 0.025
    for i in range(8):
        a = -math.pi / 2 + i * math.pi / 4
        r = r1 if i % 2 == 0 else r2
        pt = QPointF(star_c.x() + math.cos(a) * r, star_c.y() + math.sin(a) * r)
        star.moveTo(pt) if i == 0 else star.lineTo(pt)
    star.closeSubpath()
    p.fillPath(star, QColor("#f5c542"))


def icon_pixmap(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    paint_icon(p, size)
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(icon_pixmap(size))
    return icon
