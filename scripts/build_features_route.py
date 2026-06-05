"""
Hat-Parametrik Feature Engineering — v2 + v3 + v4 (tek script)
=============================================================
Eski feature_engineering_v2.ipynb + add_features_v3.py + add_dwell_features.py
mantığını TEK scriptte ve HAT-PARAMETRIK olarak birleştirir. (Bu üç eski dosya
artık silindi; tüm mantıkları burada birleşik ve hat-parametrik halde.)

Eski notebook 502'ye hardcoded'di (GTFS filtresi route_id==502, STOPS_DIR0/1).
Bu script durak koordinatlarını config.ROUTES[route_id]'den alır, GTFS
scheduled sürelerini ilgili route_id için hesaplar. Böylece 268, 565, 502
(ve config'deki herhangi bir ACTIVE_ROUTE_ID) için aynı feature seti üretilir.

Kullanim:
    python build_features_route.py --route 268
    python build_features_route.py --route 565
    python build_features_route.py --route 502        # 502'yi de yeniden uretir

Cikti:
    collected_data/route_<RID>_features_v4.csv   (modeller bunu okur)
    (ara: _v2 ve _v3 de yazilir)
"""

import os
import sys
import argparse
import sqlite3
import warnings
from collections import defaultdict
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ── Yollar ────────────────────────────────────────────────────────────────────
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT  = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
COLLECTOR_DIR = os.path.join(PROJECT_ROOT, "data_collector")
GTFS_DIR      = os.path.join(PROJECT_ROOT, "data", "bus-eshot-gtfs")
OUTPUT_DIR    = os.path.join(PROJECT_ROOT, "collected_data")

DB_CANDIDATES = [
    os.path.join(OUTPUT_DIR, "eshot_buses.db"),
    os.path.join(COLLECTOR_DIR, "collected_data", "eshot_buses.db"),
    os.path.join(COLLECTOR_DIR, "collected_data", "route_502_realtime.db"),
]
DB_PATH = next((p for p in DB_CANDIDATES if os.path.exists(p)), None)

sys.path.insert(0, COLLECTOR_DIR)
import config  # noqa: E402

# ── Dwell yapilandirma (add_dwell_features.py ile ayni) ───────────────────────
DWELL_RADIUS_M = 50
MIN_DWELL_SEC  = 10
MAX_DWELL_SEC  = 600


# ══════════════════════════════════════════════════════════════════════════════
# 1) Segment cikarimi  (notebook Cell 3) — route_id ile filtrelenir
# ══════════════════════════════════════════════════════════════════════════════
def _extract_segments(events, bus_id, yon, route_id):
    if len(events) < 2:
        return []
    segs = []
    trip_start_ts = events[0]["ts"]
    for i in range(1, len(events)):
        prev, curr = events[i - 1], events[i]
        if curr["stop_seq"] != prev["stop_seq"] - 1:
            continue
        travel_sec = (curr["ts"] - prev["ts"]).total_seconds()
        travel_min = travel_sec / 60.0
        if not (0.33 <= travel_min <= 15):
            continue
        if curr["ts"].hour < 6:
            continue
        segs.append({
            "bus_id":            bus_id,
            "route_id":          route_id,
            "yon":               yon,
            "date":              trip_start_ts.strftime("%Y-%m-%d"),
            "trip_start_time":   trip_start_ts.strftime("%H:%M:%S"),
            "arrival_timestamp": curr["ts"].strftime("%Y-%m-%d %H:%M:%S"),
            "from_stop_seq":     prev["stop_seq"],
            "to_stop_seq":       curr["stop_seq"],
            "from_stop_name":    prev["stop_name"],
            "to_stop_name":      curr["stop_name"],
            "travel_seconds":    round(travel_sec, 1),
            "travel_time_min":   round(travel_min, 3),
        })
    return segs


def build_segments(db_path, route_id):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT otobus_id, route_id, yon, stop_id, stop_seq, stop_name, timestamp
        FROM trip_events
        WHERE event_type = 'arrival' AND route_id = ?
        ORDER BY otobus_id, yon, timestamp
        """,
        (route_id,),
    ).fetchall()
    conn.close()
    print(f"  Arrival eventi (route {route_id}): {len(rows)}")

    bus_events = defaultdict(list)
    for row in rows:
        key = (row["otobus_id"], row["yon"], row["route_id"])
        bus_events[key].append({
            "ts":        datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S"),
            "stop_seq":  row["stop_seq"],
            "stop_id":   row["stop_id"],
            "stop_name": row["stop_name"],
        })

    all_segments = []
    for (bus_id, yon, rid), events in bus_events.items():
        current_trip, prev_seq, prev_ts = [], None, None
        for ev in events:
            seq, ts = ev["stop_seq"], ev["ts"]
            if prev_seq is not None:
                gap = (ts - prev_ts).total_seconds()
                if gap > 1800 or seq > prev_seq:
                    all_segments.extend(_extract_segments(current_trip, bus_id, yon, rid))
                    current_trip, prev_seq, prev_ts = [], None, None
                elif seq == prev_seq:
                    continue
            current_trip.append(ev)
            prev_seq, prev_ts = seq, ts
        all_segments.extend(_extract_segments(current_trip, bus_id, yon, rid))
    return all_segments


# ══════════════════════════════════════════════════════════════════════════════
# 2) Zamansal featurelar  (notebook Cell 5)
# ══════════════════════════════════════════════════════════════════════════════
def add_temporal(df):
    df["arrival_timestamp"] = pd.to_datetime(df["arrival_timestamp"])
    df["hour"]        = df["arrival_timestamp"].dt.hour
    df["day_of_week"] = df["arrival_timestamp"].dt.dayofweek
    df["day_type"]    = (df["day_of_week"] >= 5).astype(int)

    def get_time_block(hour):
        if 6  <= hour < 10: return 0
        if 10 <= hour < 17: return 1
        if 17 <= hour < 20: return 2
        return 3

    df["time_block"] = df["hour"].apply(get_time_block)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["dow_sin"]  = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["dow_cos"]  = np.cos(2 * np.pi * df["day_of_week"] / 7)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 3) GTFS scheduled sure  (notebook Cell 7) — route_id parametrik
# ══════════════════════════════════════════════════════════════════════════════
def add_scheduled(df, route_id):
    trips_gtfs = pd.read_csv(os.path.join(GTFS_DIR, "trips.txt"))
    stop_times = pd.read_csv(os.path.join(GTFS_DIR, "stop_times.txt"))

    route_ids = set(trips_gtfs[trips_gtfs["route_id"] == route_id]["trip_id"])
    st = stop_times[stop_times["trip_id"].isin(route_ids)].copy()
    print(f"  GTFS kayit (route {route_id}): {len(st)}")

    def time_to_sec(t):
        h, m, s = t.strip().split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)

    st["arr_sec"] = st["arrival_time"].apply(time_to_sec)
    st["dep_sec"] = st["departure_time"].apply(time_to_sec)
    st = st.sort_values(["trip_id", "stop_sequence"])

    sched_records = []
    for _, grp in st.groupby("trip_id"):
        grp = grp.sort_values("stop_sequence")
        seqs, deps, arrs = grp["stop_sequence"].values, grp["dep_sec"].values, grp["arr_sec"].values
        for i in range(1, len(seqs)):
            secs = arrs[i] - deps[i - 1]
            if secs > 0:
                sched_records.append({"gtfs_from": int(seqs[i - 1]),
                                      "gtfs_to": int(seqs[i]), "sched_sec": secs})

    sched_avg = (pd.DataFrame(sched_records)
                 .groupby(["gtfs_from", "gtfs_to"])["sched_sec"].mean().reset_index())
    sched_avg["scheduled_travel_min"] = (sched_avg["sched_sec"] / 60).round(3)

    before = len(df)
    df = df.merge(
        sched_avg[["gtfs_from", "gtfs_to", "scheduled_travel_min"]],
        left_on=["to_stop_seq", "from_stop_seq"],
        right_on=["gtfs_from", "gtfs_to"], how="inner",
    ).drop(columns=["gtfs_from", "gtfs_to"])
    print(f"  GTFS eslesme: {len(df)}/{before} ({len(df)/max(before,1)*100:.1f}% kaldi)")
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 4) Lag + trip pozisyon featurelari  (notebook Cell 9 + Cell 11)
# ══════════════════════════════════════════════════════════════════════════════
def add_lag_and_trip(df):
    df = df.sort_values(
        ["bus_id", "yon", "date", "trip_start_time", "from_stop_seq"],
        ascending=[True, True, True, True, False],
    ).reset_index(drop=True)
    g = ["bus_id", "yon", "date", "trip_start_time"]

    df["prev_travel_time_min"] = df.groupby(g)["travel_time_min"].shift(1).fillna(0.0)
    df["_dev"] = df["travel_time_min"] - df["scheduled_travel_min"]
    df["prev_deviation"] = df.groupby(g)["_dev"].shift(1).fillna(0.0)
    df = df.drop(columns=["_dev"])

    df["segments_into_trip"] = df.groupby(g).cumcount()
    df["is_trip_start"] = (df["segments_into_trip"] <= 1).astype(int)

    df["_cumsum_tt"] = df.groupby(g)["travel_time_min"].cumsum()
    df["trip_elapsed_min"] = df.groupby(g)["_cumsum_tt"].shift(1).fillna(0.0).round(3)
    df = df.drop(columns=["_cumsum_tt"])

    df["_dev_curr"] = df["travel_time_min"] - df["scheduled_travel_min"]
    df["_cumdev"]   = df.groupby(g)["_dev_curr"].cumsum()
    df["cumulative_deviation"] = df.groupby(g)["_cumdev"].shift(1).fillna(0.0).round(3)
    df = df.drop(columns=["_dev_curr", "_cumdev"])

    df["rolling_travel_avg3"] = (
        df.groupby(g)["travel_time_min"]
        .transform(lambda x: x.shift(1).rolling(window=3, min_periods=1).mean())
        .fillna(0.0).round(3)
    )
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 5) Hava  (notebook Cell 13)
# ══════════════════════════════════════════════════════════════════════════════
def add_weather(df, db_path):
    conn = sqlite3.connect(db_path)
    weather_df = pd.read_sql_query("SELECT * FROM weather_readings ORDER BY timestamp", conn)
    conn.close()
    WMAP = {"clear": 0, "cloudy": 1, "rainy": 2, "snowy": 3}
    if len(weather_df) > 0:
        weather_df["timestamp"] = pd.to_datetime(weather_df["timestamp"])
        weather_df["weather_cat_enc"] = weather_df["weather_category"].map(WMAP).fillna(1)
        df = pd.merge_asof(
            df.sort_values("arrival_timestamp"),
            weather_df[["timestamp", "temperature", "humidity", "precipitation",
                        "wind_speed", "visibility", "weather_category", "weather_cat_enc"]]
                .sort_values("timestamp"),
            left_on="arrival_timestamp", right_on="timestamp",
            direction="nearest", tolerance=pd.Timedelta("2h"),
        ).drop(columns=["timestamp"], errors="ignore")
    else:
        for col in ["temperature", "humidity", "precipitation", "wind_speed",
                    "visibility", "weather_category", "weather_cat_enc"]:
            df[col] = np.nan
    df["is_rainy"] = (df["weather_cat_enc"].fillna(0) >= 2).astype(int)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 6) Trafik  (notebook Cell 15)
# ══════════════════════════════════════════════════════════════════════════════
def add_traffic(df, db_path):
    conn = sqlite3.connect(db_path)
    traffic_df = pd.read_sql_query(
        "SELECT timestamp, from_stop_seq, to_stop_seq, direction, congestion_ratio "
        "FROM traffic_readings ORDER BY timestamp", conn)
    conn.close()
    if len(traffic_df) > 0:
        traffic_df["timestamp"] = pd.to_datetime(traffic_df["timestamp"])
        df["direction"] = df["yon"]
        df = pd.merge_asof(
            df.sort_values("arrival_timestamp"),
            traffic_df[["from_stop_seq", "to_stop_seq", "direction", "timestamp", "congestion_ratio"]]
                .sort_values("timestamp"),
            left_on="arrival_timestamp", right_on="timestamp",
            by=["from_stop_seq", "to_stop_seq", "direction"],
            direction="nearest", tolerance=pd.Timedelta("30min"),
        ).drop(columns=["timestamp", "direction"], errors="ignore")
        df["congestion_ratio"] = df["congestion_ratio"].fillna(1.0)
    else:
        df["congestion_ratio"] = 1.0
    df["congestion_x_scheduled"] = (df["congestion_ratio"] * df["scheduled_travel_min"]).round(3)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 7) Mesafe + stop_progress  (notebook Cell 17) — config.ROUTES[route_id] kullanir
# ══════════════════════════════════════════════════════════════════════════════
def haversine_vectorized(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2) ** 2
    return (R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))).round(1)


def add_distance(df, route_id):
    # Durak listesini config.ROUTES'tan al (502 icin STOPS_DIR0/1 ile ayni icerik)
    if route_id in config.ROUTES:
        stops0 = config.ROUTES[route_id]["dir0"]
        stops1 = config.ROUTES[route_id]["dir1"]
    elif route_id == config.ROUTE_ID:
        stops0, stops1 = config.STOPS_DIR0, config.STOPS_DIR1
    else:
        raise ValueError(f"route {route_id} icin durak listesi yok (config.ROUTES)")

    coord_rows = (
        [{"yon": 0, "seq": s["seq"], "lat": s["lat"], "lon": s["lon"]} for s in stops0] +
        [{"yon": 1, "seq": s["seq"], "lat": s["lat"], "lon": s["lon"]} for s in stops1]
    )
    coord_df = pd.DataFrame(coord_rows)

    df = df.merge(
        coord_df.rename(columns={"seq": "from_stop_seq", "lat": "from_lat", "lon": "from_lon"}),
        on=["yon", "from_stop_seq"], how="left",
    ).merge(
        coord_df.rename(columns={"seq": "to_stop_seq", "lat": "to_lat", "lon": "to_lon"}),
        on=["yon", "to_stop_seq"], how="left",
    )
    df["distance_m"] = haversine_vectorized(
        df["from_lat"], df["from_lon"], df["to_lat"], df["to_lon"])

    max_seq = {0: max(s["seq"] for s in stops0), 1: max(s["seq"] for s in stops1)}
    df["stop_progress"] = df.apply(
        lambda r: round((max_seq[int(r["yon"])] - int(r["to_stop_seq"])) /
                        (max_seq[int(r["yon"])] - 1), 3), axis=1)
    df = df.drop(columns=["from_lat", "from_lon", "to_lat", "to_lon"])
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 8) v3 featurelari  (add_features_v3.py)
# ══════════════════════════════════════════════════════════════════════════════
def add_v3(df):
    df = df.sort_values(["date", "trip_start_time", "from_stop_seq"]).reset_index(drop=True)
    df["deviation_minutes"] = df["travel_time_min"] - df["scheduled_travel_min"]

    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx].copy()

    stop_med = (train_df.groupby(["from_stop_seq", "yon"])["travel_time_min"]
                .median().reset_index().rename(columns={"travel_time_min": "stop_hist_median"}))
    global_med = train_df["travel_time_min"].median()
    df = df.merge(stop_med, on=["from_stop_seq", "yon"], how="left")
    df["stop_hist_median"] = df["stop_hist_median"].fillna(global_med)

    train_df["_ratio"] = train_df["travel_time_min"] / train_df["scheduled_travel_min"].clip(lower=0.01)
    stop_ratio = (train_df.groupby(["from_stop_seq", "yon"])["_ratio"]
                  .median().reset_index().rename(columns={"_ratio": "stop_hist_ratio"}))
    df = df.merge(stop_ratio, on=["from_stop_seq", "yon"], how="left")
    df["stop_hist_ratio"] = df["stop_hist_ratio"].fillna(1.0)

    df = df.sort_values(["date", "bus_id", "yon", "trip_start_time", "from_stop_seq"])
    g = df.groupby(["date", "bus_id", "yon", "trip_start_time"], sort=False)
    df["cumul_deviation"] = g["deviation_minutes"].transform(lambda x: x.shift(1).fillna(0).cumsum())
    df["rolling_3_deviation"] = g["deviation_minutes"].transform(
        lambda x: x.shift(1).rolling(3, min_periods=1).mean().fillna(0))
    df["prev_speed_mpm"] = (df["distance_m"] / df["prev_travel_time_min"].clip(lower=0.01)).clip(upper=2000)
    df = df.sort_values(["date", "trip_start_time", "from_stop_seq"]).reset_index(drop=True)

    for col in ["deviation_minutes", "cumul_deviation", "rolling_3_deviation",
                "stop_hist_median", "stop_hist_ratio", "prev_speed_mpm"]:
        df[col] = df[col].fillna(0)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# 9) v4 dwell featurelari  (add_dwell_features.py) — route_id ile filtrelenir
# ══════════════════════════════════════════════════════════════════════════════
def compute_dwell_table(db_path, route_id):
    conn = sqlite3.connect(db_path)
    df_pos = pd.read_sql_query(
        "SELECT timestamp, otobus_id, nearest_stop_seq, distance_to_nearest_m "
        "FROM bus_positions WHERE distance_to_nearest_m <= ? AND route_id = ? "
        "ORDER BY otobus_id, timestamp",
        conn, params=(DWELL_RADIUS_M, route_id))
    conn.close()
    df_pos["timestamp"] = pd.to_datetime(df_pos["timestamp"])
    df_pos["date"] = df_pos["timestamp"].dt.date.astype(str)

    GAP_SEC = 180
    records = []
    for (bus_id, stop_seq, date), grp in df_pos.groupby(
            ["otobus_id", "nearest_stop_seq", "date"], sort=False):
        ts = grp.sort_values("timestamp")["timestamp"].values
        if len(ts) == 0:
            continue
        s_start = s_end = ts[0]
        for i in range(1, len(ts)):
            diff = (ts[i] - s_end) / np.timedelta64(1, "s")
            if diff <= GAP_SEC:
                s_end = ts[i]
            else:
                dwell = (s_end - s_start) / np.timedelta64(1, "s")
                if dwell >= MIN_DWELL_SEC:
                    records.append({"otobus_id": bus_id, "from_stop_seq": stop_seq, "date": date,
                                    "approx_hour": pd.Timestamp(s_start).hour,
                                    "dwell_time_sec": round(float(min(dwell, MAX_DWELL_SEC)), 1)})
                s_start = s_end = ts[i]
        dwell = (s_end - s_start) / np.timedelta64(1, "s")
        if dwell >= MIN_DWELL_SEC:
            records.append({"otobus_id": bus_id, "from_stop_seq": stop_seq, "date": date,
                            "approx_hour": pd.Timestamp(s_start).hour,
                            "dwell_time_sec": round(float(min(dwell, MAX_DWELL_SEC)), 1)})
    return pd.DataFrame(records)


def add_v4(df, db_path, route_id):
    dwell_df = compute_dwell_table(db_path, route_id)
    if len(dwell_df) == 0:
        df["dwell_time_sec"] = 0.0
        df["prev_dwell_time_sec"] = 0.0
        return df

    df["bus_id"] = df["bus_id"].astype(int)
    df["from_stop_seq"] = df["from_stop_seq"].astype(int)

    dwell_exact = (dwell_df.groupby(["otobus_id", "from_stop_seq", "date", "approx_hour"])
                   ["dwell_time_sec"].mean().reset_index()
                   .rename(columns={"otobus_id": "bus_id", "approx_hour": "hour"}))
    dwell_exact["bus_id"] = dwell_exact["bus_id"].astype(int)
    dwell_exact["from_stop_seq"] = dwell_exact["from_stop_seq"].astype(int)
    dwell_exact["dwell_time_sec"] = dwell_exact["dwell_time_sec"].round(1)
    df = df.merge(dwell_exact, on=["bus_id", "from_stop_seq", "date", "hour"], how="left")

    stop_day_med = (dwell_df.groupby(["from_stop_seq", "date"])["dwell_time_sec"]
                    .median().reset_index().rename(columns={"dwell_time_sec": "_dwell_day_med"}))
    stop_day_med["from_stop_seq"] = stop_day_med["from_stop_seq"].astype(int)
    df = df.merge(stop_day_med, on=["from_stop_seq", "date"], how="left")

    global_med = dwell_df["dwell_time_sec"].median()
    df["dwell_time_sec"] = (df["dwell_time_sec"].fillna(df["_dwell_day_med"])
                            .fillna(global_med).round(1))
    df.drop(columns=["_dwell_day_med"], inplace=True)

    df = df.sort_values(["date", "bus_id", "yon", "trip_start_time", "from_stop_seq"])
    g = df.groupby(["date", "bus_id", "yon", "trip_start_time"], sort=False)
    df["prev_dwell_time_sec"] = g["dwell_time_sec"].transform(
        lambda x: x.shift(1).fillna(global_med)).round(1)
    df = df.sort_values(["date", "trip_start_time", "from_stop_seq"]).reset_index(drop=True)
    return df


# ══════════════════════════════════════════════════════════════════════════════
# Ana akis
# ══════════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", type=int, required=True, help="route_id (ornek: 268, 565, 502)")
    args = ap.parse_args()
    rid = args.route

    if DB_PATH is None:
        raise FileNotFoundError("DB bulunamadi.")

    print("=" * 65)
    print(f"Hat-Parametrik Feature Engineering — route {rid}")
    print("=" * 65)
    print(f"DB: {DB_PATH}")

    # v2: segment + tum temel featurelar
    print("\n[v2] Segment cikarimi ve temel featurelar...")
    df = pd.DataFrame(build_segments(DB_PATH, rid))
    if len(df) == 0:
        raise SystemExit(f"route {rid} icin segment uretilemedi.")
    print(f"  Segment: {len(df)}  | tarih: {df['date'].min()} – {df['date'].max()}")

    df = add_temporal(df)
    df = add_scheduled(df, rid)
    df = add_lag_and_trip(df)
    df = add_weather(df, DB_PATH)
    df = add_traffic(df, DB_PATH)
    df = add_distance(df, rid)

    ID_COLS = ["date", "bus_id", "route_id", "yon", "trip_start_time",
               "from_stop_seq", "to_stop_seq", "from_stop_name", "to_stop_name",
               "arrival_timestamp", "travel_seconds"]
    FEATURE_COLS = [
        "hour", "day_of_week", "day_type", "time_block",
        "hour_sin", "hour_cos", "dow_sin", "dow_cos",
        "stop_progress", "distance_m",
        "prev_travel_time_min", "prev_deviation",
        "segments_into_trip", "is_trip_start", "trip_elapsed_min",
        "cumulative_deviation", "rolling_travel_avg3",
        "scheduled_travel_min",
        "temperature", "humidity", "precipitation", "wind_speed", "visibility",
        "weather_cat_enc", "is_rainy",
        "congestion_ratio", "congestion_x_scheduled",
    ]
    TARGET = "travel_time_min"
    avail_id   = [c for c in ID_COLS      if c in df.columns]
    avail_feat = [c for c in FEATURE_COLS if c in df.columns]
    df = df[avail_id + avail_feat + [TARGET]].copy()
    # arrival_timestamp'i string'e cevir (CSV tutarliligi)
    df["arrival_timestamp"] = pd.to_datetime(df["arrival_timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")

    v2_path = os.path.join(OUTPUT_DIR, f"route_{rid}_features_v2.csv")
    df.to_csv(v2_path, index=False)
    print(f"  -> {v2_path}  ({df.shape[0]} satir, {df.shape[1]} kolon)")

    # v3
    print("\n[v3] Tarihsel + kumulatif featurelar...")
    df = add_v3(df)
    v3_path = os.path.join(OUTPUT_DIR, f"route_{rid}_features_v3.csv")
    df.to_csv(v3_path, index=False)
    print(f"  -> {v3_path}  ({df.shape[1]} kolon)")

    # v4
    print("\n[v4] Dwell time featurelari...")
    df = add_v4(df, DB_PATH, rid)
    v4_path = os.path.join(OUTPUT_DIR, f"route_{rid}_features_v4.csv")
    df.to_csv(v4_path, index=False)
    print(f"  -> {v4_path}  ({df.shape[0]} satir, {df.shape[1]} kolon)")

    print("\nTAMAM. Hedef ozeti:")
    print(f"  travel_time_min: mean={df[TARGET].mean():.3f}  std={df[TARGET].std():.3f}  "
          f"median={df[TARGET].median():.3f}")


if __name__ == "__main__":
    main()
