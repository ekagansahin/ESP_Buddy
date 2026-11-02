"""Animated weather icons (procedural, 1-bit).

icon(code, is_day, size, t, n) -> PIL '1' image (size x size)
  code: WMO weather code (Open-Meteo), t: frame index, n: frames per loop
"""
import math
import random

from PIL import Image, ImageDraw

DESCRIPTION = {
    "en": {
        0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Rime fog",
        51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
        61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
        71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
        80: "Light showers", 81: "Showers", 82: "Heavy showers", 85: "Snow showers", 86: "Heavy snow showers",
        95: "Thunderstorm", 96: "Hailstorm", 99: "Hailstorm",
    },
    "tr": {
        0: "Açık", 1: "Çoğunlukla açık", 2: "Parçalı bulutlu", 3: "Kapalı", 45: "Sisli", 48: "Kırağılı sis",
        51: "Hafif çisenti", 53: "Çisenti", 55: "Yoğun çisenti", 56: "Dondurucu çisenti", 57: "Dondurucu çisenti",
        61: "Hafif yağmur", 63: "Yağmurlu", 65: "Şiddetli yağmur", 66: "Dondurucu yağmur", 67: "Dondurucu yağmur",
        71: "Hafif kar", 73: "Karlı", 75: "Yoğun kar", 77: "Kar taneleri",
        80: "Hafif sağanak", 81: "Sağanak", 82: "Şiddetli sağanak", 85: "Kar sağanağı", 86: "Yoğun kar sağanağı",
        95: "Gök gürültülü", 96: "Dolulu fırtına", 99: "Dolulu fırtına",
    },
}


def kind(code):
    if code == 0:
        return "clear"
    if code == 1:
        return "few_clouds"
    if code == 2:
        return "partly"
    if code == 3:
        return "overcast"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57):
        return "drizzle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "storm"
    return "overcast"


def description(code, lang):
    return DESCRIPTION[lang].get(code, "?")


# --- drawing helpers (40-unit coordinate space, scaled) -------------------------
class Pen:
    def __init__(self, size):
        self.s = size / 40.0
        self.img = Image.new("1", (size, size), 0)
        self.d = ImageDraw.Draw(self.img)

    def P(self, x, y):
        return (round(x * self.s), round(y * self.s))

    def circle(self, cx, cy, r, fill=1, outline=None):
        x0, y0 = self.P(cx - r, cy - r)
        x1, y1 = self.P(cx + r, cy + r)
        self.d.ellipse([x0, y0, x1, y1], fill=fill, outline=outline if outline is not None else fill)

    def line(self, x0, y0, x1, y1, color=1, width=1):
        self.d.line([self.P(x0, y0), self.P(x1, y1)], fill=color, width=max(1, round(width * self.s)))


def sun(p, cx, cy, r, t, n, rays=True):
    p.circle(cx, cy, r)
    if not rays:
        return
    a0 = 2 * math.pi * t / n / 4          # turns 1/4 per loop (seamless thanks to 8-fold symmetry)
    pulse = 1 + 0.15 * math.sin(2 * math.pi * t / n)
    for i in range(8):
        a = a0 + i * math.pi / 4
        r0, r1 = r + 3, (r + 3) + 5 * pulse
        p.line(cx + r0 * math.cos(a), cy + r0 * math.sin(a), cx + r1 * math.cos(a), cy + r1 * math.sin(a), width=2)


def moon(p, cx, cy, r, t, n, stars=True):
    p.circle(cx, cy, r)
    p.circle(cx + r * 0.55, cy - r * 0.35, r * 0.85, fill=0)
    if stars:
        rnd = random.Random(7)
        for i in range(4):
            x, y = rnd.uniform(24, 38), rnd.uniform(2, 20)
            if (t + i * 3) % n < n * 0.6:
                p.line(x - 1.5, y, x + 1.5, y)
                p.line(x, y - 1.5, x, y + 1.5)


def cloud(p, ox, oy, scale=1.0, outline=True):
    parts = [(10, 26, 7), (18, 20, 9), (27, 22, 8), (32, 27, 6)]
    if outline:
        for cx, cy, r in parts:
            p.circle(ox + cx * scale, oy + cy * scale, r * scale + 1.6, fill=0)
        x0, y0 = p.P(ox + 10 * scale, oy + 26 * scale)
        x1, y1 = p.P(ox + 32 * scale, oy + 33 * scale + 1.6)
        p.d.rectangle([x0, y0, x1, y1], fill=0)
    for cx, cy, r in parts:
        p.circle(ox + cx * scale, oy + cy * scale, r * scale)
    x0, y0 = p.P(ox + 10 * scale, oy + 26 * scale)
    x1, y1 = p.P(ox + 32 * scale, oy + 33 * scale)
    p.d.rectangle([x0, y0, x1, y1], fill=1)


def icon(code, is_day=True, size=40, t=0, n=12):
    p = Pen(size)
    k = kind(code)
    small = size < 24
    drift = math.sin(2 * math.pi * t / n)            # -1..1, cloud drift

    if k == "clear":
        if is_day:
            sun(p, 20, 20, 8, t, n)
        else:
            moon(p, 17, 21, 11, t, n, stars=not small)
    elif k in ("few_clouds", "partly"):
        if is_day:
            sun(p, 25, 14, 7, t, n)
        else:
            moon(p, 25, 14, 8, t, n, stars=False)
        cloud(p, -3 + drift * 1.5, 5 if k == "partly" else 9, 0.8 if k == "few_clouds" else 0.92)
    elif k == "overcast":
        cloud(p, 9 - drift * 1.5, -5, 0.7, outline=False)
        cloud(p, -1 + drift * 1.5, 3, 0.95)
    elif k == "fog":
        cloud(p, 1, -6, 0.9, outline=False)
        for i, y in enumerate((24, 29, 34)):
            dx = ((t * 2 + i * 5) % 12) - 6
            p.line(4 + dx, y, 22 + dx, y, width=2)
            p.line(26 + dx, y, 36 + dx, y, width=2)
    elif k in ("drizzle", "rain", "storm"):
        cloud(p, 2 + drift, -9, 0.9)
        if k == "storm" and (t % n) in range(n // 3, n // 3 + 3):
            pts = [(23, 19), (16, 29), (21, 29), (15, 39), (28, 26), (22, 26), (27, 19)]
            p.d.polygon([p.P(x, y) for x, y in pts], fill=1)
        count = 3 if k == "drizzle" else 5
        length = 2 if k == "drizzle" else 4
        for i in range(count):
            x = 9 + i * (24 / max(1, count - 1))
            phase = (i * 7) % 13
            y = 22 + ((t * 28 / n + phase) % 14)
            if k == "storm" and 12 < x < 26:
                continue
            p.line(x, y, x - 1.5, y + length, width=1.5 if not small else 2)
    elif k == "snow":
        cloud(p, 2 + drift, -9, 0.9)
        for i in range(4):
            x0 = 8 + i * 8
            phase = (i * 5) % 14
            y = 24 + ((t * 14 / n + phase) % 13)
            x = x0 + 1.5 * math.sin(2 * math.pi * (t / n + i / 4))
            r = 1.6 if not small else 2.2
            p.line(x - r, y, x + r, y)
            p.line(x, y - r, x, y + r)
            if not small:
                p.line(x - r * 0.7, y - r * 0.7, x + r * 0.7, y + r * 0.7)
                p.line(x - r * 0.7, y + r * 0.7, x + r * 0.7, y - r * 0.7)
    return p.img
