#!/usr/bin/env python3
"""ESP_Buddy screen generator.

Fetches the data, renders every screen listed in screens.md as .olb/.liv files — once in English
and once in Turkish — and prepares the folder published on GitHub Pages (_site).

    python generator/generate.py               # real APIs
    python generator/generate.py --sample      # offline, uses generator/sample_data
    python generator/generate.py --out _site   # output folder (default: _site)
"""
import argparse
import datetime as dt
import json
import os
import random
import re
import shutil
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import data  # noqa: E402
import face  # noqa: E402
import icons  # noqa: E402
import olb  # noqa: E402
import screens as S  # noqa: E402
from font import font  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TZ = data.TZ
LANGS = ("en", "tr")
MAX_FILE = 48000          # must match MAX_FILE in firmware/ESP_Buddy/config.h

TITLES = {
    "en": {"clock": "Clock", "weather_now": "Weather: now", "weather_hourly": "Weather: 12 hours",
           "weather_3day": "Weather: 3 days", "sun_moon": "Sun & Moon", "air_quality": "Air quality",
           "usd": "USD/TRY", "markets": "Markets", "face": "Face", "earthquake": "Earthquake",
           "holiday": "Next holiday", "on_this_day": "On this day", "quote": "Quote of the day",
           "screensaver": "Screensaver"},
    "tr": {"clock": "Saat", "weather_now": "Hava: şimdi", "weather_hourly": "Hava: 12 saat",
           "weather_3day": "Hava: 3 gün", "sun_moon": "Güneş ve Ay", "air_quality": "Hava kalitesi",
           "usd": "USD/TRY", "markets": "Piyasa", "face": "Yüz", "earthquake": "Deprem",
           "holiday": "Sıradaki tatil", "on_this_day": "Bugün tarihte", "quote": "Günün sözü",
           "screensaver": "Ekran koruyucu"},
}

NOTES = {
    "en": {"clock": "Drawn by the device; time is synced from the phone", "source": "Source: {s}"},
    "tr": {"clock": "Cihaz kendisi çizer; saat telefondan eşitlenir", "source": "Kaynak: {s}"},
}

REASONS = {
    "en": {"usd_up": "USD jumped {p} in a day", "usd_down": "USD fell {p}", "rain": "Rain today",
           "snow": "It's snowing", "freezing": "It's {t} outside", "sunny": "Sunny and warm",
           "dirty_air": "Polluted air (AQI {a})", "holiday_soon": "{n}: {d} days to go", "holiday_today": "Today: {n}",
           "friday": "It's Friday", "monday": "Monday blues", "weekend": "Weekend", "quake": "M{m} earthquake",
           "idle": "Looking around", "surprise": "Surprise"},
    "tr": {"usd_up": "Dolar bir günde {p} yükseldi", "usd_down": "Dolar {p} düştü", "rain": "Bugün yağmur var",
           "snow": "Kar yağıyor", "freezing": "Hava {t}", "sunny": "Güneşli ve ılık",
           "dirty_air": "Hava kirli (AQI {a})", "holiday_soon": "{n}: {d} gün", "holiday_today": "Bugün {n}",
           "friday": "Bugün Cuma", "monday": "Pazartesi sendromu", "weekend": "Hafta sonu", "quake": "M{m} deprem",
           "idle": "Etrafı kolaçan ediyor", "surprise": "Sürpriz"},
}


def read_config(path):
    cfg = {"city": "Ankara", "lat": 39.93, "lon": 32.86, "duration": 7}
    order = []
    with open(path, encoding="utf-8") as f:
        for s in f:
            m = re.match(r"^\s*-\s*\[([ xX])\]\s*([a-z_0-9]+)", s)
            if m:
                if m.group(1).lower() == "x":
                    order.append(m.group(2))
                continue
            m = re.match(r"^\s*-\s*([a-z_]+)\s*:\s*(.+?)\s*$", s)
            if m and m.group(1) in cfg:
                v = m.group(2)
                cfg[m.group(1)] = v if isinstance(cfg[m.group(1)], str) else type(cfg[m.group(1)])(v)
    return cfg, order


def pick_moods(v, now, count):
    """Returns [(mood, reason_key, reason_args)] chosen from today's data, topped up with surprises."""
    picked = []

    def add(mood, key, **kw):
        if mood not in [x[0] for x in picked]:
            picked.append((mood, key, kw))

    usd = (v.get("markets") or {}).get("usd") or {}
    ch = usd.get("change")
    if ch is not None and ch >= 1.0:
        add("shock", "usd_up", pct=ch)
    elif ch is not None and ch <= -0.7:
        add("happy", "usd_down", pct=-ch)
    wx = v.get("weather")
    if wx:
        s = wx["now"]
        k = icons.kind(s["code"])
        today_k = icons.kind(wx["daily"][0]["code"]) if wx.get("daily") else k
        if k in ("rain", "drizzle", "storm") or today_k in ("rain", "storm"):
            add("sad", "rain")
        if k == "snow" or today_k == "snow":
            add("cold", "snow")
        elif s["temp"] is not None and s["temp"] <= 2:
            add("cold", "freezing", t=S.degrees(s["temp"]))
        if k in ("clear", "few_clouds") and s["is_day"] and (s["temp"] or 0) >= 18:
            add("cool", "sunny")
    aq = v.get("air_quality")
    if aq and aq["aqi"] > 60:
        add("angry", "dirty_air", a=round(aq["aqi"]))
    hd = v.get("holiday")
    if hd and 0 <= hd["days_left"] <= 7:
        add("excited", "holiday_soon" if hd["days_left"] else "holiday_today", holiday=True, d=hd["days_left"])
    wd = now.weekday()
    if wd == 4:
        add("party", "friday")
    elif wd == 0:
        add("sleepy", "monday")
    elif wd >= 5:
        add("love", "weekend")
    eq = v.get("earthquake") or {}
    if (eq.get("mag") or 0) >= 5:
        add("shock", "quake", m=eq["mag"])

    pool = ["curious", "happy", "laugh", "love", "dizzy", "wink", "curious"]
    random.Random(now.strftime("%Y%m%d%H")).shuffle(pool)
    if "curious" not in [x[0] for x in picked]:
        picked.insert(0, ("curious", "idle", {}))
    for m in pool:
        if len(picked) >= count:
            break
        add(m, "surprise")
    return picked[:max(count, 1)]


def reason_text(key, kw, v, lang):
    r = REASONS[lang][key]
    if "pct" in kw:
        return r.format(p=S.percent(kw["pct"], 2, lang))
    if kw.get("holiday"):
        hd = v["holiday"]
        return r.format(n=hd["name_tr"] if lang == "tr" else hd["name_en"], d=kw["d"])
    if "m" in kw:
        return r.format(m=S.number(kw["m"], 1, lang))
    return r.format(**kw)


def render_set(lang, order, cfg, v, src, now, moods, saver, cache, out_dir):
    """Renders one language. cache: language-independent renders (faces, screensaver) shared by both sets."""
    os.makedirs(os.path.join(out_dir, "screens"))
    os.makedirs(os.path.join(out_dir, "previews"))
    city, default = cfg["city"], cfg["duration"]
    wx, mk = v.get("weather"), v.get("markets") or {}
    usd = mk.get("usd")
    mood_iter = iter(moods)
    listing, skipped = [], []
    for kind in order:
        frames, duration, note, title, ext, live_bytes = None, default, "", TITLES[lang].get(kind, kind), "olb", None
        name_kind = kind
        try:
            if kind == "clock":
                parts = [city]
                if wx:
                    parts[0] += " " + S.degrees(wx["now"]["temp"])
                if usd:
                    parts.append("$" + S.number(usd["price"], 2, lang))
                info = "  ".join(parts)
                duration = max(default, 8)
                live_bytes = olb.live(olb.LIVE_CLOCK, duration, info, lang)
                frames = S.clock_preview(info, now, lang)
                ext, note = "liv", NOTES[lang]["clock"]
            elif kind == "weather_now" and wx:
                frames = S.weather_now(wx, city, lang)
                note = icons.description(wx["now"]["code"], lang)
            elif kind == "weather_hourly" and wx:
                frames = S.weather_hourly(wx, lang)
            elif kind == "weather_3day" and wx:
                frames = S.weather_3day(wx, now.date(), lang)
            elif kind == "sun_moon" and wx:
                frames = S.sun_moon(wx, now, lang)
            elif kind == "air_quality" and v.get("air_quality"):
                frames = S.air_quality(v["air_quality"], lang)
            elif kind == "usd" and usd:
                frames, duration = S.usd_big(usd, lang), 1
                note = NOTES[lang]["source"].format(s=usd.get("source"))
            elif kind == "markets" and mk:
                frames = S.markets(mk, lang)
            elif kind == "earthquake" and v.get("earthquake"):
                frames = S.earthquake(v["earthquake"], lang)
            elif kind == "holiday" and v.get("holiday"):
                frames = S.holiday(v["holiday"], lang)
            elif kind == "on_this_day" and (v.get("on_this_day") or {}).get(lang):
                t = v["on_this_day"][lang]
                frames, duration = S.text_pages(f"{S.T[lang]['on_this_day']} · {t.get('year', '')}", t["text"]), 1
            elif kind == "quote" and v.get("quote"):
                frames, duration = S.text_pages(S.T[lang]["quote"], v["quote"]["text"], v["quote"]["author"]), 1
            elif kind == "face":
                mood, key, kw = next(mood_iter, ("curious", "idle", {}))
                if ("face", mood) not in cache:
                    cache[("face", mood)] = face.face_animation(mood)
                frames, duration, name_kind = cache[("face", mood)], 5, f"face-{mood}"
                title = f"{TITLES[lang]['face']}: {face.MOODS[lang][mood]}"
                note = reason_text(key, kw, v, lang)
            elif kind == "screensaver":
                names, fn = S.SCREENSAVERS[saver]
                if ("saver", saver) not in cache:
                    cache[("saver", saver)] = fn(now.toordinal())
                frames, duration, note = cache[("saver", saver)], 1, names[lang]
        except Exception as e:  # noqa: BLE001  (one broken screen must not stop the others)
            src.status[f"screen:{kind}:{lang}"] = f"error: {type(e).__name__}: {e}"
            frames = None
        if not frames:
            skipped.append(kind)
            continue

        no = len(listing) + 1
        fname = f"{no:02d}-{name_kind.replace('_', '-')}"[:20] + "." + ext
        if ext == "liv":
            body = live_bytes
            with open(os.path.join(out_dir, "previews", fname.replace(".liv", ".olb")), "wb") as f:
                f.write(olb.olb(frames, duration))
        else:
            body = olb.olb(frames, duration)
            if len(body) > MAX_FILE:
                src.status[f"screen:{kind}:{lang}"] = f"error: file too large ({len(body)} B > {MAX_FILE})"
                skipped.append(kind)
                continue
        with open(os.path.join(out_dir, "screens", fname), "wb") as f:
            f.write(body)
        listing.append({
            "file": fname, "type": ext, "title": title, "bytes": len(body), "duration": duration, "frames": len(frames),
            "preview": ("previews/" + fname.replace(".liv", ".olb")) if ext == "liv" else ("screens/" + fname),
            "note": note, "_thumb": frames[min(len(frames) - 1, len(frames) // 2)][0],
        })
    return listing, skipped


def contact_sheet(listing, path):
    cols, scale, gap = 4, 2, 18
    rows = (len(listing) + cols - 1) // cols
    sheet = Image.new("L", (cols * (128 * scale + 8) + 8, rows * (64 * scale + gap + 8) + 8), 40)
    for i, e in enumerate(listing):
        r, c = divmod(i, cols)
        x, y = 8 + c * (128 * scale + 8), 8 + r * (64 * scale + gap + 8)
        sheet.paste(e["_thumb"].convert("L").resize((128 * scale, 64 * scale), Image.NEAREST), (x, y + gap))
        label = Image.new("1", (128 * scale, 12), 0)
        font("6x10").draw(label, 0, 1, f"{e['file']}  {e['bytes']} B")
        sheet.paste(label.convert("L"), (x, y + 2))
    sheet.save(path)


def generate(sample, out):
    now = dt.datetime.now(TZ)
    cfg, order = read_config(os.path.join(ROOT, "screens.md"))
    v, src = data.fetch_all(sample, cfg["lat"], cfg["lon"])

    moods = pick_moods(v, now, order.count("face"))
    saver = list(S.SCREENSAVERS)[now.toordinal() % len(S.SCREENSAVERS)]

    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)
    cache, report = {}, {}
    for lang in LANGS:
        listing, skipped = render_set(lang, order, cfg, v, src, now, moods, saver, cache, os.path.join(out, lang))
        contact_sheet(listing, os.path.join(out, lang, "preview.png"))
        for e in listing:
            e.pop("_thumb")
        total = sum(e["bytes"] for e in listing)
        manifest = {
            "version": 2, "lang": lang, "generated": now.isoformat(timespec="seconds"), "city": cfg["city"],
            "sample": sample, "screens": listing, "total_bytes": total, "skipped": skipped,
            "moods": [{"mood": m, "name": face.MOODS[lang][m], "reason": reason_text(k, kw, v, lang)} for m, k, kw in moods],
            "sources": src.status,
        }
        with open(os.path.join(out, lang, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        report[lang] = (listing, skipped, total)

    with open(os.path.join(out, "data.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": v, "raw": src.raw}, f, ensure_ascii=False, default=str)
    site = os.path.join(ROOT, "site")
    for name in os.listdir(site):
        shutil.copy(os.path.join(site, name), os.path.join(out, name))
    open(os.path.join(out, ".nojekyll"), "w").close()

    # console + GitHub Actions job summary
    listing, skipped, total = report["en"]
    lines = [f"## ESP_Buddy · {now:%Y-%m-%d %H:%M}", "",
             f"{len(listing)} screens per language, {total / 1024:.1f} KB (EN) / {report['tr'][2] / 1024:.1f} KB (TR)"
             + (" — SAMPLE DATA" if sample else ""), "",
             "| # | File | Bytes | Note |", "|---|---|---|---|"]
    lines += [f"| {i + 1} | {e['file']} | {e['bytes']} | {e['note']} |" for i, e in enumerate(listing)]
    lines += ["", "**Sources**", ""] + [f"- {'✅' if s == 'ok' else '⚠️'} `{k}` {'' if s == 'ok' else s}" for k, s in src.status.items()]
    if skipped:
        lines += ["", f"Skipped (no data): {', '.join(skipped)}"]
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text + "\n")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="offline: use the saved sample responses")
    ap.add_argument("--out", default=os.path.join(ROOT, "_site"))
    a = ap.parse_args()
    r = generate(a.sample, a.out)
    if not r["en"][0]:
        sys.exit("No screens could be generated")
