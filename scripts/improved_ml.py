"""
Improved ML Models — Bus Travel Time Prediction
================================================
Random Forest + XGBoost uzerindeki iyilestirmeler:

  1. Log-transform (log1p)       — Hedef degiskeni normalize eder -> MAPE dusuror, R2 artar
  2. Daha iyi hiperparametreler  — Daha fazla agac, daha derin, daha az min_samples_leaf
  3. Yeni ozellikler             — v3 verisi varsa: cumul_deviation, rolling_3_deviation,
                                   stop_hist_median, prev_speed_mpm, stop_hist_ratio
  4. Segment bazli modeller      — Baslangic/orta/bitis duraklar icin ayri RF modeli
                                   (baslangic duraklarinda hata 2x daha yuksek!)

Kullanim:
    # Once ilgili hat icin feature setini olustur (v2+v3+v4 tek script):
    python build_features_route.py --route 502

    # Sonra bu scripti calistir:
    python improved_ml.py --route 502
"""

import os
import argparse
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

try:
    from xgboost import XGBRegressor
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    print("XGBoost bulunamadi — RF sonuclari gosterilecek")

# ── Hat parametresi ───────────────────────────────────────────────────────────
_ap = argparse.ArgumentParser()
_ap.add_argument("--route", type=int, default=502, help="route_id (502, 268, 565)")
_args, _ = _ap.parse_known_args()
ROUTE_ID = _args.route

# ── Yollar ────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
CSV_V4       = os.path.join(PROJECT_ROOT, "collected_data", f"route_{ROUTE_ID}_features_v4.csv")
CSV_V3       = os.path.join(PROJECT_ROOT, "collected_data", f"route_{ROUTE_ID}_features_v3.csv")
CSV_V2       = os.path.join(PROJECT_ROOT, "collected_data", f"route_{ROUTE_ID}_features_v2.csv")
RESULTS_DIR  = os.path.join(PROJECT_ROOT, "results")

os.makedirs(os.path.join(RESULTS_DIR, "tables"), exist_ok=True)

print("=" * 65)
print("Improved ML Models — Bus Travel Time Prediction")
print("=" * 65)

# ── Veri yukle ────────────────────────────────────────────────────────────────
if os.path.exists(CSV_V4):
    CSV_PATH = CSV_V4
    print(f"Veri: v4 (dwell_time_sec + v3 ozellikleri mevcut)")
elif os.path.exists(CSV_V3):
    CSV_PATH = CSV_V3
    print(f"Veri: v3 (v4/dwell icin: build_features_route.py --route {ROUTE_ID})")
else:
    CSV_PATH = CSV_V2
    print(f"Veri: v2 (tum ozellikler icin: build_features_route.py --route {ROUTE_ID})")

df = pd.read_csv(CSV_PATH)
print(f"Yuklendi: {len(df)} satir, {len(df.columns)} kolon")
print(f"Hedef (travel_time_min): min={df['travel_time_min'].min():.2f}  "
      f"max={df['travel_time_min'].max():.2f}  "
      f"mean={df['travel_time_min'].mean():.2f}  "
      f"std={df['travel_time_min'].std():.2f}")

# ── Kronolojik siralama ───────────────────────────────────────────────────────
df = df.sort_values(["date", "trip_start_time", "from_stop_seq"]).reset_index(drop=True)

# ── Cold-start düzeltmesi ─────────────────────────────────────────────────────
if "prev_travel_time_min" in df.columns:
    df.loc[df["prev_travel_time_min"] == 0.0, "prev_travel_time_min"] = df["scheduled_travel_min"]
    print("  prev_travel_time_min: 0.0 değerleri scheduled_travel_min ile dolduruldu (Cold-start)")

if "prev_speed_mpm" in df.columns and "distance_m" in df.columns:
    df["prev_speed_mpm"] = (
        df["distance_m"] / df["prev_travel_time_min"].clip(lower=0.01)
    ).clip(upper=2000)
    print("  prev_speed_mpm: düzeltilmiş prev_travel_time_min ile yeniden hesaplandı")

TARGET = "travel_time_min"

# ── Ozellik listesi ───────────────────────────────────────────────────────────
BASE_FEATURES = [
    "hour", "day_of_week", "day_type", "time_block",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos",
    "from_stop_seq", "to_stop_seq",
    "distance_m", "stop_progress",
    "prev_travel_time_min", "prev_deviation",
    "scheduled_travel_min",
    "temperature", "humidity", "precipitation", "wind_speed",
    "visibility", "weather_cat_enc", "congestion_ratio",
]
NEW_FEATURES = [
    "cumul_deviation", "rolling_3_deviation",
    "stop_hist_median", "prev_speed_mpm", "stop_hist_ratio",
    "dwell_time_sec", "prev_dwell_time_sec",
]

available_features = [
    f for f in BASE_FEATURES + NEW_FEATURES
    if f in df.columns and df[f].notna().all()
]
added_v3 = [f for f in NEW_FEATURES if f in available_features]
print(f"\nToplam ozellik: {len(available_features)}")
print(f"v3 yeni ozellikler: {added_v3 if added_v3 else 'YOK (v2 verisi kullaniliyor)'}")

X = df[available_features].values
y = df[TARGET].values

# ── Train / Test bolme ────────────────────────────────────────────────────────
split_idx  = int(len(df) * 0.8)
X_train    = X[:split_idx];       X_test    = X[split_idx:]
y_train    = y[:split_idx];       y_test    = y[split_idx:]

# Log-transform hedef
y_train_log = np.log1p(y_train)
y_test_log  = np.log1p(y_test)

print(f"Train: {len(y_train)}  Test: {len(y_test)}")

# ── Metrik fonksiyonu ─────────────────────────────────────────────────────────
def evaluate(y_true, y_pred, name):
    mae  = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2   = r2_score(y_true, y_pred)
    mask = y_true > 0.01
    mape = (np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100
            if mask.sum() > 0 else float("nan"))
    return {
        "model"    : name,
        "MAE (dk)" : round(mae,  4),
        "RMSE (dk)": round(rmse, 4),
        "MAPE (%)" : round(mape, 2),
        "R2"       : round(r2,   4),
    }

results = []

# ═══════════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("1. BASELINE: Random Forest (orijinal parametreler, log-transform YOK)")
print(f"{'='*65}")

rf_base = RandomForestRegressor(
    n_estimators=100, max_depth=10, min_samples_leaf=2,
    random_state=42, n_jobs=-1
)
rf_base.fit(X_train, y_train)
y_pred_base = rf_base.predict(X_test)
r_base = evaluate(y_test, y_pred_base, "RF Baseline (orijinal)")
results.append(r_base)
print(f"MAE={r_base['MAE (dk)']:.4f}  MAPE={r_base['MAPE (%)']:.2f}%  R2={r_base['R2']:.4f}")

# ═══════════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("2. IMPROVED: Random Forest (daha iyi parametreler + log-transform)")
print(f"{'='*65}")
print("  n_estimators: 100 -> 300")
print("  max_depth   : 10  -> 15")
print("  min_samples : 2   -> 1")
print("  Hedef       : y   -> log1p(y)")

rf_imp = RandomForestRegressor(
    n_estimators=300,     # 100 -> 300
    max_depth=15,         # 10  -> 15
    min_samples_leaf=1,   # 2   -> 1
    max_features="sqrt",
    random_state=42,
    n_jobs=-1,
)
rf_imp.fit(X_train, y_train_log)
y_pred_rf_log = rf_imp.predict(X_test)
y_pred_rf     = np.expm1(y_pred_rf_log)
y_pred_rf     = np.clip(y_pred_rf, 0, None)

r_rf = evaluate(y_test, y_pred_rf, "RF Improved (log-transform)")
results.append(r_rf)
print(f"MAE={r_rf['MAE (dk)']:.4f}  MAPE={r_rf['MAPE (%)']:.2f}%  R2={r_rf['R2']:.4f}")

# Feature importances (top 10)
importances = pd.Series(
    rf_imp.feature_importances_, index=available_features
).sort_values(ascending=False)
print("\n  Top 10 Ozellik Onem Sirasi:")
for feat, imp in importances.head(10).items():
    bar = "#" * int(imp * 50)
    print(f"    {feat:30s} {imp:.4f}  {bar}")

# ═══════════════════════════════════════════════════════════════════
if HAS_XGB:
    print(f"\n{'='*65}")
    print("3. IMPROVED: XGBoost (daha iyi parametreler + log-transform)")
    print(f"{'='*65}")
    print("  n_estimators  : 200 -> 500")
    print("  max_depth     : 6   -> 8")
    print("  learning_rate : 0.05 -> 0.03")
    print("  min_child_wt  : 3   -> 1")
    print("  subsample     : yok -> 0.8")
    print("  Hedef         : y   -> log1p(y)")

    xgb_imp = XGBRegressor(
        n_estimators=500,        # 200 -> 500
        max_depth=8,             # 6   -> 8
        learning_rate=0.03,      # 0.05 -> 0.03
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=1,      # 3   -> 1
        random_state=42,
        verbosity=0,
    )
    xgb_imp.fit(X_train, y_train_log)
    y_pred_xgb_log = xgb_imp.predict(X_test)
    y_pred_xgb     = np.expm1(y_pred_xgb_log)
    y_pred_xgb     = np.clip(y_pred_xgb, 0, None)

    r_xgb = evaluate(y_test, y_pred_xgb, "XGBoost Improved (log-transform)")
    results.append(r_xgb)
    print(f"MAE={r_xgb['MAE (dk)']:.4f}  MAPE={r_xgb['MAPE (%)']:.2f}%  R2={r_xgb['R2']:.4f}")

# ═══════════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("4. SEGMENT BAZLI MODEL (Mixture of Experts)")
print(f"{'='*65}")
print("  Baslangic duraklari (stop_progress < 0.33): ayri RF modeli")
print("  Orta duraklar (0.33-0.66)                 : ayri RF modeli")
print("  Bitis duraklari (>0.66)                   : ayri RF modeli")

test_df  = df.iloc[split_idx:].reset_index(drop=True)
train_df = df.iloc[:split_idx].reset_index(drop=True)

y_pred_seg = np.zeros(len(y_test))

segments = [
    ("Baslangic (0-33%)" , 0.00, 0.33),
    ("Orta (33-66%)"     , 0.33, 0.66),
    ("Bitis (66-100%)"   , 0.66, 1.01),
]

for seg_label, lo, hi in segments:
    tr_mask = ((train_df["stop_progress"] >= lo) &
               (train_df["stop_progress"] <  hi)).values
    te_mask = ((test_df["stop_progress"]  >= lo) &
               (test_df["stop_progress"]  <  hi)).values

    n_tr = tr_mask.sum()
    n_te = te_mask.sum()

    if n_tr < 20 or n_te == 0:
        print(f"  {seg_label}: yetersiz veri (train={n_tr}, test={n_te}) -> atlaniyor")
        # Fallback: genel modeli kullan
        y_pred_seg[te_mask] = np.expm1(rf_imp.predict(X_test[te_mask]))
        continue

    X_tr_s = X_train[tr_mask];  y_tr_s = y_train_log[tr_mask]
    X_te_s = X_test[te_mask];   y_te_s = y_test[te_mask]

    rf_seg = RandomForestRegressor(
        n_estimators=200, max_depth=12, min_samples_leaf=1,
        random_state=42, n_jobs=-1
    )
    rf_seg.fit(X_tr_s, y_tr_s)

    y_pred_part = np.expm1(rf_seg.predict(X_te_s))
    y_pred_part = np.clip(y_pred_part, 0, None)
    y_pred_seg[te_mask] = y_pred_part

    seg_mae = mean_absolute_error(y_te_s, y_pred_part)
    seg_r2  = r2_score(y_te_s, y_pred_part)
    print(f"  {seg_label}: n_test={n_te:5d}  MAE={seg_mae:.4f}  R2={seg_r2:.4f}")

r_seg = evaluate(y_test, y_pred_seg, "RF Segment Bazli (Mixture of Experts)")
results.append(r_seg)
print(f"\n  GENEL: MAE={r_seg['MAE (dk)']:.4f}  MAPE={r_seg['MAPE (%)']:.2f}%  R2={r_seg['R2']:.4f}")

# ═══════════════════════════════════════════════════════════════════
print(f"\n{'='*65}")
print("TAM KARSILASTIRMA TABLOSU")
print(f"{'='*65}")

# Baseline metrikleri ekle — referans degerler SADECE 502 icin gecerli
if ROUTE_ID == 502:
    results.extend([
        {"model": "RF Baseline Ref (from notebook)", "MAE (dk)": 0.4695, "RMSE (dk)": 0.8731,
         "MAPE (%)": 50.22, "R2": 0.3325},
        {"model": "LSTM Baseline Ref",               "MAE (dk)": 0.4138, "RMSE (dk)": 0.6914,
         "MAPE (%)": 42.11, "R2": 0.0484},
    ])

results_df = pd.DataFrame(results).sort_values("MAE (dk)")
print(results_df.to_string(index=False))

# En iyi sonuclar
best_r2  = results_df.loc[results_df["R2"].idxmax()]
best_mae = results_df.loc[results_df["MAE (dk)"].idxmin()]
print(f"\nEn yuksek R2  : {best_r2['model']}  -> R2={best_r2['R2']:.4f}")
print(f"En dusuk MAE  : {best_mae['model']} -> MAE={best_mae['MAE (dk)']:.4f}")

# Baseline'a gore iyilesme (RF Improved)
print(f"\nRF Improved iyilesmesi vs RF Baseline (0.4695, 50.22%, 0.3325):")
print(f"  MAE  : {0.4695:.4f} -> {r_rf['MAE (dk)']:.4f}  ({r_rf['MAE (dk)'] - 0.4695:+.4f})")
print(f"  MAPE : {50.22:.2f}% -> {r_rf['MAPE (%)']:.2f}%  ({r_rf['MAPE (%)'] - 50.22:+.2f}%)")
print(f"  R2   : {0.3325:.4f} -> {r_rf['R2']:.4f}  ({r_rf['R2'] - 0.3325:+.4f})")

# ── Kaydet ───────────────────────────────────────────────────────────────────
# Hat 502 icin geriye-donuk uyumlu isim; diger hatlar icin route'lu isim
suffix = "" if ROUTE_ID == 502 else f"_route_{ROUTE_ID}"
out_path = os.path.join(RESULTS_DIR, "tables", f"improved_ml_results{suffix}.csv")
results_df.to_csv(out_path, index=False)
print(f"\nSonuclar kaydedildi: {out_path}")
