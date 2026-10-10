"""Cross-platform "what color is under the cursor" reader.

Windows: GDI GetPixel on the screen DC (fast, no extra dependencies, DPI-correct
because Qt makes the process per-monitor DPI aware).
macOS / Linux: QScreen.grabWindow on the screen under the cursor. On macOS this
needs the Screen Recording permission for the terminal/app that runs it.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QPoint
from PySide6.QtGui import QCursor, QGuiApplication

RGB = tuple[int, int, int]


class _WinGdi:
    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self.ctypes = ctypes
        self.wintypes = wintypes
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        self.user32.GetDC.restype = wintypes.HDC
        self.user32.GetDC.argtypes = [wintypes.HWND]
        self.user32.ReleaseDC.restype = ctypes.c_int
        self.user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        self.user32.GetCursorPos.restype = wintypes.BOOL
        self.user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        self.gdi32.GetPixel.restype = wintypes.COLORREF
        self.gdi32.GetPixel.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
        self.gdi32.CreateCompatibleDC.restype = wintypes.HDC
        self.gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        self.gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
        self.gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
        self.gdi32.SelectObject.restype = wintypes.HGDIOBJ
        self.gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        self.gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        self.gdi32.DeleteDC.argtypes = [wintypes.HDC]
        self.gdi32.BitBlt.restype = wintypes.BOOL
        self.gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_int, wintypes.HDC, ctypes.c_int, ctypes.c_int,
                                      wintypes.DWORD]

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                        ("biClrImportant", wintypes.DWORD)]

        self.BITMAPINFOHEADER = BITMAPINFOHEADER
        self.gdi32.GetDIBits.restype = ctypes.c_int
        self.gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT,
                                         wintypes.UINT, ctypes.c_void_p,
                                         ctypes.POINTER(BITMAPINFOHEADER), wintypes.UINT]

    def read(self, sample: int) -> RGB | None:
        pt = self.wintypes.POINT()
        if not self.user32.GetCursorPos(self.ctypes.byref(pt)):
            return None
        hdc = self.user32.GetDC(None)
        if not hdc:
            return None
        try:
            if sample <= 1:
                c = self.gdi32.GetPixel(hdc, pt.x, pt.y)
                if c == 0xFFFFFFFF:  # CLR_INVALID
                    return None
                return c & 0xFF, (c >> 8) & 0xFF, (c >> 16) & 0xFF
            return self._read_block(hdc, pt.x - sample // 2, pt.y - sample // 2, sample)
        finally:
            self.user32.ReleaseDC(None, hdc)

    def _read_block(self, hdc, x: int, y: int, n: int) -> RGB | None:
        """Average an n×n block with one BitBlt (GetPixel per pixel is ~4 ms each)."""
        ctypes, gdi = self.ctypes, self.gdi32
        mem = gdi.CreateCompatibleDC(hdc)
        if not mem:
            return None
        bmp = gdi.CreateCompatibleBitmap(hdc, n, n)
        if not bmp:
            gdi.DeleteDC(mem)
            return None
        old = gdi.SelectObject(mem, bmp)
        try:
            if not gdi.BitBlt(mem, 0, 0, n, n, hdc, x, y, 0x00CC0020):  # SRCCOPY
                return None
            bmi = self.BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(bmi)
            bmi.biWidth, bmi.biHeight = n, -n  # top-down
            bmi.biPlanes, bmi.biBitCount, bmi.biCompression = 1, 32, 0
            buf = (ctypes.c_ubyte * (n * n * 4))()
            if gdi.GetDIBits(mem, bmp, 0, n, buf, ctypes.byref(bmi), 0) != n:
                return None
            px = n * n
            bs = sum(buf[0::4])
            gs = sum(buf[1::4])
            rs = sum(buf[2::4])
            return round(rs / px), round(gs / px), round(bs / px)
        finally:
            gdi.SelectObject(mem, old)
            gdi.DeleteObject(bmp)
            gdi.DeleteDC(mem)


class PixelReader:
    def __init__(self) -> None:
        self._win: _WinGdi | None = None
        if sys.platform == "win32":
            try:
                self._win = _WinGdi()
            except Exception:
                self._win = None

    @property
    def backend(self) -> str:
        return "gdi" if self._win else "qt"

    def read_at_cursor(self, sample: int = 1) -> RGB | None:
        sample = max(1, sample | 1)  # force odd so the cursor pixel is centred
        if self._win is not None:
            rgb = self._win.read(sample)
            if rgb is not None:
                return rgb
        return self._read_qt(QCursor.pos(), sample)

    @staticmethod
    def _read_qt(pos: QPoint, sample: int) -> RGB | None:
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        if screen is None:
            return None
        geo = screen.geometry()
        half = sample // 2
        x = pos.x() - geo.x() - half
        y = pos.y() - geo.y() - half
        pm = screen.grabWindow(0, x, y, sample, sample)
        if pm.isNull():
            return None
        img = pm.toImage()
        if img.isNull() or img.width() == 0 or img.height() == 0:
            return None
        rs = gs = bs = n = 0
        for yy in range(img.height()):
            for xx in range(img.width()):
                c = img.pixelColor(xx, yy)
                rs += c.red()
                gs += c.green()
                bs += c.blue()
                n += 1
        return round(rs / n), round(gs / n), round(bs / n)
