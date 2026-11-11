#!/usr/bin/env python3
"""Milo in a teacup — the cutest cat, drawn procedurally.

A sleepy cream kitten curled inside a big teal teacup: paws draped over the
rim, big droopy-but-bright amber eyes, curled tail peeking out, steam wisps
curling up, and a tiny fish biscuit waiting on the saucer.

Pure standard library only. Deterministic: no randomness, no clock, no
network. Renders at 2x supersampling, box-downsamples to 1024x1024, and
writes /output/entry.png (or $MAKEFUN_OUTPUT_DIR/entry.png).
"""
import binascii
import math
import os
import struct
import zlib

W = 1024          # output size
SS = 2            # supersample factor
SW = W * SS       # working buffer width (2048)

# ---------------------------------------------------------------- palette
CREAM = bytes((255, 241, 220))   # kitten fur
CREAM_SHADE = bytes((255, 224, 184))
GINGER = bytes((240, 190, 138))  # forehead stripes / tail stripes
OUTLINE = bytes((122, 90, 64))   # warm dark brown outlines
PINK = bytes((245, 168, 184))    # inner ears
NOSE = bytes((232, 122, 138))
BLUSH = bytes((255, 185, 185))
IRIS = bytes((192, 138, 62))     # amber eyes
PUPIL = bytes((36, 24, 18))
WHITE = bytes((255, 255, 255))
TEAL = bytes((79, 163, 155))     # teacup
TEAL_DARK = bytes((47, 107, 100))
TEAL_LIGHT = bytes((143, 207, 197))
TEA = bytes((243, 217, 168))     # milky tea surface
SAUCER = bytes((253, 246, 238))
SAUCER_EDGE = bytes((232, 217, 196))
FISH = bytes((242, 166, 90))     # fish biscuit
STEAM = bytes((255, 255, 255))

# Working buffer: SW x SW RGB, row-major.
buf = bytearray(SW * SW * 3)


def _span(y, x0, x1, c):
    """Fill pixels [x0, x1) on supersampled row y with 3-byte color c."""
    if x1 <= x0 or y < 0 or y >= SW:
        return
    if x0 < 0:
        x0 = 0
    if x1 > SW:
        x1 = SW
    if x1 <= x0:
        return
    base = (y * SW + x0) * 3
    buf[base:base + (x1 - x0) * 3] = c * (x1 - x0)


def circle(cx, cy, r, c):
    """Filled circle; centre/radius given in 1024-space coordinates."""
    cx *= SS
    cy *= SS
    r *= SS
    r2 = r * r
    y0 = max(0, int(cy - r))
    y1 = min(SW - 1, int(cy + r) + 1)
    for y in range(y0, y1 + 1):
        dy = y - cy
        d2 = r2 - dy * dy
        if d2 < 0:
            continue
        dx = int(math.sqrt(d2))
        _span(y, int(cx - dx), int(cx + dx) + 1, c)


def ellipse(cx, cy, rx, ry, c):
    """Filled ellipse; centre/radii given in 1024-space coordinates."""
    cx *= SS
    cy *= SS
    rx *= SS
    ry *= SS
    y0 = max(0, int(cy - ry))
    y1 = min(SW - 1, int(cy + ry) + 1)
    for y in range(y0, y1 + 1):
        t = (y - cy) / ry
        q = 1.0 - t * t
        if q <= 0:
            continue
        dx = int(rx * math.sqrt(q))
        _span(y, int(cx - dx), int(cx + dx) + 1, c)


def poly(points, c):
    """Scanline-filled polygon; points are (x, y) in 1024-space."""
    pts = [(x * SS, y * SS) for (x, y) in points]
    n = len(pts)
    ys = [p[1] for p in pts]
    y0 = max(0, int(min(ys)))
    y1 = min(SW - 1, int(max(ys)) + 1)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x1, y1p = pts[i]
            x2, y2p = pts[(i + 1) % n]
            if (y1p <= y < y2p) or (y2p <= y < y1p):
                t = (y - y1p) / (y2p - y1p)
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            _span(y, int(xs[k]), int(xs[k + 1]) + 1, c)


def thick_line(x1, y1, x2, y2, w, c):
    """A line as a filled quad with round caps; w is width in 1024-space."""
    dx = x2 - x1
    dy = y2 - y1
    ln = math.hypot(dx, dy)
    if ln == 0:
        circle(x1, y1, w / 2.0, c)
        return
    nx = -dy / ln * w / 2.0
    ny = dx / ln * w / 2.0
    poly([(x1 + nx, y1 + ny), (x2 + nx, y2 + ny),
          (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)], c)
    circle(x1, y1, w / 2.0, c)
    circle(x2, y2, w / 2.0, c)


def arc_dots(cx, cy, r, a0, a1, w, c, steps=24):
    """A thick arc drawn as dots along it; angles in radians."""
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        circle(cx + r * math.cos(a), cy + r * math.sin(a), w / 2.0, c)


def band_dots(points, r_out, r_in, c_out, c_in):
    """A thick curved band through points: outline dots then fill dots."""
    for (x, y) in points:
        circle(x, y, r_out, c_out)
    for (x, y) in points:
        circle(x, y, r_in, c_in)


def gradient(top, bottom):
    """Vertical gradient background, top -> bottom color."""
    for y in range(SW):
        t = y / (SW - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        _span(y, 0, SW, bytes((r, g, b)))


def downsample():
    """2x2 box average -> 1024x1024 RGB bytes."""
    out = bytearray(W * W * 3)
    for oy in range(W):
        ra = buf[(oy * 2) * SW * 3:(oy * 2 + 1) * SW * 3]
        rb = buf[(oy * 2 + 1) * SW * 3:(oy * 2 + 2) * SW * 3]
        base = oy * W * 3
        for ox in range(W):
            i = ox * 6
            out[base + ox * 3] = (ra[i] + ra[i + 3] + rb[i] + rb[i + 3]) // 4
            out[base + ox * 3 + 1] = (ra[i + 1] + ra[i + 4] + rb[i + 1] + rb[i + 4]) // 4
            out[base + ox * 3 + 2] = (ra[i + 2] + ra[i + 5] + rb[i + 2] + rb[i + 5]) // 4
    return bytes(out)


def png_bytes(w, h, rgb):
    """Minimal deterministic PNG encoder (RGB, 8-bit, no interlace)."""
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgb[y * w * 3:(y + 1) * w * 3]

    def chunk(typ, data):
        out = struct.pack(">I", len(data)) + typ + data
        return out + struct.pack(">I", binascii.crc32(typ + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def background():
    gradient(bytes((255, 227, 199)), bytes((255, 247, 236)))
    # soft bokeh circles, low contrast, behind everything
    for (x, y, r, c) in [
        (150, 180, 90, bytes((255, 217, 184))),
        (880, 140, 70, bytes((255, 217, 184))),
        (920, 420, 55, bytes((255, 233, 207))),
        (90, 520, 60, bytes((255, 233, 207))),
        (830, 760, 80, bytes((255, 217, 184))),
        (120, 830, 65, bytes((255, 233, 207))),
    ]:
        circle(x, y, r, c)


def saucer():
    # wide flat saucer under the cup
    ellipse(512, 888, 392, 58, SAUCER_EDGE)
    ellipse(512, 884, 378, 50, SAUCER)
    ellipse(512, 882, 300, 36, bytes((255, 251, 244)))


def tail():
    # curled tail peeking out of the cup's left side, tip pointing up
    pts = []
    for i in range(13):
        t = i / 12.0
        a = math.pi * (0.95 - 0.75 * t)   # arc from low-left up around
        x = 235 + 105 * math.cos(a) - 20 * t
        y = 800 - 150 * math.sin(a) + 10 * t
        pts.append((x, y))
    band_dots(pts, 46, 36, OUTLINE, CREAM)
    # two soft ginger stripes across the tail
    for (x, y) in [pts[4], pts[8]]:
        circle(x, y, 37, GINGER)
        circle(x, y, 30, CREAM)
    # tail tip tuft (free end, lower left)
    circle(pts[0][0], pts[0][1], 38, CREAM)


def cup():
    # cup body: tapered bowl, rim at y=660, bottom resting on the saucer
    for y in range(660, 892):
        t = (y - 660) / 232.0
        half = 320 - 92 * (t ** 1.15)
        if y > 860:  # round the bottom
            half -= (y - 860) * 2.2
        if half < 4:
            break
        _span(int(y * SS), int((512 - half) * SS), int((512 + half) * SS) + 1,
              TEAL)
    # right-side shading
    for y in range(668, 884):
        t = (y - 660) / 232.0
        half = 320 - 92 * (t ** 1.15)
        if y > 860:
            half -= (y - 860) * 2.2
        if half < 4:
            break
        _span(int(y * SS), int((512 + half * 0.45) * SS),
              int((512 + half) * SS) + 1, TEAL_DARK)
    # left highlight stripe
    for y in range(672, 840):
        t = (y - 660) / 232.0
        half = 320 - 92 * (t ** 1.15)
        _span(int(y * SS), int((512 - half * 0.82) * SS),
              int((512 - half * 0.66) * SS) + 1, TEAL_LIGHT)
    # handle: C-shaped arc on the right, opening toward the cup
    pts = []
    for i in range(29):
        a = math.radians(-70 + 220 * i / 28.0)
        pts.append((858 + 92 * math.cos(a), 748 + 92 * math.sin(a)))
    band_dots(pts, 34, 24, TEAL_DARK, TEAL)
    # rim + milky tea surface
    ellipse(512, 660, 322, 64, TEAL_DARK)
    ellipse(512, 660, 302, 52, TEA)


def steam():
    # two soft wavy wisps rising past the head, left and right
    for (x0, phase) in [(350, 0.0), (680, 1.7)]:
        pts = []
        for i in range(16):
            t = i / 15.0
            x = x0 + 26 * math.sin(phase + t * 5.2)
            y = 268 - t * 138
            pts.append((x, y))
        for i, (x, y) in enumerate(pts):
            r = 15 - 7 * (i / 15.0)
            circle(x, y, r, STEAM)


def kitten():
    # ears first so the head overlaps their bases
    poly([(318, 340), (392, 168), (478, 322)], OUTLINE)
    poly([(338, 322), (392, 196), (458, 310)], CREAM)
    poly([(362, 306), (392, 222), (436, 298)], PINK)
    poly([(706, 340), (632, 168), (546, 322)], OUTLINE)
    poly([(686, 322), (632, 196), (566, 310)], CREAM)
    poly([(662, 306), (632, 222), (588, 298)], PINK)
    # head
    circle(512, 470, 233, OUTLINE)
    circle(512, 470, 225, CREAM)
    # forehead stripes
    thick_line(470, 300, 478, 262, 14, GINGER)
    thick_line(512, 292, 512, 252, 14, GINGER)
    thick_line(554, 300, 546, 262, 14, GINGER)
    # big sleepy amber eyes
    for cx in (425, 599):
        circle(cx, 482, 52, IRIS)
        circle(cx, 482, 23, PUPIL)
        circle(cx - 15, 465, 11, WHITE)
        circle(cx + 13, 497, 5, WHITE)
        # sleepy eyelid draped over the top of the eye
        ellipse(cx, 438, 54, 30, CREAM)
        for i in range(25):
            a = math.radians(205 + 130 * i / 24.0)
            circle(cx + 54 * math.cos(a), 438 + 30 * math.sin(a), 3, OUTLINE)
    # nose + omega mouth
    poly([(490, 544), (534, 544), (512, 574)], OUTLINE)
    poly([(494, 548), (530, 548), (512, 570)], NOSE)
    arc_dots(499, 584, 13, 0.0, math.pi, 6, OUTLINE, steps=12)
    arc_dots(525, 584, 13, 0.0, math.pi, 6, OUTLINE, steps=12)
    # blush cheeks
    ellipse(368, 556, 34, 20, BLUSH)
    ellipse(656, 556, 34, 20, BLUSH)
    # whiskers
    for (x1, y1, x2, y2) in [
        (398, 540, 296, 512), (396, 556, 292, 552), (398, 572, 300, 592),
        (626, 540, 728, 512), (628, 556, 732, 552), (626, 572, 724, 592),
    ]:
        thick_line(x1, y1, x2, y2, 5, OUTLINE)
    # paws draped over the cup rim
    for cx in (395, 629):
        ellipse(cx, 652, 70, 50, OUTLINE)
        ellipse(cx, 652, 62, 42, CREAM)
        thick_line(cx - 16, 638, cx - 16, 668, 5, OUTLINE)
        thick_line(cx + 16, 638, cx + 16, 668, 5, OUTLINE)


def fish_biscuit():
    # tiny fish biscuit waiting on the saucer
    poly([(846, 884), (874, 864), (874, 904)], OUTLINE)
    poly([(848, 884), (870, 868), (870, 900)], FISH)
    ellipse(810, 884, 44, 24, OUTLINE)
    ellipse(810, 884, 40, 20, FISH)
    circle(792, 878, 4, PUPIL)


def main():
    background()
    saucer()
    tail()
    cup()
    steam()
    kitten()
    fish_biscuit()
    rgb = downsample()
    data = png_bytes(W, W, rgb)
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "entry.png"), "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
