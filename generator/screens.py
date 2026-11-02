"""Rendering of every screen. Each function returns [(PIL '1' 128x64, ms), ...] or None when there is no data.

All user-visible text goes through T[lang] so every screen exists in English and Turkish.
"""
import datetime as dt
import math
import random

from PIL import Image, ImageDraw

import icons
import turkey_map
from font import font

W, H = 128, 64

T = {
    "en": {
        "months": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                   "October", "November", "December"],
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "days_short": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "today": "Today", "tomorrow": "Tomorrow",
        "feels": "Feels", "humidity": "RH", "kmh": "km/h",
        "next_12h": "Next 12 hours", "rain": "rain", "no_rain": "no rain",
        "sun": "Sun", "moon": "Moon", "waxing": "waxing", "waning": "waning", "day_len": "{h} h {m} min",
        "phases": ["New Moon", "Crescent", "First Quarter", "Gibbous", "Full Moon", "Gibbous", "Last Quarter",
                   "Crescent", "New Moon"],
        "air_quality": "Air quality", "aqi_index": "European index",
        "aqi_levels": ["Good", "Fair", "Moderate", "Poor", "Very poor", "Extremely poor"],
        "markets": "Markets", "gold": "Gold (g)", "cbrt": "CBRT $", "days_abbr": "d",
        "quakes_24h": "Last 24h: {n} quakes", "quakes_title": "Earthquakes (Kandilli)", "no_quakes": "No quakes in the last 24h",
        "next_holiday": "Next holiday", "tomorrow_excl": "tomorrow!", "day": "day", "days_word": "days", "today_caps": "TODAY",
        "on_this_day": "On this day", "quote": "Quote of the day",
    },
    "tr": {
        "months": ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim",
                   "Kasım", "Aralık"],
        "days": ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"],
        "days_short": ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"],
        "today": "Bugün", "tomorrow": "Yarın",
        "feels": "His", "humidity": "Nem", "kmh": "km/sa",
        "next_12h": "Sonraki 12 saat", "rain": "yağış", "no_rain": "yağış yok",
        "sun": "Güneş", "moon": "Ay", "waxing": "büyüyor", "waning": "küçülüyor", "day_len": "{h} sa {m} dk",
        "phases": ["Yeni Ay", "Hilal", "İlk Dördün", "Şişkin Ay", "Dolunay", "Şişkin Ay", "Son Dördün", "Hilal",
                   "Yeni Ay"],
        "air_quality": "Hava kalitesi", "aqi_index": "Avrupa endeksi",
        "aqi_levels": ["İyi", "Makul", "Orta", "Kötü", "Çok kötü", "Aşırı kötü"],
        "markets": "Piyasa", "gold": "Gram altın", "cbrt": "TCMB $", "days_abbr": "g",
        "quakes_24h": "Son 24 saat: {n} deprem", "quakes_title": "Deprem (Kandilli)", "no_quakes": "Son 24 saatte kayıt yok",
        "next_holiday": "Sıradaki tatil", "tomorrow_excl": "yarın!", "day": "gün", "days_word": "gün", "today_caps": "BUGÜN",
        "on_this_day": "Bugün tarihte", "quote": "Günün sözü",
    },
}


# --- helpers ------------------------------------------------------------------------
def canvas():
    im = Image.new("1", (W, H), 0)
    return im, ImageDraw.Draw(im)


def number(x, decimals=2, lang="tr"):
    s = f"{x:,.{decimals}f}"
    if lang == "tr":
        s = s.replace(",", "_").replace(".", ",").replace("_", ".")
    return s


def percent(x, decimals=2, lang="tr"):
    v = number(x, decimals, lang)
    return f"%{v}" if lang == "tr" else f"{v}%"


def degrees(x):
    return f"{round(x):d}°" if x is not None else "-"


def header(im, d, left, right=None):
    f = font("5x8")
    f.draw(im, 0, 0, left)
    if right:
        f.right(im, W, 0, right)
    for x in range(0, W, 2):
        d.point((x, 9), fill=1)


def arrow(d, x, y, up=True, s=3):
    if up:
        d.polygon([(x, y + s), (x + s, y - s + 1), (x + 2 * s, y + s)], fill=1)
    else:
        d.polygon([(x, y - s + 1), (x + s, y + s), (x + 2 * s, y - s + 1)], fill=1)


def date_text(t: dt.date, lang):
    L = T[lang]
    if lang == "tr":
        return f"{t.day} {L['months'][t.month - 1]} {L['days'][t.weekday()]}"
    return f"{L['days'][t.weekday()]}, {t.day} {L['months'][t.month - 1]}"


def hhmm(iso):
    return iso[11:16] if iso and len(iso) >= 16 else "--:--"


def fit(text, width, fonts=("5x8", "4x6")):
    """The first font in which the text fits (the last one otherwise)."""
    for name in fonts:
        if font(name).width(text) <= width:
            return font(name)
    return font(fonts[-1])


# --- clock (drawn by the device; this is only the preview — same layout as the firmware) ---
def clock_top_line(now: dt.datetime, lang):
    L = T[lang]
    if lang == "tr":
        return f"{now.day} {L['months'][now.month - 1]} {L['days'][now.weekday()]}"
    return f"{L['days_short'][now.weekday()]} {now.day} {L['months'][now.month - 1]}"


def clock_preview(info, now: dt.datetime, lang):
    im, d = canvas()
    ft, fc = font("6x10"), font("spleen-16x32")
    top = clock_top_line(now, lang)
    ft.draw(im, (W - ft.width(top)) // 2, 8 - ft.ascent, top)
    s = f"{now:%H:%M}"
    fc.draw(im, (W - fc.width(s)) // 2, 42 - fc.ascent, s)
    sec = now.second
    for x in range(14, 115, 2):
        d.point((x, 47), fill=1)
    if sec:
        d.rectangle([14, 46, 14 + round(100 * sec / 59), 47], fill=1)
    ft.draw(im, (W - ft.width(info)) // 2, 62 - ft.ascent, info)
    return [(im, 1000)]


# --- weather ------------------------------------------------------------------------
def weather_now(wx, city, lang):
    L = T[lang]
    s = wx["now"]
    n = 12
    out = []
    for t in range(n):
        im, d = canvas()
        header(im, d, city.upper(), hhmm(s.get("time")))
        im.paste(icons.icon(s["code"], s["is_day"], 40, t, n), (1, 12))
        font("helvB24").draw(im, 46, 7, degrees(s["temp"]))
        desc = icons.description(s["code"], lang)
        fd = font("6x10") if font("6x10").width(desc) <= 82 else font("5x8")
        fd.draw(im, 46, 39, fd.ellipsize(desc, 82))
        hum = percent(round(s.get("humidity") or 0), 0, lang)
        feels = f"{L['feels']} {degrees(s.get('feels_like'))}"
        line = f"{feels}  {L['humidity']} {hum}"
        if font("5x8").width(line) > 82:
            line = f"{feels} {L['humidity']} {hum}"
        fit(line, 82).draw(im, 46, 50, line)
        font("4x6").center(im, 56, f"{round(s.get('wind') or 0)} {L['kmh']}", x0=0, x1=42)
        out.append((im, 110))
    return out


def weather_hourly(wx, lang):
    L = T[lang]
    hr = wx["hourly"][:13]
    if len(hr) < 4:
        return None
    im, d = canvas()
    max_rain = max(x["rain"] for x in hr)
    header(im, d, L["next_12h"], f"{L['rain']} {percent(max_rain, 0, lang)}" if max_rain else L["no_rain"])
    t = [x["temp"] for x in hr]
    lo, hi = min(t), max(t)
    if hi - lo < 4:
        hi, lo = (hi + lo) / 2 + 2, (hi + lo) / 2 - 2
    x0, x1, y0, y1 = 16, 124, 14, 36
    pts = []
    for i, v in enumerate(t):
        x = x0 + (x1 - x0) * i / (len(t) - 1)
        y = y1 - (v - lo) / (hi - lo) * (y1 - y0)
        pts.append((x, y))
    d.line(pts, fill=1, width=1)
    for x, y in pts[::3]:
        d.ellipse([x - 1, y - 1, x + 1, y + 1], fill=1)
    f4 = font("4x6")
    f4.draw(im, 0, 12, degrees(max(t)))
    f4.draw(im, 0, 32, degrees(min(t)))
    for i, x in enumerate(hr):
        bx = x0 + (x1 - x0) * i / (len(t) - 1)
        bh = round(x["rain"] / 100 * 11)
        if bh:
            d.rectangle([bx - 2, 50 - bh, bx + 2, 50], fill=1)
        else:
            d.point((bx, 50), fill=1)
    f4.draw(im, 0, 44, "%")
    for i in range(0, len(hr), 3):
        bx = x0 + (x1 - x0) * i / (len(t) - 1)
        f4.center(im, 56, hr[i]["hour"], x0=int(bx) - 6, x1=int(bx) + 7)
    return [(im, 1000)]


def weather_3day(wx, today: dt.date, lang):
    L = T[lang]
    days = wx["daily"][:3]
    if len(days) < 3:
        return None
    n = 8
    out = []
    for t in range(n):
        im, d = canvas()
        for i, g in enumerate(days):
            x0 = i * 43
            date = dt.date.fromisoformat(g["date"])
            if date == today:
                name = L["today"]
            elif date == today + dt.timedelta(days=1) and font("6x10").width(L["tomorrow"]) <= 42:
                name = L["tomorrow"]
            else:
                name = L["days_short"][date.weekday()]
            font("6x10").center(im, 0, name, x0=x0, x1=x0 + 42)
            im.paste(icons.icon(g["code"], True, 16, t, n), (x0 + 13, 11))
            font("helvB12").center(im, 27, degrees(g["max"]), x0=x0, x1=x0 + 42)
            font("6x10").center(im, 43, degrees(g["min"]), x0=x0, x1=x0 + 42)
            font("4x6").center(im, 57, percent(g["rain"], 0, lang), x0=x0, x1=x0 + 42)
            if i:
                for y in range(0, H, 3):
                    d.point((x0 - 1, y), fill=1)
        out.append((im, 150))
    return out


def moon_phase(when: dt.datetime):
    jd = when.timestamp() / 86400.0 + 2440587.5
    P = 29.530588853
    age = (jd - 2451550.1) % P
    lit = (1 - math.cos(2 * math.pi * age / P)) / 2
    limits = [1.84, 5.53, 9.22, 12.91, 16.61, 20.30, 23.99, 27.68, P + 1]
    idx = next(i for i, s in enumerate(limits) if age < s)
    return age, lit, idx, age < P / 2


def draw_moon(im, cx, cy, r, age):
    P = 29.530588853
    k = math.cos(2 * math.pi * age / P)
    waxing = age < P / 2
    px = im.load()
    for y in range(-r, r + 1):
        for x in range(-r, r + 1):
            if x * x + y * y > r * r:
                continue
            yy = y / r
            xx = x / r
            edge = k * math.sqrt(max(0.0, 1 - yy * yy))
            if (xx > edge) if waxing else (xx < -edge):
                px[cx + x, cy + y] = 1
    ImageDraw.Draw(im).ellipse([cx - r, cy - r, cx + r, cy + r], outline=1)


def sun_moon(wx, when: dt.datetime, lang):
    L = T[lang]
    g = wx["daily"][0]
    rise, sset = g["sunrise"], g["sunset"]
    try:
        span = dt.datetime.fromisoformat(sset) - dt.datetime.fromisoformat(rise)
        mins = int(span.total_seconds() // 60)
        day_len = L["day_len"].format(h=mins // 60, m=mins % 60)
    except ValueError:
        day_len = ""
    age, lit, idx, waxing = moon_phase(when)
    out = []
    rnd = random.Random(4)
    stars = [(rnd.randint(68, 126), rnd.randint(11, 40)) for _ in range(6)]
    for t in range(2):
        im, d = canvas()
        header(im, d, L["sun"], L["moon"])
        cx, cy, R = 32, 40, 24
        for a in range(0, 181, 9):
            r = math.radians(a)
            d.point((cx - R * math.cos(r), cy - R * 0.85 * math.sin(r)), fill=1)
        d.line([(4, cy), (60, cy)], fill=1)
        d.ellipse([cx - 5, cy - R * 0.85 - 5, cx + 5, cy - R * 0.85 + 5], fill=1)
        f5 = font("5x8")
        arrow(d, 1, 46, True, 2)
        f5.draw(im, 7, 42, hhmm(rise))
        arrow(d, 34, 46, False, 2)
        f5.draw(im, 40, 42, hhmm(sset))
        font("4x6").center(im, 55, day_len, x0=0, x1=64)
        for i, (x, y) in enumerate(stars):
            if abs(x - 96) > 16 or abs(y - 27) > 16:
                if (i + t) % 2:
                    d.point((x, y), fill=1)
                else:
                    d.line([(x - 1, y), (x + 1, y)], fill=1)
                    d.line([(x, y - 1), (x, y + 1)], fill=1)
        draw_moon(im, 96, 27, 13, age)
        fit(L["phases"][idx], 58).center(im, 43, L["phases"][idx], x0=64, x1=128)
        font("4x6").center(im, 55, f"{percent(round(lit * 100), 0, lang)} · {L['waxing'] if waxing else L['waning']}", x0=64, x1=128)
        out.append((im, 700))
    return out


AQI_LIMITS = [20, 40, 60, 80, 100, 10 ** 9]


def air_quality(aq, lang):
    L = T[lang]
    v = aq["aqi"]
    level = L["aqi_levels"][next(i for i, s in enumerate(AQI_LIMITS) if v <= s)]
    im, d = canvas()
    header(im, d, L["air_quality"], "AQI")
    font("helvB24").draw(im, 0, 8, str(round(v)))
    fit(level, 70, ("6x13B", "6x10", "5x8")).draw(im, 58, 14, level)
    font("4x6").draw(im, 58, 29, L["aqi_index"])
    x0, x1, y0 = 4, 123, 44
    d.rectangle([x0, y0, x1, y0 + 4], outline=1)
    for i in range(1, 6):
        x = x0 + (x1 - x0) * i / 6
        d.line([(x, y0), (x, y0 + 4)], fill=1)
    p = x0 + (x1 - x0) * min(v, 120) / 120
    d.rectangle([x0, y0, p, y0 + 4], fill=1)
    d.polygon([(p - 3, y0 - 5), (p + 3, y0 - 5), (p, y0 - 1)], fill=1)
    pm = f"PM2.5 {round(aq['pm25'] or 0)}  PM10 {round(aq['pm10'] or 0)} µg/m³"
    font("5x8").center(im, 54, pm)
    return [(im, 1000)]


# --- markets ------------------------------------------------------------------------
def usd_big(usd, lang):
    L = T[lang]
    series = [x for x in usd.get("series", []) if x]
    change = usd.get("change")
    out = []
    steps = 14 if len(series) >= 5 else 1
    for t in range(steps):
        im, d = canvas()
        font("6x13B").draw(im, 0, -2, "USD/TRY")
        if change is not None:
            txt = percent(abs(change), 2, lang)
            w = font("6x10").width(txt)
            font("6x10").draw(im, W - w, 0, txt)
            arrow(d, W - w - 9, 4, change >= 0, 3)
        bx = font("helvB24").draw(im, 0, 8, number(usd["price"], 2, lang))
        font("helvB14").draw(im, bx + 3, 18, "₺" if font("helvB14").has("₺") else "TL")
        if len(series) >= 5:
            lo, hi = min(series), max(series)
            hi = hi if hi > lo else lo + 0.01
            x0, x1, y0, y1 = 0, 103, 42, 62
            pts = [(x0 + (x1 - x0) * i / (len(series) - 1), y1 - (v - lo) / (hi - lo) * (y1 - y0)) for i, v in enumerate(series)]
            k = max(2, round(len(pts) * (t + 1) / steps))
            d.line(pts[:k], fill=1, width=1)
            for x in range(x0, x1 + 1, 4):
                d.point((x, y1 + 1), fill=1)
            if t == steps - 1:
                x, y = pts[-1]
                d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=1)
            f4 = font("4x6")
            f4.right(im, W, 41, number(hi, 2, lang))
            f4.right(im, W, 57, number(lo, 2, lang))
            f4.right(im, W, 49, f"{len(series)}{L['days_abbr']}")
        out.append((im, 45 if t < steps - 1 else 6000))
    return out


def markets(mk, lang):
    L = T[lang]
    rows = []
    if mk.get("eur"):
        rows.append(("EUR/TRY", number(mk["eur"]["price"], 2, lang), mk["eur"].get("change")))
    if mk.get("gold"):
        rows.append((L["gold"], number(mk["gold"]["price"], 0, lang), mk["gold"].get("change")))
    if mk.get("btc"):
        rows.append(("BTC $", number(mk["btc"]["price"], 0, lang), mk["btc"].get("change")))
    if mk.get("cbrt_usd") and mk["cbrt_usd"].get("sell"):
        rows.append((L["cbrt"], number(mk["cbrt_usd"]["sell"], 2, lang), None))
    if not rows:
        return None
    im, d = canvas()
    header(im, d, L["markets"], (mk.get("cbrt_usd", {}).get("date") or "")[:5].replace(".", "/") or None)
    f6, f4 = font("6x10"), font("4x6")
    for i, (name, value, change) in enumerate(rows[:4]):
        y = 12 + i * 13
        f6.draw(im, 0, y, name)
        f6.right(im, 100, y, value)
        if change is not None:
            arrow(d, 104, y + 5, change >= 0, 2)
            f4.right(im, W, y + 2, number(abs(change), 1, lang))
    return [(im, 1000)]


# --- earthquake / holiday / text -------------------------------------------------------
def earthquake(eq, lang):
    L = T[lang]
    if eq.get("count", 0) == 0:
        im, d = canvas()
        header(im, d, L["quakes_title"])
        turkey_map.draw(d, 20, 14, 88, 38)
        font("5x8").center(im, 55, L["no_quakes"])
        return [(im, 1000)]
    n = 10
    out = []
    when = eq.get("time") or ""
    for t in range(n):
        im, d = canvas()
        header(im, d, L["quakes_24h"].format(n=eq["count"]))
        turkey_map.draw(d, 0, 12, 87, 38)
        if eq.get("lat") is not None:
            x, y = turkey_map.project(eq["lon"], eq["lat"], 0, 12, 87, 38)
            x, y = max(1, min(86, x)), max(12, min(50, y))
            d.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=1)
            r = 2 + t * 1.2
            if t < n - 2:
                d.ellipse([x - r, y - r, x + r, y + r], outline=1)
        font("5x8").draw(im, 90, 12, "M")
        font("helvB18").draw(im, 96, 8, number(eq["mag"] or 0, 1, lang))
        font("5x8").draw(im, 90, 32, f"{round(eq.get('depth') or 0)} km")
        font("5x8").draw(im, 90, 42, when[11:16])
        font("5x8").center(im, 55, font("5x8").ellipsize(eq.get("place", ""), 128))
        out.append((im, 140))
    return out


def holiday(hd, lang):
    L = T[lang]
    date = dt.date.fromisoformat(hd["date"])
    left = hd["days_left"]
    name = hd["name_tr"] if lang == "tr" else hd["name_en"]
    f13 = font("6x13B")
    lines = f13.wrap(name, 126)[:2]
    if left <= 0:
        out = []
        rnd = random.Random(2)
        ps = [(rnd.randint(0, 127), rnd.randint(0, 63), rnd.choice((1, 2))) for _ in range(30)]
        for k in range(16):
            im, d = canvas()
            for x, y, v in ps:
                yy = (y + k * v * 4) % 64
                d.rectangle([x, yy, x + 1, yy + 1], fill=1)
            d.rectangle([4, 14, 123, 50], fill=0)
            font("helvB18").center(im, 12, L["today_caps"])
            for i, s in enumerate(lines):
                f13.center(im, 34 + i * 12, s)
            out.append((im, 90))
        return out
    im, d = canvas()
    header(im, d, L["next_holiday"], L["tomorrow_excl"] if left == 1 else None)
    y = 11
    for s in lines:
        f13.center(im, y, s)
        y += 12
    count = str(left)
    word = L["day"] if left == 1 else L["days_word"]
    fb, fs = (font("helvB24"), font("helvB12")) if len(lines) == 1 else (font("helvB18"), font("helvB10"))
    w = fb.width(count) + 4 + fs.width(word)
    x = (W - w) // 2
    x = fb.draw(im, x, y - 4, count)
    fs.draw(im, x + 4, y + (8 if len(lines) == 1 else 4), word)
    font("5x8").center(im, 56, date_text(date, lang))
    return [(im, 1000)]


def text_pages(title, text, footer=None, page_ms=4000):
    options = []
    for name, per_page, step in (("6x10", 5, 10), ("5x8", 6, 9)):
        f = font(name)
        lines = f.wrap(text, 127)
        if footer:
            lines.append(f.ellipsize("— " + footer, 127))
        pages = (len(lines) + per_page - 1) // per_page
        options.append((pages, name != "6x10", f, lines, per_page, step))
    _, _, f, lines, per_page, step = min(options, key=lambda x: (x[0], x[1]))
    pages = [lines[i:i + per_page] for i in range(0, len(lines), per_page)][:4]
    out = []
    for i, pg in enumerate(pages):
        im, d = canvas()
        header(im, d, title, f"{i + 1}/{len(pages)}" if len(pages) > 1 else None)
        for j, s in enumerate(pg):
            f.draw(im, 0, 11 + j * step, s)
        out.append((im, page_ms))
    return out


# --- screensavers -------------------------------------------------------------------
def game_of_life(seed, n=60):
    rnd = random.Random(seed)
    GW, GH = 64, 32
    g = [[1 if rnd.random() < 0.33 else 0 for _ in range(GW)] for _ in range(GH)]
    out = []
    for t in range(n):
        im, d = canvas()
        px = im.load()
        for y in range(GH):
            for x in range(GW):
                if g[y][x]:
                    px[2 * x, 2 * y] = px[2 * x + 1, 2 * y] = px[2 * x, 2 * y + 1] = 1
        out.append((im, 90))
        new = [[0] * GW for _ in range(GH)]
        alive = 0
        for y in range(GH):
            for x in range(GW):
                k = sum(g[(y + dy) % GH][(x + dx) % GW] for dy in (-1, 0, 1) for dx in (-1, 0, 1)) - g[y][x]
                new[y][x] = 1 if (k == 3 or (g[y][x] and k == 2)) else 0
                alive += new[y][x]
        g = new
        if alive < 40:
            for _ in range(60):
                g[rnd.randrange(GH)][rnd.randrange(GW)] = 1
    return out


def starfield(seed, n=40):
    rnd = random.Random(seed)
    stars = [(rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(0.1, 1.0)) for _ in range(70)]
    out = []
    for t in range(n):
        im, d = canvas()
        for x, y, z0 in stars:
            z = (z0 - t / n) % 1.0 + 0.02
            sx, sy = 64 + x / z * 40, 32 + y / z * 20
            if 0 <= sx < W and 0 <= sy < H:
                if z < 0.3:
                    d.rectangle([sx, sy, sx + 1, sy + 1], fill=1)
                else:
                    d.point((sx, sy), fill=1)
        out.append((im, 50))
    return out


def matrix(seed, n=40):
    rnd = random.Random(seed)
    f = font("4x6")
    chars = "0123456789ABCDEFZXK$#%&*+<>"
    columns = [(rnd.uniform(0, 12), rnd.choice((1, 2)), rnd.randint(4, 9)) for _ in range(32)]
    grid = [[rnd.choice(chars) for _ in range(12)] for _ in range(32)]
    out = []
    for t in range(n):
        im, d = canvas()
        for c, (y0, speed, length) in enumerate(columns):
            head = (y0 + t * speed * 12 / n * 2) % (12 + length)
            for k in range(length):
                r = int(head) - k
                if 0 <= r < 11:
                    ch = grid[c][(r + t) % 12] if k == 0 else grid[c][r]
                    f.draw(im, c * 4, r * 6, ch)
                    if k == 0:
                        d.rectangle([c * 4, r * 6 + 5, c * 4 + 3, r * 6 + 5], fill=1)
        out.append((im, 70))
    return out


SCREENSAVERS = {
    "life": ({"en": "Game of Life", "tr": "Hayat oyunu"}, game_of_life),
    "stars": ({"en": "Starfield", "tr": "Yıldız akışı"}, starfield),
    "matrix": ({"en": "Matrix", "tr": "Matrix"}, matrix),
}
