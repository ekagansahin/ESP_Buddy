"""Fetches data from the APIs. Every source is independent: if one fails, only the screens using it are dropped.

In --sample mode nothing goes to the internet; saved responses in generator/sample_data/ are used instead.
"""
import datetime as dt
import json
import os
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

import requests

TZ = ZoneInfo("Europe/Istanbul")
UA = "Mozilla/5.0 (X11; Linux x86_64) ESP_Buddy/0.2 (+https://github.com/ekagansahin/ESP_Buddy)"
SAMPLES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_data")


class Sources:
    def __init__(self, sample=False):
        self.sample = sample
        self.status = {}    # name -> "ok" | error message
        self.raw = {}       # name -> parsed response (published on Pages as data.json)

    def _fetch(self, name, url, params=None, text=False):
        if self.sample:
            for ext in (".json", ".xml"):
                path = os.path.join(SAMPLES, name + ext)
                if os.path.exists(path):
                    with open(path, encoding="utf-8") as f:
                        return f.read() if (text or ext == ".xml") else json.load(f)
            raise FileNotFoundError(f"no sample data: {name}")
        last = None
        for _ in range(2):
            try:
                r = requests.get(url, params=params, headers={"User-Agent": UA, "Accept": "*/*"}, timeout=20)
                r.raise_for_status()
                return r.text if text else r.json()
            except Exception as e:  # noqa: BLE001
                last = e
        raise last

    def get(self, name, url, params=None, text=False):
        try:
            v = self._fetch(name, url, params, text)
            self.status[name] = "ok"
            if not text:
                self.raw[name] = v
            return v
        except Exception as e:  # noqa: BLE001
            self.status[name] = f"error: {type(e).__name__}: {str(e)[:120]}"
            return None


def num(x):
    """'4.512,34' / '%0,12' / 48.8 -> float"""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).replace("%", "").replace("$", "").replace("₺", "").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


# --- weather -------------------------------------------------------------------
def weather(src: Sources, lat, lon):
    d = src.get("openmeteo", "https://api.open-meteo.com/v1/forecast", {
        "latitude": lat, "longitude": lon, "timezone": "Europe/Istanbul", "forecast_days": 4,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,is_day,wind_speed_10m",
        "hourly": "temperature_2m,precipitation_probability,weather_code,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
    })
    if not d:
        return None
    c = d["current"]
    now = {"temp": c["temperature_2m"], "feels_like": c.get("apparent_temperature"),
           "humidity": c.get("relative_humidity_2m"), "wind": c.get("wind_speed_10m"),
           "code": int(c.get("weather_code") or 0), "is_day": bool(c.get("is_day", 1)), "time": c.get("time")}
    h = d["hourly"]
    start = 0
    ref = (c.get("time") or "")[:13]
    for i, t in enumerate(h["time"]):
        if t[:13] >= ref:
            start = i
            break
    hourly = []
    for i in range(start, min(start + 13, len(h["time"]))):
        hourly.append({"hour": h["time"][i][11:13], "temp": h["temperature_2m"][i],
                       "rain": h["precipitation_probability"][i] or 0, "code": int(h["weather_code"][i] or 0),
                       "is_day": bool(h["is_day"][i])})
    g = d["daily"]
    daily = []
    for i in range(len(g["time"])):
        daily.append({"date": g["time"][i], "code": int(g["weather_code"][i] or 0),
                      "max": g["temperature_2m_max"][i], "min": g["temperature_2m_min"][i],
                      "rain": g["precipitation_probability_max"][i] or 0,
                      "sunrise": g["sunrise"][i], "sunset": g["sunset"][i]})
    return {"now": now, "hourly": hourly, "daily": daily}


def air_quality(src: Sources, lat, lon):
    d = src.get("openmeteo_aq", "https://air-quality-api.open-meteo.com/v1/air-quality", {
        "latitude": lat, "longitude": lon, "current": "pm10,pm2_5,european_aqi", "timezone": "Europe/Istanbul"})
    if not d or d.get("current", {}).get("european_aqi") is None:
        return None
    c = d["current"]
    return {"aqi": c["european_aqi"], "pm25": c.get("pm2_5"), "pm10": c.get("pm10")}


# --- markets -------------------------------------------------------------------
def _yahoo(src, symbol, name):
    d = src.get(name, f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}", {"range": "1mo", "interval": "1d"})
    if not d:
        return None
    r = d["chart"]["result"][0]
    price = r["meta"].get("regularMarketPrice")
    closes = [x for x in r["indicators"]["quote"][0].get("close", []) if x]
    if not price and closes:
        price = closes[-1]
    if not price:
        return None
    prev = closes[-2] if len(closes) >= 2 else r["meta"].get("chartPreviousClose")
    series = closes[:-1] + [price] if closes else [price]
    return {"price": price, "prev": prev, "series": series, "source": "Yahoo"}


def markets(src: Sources):
    today = dt.datetime.now(TZ).date()
    out = {}

    ca = src.get("currency_api", "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json")
    if not ca:
        ca = src.get("currency_api_backup", "https://latest.currency-api.pages.dev/v1/currencies/usd.json")
    cau = (ca or {}).get("usd", {})

    usd = _yahoo(src, "USDTRY=X", "yahoo_usdtry")
    if not usd and cau.get("try"):
        usd = {"price": cau["try"], "prev": None, "series": [], "source": "currency-api"}
    tcmb = src.get("tcmb", "https://www.tcmb.gov.tr/kurlar/today.xml", text=True)
    if tcmb:
        try:
            root = ET.fromstring(tcmb.encode("utf-8") if isinstance(tcmb, str) else tcmb)
            for c in root.findall("Currency"):
                if c.get("Kod") == "USD":
                    out["cbrt_usd"] = {"sell": num(c.findtext("ForexSelling")), "date": root.get("Tarih")}
        except ET.ParseError as e:
            src.status["tcmb"] = f"error: XML {e}"
    if not usd and out.get("cbrt_usd", {}).get("sell"):
        usd = {"price": out["cbrt_usd"]["sell"], "prev": None, "series": [], "source": "TCMB"}

    if usd and len(usd["series"]) < 10:
        start = (today - dt.timedelta(days=45)).isoformat()
        fr = src.get("frankfurter", f"https://api.frankfurter.dev/v1/{start}..", {"from": "USD", "to": "TRY"})
        if fr and fr.get("rates"):
            series = [v["TRY"] for _, v in sorted(fr["rates"].items()) if "TRY" in v]
            if series:
                if not usd["prev"]:
                    usd["prev"] = series[-1]
                usd["series"] = series[-29:] + [usd["price"]]
    if usd:
        usd["change"] = (usd["price"] / usd["prev"] - 1) * 100 if usd.get("prev") else None
        out["usd"] = usd

    eur = _yahoo(src, "EURTRY=X", "yahoo_eurtry")
    if not eur and cau.get("try") and cau.get("eur"):
        eur = {"price": cau["try"] / cau["eur"], "prev": None, "series": [], "source": "currency-api"}
    if eur:
        eur["change"] = (eur["price"] / eur["prev"] - 1) * 100 if eur.get("prev") else None
        out["eur"] = eur

    tg = src.get("truncgil", "https://finans.truncgil.com/today.json")
    if tg and isinstance(tg.get("gram-altin"), dict):
        g = tg["gram-altin"]
        out["gold"] = {"price": num(g.get("Satış") or g.get("Satis")), "change": num(g.get("Değişim") or g.get("Degisim"))}
    elif cau.get("xau") and cau.get("try"):
        out["gold"] = {"price": cau["try"] / cau["xau"] / 31.1034768, "change": None}

    cg = src.get("coingecko", "https://api.coingecko.com/api/v3/simple/price",
                 {"ids": "bitcoin", "vs_currencies": "usd", "include_24hr_change": "true"})
    if cg and cg.get("bitcoin", {}).get("usd"):
        out["btc"] = {"price": cg["bitcoin"]["usd"], "change": cg["bitcoin"].get("usd_24h_change")}
    elif cau.get("btc"):
        out["btc"] = {"price": 1 / cau["btc"], "change": None}
    return out


# --- other ---------------------------------------------------------------------
def earthquake(src: Sources):
    d = src.get("kandilli", "https://api.orhanaydogdu.com.tr/deprem/kandilli/live")
    if not d or not isinstance(d.get("result"), list):
        return None
    r = d["result"]
    if not r:
        return {"count": 0}
    e = max(r, key=lambda x: x.get("mag") or 0)
    lon, lat = ((e.get("geojson") or {}).get("coordinates") or [None, None])[:2]
    return {"count": len(r), "mag": e.get("mag"), "place": e.get("title", ""), "time": e.get("date_time") or e.get("date", ""),
            "depth": e.get("depth"), "lat": lat, "lon": lon}


def holiday(src: Sources):
    today = dt.datetime.now(TZ).date()
    days = []
    for year in (today.year, today.year + 1):
        d = src.get(f"holidays_{year}", f"https://date.nager.at/api/v3/PublicHolidays/{year}/TR")
        if d:
            days += d
    if not days:
        return None
    upcoming = sorted((dt.date.fromisoformat(x["date"]), i, x) for i, x in enumerate(days) if dt.date.fromisoformat(x["date"]) >= today)
    if not upcoming:
        return None
    t, _, x = upcoming[0]
    return {"name_tr": x.get("localName") or x.get("name"), "name_en": x.get("name") or x.get("localName"),
            "date": t.isoformat(), "days_left": (t - today).days}


def on_this_day(src: Sources, lang):
    n = dt.datetime.now(TZ)
    d = src.get(f"onthisday_{lang}", f"https://api.wikimedia.org/feed/v1/wikipedia/{lang}/onthisday/selected/{n:%m}/{n:%d}")
    if not d:
        return None
    events = [x for x in d.get("selected", []) if x.get("text")] or [x for x in d.get("events", []) if x.get("text")]
    if not events:
        return None
    events.sort(key=lambda x: len(x["text"]))
    pick = events[0] if len(events[0]["text"]) > 40 or len(events) == 1 else events[1]
    return {"year": pick.get("year"), "text": pick["text"]}


def quote(src: Sources):
    d = src.get("zenquotes", "https://zenquotes.io/api/today")
    if not d or not isinstance(d, list) or not d[0].get("q"):
        return None
    return {"text": d[0]["q"], "author": d[0].get("a", "")}


def fetch_all(sample=False, lat=39.93, lon=32.86):
    src = Sources(sample)
    v = {
        "weather": weather(src, lat, lon),
        "air_quality": air_quality(src, lat, lon),
        "markets": markets(src),
        "earthquake": earthquake(src),
        "holiday": holiday(src),
        "on_this_day": {"tr": on_this_day(src, "tr"), "en": on_this_day(src, "en")},
        "quote": quote(src),
    }
    return v, src
