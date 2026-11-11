"""Noir Hugs a Fish — cutest-cat v4 entry (make.fun cutest-cat-01).

A black kitten with big amber eyes hugs a big pink fish plush.
Drawn procedurally: pure-stdlib PNG writer + supersampled rasterizer.
Deterministic: same bytes on every run. No network, no files read.
"""
import math
import os
import struct
import zlib

W = 1024
SS = 2
BW = W * SS

CREAM = (255, 246, 232)
CREAM2 = (255, 238, 214)
DOT = (242, 224, 198)
SHADOW = (214, 196, 168)
INK = (43, 43, 51)
INK2 = (62, 62, 74)
INK3 = (80, 80, 94)
PINK = (255, 159, 178)
PINK_D = (238, 120, 145)
PINK_L = (255, 196, 207)
AMBER = (245, 166, 35)
AMBER_D = (214, 130, 10)
WHITE = (255, 255, 255)
DARK = (30, 30, 38)
NOSE = (255, 120, 140)
WHISK = (228, 222, 210)


def write_png(path, w, h, rgb):
    raw = b"".join(b"\x00" + rgb[y * w * 3:(y + 1) * w * 3]
                   for y in range(h))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


# ---------------- canvas (supersampled) ----------------
buf = bytearray(bytes(CREAM) * BW * BW)


def _fill_row(y, xa, xb, color):
    if y < 0 or y >= BW:
        return
    xa = max(0, xa)
    xb = min(BW - 1, xb)
    if xa > xb:
        return
    n = xb - xa + 1
    i0 = (y * BW + xa) * 3
    buf[i0:i0 + n * 3] = bytes(color) * n


def ellipse(cx, cy, rx, ry, color):
    y0 = max(0, int(cy - ry))
    y1 = min(BW - 1, int(cy + ry) + 1)
    for y in range(y0, y1 + 1):
        dy = (y - cy) / ry
        s = 1.0 - dy * dy
        if s <= 0:
            continue
        dx = math.sqrt(s) * rx
        _fill_row(y, int(cx - dx), int(cx + dx), color)


def circle(cx, cy, r, color):
    ellipse(cx, cy, r, r, color)


def poly(points, color):
    if len(points) < 3:
        return
    ys = [p[1] for p in points]
    y0 = max(0, int(min(ys)))
    y1 = min(BW - 1, int(max(ys)) + 1)
    n = len(points)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x0, y0p = points[i]
            x1, y1p = points[(i + 1) % n]
            if (y0p <= y < y1p) or (y1p <= y < y0p):
                t = (y - y0p) / (y1p - y0p)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            _fill_row(y, int(xs[k]), int(xs[k + 1]), color)


def rrect(x0, y0, x1, y1, r, color):
    for y in range(max(0, int(y0)), min(BW, int(y1) + 1)):
        _fill_row(y, int(x0), int(x1), color)
    # corners are square here; circles at the corners soften them
    circle(x0 + r, y0 + r, r, color)
    circle(x1 - r, y0 + r, r, color)
    circle(x0 + r, y1 - r, r, color)
    circle(x1 - r, y1 - r, r, color)


def thick_line(x0, y0, x1, y1, w, color):
    dx = x1 - x0
    dy = y1 - y0
    ln = math.hypot(dx, dy)
    if ln == 0:
        circle(x0, y0, w / 2.0, color)
        return
    nx = -dy / ln * w / 2.0
    ny = dx / ln * w / 2.0
    poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
          (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], color)
    circle(x0, y0, w / 2.0, color)
    circle(x1, y1, w / 2.0, color)


def arc(cx, cy, r, a0, a1, w, color, steps=24):
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        x = cx + r * math.cos(a)
        y = cy + r * math.sin(a)
        circle(x, y, w / 2.0, color)


def bezier(p0, p1, p2, w, color, steps=28):
    prev = None
    for i in range(steps + 1):
        t = i / steps
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]
        if prev is not None:
            thick_line(prev[0], prev[1], x, y, w, color)
        prev = (x, y)


def rot_pt(x, y, cx, cy, ang):
    c = math.cos(ang)
    s = math.sin(ang)
    dx = x - cx
    dy = y - cy
    return (cx + dx * c - dy * s, cy + dx * s + dy * c)


# ---------------- background ----------------
def draw_background():
    # soft halo behind the subjects
    ellipse(1024, 1050, 760, 700, CREAM2)
    # a few small paw-print dots scattered around
    for (x, y, r) in [(300, 420, 26), (350, 470, 20), (1760, 480, 24),
                      (1800, 540, 18), (260, 1560, 22), (1820, 1620, 26),
                      (1500, 300, 20), (560, 300, 18)]:
        circle(x, y, r, DOT)
    # ground shadow
    ellipse(1024, 1580, 620, 110, SHADOW)


# ---------------- the pink fish plush ----------------
def draw_fish():
    # Fish body as a rotated polygon, held in front of the belly
    # (drawn after the kitten body, before the front paws).
    cx, cy = 1030, 1360
    ang = -0.5  # tilt
    S = 0.8
    # body outline in local coords (before rotation): a plump fish
    local = [
        (330, -40), (300, -150), (190, -230), (40, -250), (-140, -210),
        (-280, -120), (-330, -30), (-280, 60), (-300, 150), (-180, 210),
        (-40, 250), (140, 230), (260, 150), (320, 60),
    ]
    pts = [rot_pt(x * S + cx, y * S + cy, cx, cy, ang) for (x, y) in local]
    poly(pts, PINK)
    # belly patch (lighter, lower half)
    belly = [rot_pt(x * S + cx, y * S + cy + 70 * S, cx, cy, ang)
             for (x, y) in [
                 (260, -20), (200, -90), (80, -130), (-80, -120),
                 (-200, -60), (-230, 10), (-140, 70), (0, 100),
                 (150, 80), (240, 30),
             ]]
    poly(belly, PINK_L)
    # tail fin (two triangles fanning down-left)
    tail = [rot_pt(x * S + cx, y * S + cy, cx, cy, ang) for (x, y) in [
        (-300, -60), (-520, -190), (-430, -30), (-520, 170), (-290, 70),
    ]]
    poly(tail, PINK_D)
    # dorsal fin on top
    dorsal = [rot_pt(x * S + cx, y * S + cy, cx, cy, ang) for (x, y) in [
        (-60, -240), (60, -330), (170, -250), (120, -210), (-20, -220),
    ]]
    poly(dorsal, PINK_D)
    # gill curve
    gx, gy = rot_pt(cx + 180 * S, cy - 40 * S, cx, cy, ang)
    arc(gx, gy, 88, 0.5, 2.2, 12, PINK_D, steps=18)
    # fish eye (big, friendly)
    ex, ey = rot_pt(cx + 210 * S, cy - 120 * S, cx, cy, ang)
    circle(ex, ey, 50, WHITE)
    circle(ex + 6, ey + 5, 27, DARK)
    circle(ex - 10, ey - 11, 11, WHITE)
    # shine on the body
    sx, sy = rot_pt(cx - 40 * S, cy - 130 * S, cx, cy, ang)
    ellipse(sx, sy, 96, 34, PINK_L)


# ---------------- the black kitten ----------------
def draw_kitten():
    # tail curling out to the right, behind the body
    bezier((1250, 1420), (1520, 1500), (1560, 1260), 90, INK, steps=24)
    circle(1560, 1260, 48, INK2)
    # ears (behind the head)
    poly([(700, 700), (790, 420), (900, 660)], INK)
    poly([(1100, 660), (1210, 420), (1300, 700)], INK)
    poly([(750, 650), (795, 500), (855, 630)], PINK_D)
    poly([(1145, 630), (1205, 500), (1250, 650)], PINK_D)
    # body (sitting)
    ellipse(960, 1290, 340, 310, INK)
    # lighter chest/belly patch
    ellipse(960, 1330, 210, 210, INK2)
    # head
    circle(960, 880, 310, INK)
    # eyes: big amber ovals
    for ex in (820, 1100):
        ellipse(ex, 880, 96, 112, AMBER)
        ellipse(ex, 890, 52, 66, DARK)
        circle(ex - 28, 850, 22, WHITE)
        circle(ex + 30, 920, 10, WHITE)
    # pink nose
    poly([(960, 1000), (920, 1030), (1000, 1030)], NOSE)
    # mouth: little omega curve under the nose
    arc(930, 1060, 42, 0.15 * math.pi, 0.85 * math.pi, 12, INK3, steps=14)
    arc(990, 1060, 42, 0.15 * math.pi, 0.85 * math.pi, 12, INK3, steps=14)
    # blush
    ellipse(700, 1020, 62, 34, (255, 130, 150))
    ellipse(1220, 1020, 62, 34, (255, 130, 150))
    # whiskers (light, thin)
    for (x0, y0, x1, y1) in [
            (700, 990, 520, 950), (700, 1030, 520, 1030),
            (700, 1070, 540, 1110),
            (1220, 990, 1400, 950), (1220, 1030, 1400, 1030),
            (1220, 1070, 1380, 1110)]:
        thick_line(x0, y0, x1, y1, 8, WHISK)
    # hind paws at the base
    ellipse(700, 1530, 120, 70, INK)
    ellipse(1220, 1530, 120, 70, INK)


def draw_paws():
    # front paws wrapped around the fish (the hug), drawn over the fish
    ellipse(1230, 1300, 130, 95, INK)
    ellipse(830, 1330, 120, 90, INK)
    # tiny toe lines on the front paws
    for (x0, y0, x1, y1) in [(1200, 1240, 1200, 1300),
                             (1250, 1240, 1250, 1300),
                             (810, 1270, 810, 1330),
                             (855, 1270, 855, 1330)]:
        thick_line(x0, y0, x1, y1, 7, INK3)


def downsample():
    out = bytearray(W * W * 3)
    for y in range(W):
        for x in range(W):
            i0 = ((2 * y) * BW + 2 * x) * 3
            i1 = i0 + 3
            i2 = ((2 * y + 1) * BW + 2 * x) * 3
            i3 = i2 + 3
            o = (y * W + x) * 3
            out[o] = (buf[i0] + buf[i1] + buf[i2] + buf[i3]) // 4
            out[o + 1] = (buf[i0 + 1] + buf[i1 + 1] + buf[i2 + 1] + buf[i3 + 1]) // 4
            out[o + 2] = (buf[i0 + 2] + buf[i1 + 2] + buf[i2 + 2] + buf[i3 + 2]) // 4
    return bytes(out)


def main():
    draw_background()
    draw_kitten()
    draw_fish()
    draw_paws()
    rgb = downsample()
    out = os.environ.get("ENTRY_OUT", "/output/entry.png")
    try:
        write_png(out, W, W, rgb)
    except OSError:
        out = "out/entry.png"
        os.makedirs("out", exist_ok=True)
        write_png(out, W, W, rgb)
    print("wrote", out)


if __name__ == "__main__":
    main()
