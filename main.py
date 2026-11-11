# Pumpkin Purr v6 - cream kitten in a pumpkin (final)
import zlib
import struct
import math
import os

# Configuration
WIDTH, HEIGHT = 1024, 1024
SCALE = 2
S_WIDTH, S_HEIGHT = WIDTH * SCALE, HEIGHT * SCALE
BG_COLOR = (255, 243, 224)
PUMPKIN_COLOR = (245, 124, 0)
PUMPKIN_DARK = (230, 81, 0)
PUMPKIN_LIGHT = (255, 183, 77)
KITTEN_COLOR = (255, 248, 225)
EYE_COLOR = (255, 143, 0)
PINK = (255, 182, 193)
GREEN = (76, 175, 80)
DARK = (50, 50, 50)

# Buffer (2048x2048)
buffer = [[BG_COLOR for _ in range(S_WIDTH)] for _ in range(S_HEIGHT)]

def set_px(x, y, color):
    if 0 <= x < S_WIDTH and 0 <= y < S_HEIGHT:
        buffer[y][x] = color

def draw_ellipse(cx, cy, rx, ry, color, stroke=0):
    min_x = max(0, int((cx - rx) * SCALE))
    max_x = min(S_WIDTH, int((cx + rx) * SCALE + 1))
    min_y = max(0, int((cy - ry) * SCALE))
    max_y = min(S_HEIGHT, int((cy + ry) * SCALE + 1))
    for y in range(min_y, max_y):
        for x in range(min_x, max_x):
            d = ((x / SCALE - cx) / rx) ** 2 + ((y / SCALE - cy) / ry) ** 2
            if d <= 1:
                if stroke > 0 and d > (1 - stroke / max(rx, ry)) ** 2:
                    buffer[y][x] = DARK
                else:
                    buffer[y][x] = color

def draw_circle(cx, cy, r, color, stroke=0):
    draw_ellipse(cx, cy, r, r, color, stroke)

def draw_triangle(p1, p2, p3, color, stroke=0):
    # Barycentric fill at supersampled resolution
    min_x = max(0, int(min(p1[0], p2[0], p3[0]) * SCALE))
    max_x = min(S_WIDTH, int(max(p1[0], p2[0], p3[0]) * SCALE + 1))
    min_y = max(0, int(min(p1[1], p2[1], p3[1]) * SCALE))
    max_y = min(S_HEIGHT, int(max(p1[1], p2[1], p3[1]) * SCALE + 1))
    (x1, y1), (x2, y2), (x3, y3) = p1, p2, p3
    den = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
    if den == 0:
        return
    for y in range(min_y, max_y):
        for x in range(min_x, max_x):
            px, py = x / SCALE, y / SCALE
            a = ((y2 - y3) * (px - x3) + (x3 - x2) * (py - y3)) / den
            b = ((y3 - y1) * (px - x3) + (x1 - x3) * (py - y3)) / den
            c = 1 - a - b
            if a >= 0 and b >= 0 and c >= 0:
                # stroke: darken near edges
                if stroke > 0 and (a < 0.06 or b < 0.06 or c < 0.06):
                    buffer[y][x] = DARK
                else:
                    buffer[y][x] = color

def draw_line(x1, y1, x2, y2, color, width=2):
    steps = int(max(abs(x2 - x1), abs(y2 - y1)) * SCALE * 2) + 1
    for i in range(steps + 1):
        t = i / steps
        px = x1 + (x2 - x1) * t
        py = y1 + (y2 - y1) * t
        r = width * SCALE / 2
        for dy in range(-int(r) - 1, int(r) + 2):
            for dx in range(-int(r) - 1, int(r) + 2):
                if dx * dx + dy * dy <= r * r:
                    set_px(int(px * SCALE) + dx, int(py * SCALE) + dy, color)

def draw_arc(cx, cy, r, a0, a1, color, width=3):
    # arc in radians, y down
    steps = int(abs(a1 - a0) * r * SCALE) + 1
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        px = cx + r * math.cos(a)
        py = cy + r * math.sin(a)
        rr = width * SCALE / 2
        for dy in range(-int(rr) - 1, int(rr) + 2):
            for dx in range(-int(rr) - 1, int(rr) + 2):
                if dx * dx + dy * dy <= rr * rr:
                    set_px(int(px * SCALE) + dx, int(py * SCALE) + dy, color)

# ---- Background leaves (small, scattered) ----
draw_ellipse(150, 200, 18, 10, (255, 167, 38))
draw_ellipse(880, 620, 16, 9, (255, 167, 38))
draw_ellipse(130, 760, 15, 9, (255, 213, 79))
draw_ellipse(900, 300, 14, 8, (255, 213, 79))

# ---- Butterfly (top right) ----
draw_ellipse(845, 190, 16, 22, (255, 143, 0))
draw_ellipse(875, 190, 16, 22, (255, 143, 0))
draw_ellipse(860, 205, 5, 12, DARK)

# ---- Pumpkin ----
draw_ellipse(512, 690, 360, 260, PUMPKIN_COLOR, stroke=4)
# ribs (darker orange vertical ellipses, drawn over pumpkin)
for rx_x in (360, 440, 584, 664):
    draw_ellipse(rx_x, 690, 10, 235, PUMPKIN_DARK)
# highlight (upper left)
draw_ellipse(350, 540, 80, 45, PUMPKIN_LIGHT)
# stem peeking from behind head (top right of pumpkin)
draw_ellipse(640, 420, 14, 26, GREEN)
draw_ellipse(668, 448, 26, 12, GREEN)

# ---- Kitten ears (behind head circle, drawn first) ----
# left ear
draw_triangle((392, 340), (468, 318), (420, 235), KITTEN_COLOR, stroke=3)
draw_triangle((408, 322), (452, 308), (424, 262), PINK)
# right ear
draw_triangle((556, 318), (632, 340), (604, 235), KITTEN_COLOR, stroke=3)
draw_triangle((572, 308), (616, 322), (600, 262), PINK)

# ---- Kitten head ----
draw_circle(512, 430, 150, KITTEN_COLOR, stroke=4)

# ---- Eyes (big amber, black pupil, white highlight) ----
draw_circle(450, 420, 42, EYE_COLOR, stroke=4)
draw_circle(574, 420, 42, EYE_COLOR, stroke=4)
draw_circle(450, 420, 15, (0, 0, 0))
draw_circle(574, 420, 15, (0, 0, 0))
draw_circle(438, 408, 9, (255, 255, 255))
draw_circle(562, 408, 9, (255, 255, 255))

# ---- Nose / blush / mouth ----
draw_ellipse(512, 480, 15, 10, PINK)
draw_circle(400, 490, 22, PINK)
draw_circle(624, 490, 22, PINK)
# happy mouth: two small arcs below nose
draw_arc(496, 498, 16, 0.15 * math.pi, 0.85 * math.pi, DARK, width=3)
draw_arc(528, 498, 16, 0.15 * math.pi, 0.85 * math.pi, DARK, width=3)

# ---- Whiskers (3 per side) ----
for (x1, y1, x2, y2) in (
    (392, 478, 318, 462), (390, 500, 312, 500), (392, 522, 318, 538),
    (632, 478, 706, 462), (634, 500, 712, 500), (632, 522, 706, 538),
):
    draw_line(x1, y1, x2, y2, DARK, width=2)

# ---- Paws on pumpkin rim ----
draw_ellipse(420, 700, 46, 30, KITTEN_COLOR, stroke=3)
draw_ellipse(604, 700, 46, 30, KITTEN_COLOR, stroke=3)

# ---- Downsampling ----
final_buffer = [[(0, 0, 0) for _ in range(WIDTH)] for _ in range(HEIGHT)]
for y in range(HEIGHT):
    for x in range(WIDTH):
        r, g, b = 0, 0, 0
        for sy in range(SCALE):
            for sx in range(SCALE):
                pr, pg, pb = buffer[y * SCALE + sy][x * SCALE + sx]
                r += pr
                g += pg
                b += pb
        final_buffer[y][x] = (r // (SCALE ** 2), g // (SCALE ** 2), b // (SCALE ** 2))

# ---- PNG writing ----
def write_png(filename, data, w, h):
    def crc32(d):
        return zlib.crc32(d) & 0xffffffff

    def write_chunk(f, typ, d):
        f.write(struct.pack('>I', len(d)))
        f.write(typ)
        f.write(d)
        f.write(struct.pack('>I', crc32(typ + d)))

    with open(filename, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        write_chunk(f, b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
        rows = []
        for y in range(h):
            row = bytearray(b'\x00')
            for x in range(w):
                r, g, b = data[y][x]
                row += bytes((r, g, b))
            rows.append(bytes(row))
        write_chunk(f, b'IDAT', zlib.compress(b''.join(rows), 6))
        write_chunk(f, b'IEND', b'')

os.makedirs('/output', exist_ok=True)
write_png('/output/entry.png', final_buffer, WIDTH, HEIGHT)
os.makedirs('output', exist_ok=True)
write_png('output/entry.png', final_buffer, WIDTH, HEIGHT)
