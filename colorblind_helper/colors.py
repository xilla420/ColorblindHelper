"""Color math: conversions, nearest-name lookup, plain-language description,
and color-vision-deficiency (CVD) simulation."""
from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache

from .names import CSS_COLORS

RGB = tuple[int, int, int]


# --------------------------------------------------------------------------- conversions

def rgb_to_hex(rgb: RGB, upper: bool = True) -> str:
    s = "#{:02x}{:02x}{:02x}".format(*rgb)
    return s.upper() if upper else s


def hex_to_rgb(s: str) -> RGB:
    s = s.lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def _hue(r: float, g: float, b: float, mx: float, d: float) -> float:
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return (h * 60.0) % 360.0


def rgb_to_hsl(rgb: RGB) -> tuple[float, float, float]:
    """Returns (hue 0-360, saturation 0-1, lightness 0-1)."""
    r, g, b = (c / 255.0 for c in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2.0
    d = mx - mn
    if d == 0:
        return 0.0, 0.0, l
    s = d / (1.0 - abs(2.0 * l - 1.0))
    return _hue(r, g, b, mx, d), s, l


def rgb_to_hsv(rgb: RGB) -> tuple[float, float, float]:
    """Returns (hue 0-360, saturation 0-1, value 0-1)."""
    r, g, b = (c / 255.0 for c in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    s = 0.0 if mx == 0 else d / mx
    h = 0.0 if d == 0 else _hue(r, g, b, mx, d)
    return h, s, mx


def rgb_to_cmyk(rgb: RGB) -> tuple[float, float, float, float]:
    r, g, b = (c / 255.0 for c in rgb)
    k = 1.0 - max(r, g, b)
    if k >= 1.0:
        return 0.0, 0.0, 0.0, 1.0
    return (1 - r - k) / (1 - k), (1 - g - k) / (1 - k), (1 - b - k) / (1 - k), k


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    c = min(1.0, max(0.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def relative_luminance(rgb: RGB) -> float:
    r, g, b = (srgb_to_linear(c / 255.0) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: RGB, b: RGB) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def rgb_to_lab(rgb: RGB) -> tuple[float, float, float]:
    r, g, b = (srgb_to_linear(c / 255.0) for c in rgb)
    x = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047
    y = (0.2126729 * r + 0.7151522 * g + 0.0721750 * b) / 1.00000
    z = (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16.0 / 116.0

    fx, fy, fz = f(x), f(y), f(z)
    return 116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)


def ciede2000(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
    """CIEDE2000 perceptual color difference."""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1, C2 = math.hypot(a1, b1), math.hypot(a2, b2)
    Cbar = (C1 + C2) / 2.0
    G = 0.5 * (1.0 - math.sqrt(Cbar ** 7 / (Cbar ** 7 + 25.0 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)

    def hp(a: float, b: float) -> float:
        if a == 0 and b == 0:
            return 0.0
        h = math.degrees(math.atan2(b, a))
        return h + 360.0 if h < 0 else h

    h1p, h2p = hp(a1p, b1), hp(a2p, b2)
    dLp = L2 - L1
    dCp = C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    else:
        dhp = h2p - h1p
        if dhp > 180:
            dhp -= 360
        elif dhp < -180:
            dhp += 360
    dHp = 2.0 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp / 2.0))
    Lbp = (L1 + L2) / 2.0
    Cbp = (C1p + C2p) / 2.0
    if C1p * C2p == 0:
        hbp = h1p + h2p
    else:
        s, d = h1p + h2p, abs(h1p - h2p)
        if d <= 180:
            hbp = s / 2.0
        elif s < 360:
            hbp = (s + 360) / 2.0
        else:
            hbp = (s - 360) / 2.0
    rad = math.radians
    T = (1 - 0.17 * math.cos(rad(hbp - 30)) + 0.24 * math.cos(rad(2 * hbp))
         + 0.32 * math.cos(rad(3 * hbp + 6)) - 0.20 * math.cos(rad(4 * hbp - 63)))
    dtheta = 30.0 * math.exp(-(((hbp - 275.0) / 25.0) ** 2))
    RC = 2.0 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25.0 ** 7))
    SL = 1 + 0.015 * (Lbp - 50) ** 2 / math.sqrt(20 + (Lbp - 50) ** 2)
    SC = 1 + 0.045 * Cbp
    SH = 1 + 0.015 * Cbp * T
    RT = -math.sin(rad(2 * dtheta)) * RC
    return math.sqrt((dLp / SL) ** 2 + (dCp / SC) ** 2 + (dHp / SH) ** 2
                     + RT * (dCp / SC) * (dHp / SH))


# --------------------------------------------------------------------------- naming

_NAMED: list[tuple[str, RGB, tuple[float, float, float]]] = [
    (name, hex_to_rgb(hx), rgb_to_lab(hex_to_rgb(hx))) for name, hx in CSS_COLORS
]


def nearest_named_color(rgb: RGB) -> tuple[str, RGB, float]:
    """Closest CSS color by CIEDE2000 distance. Returns (name, its rgb, distance)."""
    lab = rgb_to_lab(rgb)
    best = min(_NAMED, key=lambda e: ciede2000(lab, e[2]))
    return best[0], best[1], ciede2000(lab, best[2])


# --------------------------------------------------------------------------- CVD simulation

# Machado, Oliveira & Fernandes (2009), severity 1.0, applied in linear RGB.
_CVD_MATRICES: dict[str, tuple[tuple[float, float, float], ...]] = {
    "protan": ((0.152286, 1.052583, -0.204868),
               (0.114503, 0.786281, 0.099216),
               (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968),
               (0.280085, 0.672501, 0.047413),
               (-0.011820, 0.042940, 0.968881)),
    "tritan": ((1.255528, -0.076749, -0.178779),
               (-0.078411, 0.930809, 0.147602),
               (0.004733, 0.691367, 0.303900)),
}

CVD_LABELS: dict[str, str] = {
    "protan": "Protan (red-blind)",
    "deutan": "Deutan (green-blind)",
    "tritan": "Tritan (blue-blind)",
    "achroma": "Achromat (no colour)",
}
CVD_KINDS: tuple[str, ...] = tuple(CVD_LABELS)


def simulate_cvd(rgb: RGB, kind: str) -> RGB:
    if kind == "achroma":
        v = int(round(linear_to_srgb(relative_luminance(rgb)) * 255))
        return v, v, v
    m = _CVD_MATRICES[kind]
    lin = [srgb_to_linear(c / 255.0) for c in rgb]
    out = []
    for row in m:
        v = row[0] * lin[0] + row[1] * lin[1] + row[2] * lin[2]
        out.append(int(round(linear_to_srgb(v) * 255)))
    return out[0], out[1], out[2]


# --------------------------------------------------------------------------- description

_HUE_FAMILIES: list[tuple[float, str]] = [
    (12, "red"), (22, "red-orange"), (40, "orange"), (50, "amber"), (64, "yellow"),
    (80, "yellow-green"), (158, "green"), (178, "teal"), (192, "cyan"),
    (207, "sky blue"), (255, "blue"), (275, "violet"), (305, "purple"),
    (335, "magenta"), (350, "pink"), (361, "red"),
]
_WARM = {"red", "red-orange", "orange", "amber", "yellow", "pink"}
_COOL = {"teal", "cyan", "sky blue", "blue", "violet"}


def hue_family(h: float) -> str:
    for upper, name in _HUE_FAMILIES:
        if h < upper:
            return name
    return "red"


def _tier(value: float, tiers: list[tuple[float, str]]) -> str:
    for upper, name in tiers:
        if value < upper:
            return name
    return tiers[-1][1]


def describe(rgb: RGB) -> str:
    """Plain-language color description, e.g. 'Light muted teal' or 'Dark brown'."""
    h, _, l = rgb_to_hsl(rgb)
    _, s, v = rgb_to_hsv(rgb)  # HSV saturation tracks perceived colorfulness better

    # Neutrals: black / white / grays, optionally warm- or cool-tinted.
    if v < 0.06:
        return "Black"
    # Faint tints are obvious on light colours but invisible on mid-tone grays.
    if s < (0.07 if l > 0.85 else 0.12):
        if l > 0.93:
            base = "white" if s < 0.03 else "off-white"
        else:
            base = _tier(l, [(0.2, "very dark gray"), (0.4, "dark gray"), (0.6, "gray"),
                             (0.8, "light gray"), (1.01, "very light gray")])
        if s >= 0.03:
            fam = hue_family(h)
            if fam in _WARM:
                base = base.replace("gray", "warm gray").replace("off-white", "warm off-white")
            elif fam in _COOL:
                base = base.replace("gray", "cool gray").replace("off-white", "cool off-white")
        return base[0].upper() + base[1:]

    fam = hue_family(h)
    light = _tier(l, [(0.18, "very dark"), (0.35, "dark"), (0.65, ""), (0.82, "light"),
                      (1.01, "very light")])
    sat = _tier(s, [(0.2, "grayish"), (0.45, "muted"), (0.8, ""), (1.01, "vivid")])

    # Everyday names that people use instead of "dark orange" etc.
    if fam in ("red-orange", "orange", "amber") and l < 0.45 and s > 0.2:
        fam = "brown"
        if sat != "grayish":
            sat = ""
    elif fam == "pink" and l < 0.6 and s > 0.45:  # crimson, raspberry: reads as red
        fam = "red" if h >= 342 else "magenta"
    elif fam in ("red", "pink", "magenta") and l > 0.8 or fam == "red" and l > 0.7:
        fam = "pink"
        if light == "very light":
            light, sat = "pale", ""
    elif fam == "cyan" and l < 0.4:
        fam = "teal"
        if sat != "grayish":
            sat = ""
    elif fam in ("orange", "amber", "yellow") and 0.55 <= l <= 0.85 and 0.15 <= s <= 0.6:
        fam, light, sat = "tan", _tier(l, [(0.65, "dark"), (0.8, ""), (1.01, "light")]), ""
    elif fam in ("orange", "amber", "yellow") and l > 0.85 and s < 0.7:
        fam, light, sat = "beige", "", ""
    elif fam in ("yellow", "yellow-green") and l < 0.45:
        fam, light = "olive", _tier(l, [(0.2, "dark"), (1.01, "")])
        if sat != "grayish":
            sat = ""
    elif fam == "blue" and l <= 0.3:
        fam, light, sat = "navy", "", ""
    elif light == "very light" and sat in ("grayish", "muted"):
        light, sat = "pale", ""

    words = [w for w in (light, sat, fam) if w]
    text = " ".join(words)
    return text[0].upper() + text[1:]


# --------------------------------------------------------------------------- bundle

@dataclass(frozen=True)
class ColorInfo:
    rgb: RGB
    hsl: tuple[float, float, float]
    hsv: tuple[float, float, float]
    cmyk: tuple[float, float, float, float]
    lab: tuple[float, float, float]
    name: str
    name_rgb: RGB
    name_distance: float
    description: str
    simulations: tuple[tuple[str, RGB, str], ...]  # (kind, rgb, description)
    luminance: float

    @property
    def name_is_exact(self) -> bool:
        return self.name_distance < 1.0

    def hex(self, upper: bool = True) -> str:
        return rgb_to_hex(self.rgb, upper)

    @property
    def contrast_white(self) -> float:
        return contrast_ratio(self.rgb, (255, 255, 255))

    @property
    def contrast_black(self) -> float:
        return contrast_ratio(self.rgb, (0, 0, 0))


@lru_cache(maxsize=4096)
def color_info(rgb: RGB) -> ColorInfo:
    name, name_rgb, dist = nearest_named_color(rgb)
    sims = tuple(
        (kind, sim, describe(sim))
        for kind in CVD_KINDS
        for sim in (simulate_cvd(rgb, kind),)
    )
    return ColorInfo(
        rgb=rgb,
        hsl=rgb_to_hsl(rgb),
        hsv=rgb_to_hsv(rgb),
        cmyk=rgb_to_cmyk(rgb),
        lab=rgb_to_lab(rgb),
        name=name,
        name_rgb=name_rgb,
        name_distance=dist,
        description=describe(rgb),
        simulations=sims,
        luminance=relative_luminance(rgb),
    )
