"""
Multi-Route Real-Time Data Collector (Hat 268, 565, 502)

Izmir ESHOT API'den 3 hat icin gercek zamanli otobus konum verisi toplar.
Her saatte bir hava durumu, her 20 dakikada bir Route 502 trafik verisi
(TomTom) kaydedilir. Veriler SQLite veritabanina kaydedilir.

Kullanim:
    python collector.py                  # Normal calistir (Ctrl+C ile durdur)
    python collector.py --interval 60    # 60 saniye aralikla topla
    python collector.py --duration 3600  # 1 saat boyunca topla
    python collector.py --test           # Tek bir API cagri testi yap

Ortam degiskenleri (opsiyonel):
    OPENWEATHER_API_KEY  - Gercek hava verisi icin (yoksa mock)
    TOMTOM_API_KEY       - Route 502 trafik verisi icin (yoksa atlanir)

NOT: TomTom ucretsiz limiti 2500 istek/gun. Route 502 (31 segment x 72
istek/gun = 2232) bu limite sigmaktadir.
"""

import argparse
import json
import logging
import math
import os
import signal
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv yuklu degilse ortam degiskenleri dogrudan okunur

from config import (
    # Route 502 kimligi (TomTom trafik toplama icin)
    ROUTE_ID,
    # Endpoint'ler
    ENDPOINT_BUS_POSITIONS,
    ENDPOINT_BUSES_AT_STOP,
    # Genel ayarlar
    POLL_INTERVAL_SECONDS,
    DATA_DIR,
    # Aktif hat konfigurasyonu
    ACTIVE_ROUTE_IDS,
    ACTIVE_ROUTE_IDS_SET,
    ROUTES,
    ALL_ROUTE_STOP_IDS,
)

# --- Hava durumu ---
WEATHER_LAT = 38.4600
WEATHER_LON = 27.1700
WEATHER_INTERVAL_SECONDS = 3600
OPENWEATHER_KEY = os.getenv("OPENWEATHER_API_KEY", "")

# --- TomTom trafik (Route 502) ---
TOMTOM_KEY = os.getenv("TOMTOM_API_KEY", "")
TRAFFIC_INTERVAL_SECONDS = 1200   # 20 dakikada bir
TOMTOM_FLOW_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("collector")

# --- Database ---
DB_PATH = os.path.join(DATA_DIR, "route_502_realtime.db")


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def init_db():
    """Veritabani ve tablolari olustur; mevcut DB icin migration uygula."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # bus_positions: route_id eklendi
    c.execute("""
        CREATE TABLE IF NOT EXISTS bus_positions (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp             TEXT NOT NULL,
            poll_id               TEXT NOT NULL,
            route_id              INTEGER,
            otobus_id             INTEGER NOT NULL,
            yon                   INTEGER NOT NULL,
            lat                   REAL NOT NULL,
            lon                   REAL NOT NULL,
            nearest_stop_id       INTEGER,
            nearest_stop_seq      INTEGER,
            distance_to_nearest_m REAL
        )
    """)

    # stop_arrivals
    c.execute("""
        CREATE TABLE IF NOT EXISTS stop_arrivals (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp         TEXT NOT NULL,
            poll_id           TEXT NOT NULL,
            durak_id          INTEGER NOT NULL,
            otobus_id         INTEGER NOT NULL,
            hat_numarasi      INTEGER NOT NULL,
            kalan_durak_sayisi INTEGER NOT NULL,
            hattin_yonu       INTEGER NOT NULL,
            lat               REAL NOT NULL,
            lon               REAL NOT NULL
        )
    """)

    # trip_events: route_id eklendi
    c.execute("""
        CREATE TABLE IF NOT EXISTS trip_events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp  TEXT NOT NULL,
            route_id   INTEGER,
            otobus_id  INTEGER NOT NULL,
            yon        INTEGER NOT NULL,
            stop_id    INTEGER NOT NULL,
            stop_seq   INTEGER NOT NULL,
            stop_name  TEXT,
            event_type TEXT NOT NULL,
            lat        REAL NOT NULL,
            lon        REAL NOT NULL
        )
    """)

    # weather_readings
    c.execute("""
        CREATE TABLE IF NOT EXISTS weather_readings (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp        TEXT NOT NULL,
            source           TEXT NOT NULL,
            temperature      REAL,
            humidity         REAL,
            precipitation    REAL,
            wind_speed       REAL,
            visibility       REAL,
            conditions       TEXT,
            weather_category TEXT NOT NULL
        )
    """)

    # traffic_readings (Route 502, TomTom)
    c.execute("""
        CREATE TABLE IF NOT EXISTS traffic_readings (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp             TEXT NOT NULL,
            source                TEXT NOT NULL,
            segment_id            TEXT NOT NULL,
            from_stop_id          INTEGER NOT NULL,
            to_stop_id            INTEGER NOT NULL,
            from_stop_seq         INTEGER NOT NULL,
            to_stop_seq           INTEGER NOT NULL,
            direction             INTEGER NOT NULL,
            query_lat             REAL NOT NULL,
            query_lon             REAL NOT NULL,
            current_speed         REAL,
            free_flow_speed       REAL,
            congestion_ratio      REAL,
            current_travel_time   REAL,
            free_flow_travel_time REAL,
            confidence            REAL
        )
    """)

    # Indeksler
    c.execute("CREATE INDEX IF NOT EXISTS idx_bp_poll   ON bus_positions(poll_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_bp_bus    ON bus_positions(otobus_id, timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_bp_route  ON bus_positions(route_id, timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sa_stop   ON stop_arrivals(durak_id, timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_te_bus    ON trip_events(otobus_id, timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_te_route  ON trip_events(route_id, timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_wr_ts     ON weather_readings(timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tr_ts     ON traffic_readings(timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tr_seg    ON traffic_readings(segment_id, timestamp)")

    # Migration: mevcut DB'ye route_id sutununu ekle (zaten varsa hata vermez)
    for stmt in (
        "ALTER TABLE bus_positions ADD COLUMN route_id INTEGER",
        "ALTER TABLE trip_events   ADD COLUMN route_id INTEGER",
    ):
        try:
            c.execute(stmt)
        except sqlite3.OperationalError:
            pass  # Sutun zaten mevcut

    conn.commit()
    conn.close()
    log.info(f"Database initialized: {DB_PATH}")


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------

def _categorize_weather(condition):
    c = condition.lower()
    if any(w in c for w in ["rain", "drizzle", "shower", "thunderstorm"]):
        return "rainy"
    elif any(w in c for w in ["overcast", "fog", "mist", "haze"]):
        return "overcast"
    elif any(w in c for w in ["cloud", "partly", "scattered", "broken"]):
        return "partly_cloudy"
    else:
        return "clear"


def fetch_weather():
    """OpenWeatherMap'ten hava durumu cek; key yoksa mock veri uret."""
    if OPENWEATHER_KEY:
        params = urlencode({
            "lat": WEATHER_LAT, "lon": WEATHER_LON,
            "appid": OPENWEATHER_KEY, "units": "metric",
        })
        try:
            req = Request(
                f"http://api.openweathermap.org/data/2.5/weather?{params}",
                headers={"Accept": "application/json"},
            )
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            conditions = data["weather"][0]["description"]
            return {
                "source":           "openweathermap",
                "temperature":      data["main"]["temp"],
                "humidity":         data["main"]["humidity"],
                "precipitation":    data.get("rain", {}).get("1h", 0.0),
                "wind_speed":       data["wind"]["speed"] * 3.6,
                "visibility":       data.get("visibility", 10000) / 1000.0,
                "conditions":       conditions,
                "weather_category": _categorize_weather(conditions),
            }
        except Exception as e:
            log.warning(f"OpenWeatherMap hatasi: {e}. Mock veri kullaniliyor.")

    hour      = datetime.now().hour
    day_seed  = datetime.now().timetuple().tm_yday
    base_temp = 18 + 8 * math.sin(math.pi * (hour - 6) / 12)
    humidity  = 65 - 15 * math.sin(math.pi * (hour - 6) / 12)
    precip    = 2.0 if (day_seed % 7 == 0 and 8 <= hour < 18) else 0.0
    conditions = "rain" if precip > 0 else ("cloud" if humidity > 70 else "clear sky")
    return {
        "source":           "mock",
        "temperature":      round(base_temp, 1),
        "humidity":         round(humidity, 1),
        "precipitation":    precip,
        "wind_speed":       round(8 + 4 * math.sin(math.pi * hour / 12), 1),
        "visibility":       8.0 if precip > 0 else 12.0,
        "conditions":       conditions,
        "weather_category": _categorize_weather(conditions),
    }


def save_weather(timestamp, weather):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO weather_readings
        (timestamp, source, temperature, humidity, precipitation,
         wind_speed, visibility, conditions, weather_category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        timestamp, weather["source"], weather["temperature"],
        weather["humidity"], weather["precipitation"], weather["wind_speed"],
        weather["visibility"], weather["conditions"], weather["weather_category"],
    ))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Traffic (TomTom) — sadece Route 502, ucretsiz limit 2500/gun
# ---------------------------------------------------------------------------

def _build_segment_midpoints():
    """
    Route 502 segment orta noktalarini hesapla (TomTom icin).
    31 segment x 72 istek/gun = 2232 < 2500 (ucretsiz limit).
    Diger hatlara genisletmek icin ucretli TomTom plani gereklidir.
    """
    segments = []
    route502 = ROUTES.get(ROUTE_ID, {})
    dir0 = route502.get("dir0", [])
    for i in range(len(dir0) - 1):
        s1, s2 = dir0[i], dir0[i + 1]
        segments.append({
            "segment_id":   f"{s1['stop_id']}_{s2['stop_id']}",
            "from_stop_id": s1["stop_id"],
            "to_stop_id":   s2["stop_id"],
            "from_stop_seq": s1["seq"],
            "to_stop_seq":  s2["seq"],
            "direction":    0,
            "lat":          round((s1["lat"] + s2["lat"]) / 2, 5),
            "lon":          round((s1["lon"] + s2["lon"]) / 2, 5),
        })
    return segments


ROUTE_SEGMENTS = _build_segment_midpoints()


def fetch_traffic_segment(lat, lon):
    """TomTom Flow Segment Data API'den tek nokta icin trafik bilgisi cek."""
    params = urlencode({"point": f"{lat},{lon}", "unit": "KMPH",
                        "openLr": "false", "key": TOMTOM_KEY})
    data = fetch_json(f"{TOMTOM_FLOW_URL}?{params}")
    if data is None:
        return None
    fsd = data.get("flowSegmentData")
    if fsd is None:
        return None
    current_speed  = fsd.get("currentSpeed", 0)
    free_flow_speed = fsd.get("freeFlowSpeed", 1)
    return {
        "current_speed":         current_speed,
        "free_flow_speed":       free_flow_speed,
        "congestion_ratio":      round(current_speed / free_flow_speed, 3) if free_flow_speed > 0 else 0.0,
        "current_travel_time":   fsd.get("currentTravelTime"),
        "free_flow_travel_time": fsd.get("freeFlowTravelTime"),
        "confidence":            fsd.get("confidence", -1.0),
    }


def fetch_all_traffic():
    """Route 502 segmentleri icin trafik verisi topla."""
    if not TOMTOM_KEY:
        return []
    results = []
    for seg in ROUTE_SEGMENTS:
        traffic = fetch_traffic_segment(seg["lat"], seg["lon"])
        if traffic:
            results.append({**seg, **traffic, "source": "tomtom"})
        else:
            log.warning(f"Trafik verisi alinamadi: segment {seg['segment_id']}")
    return results


def save_traffic(timestamp, traffic_list):
    if not traffic_list:
        return
    conn = sqlite3.connect(DB_PATH)
    for t in traffic_list:
        conn.execute("""
            INSERT INTO traffic_readings
            (timestamp, source, segment_id, from_stop_id, to_stop_id,
             from_stop_seq, to_stop_seq, direction, query_lat, query_lon,
             current_speed, free_flow_speed, congestion_ratio,
             current_travel_time, free_flow_travel_time, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp, t["source"], t["segment_id"],
            t["from_stop_id"], t["to_stop_id"],
            t["from_stop_seq"], t["to_stop_seq"],
            t["direction"], t["lat"], t["lon"],
            t["current_speed"], t["free_flow_speed"], t["congestion_ratio"],
            t["current_travel_time"], t["free_flow_travel_time"], t["confidence"],
        ))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# API yardimcilari
# ---------------------------------------------------------------------------

def fetch_json(url, timeout=10):
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        log.warning(f"HTTP {e.code} — {url}")
        return None
    except (URLError, TimeoutError) as e:
        log.warning(f"Baglanti hatasi — {url}: {e}")
        return None
    except json.JSONDecodeError as e:
        log.warning(f"JSON parse hatasi — {url}: {e}")
        return None


def parse_turkish_float(val):
    if isinstance(val, (int, float)):
        return float(val)
    return float(str(val).replace(",", "."))


# ---------------------------------------------------------------------------
# Bus positions
# ---------------------------------------------------------------------------

def fetch_bus_positions():
    """
    Aktif hatlarin tum otobuslerinin anlik konumlarini paralel olarak getir.
    Her hat icin ayri API cagrisi yapilir.
    Donen her kayit icinde 'route_id' alani bulunur.
    """
    def _fetch_one(route_id):
        url  = ENDPOINT_BUS_POSITIONS.format(hat_id=route_id)
        data = fetch_json(url)
        if data is None:
            return []
        if data.get("HataVarMi", False):
            log.warning(f"Hat {route_id} API hatasi: {data.get('HataMesaj', '?')}")
            return []
        return [
            {
                "route_id":  route_id,
                "otobus_id": item["OtobusId"],
                "yon":       item["Yon"],
                "lat":       parse_turkish_float(item["KoorX"]),
                "lon":       parse_turkish_float(item["KoorY"]),
            }
            for item in data.get("HatOtobusKonumlari", [])
        ]

    all_buses = []
    with ThreadPoolExecutor(max_workers=len(ACTIVE_ROUTE_IDS)) as executor:
        futures = {executor.submit(_fetch_one, rid): rid for rid in ACTIVE_ROUTE_IDS}
        for future in as_completed(futures):
            all_buses.extend(future.result())
    return all_buses


# ---------------------------------------------------------------------------
# Stop arrivals
# ---------------------------------------------------------------------------

def fetch_stop_arrivals(stop_ids):
    """
    Belirtilen duraklara yaklasan otobusleri paralel olarak getir.
    Yalnizca aktif hatlardan gelen kayitlar saklanir; diger hatlar filtrelenir.
    """
    def _fetch_one(sid):
        url  = ENDPOINT_BUSES_AT_STOP.format(durak_id=sid)
        data = fetch_json(url)
        if data is None or not isinstance(data, list):
            return []
        return [
            {
                "durak_id":     sid,
                "otobus_id":    item["OtobusId"],
                "hat_numarasi": item["HatNumarasi"],
                "kalan_durak":  item["KalanDurakSayisi"],
                "hattin_yonu":  item["HattinYonu"],
                "lat":          parse_turkish_float(item["KoorX"]),
                "lon":          parse_turkish_float(item["KoorY"]),
            }
            for item in data
            if item.get("HatNumarasi") in ACTIVE_ROUTE_IDS_SET
        ]

    arrivals = []
    with ThreadPoolExecutor(max_workers=32) as executor:
        futures = {executor.submit(_fetch_one, sid): sid for sid in stop_ids}
        for future in as_completed(futures):
            arrivals.extend(future.result())
    return arrivals


# ---------------------------------------------------------------------------
# Spatial utils
# ---------------------------------------------------------------------------

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_nearest_stop(lat, lon, route_id, yon):
    """
    Verilen konuma en yakin duragi, ilgili hatin ve yonunun duraklari
    arasinda bul. ROUTES sozlugunden yararlanir.
    """
    route = ROUTES.get(route_id)
    if route is None:
        return None, float("inf")
    stops = route["dir0"] if yon == 0 else route["dir1"]
    if not stops:
        return None, float("inf")
    best_stop, best_dist = None, float("inf")
    for s in stops:
        d = haversine_m(lat, lon, s["lat"], s["lon"])
        if d < best_dist:
            best_dist = d
            best_stop = s
    return best_stop, best_dist


# ---------------------------------------------------------------------------
# Trip detection
# ---------------------------------------------------------------------------

# (bus_id, route_id, yon) -> son bilinen durak seq
_last_known_stop: dict = {}


def detect_trip_events(bus_positions, timestamp):
    """
    Otobüslerin durak gecislerini tespit et.
    Her otobus kendi hattinin duraklariyla eslestirilerek
    150m esigini gecer gecmez arrival event uretilir.
    """
    events = []
    for bp in bus_positions:
        bus_id   = bp["otobus_id"]
        route_id = bp["route_id"]
        yon      = bp["yon"]
        stop, dist = find_nearest_stop(bp["lat"], bp["lon"], route_id, yon)

        if stop is None or dist > 150:
            continue

        key      = (bus_id, route_id, yon)
        prev_seq = _last_known_stop.get(key)

        if prev_seq != stop["seq"]:
            events.append({
                "timestamp": timestamp,
                "route_id":  route_id,
                "otobus_id": bus_id,
                "yon":       yon,
                "stop_id":   stop["stop_id"],
                "stop_seq":  stop["seq"],
                "stop_name": stop["name"],
                "event_type": "arrival",
                "lat":       bp["lat"],
                "lon":       bp["lon"],
            })
            _last_known_stop[key] = stop["seq"]

    return events


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def save_poll(timestamp, poll_id, bus_positions, stop_arrivals, trip_events):
    """Bir polling turundaki tum verileri veritabanina kaydet."""
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    for bp in bus_positions:
        stop, dist = find_nearest_stop(bp["lat"], bp["lon"], bp["route_id"], bp["yon"])
        c.execute("""
            INSERT INTO bus_positions
            (timestamp, poll_id, route_id, otobus_id, yon, lat, lon,
             nearest_stop_id, nearest_stop_seq, distance_to_nearest_m)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp, poll_id, bp["route_id"], bp["otobus_id"], bp["yon"],
            bp["lat"], bp["lon"],
            stop["stop_id"] if stop else None,
            stop["seq"]     if stop else None,
            round(dist, 1)  if stop else None,
        ))

    for sa in stop_arrivals:
        c.execute("""
            INSERT INTO stop_arrivals
            (timestamp, poll_id, durak_id, otobus_id, hat_numarasi,
             kalan_durak_sayisi, hattin_yonu, lat, lon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp, poll_id, sa["durak_id"], sa["otobus_id"],
            sa["hat_numarasi"], sa["kalan_durak"],
            sa["hattin_yonu"], sa["lat"], sa["lon"],
        ))

    for te in trip_events:
        c.execute("""
            INSERT INTO trip_events
            (timestamp, route_id, otobus_id, yon, stop_id, stop_seq,
             stop_name, event_type, lat, lon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            te["timestamp"], te["route_id"], te["otobus_id"], te["yon"],
            te["stop_id"], te["stop_seq"], te["stop_name"],
            te["event_type"], te["lat"], te["lon"],
        ))

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

_running = True


def signal_handler(*_):
    global _running
    log.info("Durdurma sinyali alindi, temiz kapatiliyor...")
    _running = False


def poll_once():
    """Tek bir polling turu: GPS konumlari + durak sorgusu + trip detection."""
    now       = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    poll_id   = now.strftime("%Y%m%d_%H%M%S")

    # 1. Otobus konumlari (3 hat, paralel)
    positions = fetch_bus_positions()
    route_counts = {}
    for p in positions:
        route_counts[p["route_id"]] = route_counts.get(p["route_id"], 0) + 1
    log.info(f"Bus positions: {len(positions)} otobus aktif ({len(route_counts)} hatta)")

    # 2. Aktif hat duraklarindaki yaklasan otobusler (paralel)
    arrivals = fetch_stop_arrivals(ALL_ROUTE_STOP_IDS)
    log.info(f"Stop arrivals: {len(arrivals)} kayit ({len(ALL_ROUTE_STOP_IDS)} durak sorgusu)")

    # 3. Trip event detection
    events = detect_trip_events(positions, timestamp)
    if events:
        log.info(f"Trip events: {len(events)} durak gecisi tespit edildi")

    # 4. Kaydet
    save_poll(timestamp, poll_id, positions, arrivals, events)

    return len(positions), len(arrivals), len(events)


_last_weather_fetch: datetime = None
_last_traffic_fetch: datetime = None


def maybe_fetch_weather(now: datetime):
    global _last_weather_fetch
    if _last_weather_fetch is None or \
            (now - _last_weather_fetch).total_seconds() >= WEATHER_INTERVAL_SECONDS:
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        weather   = fetch_weather()
        save_weather(timestamp, weather)
        src = "GERCEK" if weather["source"] == "openweathermap" else "MOCK"
        log.info(
            f"Hava [{src}]: {weather['temperature']}C, {weather['weather_category']}, "
            f"yagis={weather['precipitation']}mm, nem={weather['humidity']}%"
        )
        _last_weather_fetch = now


def maybe_fetch_traffic(now: datetime):
    global _last_traffic_fetch
    if not TOMTOM_KEY:
        return
    if _last_traffic_fetch is None or \
            (now - _last_traffic_fetch).total_seconds() >= TRAFFIC_INTERVAL_SECONDS:
        timestamp    = now.strftime("%Y-%m-%d %H:%M:%S")
        traffic_list = fetch_all_traffic()
        save_traffic(timestamp, traffic_list)
        if traffic_list:
            avg = sum(t["congestion_ratio"] for t in traffic_list) / len(traffic_list)
            log.info(
                f"Trafik [TomTom / Route 502]: {len(traffic_list)}/{len(ROUTE_SEGMENTS)} "
                f"segment, ort.akicilik={avg:.2f}"
            )
        else:
            log.warning("Trafik verisi alinamadi.")
        _last_traffic_fetch = now


# ---------------------------------------------------------------------------
# Test modu
# ---------------------------------------------------------------------------

def run_test():
    """Tum sistemleri test et ve sonuclari logla."""
    log.info("=== TEST MODE (Hat 268, 565, 502) ===")
    init_db()

    # 1. Bus positions
    log.info(f"1. {len(ACTIVE_ROUTE_IDS)} hat icin otobus konumlari sorgulanıyor...")
    positions = fetch_bus_positions()
    route_counts = {}
    for p in positions:
        route_counts[p["route_id"]] = route_counts.get(p["route_id"], 0) + 1
    for rid in sorted(route_counts):
        log.info(f"   Hat {rid:>5}: {route_counts[rid]} aktif otobus")
    log.info(f"   Toplam : {len(positions)} otobus, {len(route_counts)} aktif hat")

    # 2. Stop arrivals — sadece 1 durakla ornek (tam sorgu uzun surer)
    log.info("2. Ornek durak sorgusu (Halkapinar Metro - 10462)...")
    sample_arrivals = fetch_stop_arrivals([10462])
    for a in sample_arrivals:
        log.info(
            f"   Hat {a['hat_numarasi']} Bus {a['otobus_id']}: "
            f"{a['kalan_durak']} durak kaldi"
        )
    if not sample_arrivals:
        log.info("   (Su an yaklasan otobus yok)")
    log.info(
        f"   Tam sorguda {len(ALL_ROUTE_STOP_IDS)} benzersiz durak sorgulanacak."
    )

    # 3. Weather
    log.info("3. Hava durumu test ediliyor...")
    weather  = fetch_weather()
    src_label = "GERCEK (OpenWeatherMap)" if weather["source"] == "openweathermap" \
                else "MOCK (API key yok)"
    log.info(f"   Kaynak   : {src_label}")
    log.info(f"   Sicaklik : {weather['temperature']} C")
    log.info(f"   Nem      : {weather['humidity']} %")
    log.info(f"   Yagis    : {weather['precipitation']} mm")
    log.info(f"   Durum    : {weather['conditions']} ({weather['weather_category']})")

    # 4. Traffic
    log.info("4. Trafik (Route 502, TomTom) test ediliyor...")
    if TOMTOM_KEY:
        test_seg = ROUTE_SEGMENTS[len(ROUTE_SEGMENTS) // 2]
        traffic  = fetch_traffic_segment(test_seg["lat"], test_seg["lon"])
        if traffic:
            log.info(f"   Segment  : {test_seg['segment_id']}")
            log.info(f"   Hiz      : {traffic['current_speed']} km/h (serbest: {traffic['free_flow_speed']} km/h)")
            log.info(f"   Akicilik : {traffic['congestion_ratio']:.2f}")
        else:
            log.warning("   TomTom API'den veri alinamadi!")
    else:
        log.info("   TOMTOM_API_KEY ayarlanmamis — trafik verisi toplanmiyor.")

    log.info(
        f"\nTest tamamlandi: {len(positions)} otobus, "
        f"{len(sample_arrivals)} yaklasma (ornek), "
        f"hava: {weather['weather_category']}"
    )


# ---------------------------------------------------------------------------
# Collector loop
# ---------------------------------------------------------------------------

def run_collector(interval, duration):
    """Ana veri toplama dongusu."""
    signal.signal(signal.SIGINT,  signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    init_db()
    log.info(
        f"Veri toplama basliyor: {len(ACTIVE_ROUTE_IDS)} hat, "
        f"{len(ALL_ROUTE_STOP_IDS)} benzersiz durak, her {interval}s"
    )
    if duration:
        end_time = datetime.now() + timedelta(seconds=duration)
        log.info(f"Sure limiti: {duration}s (bitis: {end_time.strftime('%H:%M:%S')})")
    else:
        end_time = None
        log.info("Sure limiti yok. Ctrl+C ile durdurun.")

    total_polls = total_positions = total_arrivals = total_events = 0
    start_time  = datetime.now()

    while _running:
        if end_time and datetime.now() >= end_time:
            log.info("Sure limiti doldu.")
            break
        try:
            now = datetime.now()
            maybe_fetch_weather(now)
            maybe_fetch_traffic(now)

            n_pos, n_arr, n_evt = poll_once()
            total_polls     += 1
            total_positions += n_pos
            total_arrivals  += n_arr
            total_events    += n_evt

            if total_polls % 10 == 0:
                elapsed = (datetime.now() - start_time).total_seconds() / 60
                log.info(
                    f"--- Ozet: {total_polls} poll, {total_positions} konum, "
                    f"{total_arrivals} yaklasma, {total_events} gecis "
                    f"({elapsed:.1f} dk) ---"
                )
        except Exception as e:
            log.error(f"Poll hatasi: {e}")

        for _ in range(interval):
            if not _running:
                break
            time.sleep(1)

    elapsed = (datetime.now() - start_time).total_seconds() / 60
    log.info(
        f"Toplam: {total_polls} poll, {total_positions} konum, "
        f"{total_arrivals} yaklasma, {total_events} gecis ({elapsed:.1f} dk)"
    )
    log.info("Collector durdu.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ESHOT Real-Time Collector (Hat 268, 565, 502)")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL_SECONDS,
                        help=f"Polling araligi saniye (default: {POLL_INTERVAL_SECONDS})")
    parser.add_argument("--duration", type=int, default=None,
                        help="Toplam calisma suresi saniye (default: sinirsiz)")
    parser.add_argument("--test", action="store_true",
                        help="Tek bir API testi yap ve cik")
    args = parser.parse_args()

    if args.test:
        run_test()
    else:
        run_collector(args.interval, args.duration)
