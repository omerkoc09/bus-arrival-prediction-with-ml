"""
Route 502 Real-Time Data Collector

Izmir ESHOT API'den Route 502 icin gercek zamanli otobus konum verisi toplar.
Her saatte bir OpenWeatherMap API'den hava durumu da kaydedilir.
Veriler SQLite veritabanina kaydedilir.

Kullanim:
    python collector.py                  # Normal calistir (Ctrl+C ile durdur)
    python collector.py --interval 60    # 60 saniye aralikla topla
    python collector.py --duration 3600  # 1 saat boyunca topla
    python collector.py --test           # Tek bir API cagri testi yap

Hava durumu icin cevresel degisken ayarla (opsiyonel):
    Windows : set OPENWEATHER_API_KEY=your_key_here
    Linux   : export OPENWEATHER_API_KEY=your_key_here
    API key yoksa mock veri kaydedilir (gercek proje icin anahtar alin).
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
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode

from config import (
    ROUTE_ID,
    ENDPOINT_BUS_POSITIONS,
    ENDPOINT_BUSES_AT_STOP,
    ALL_STOP_IDS,
    STOPS_DIR0,
    STOPS_DIR1,
    POLL_INTERVAL_SECONDS,
    DATA_DIR,
)

# --- Hava durumu sabitleri ---
# Route 502 guzergahinin merkez koordinatlari (Bayrakli bolgesi)
WEATHER_LAT = 38.4600
WEATHER_LON = 27.1700
WEATHER_INTERVAL_SECONDS = 3600   # Saatte bir hava durumu cek
OPENWEATHER_KEY = os.getenv("OPENWEATHER_API_KEY", "")

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("collector")


# --- Database ---
DB_PATH = os.path.join(DATA_DIR, "route_502_realtime.db")


def init_db():
    """Veritabani ve tablolari olustur."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Otobus konum kayitlari (ana tablo)
    c.execute("""
        CREATE TABLE IF NOT EXISTS bus_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            poll_id TEXT NOT NULL,
            otobus_id INTEGER NOT NULL,
            yon INTEGER NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            nearest_stop_id INTEGER,
            nearest_stop_seq INTEGER,
            distance_to_nearest_m REAL
        )
    """)

    # Duraga yaklasan otobus kayitlari
    c.execute("""
        CREATE TABLE IF NOT EXISTS stop_arrivals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            poll_id TEXT NOT NULL,
            durak_id INTEGER NOT NULL,
            otobus_id INTEGER NOT NULL,
            hat_numarasi INTEGER NOT NULL,
            kalan_durak_sayisi INTEGER NOT NULL,
            hattin_yonu INTEGER NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL
        )
    """)

    # Seyahat (trip) tespiti - otobuslerin duraklar arasi gecislerini izler
    c.execute("""
        CREATE TABLE IF NOT EXISTS trip_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            otobus_id INTEGER NOT NULL,
            yon INTEGER NOT NULL,
            stop_id INTEGER NOT NULL,
            stop_seq INTEGER NOT NULL,
            stop_name TEXT,
            event_type TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL
        )
    """)

    # Hava durumu kayitlari (saatte bir)
    c.execute("""
        CREATE TABLE IF NOT EXISTS weather_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL,
            temperature REAL,
            humidity REAL,
            precipitation REAL,
            wind_speed REAL,
            visibility REAL,
            conditions TEXT,
            weather_category TEXT NOT NULL
        )
    """)

    # Indeksler
    c.execute("CREATE INDEX IF NOT EXISTS idx_bp_poll ON bus_positions(poll_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_bp_bus ON bus_positions(otobus_id, timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sa_stop ON stop_arrivals(durak_id, timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_te_bus ON trip_events(otobus_id, timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_wr_ts ON weather_readings(timestamp)")

    conn.commit()
    conn.close()
    log.info(f"Database initialized: {DB_PATH}")


# --- Weather ---
def _categorize_weather(condition):
    """Hava durumunu 4 kategoriye ayir (makale standardı)."""
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
    """
    OpenWeatherMap'ten anlık hava durumu cek.
    API key yoksa deterministik mock veri uret (saat bazli, tutarli).
    """
    if OPENWEATHER_KEY:
        params = urlencode({
            "lat": WEATHER_LAT,
            "lon": WEATHER_LON,
            "appid": OPENWEATHER_KEY,
            "units": "metric",
        })
        url = f"http://api.openweathermap.org/data/2.5/weather?{params}"
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            conditions = data["weather"][0]["description"]
            return {
                "source": "openweathermap",
                "temperature": data["main"]["temp"],
                "humidity": data["main"]["humidity"],
                "precipitation": data.get("rain", {}).get("1h", 0.0),
                "wind_speed": data["wind"]["speed"] * 3.6,  # m/s -> km/h
                "visibility": data.get("visibility", 10000) / 1000.0,
                "conditions": conditions,
                "weather_category": _categorize_weather(conditions),
            }
        except Exception as e:
            log.warning(f"OpenWeatherMap hatasi: {e}. Mock veri kullaniliyor.")

    # --- Mock veri (API key yokken veya hata durumunda) ---
    # Saate gore deterministik degerler (rastgele degil, tekrar uretilebilir)
    hour = datetime.now().hour
    base_temp = 18 + 8 * math.sin(math.pi * (hour - 6) / 12)  # Gun ici sicaklik egrisi
    humidity = 65 - 15 * math.sin(math.pi * (hour - 6) / 12)
    # Gunden güne farklılık icin gun sayisi kullan
    day_seed = datetime.now().timetuple().tm_yday
    precip = 2.0 if (day_seed % 7 == 0 and hour in range(8, 18)) else 0.0
    conditions = "rain" if precip > 0 else ("cloud" if humidity > 70 else "clear sky")
    return {
        "source": "mock",
        "temperature": round(base_temp, 1),
        "humidity": round(humidity, 1),
        "precipitation": precip,
        "wind_speed": round(8 + 4 * math.sin(math.pi * hour / 12), 1),
        "visibility": 8.0 if precip > 0 else 12.0,
        "conditions": conditions,
        "weather_category": _categorize_weather(conditions),
    }


def save_weather(timestamp, weather):
    """Hava durumu kaydini veritabanina ekle."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO weather_readings
        (timestamp, source, temperature, humidity, precipitation,
         wind_speed, visibility, conditions, weather_category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        timestamp,
        weather["source"],
        weather["temperature"],
        weather["humidity"],
        weather["precipitation"],
        weather["wind_speed"],
        weather["visibility"],
        weather["conditions"],
        weather["weather_category"],
    ))
    conn.commit()
    conn.close()


# --- API Calls ---
def fetch_json(url, timeout=10):
    """URL'den JSON veri cek."""
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except HTTPError as e:
        log.warning(f"HTTP {e.code} for {url}")
        return None
    except (URLError, TimeoutError) as e:
        log.warning(f"Connection error for {url}: {e}")
        return None
    except json.JSONDecodeError as e:
        log.warning(f"JSON decode error for {url}: {e}")
        return None


def parse_turkish_float(val):
    """Turkce formatli float'u parse et (virgul -> nokta)."""
    if isinstance(val, (int, float)):
        return float(val)
    return float(str(val).replace(",", "."))


def fetch_bus_positions():
    """Route 502 otobuslerinin anlik konumlarini getir."""
    url = ENDPOINT_BUS_POSITIONS.format(hat_id=ROUTE_ID)
    data = fetch_json(url)
    if data is None:
        return []

    if data.get("HataVarMi", False):
        log.warning(f"API error: {data.get('HataMesaj', 'unknown')}")
        return []

    buses = []
    for item in data.get("HatOtobusKonumlari", []):
        buses.append({
            "otobus_id": item["OtobusId"],
            "yon": item["Yon"],
            "lat": parse_turkish_float(item["KoorX"]),
            "lon": parse_turkish_float(item["KoorY"]),
        })
    return buses


def fetch_stop_arrivals(stop_ids):
    """Belirli duraklara yaklasan otobusleri getir (sadece Route 502)."""
    arrivals = []
    for sid in stop_ids:
        url = ENDPOINT_BUSES_AT_STOP.format(durak_id=sid)
        data = fetch_json(url)
        if data is None or not isinstance(data, list):
            continue
        for item in data:
            if item.get("HatNumarasi") != ROUTE_ID:
                continue
            arrivals.append({
                "durak_id": sid,
                "otobus_id": item["OtobusId"],
                "hat_numarasi": item["HatNumarasi"],
                "kalan_durak": item["KalanDurakSayisi"],
                "hattin_yonu": item["HattinYonu"],
                "lat": parse_turkish_float(item["KoorX"]),
                "lon": parse_turkish_float(item["KoorY"]),
            })
    return arrivals


# --- Spatial Utils ---
def haversine_m(lat1, lon1, lat2, lon2):
    """Iki nokta arasi mesafe (metre)."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_nearest_stop(lat, lon, yon):
    """Verilen konuma en yakin duragi bul."""
    stops = STOPS_DIR0 if yon == 0 else STOPS_DIR1
    best = None
    best_dist = float("inf")
    for s in stops:
        d = haversine_m(lat, lon, s["lat"], s["lon"])
        if d < best_dist:
            best_dist = d
            best = s
    return best, best_dist


# --- Trip Detection ---
# Otobus ID -> son bilinen durak (trip event tracking)
_last_known_stop = {}


def detect_trip_events(bus_positions, timestamp):
    """Otobuslerin durak gecislerini tespit et."""
    events = []
    for bp in bus_positions:
        bus_id = bp["otobus_id"]
        yon = bp["yon"]
        stop, dist = find_nearest_stop(bp["lat"], bp["lon"], yon)

        if stop is None or dist > 150:
            # 150m'den uzak = durakta degil
            continue

        key = (bus_id, yon)
        prev_seq = _last_known_stop.get(key)

        if prev_seq != stop["seq"]:
            # Yeni duraga geldi
            events.append({
                "timestamp": timestamp,
                "otobus_id": bus_id,
                "yon": yon,
                "stop_id": stop["stop_id"],
                "stop_seq": stop["seq"],
                "stop_name": stop["name"],
                "event_type": "arrival",
                "lat": bp["lat"],
                "lon": bp["lon"],
            })
            _last_known_stop[key] = stop["seq"]

    return events


# --- Storage ---
def save_poll(timestamp, poll_id, bus_positions, stop_arrivals, trip_events):
    """Bir polling turundaki tum verileri kaydet."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for bp in bus_positions:
        stop, dist = find_nearest_stop(bp["lat"], bp["lon"], bp["yon"])
        c.execute("""
            INSERT INTO bus_positions
            (timestamp, poll_id, otobus_id, yon, lat, lon, nearest_stop_id, nearest_stop_seq, distance_to_nearest_m)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp, poll_id, bp["otobus_id"], bp["yon"],
            bp["lat"], bp["lon"],
            stop["stop_id"] if stop else None,
            stop["seq"] if stop else None,
            round(dist, 1) if stop else None,
        ))

    for sa in stop_arrivals:
        c.execute("""
            INSERT INTO stop_arrivals
            (timestamp, poll_id, durak_id, otobus_id, hat_numarasi, kalan_durak_sayisi, hattin_yonu, lat, lon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp, poll_id, sa["durak_id"], sa["otobus_id"],
            sa["hat_numarasi"], sa["kalan_durak"],
            sa["hattin_yonu"], sa["lat"], sa["lon"],
        ))

    for te in trip_events:
        c.execute("""
            INSERT INTO trip_events
            (timestamp, otobus_id, yon, stop_id, stop_seq, stop_name, event_type, lat, lon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            te["timestamp"], te["otobus_id"], te["yon"],
            te["stop_id"], te["stop_seq"], te["stop_name"],
            te["event_type"], te["lat"], te["lon"],
        ))

    conn.commit()
    conn.close()


# --- Main Loop ---
_running = True


def signal_handler(sig, frame):
    global _running
    log.info("Durdurma sinyali alindi, temiz kapatiliyor...")
    _running = False


def poll_once():
    """Tek bir polling turu calistir."""
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    poll_id = now.strftime("%Y%m%d_%H%M%S")

    # 1. Otobus konumlari
    positions = fetch_bus_positions()
    log.info(f"Bus positions: {len(positions)} otobus aktif")

    # 2. Kilit duraklardaki yaklasan otobusler
    # Tum duraklari sorgulamak API'yi yorar, kilit noktalari sec
    key_stops = [
        31082,  # Cengizhan Son Durak (baslangic)
        31062,  # Alpaslan (orta-baslangic)
        20134,  # Bayrakli Ust Gecit (orta)
        30286,  # Manas (orta-son)
        30280,  # Adliye (son bolge)
        10462,  # Halkapinar Metro (bitis)
    ]
    arrivals = fetch_stop_arrivals(key_stops)
    log.info(f"Stop arrivals: {len(arrivals)} kayit (Route 502)")

    # 3. Trip event detection
    events = detect_trip_events(positions, timestamp)
    if events:
        log.info(f"Trip events: {len(events)} durak gecisi tespit edildi")

    # 4. Kaydet
    save_poll(timestamp, poll_id, positions, arrivals, events)

    return len(positions), len(arrivals), len(events)


# Son hava durumu cekme zamani (baslangicta None -> ilk pollda hemen cek)
_last_weather_fetch: datetime = None


def maybe_fetch_weather(now: datetime):
    """
    WEATHER_INTERVAL_SECONDS sureden fazla gecmisse hava durumu cek ve kaydet.
    Ilk pollda da hemen ceker.
    """
    global _last_weather_fetch
    if _last_weather_fetch is None or (now - _last_weather_fetch).total_seconds() >= WEATHER_INTERVAL_SECONDS:
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        weather = fetch_weather()
        save_weather(timestamp, weather)
        src_label = "GERCEK" if weather["source"] == "openweathermap" else "MOCK"
        log.info(
            f"Hava durumu [{src_label}]: {weather['temperature']}C, "
            f"{weather['weather_category']}, "
            f"yagis={weather['precipitation']}mm, "
            f"nem={weather['humidity']}%"
        )
        _last_weather_fetch = now


def run_test():
    """Tek bir API cagri testi yap ve sonuclari goster."""
    log.info("=== TEST MODE ===")
    init_db()

    log.info("1. Otobus konumlari getiriliyor...")
    positions = fetch_bus_positions()
    for p in positions:
        stop, dist = find_nearest_stop(p["lat"], p["lon"], p["yon"])
        dir_label = "Gidis" if p["yon"] == 0 else "Donus"
        stop_label = f"{stop['name']} ({dist:.0f}m)" if stop else "?"
        log.info(f"  Bus {p['otobus_id']} [{dir_label}] @ ({p['lat']:.4f}, {p['lon']:.4f}) -> {stop_label}")

    log.info("2. Halkapinar Metro (10462) duragi sorgulanıyor...")
    arrivals = fetch_stop_arrivals([10462])
    for a in arrivals:
        log.info(f"  Bus {a['otobus_id']}: {a['kalan_durak']} durak kaldi @ ({a['lat']:.4f}, {a['lon']:.4f})")

    log.info("3. Hava durumu test ediliyor...")
    weather = fetch_weather()
    src_label = "GERCEK (OpenWeatherMap)" if weather["source"] == "openweathermap" else "MOCK (API key yok)"
    log.info(f"  Kaynak   : {src_label}")
    log.info(f"  Sicaklik : {weather['temperature']} C")
    log.info(f"  Nem      : {weather['humidity']} %")
    log.info(f"  Yagis    : {weather['precipitation']} mm")
    log.info(f"  Ruzgar   : {weather['wind_speed']} km/h")
    log.info(f"  Gorunum  : {weather['visibility']} km")
    log.info(f"  Durum    : {weather['conditions']}")
    log.info(f"  Kategori : {weather['weather_category']}")

    log.info(
        f"\nTest tamamlandi. {len(positions)} otobus, "
        f"{len(arrivals)} yaklasan kaydi, hava: {weather['weather_category']}."
    )


def run_collector(interval, duration):
    """Ana veri toplama dongusu."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    init_db()
    log.info(f"Veri toplama basliyor: Route {ROUTE_ID}, her {interval}s")
    if duration:
        end_time = datetime.now() + timedelta(seconds=duration)
        log.info(f"Süre limiti: {duration}s (bitis: {end_time.strftime('%H:%M:%S')})")
    else:
        end_time = None
        log.info("Sure limiti yok. Ctrl+C ile durdurun.")

    total_polls = 0
    total_positions = 0
    total_arrivals = 0
    total_events = 0
    start_time = datetime.now()

    while _running:
        if end_time and datetime.now() >= end_time:
            log.info("Sure limiti doldu.")
            break

        try:
            now = datetime.now()

            # Hava durumu: saatte bir
            maybe_fetch_weather(now)

            # Otobus verisi: her pollda
            n_pos, n_arr, n_evt = poll_once()
            total_polls += 1
            total_positions += n_pos
            total_arrivals += n_arr
            total_events += n_evt

            if total_polls % 10 == 0:
                elapsed = (datetime.now() - start_time).total_seconds() / 60
                log.info(
                    f"--- Ozet: {total_polls} poll, {total_positions} konum, "
                    f"{total_arrivals} yaklasma, {total_events} gecis ({elapsed:.1f} dk) ---"
                )
        except Exception as e:
            log.error(f"Poll hatasi: {e}")

        # Bekle
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
    parser = argparse.ArgumentParser(description="Route 502 Real-Time Data Collector")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL_SECONDS,
                        help=f"Polling araligi (saniye, default: {POLL_INTERVAL_SECONDS})")
    parser.add_argument("--duration", type=int, default=None,
                        help="Toplam calisma suresi (saniye, default: sinirsiz)")
    parser.add_argument("--test", action="store_true",
                        help="Tek bir API testi yap")
    args = parser.parse_args()

    if args.test:
        run_test()
    else:
        run_collector(args.interval, args.duration)
