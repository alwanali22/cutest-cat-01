#!/usr/bin/env python3
"""Draw the cutest cat (make.fun bounty cutest-cat-01).

A deterministic, standard-library-only program. It draws one front-facing
kawaii kitten with a tiny vector rasterizer (2x supersampled span fills,
2x2 box downsample) and writes it as a PNG to /output/entry.png
(or $MAKEFUN_OUTPUT_DIR/entry.png).

No randomness, no wall clock, no network, no files read: two runs write
byte-identical output.
"""

import math
import os
import struct
import zlib

FINAL = 1024          # output size, square
SS = 2                # supersample factor
W = FINAL * SS        # render buffer size
H = FINAL * SS


# ---------------------------------------------------------------- PNG writer

def _png_chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return out


def write_png(path, width, height, rgb):
    """Write RGB bytes (row-major, 3 bytes/pixel) as a PNG file."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = bytearray()
    stride = width * 3
    for y in range(height):
        raw.append(0)  # filter: none
        raw += rgb[y * stride:(y + 1) * stride]
    idat = zlib.compress(bytes(raw), 6)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(_png_chunk(b"IHDR", ihdr))
        f.write(_png_chunk(b"IDAT", idat))
        f.write(_png_chunk(b"IEND", b""))


# ------------------------------------------------------------------- canvas

class Canvas:
    """RGB canvas rendered at SSx, downsampled to FINAL on save."""

    def __init__(self):
        self.buf = bytearray(W * H * 3)

    def _span(self, y, x0, x1, rgb):
        """Fill one buffer row from x0 to x1 inclusive with a solid color."""
        if y < 0 or y >= H:
            return
        x0 = max(0, int(x0))
        x1 = min(W - 1, int(x1))
        if x1 < x0:
            return
        n = x1 - x0 + 1
        o = (y * W + x0) * 3
        self.buf[o:o + n * 3] = bytes(rgb) * n

    def ellipse(self, cx, cy, rx, ry, rgb):
        """Filled axis-aligned ellipse; cx/cy/rx/ry in final coordinates."""
        cx, cy, rx, ry = cx * SS, cy * SS, rx * SS, ry * SS
        y0 = max(0, int(math.ceil(cy - ry)))
        y1 = min(H - 1, int(math.floor(cy + ry)))
        for y in range(y0, y1 + 1):
            dy = (y + 0.5 - cy) / ry
            t = 1.0 - dy * dy
            if t <= 0:
                continue
            dx = rx * math.sqrt(t)
            self._span(y, cx - dx, cx + dx, rgb)

    def circle(self, cx, cy, r, rgb):
        self.ellipse(cx, cy, r, r, rgb)

    def ellipse_alpha(self, cx, cy, rx, ry, rgb, alpha):
        """Soft ellipse blended over what is already there (0..255 alpha)."""
        cx, cy, rx, ry = cx * SS, cy * SS, rx * SS, ry * SS
        y0 = max(0, int(math.ceil(cy - ry)))
        y1 = min(H - 1, int(math.floor(cy + ry)))
        inv = 255 - alpha
        buf = self.buf
        for y in range(y0, y1 + 1):
            dy = (y + 0.5 - cy) / ry
            t = 1.0 - dy * dy
            if t <= 0:
                continue
            dx = rx * math.sqrt(t)
            x0 = max(0, int(math.ceil(cx - dx)))
            x1 = min(W - 1, int(math.floor(cx + dx)))
            for x in range(x0, x1 + 1):
                o = (y * W + x) * 3
                buf[o] = (rgb[0] * alpha + buf[o] * inv) // 255
                buf[o + 1] = (rgb[1] * alpha + buf[o + 1] * inv) // 255
                buf[o + 2] = (rgb[2] * alpha + buf[o + 2] * inv) // 255

    def polygon(self, points, rgb):
        """Filled polygon; points are (x, y) in final coordinates."""
        pts = [(x * SS, y * SS) for (x, y) in points]
        y0 = max(0, int(math.ceil(min(p[1] for p in pts))))
        y1 = min(H - 1, int(math.floor(max(p[1] for p in pts))))
        n = len(pts)
        for y in range(y0, y1 + 1):
            yc = y + 0.5
            xs = []
            for i in range(n):
                x0, y0p = pts[i]
                x1, y1p = pts[(i + 1) % n]
                if (y0p <= yc < y1p) or (y1p <= yc < y0p):
                    xs.append(x0 + (yc - y0p) * (x1 - x0) / (y1p - y0p))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self._span(y, xs[i], xs[i + 1], rgb)

    def thick_line(self, x0, y0, x1, y1, width, rgb):
        """Line with round caps; width in final coordinates."""
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length == 0:
            self.circle(x0, y0, width / 2, rgb)
            return
        nx, ny = -dy / length * width / 2, dx / length * width / 2
        self.polygon([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                      (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], rgb)
        self.circle(x0, y0, width / 2, rgb)
        self.circle(x1, y1, width / 2, rgb)

    def bezier(self, p0, p1, p2, width, rgb, steps=24):
        """Quadratic Bezier stroke (p0, p1 control, p2 end)."""
        prev = p0
        for i in range(1, steps + 1):
            t = i / steps
            u = 1 - t
            x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
            y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
            self.thick_line(prev[0], prev[1], x, y, width, rgb)
            prev = (x, y)

    def downsample(self):
        """2x2 box-average the SSx buffer down to FINAL x FINAL RGB bytes."""
        out = bytearray(FINAL * FINAL * 3)
        buf = self.buf
        for oy in range(FINAL):
            sy = oy * 2
            orow = oy * FINAL * 3
            for ox in range(FINAL):
                sx = ox * 2
                o0 = (sy * W + sx) * 3
                o1 = o0 + 3
                o2 = o0 + W * 3
                o3 = o2 + 3
                oo = orow + ox * 3
                out[oo] = (buf[o0] + buf[o1] + buf[o2] + buf[o3]) // 4
                out[oo + 1] = (buf[o0 + 1] + buf[o1 + 1] + buf[o2 + 1] + buf[o3 + 1]) // 4
                out[oo + 2] = (buf[o0 + 2] + buf[o1 + 2] + buf[o2 + 2] + buf[o3 + 2]) // 4
        return bytes(out)


# ------------------------------------------------------------------ palette
BG_TOP = (255, 227, 200)      # pale peach
BG_BOTTOM = (255, 247, 236)   # pale cream
BOKEH_A = (255, 214, 178)
BOKEH_B = (255, 240, 220)
FUR = (242, 164, 92)          # ginger
FUR_DARK = (222, 138, 61)     # tabby stripes
CREAM = (253, 235, 215)       # chest / muzzle
OUTLINE = (124, 74, 45)       # warm dark brown
PINK_EAR = (246, 168, 184)
PINK_NOSE = (232, 122, 144)
BLUSH = (244, 154, 168)
EYE_DARK = (51, 36, 28)
WHISKER = (138, 90, 59)
YARN = (232, 106, 122)
YARN_DARK = (201, 79, 96)
SHADOW = (124, 74, 45)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def draw_background(c):
    """Soft vertical gradient, a few pale bokeh circles, tiny stars."""
    for y in range(H):
        t = y / (H - 1)
        c._span(y, 0, W - 1, _lerp(BG_TOP, BG_BOTTOM, t))
    for (cx, cy, r, col) in [
            (150, 170, 90, BOKEH_A), (880, 130, 70, BOKEH_B),
            (930, 700, 110, BOKEH_A), (90, 760, 80, BOKEH_B),
            (820, 930, 60, BOKEH_B)]:
        c.ellipse(cx, cy, r, r, col)
    # tiny four-point stars, barely there
    for (cx, cy, r) in [(210, 330, 7), (800, 330, 6), (120, 480, 6),
                         (905, 480, 7), (700, 120, 5), (320, 110, 5)]:
        c.polygon([(cx, cy - r), (cx + r * 0.28, cy - r * 0.28),
                   (cx + r, cy), (cx + r * 0.28, cy + r * 0.28),
                   (cx, cy + r), (cx - r * 0.28, cy + r * 0.28),
                   (cx - r, cy), (cx - r * 0.28, cy - r * 0.28)], BOKEH_B)


def draw_tail(c):
    """One curled tail around the cat's right side, cream tip."""
    c.bezier((740, 830), (880, 860), (905, 760), 52, OUTLINE, steps=28)
    c.bezier((740, 830), (880, 860), (905, 760), 42, FUR, steps=28)
    c.circle(905, 758, 26, OUTLINE)
    c.circle(905, 758, 20, CREAM)


def draw_body(c):
    """Sitting body, cream belly, hind paws at the sides, front paws."""
    # body outline then fill
    c.ellipse(512, 782, 306, 216, OUTLINE)
    c.ellipse(512, 782, 296, 206, FUR)
    # cream belly patch
    c.ellipse(512, 806, 192, 152, CREAM)
    # hind paws tucked against the lower sides
    for cx in (296, 728):
        c.ellipse(cx, 884, 62, 40, OUTLINE)
        c.ellipse(cx, 884, 54, 32, CREAM)
    # front paws, side by side
    for cx in (428, 596):
        c.ellipse(cx, 906, 100, 58, OUTLINE)
        c.ellipse(cx, 906, 91, 49, CREAM)
        # two toe lines on each paw
        for tx in (cx - 26, cx + 26):
            c.thick_line(tx, 884, tx, 924, 5, OUTLINE)


def draw_ear(c, cx, cy, tilt):
    """One rounded-triangle ear; tilt shifts its tip sideways."""
    tip = (cx + tilt, cy - 118)
    base_l = (cx - 78, cy + 52)
    base_r = (cx + 78, cy + 52)
    # outer: outline then fur, inner: pink
    for pts, col in [
            ([tip, base_l, base_r], OUTLINE),
            ([(tip[0] * 0.94 + cx * 0.06, tip[1] * 0.94 + cy * 0.06),
              (base_l[0] * 0.94 + cx * 0.06, base_l[1] * 0.94 + cy * 0.06),
              (base_r[0] * 0.94 + cx * 0.06, base_r[1] * 0.94 + cy * 0.06)],
             FUR)]:
        c.polygon(pts, col)
    inner = [(cx + tilt * 0.5, cy - 62),
             (cx - 38, cy + 30), (cx + 38, cy + 30)]
    c.polygon(inner, PINK_EAR)


def draw_head(c):
    """Big round head, tilted: left ear and eye sit a touch higher."""
    # ears first so the head covers their bases
    draw_ear(c, 330, 216, -14)   # viewer-left ear, higher
    draw_ear(c, 694, 228, 14)    # viewer-right ear, lower
    # head outline then fill
    c.circle(512, 430, 272, OUTLINE)
    c.circle(512, 430, 262, FUR)
    # tabby stripes on the forehead
    for (x0, y0, x1, y1) in [(452, 196, 446, 232), (512, 184, 512, 222),
                             (572, 196, 578, 232)]:
        c.thick_line(x0, y0, x1, y1, 10, FUR_DARK)
    # cream muzzle patch
    c.ellipse(512, 522, 152, 106, CREAM)


def draw_eye(c, cx, cy):
    """One huge glossy eye: outline, dark oval, two white highlights."""
    c.ellipse(cx, cy, 60, 76, OUTLINE)
    c.ellipse(cx, cy, 52, 68, EYE_DARK)
    c.circle(cx - 17, cy - 24, 19, (255, 255, 255))
    c.circle(cx + 19, cy + 20, 9, (255, 255, 255))


def draw_face(c):
    """Eyes, nose, mouth, blush, whiskers."""
    # eyes sit slightly tilted with the head
    draw_eye(c, 408, 428)
    draw_eye(c, 616, 440)
    # tiny pink nose, rounded triangle
    c.polygon([(488, 494), (536, 494), (512, 522)], PINK_NOSE)
    c.circle(500, 502, 6, (255, 255, 255))
    # little "w" mouth under the nose: two small upward curls
    c.bezier((512, 530), (499, 546), (486, 536), 6, OUTLINE, steps=10)
    c.bezier((512, 530), (525, 546), (538, 536), 6, OUTLINE, steps=10)
    # blush cheeks
    c.ellipse_alpha(348, 522, 50, 27, BLUSH, 110)
    c.ellipse_alpha(676, 532, 50, 27, BLUSH, 110)
    # whiskers, three per side, gently curved
    for (x0, y0, x1, y1, x2, y2) in [
            (398, 498, 330, 478, 268, 462),
            (396, 516, 322, 510, 258, 506),
            (400, 534, 334, 548, 276, 562)]:
        c.bezier((x0, y0), (x1, y1), (x2, y2), 4, WHISKER, steps=12)
    for (x0, y0, x1, y1, x2, y2) in [
            (626, 508, 694, 488, 756, 472),
            (628, 526, 702, 520, 766, 516),
            (624, 544, 690, 558, 748, 572)]:
        c.bezier((x0, y0), (x1, y1), (x2, y2), 4, WHISKER, steps=12)


def draw_yarn_and_heart(c):
    """Charm: a yarn ball by the left paw, loose thread, tiny heart."""
    # loose thread first, so the ball covers its end
    c.bezier((252, 822), (300, 780), (352, 792), 6, YARN_DARK, steps=14)
    # ball: outline, fill, wrap lines
    c.circle(252, 878, 66, OUTLINE)
    c.circle(252, 878, 58, YARN)
    c.bezier((198, 852), (252, 836), (306, 852), 6, YARN_DARK, steps=12)
    c.bezier((196, 886), (252, 902), (308, 886), 6, YARN_DARK, steps=12)
    c.bezier((212, 830), (238, 878), (216, 926), 6, YARN_DARK, steps=12)
    # tiny heart floating in the clear space left of the cat
    hx, hy, s = 205, 695, 20
    c.circle(hx - s * 0.45, hy - s * 0.25, s * 0.52, YARN)
    c.circle(hx + s * 0.45, hy - s * 0.25, s * 0.52, YARN)
    c.polygon([(hx - s * 0.95, hy - s * 0.1), (hx + s * 0.95, hy - s * 0.1),
               (hx, hy + s)], YARN)


def draw():
    """Compose the whole picture and return FINAL x FINAL RGB bytes."""
    c = Canvas()
    draw_background(c)
    # soft ground shadow under the cat
    c.ellipse_alpha(512, 884, 330, 42, SHADOW, 30)
    draw_tail(c)
    draw_body(c)
    draw_yarn_and_heart(c)
    draw_head(c)
    draw_face(c)
    return c.downsample()


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    rgb = draw()
    write_png(os.path.join(out_dir, "entry.png"), FINAL, FINAL, rgb)


if __name__ == "__main__":
    main()
