"""
Trip Extractor - Toplanan gercek zamanli veriden seyahat surelerini cikarir.

trip_events tablosundaki durak gecis olaylarindan:
1. Her otobusun her seferini (trip) tespit eder
2. Duraklar arasi gercek seyahat surelerini hesaplar
3. ML icin hazir CSV dataset olusturur

Not (API yon eslesmesi):
    API Yon=1 -> config.ROUTES[hat]["dir0"] (Cengizhan -> Halkapinar, seq artar)
    API Yon=0 -> config.ROUTES[hat]["dir1"] (Halkapinar -> Cengizhan, seq azalir)
    collector.py find_nearest_stop(yon) ile durak eslesmesi yapiliyor,
    bu nedenle trip_events.stop_seq degerleri zaten dogru stop listesine gore.
    Burada sadece seq'in artan mi azalan mi olduguna bakarak yonu normalize ediyoruz.

Kullanim:
    python trip_extractor.py                    # Tum veriyi isle
    python trip_extractor.py --date 2026-03-26  # Belirli gun
    python trip_extractor.py --stats            # Istatistik goster
"""

import argparse
import csv
import os
import sqlite3
from collections import defaultdict
from datetime import datetime

from config import DATA_DIR, ROUTE_ID

DB_PATH = os.path.join(DATA_DIR, "route_502_realtime.db")
OUTPUT_DIR = os.path.join(DATA_DIR, "extracted_trips")

# Yon etiketi: gosterim icin
YON_LABEL = {0: "Halkapinar->Cengizhan", 1: "Cengizhan->Halkapinar"}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def extract_trips(date_filter=None):
    """
    trip_events tablosundaki durak gecislerinden seyahat surelerini hesaplar.

    Her (otobus_id, yon) cifti icin olay listesi kronolojik siraya dizilir.
    Seq'in artis/azalis yonune gore tutarli segmentler bir 'trip' olarak gruplandırilir.
    30 dk'dan fazla bosluk yeni bir trip baslatir.
    """
    conn = get_db()

    query = """
        SELECT otobus_id, yon, stop_id, stop_seq, stop_name, timestamp
        FROM trip_events
        WHERE event_type = 'arrival'
    """
    params = []
    if date_filter:
        query += " AND timestamp LIKE ?"
        params.append(f"{date_filter}%")
    query += " ORDER BY otobus_id, yon, timestamp"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        print("Veri bulunamadi.")
        return []

    print(f"Isleniyor: {len(rows)} durak gecis olayi")

    # (otobus_id, yon) bazinda grupla
    bus_events = defaultdict(list)
    for row in rows:
        key = (row["otobus_id"], row["yon"])
        bus_events[key].append({
            "timestamp": datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S"),
            "stop_id": row["stop_id"],
            "stop_seq": row["stop_seq"],
            "stop_name": row["stop_name"],
        })

    trips = []
    for (bus_id, yon), events in bus_events.items():
        # Seq artis yonunu belirle:
        # Yon=1 -> dir0 kullaniliyor -> seq 1'den 32'ye artar
        # Yon=0 -> dir1 kullaniliyor -> seq 1'den 28'e artar
        # Her iki durumda da seq artmali — azaliyorsa yeni trip basliyor
        trips.extend(_split_into_trips(bus_id, yon, events))

    print(f"Toplam {len(trips)} trip, "
          f"{sum(len(t['segments']) for t in trips)} segment tespit edildi.")
    return trips


def _split_into_trips(bus_id, yon, events):
    """
    Kronolojik olay listesini trip'lere ayirir.
    Seq geri giderse (yeni sefer basladi) veya 30 dk bosluk varsa yeni trip.
    """
    trips = []
    current = []
    prev_seq = -1
    prev_time = None

    for ev in events:
        seq = ev["stop_seq"]
        ts = ev["timestamp"]

        new_trip = False
        if prev_time and (ts - prev_time).total_seconds() > 1800:
            # 30 dk'dan uzun bosluk = yeni sefer
            new_trip = True
        elif prev_seq != -1 and seq >= prev_seq:
            # Seq artarsa veya ayni durak tekrar = yeni sefer basladi
            new_trip = True

        if new_trip and current:
            record = _build_trip(bus_id, yon, current)
            if record:
                trips.append(record)
            current = []

        current.append(ev)
        prev_seq = seq
        prev_time = ts

    if current:
        record = _build_trip(bus_id, yon, current)
        if record:
            trips.append(record)

    return trips


def _build_trip(bus_id, yon, events):
    """
    Bir trip icin duraklar arasi seyahat surelerini hesaplar.
    En az 2 durak olmayan trip'leri atar.
    """
    if len(events) < 2:
        return None

    segments = []
    for i in range(1, len(events)):
        prev = events[i - 1]
        curr = events[i]

        # Ardisik seq cifti: seq azaliyor (prev=N, curr=N-1)
        if curr["stop_seq"] != prev["stop_seq"] - 1:
            continue

        travel_seconds = (curr["timestamp"] - prev["timestamp"]).total_seconds()
        travel_minutes = travel_seconds / 60.0

        # Makul aralik: 20 saniye – 15 dakika
        if not (0.33 <= travel_minutes <= 15):
            continue

        segments.append({
            "from_seq": prev["stop_seq"],
            "to_seq": curr["stop_seq"],
            "from_stop_name": prev["stop_name"],
            "to_stop_name": curr["stop_name"],
            "travel_seconds": round(travel_seconds, 1),
            "travel_minutes": round(travel_minutes, 2),
        })

    start = events[0]["timestamp"]
    end = events[-1]["timestamp"]

    return {
        "bus_id": bus_id,
        "yon": yon,
        "date": start.strftime("%Y-%m-%d"),
        "start_time": start.strftime("%H:%M:%S"),
        "end_time": end.strftime("%H:%M:%S"),
        "total_minutes": round((end - start).total_seconds() / 60.0, 2),
        "stops_observed": len(events),
        "segments": segments,
        "hour": start.hour,
        "day_of_week": start.weekday(),  # 0=Pazartesi, 6=Pazar
    }


def export_segments_csv(trips, output_path=None):
    """Duraklar arasi seyahat surelerini CSV'ye aktar (ML icin ana tablo)."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, "route_502_segments.csv")

    fieldnames = [
        "date", "bus_id", "yon", "trip_start_time", "hour", "day_of_week",
        "from_stop_seq", "to_stop_seq", "from_stop_name", "to_stop_name",
        "travel_seconds", "travel_minutes",
    ]

    rows = []
    for trip in trips:
        for seg in trip["segments"]:
            rows.append({
                "date": trip["date"],
                "bus_id": trip["bus_id"],
                "yon": trip["yon"],
                "trip_start_time": trip["start_time"],
                "hour": trip["hour"],
                "day_of_week": trip["day_of_week"],
                "from_stop_seq": seg["from_seq"],
                "to_stop_seq": seg["to_seq"],
                "from_stop_name": seg["from_stop_name"],
                "to_stop_name": seg["to_stop_name"],
                "travel_seconds": seg["travel_seconds"],
                "travel_minutes": seg["travel_minutes"],
            })

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Segments CSV: {output_path} ({len(rows)} segment)")
    return output_path


def export_trips_csv(trips, output_path=None):
    """Trip ozet bilgilerini CSV'ye aktar."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, "route_502_trips.csv")

    fieldnames = [
        "date", "bus_id", "yon", "start_time", "end_time",
        "total_minutes", "stops_observed", "segments_extracted",
        "hour", "day_of_week",
    ]

    rows = []
    for trip in trips:
        rows.append({
            "date": trip["date"],
            "bus_id": trip["bus_id"],
            "yon": trip["yon"],
            "start_time": trip["start_time"],
            "end_time": trip["end_time"],
            "total_minutes": trip["total_minutes"],
            "stops_observed": trip["stops_observed"],
            "segments_extracted": len(trip["segments"]),
            "hour": trip["hour"],
            "day_of_week": trip["day_of_week"],
        })

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Trips CSV: {output_path} ({len(rows)} trip)")
    return output_path


def show_stats():
    """Veritabanindaki veri istatistiklerini goster."""
    conn = get_db()

    tables = {
        "bus_positions": "Otobus konum kaydi",
        "stop_arrivals": "Durak yaklasma kaydi",
        "trip_events": "Durak gecis olaylari",
    }

    # weather_readings tablosu varsa ekle
    existing = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    if "weather_readings" in existing:
        tables["weather_readings"] = "Hava durumu kaydi"

    print("=== Veritabani Istatistikleri ===\n")
    for table, desc in tables.items():
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{desc} ({table}): {count:,} kayit")

        if count > 0:
            first = conn.execute(f"SELECT MIN(timestamp) FROM {table}").fetchone()[0]
            last = conn.execute(f"SELECT MAX(timestamp) FROM {table}").fetchone()[0]
            print(f"  Zaman araligi: {first} -> {last}")

            if table == "bus_positions":
                buses = conn.execute(
                    "SELECT COUNT(DISTINCT otobus_id) FROM bus_positions"
                ).fetchone()[0]
                polls = conn.execute(
                    "SELECT COUNT(DISTINCT poll_id) FROM bus_positions"
                ).fetchone()[0]
                print(f"  Benzersiz otobus: {buses}, Toplam poll: {polls}")

            if table == "trip_events":
                per_yon = conn.execute(
                    "SELECT yon, COUNT(*) FROM trip_events GROUP BY yon"
                ).fetchall()
                for yon, cnt in per_yon:
                    print(f"  Yon {yon} ({YON_LABEL.get(yon, '?')}): {cnt} gecis")
        print()

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Route 502 Trip Extractor")
    parser.add_argument("--date", type=str, default=None, help="Tarih filtresi (YYYY-MM-DD)")
    parser.add_argument("--stats", action="store_true", help="Istatistikleri goster")
    args = parser.parse_args()

    if args.stats:
        show_stats()
    else:
        trips = extract_trips(args.date)
        if trips:
            export_segments_csv(trips)
            export_trips_csv(trips)
        else:
            print("Segment olusturulamadi. Daha fazla veri bekleniyor.")
