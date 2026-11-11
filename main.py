# Mimi Hugs a Heart — cutest-cat v5 entry (make.fun cutest-cat-01)
# A fluffy white kitten with big bright blue eyes and a little red bow
# hugs a big red heart. Pure stdlib Python: draws procedurally, no
# network, no fonts, deterministic. Writes one PNG to /output/entry.png.
import os, struct, zlib, math

S = 2.0
W = 1024
H = 1024
B = int(W * S)

# --- palette ---
BG      = (255, 233, 236)  # soft pink background
HALO    = (255, 245, 246)  # pale halo behind the kitten
WHITE   = (255, 255, 255)
SHADE   = (232, 221, 213)  # soft taupe edge under white shapes
INNER   = (255, 176, 184)  # pink inner ears / nose / blush
RED     = (255, 90, 110)   # heart + bow
RED_D   = (230, 60, 85)
BLUE    = (58, 160, 255)   # bright blue eyes
DARK    = (48, 42, 46)     # pupils / outlines / mouth
GREY    = (170, 158, 152)  # whiskers / toes
CREAM   = (255, 250, 244)  # belly patch

def new_canvas():
    return bytearray(BG * B * B)

def set_px(px, x, y, c):
    if 0 <= x < B and 0 <= y < B:
        i = (y * B + x) * 3
        px[i:i+3] = bytes(c)

def ellipse(px, cx, cy, rx, ry, c, rot=0.0):
    cr, sr = math.cos(rot), math.sin(rot)
    x0 = max(0, int(cx - rx - 2)); x1 = min(B - 1, int(cx + rx + 2))
    y0 = max(0, int(cy - ry - 2)); y1 = min(B - 1, int(cy + ry + 2))
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            dx, dy = x - cx, y - cy
            ex = dx * cr + dy * sr; ey = -dx * sr + dy * cr
            if (ex / rx) ** 2 + (ey / ry) ** 2 <= 1.0:
                set_px(px, x, y, c)

def poly(px, pts, c):
    # scanline polygon fill
    y0 = max(0, int(min(p[1] for p in pts))); y1 = min(B - 1, int(max(p[1] for p in pts)))
    n = len(pts)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x1, y1p = pts[i]; x2, y2p = pts[(i + 1) % n]
            if (y1p <= y < y2p) or (y2p <= y < y1p):
                t = (y - y1p) / (y2p - y1p)
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            for x in range(max(0, int(xs[k])), min(B - 1, int(xs[k + 1])) + 1):
                set_px(px, x, y, c)

def arc(px, cx, cy, r, a0, a1, c, th=10):
    n = max(8, int((a1 - a0) * r / 8))
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        for d in range(-th // 2, th // 2 + 1):
            set_px(px, int(cx + (r + d) * math.cos(a)), int(cy + (r + d) * math.sin(a)), c)

def line(px, x1, y1, x2, y2, c, th=8):
    n = max(2, int(max(abs(x2 - x1), abs(y2 - y1)) / 4))
    for i in range(n + 1):
        t = i / n
        x = x1 + (x2 - x1) * t; y = y1 + (y2 - y1) * t
        for dx in range(-th // 2, th // 2 + 1):
            for dy in range(-th // 2, th // 2 + 1):
                if dx * dx + dy * dy <= (th // 2) ** 2:
                    set_px(px, int(x) + dx, int(y) + dy, c)

def heart(px, cx, cy, s, c, dc):
    # two round lobes + downward triangle, classic heart
    ellipse(px, cx - int(0.42 * s), cy - int(0.28 * s), int(0.46 * s), int(0.46 * s), c)
    ellipse(px, cx + int(0.42 * s), cy - int(0.28 * s), int(0.46 * s), int(0.46 * s), c)
    poly(px, [(cx - int(0.86 * s), cy - int(0.10 * s)),
              (cx + int(0.86 * s), cy - int(0.10 * s)),
              (cx, cy + int(0.95 * s))], c)
    # glossy highlight on the upper-left lobe
    ellipse(px, cx - int(0.55 * s), cy - int(0.48 * s), int(0.16 * s), int(0.10 * s), (255, 205, 210), rot=-0.5)

def draw_background(px):
    ellipse(px, 1024, 1000, 900, 900, HALO)
    # tiny floating hearts + dots
    for (hx, hy, hs) in [(300, 330, 60), (1760, 300, 48), (1820, 1550, 55),
                         (260, 1580, 50), (1500, 190, 40), (520, 180, 42)]:
        heart(px, hx, hy, hs, (255, 150, 165), RED_D)
    for (dx, dy, r) in [(420, 700, 16), (1660, 700, 16), (700, 220, 12),
                        (1400, 300, 12), (180, 1100, 14), (1900, 1050, 14)]:
        ellipse(px, dx, dy, r, r, (255, 210, 216))

def draw_tail(px):
    # curling tail: overlapping circles rising from the body's right side
    for (tx, ty, tr) in [(1360, 1560, 95), (1460, 1470, 85), (1530, 1370, 75)]:
        ellipse(px, tx, ty + 6, tr, tr, SHADE)
        ellipse(px, tx, ty, tr - 8, tr - 8, WHITE)

def draw_body(px):
    # soft edge, then the body, then the belly patch
    ellipse(px, 1024, 1396, 345, 300, SHADE)
    ellipse(px, 1024, 1388, 335, 292, WHITE)
    ellipse(px, 1024, 1470, 225, 190, CREAM)
    # hind paws at the base
    ellipse(px, 830, 1665, 130, 62, SHADE)
    ellipse(px, 830, 1658, 124, 56, WHITE)
    ellipse(px, 1225, 1665, 130, 62, SHADE)
    ellipse(px, 1225, 1658, 124, 56, WHITE)
    for lx in (790, 830, 870):
        line(px, lx, 1640, lx, 1678, GREY, th=6)
    for lx in (1185, 1225, 1265):
        line(px, lx, 1640, lx, 1678, GREY, th=6)

def draw_big_heart(px):
    heart(px, 1024, 1240, 600, RED, RED_D)

def draw_head(px):
    # ears first (behind the head)
    poly(px, [(770, 760), (700, 400), (1010, 600)], SHADE)
    poly(px, [(770, 750), (710, 420), (990, 600)], WHITE)
    poly(px, [(800, 690), (750, 490), (930, 620)], INNER)
    poly(px, [(1280, 760), (1350, 400), (1040, 600)], SHADE)
    poly(px, [(1280, 750), (1340, 420), (1060, 600)], WHITE)
    poly(px, [(1250, 690), (1300, 490), (1120, 620)], INNER)
    # head with a soft lower edge
    ellipse(px, 1024, 920, 300, 296, SHADE)
    ellipse(px, 1024, 912, 292, 290, WHITE)
    # big bright blue eyes
    for ex in (885, 1163):
        ellipse(px, ex, 900, 92, 108, BLUE)
        ellipse(px, ex, 905, 52, 66, DARK)
        ellipse(px, ex - 22, 865, 26, 30, WHITE)
    # pink nose + happy mouth
    poly(px, [(994, 1030), (1054, 1030), (1024, 1066)], INNER)
    arc(px, 978, 1062, 70, 0.15 * math.pi, 0.85 * math.pi, DARK, th=14)
    arc(px, 1070, 1062, 70, 0.15 * math.pi, 0.85 * math.pi, DARK, th=14)
    # blush + whiskers
    ellipse(px, 760, 1010, 55, 32, (255, 190, 196), rot=-0.15)
    ellipse(px, 1288, 1010, 55, 32, (255, 190, 196), rot=0.15)
    for wy in (950, 990, 1030):
        line(px, 730, wy, 560, wy - 40, GREY, th=7)
        line(px, 1318, wy, 1488, wy - 40, GREY, th=7)

def draw_bow(px):
    # little red bow on the neck
    poly(px, [(1024, 1200), (900, 1130), (900, 1270)], RED)
    poly(px, [(1024, 1200), (1148, 1130), (1148, 1270)], RED)
    ellipse(px, 1024, 1200, 42, 42, RED_D)
    ellipse(px, 1024, 1200, 26, 26, RED)

def draw_paws(px):
    # front paws wrapped over the big heart
    for (cx, cy, rot) in ((850, 1330, 0.5), (1198, 1330, -0.5)):
        ellipse(px, cx, cy + 8, 110, 88, SHADE, rot=rot)
        ellipse(px, cx, cy, 104, 82, WHITE, rot=rot)
    for lx in (812, 850, 888):
        line(px, lx, 1312, lx, 1352, GREY, th=6)
    for lx in (1160, 1198, 1236):
        line(px, lx, 1312, lx, 1352, GREY, th=6)

def downsample(px):
    out = bytearray(W * H * 3)
    for y in range(H):
        for x in range(W):
            r = g = b = 0
            for dy in range(2):
                for dx in range(2):
                    i = ((y * 2 + dy) * B + (x * 2 + dx)) * 3
                    r += px[i]; g += px[i + 1]; b += px[i + 2]
            j = (y * W + x) * 3
            out[j] = r // 4; out[j + 1] = g // 4; out[j + 2] = b // 4
    return out

def write_png(path, rgb):
    raw = b"".join(b"\x00" + bytes(rgb[y * W * 3:(y + 1) * W * 3]) for y in range(H))
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)

def main():
    px = new_canvas()
    draw_background(px)
    draw_big_heart(px)
    draw_tail(px)
    draw_body(px)
    draw_head(px)
    draw_bow(px)
    draw_paws(px)
    os.makedirs("/output", exist_ok=True)
    write_png("/output/entry.png", downsample(px))

if __name__ == "__main__":
    main()
