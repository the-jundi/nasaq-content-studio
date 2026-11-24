"""Hand-drawn art-director marks as SVG path data, deterministic per seed (nasaq-content-studio; from the tech brand kit).
circle: open loop that overshoots its start · arrow: one curved stroke + 2-stroke head · underline / strike: wavy lines.
Every path is a single stroke so reels can draw it with stroke-dashoffset."""
import math
import random

def _fmt(pts):
    d = f'M{pts[0][0]:.1f},{pts[0][1]:.1f}'
    for i in range(1, len(pts) - 1, 2):
        (x1, y1), (x2, y2) = pts[i], pts[i + 1]
        d += f' Q{x1:.1f},{y1:.1f} {x2:.1f},{y2:.1f}'
    return d

def circle(cx, cy, rx, ry, seed=1, overshoot=22, start=200, tilt=-6):
    """Open loop, slightly egg-shaped, starts at `start` degrees and runs ~360+overshoot, radius wobbling 4%."""
    r = random.Random(seed)
    total = 360 + overshoot
    n = 48
    ph = [r.random() * 6.28 for _ in range(3)]
    pts = []
    for i in range(n + 1):
        a = math.radians(start - total * i / n)  # counter-clockwise like a right-handed pen
        k = i / n
        wob = 1 + 0.035 * math.sin(3 * a + ph[0]) + 0.02 * math.sin(5 * a + ph[1])
        drift = 1 + 0.06 * k  # the loop opens up a little as it closes (spiral feel)
        x, y = rx * wob * drift * math.cos(a), ry * wob * drift * math.sin(a)
        t = math.radians(tilt)
        pts.append((cx + x * math.cos(t) - y * math.sin(t), cy + x * math.sin(t) + y * math.cos(t)))
    if len(pts) % 2 == 0:
        pts.append(pts[-1])
    return _fmt(pts)

def arrow(x0, y0, x1, y1, seed=2, bend=0.22, head=26):
    """Curved stroke from (x0,y0) to (x1,y1) then a two-stroke head at the end."""
    r = random.Random(seed)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy) or 1
    nx, ny = -dy / L, dx / L
    b = bend * L * (1 if r.random() > 0.5 else -1)
    cx, cy = mx + nx * b, my + ny * b
    body = f'M{x0:.1f},{y0:.1f} Q{cx:.1f},{cy:.1f} {x1:.1f},{y1:.1f}'
    ang = math.atan2(y1 - cy, x1 - cx)
    h1 = (x1 - head * math.cos(ang - 0.45), y1 - head * math.sin(ang - 0.45))
    h2 = (x1 - head * math.cos(ang + 0.5), y1 - head * math.sin(ang + 0.5))
    headp = f'M{h1[0]:.1f},{h1[1]:.1f} L{x1:.1f},{y1:.1f} L{h2[0]:.1f},{h2[1]:.1f}'
    return body, headp

def underline(x0, x1, y, seed=3, amp=5):
    """Wavy underline drawn right-to-left (Arabic hand), slight upward drift at the end."""
    r = random.Random(seed)
    n = 8
    pts = []
    for i in range(n + 1):
        k = i / n
        x = x1 - (x1 - x0) * k
        pts.append((x, y + amp * math.sin(k * 5 + r.random()) - 6 * k))
    if len(pts) % 2 == 0:
        pts.append(pts[-1])
    return _fmt(pts)

def strike(x0, y0, x1, y1, seed=4):
    r = random.Random(seed)
    mx, my = (x0 + x1) / 2 + r.uniform(-6, 6), (y0 + y1) / 2 + r.uniform(-6, 6)
    return f'M{x0:.1f},{y0:.1f} Q{mx:.1f},{my:.1f} {x1:.1f},{y1:.1f}'

def tick(x, y, s=34, seed=5):
    r = random.Random(seed)
    return f'M{x:.1f},{y:.1f} L{x + s*0.35:.1f},{y + s*0.4 + r.uniform(-2,2):.1f} L{x + s:.1f},{y - s*0.55:.1f}'

def cropmarks(x, y, w, h, gap=12, arm=26):
    """Printer's crop marks just outside the four corners of a rectangle."""
    d = []
    for cx, sx in ((x, -1), (x + w, 1)):
        for cy, sy in ((y, -1), (y + h, 1)):
            d.append(f'M{cx + sx*gap:.1f},{cy:.1f} h{sx*arm}')
            d.append(f'M{cx:.1f},{cy + sy*gap:.1f} v{sy*arm}')
    return ' '.join(d)
