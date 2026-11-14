#!/usr/bin/env python3
"""news-image-01 — "The World Today: Friday 13 November 2026".

A deterministic pure-stdlib Python program that draws one front-page
image summing up the world's news of Friday 13 November 2026:

  1. The US Senate summons Huang & Lutnick to testify
  2. Zelensky meets US envoys (Europe brought into the talks)
  3. A Ukrainian drone hits a Russian warship in the Gulf of Finland
  4. Iran claims a strike on a US radar site in Bahrain
  5. The FBI on North Korea's $400m crypto hack via fake video calls
  6. Harry Kane breaks England's caps record
  7. The US reports a record 483,200 deportations in 2026

Rendering: a small vector engine (supersampled 2x, box-downsampled)
with a hand-drawn stroke grotesque for crisp editorial type. No
network, no clock, no randomness outside a fixed-seed LCG: every run
writes byte-identical output to $MAKEFUN_OUTPUT_DIR/entry.png
(PNG, 1024x1024).
"""
import math, os, zlib, struct

SS = 2
W, H = 1024, 1024
SW, SH = W * SS, H * SS

# framebuffer: list of bytearray rows, RGB
FB = [bytearray(SW * 3) for _ in range(SH)]


def _si(v):
    return int(round(v * SS))


def set_px(x, y, color):
    if 0 <= x < SW and 0 <= y < SH:
        row = FB[y]
        i = x * 3
        row[i] = color[0]; row[i + 1] = color[1]; row[i + 2] = color[2]


def blend_px(x, y, color, a):
    if a <= 0:
        return
    if 0 <= x < SW and 0 <= y < SH:
        row = FB[y]
        i = x * 3
        ia = 1.0 - a
        row[i] = int(row[i] * ia + color[0] * a)
        row[i + 1] = int(row[i + 1] * ia + color[1] * a)
        row[i + 2] = int(row[i + 2] * ia + color[2] * a)


def fill_all(color):
    rowbytes = bytes(color) * SW
    for y in range(SH):
        FB[y][:] = rowbytes


def rect(x0, y0, x1, y1, color):
    X0, Y0, X1, Y1 = _si(x0), _si(y0), _si(x1), _si(y1)
    if X1 < 0 or Y1 < 0 or X0 >= SW or Y0 >= SH:
        return
    X0 = max(0, X0); Y0 = max(0, Y0); X1 = min(SW, X1); Y1 = min(SH, Y1)
    seg = bytes(color) * (X1 - X0)
    for y in range(Y0, Y1):
        FB[y][X0 * 3:X1 * 3] = seg


def vgrad(x0, y0, x1, y1, c_top, c_bot):
    X0, Y0, X1, Y1 = _si(x0), _si(y0), _si(x1), _si(y1)
    X0 = max(0, X0); Y0 = max(0, Y0); X1 = min(SW, X1); Y1 = min(SH, Y1)
    if X1 <= X0 or Y1 <= Y0:
        return
    span = max(1, Y1 - Y0 - 1)
    for y in range(Y0, Y1):
        t = (y - Y0) / span
        c = (int(c_top[0] + (c_bot[0] - c_top[0]) * t),
             int(c_top[1] + (c_bot[1] - c_top[1]) * t),
             int(c_top[2] + (c_bot[2] - c_top[2]) * t))
        FB[y][X0 * 3:X1 * 3] = bytes(c) * (X1 - X0)


def hgrad(x0, y0, x1, y1, c_left, c_right):
    X0, Y0, X1, Y1 = _si(x0), _si(y0), _si(x1), _si(y1)
    X0 = max(0, X0); Y0 = max(0, Y0); X1 = min(SW, X1); Y1 = min(SH, Y1)
    if X1 <= X0 or Y1 <= Y0:
        return
    span = max(1, X1 - X0 - 1)
    for x in range(X0, X1):
        t = (x - X0) / span
        c = bytes((int(c_left[0] + (c_right[0] - c_left[0]) * t),
                   int(c_left[1] + (c_right[1] - c_left[1]) * t),
                   int(c_left[2] + (c_right[2] - c_left[2]) * t)))
        for y in range(Y0, Y1):
            FB[y][x * 3:x * 3 + 3] = c


def disc(cx, cy, r, color):
    CX, CY, R = cx * SS, cy * SS, r * SS
    x0 = int(max(0, CX - R - 1)); x1 = int(min(SW - 1, CX + R + 1))
    y0 = int(max(0, CY - R - 1)); y1 = int(min(SH - 1, CY + R + 1))
    r2 = R * R
    for y in range(y0, y1 + 1):
        dy = y - CY
        rem = r2 - dy * dy
        if rem < 0:
            continue
        dx = math.sqrt(rem)
        xa = int(max(0, CX - dx)); xb = int(min(SW - 1, CX + dx))
        FB[y][xa * 3:(xb + 1) * 3] = bytes(color) * (xb + 1 - xa)


def disc_ring(cx, cy, r, wdt, color):
    CX, CY = cx * SS, cy * SS
    R = r * SS; Wd = wdt * SS
    x0 = int(max(0, CX - R - Wd)); x1 = int(min(SW - 1, CX + R + Wd))
    y0 = int(max(0, CY - R - Wd)); y1 = int(min(SH - 1, CY + R + Wd))
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            d = math.hypot(x - CX, y - CY)
            if abs(d - R) <= Wd / 2:
                set_px(x, y, color)


def ellipse(cx, cy, rx, ry, color):
    CX, CY, RX, RY = cx * SS, cy * SS, rx * SS, ry * SS
    x0 = int(max(0, CX - RX - 1)); x1 = int(min(SW - 1, CX + RX + 1))
    y0 = int(max(0, CY - RY - 1)); y1 = int(min(SH - 1, CY + RY + 1))
    for y in range(y0, y1 + 1):
        t = (y - CY) / RY
        if abs(t) > 1:
            continue
        dx = RX * math.sqrt(1 - t * t)
        xa = int(max(0, CX - dx)); xb = int(min(SW - 1, CX + dx))
        FB[y][xa * 3:(xb + 1) * 3] = bytes(color) * (xb + 1 - xa)


def poly(points, color):
    pts = [(x * SS, y * SS) for x, y in points]
    ys = [p[1] for p in pts]
    y0 = int(max(0, min(ys))); y1 = int(min(SH - 1, max(ys)))
    n = len(pts)
    for y in range(y0, y1 + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            xa, ya = pts[i]; xb, yb = pts[(i + 1) % n]
            if (ya <= yc < yb) or (yb <= yc < ya):
                xs.append(xa + (yc - ya) * (xb - xa) / (yb - ya))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            xa = int(max(0, xs[i])); xb = int(min(SW - 1, xs[i + 1]))
            if xb >= xa:
                FB[y][xa * 3:(xb + 1) * 3] = bytes(color) * (xb + 1 - xa)


def line(x0, y0, x1, y1, wdt, color):
    """Capsule line with round caps, in 1024-space coords."""
    X0, Y0, X1, Y1 = x0 * SS, y0 * SS, x1 * SS, y1 * SS
    Wd = wdt * SS / 2.0
    bx0 = int(max(0, min(X0, X1) - Wd - 1)); bx1 = int(min(SW - 1, max(X0, X1) + Wd + 1))
    by0 = int(max(0, min(Y0, Y1) - Wd - 1)); by1 = int(min(SH - 1, max(Y0, Y1) + Wd + 1))
    dx, dy = X1 - X0, Y1 - Y0
    L2 = dx * dx + dy * dy
    for y in range(by0, by1 + 1):
        for x in range(bx0, bx1 + 1):
            if L2 == 0:
                d = math.hypot(x - X0, y - Y0)
            else:
                t = ((x - X0) * dx + (y - Y0) * dy) / L2
                t = 0.0 if t < 0 else (1.0 if t > 1 else t)
                d = math.hypot(x - (X0 + t * dx), y - (Y0 + t * dy))
            if d <= Wd:
                set_px(x, y, color)


def arc_line(cx, cy, r, a0, a1, wdt, color, steps=None):
    if steps is None:
        steps = max(8, int(abs(a1 - a0) / 6))
    pts = []
    for i in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * i / steps)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    for i in range(len(pts) - 1):
        line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], wdt, color)


def rrect(x0, y0, x1, y1, rad, color):
    rect(x0 + rad, y0, x1 - rad, y1, color)
    rect(x0, y0 + rad, x1, y1 - rad, color)
    disc(x0 + rad, y0 + rad, rad, color)
    disc(x1 - rad, y0 + rad, rad, color)
    disc(x0 + rad, y1 - rad, rad, color)
    disc(x1 - rad, y1 - rad, rad, color)


def glow(cx, cy, r, color, peak):
    CX, CY, R = cx * SS, cy * SS, r * SS
    x0 = int(max(0, CX - R)); x1 = int(min(SW - 1, CX + R))
    y0 = int(max(0, CY - R)); y1 = int(min(SH - 1, CY + R))
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            d = math.hypot(x - CX, y - CY) / R
            if d < 1:
                blend_px(x, y, color, peak * (1 - d) * (1 - d))


def star5(cx, cy, r, color, rot=-90):
    pts = []
    for i in range(10):
        ang = math.radians(rot + i * 36)
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    poly(pts, color)


class LCG:
    def __init__(self, seed):
        self.s = seed & 0x7FFFFFFF

    def next(self):
        self.s = (1103515245 * self.s + 12345) & 0x7FFFFFFF
        return self.s / 0x7FFFFFFF


def downsample_png(path):
    out_rows = []
    for y in range(H):
        r0 = FB[2 * y]; r1 = FB[2 * y + 1]
        row = bytearray(W * 3)
        for x in range(W):
            i2 = 2 * x * 3; o = x * 3
            for c in range(3):
                row[o + c] = (r0[i2 + c] + r0[i2 + 3 + c] + r1[i2 + c] + r1[i2 + 3 + c] + 2) // 4
        out_rows.append(bytes(row))
    raw = b"".join(b"\x00" + r for r in out_rows)
    comp = zlib.compress(raw, 9)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", comp)
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ---------------------------------------------------------------- font
# Hand-drawn stroke grotesque. Glyph space: x 0..~7 wide, y 0 (baseline)
# .. 10 (cap top), y UP. Strokes are capsules, so type stays crisp and
# even at headline sizes and at thumbnail scale.
def _arc(cx, cy, rx, ry, a0, a1, n=10):
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((round(cx + rx * math.cos(a), 2), round(cy + ry * math.sin(a), 2)))
    return pts


GLYPHS = {
    'A': (7.2, [[(0, 0), (3.6, 10), (7.2, 0)], [(1.35, 3.7), (5.85, 3.7)]]),
    'B': (6.6, [[(0, 0), (0, 10)], [(0, 10), (2.9, 10), (4.4, 9.1), (4.7, 7.6), (4.4, 6.0), (2.9, 5.2), (0, 5.2)],
                [(0, 5.2), (3.2, 5.2), (5.0, 4.4), (5.3, 2.6), (5.0, 0.9), (3.2, 0), (0, 0)]]),
    'C': (7.0, [_arc(3.5, 5, 3.4, 5, 48, 312, 14)]),
    'D': (7.0, [[(0, 0), (0, 10)], [(0, 10), (3.0, 10), (5.3, 8.6), (6.1, 5), (5.3, 1.4), (3.0, 0), (0, 0)]]),
    'E': (6.4, [[(6.4, 10), (0, 10), (0, 0), (6.4, 0)], [(0, 5.2), (5.2, 5.2)]]),
    'F': (6.2, [[(6.2, 10), (0, 10), (0, 0)], [(0, 5.2), (5.0, 5.2)]]),
    'G': (7.2, [_arc(3.5, 5, 3.5, 5, 48, 302, 14), [(7.1, 4.3), (4.0, 4.3), (4.0, 4.3), (7.1, 4.3), (7.1, 1.0)]]),
    'H': (7.2, [[(0, 0), (0, 10)], [(7.2, 0), (7.2, 10)], [(0, 5.1), (7.2, 5.1)]]),
    'I': (3.6, [[(1.8, 0), (1.8, 10)], [(0.1, 10), (3.5, 10)], [(0.1, 0), (3.5, 0)]]),
    'J': (6.4, [[(0.2, 10), (6.4, 10)], [(5.2, 10), (5.2, 2.4), (4.4, 0.7), (2.9, 0), (1.3, 0.5), (0.4, 1.9)]]),
    'K': (7.0, [[(0, 0), (0, 10)], [(6.9, 10), (0.7, 4.7)], [(1.9, 5.7), (7.0, 0)]]),
    'L': (6.2, [[(0, 10), (0, 0), (6.2, 0)]]),
    'M': (8.0, [[(0, 0), (0, 10), (4.0, 4.0), (8.0, 10), (8.0, 0)]]),
    'N': (7.4, [[(0, 0), (0, 10), (7.4, 0), (7.4, 10)]]),
    'O': (7.6, [_arc(3.8, 5, 3.7, 5, 0, 360, 18)]),
    'P': (6.6, [[(0, 0), (0, 10)], [(0, 10), (3.2, 10), (5.1, 9.0), (5.5, 7.4), (5.1, 5.7), (3.2, 4.7), (0, 4.7)]]),
    'Q': (7.6, [_arc(3.8, 5, 3.7, 5, 0, 360, 18), [(4.5, 2.7), (7.3, 0)]]),
    'R': (6.8, [[(0, 0), (0, 10)], [(0, 10), (3.2, 10), (5.1, 9.0), (5.5, 7.4), (5.1, 5.7), (3.2, 4.7), (0, 4.7)],
                [(2.9, 4.7), (6.9, 0)]]),
    'S': (6.6, [[(6.3, 8.7), (4.7, 10), (2.4, 9.7), (0.9, 7.9), (1.2, 6.3), (2.9, 5.2), (4.7, 4.3), (6.1, 3.1),
                 (6.2, 1.4), (4.7, 0.2), (2.4, 0), (0.7, 1.1)]]),
    'T': (7.0, [[(0, 10), (7.0, 10)], [(3.5, 10), (3.5, 0)]]),
    'U': (7.4, [[(0, 10), (0, 2.7), (0.8, 0.8), (2.3, 0), (5.1, 0), (6.6, 0.8), (7.4, 2.7), (7.4, 10)]]),
    'V': (7.2, [[(0, 10), (3.6, 0), (7.2, 10)]]),
    'W': (9.4, [[(0, 10), (1.7, 0), (4.7, 6.6), (7.7, 0), (9.4, 10)]]),
    'X': (7.0, [[(0, 0), (7.0, 10)], [(0, 10), (7.0, 0)]]),
    'Y': (7.0, [[(0, 10), (3.5, 5.3), (7.0, 10)], [(3.5, 5.3), (3.5, 0)]]),
    'Z': (6.8, [[(0, 10), (6.8, 10), (0, 0), (6.8, 0)]]),
    '0': (7.2, [_arc(3.6, 5, 3.3, 5, 0, 360, 18)]),
    '1': (6.4, [[(1.5, 8.1), (4.3, 10), (4.3, 0)], [(1.3, 0), (6.3, 0)]]),
    '2': (6.8, [[(0.8, 8.5), (2.3, 10), (4.7, 9.8), (5.9, 8.1), (5.4, 6.0), (0.7, 0), (6.8, 0)]]),
    '3': (6.6, [[(0.8, 9.3), (3.2, 10), (5.1, 9.1), (5.5, 7.5), (4.6, 5.9), (2.9, 5.3)],
                [(2.9, 5.3), (4.9, 4.5), (5.7, 2.7), (5.0, 0.9), (3.0, 0), (0.8, 0.8)]]),
    '4': (7.2, [[(4.7, 0), (4.7, 10), (0.4, 3.4)], [(0.4, 3.4), (6.9, 3.4)]]),
    '5': (6.6, [[(6.5, 10), (1.3, 10), (1.0, 6.1), (3.1, 6.7), (5.1, 5.7), (5.9, 3.5), (4.9, 1.1), (2.7, 0), (0.8, 0.9)]]),
    '6': (6.8, [[(6.3, 9.1), (3.7, 10.1), (1.5, 7.7), (0.7, 3.7), (1.6, 1.1), (3.5, 0), (5.3, 0.9), (6.1, 2.9),
                 (5.3, 4.9), (3.3, 5.5), (1.0, 4.3)]]),
    '7': (6.8, [[(0.6, 10), (6.8, 10), (3.3, 0)]]),
    '8': (6.8, [_arc(3.4, 7.5, 2.6, 2.5, 0, 360, 14), _arc(3.4, 2.7, 3.0, 2.7, 0, 360, 14)]),
    '9': (6.8, [[(0.7, 0.9), (3.3, 0), (5.5, 2.3), (6.3, 6.3), (5.4, 9.0), (3.6, 10), (1.8, 9.1), (1.0, 7.1),
                 (1.9, 5.2), (3.9, 4.6), (6.1, 5.9)]]),
    '.': (3.2, [[(1.6, 0.6), (1.6, 0.6)]]),
    ',': (3.2, [[(1.9, 2.0), (1.2, 0.1)]]),
    ':': (3.2, [[(1.6, 7.6), (1.6, 7.6)], [(1.6, 0.6), (1.6, 0.6)]]),
    '-': (5.4, [[(0.6, 5), (4.8, 5)]]),
    "'": (2.8, [[(1.6, 10), (1.1, 7.9)]]),
    '&': (7.4, [_arc(3.2, 7.9, 1.9, 2.0, 0, 330, 10),
                [(4.4, 6.4), (1.1, 4.4), (0.7, 2.2), (2.0, 0.5), (4.3, 0), (7.0, 1.7)]]),
    '$': (6.8, [[(6.4, 8.7), (4.8, 10), (2.5, 9.7), (1.0, 7.9), (1.3, 6.3), (3.0, 5.2), (4.8, 4.3), (6.2, 3.1),
                 (6.3, 1.4), (4.8, 0.2), (2.5, 0), (0.8, 1.1)], [(3.4, -0.9), (3.4, 10.9)]]),
    '!': (3.2, [[(1.6, 10), (1.6, 2.9)], [(1.6, 0.6), (1.6, 0.6)]]),
    '+': (6.4, [[(3.2, 2.4), (3.2, 7.6)], [(0.6, 5), (5.8, 5)]]),
    '/': (5.6, [[(0.8, 0), (4.8, 10)]]),
    '(': (4.6, [_arc(4.4, 5, 2.8, 5.6, 115, 245, 8)]),
    ')': (4.6, [_arc(0.2, 5, 2.8, 5.6, -65, 65, 8)]),
    '%': (9.0, [_arc(1.9, 7.6, 1.7, 2.2, 0, 360, 10), _arc(7.1, 2.4, 1.7, 2.2, 0, 360, 10), [(7.6, 10), (1.4, 0)]]),
    ' ': (3.8, []),
}


def glyph_w(ch):
    return GLYPHS.get(ch, GLYPHS[' '])[0]


def text_w(text, size, tracking=0.6):
    if not text:
        return 0
    s = size / 10.0
    w = sum(glyph_w(c) for c in text) * s + tracking * s * (len(text) - 1)
    return w


def draw_text(text, cx, top, size, color, weight=1.5, tracking=0.6, align='center'):
    """Draw text; `top` is the y of the cap top in 1024-space."""
    s = size / 10.0
    total = text_w(text, size, tracking)
    if align == 'center':
        x = cx - total / 2
    elif align == 'left':
        x = cx
    else:
        x = cx - total
    wdt = weight * s
    for ch in text:
        gw, strokes = GLYPHS.get(ch, GLYPHS[' '])
        for stroke in strokes:
            pts = [(x + px * s, top + (10 - py) * s) for px, py in stroke]
            for i in range(len(pts) - 1):
                line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], wdt, color)
            if len(pts) == 1:
                line(pts[0][0], pts[0][1], pts[0][0], pts[0][1], wdt, color)
        x += (gw + tracking) * s
    return total


def fit_size(text, max_w, start, tracking=0.6):
    """Largest size <= start at which the text fits max_w."""
    size = start
    while size > 8 and text_w(text, size, tracking) > max_w:
        size -= 1
    return size


# ---------------------------------------------------------------- palette
NAVY = (18, 36, 58)
NAVY2 = (27, 54, 84)
INK = (24, 32, 44)
CREAM = (246, 239, 222)
PAPER = (244, 236, 217)
GOLD = (201, 162, 39)
GOLD_L = (227, 185, 62)
GOLD_PALE = (240, 214, 130)
RED = (166, 58, 46)
RED_D = (128, 40, 32)
TEAL = (46, 125, 116)
SKIN = (222, 168, 128)
WHITE = (252, 252, 250)
GREY = (120, 130, 140)


# ---------------------------------------------------------------- scenes
def scene_senate(x, y, w, h):
    vgrad(x, y, x + w, y + h, (233, 224, 198), (206, 188, 148))
    # wall columns
    for fx in (0.06, 0.90):
        cxp = x + w * fx
        rect(cxp, y + h * 0.06, cxp + w * 0.045, y + h * 0.72, (196, 178, 138))
        rect(cxp - w * 0.008, y + h * 0.04, cxp + w * 0.061, y + h * 0.09, (176, 154, 110))
    # seal on wall
    disc(x + w * 0.5, y + h * 0.24, w * 0.075, GOLD)
    disc(x + w * 0.5, y + h * 0.24, w * 0.058, (176, 140, 60))
    star5(x + w * 0.5, y + h * 0.24, w * 0.042, GOLD_PALE)
    # dais desk
    desk_y = y + h * 0.60
    hgrad(x + w * 0.06, desk_y, x + w * 0.94, desk_y + h * 0.13, (122, 84, 50), (100, 66, 38))
    rect(x + w * 0.06, desk_y, x + w * 0.94, desk_y + h * 0.025, (150, 108, 66))
    # nameplates + mics on dais
    for fx in (0.30, 0.62):
        rect(x + w * fx, desk_y + h * 0.045, x + w * (fx + 0.09), desk_y + h * 0.085, CREAM)
        line(x + w * (fx + 0.045), desk_y + h * 0.04, x + w * (fx + 0.045), desk_y - h * 0.05, 1.6, INK)
        disc(x + w * (fx + 0.045), desk_y - h * 0.055, w * 0.008, INK)
    # witness table (front)
    tab_y = y + h * 0.84
    rect(x + w * 0.14, tab_y, x + w * 0.86, tab_y + h * 0.075, (92, 62, 36))
    # two witness chairs behind the table, backs rising above it
    for fx in (0.335, 0.575):
        cxp = x + w * fx
        rrect(cxp, tab_y - h * 0.30, cxp + w * 0.11, tab_y + h * 0.01, 3, (74, 50, 30))
        rrect(cxp + w * 0.012, tab_y - h * 0.283, cxp + w * 0.098, tab_y - h * 0.02, 2, (96, 66, 40))
        line(x + w * (fx + 0.055), tab_y - h * 0.01, x + w * (fx + 0.055), tab_y - h * 0.10, 1.6, INK)
        disc(x + w * (fx + 0.055), tab_y - h * 0.105, w * 0.008, INK)
    # black leather jacket draped over the left chair back (Huang's jacket)
    jx = x + w * 0.335
    poly([(jx - w * 0.016, tab_y - h * 0.30), (jx + w * 0.126, tab_y - h * 0.30),
          (jx + w * 0.142, tab_y - h * 0.15), (jx + w * 0.088, tab_y - h * 0.19),
          (jx + w * 0.055, tab_y - h * 0.105), (jx + w * 0.022, tab_y - h * 0.19),
          (jx - w * 0.026, tab_y - h * 0.15)], (26, 26, 30))
    line(jx + w * 0.055, tab_y - h * 0.30, jx + w * 0.055, tab_y - h * 0.19, 1.4, (70, 70, 78))
    # floor
    rect(x, y + h * 0.915, x + w, y + h, (168, 142, 104))


def scene_handshake(x, y, w, h):
    vgrad(x, y, x + w, y + h, (216, 226, 232), (188, 200, 210))

    # flags: US, EU, UA on stands behind the table
    def flag(fx, kind):
        px = x + w * fx
        top = y + h * 0.10
        line(px, top, px, y + h * 0.62, 2.2, INK)
        fw, fh = w * 0.20, h * 0.26
        if kind == 'us':
            for i in range(7):
                c = (178, 52, 52) if i % 2 == 0 else WHITE
                rect(px, top + fh * i / 7, px + fw, top + fh * (i + 1) / 7, c)
            rect(px, top, px + fw * 0.45, top + fh * 4 / 7, (40, 56, 120))
            for r_ in range(3):
                for c_ in range(4):
                    disc(px + fw * (0.08 + 0.11 * c_), top + fh * (0.09 + 0.16 * r_), 1.3, WHITE)
        elif kind == 'eu':
            rect(px, top, px + fw, top + fh, (38, 66, 150))
            for i in range(8):
                a = math.radians(i * 45)
                star5(px + fw / 2 + fw * 0.30 * math.cos(a), top + fh / 2 + fh * 0.30 * math.sin(a), 2.6, GOLD_L)
        else:
            rect(px, top, px + fw, top + fh / 2, (52, 110, 180))
            rect(px, top + fh / 2, px + fw, top + fh, (240, 200, 60))
        rect(px, top, px + fw, top + 2, (150, 150, 150))

    flag(0.13, 'us'); flag(0.42, 'eu'); flag(0.71, 'ua')
    # table
    tab_y = y + h * 0.66
    ellipse(x + w * 0.5, tab_y, w * 0.40, h * 0.085, (112, 78, 46))
    ellipse(x + w * 0.5, tab_y - h * 0.012, w * 0.40, h * 0.085, (140, 102, 62))
    rect(x + w * 0.44, tab_y + h * 0.03, x + w * 0.56, y + h * 0.94, (96, 66, 38))
    # arms + handshake
    hy = y + h * 0.44
    line(x + w * 0.06, hy + h * 0.10, x + w * 0.435, hy, h * 0.085, NAVY2)
    line(x + w * 0.94, hy + h * 0.10, x + w * 0.565, hy, h * 0.085, (64, 70, 80))
    rect(x + w * 0.395, hy - h * 0.045, x + w * 0.445, hy + h * 0.045, WHITE)
    rect(x + w * 0.555, hy - h * 0.045, x + w * 0.605, hy + h * 0.045, WHITE)
    ellipse(x + w * 0.485, hy, w * 0.045, h * 0.055, SKIN)
    ellipse(x + w * 0.525, hy + h * 0.012, w * 0.042, h * 0.052, (205, 148, 108))
    for i in range(3):
        line(x + w * (0.462 + 0.018 * i), hy + h * 0.048, x + w * (0.470 + 0.018 * i), hy + h * 0.085, 2.0, SKIN)


def scene_warship(x, y, w, h):
    vgrad(x, y, x + w, y + h * 0.58, (168, 192, 206), (206, 220, 226))
    vgrad(x, y + h * 0.58, x + w, y + h, (62, 106, 138), (36, 76, 104))
    rect(x, y + h * 0.545, x + w, y + h * 0.575, (140, 158, 168))
    ship_y = y + h * 0.60
    hull = [(x + w * 0.10, ship_y), (x + w * 0.86, ship_y), (x + w * 0.80, ship_y + h * 0.10),
            (x + w * 0.20, ship_y + h * 0.10)]
    poly(hull, (88, 98, 110))
    rect(x + w * 0.10, ship_y - h * 0.012, x + w * 0.86, ship_y, (70, 80, 92))
    # superstructure
    rect(x + w * 0.34, ship_y - h * 0.13, x + w * 0.58, ship_y - h * 0.01, (104, 114, 126))
    rect(x + w * 0.40, ship_y - h * 0.21, x + w * 0.52, ship_y - h * 0.13, (96, 106, 118))
    line(x + w * 0.46, ship_y - h * 0.21, x + w * 0.46, ship_y - h * 0.33, 2.4, (70, 78, 88))
    arc_line(x + w * 0.46, ship_y - h * 0.335, w * 0.028, 180, 360, 2.0, (70, 78, 88))
    rect(x + w * 0.60, ship_y - h * 0.09, x + w * 0.70, ship_y - h * 0.01, (98, 108, 120))
    # gun turret fore
    poly([(x + w * 0.16, ship_y - h * 0.01), (x + w * 0.28, ship_y - h * 0.01),
          (x + w * 0.26, ship_y - h * 0.055), (x + w * 0.19, ship_y - h * 0.055)], (80, 90, 102))
    line(x + w * 0.20, ship_y - h * 0.05, x + w * 0.10, ship_y - h * 0.075, 3.0, (70, 78, 88))
    # smoke plume
    for i, (dx, dy, rr) in enumerate([(0.66, -0.16, 0.030), (0.70, -0.22, 0.042), (0.75, -0.28, 0.055), (0.81, -0.34, 0.068)]):
        disc(x + w * dx, ship_y + h * dy, w * rr, (168, 172, 176) if i % 2 else (188, 190, 192))
    # explosion at the bow + splash, kept inside the panel
    star5(x + w * 0.865, ship_y + h * 0.015, w * 0.046, (240, 160, 50))
    star5(x + w * 0.865, ship_y + h * 0.015, w * 0.026, (250, 205, 90))
    ellipse(x + w * 0.845, ship_y + h * 0.115, w * 0.055, h * 0.024, (225, 238, 244))
    # drone quadcopter, top-left
    dx_, dy_ = x + w * 0.20, y + h * 0.16
    line(dx_ - w * 0.068, dy_ - h * 0.056, dx_ + w * 0.068, dy_ + h * 0.056, 3.6, INK)
    line(dx_ - w * 0.068, dy_ + h * 0.056, dx_ + w * 0.068, dy_ - h * 0.056, 3.6, INK)
    for sx, sy in [(-0.068, -0.056), (0.068, -0.056), (-0.068, 0.056), (0.068, 0.056)]:
        ellipse(dx_ + w * sx, dy_ + h * sy, w * 0.037, h * 0.020, (50, 56, 64))
    disc(dx_, dy_, w * 0.024, (36, 40, 46))
    disc(dx_, dy_ + h * 0.042, w * 0.009, RED)
    # dashed dive path from drone toward the ship
    for i in range(6):
        t = i / 6
        px = dx_ + (x + w * 0.86 - dx_) * t
        py = dy_ + (ship_y - dy_) * t + math.sin(t * math.pi) * -h * 0.05
        if i % 2 == 0:
            disc(px, py, 2.0, (90, 100, 110))
    # wave dashes
    rng = LCG(42)
    for i in range(9):
        wx = x + w * (0.06 + 0.10 * i) + rng.next() * 6
        wy = y + h * (0.78 + 0.09 * (i % 3))
        line(wx, wy, wx + w * 0.045, wy, 2.0, (190, 218, 232))


def scene_radar(x, y, w, h):
    vgrad(x, y, x + w, y + h * 0.66, (246, 205, 140), (238, 160, 105))
    disc(x + w * 0.80, y + h * 0.30, w * 0.075, (250, 224, 160))
    disc(x + w * 0.80, y + h * 0.30, w * 0.058, (252, 236, 180))
    # dunes
    poly([(x, y + h * 0.66), (x + w * 0.35, y + h * 0.60), (x + w * 0.7, y + h * 0.68),
          (x + w, y + h * 0.63), (x + w, y + h), (x, y + h)], (222, 184, 130))
    poly([(x, y + h * 0.78), (x + w * 0.4, y + h * 0.72), (x + w, y + h * 0.80),
          (x + w, y + h), (x, y + h)], (206, 164, 108))
    # radar dome on a pedestal (right)
    bx, by = x + w * 0.66, y + h * 0.86
    rect(bx - w * 0.085, by - h * 0.20, bx + w * 0.085, by, (120, 116, 110))
    rect(bx - w * 0.020, by - h * 0.16, bx + w * 0.020, by, (88, 84, 80))
    pts = []
    for i in range(15):
        a = math.radians(180 * i / 14)
        pts.append((bx + w * 0.115 * math.cos(a), by - h * 0.20 - h * 0.30 * math.sin(a)))
    poly(pts + [(bx + w * 0.115, by - h * 0.20)], (240, 240, 236))
    line(bx - w * 0.115, by - h * 0.20, bx + w * 0.115, by - h * 0.20, 3, (200, 200, 196))
    # dome seams + beacon
    arc_line(bx, by - h * 0.205, w * 0.062, 180, 360, 1.8, (198, 198, 192))
    line(bx, by - h * 0.20, bx, by - h * 0.495, 1.8, (198, 198, 192))
    disc(bx, by - h * 0.505, w * 0.009, RED)
    # radar dish on a pole (left), face turned up-left toward the missile
    px, py = x + w * 0.20, y + h * 0.86
    line(px, py, px, py - h * 0.30, 4.5, (90, 88, 84))
    line(px - w * 0.05, py, px, py - h * 0.15, 3, (90, 88, 84))
    line(px + w * 0.05, py, px, py - h * 0.15, 3, (90, 88, 84))
    dcx, dcy = px + w * 0.01, py - h * 0.36
    dang = math.radians(-125)
    dxu, dyu = math.cos(dang), math.sin(dang)
    R = w * 0.105
    bowl = []
    for i in range(13):
        a = dang + math.radians(-68 + 136 * i / 12)
        bowl.append((dcx + dxu * R * 0.38 + R * 0.72 * math.cos(a),
                     dcy + dyu * R * 0.38 + R * 0.72 * math.sin(a)))
    for i in range(len(bowl) - 1):
        line(bowl[i][0], bowl[i][1], bowl[i + 1][0], bowl[i + 1][1], 5.0, (70, 68, 64))
    fx = dcx + dxu * R * 1.05; fy = dcy + dyu * R * 1.05
    line(dcx, dcy, fx, fy, 2.6, (70, 68, 64))
    disc(fx, fy, w * 0.011, RED)
    # missile trail: a solid pale arc from top-left down to the dome
    pts = []
    for i in range(21):
        t = i / 20
        mx = x + w * (0.05 + 0.485 * t)
        my = y + h * (0.08 + 0.50 * t * t + 0.05 * t)
        pts.append((mx, my))
    for i in range(len(pts) - 1):
        line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], 3.4, (252, 246, 232))
    # the missile itself at the end of the trail, flame at its tail
    ex, ey = pts[-1]
    line(ex - w * 0.062, ey - h * 0.088, ex, ey, 8.5, (240, 240, 236))
    poly([(ex - w * 0.088, ey - h * 0.115), (ex - w * 0.056, ey - h * 0.052), (ex - w * 0.104, ey - h * 0.042)], (240, 130, 50))
    disc(ex - w * 0.072, ey - h * 0.082, w * 0.013, (250, 180, 70))
    # burst + smoke at the dome's shoulder
    star5(bx - w * 0.115, by - h * 0.30, w * 0.046, (246, 170, 60))
    star5(bx - w * 0.115, by - h * 0.30, w * 0.024, (252, 214, 110))
    disc(bx - w * 0.085, by - h * 0.40, w * 0.030, (176, 168, 158))
    disc(bx - w * 0.045, by - h * 0.45, w * 0.038, (190, 182, 172))


def scene_hack(x, y, w, h):
    vgrad(x, y, x + w, y + h, (18, 24, 36), (10, 14, 22))
    # monitor
    mx0, my0, mx1, my1 = x + w * 0.09, y + h * 0.07, x + w * 0.91, y + h * 0.72
    rrect(mx0 - 4, my0 - 4, mx1 + 4, my1 + 4, 8, (52, 60, 72))
    vgrad(mx0, my0, mx1, my1, (16, 52, 78), (10, 32, 52))
    # call top bar with record dot
    rect(mx0, my0, mx1, my0 + h * 0.085, (8, 22, 36))
    disc(mx0 + w * 0.045, my0 + h * 0.042, w * 0.012, RED)
    rect(mx0 + w * 0.085, my0 + h * 0.028, mx0 + w * 0.30, my0 + h * 0.056, (70, 110, 140))
    # masked face in the call, centre
    cx, cy = x + w * 0.5, y + h * 0.40
    ellipse(cx, cy - h * 0.02, w * 0.155, h * 0.235, (24, 24, 28))
    ellipse(cx, cy, w * 0.105, h * 0.165, (238, 236, 230))
    ellipse(cx - w * 0.042, cy - h * 0.035, w * 0.020, h * 0.020, (20, 20, 24))
    ellipse(cx + w * 0.042, cy - h * 0.035, w * 0.020, h * 0.020, (20, 20, 24))
    arc_line(cx, cy + h * 0.075, w * 0.045, 20, 160, 2.6, (120, 118, 112))
    line(cx, cy - h * 0.10, cx, cy + h * 0.01, 2.2, (200, 198, 190))
    # self-view mini window
    sx0, sy0 = mx1 - w * 0.235, my0 + h * 0.115
    rrect(sx0, sy0, sx0 + w * 0.19, sy0 + h * 0.155, 4, (30, 44, 60))
    disc(sx0 + w * 0.095, sy0 + h * 0.062, w * 0.026, (140, 150, 160))
    ellipse(sx0 + w * 0.095, sy0 + h * 0.148, w * 0.048, h * 0.045, (140, 150, 160))
    # stand + desk
    rect(x + w * 0.465, my1 + 4, x + w * 0.535, y + h * 0.82, (52, 60, 72))
    rect(x + w * 0.30, y + h * 0.82, x + w * 0.70, y + h * 0.845, (52, 60, 72))
    rect(x, y + h * 0.845, x + w, y + h * 0.86, (30, 36, 48))
    # gold coins spilling from the screen
    coins = [(0.30, 0.845, 0.030), (0.38, 0.875, 0.034), (0.47, 0.855, 0.028), (0.56, 0.885, 0.036),
             (0.65, 0.85, 0.030), (0.71, 0.885, 0.027), (0.42, 0.915, 0.030), (0.60, 0.92, 0.032),
             (0.50, 0.90, 0.026), (0.335, 0.905, 0.024)]
    for fx, fy, fr in coins:
        disc(x + w * fx, y + h * fy, w * fr, GOLD)
        disc_ring(x + w * fx, y + h * fy, w * fr * 0.68, 1.6, (160, 124, 30))
        star5(x + w * fx, y + h * fy, w * fr * 0.4, GOLD_PALE)


def scene_kane(x, y, w, h):
    vgrad(x, y, x + w, y + h * 0.62, (24, 48, 84), (38, 78, 122))
    glow(x + w * 0.08, y + h * 0.05, w * 0.20, (255, 240, 190), 0.55)
    glow(x + w * 0.92, y + h * 0.05, w * 0.20, (255, 240, 190), 0.55)
    # crowd confetti
    rng = LCG(1234)
    cols = [(240, 200, 60), (230, 90, 80), (120, 180, 230), (240, 240, 240), (150, 220, 150)]
    for i in range(150):
        cxx = x + rng.next() * w
        cyy = y + h * (0.06 + rng.next() * 0.34)
        disc(cxx, cyy, 1.7 + rng.next() * 1.4, cols[int(rng.next() * 5) % 5])
    # pitch with mowing stripes
    vgrad(x, y + h * 0.62, x + w, y + h, (52, 138, 66), (36, 104, 50))
    for i in range(4):
        if i % 2 == 0:
            rect(x + w * i / 4, y + h * 0.62, x + w * (i + 1) / 4, y + h, (58, 148, 72))
    line(x, y + h * 0.62, x + w, y + h * 0.62, 2.4, (220, 240, 220))
    # the player, arms raised
    cx = x + w * 0.5
    gy = y + h * 0.90
    line(cx - w * 0.012, gy - h * 0.16, cx - w * 0.045, gy - h * 0.015, w * 0.020, SKIN)
    line(cx + w * 0.012, gy - h * 0.16, cx + w * 0.050, gy - h * 0.015, w * 0.020, SKIN)
    rect(cx - w * 0.055, gy - h * 0.018, cx - w * 0.028, gy, WHITE)
    rect(cx + w * 0.038, gy - h * 0.018, cx + w * 0.066, gy, WHITE)
    poly([(cx - w * 0.052, gy - h * 0.27), (cx + w * 0.052, gy - h * 0.27),
          (cx + w * 0.045, gy - h * 0.155), (cx + w * 0.008, gy - h * 0.155),
          (cx, gy - h * 0.20), (cx - w * 0.008, gy - h * 0.155),
          (cx - w * 0.045, gy - h * 0.155)], WHITE)
    # shirt with the red cross of St George
    rrect(cx - w * 0.055, gy - h * 0.50, cx + w * 0.055, gy - h * 0.26, 5, WHITE)
    rect(cx - w * 0.011, gy - h * 0.50, cx + w * 0.011, gy - h * 0.26, (200, 40, 46))
    rect(cx - w * 0.055, gy - h * 0.395, cx + w * 0.055, gy - h * 0.365, (200, 40, 46))
    # arms up
    line(cx - w * 0.048, gy - h * 0.47, cx - w * 0.115, gy - h * 0.635, w * 0.021, WHITE)
    line(cx - w * 0.115, gy - h * 0.635, cx - w * 0.128, gy - h * 0.665, w * 0.016, SKIN)
    line(cx + w * 0.048, gy - h * 0.47, cx + w * 0.115, gy - h * 0.635, w * 0.021, WHITE)
    line(cx + w * 0.115, gy - h * 0.635, cx + w * 0.128, gy - h * 0.665, w * 0.016, SKIN)
    disc(cx - w * 0.130, gy - h * 0.672, w * 0.013, SKIN)
    disc(cx + w * 0.130, gy - h * 0.672, w * 0.013, SKIN)
    # head
    disc(cx, gy - h * 0.565, w * 0.036, SKIN)
    arc_line(cx, gy - h * 0.578, w * 0.036, 180, 360, 3.4, (60, 44, 30))
    # ball at his feet
    disc(cx + w * 0.13, gy - h * 0.03, w * 0.030, WHITE)
    disc(cx + w * 0.13, gy - h * 0.03, w * 0.012, INK)
    disc(cx + w * 0.115, gy - h * 0.048, w * 0.007, INK)
    disc(cx + w * 0.146, gy - h * 0.045, w * 0.007, INK)
    # gold stars
    star5(x + w * 0.80, y + h * 0.16, w * 0.045, GOLD_L)
    star5(x + w * 0.80, y + h * 0.16, w * 0.024, GOLD_PALE)
    star5(x + w * 0.16, y + h * 0.22, w * 0.026, GOLD_PALE)


SCENES = [scene_senate, scene_handshake, scene_warship, scene_radar, scene_hack, scene_kane]
LABELS = [("SENATE SUMMONS", "HUANG & LUTNICK"),
          ("ZELENSKY MEETS", "US ENVOYS"),
          ("DRONE HITS", "RUSSIAN WARSHIP"),
          ("IRAN CLAIMS STRIKE", "ON US RADAR"),
          ("FBI: N. KOREA", "$400M CRYPTO HACK"),
          ("KANE BREAKS", "ENGLAND CAPS RECORD")]


# ---------------------------------------------------------------- layout
FOOTER_LINE = "US REPORTS RECORD 483,200 DEPORTATIONS IN 2026"


def panel(px, py, pw, ph, idx):
    scene_h = ph - 76
    rect(px - 2, py - 2, px + pw + 2, py + ph + 2, NAVY)
    SCENES[idx](px, py, pw, scene_h)
    rect(px, py + scene_h, px + pw, py + scene_h + 3, GOLD)
    rect(px, py + scene_h + 3, px + pw, py + ph, NAVY)
    l1, l2 = LABELS[idx]
    sz = min(fit_size(l1, pw - 22, 28), fit_size(l2, pw - 22, 28))
    draw_text(l1, px + pw / 2, py + scene_h + 13, sz, CREAM, 1.55)
    draw_text(l2, px + pw / 2, py + scene_h + 13 + sz + 7, sz, CREAM, 1.55)
    # index badge
    disc(px + 17, py + 17, 13.5, GOLD)
    draw_text(str(idx + 1), px + 17, py + 10.5, 19, NAVY, 1.7)


def page_frame():
    """Page frame: navy outer rule, gold inner rule."""
    rect(8, 8, W - 8, 14, NAVY); rect(8, H - 14, W - 8, H - 8, NAVY)
    rect(8, 8, 14, H - 8, NAVY); rect(W - 14, 8, W - 8, H - 8, NAVY)
    rect(17, 17, W - 17, 19, GOLD); rect(17, H - 19, W - 17, H - 17, GOLD)
    rect(17, 17, 19, H - 17, GOLD); rect(W - 19, 17, W - 17, H - 17, GOLD)


def render():
    fill_all(PAPER)
    page_frame()
    # masthead
    draw_text("THE DAY IN ONE PAGE", 512, 30, 22, (150, 116, 40), 1.5, tracking=2.8)
    draw_text("THE WORLD TODAY", 512, 64, 84, NAVY, 1.6, tracking=0.4)
    # date chip
    chip_w = text_w("FRIDAY 13 NOVEMBER 2026", 27, 1.1) + 44
    rrect(512 - chip_w / 2, 164, 512 + chip_w / 2, 200, 17, NAVY)
    draw_text("FRIDAY 13 NOVEMBER 2026", 512, 170, 27, GOLD_PALE, 1.5, tracking=1.1)
    rect(30, 212, 994, 214.5, GOLD)
    # story grid, 2 rows of 3
    pw, ph, gap, mx = 312, 322, 14, 30
    y1 = 226
    for i in range(6):
        px = mx + (pw + gap) * (i % 3)
        py = y1 + (ph + gap) * (i // 3)
        panel(px, py, pw, ph, i)
    # footer band: the seventh story
    fy = y1 + 2 * ph + gap + 14
    rect(30, fy, 994, 998, RED)
    rect(30, fy, 994, fy + 3, GOLD)
    star5(58, (fy + 998) / 2, 10, GOLD_L)
    star5(966, (fy + 998) / 2, 10, GOLD_L)
    fsize = fit_size(FOOTER_LINE, 850, 30)
    draw_text(FOOTER_LINE, 512, (fy + 998) / 2 - fsize / 2, fsize, WHITE, 1.55)


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    render()
    n = downsample_png(os.path.join(out_dir, "entry.png"))
    print("entry.png bytes:", n)


if __name__ == "__main__":
    main()
