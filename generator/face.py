"""ESP_Buddy's face: robot-style rounded eyes acting out moods (128x64, 1-bit).

face_animation(mood) -> [(PIL '1' image, ms), ...]
"""
import math
import random

from PIL import Image, ImageChops, ImageDraw

from font import font

W, H = 128, 64
LEFT, RIGHT = (38, 28), (90, 28)
EW, EH, ER = 30, 34, 9        # eye width, height, corner radius

MOODS = {
    "en": {"curious": "Curious", "happy": "Happy", "laugh": "Laughing", "shock": "Shocked", "sleepy": "Sleepy",
           "love": "In love", "dizzy": "Dizzy", "wink": "Winking", "angry": "Angry", "sad": "Sad",
           "cool": "Cool", "excited": "Excited", "party": "Party", "cold": "Freezing"},
    "tr": {"curious": "Meraklı", "happy": "Mutlu", "laugh": "Kahkaha", "shock": "Şok", "sleepy": "Uykulu",
           "love": "Aşık", "dizzy": "Sersem", "wink": "Göz kırpıyor", "angry": "Kızgın", "sad": "Üzgün",
           "cool": "Havalı", "excited": "Heyecanlı", "party": "Parti", "cold": "Üşüyor"},
}


def _canvas():
    im = Image.new("1", (W, H), 0)
    return im, ImageDraw.Draw(im)


def _lerp(a, b, f):
    return a + (b - a) * f


def _ease(f):
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, f)))


# --- eye shapes -----------------------------------------------------------------
def eye(d, cx, cy, w=EW, h=EH, r=ER):
    h = max(2, h)
    r = min(r, h / 2, w / 2)
    d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], radius=r, fill=1)


def eye_happy(d, cx, cy, w=EW, h=EH, thickness=0.45):
    eye(d, cx, cy, w, h)
    d.ellipse([cx - w * 0.75, cy - h / 2 + h * thickness, cx + w * 0.75, cy + h * 1.2], fill=0)


def eye_cut(d, cx, cy, inner_side, cut_inner=True, w=EW, h=EH, depth=0.5):
    """cut_inner=True: angry (inner top corner cut); False: sad (outer top corner cut)."""
    eye(d, cx, cy, w, h)
    x_in = cx + inner_side * w / 2
    x_out = cx - inner_side * w / 2
    y0 = cy - h / 2 - 1
    if cut_inner:
        pts = [(x_out - 2 * inner_side, y0 - 2), (x_in + 2 * inner_side, y0 - 2), (x_in + 2 * inner_side, y0 + h * depth)]
    else:
        pts = [(x_in + 2 * inner_side, y0 - 2), (x_out - 2 * inner_side, y0 - 2), (x_out - 2 * inner_side, y0 + h * depth)]
    d.polygon(pts, fill=0)


def eye_ring(d, cx, cy, r, pupil_r, dx=0, dy=0):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=1)
    d.ellipse([cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4], fill=0)
    d.ellipse([cx + dx - pupil_r, cy + dy - pupil_r, cx + dx + pupil_r, cy + dy + pupil_r], fill=1)


def heart(d, cx, cy, s, color=1):
    r = s * 0.27
    d.ellipse([cx - 2 * r, cy - s * 0.32 - r, cx, cy - s * 0.32 + r], fill=color)
    d.ellipse([cx, cy - s * 0.32 - r, cx + 2 * r, cy - s * 0.32 + r], fill=color)
    d.polygon([(cx - 2 * r - 0.3, cy - s * 0.26), (cx + 2 * r + 0.3, cy - s * 0.26), (cx, cy + s * 0.42)], fill=color)


def star(d, cx, cy, R, angle=0.0, color=1, points=5, inner=0.45):
    pts = []
    for i in range(points * 2):
        r = R if i % 2 == 0 else R * inner
        a = angle + i * math.pi / points - math.pi / 2
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=color)


def spiral(d, cx, cy, R, angle):
    pts = []
    for i in range(70):
        th = i * 0.27
        r = R * i / 70
        pts.append((cx + r * math.cos(th + angle), cy + r * math.sin(th + angle)))
    d.line(pts, fill=1, width=2)


def sparkle(d, x, y, r):
    d.line([(x - r, y), (x + r, y)], fill=1)
    d.line([(x, y - r), (x, y + r)], fill=1)
    if r >= 3:
        d.point([(x - 1, y - 1), (x + 1, y + 1), (x - 1, y + 1), (x + 1, y - 1)], fill=1)


def drop(d, x, y, s=4):
    d.ellipse([x - s, y - s + 2, x + s, y + s + 2], fill=1)
    d.polygon([(x - s + 1, y + 1), (x + s - 1, y + 1), (x, y - s * 1.6)], fill=1)


def mouth_smile(d, cx, cy, w=16, h=8):
    d.arc([cx - w / 2, cy - h, cx + w / 2, cy + h / 2], 20, 160, fill=1, width=2)


def mouth_frown(d, cx, cy, w=14, h=8):
    d.arc([cx - w / 2, cy, cx + w / 2, cy + h * 1.4], 200, 340, fill=1, width=2)


def mouth_o(d, cx, cy, r):
    d.ellipse([cx - r, cy - r * 1.2, cx + r, cy + r * 1.2], fill=1)
    if r > 3:
        d.ellipse([cx - r + 2, cy - r * 1.2 + 2, cx + r - 2, cy + r * 1.2 - 2], fill=0)


def mouth_open(d, cx, cy, w, h):
    d.pieslice([cx - w / 2, cy - h, cx + w / 2, cy + h], 0, 180, fill=1)


def blush(d, dy=0):
    for (cx, cy) in (LEFT, RIGHT):
        for k in range(3):
            x = cx - 8 + k * 6
            d.line([(x, cy + 22 + dy), (x + 3, cy + 19 + dy)], fill=1)


# --- particles (seamless loops) ----------------------------------------------------
def particles(n_frames, count, seed, laps=1, area=(0, W, -6, H + 6)):
    rnd = random.Random(seed)
    x0, x1, y0, y1 = area
    span = y1 - y0
    ps = [(rnd.uniform(x0, x1), rnd.uniform(0, span), rnd.choice([1, 2]) * laps, rnd.random()) for _ in range(count)]

    def positions(t):
        for x, y, lap, phase in ps:
            yy = (y + span * lap * t / n_frames) % span + y0
            yield x, yy, phase
    return positions


# --- moods ----------------------------------------------------------------------
def _two_eyes(d, dx=0, dy=0, h_left=1.0, h_right=1.0, w=EW, h=EH):
    eye(d, LEFT[0] + dx, LEFT[1] + dy, w, h * h_left)
    eye(d, RIGHT[0] + dx, RIGHT[1] + dy, w, h * h_right)


def _blink(t, start):
    seq = [1, 0.55, 0.08, 0.08, 0.55, 1]
    i = t - start
    return seq[i] if 0 <= i < len(seq) else 1


def curious(n=44):
    path = [(0, 0, 0), (6, 0, 0), (10, -16, 0), (17, -16, 0), (21, 15, -3), (28, 15, -3), (32, 0, 2), (36, 0, 0), (n, 0, 0)]
    out = []
    for t in range(n):
        for (a, ax, ay), (b, bx, by) in zip(path, path[1:]):
            if a <= t <= b:
                f = _ease((t - a) / max(1, b - a))
                dx, dy = _lerp(ax, bx, f), _lerp(ay, by, f)
                break
        k = _blink(t, 37)
        im, d = _canvas()
        left = 1 + max(0, -dx) / 60 - max(0, dx) / 90
        right = 1 + max(0, dx) / 60 - max(0, -dx) / 90
        _two_eyes(d, dx, dy, left * k, right * k)
        out.append((im, 70))
    return out


def happy(n=24):
    out = []
    for t in range(n):
        im, d = _canvas()
        dy = round(2 * math.sin(2 * math.pi * t / n))
        eye_happy(d, LEFT[0], LEFT[1] + dy)
        eye_happy(d, RIGHT[0], RIGHT[1] + dy)
        blush(d, dy - 2)
        mouth_smile(d, 64, 55 + dy)
        out.append((im, 80))
    return out


def laugh(n=20):
    out = []
    rnd = random.Random(3)
    spots = [(rnd.randint(2, 20), rnd.randint(0, 50)) for _ in range(4)] + [(rnd.randint(104, 118), rnd.randint(0, 50)) for _ in range(4)]
    for t in range(n):
        im, d = _canvas()
        dy = -2 if t % 2 else 1
        eye_happy(d, LEFT[0], LEFT[1] + dy - 2, h=EH * 0.8, thickness=0.35)
        eye_happy(d, RIGHT[0], RIGHT[1] + dy - 2, h=EH * 0.8, thickness=0.35)
        h = 12 + (t % 2) * 3
        mouth_open(d, 64, 45 + dy, 28, h)
        d.pieslice([64 - 11, 45 + dy - (h - 3), 64 + 11, 45 + dy + (h - 3)], 0, 180, fill=0)
        d.ellipse([58, 45 + dy + h - 8, 70, 45 + dy + h], fill=1)
        x, y = spots[t % len(spots)]
        font("5x8").draw(im, x, y, "HA")
        out.append((im, 70))
    return out


def shock(n=34):
    out = []
    for t in range(n):
        im, d = _canvas()
        shake = (1 if t % 2 else -1) if t > 8 else 0
        if t < 4:
            _two_eyes(d)
        else:
            f = _ease((t - 4) / 4)
            r = _lerp(15, 18, f)
            pr = _lerp(7, 3, f)
            eye_ring(d, LEFT[0] + shake, LEFT[1] - 2, r, pr)
            eye_ring(d, RIGHT[0] + shake, RIGHT[1] - 2, r, pr)
            mouth_o(d, 64, 55, _lerp(2, 5, f))
        if t >= 8:
            drop(d, 113, 6 + (t - 8) * 1.6, 3)
        out.append((im, 70))
    return out


def sleepy(n=48):
    out = []
    for t in range(n):
        im, d = _canvas()
        if t < 32:
            lid = _lerp(0.5, 0.1, _ease(t / 30))
            nod = _lerp(0, 3, _ease(t / 30))
        elif t < 35:
            lid, nod = 0.75, -1
        else:
            lid = _lerp(0.75, 0.5, (t - 35) / (n - 35))
            nod = _lerp(-1, 0, (t - 35) / (n - 35))
        _two_eyes(d, 0, 4 + nod, lid, lid)
        for k in range(3):
            phase = ((t / n) + k / 3) % 1
            x = 100 + phase * 18
            y = 30 - phase * 30
            f = font("4x6") if phase < 0.33 else (font("6x10") if phase < 0.66 else font("7x14B"))
            f.draw(im, int(x), int(y), "z" if phase < 0.66 else "Z")
        out.append((im, 90))
    return out


def love(n=24):
    out = []
    hearts = particles(n, 6, 11, laps=-1)
    for t in range(n):
        im, d = _canvas()
        for x, y, phase in hearts(t):
            if not (20 < x < 108 and 8 < y < 50):
                heart(d, x + 2 * math.sin(2 * math.pi * (t / n + phase)), y, 8)
        s = 30 * (1 + 0.12 * math.sin(2 * math.pi * t / n * 2))
        heart(d, LEFT[0], LEFT[1] + 2, s)
        heart(d, RIGHT[0], RIGHT[1] + 2, s)
        mouth_smile(d, 64, 57, 12, 6)
        out.append((im, 80))
    return out


def dizzy(n=24):
    out = []
    for t in range(n):
        im, d = _canvas()
        a = 2 * math.pi * t / n
        dx, dy = 4 * math.sin(a), 2 * math.cos(a)
        spiral(d, LEFT[0] + dx, LEFT[1] + dy, 15, a * 2)
        spiral(d, RIGHT[0] + dx, RIGHT[1] + dy, 15, a * 2)
        for k in range(3):
            b = a + k * 2 * math.pi / 3
            star(d, 64 + 30 * math.cos(b) + dx, 5 + 3 * math.sin(b), 3.5, b)
        d.line([(54 + dx, 56), (60 + dx, 53), (66 + dx, 57), (72 + dx, 54)], fill=1, width=2)
        out.append((im, 70))
    return out


def wink(n=30):
    out = []
    for t in range(n):
        im, d = _canvas()
        eye(d, *LEFT)
        if 10 <= t <= 20:
            k = _ease((t - 10) / 3) if t < 14 else (1 if t < 18 else 1 - _ease((t - 18) / 3))
            if k > 0.7:
                d.arc([RIGHT[0] - 14, RIGHT[1] - 4, RIGHT[0] + 14, RIGHT[1] + 14], 200, 340, fill=1, width=4)
                if 13 <= t <= 18:
                    sparkle(d, 116, 10, 4 if t % 2 else 2)
            else:
                eye(d, RIGHT[0], RIGHT[1], EW, EH * (1 - k))
            d.arc([56, 46, 80, 58], 10, 120, fill=1, width=2)
        else:
            eye(d, *RIGHT)
        out.append((im, 80))
    return out


def angry(n=24):
    out = []
    for t in range(n):
        im, d = _canvas()
        dx = (2 if t % 2 else -2) if (t // 6) % 2 == 0 else 0
        eye_cut(d, LEFT[0] + dx, LEFT[1] + 3, inner_side=1, cut_inner=True, h=EH * 0.85)
        eye_cut(d, RIGHT[0] + dx, RIGHT[1] + 3, inner_side=-1, cut_inner=True, h=EH * 0.85)
        for k, x in enumerate((8, 120)):
            phase = ((t / n) * 2 + k * 0.5) % 1
            r = 2 + phase * 3
            y = 22 - phase * 20
            d.ellipse([x - r, y - r, x + r, y + r], outline=1)
        d.line([(56 + dx, 57), (72 + dx, 55)], fill=1, width=2)
        out.append((im, 60))
    return out


def sad(n=36, rain=True):
    out = []
    drops = particles(n, 14, 5, laps=2)
    for t in range(n):
        im, d = _canvas()
        if rain:
            for x, y, _ in drops(t):
                d.line([(x, y), (x - 1, y + 3)], fill=1)
        for (cx, cy), side in ((LEFT, 1), (RIGHT, -1)):
            d.rounded_rectangle([cx - EW / 2 - 2, cy - EH / 2, cx + EW / 2 + 2, cy + EH / 2 + 6], radius=8, fill=0)
            eye_cut(d, cx, cy + 5, inner_side=side, cut_inner=False, h=EH * 0.8, depth=0.45)
        f = (t % 24) / 24
        drop(d, LEFT[0] + 10, 40 + f * 22, 2.5)
        d.rectangle([52, 50, 76, 62], fill=0)
        mouth_frown(d, 64, 54)
        out.append((im, 90))
    return out


def cool(n=32):
    out = []
    for t in range(n):
        im, d = _canvas()
        dy = round(math.sin(2 * math.pi * t / n))
        y0 = 16 + dy
        lens = Image.new("1", (W, H), 0)
        dl = ImageDraw.Draw(lens)
        for cx in (LEFT[0], RIGHT[0]):
            dl.rounded_rectangle([cx - 20, y0, cx + 20, y0 + 22], radius=7, fill=1)
        dl.rectangle([58, y0, 70, y0 + 22], fill=0)
        im.paste(1, (0, 0), lens)
        d.line([(2, y0 + 1), (126, y0 + 1)], fill=1, width=3)
        if 6 <= t <= 22:
            p = (t - 6) / 16 * 70 - 15
            glint = Image.new("1", (W, H), 0)
            dg = ImageDraw.Draw(glint)
            for cx in (LEFT[0], RIGHT[0]):
                x = cx - 20 + p
                dg.line([(x, y0 + 22), (x + 12, y0)], fill=1, width=3)
                dg.line([(x + 7, y0 + 22), (x + 19, y0)], fill=1, width=1)
            glint = ImageChops.logical_and(glint, lens)
            im.paste(0, (0, 0), glint)
        d.arc([62, 44 + dy, 84, 56 + dy], 20, 110, fill=1, width=2)
        out.append((im, 80))
    return out


def excited(n=24):
    out = []
    rnd = random.Random(9)
    pts = [(rnd.randint(4, 124), rnd.randint(2, 62)) for _ in range(10)]
    for t in range(n):
        im, d = _canvas()
        dy = -round(abs(math.sin(2 * math.pi * t / n * 2)) * 4)
        a = 2 * math.pi * t / n / 5
        R = 17 * (1 + 0.1 * math.sin(2 * math.pi * t / n * 4))
        star(d, LEFT[0], LEFT[1] + dy + 2, R, a)
        star(d, RIGHT[0], RIGHT[1] + dy + 2, R, -a)
        mouth_open(d, 64, 50 + dy, 20, 9)
        for i, (x, y) in enumerate(pts):
            if (t + i * 3) % 8 < 4 and not (18 < x < 110 and 8 < y < 56):
                sparkle(d, x, y, 2 + (i % 2))
        out.append((im, 70))
    return out


def party(n=36):
    out = []
    confetti = particles(n, 26, 21, laps=1)
    for t in range(n):
        im, d = _canvas()
        dy = round(2 * math.sin(2 * math.pi * t / n * 2))
        eye_happy(d, LEFT[0], LEFT[1] + dy)
        eye_happy(d, RIGHT[0], RIGHT[1] + dy)
        mouth_open(d, 64, 48 + dy, 22, 10)
        for x, y, phase in confetti(t):
            x = x + 3 * math.sin(2 * math.pi * (t / n * 2 + phase))
            if phase < 0.5:
                d.rectangle([x, y, x + 1, y + 1], fill=1)
            else:
                d.line([(x, y), (x + 2, y + 1)], fill=1)
        out.append((im, 80))
    return out


def cold(n=24):
    out = []
    snow = particles(n, 16, 13, laps=1)
    for t in range(n):
        im, d = _canvas()
        for x, y, phase in snow(t):
            x = x + 2 * math.sin(2 * math.pi * (t / n + phase))
            sparkle(d, x, y, 1)
        dx = 1 if t % 2 else -1
        for (cx, cy) in (LEFT, RIGHT):
            d.rounded_rectangle([cx - EW / 2 - 2, cy - 12, cx + EW / 2 + 2, cy + 12], radius=4, fill=0)
            eye(d, cx + dx, cy + 2, EW, EH * 0.45)
        a = 3 if t % 2 else 1
        pts = [(50 + i * 4, 55 + (a if i % 2 else -a)) for i in range(8)]
        d.rectangle([46, 49, 82, 61], fill=0)
        d.line(pts, fill=1, width=1)
        d.rectangle([48, 51, 80, 59], outline=1)
        out.append((im, 70))
    return out


ANIMATIONS = {
    "curious": curious, "happy": happy, "laugh": laugh, "shock": shock, "sleepy": sleepy, "love": love,
    "dizzy": dizzy, "wink": wink, "angry": angry, "sad": sad, "cool": cool,
    "excited": excited, "party": party, "cold": cold,
}


def face_animation(mood):
    return ANIMATIONS[mood]()
