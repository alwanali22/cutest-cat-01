"""Pip in a Box — cutest-cat v3 entry (make.fun cutest-cat-01).

A tiny grey-and-white kitten sits in an open cardboard box, one paw
raised, batting at a small orange butterfly fluttering just above its
nose. Big round bright eyes look up, mouth open in a happy smile.

Pure Python 3.13 stdlib only. Own rasterizer (2x supersampled span
fills + 2x2 box downsample) and own PNG encoder (zlib). Deterministic:
same bytes on every run, no network, no randomness, no clock.
Writes /output/entry.png (or $MAKEFUN_OUTPUT_DIR/entry.png).
"""
import math
import os
import struct
import zlib

W = 1024            # output size
SS = 2              # supersample factor
SW = W * SS         # supersampled width

# ---------------------------------------------------------------- canvas
buf = bytearray(SW * SW * 3)


def _set(x, y, c):
    if 0 <= x < SW and 0 <= y < SW:
        i = (y * SW + x) * 3
        buf[i] = c[0]
        buf[i + 1] = c[1]
        buf[i + 2] = c[2]


def span(y, x0, x1, c):
    """Fill one supersampled scanline from x0 to x1 (inclusive)."""
    if y < 0 or y >= SW:
        return
    x0 = max(0, int(math.floor(x0)))
    x1 = min(SW - 1, int(math.ceil(x1)))
    if x1 < x0:
        return
    i = (y * SW + x0) * 3
    n = x1 - x0 + 1
    row = bytes(c) * n
    buf[i:i + n * 3] = row


def disc(cx, cy, r, c):
    """Filled circle, centre (cx, cy), radius r (output-pixel units)."""
    cx *= SS
    cy *= SS
    r *= SS
    r2 = r * r
    y0 = int(math.floor(cy - r))
    y1 = int(math.ceil(cy + r))
    for y in range(y0, y1 + 1):
        dy = y - cy
        dx = math.sqrt(max(0.0, r2 - dy * dy))
        span(y, cx - dx, cx + dx, c)


def ellipse(cx, cy, rx, ry, c):
    """Filled axis-aligned ellipse (output-pixel units)."""
    cx *= SS
    cy *= SS
    rx *= SS
    ry *= SS
    y0 = int(math.floor(cy - ry))
    y1 = int(math.ceil(cy + ry))
    for y in range(y0, y1 + 1):
        dy = (y - cy) / ry
        t = 1.0 - dy * dy
        if t < 0:
            continue
        dx = rx * math.sqrt(t)
        span(y, cx - dx, cx + dx, c)


def rellipse(cx, cy, rx, ry, ang, c):
    """Filled ellipse rotated by ang degrees (output-pixel units)."""
    a = math.radians(ang)
    ca, sa = math.cos(a), math.sin(a)
    cx *= SS
    cy *= SS
    rx *= SS
    ry *= SS
    # bounding box of the rotated ellipse
    bx = math.sqrt((rx * ca) ** 2 + (ry * sa) ** 2)
    by = math.sqrt((rx * sa) ** 2 + (ry * ca) ** 2)
    y0 = int(math.floor(cy - by))
    y1 = int(math.ceil(cy + by))
    for y in range(y0, y1 + 1):
        dy = y - cy
        # solve for x range: ((x ca + y sa)/rx)^2 + ((-x sa + y ca)/ry)^2 <= 1
        # A x^2 + B x + C <= 0 with
        A = (ca / rx) ** 2 + (sa / ry) ** 2
        B = 2 * dy * (ca * sa / rx ** 2 - sa * ca / ry ** 2)
        C = (dy * sa / rx) ** 2 + (dy * ca / ry) ** 2 - 1.0
        discr = B * B - 4 * A * C
        if discr < 0:
            continue
        sq = math.sqrt(discr)
        x_lo = (-B - sq) / (2 * A)
        x_hi = (-B + sq) / (2 * A)
        span(y, cx + x_lo, cx + x_hi, c)


def poly(points, c):
    """Filled polygon, points in output-pixel units."""
    pts = [(x * SS, y * SS) for (x, y) in points]
    ys = [p[1] for p in pts]
    y0 = int(math.floor(min(ys)))
    y1 = int(math.ceil(max(ys)))
    n = len(pts)
    for y in range(y0, y1 + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            x0, y0p = pts[i]
            x1, y1p = pts[(i + 1) % n]
            if (y0p <= yc < y1p) or (y1p <= yc < y0p):
                t = (yc - y0p) / (y1p - y0p)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            span(y, xs[j], xs[j + 1], c)


def rrect(x0, y0, x1, y1, r, c):
    """Filled rounded rectangle (output-pixel units)."""
    poly([(x0 + r, y0), (x1 - r, y0), (x1, y0 + r), (x1, y1 - r),
          (x1 - r, y1), (x0 + r, y1), (x0, y1 - r), (x0, y0 + r)], c)
    disc(x0 + r, y0 + r, r, c)
    disc(x1 - r, y0 + r, r, c)
    disc(x0 + r, y1 - r, r, c)
    disc(x1 - r, y1 - r, r, c)


def thick_line(x0, y0, x1, y1, w, c):
    """Line of width w (output-pixel units) with round caps."""
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    if L < 1e-6:
        disc(x0, y0, w / 2.0, c)
        return
    nx, ny = -dy / L * w / 2.0, dx / L * w / 2.0
    poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
          (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], c)
    disc(x0, y0, w / 2.0, c)
    disc(x1, y1, w / 2.0, c)


def arc(cx, cy, r, a0, a1, w, c):
    """Arc stroke, angles in degrees, width w (output-pixel units)."""
    steps = max(4, int(abs(a1 - a0) / 4))
    for i in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * i / steps)
        disc(cx + r * math.cos(a), cy + r * math.sin(a), w / 2.0, c)


def outline_disc(cx, cy, r, fill, out, ow):
    disc(cx, cy, r + ow, out)
    disc(cx, cy, r, fill)


def outline_ellipse(cx, cy, rx, ry, fill, out, ow):
    ellipse(cx, cy, rx + ow, ry + ow, out)
    ellipse(cx, cy, rx, ry, fill)


# ---------------------------------------------------------------- PNG
def png_bytes(w, h, rgb):
    def chunk(kind, data):
        out = struct.pack(">I", len(data)) + kind + data
        out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgb[y * w * 3:(y + 1) * w * 3]
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def downsample():
    """2x2 box average of the supersampled buffer -> 1024x1024 RGB."""
    rgb = bytearray(W * W * 3)
    for y in range(W):
        for x in range(W):
            sx = x * SS
            sy = y * SS
            acc = [0, 0, 0]
            for dy in range(SS):
                base = ((sy + dy) * SW + sx) * 3
                for dx in range(SS):
                    i = base + dx * 3
                    acc[0] += buf[i]
                    acc[1] += buf[i + 1]
                    acc[2] += buf[i + 2]
            o = (y * W + x) * 3
            rgb[o] = acc[0] // 4
            rgb[o + 1] = acc[1] // 4
            rgb[o + 2] = acc[2] // 4
    return bytes(rgb)


# ---------------------------------------------------------------- colors
BG_TOP = (255, 238, 218)
BG_BOT = (255, 222, 192)
BOKEH = (255, 246, 232)
BOKEH2 = (250, 214, 178)
OUT = (74, 64, 56)          # warm dark outline
BOX = (208, 166, 112)       # cardboard
BOX_DARK = (176, 132, 82)
BOX_IN = (150, 108, 64)     # box interior shadow
TAPE = (188, 146, 94)
GREY = (172, 182, 194)      # kitten fur
GREY_D = (140, 150, 164)
WHITE = (252, 252, 252)
CREAM = (232, 236, 240)     # face patch / chest
PINK_IN = (246, 172, 186)   # inner ear
EYE = (44, 146, 128)        # teal-green iris
PUPIL = (28, 28, 34)
NOSE = (232, 118, 138)
MOUTH = (96, 62, 56)
TONGUE = (242, 132, 142)
BLUSH = (246, 164, 172)
FLY_O = (246, 152, 58)      # butterfly orange
FLY_D = (214, 110, 30)
FLY_BODY = (70, 52, 40)


def background():
    for y in range(W):
        t = y / (W - 1)
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        span(y * SS, 0, SW - 1, (r, g, b))
        span(y * SS + 1, 0, SW - 1, (r, g, b))
    # soft bokeh dots, low contrast so the cat stays the subject
    for (x, y, r, c) in [
            (130, 150, 62, BOKEH), (880, 120, 74, BOKEH),
            (120, 830, 56, BOKEH2), (905, 800, 66, BOKEH),
            (80, 480, 40, BOKEH), (950, 470, 44, BOKEH2),
            (300, 90, 34, BOKEH2), (700, 80, 30, BOKEH)]:
        disc(x, y, r, c)


def box():
    # open cardboard box, front face + flaps, cat sits inside it
    # front face
    rrect(168, 700, 856, 952, 14, BOX)
    # top rim band (opening) and interior shadow
    poly([(168, 700), (856, 700), (820, 748), (204, 748)], BOX_IN)
    ellipse(512, 724, 322, 26, (122, 86, 50))
    # tape strip down the middle of the front face
    poly([(492, 748), (532, 748), (532, 952), (492, 952)], TAPE)
    thick_line(492, 748, 492, 952, 3, BOX_DARK)
    thick_line(532, 748, 532, 952, 3, BOX_DARK)
    # side flaps, angled outward
    poly([(168, 700), (238, 636), (330, 668), (262, 716)], BOX)
    poly([(168, 700), (238, 636), (330, 668), (262, 716)], BOX)  # densify
    poly([(856, 700), (786, 636), (694, 668), (762, 716)], BOX)
    # flap edge lines
    thick_line(168, 700, 238, 636, 5, BOX_DARK)
    thick_line(856, 700, 786, 636, 5, BOX_DARK)
    # front face outline
    thick_line(168, 700, 856, 700, 6, OUT)
    thick_line(168, 700, 168, 938, 6, OUT)
    thick_line(856, 700, 856, 938, 6, OUT)
    thick_line(168, 938, 856, 938, 6, OUT)
    # small heart drawn on the box front (charm, no text)
    disc(512, 830, 16, (226, 110, 128))
    disc(540, 830, 16, (226, 110, 128))
    poly([(496, 838), (556, 838), (526, 876)], (226, 110, 128))


def tail():
    # curled tail hook peeking from behind the box's right edge.
    # Drawn BEFORE the box so its base stays hidden behind the box.
    arc(905, 895, 52, 175, 345, 42, OUT)
    arc(905, 895, 52, 175, 345, 34, GREY)
    disc(955, 881, 17, OUT)
    disc(955, 881, 13, WHITE)


def butterfly(cx, cy):
    # small orange butterfly, wings up, hovering above the nose
    # upper wings
    rellipse(cx - 26, cy - 16, 26, 15, -32, OUT)
    rellipse(cx - 26, cy - 16, 21, 11, -32, FLY_O)
    rellipse(cx + 26, cy - 16, 26, 15, 32, OUT)
    rellipse(cx + 26, cy - 16, 21, 11, 32, FLY_O)
    # lower wings
    rellipse(cx - 20, cy + 12, 17, 10, -140, OUT)
    rellipse(cx - 20, cy + 12, 13, 7, -140, FLY_O)
    rellipse(cx + 20, cy + 12, 17, 10, 140, OUT)
    rellipse(cx + 20, cy + 12, 13, 7, 140, FLY_O)
    # wing dots
    disc(cx - 26, cy - 18, 5, FLY_D)
    disc(cx + 26, cy - 18, 5, FLY_D)
    # body + antennae
    ellipse(cx, cy, 5, 15, FLY_BODY)
    arc(cx - 2, cy - 14, 12, 200, 250, 3, FLY_BODY)
    arc(cx + 2, cy - 14, 12, 290, 340, 3, FLY_BODY)
    disc(cx - 9, cy - 24, 3, FLY_BODY)
    disc(cx + 9, cy - 24, 3, FLY_BODY)
    # tiny motion dots
    disc(cx - 52, cy - 34, 3, FLY_O)
    disc(cx + 54, cy - 30, 3, FLY_O)


def kitten():
    # chest peeking above the box rim
    outline_ellipse(512, 720, 165, 78, CREAM, OUT, 6)
    # ---- head ----
    # ears (slightly asymmetric = head tilt); big so they clear the head
    poly([(318, 400), (348, 205), (470, 330)], OUT)
    poly([(332, 380), (356, 240), (446, 326)], GREY)
    poly([(350, 356), (360, 270), (428, 322)], PINK_IN)
    poly([(560, 322), (668, 198), (712, 388)], OUT)
    poly([(578, 322), (660, 232), (692, 372)], GREY)
    poly([(596, 322), (652, 262), (676, 352)], PINK_IN)
    # head ball
    outline_disc(512, 470, 225, GREY, OUT, 7)
    # cream face patch (muzzle + cheeks)
    ellipse(512, 545, 152, 112, CREAM)
    # forehead stripes
    thick_line(470, 288, 462, 318, 10, GREY_D)
    thick_line(512, 282, 512, 314, 10, GREY_D)
    thick_line(554, 288, 562, 318, 10, GREY_D)
    # ---- eyes: big, round, bright, looking up at the butterfly ----
    for (ex, ey) in [(428, 462), (596, 455)]:
        outline_disc(ex, ey, 58, EYE, OUT, 6)
        disc(ex, ey - 12, 30, PUPIL)
        disc(ex - 14, ey - 26, 16, WHITE)
        disc(ex + 12, ey + 6, 7, WHITE)
    # upper lid lines + tiny lashes
    arc(428, 462, 58, 205, 335, 6, OUT)
    arc(596, 455, 58, 205, 335, 6, OUT)
    thick_line(376, 414, 362, 400, 5, OUT)
    thick_line(384, 408, 374, 392, 5, OUT)
    thick_line(648, 407, 662, 393, 5, OUT)
    thick_line(640, 401, 652, 385, 5, OUT)
    # blush
    disc(366, 568, 24, BLUSH)
    disc(658, 562, 24, BLUSH)
    # nose
    poly([(486, 546), (538, 546), (512, 574)], OUT)
    poly([(491, 550), (533, 550), (512, 568)], NOSE)
    # open happy mouth + tongue
    outline_ellipse(512, 610, 26, 30, MOUTH, OUT, 4)
    ellipse(512, 624, 17, 11, TONGUE)
    # whiskers
    for (x0, y0, x1, y1) in [
            (392, 560, 296, 540), (392, 578, 300, 582),
            (392, 596, 312, 622),
            (632, 554, 728, 534), (632, 572, 724, 576),
            (632, 590, 712, 616)]:
        thick_line(x0, y0, x1, y1, 4, OUT)
    # raised paw beside the head, reaching up for the butterfly
    # (overlaps the head edge so it reads as attached, no floating arm)
    outline_disc(715, 320, 42, WHITE, OUT, 6)
    thick_line(704, 288, 702, 306, 4, OUT)
    thick_line(716, 284, 716, 302, 4, OUT)
    thick_line(728, 288, 730, 306, 4, OUT)
    # resting paw on the box rim
    outline_ellipse(385, 692, 58, 32, WHITE, OUT, 6)
    thick_line(368, 676, 368, 692, 4, OUT)
    thick_line(400, 676, 400, 692, 4, OUT)


def main():
    background()
    tail()
    box()
    kitten()
    butterfly(770, 230)
    rgb = downsample()
    data = png_bytes(W, W, rgb)
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "entry.png"), "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
