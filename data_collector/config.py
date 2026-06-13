"""Route Data Collector - Configuration"""

import csv
import os

# --- API endpoints ---
BASE_URL = "https://openapi.izmir.bel.tr/api/iztek"
ENDPOINT_BUS_POSITIONS      = f"{BASE_URL}/hatotobuskonumlari/{{hat_id}}"
ENDPOINT_BUSES_AT_STOP      = f"{BASE_URL}/duragayaklasanotobusler/{{durak_id}}"
ENDPOINT_ROUTE_BUSES_AT_STOP = f"{BASE_URL}/hattinyaklasanotobusleri/{{hat_id}}/{{durak_id}}"

# --- Route 502 kimligi ---
# Sadece kimlik bilgisi; durak listeleri ASIL kaynak olan GTFS'ten gelir
# (asagidaki _load_routes_from_gtfs). 502 ozel olarak TomTom trafik toplama
# ve bazi geriye-donuk importlar (ROUTE_ID) icin referans alinir.
ROUTE_ID   = 502
ROUTE_NAME = "CENGİZHAN - HALKAPINAR METRO"

# --- Collection settings ---
POLL_INTERVAL_SECONDS = 30
DATA_DIR = "collected_data"


# ---------------------------------------------------------------------------
# Top-30 Hat: GTFS'ten dinamik olarak yuklenen cok-hat konfigurasyonu
# Sira: gunluk sefer sayisina gore azalan (GTFS trips.txt analizi)
# ---------------------------------------------------------------------------
ACTIVE_ROUTE_IDS = [268, 565, 502]

ACTIVE_ROUTE_IDS_SET = set(ACTIVE_ROUTE_IDS)

# GTFS statik veri klasoru (config.py'nin bir ust dizininde)
GTFS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "bus-eshot-gtfs")
)


def _load_routes_from_gtfs():
    """
    GTFS dosyalarindan aktif hatlarin durak listelerini yukle.

    Doner:
        {
            route_id (int): {
                "dir0": [{"stop_id", "seq", "name", "lat", "lon"}, ...],
                "dir1": [...]
            },
            ...
        }

    Her hat icin dir0 ve dir1 icin birer temsilci trip secilir;
    o trip'in durak sirasi kullanilir.
    """
    stops_file      = os.path.join(GTFS_DIR, "stops.txt")
    trips_file      = os.path.join(GTFS_DIR, "trips.txt")
    stop_times_file = os.path.join(GTFS_DIR, "stop_times.txt")

    # 1. stops.txt: stop_id -> {name, lat, lon}
    stops_info = {}
    with open(stops_file, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            stops_info[row["stop_id"]] = {
                "name": row["stop_name"],
                "lat":  float(row["stop_lat"]),
                "lon":  float(row["stop_lon"]),
            }

    # 2. trips.txt: her (route_id, direction_id) icin ilk trip_id'yi sec
    target_routes = {str(r) for r in ACTIVE_ROUTE_IDS}
    rep_trips = {}   # (route_id_str, dir_str) -> trip_id
    with open(trips_file, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["route_id"] not in target_routes:
                continue
            key = (row["route_id"], row["direction_id"])
            if key not in rep_trips:
                rep_trips[key] = row["trip_id"]

    needed_trips = set(rep_trips.values())

    # 3. stop_times.txt: secili trip'lerin durak siralarini yukle
    #    (87MB dosyayi bir kez tarar, sadece ihtiyac duyulan trip_id'leri alir)
    trip_stops = {tid: [] for tid in needed_trips}
    with open(stop_times_file, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["trip_id"] not in trip_stops:
                continue
            trip_stops[row["trip_id"]].append(
                (int(row["stop_sequence"]), row["stop_id"])
            )
    for tid in trip_stops:
        trip_stops[tid].sort(key=lambda x: x[0])

    # 4. ROUTES sozlugunu olustur
    routes = {}
    for route_id_int in ACTIVE_ROUTE_IDS:
        rid = str(route_id_int)
        entry = {"dir0": [], "dir1": []}
        for dir_key in ("0", "1"):
            tid = rep_trips.get((rid, dir_key))
            if tid is None:
                continue
            dir_label = f"dir{dir_key}"
            for seq, sid in trip_stops.get(tid, []):
                if sid not in stops_info:
                    continue
                s = stops_info[sid]
                entry[dir_label].append({
                    "stop_id": int(sid),
                    "seq":     seq,
                    "name":    s["name"],
                    "lat":     s["lat"],
                    "lon":     s["lon"],
                })
        routes[route_id_int] = entry
    return routes


# GTFS, tum durak/hat verisinin TEK kaynagidir. Yuklenemezse calismaya devam
# etmek anlamsiz (durak koordinati/sirasi olmadan ne toplama ne feature uretilir),
# bu yuzden acik bir hata firlatilir. (Eski hardcoded STOPS_DIR0/DIR1 fallback'i
# kaldirildi — bkz. Adim 1 refaktoru.)
try:
    ROUTES = _load_routes_from_gtfs()
except Exception as _gtfs_err:
    raise RuntimeError(
        f"GTFS statik verisi yuklenemedi: {_gtfs_err}\n"
        f"Beklenen konum: {GTFS_DIR} (stops.txt, trips.txt, stop_times.txt)\n"
        f"Durak listeleri tamamen GTFS'ten gelir; bu dosyalar olmadan collector "
        f"ve feature pipeline calisamaz."
    ) from _gtfs_err

# Tum aktif hat durak ID'leri (her iki yon, benzersiz)
ALL_ROUTE_STOP_IDS = list({
    s["stop_id"]
    for route in ROUTES.values()
    for stops in (route["dir0"], route["dir1"])
    for s in stops
})
