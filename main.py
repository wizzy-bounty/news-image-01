"""The World Today - one image summing up Friday 13 November 2026.

A newsroom magazine cover / infographic: a navy masthead, a stylised
globe as the focal point, six illustrated vignette panels (two rows of
three) for the day's six biggest stories, and a brick-red footer ticker
for the seventh story (the record deportations figure).

Pure Python 3 standard library, fully deterministic: fixed integer
arithmetic, a seeded LCG only for scattering crowd dots, no clock, no
network, no unseeded randomness. Every run writes byte-identical bytes
to $MAKEFUN_OUTPUT_DIR/entry.png (PNG, 1024x1024, filter 0 per row).
"""

import math
import os
import struct
import zlib

W = 1024
H = 1024


# ---------------------------------------------------------------------------
# Deterministic scatter helper
# ---------------------------------------------------------------------------

class LCG:
    """Tiny linear congruential generator: exact integer math, so the
    stream is identical on every run and every platform."""

    def __init__(self, seed):
        self.state = seed & 0xFFFFFFFF

    def next(self):
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state

    def uniform(self):
        return self.next() / 4294967296.0

    def randint(self, lo, hi):
        return lo + self.next() % (hi - lo + 1)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def lerp3(c0, c1, t):
    return (int(c0[0] + (c1[0] - c0[0]) * t),
            int(c0[1] + (c1[1] - c0[1]) * t),
            int(c0[2] + (c1[2] - c0[2]) * t))


# ---------------------------------------------------------------------------
# Canvas: a list of RGB bytearray rows, with flat-shape drawing helpers
# ---------------------------------------------------------------------------

ROWS = [bytearray(W * 3) for _ in range(H)]


def set_px(x, y, color):
    if 0 <= x < W and 0 <= y < H:
        i = x * 3
        row = ROWS[y]
        row[i] = color[0]
        row[i + 1] = color[1]
        row[i + 2] = color[2]


def blend_px(x, y, color, alpha):
    """Blend a colour over the pixel with the given coverage 0..1."""
    if alpha <= 0.0 or not (0 <= x < W and 0 <= y < H):
        return
    if alpha >= 1.0:
        set_px(x, y, color)
        return
    i = x * 3
    row = ROWS[y]
    row[i] = int(row[i] + (color[0] - row[i]) * alpha)
    row[i + 1] = int(row[i + 1] + (color[1] - row[i + 1]) * alpha)
    row[i + 2] = int(row[i + 2] + (color[2] - row[i + 2]) * alpha)


def fill_rect(x0, y0, x1, y1, color):
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(W - 1, x1)
    y1 = min(H - 1, y1)
    if x0 > x1 or y0 > y1:
        return
    span = bytes(color) * (x1 - x0 + 1)
    for y in range(y0, y1 + 1):
        ROWS[y][x0 * 3:(x1 + 1) * 3] = span


def fill_disc(cx, cy, r, color):
    """Filled circle with a one-pixel soft edge."""
    r = float(r)
    x0 = max(0, int(cx - r - 1))
    x1 = min(W - 1, int(cx + r + 1))
    y0 = max(0, int(cy - r - 1))
    y1 = min(H - 1, int(cy + r + 1))
    for y in range(y0, y1 + 1):
        dy = y - cy
        for x in range(x0, x1 + 1):
            dx = x - cx
            d = math.sqrt(dx * dx + dy * dy)
            if d <= r - 0.5:
                set_px(x, y, color)
            elif d <= r + 0.5:
                blend_px(x, y, color, r + 0.5 - d)


def fill_disc_plain(cx, cy, r, color):
    """Filled circle, hard edge (for small detail dots and line joints)."""
    r = int(r)
    for y in range(max(0, cy - r), min(H, cy + r + 1)):
        dy = y - cy
        span = int(math.sqrt(max(0, r * r - dy * dy)))
        for x in range(max(0, cx - span), min(W, cx + span + 1)):
            set_px(x, y, color)


def fill_ellipse(cx, cy, rx, ry, color):
    """Filled ellipse with a one-pixel soft edge."""
    rx = float(rx)
    ry = float(ry)
    x0 = max(0, int(cx - rx - 1))
    x1 = min(W - 1, int(cx + rx + 1))
    y0 = max(0, int(cy - ry - 1))
    y1 = min(H - 1, int(cy + ry + 1))
    for y in range(y0, y1 + 1):
        ny = (y - cy) / ry
        for x in range(x0, x1 + 1):
            nx = (x - cx) / rx
            q = math.sqrt(nx * nx + ny * ny)
            if q <= 0.97:
                set_px(x, y, color)
            elif q <= 1.03:
                blend_px(x, y, color, (1.03 - q) / 0.06)


def fill_poly(points, color):
    """Even-odd scanline fill of a simple polygon (integer vertices)."""
    if len(points) < 3:
        return
    ys = [p[1] for p in points]
    y0 = max(0, min(ys))
    y1 = min(H - 1, max(ys))
    n = len(points)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x1, y1p = points[i]
            x2, y2p = points[(i + 1) % n]
            if (y1p <= y < y2p) or (y2p <= y < y1p):
                t = (y - y1p) / (y2p - y1p)
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = max(0, int(math.ceil(xs[k])))
            xb = min(W - 1, int(math.floor(xs[k + 1])))
            if xa <= xb:
                ROWS[y][xa * 3:(xb + 1) * 3] = bytes(color) * (xb - xa + 1)


def fill_poly_circle_clip(points, cx, cy, r, color):
    """fill_poly, but clipped to the disc centred (cx, cy) radius r."""
    if len(points) < 3:
        return
    ys = [p[1] for p in points]
    y0 = max(0, min(ys))
    y1 = min(H - 1, max(ys))
    n = len(points)
    for y in range(y0, y1 + 1):
        dy = y - cy
        if abs(dy) > r:
            continue
        hw = int(math.sqrt(r * r - dy * dy))
        xs = []
        for i in range(n):
            x1, y1p = points[i]
            x2, y2p = points[(i + 1) % n]
            if (y1p <= y < y2p) or (y2p <= y < y1p):
                t = (y - y1p) / (y2p - y1p)
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = max(cx - hw, int(math.ceil(xs[k])))
            xb = min(cx + hw, int(math.floor(xs[k + 1])))
            if xa <= xb:
                ROWS[y][xa * 3:(xb + 1) * 3] = bytes(color) * (xb - xa + 1)


def thick_line(x0, y0, x1, y1, width, color):
    """A thick straight segment, drawn as a chain of small discs."""
    dx = x1 - x0
    dy = y1 - y0
    dist = math.sqrt(dx * dx + dy * dy)
    steps = max(1, int(dist / 2.0) + 1)
    r = max(1, int(width / 2))
    for s in range(steps + 1):
        t = s / steps
        fill_disc_plain(int(x0 + dx * t), int(y0 + dy * t), r, color)


def arc(cx, cy, r, a0, a1, width, color):
    """A thick arc, angles in radians, drawn as a chain of small discs."""
    span = a1 - a0
    steps = max(8, int(abs(span) * r / 3.0) + 1)
    rad = max(1, int(width / 2))
    for s in range(steps + 1):
        a = a0 + span * s / steps
        fill_disc_plain(int(cx + r * math.cos(a)), int(cy + r * math.sin(a)),
                        rad, color)


def ellipse_outline(cx, cy, rx, ry, rot, color, width, y_min=None):
    """Outline of a (possibly rotated) ellipse. When y_min is given, only
    segments whose endpoints are at or below y_min are drawn."""
    pts = []
    n = 160
    for i in range(n + 1):
        t = 2.0 * math.pi * i / n
        ex = rx * math.cos(t)
        ey = ry * math.sin(t)
        x = cx + ex * math.cos(rot) - ey * math.sin(rot)
        y = cy + ex * math.sin(rot) + ey * math.cos(rot)
        pts.append((x, y))
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        if y_min is not None and not (y0 >= y_min and y1 >= y_min):
            continue
        thick_line(int(x0), int(y0), int(x1), int(y1), width, color)


def rounded_rect(x0, y0, x1, y1, rad, color):
    """Filled rectangle with rounded corners."""
    fill_rect(x0 + rad, y0, x1 - rad, y1, color)
    fill_rect(x0, y0 + rad, x1, y1 - rad, color)
    fill_disc(x0 + rad, y0 + rad, rad, color)
    fill_disc(x1 - rad, y0 + rad, rad, color)
    fill_disc(x0 + rad, y1 - rad, rad, color)
    fill_disc(x1 - rad, y1 - rad, rad, color)


def rect_outline(x0, y0, x1, y1, width, color):
    fill_rect(x0, y0, x1, y0 + width - 1, color)
    fill_rect(x0, y1 - width + 1, x1, y1, color)
    fill_rect(x0, y0, x0 + width - 1, y1, color)
    fill_rect(x1 - width + 1, y0, x1, y1, color)


# ---------------------------------------------------------------------------
# Palette: a mature newsroom palette - deep navy, paper cream, gold,
# brick red, ocean blue, muted green land.
# ---------------------------------------------------------------------------

NAVY = (18, 38, 66)
NAVY_DARK = (12, 26, 46)
PAPER = (247, 241, 226)
PANEL_BG = (255, 253, 244)
GOLD = (214, 178, 94)
GOLD_DARK = (176, 140, 62)
CREAM = (245, 237, 216)
BRICK = (158, 59, 43)
BRICK_LIGHT = (192, 90, 68)
WHITE = (255, 255, 255)
INK = (24, 32, 44)
OCEAN_TOP = (72, 138, 196)
OCEAN_BOT = (24, 68, 130)
LATLINE = (178, 210, 232)
LAND = (78, 122, 82)
LAND_DARK = (58, 98, 64)
CITY = (255, 205, 92)
WOOD = (122, 84, 50)
WOOD_DARK = (96, 58, 32)
STEEL = (110, 123, 134)
STEEL_DARK = (84, 96, 108)
SEA = (58, 110, 140)
SAND = (217, 185, 138)
SKIN = (232, 184, 138)
SKIN_DARK = (205, 152, 108)
HAIR = (60, 40, 20)
PITCH = (58, 140, 74)
CHARCOAL = (58, 58, 62)


# ---------------------------------------------------------------------------
# Hand-drawn 5x7 bitmap font (every glyph the labels need)
# ---------------------------------------------------------------------------

GLYPHS = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11100", "10010", "10001", "10001", "10001", "10010", "11100"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    ":": ("00000", "00100", "00000", "00000", "00000", "00100", "00000"),
    "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    ",": ("00000", "00000", "00000", "00000", "00000", "00100", "01000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00000", "00100"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
}


def text_width(text, scale, adv):
    return len(text) * adv - (adv - 5 * scale)


def draw_text(text, cx, top, scale, color, adv=None, bold=False):
    """Draw text centred on cx in the bitmap font. With bold=True every
    filled cell is drawn one pixel larger on each side, so the strokes
    read as heavy headline type."""
    if adv is None:
        adv = 6 * scale
    x = cx - text_width(text, scale, adv) // 2
    for ch in text:
        glyph = GLYPHS[ch]
        for r in range(7):
            row = glyph[r]
            for c in range(5):
                if row[c] == "1":
                    px = x + c * scale
                    py = top + r * scale
                    if bold:
                        fill_rect(px - 1, py - 1, px + scale, py + scale - 1,
                                  color)
                    else:
                        fill_rect(px, py, px + scale - 1, py + scale - 1,
                                  color)
        x += adv


# ---------------------------------------------------------------------------
# Masthead
# ---------------------------------------------------------------------------

def draw_masthead():
    fill_rect(0, 0, W - 1, 119, NAVY)
    fill_rect(0, 0, W - 1, 3, GOLD)
    draw_text("THE WORLD TODAY", 512, 14, 9, GOLD)
    draw_text("FRIDAY 13 NOVEMBER 2026", 512, 88, 3, CREAM)
    fill_rect(0, 114, W - 1, 115, GOLD)


# ---------------------------------------------------------------------------
# Globe (focal point) with orbit ring, side ornaments
# ---------------------------------------------------------------------------

GLOBE_CX = 512
GLOBE_CY = 308
GLOBE_R = 148


def draw_globe_ocean():
    """Ocean as a vertical gradient: light at the top, deep at the
    bottom, clipped to the disc by per-row chords."""
    for y in range(GLOBE_CY - GLOBE_R, GLOBE_CY + GLOBE_R + 1):
        dy = y - GLOBE_CY
        hw = int(math.sqrt(GLOBE_R * GLOBE_R - dy * dy))
        t = (y - (GLOBE_CY - GLOBE_R)) / (2.0 * GLOBE_R)
        c = lerp3(OCEAN_TOP, OCEAN_BOT, t)
        x0 = GLOBE_CX - hw
        x1 = GLOBE_CX + hw
        ROWS[y][x0 * 3:(x1 + 1) * 3] = bytes(c) * (x1 - x0 + 1)


def draw_globe_lines():
    """Latitude chords and longitude ellipses in pale blue."""
    for lat in (-60, -35, 0, 35, 60):
        dy = int(GLOBE_R * math.sin(math.radians(lat)))
        hw = int(GLOBE_R * math.cos(math.radians(lat)))
        thick_line(GLOBE_CX - hw, GLOBE_CY + dy,
                   GLOBE_CX + hw, GLOBE_CY + dy, 2, LATLINE)
    # central meridian
    thick_line(GLOBE_CX, GLOBE_CY - GLOBE_R, GLOBE_CX, GLOBE_CY + GLOBE_R,
               2, LATLINE)
    for lon in (45, 75):
        rx = int(GLOBE_R * math.cos(math.radians(lon)))
        ellipse_outline(GLOBE_CX, GLOBE_CY, rx, GLOBE_R, 0.0, LATLINE, 2)


CONTINENTS = [
    # North America
    [(420, 190), (455, 172), (498, 182), (512, 206), (498, 236),
     (472, 256), (448, 238), (428, 222), (412, 206)],
    # South America
    [(482, 262), (506, 258), (516, 282), (502, 328), (486, 348),
     (472, 312), (470, 282)],
    # Greenland
    [(498, 162), (516, 158), (522, 172), (508, 180)],
    # Europe
    [(542, 192), (566, 182), (582, 198), (572, 224), (550, 230),
     (536, 214)],
    # Africa
    [(546, 244), (576, 238), (592, 258), (586, 300), (566, 330),
     (546, 310), (536, 274)],
    # Asia
    [(586, 184), (642, 168), (666, 194), (652, 230), (616, 240),
     (596, 220)],
    # Australia
    [(612, 298), (642, 294), (652, 314), (632, 330), (610, 320)],
]

CITY_LIGHTS = [(455, 200), (490, 225), (470, 250), (505, 300),
               (560, 205), (575, 275), (625, 205), (635, 310)]


def draw_globe():
    # orbit ring behind the globe (its lower arc is redrawn in front)
    ellipse_outline(GLOBE_CX, GLOBE_CY, 205, 54, math.radians(-18),
                    GOLD, 3)
    draw_globe_ocean()
    draw_globe_lines()
    for land in CONTINENTS:
        fill_poly_circle_clip(land, GLOBE_CX, GLOBE_CY, GLOBE_R, LAND)
    for (lx, ly) in CITY_LIGHTS:
        fill_disc_plain(lx, ly, 3, CITY)
        fill_disc_plain(lx - 1, ly - 1, 1, WHITE)
    # navy rim
    arc(GLOBE_CX, GLOBE_CY, GLOBE_R, 0.0, 2.0 * math.pi, 4, NAVY)
    # orbit ring in front of the globe's lower half
    ellipse_outline(GLOBE_CX, GLOBE_CY, 205, 54, math.radians(-18),
                    GOLD, 3, y_min=GLOBE_CY - 4)
    # small satellite on the upper-right of the ring
    t = -0.6
    ex = 205 * math.cos(t)
    ey = 54 * math.sin(t)
    rot = math.radians(-18)
    sx = int(GLOBE_CX + ex * math.cos(rot) - ey * math.sin(rot))
    sy = int(GLOBE_CY + ex * math.sin(rot) + ey * math.cos(rot))
    fill_disc_plain(sx, sy, 5, GOLD_DARK)
    fill_disc_plain(sx - 1, sy - 1, 2, GOLD)


def draw_compass_rose(cx, cy):
    """A small gold compass rose left of the globe."""
    arc(cx, cy, 34, 0.0, 2.0 * math.pi, 3, NAVY)
    arc(cx, cy, 26, 0.0, 2.0 * math.pi, 2, GOLD_DARK)
    fill_poly([(cx, cy - 24), (cx + 6, cy - 6), (cx, cy), (cx - 6, cy - 6)],
              GOLD)
    fill_poly([(cx, cy + 24), (cx + 6, cy + 6), (cx, cy), (cx - 6, cy + 6)],
              GOLD)
    fill_poly([(cx - 24, cy), (cx - 6, cy - 6), (cx, cy), (cx - 6, cy + 6)],
              NAVY)
    fill_poly([(cx + 24, cy), (cx + 6, cy - 6), (cx, cy), (cx + 6, cy + 6)],
              NAVY)
    fill_disc_plain(cx, cy, 5, NAVY)


def draw_newspaper_stack(cx, cy):
    """A small stack of newspapers right of the globe (no text)."""
    # bottom sheet
    fill_rect(cx - 52, cy - 26, cx + 44, cy + 34, WHITE)
    rect_outline(cx - 52, cy - 26, cx + 44, cy + 34, 2, NAVY)
    for i, ly in enumerate((-14, -2, 10, 22)):
        fill_rect(cx - 44, cy + ly, cx + 36, cy + ly + 3, (150, 160, 175))
    # top sheet, slightly tilted
    fill_poly([(cx - 46, cy - 38), (cx + 58, cy - 46), (cx + 64, cy + 22),
               (cx - 40, cy + 30)], WHITE)
    thick_line(cx - 46, cy - 38, cx + 58, cy - 46, 2, NAVY)
    thick_line(cx + 58, cy - 46, cx + 64, cy + 22, 2, NAVY)
    thick_line(cx + 64, cy + 22, cx - 40, cy + 30, 2, NAVY)
    thick_line(cx - 40, cy + 30, cx - 46, cy - 38, 2, NAVY)
    fill_rect(cx - 38, cy - 32, cx + 10, cy - 20, NAVY)
    for i, ly in enumerate((-14, -4, 6, 16)):
        thick_line(cx - 38, cy + ly, cx + 52, cy + ly - 2, 3,
                   (150, 160, 175))


# ---------------------------------------------------------------------------
# Vignette panels (2 rows x 3 columns)
# ---------------------------------------------------------------------------

PANEL_XS = (4, 344, 684)
PANEL_YS = (516, 708)
PANEL_W = 336
PANEL_H = 184


def draw_panel_frame(px, py):
    fill_rect(px, py, px + PANEL_W - 1, py + PANEL_H - 1, PANEL_BG)
    rect_outline(px, py, px + PANEL_W - 1, py + PANEL_H - 1, 3, NAVY)
    # gold divider between the illustration and the caption
    fill_rect(px + 12, py + 121, px + PANEL_W - 13, py + 122, GOLD)


def draw_panel_labels(px, py, line1, line2):
    draw_text(line1, px + PANEL_W // 2, py + 128, 3, NAVY, adv=17,
              bold=True)
    draw_text(line2, px + PANEL_W // 2, py + 154, 3, NAVY, adv=17,
              bold=True)


def art_senate(px, py):
    """An empty witness chair behind the Senate hearing table."""
    fill_rect(px + 6, py + 6, px + 329, py + 52, (201, 210, 220))
    fill_rect(px + 6, py + 52, px + 329, py + 58, WOOD)
    # empty witness chair, centred: light-wood slatted backrest + seat
    # with a pale top edge, so it reads as a chair against the grey wall
    # (the old solid-navy block read as a dark slab)
    fill_rect(px + 138, py + 28, px + 198, py + 34, WOOD)
    fill_rect(px + 138, py + 28, px + 198, py + 30, (178, 138, 96))
    fill_rect(px + 140, py + 34, px + 196, py + 76, (150, 110, 74))
    for sx in (152, 166, 180):
        fill_rect(px + sx, py + 36, px + sx + 4, py + 72, WOOD_DARK)
    fill_rect(px + 130, py + 76, px + 206, py + 86, (150, 110, 74))
    fill_rect(px + 130, py + 76, px + 206, py + 78, (178, 138, 96))
    fill_rect(px + 130, py + 84, px + 206, py + 86, WOOD_DARK)
    thick_line(px + 136, py + 86, px + 136, py + 96, 5, WOOD_DARK)
    thick_line(px + 200, py + 86, px + 200, py + 96, 5, WOOD_DARK)
    # hearing table
    fill_rect(px + 36, py + 92, px + 300, py + 116, WOOD)
    fill_rect(px + 36, py + 104, px + 300, py + 116, WOOD_DARK)
    fill_rect(px + 36, py + 92, px + 300, py + 94, (150, 110, 74))
    # microphone on the table
    thick_line(px + 250, py + 92, px + 250, py + 74, 3, INK)
    fill_disc_plain(px + 250, py + 70, 6, INK)
    # papers and a nameplate on the table
    fill_rect(px + 70, py + 95, px + 110, py + 102, WHITE)
    fill_rect(px + 120, py + 96, px + 150, py + 102, WHITE)
    fill_rect(px + 162, py + 95, px + 212, py + 105, GOLD)
    fill_rect(px + 166, py + 98, px + 208, py + 100, GOLD_DARK)


def art_handshake(px, py):
    """Two arms meet in a handshake over a table with two small flags."""
    fill_rect(px + 6, py + 6, px + 329, py + 118, (214, 226, 235))
    # small flags on poles at the table ends
    # United States flag (stripes + blue canton)
    thick_line(px + 52, py + 30, px + 52, py + 92, 3, INK)
    for s in range(7):
        col = (178, 52, 44) if s % 2 == 0 else WHITE
        fill_rect(px + 53, py + 34 + s * 3, px + 88, py + 36 + s * 3, col)
    fill_rect(px + 53, py + 34, px + 68, py + 45, (40, 70, 130))
    fill_disc_plain(px + 57, py + 37, 1, WHITE)
    fill_disc_plain(px + 64, py + 42, 1, WHITE)
    fill_disc_plain(px + 60, py + 39, 1, WHITE)
    # Ukraine flag (blue over yellow)
    thick_line(px + 284, py + 30, px + 284, py + 92, 3, INK)
    fill_rect(px + 248, py + 34, px + 283, py + 45, (0, 91, 172))
    fill_rect(px + 248, py + 46, px + 283, py + 57, (255, 213, 0))
    # table
    fill_rect(px + 6, py + 92, px + 329, py + 118, WOOD)
    fill_rect(px + 6, py + 92, px + 329, py + 95, (150, 110, 74))
    # sleeves reaching in from both sides
    thick_line(px + 10, py + 82, px + 150, py + 66, 22, NAVY)
    thick_line(px + 326, py + 82, px + 186, py + 66, 22, CHARCOAL)
    # white cuffs
    fill_rect(px + 138, py + 56, px + 152, py + 76, WHITE)
    fill_rect(px + 184, py + 56, px + 198, py + 76, WHITE)
    # clasped hands
    fill_disc_plain(px + 168, py + 64, 14, SKIN)
    fill_ellipse(px + 156, py + 70, 12, 10, SKIN_DARK)
    fill_ellipse(px + 180, py + 58, 12, 10, SKIN)


def art_warship(px, py):
    """A grey warship smoking on a cold sea, a drone above it."""
    fill_rect(px + 6, py + 6, px + 329, py + 70, (207, 224, 232))
    # smoke from the funnel
    fill_disc(px + 208, py + 46, 10, (185, 194, 200))
    fill_disc(px + 218, py + 30, 13, (200, 208, 212))
    fill_disc(px + 232, py + 16, 9, (214, 220, 224))
    # small drone with a dashed trail
    fill_disc_plain(px + 292, py + 22, 3, INK)
    for (dx, dy) in ((300, 18), (308, 14), (316, 10)):
        fill_disc_plain(px + dx, py + dy, 2, (140, 150, 158))
    # superstructure and mast
    fill_rect(px + 120, py + 52, px + 180, py + 76, STEEL)
    fill_rect(px + 128, py + 44, px + 164, py + 52, STEEL_DARK)
    thick_line(px + 146, py + 44, px + 146, py + 28, 3, STEEL_DARK)
    fill_disc_plain(px + 146, py + 26, 4, STEEL_DARK)
    # funnel
    fill_rect(px + 200, py + 58, px + 216, py + 76, STEEL_DARK)
    # hull
    fill_poly([(px + 55, py + 76), (px + 270, py + 76), (px + 296, py + 86),
               (px + 268, py + 98), (px + 70, py + 98)], STEEL)
    fill_rect(px + 60, py + 76, px + 292, py + 79, STEEL_DARK)
    # sea with white wave lines
    fill_rect(px + 6, py + 98, px + 329, py + 118, SEA)
    for (wx, wy, wl) in ((30, 106, 40), (120, 112, 52), (220, 106, 44),
                         (280, 113, 36)):
        thick_line(px + wx, py + wy, px + wx + wl, py + wy, 2, WHITE)


def art_radar(px, py):
    """A radar dome on a desert coast, a missile trail arcing overhead."""
    fill_rect(px + 6, py + 6, px + 329, py + 76, (246, 232, 200))
    fill_disc_plain(px + 300, py + 24, 10, GOLD)
    # missile trail: a bold curved smoke arc with soft puffs, ending in
    # the missile + flame (reads as a launch/strike at a glance)
    arc(px + 330, py + 120, 102, -2.47, -1.91, 4, (185, 185, 185))
    for (sx, sy, sr) in ((286, 32, 5), (274, 40, 6), (262, 48, 7),
                         (250, 56, 6)):
        fill_disc(px + sx, py + sy, sr, (208, 208, 208))
    fill_poly([(px + 236, py + 50), (px + 254, py + 58), (px + 238, py + 66),
               (px + 230, py + 60)], (210, 210, 210))
    fill_disc_plain(px + 232, py + 58, 5, (255, 138, 61))
    # desert sand and sea strip
    fill_rect(px + 6, py + 76, px + 240, py + 118, SAND)
    fill_rect(px + 240, py + 76, px + 329, py + 118, SEA)
    thick_line(px + 240, py + 76, px + 240, py + 118, 2, WHITE)
    fill_ellipse(px + 90, py + 112, 60, 12, (200, 168, 118))
    fill_ellipse(px + 190, py + 114, 46, 10, (200, 168, 118))
    # radar dome: bigger white dome on a dark pedestal, with a tall
    # antenna mast + crossbar + red tip on top so it reads as radar
    fill_rect(px + 96, py + 78, px + 104, py + 112, STEEL_DARK)
    fill_rect(px + 78, py + 110, px + 122, py + 118, STEEL_DARK)
    fill_disc(px + 100, py + 52, 30, WHITE)
    fill_rect(px + 70, py + 52, px + 130, py + 55, (246, 232, 200))
    arc(px + 100, py + 52, 20, math.pi, 2.0 * math.pi, 2, (180, 190, 200))
    thick_line(px + 100, py + 22, px + 100, py + 10, 3, STEEL_DARK)
    thick_line(px + 92, py + 15, px + 108, py + 15, 2, STEEL_DARK)
    fill_disc_plain(px + 100, py + 8, 3, (226, 59, 59))
    # parabolic dish on its own pole, tilted up-left toward the missile
    thick_line(px + 168, py + 118, px + 168, py + 86, 4, STEEL_DARK)
    fill_rect(px + 158, py + 112, px + 178, py + 118, STEEL_DARK)
    arc(px + 168, py + 80, 16, math.pi * 1.05, math.pi * 1.95, 5, STEEL)
    thick_line(px + 168, py + 80, px + 156, py + 62, 2, STEEL_DARK)
    fill_disc_plain(px + 155, py + 61, 3, STEEL_DARK)
    # sweeping beam from the dome
    thick_line(px + 100, py + 48, px + 152, py + 26, 3, GOLD_DARK)


def art_hack(px, py):
    """A hooded masked face on a video-call screen, coins falling below."""
    # video-call screen
    fill_rect(px + 24, py + 8, px + 312, py + 82, (16, 28, 48))
    rect_outline(px + 24, py + 8, px + 312, py + 82, 2, (120, 140, 160))
    fill_disc_plain(px + 292, py + 18, 4, (226, 59, 59))
    # hooded figure: dark hood, pale mask, black eye slits
    fill_disc(px + 168, py + 48, 26, (30, 34, 40))
    fill_ellipse(px + 168, py + 50, 18, 22, (232, 232, 225))
    fill_rect(px + 152, py + 42, px + 161, py + 46, INK)
    fill_rect(px + 175, py + 42, px + 184, py + 46, INK)
    thick_line(px + 160, py + 64, px + 176, py + 64, 2, INK)
    fill_ellipse(px + 168, py + 80, 34, 8, (30, 34, 40))
    # falling gold coins with a $ mark
    for (cx, cy) in ((70, 98), (168, 106), (266, 96)):
        fill_disc_plain(px + cx, py + cy, 10, (232, 178, 60))
        fill_disc_plain(px + cx, py + cy, 6, (198, 146, 40))
        draw_text("$", px + cx, py + cy - 3, 1, (122, 84, 20))
    # motion dashes under the coins
    for (cx, cy) in ((70, 112), (168, 118), (266, 110)):
        thick_line(px + cx - 6, py + cy, px + cx + 6, py + cy, 2,
                   (170, 170, 170))


def art_kane(px, py):
    """A footballer in white lifting one hand, a gold star above him."""
    # stadium stands with a dotted crowd
    fill_rect(px + 6, py + 6, px + 329, py + 46, (28, 44, 74))
    rng = LCG(0xCA9E)
    for _ in range(60):
        cx = rng.randint(px + 12, px + 324)
        cy = rng.randint(py + 12, py + 40)
        col = [(232, 232, 225), (214, 178, 94), (178, 52, 44),
               (120, 160, 200)][rng.next() % 4]
        fill_disc_plain(cx, cy, 2, col)
    # pitch
    fill_rect(px + 6, py + 74, px + 329, py + 118, PITCH)
    fill_rect(px + 6, py + 74, px + 329, py + 76, WHITE)
    # gold star above the raised hand
    star = []
    for k in range(10):
        a = -math.pi / 2.0 + k * math.pi / 5.0
        r = 11 if k % 2 == 0 else 5
        star.append((int(px + 232 + r * math.cos(a)),
                     int(py + 18 + r * math.sin(a))))
    fill_poly(star, GOLD)
    # player: head, white shirt, shorts, legs, one arm raised high
    fill_disc_plain(px + 168, py + 54, 12, SKIN)
    fill_ellipse(px + 168, py + 48, 12, 6, HAIR)
    fill_rect(px + 154, py + 64, px + 182, py + 88, WHITE)
    fill_rect(px + 154, py + 64, px + 182, py + 66, NAVY)
    fill_rect(px + 156, py + 88, px + 180, py + 98, WHITE)
    thick_line(px + 162, py + 98, px + 158, py + 112, 7, SKIN)
    thick_line(px + 174, py + 98, px + 178, py + 112, 7, SKIN)
    fill_disc_plain(px + 156, py + 114, 5, INK)
    fill_disc_plain(px + 180, py + 114, 5, INK)
    # raised arm (right) and lowered arm (left)
    thick_line(px + 180, py + 68, px + 208, py + 34, 8, WHITE)
    fill_disc_plain(px + 210, py + 30, 5, SKIN)
    thick_line(px + 156, py + 68, px + 142, py + 88, 8, WHITE)
    fill_disc_plain(px + 140, py + 90, 5, SKIN)
    # ball at his feet
    fill_disc_plain(px + 128, py + 108, 8, WHITE)
    fill_disc_plain(px + 128, py + 108, 3, INK)
    fill_disc_plain(px + 124, py + 104, 1, INK)
    fill_disc_plain(px + 132, py + 112, 1, INK)


PANELS = [
    (art_senate, "SENATE SUMMONS", "HUANG & LUTNICK"),
    (art_handshake, "ZELENSKY MEETS", "US ENVOYS"),
    (art_warship, "DRONE HITS", "RUSSIAN WARSHIP"),
    (art_radar, "IRAN CLAIMS STRIKE", "ON US RADAR"),
    (art_hack, "FBI: N. KOREA", "$400M CRYPTO HACK"),
    (art_kane, "KANE BREAKS", "ENGLAND CAPS RECORD"),
]


# ---------------------------------------------------------------------------
# Footer ticker (story 7)
# ---------------------------------------------------------------------------

def draw_footer():
    fill_rect(0, 904, W - 1, H - 1, BRICK)
    fill_rect(0, 904, W - 1, 906, GOLD)
    rect_outline(6, 912, W - 7, H - 7, 2, BRICK_LIGHT)
    # Footer ticker text: scale 3 / adv 17 -> measured width 780 px, so the
    # line spans x=122..902, leaving >100 px clear of both edges (the old
    # scale-4 line ran x=29..996 and the gold diamonds at x=36/988 painted
    # over the first "U" and the last "6"). Diamonds stay at 36/988, now
    # well clear of the text.
    draw_text("US REPORTS RECORD 483,200 DEPORTATIONS IN 2026",
              512, 950, 3, WHITE, adv=17, bold=True)
    # small gold diamonds flanking the ticker text
    for dx in (36, 988):
        fill_poly([(dx, 956), (dx + 8, 964), (dx, 972), (dx - 8, 964)],
                  GOLD)


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------

def render():
    fill_rect(0, 0, W - 1, H - 1, PAPER)
    draw_masthead()
    draw_compass_rose(248, 308)
    draw_newspaper_stack(772, 308)
    draw_globe()
    fill_rect(40, 500, 983, 501, GOLD)
    for i, (art, line1, line2) in enumerate(PANELS):
        px = PANEL_XS[i % 3]
        py = PANEL_YS[i // 3]
        draw_panel_frame(px, py)
        art(px, py)
        draw_panel_labels(px, py, line1, line2)
    draw_footer()


# ---------------------------------------------------------------------------
# PNG encoding (deterministic; filter 0 on every row)
# ---------------------------------------------------------------------------

def _chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def encode_png(rows):
    raw = bytearray()
    for row in rows:
        raw.append(0)
        raw += row
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + _chunk(b"IEND", b""))


def main():
    render()
    data = encode_png(ROWS)
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "entry.png"), "wb") as fh:
        fh.write(data)


if __name__ == "__main__":
    main()
