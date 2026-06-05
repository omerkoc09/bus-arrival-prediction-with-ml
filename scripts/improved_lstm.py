"""
Improved LSTM — Bus Travel Time Prediction
==========================================
Baseline LSTM uzerindeki iyilestirmeler:

  1. HuberLoss (delta=1.0)  — L1Loss yerine; buyuk hatalari cezalandirir -> R2 artar
  2. Log-transform (log1p)  — Hedef degiskeni normalize eder -> MAPE dusuror
  3. Window size = 5         — 3'ten arttirildi; daha fazla gecmis bilgi
  4. 2-katmanli LSTM         — Daha derin ogrenme kapasitesi
  5. Batch size = 64         — 16'dan arttirildi; daha karararli gradyanlar
  6. 50 epoch               — 30'dan arttirildi
  7. Yeni ozellikler         — v3 verisi varsa: cumul_deviation, rolling_3_deviation,
                               stop_hist_median, prev_speed_mpm

Kullanim:
    # Once ilgili hat icin feature setini olustur (v2+v3+v4 tek script):
    python build_features_route.py --route 502

    # Sonra bu scripti calistir:
    python improved_lstm.py --route 502
"""

import os
import argparse
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import MinMaxScaler, LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

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
MODELS_DIR   = os.path.join(PROJECT_ROOT, "models")

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(os.path.join(RESULTS_DIR, "tables"), exist_ok=True)
os.makedirs(os.path.join(RESULTS_DIR, "figures"), exist_ok=True)

# ── Hyperparametreler ─────────────────────────────────────────────────────────
WINDOW_SIZE = 5       # 3 -> 5
EPOCHS      = 50      # 30 -> 50
BATCH_SIZE  = 64      # 16 -> 64
PATIENCE    = 15
LR          = 0.001
RNN_UNITS   = 128
DROPOUT     = 0.2

# ── Cihaz ─────────────────────────────────────────────────────────────────────
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("=" * 60)
print("Improved LSTM — Bus Travel Time Prediction")
print("=" * 60)
print(f"Device : {DEVICE}")

# ── Veri yukle ────────────────────────────────────────────────────────────────
if os.path.exists(CSV_V4):
    CSV_PATH = CSV_V4
    print(f"Veri   : v4 (dwell_time_sec + v3 ozellikleri mevcut)")
elif os.path.exists(CSV_V3):
    CSV_PATH = CSV_V3
    print(f"Veri   : v3 (v4/dwell icin: build_features_route.py --route {ROUTE_ID})")
else:
    CSV_PATH = CSV_V2
    print(f"Veri   : v2 (tum ozellikler icin: build_features_route.py --route {ROUTE_ID})")

df = pd.read_csv(CSV_PATH)
print(f"Yuklendi: {len(df)} satir")

# ── Kolon uyumlulugu ──────────────────────────────────────────────────────────
df = df.rename(columns={
    "travel_time_min"     : "travel_minutes",
    "scheduled_travel_min": "scheduled_travel_minutes",
})
df["is_weekend"] = df["day_type"].astype(int)

if "deviation_minutes" not in df.columns:
    df["deviation_minutes"] = df["travel_minutes"] - df["scheduled_travel_minutes"]

# ── Cold-start düzeltmesi ─────────────────────────────────────────────────────
if "prev_travel_time_min" in df.columns:
    df.loc[df["prev_travel_time_min"] == 0.0, "prev_travel_time_min"] = df["scheduled_travel_minutes"]
    print("  prev_travel_time_min: 0.0 değerleri scheduled_travel_minutes ile dolduruldu (Cold-start)")

if "prev_speed_mpm" in df.columns and "distance_m" in df.columns:
    df["prev_speed_mpm"] = (
        df["distance_m"] / df["prev_travel_time_min"].clip(lower=0.01)
    ).clip(upper=2000)
    print("  prev_speed_mpm: düzeltilmiş prev_travel_time_min ile yeniden hesaplandı")

# Kategorik kodlama
_w_map = {0: "clear", 1: "cloudy", 2: "rainy", 3: "snowy"}
df["weather_category"] = df["weather_cat_enc"].map(_w_map).fillna("clear")
df["is_rainy"] = (df["weather_cat_enc"] == 2).astype(int)

_tb_map = {0: "morning_peak", 1: "off_peak", 2: "evening_peak", 3: "night"}
if pd.api.types.is_numeric_dtype(df["time_block"]):
    df["time_block"] = df["time_block"].map(_tb_map).fillna("off_peak")
le_tb = LabelEncoder()
df["time_block_enc"] = le_tb.fit_transform(df["time_block"])

# ── Ozellikler ────────────────────────────────────────────────────────────────
SEQUENCE_FEATURES = [
    "travel_minutes",        # geçmiş durak süreleri (lag) — tahmin anında bilinir
    "scheduled_travel_minutes",
    "distance_m",
    "stop_progress",
]
CONTEXT_FEATURES = [
    "hour", "day_of_week", "is_weekend", "time_block_enc",
    "temperature", "humidity", "precipitation", "is_rainy",
]

# v3 ozellikleri: cumul_deviation ve rolling_3_deviation context'e aliniyor
# (sequence'a eklenirse window icinde matematiksel turetim mumkun olur — leakage riski)
for f in ["cumul_deviation", "rolling_3_deviation",
          "stop_hist_median", "prev_speed_mpm", "stop_hist_ratio",
          "dwell_time_sec", "prev_dwell_time_sec"]:
    if f in df.columns:
        CONTEXT_FEATURES.append(f)
        print(f"  + Context ozellik eklendi : {f}")

TARGET = "travel_minutes"
print(f"\nSequence ozellikler ({len(SEQUENCE_FEATURES)}): {SEQUENCE_FEATURES}")
print(f"Context ozellikler  ({len(CONTEXT_FEATURES)}): {CONTEXT_FEATURES}")
print(f"Window size: {WINDOW_SIZE}")

# ── Sliding window sequence olusturma ────────────────────────────────────────
def create_sequences(df, window_size):
    """
    Her trip için sliding window oluşturur ve sonuçları
    kronolojik (tarih+saat) sırasına göre döndürür.

    Düzeltme: groupby sonrası trip sırası bozuluyordu →
    tüm örnekler arrival_timestamp'e göre sıralanarak döndürülür,
    böylece train/test split tarihsel olarak temiz kalır.
    """
    X_seq_list, X_ctx_list, y_list, ts_list = [], [], [], []
    trip_groups = df.groupby(["bus_id", "yon", "trip_start_time"])
    skipped = 0

    for _, trip in trip_groups:
        trip = trip.sort_values("from_stop_seq", ascending=False)
        if len(trip) < window_size + 1:
            skipped += 1
            continue
        seq_vals    = trip[SEQUENCE_FEATURES].values.astype(np.float32)
        ctx_vals    = trip[CONTEXT_FEATURES].values.astype(np.float32)
        target_vals = trip[TARGET].values.astype(np.float32)
        timestamps  = trip["arrival_timestamp"].values

        for i in range(window_size, len(trip)):
            X_seq_list.append(seq_vals[i - window_size:i])
            X_ctx_list.append(ctx_vals[i])
            y_list.append(target_vals[i])
            ts_list.append(timestamps[i])

    print(f"  Trip atlandı (kisa): {skipped}")
    if not X_seq_list:
        return np.array([]), np.array([]), np.array([])

    # Kronolojik sıralama — train/test split için kritik
    order = np.argsort(ts_list)
    return (np.array(X_seq_list, dtype=np.float32)[order],
            np.array(X_ctx_list, dtype=np.float32)[order],
            np.array(y_list,     dtype=np.float32)[order])


print(f"\nSequence olusturuluyor (window={WINDOW_SIZE})...")
X_seq, X_ctx, y = create_sequences(df, WINDOW_SIZE)
print(f"X_seq: {X_seq.shape}  X_ctx: {X_ctx.shape}  y: {y.shape}")

# ── Log-transform ─────────────────────────────────────────────────────────────
# KEY CHANGE: log1p ile hedef degiskeni normalize et
y_log = np.log1p(y)
print(f"\nHedef (orijinal):  min={y.min():.3f}, max={y.max():.3f}, mean={y.mean():.3f}, std={y.std():.3f}")
print(f"Hedef (log1p) :    min={y_log.min():.3f}, max={y_log.max():.3f}, mean={y_log.mean():.3f}, std={y_log.std():.3f}")

# ── Train / Test bolme (kronolojik) ───────────────────────────────────────────
split_idx = int(len(y) * 0.8)
X_seq_tr, X_seq_te = X_seq[:split_idx], X_seq[split_idx:]
X_ctx_tr, X_ctx_te = X_ctx[:split_idx], X_ctx[split_idx:]
y_tr_log, y_te_log = y_log[:split_idx], y_log[split_idx:]
y_te_orig           = y[split_idx:]          # Geri donusum icin orijinal degerler
print(f"\nTrain: {len(y_tr_log)}  Test: {len(y_te_log)}")

# ── Normalizasyon (sadece train'den fit) ──────────────────────────────────────
n_seq_feats = X_seq.shape[2]
scaler_seq  = MinMaxScaler()
X_seq_tr_n  = scaler_seq.fit_transform(
    X_seq_tr.reshape(-1, n_seq_feats)).reshape(X_seq_tr.shape)
X_seq_te_n  = scaler_seq.transform(
    X_seq_te.reshape(-1, n_seq_feats)).reshape(X_seq_te.shape)

scaler_ctx  = MinMaxScaler()
X_ctx_tr_n  = scaler_ctx.fit_transform(X_ctx_tr)
X_ctx_te_n  = scaler_ctx.transform(X_ctx_te)

# ── Model Mimarisi ────────────────────────────────────────────────────────────
class ImprovedLSTM(nn.Module):
    """
    2-katmanli LSTM + Context branch.
    Degisiklikler:
      - num_layers=2  (1'den arttirildi)
      - HuberLoss ile egitilecek (L1Loss yerine)
    """
    def __init__(self, n_seq_feats, n_ctx_feats,
                 rnn_units=RNN_UNITS, dropout=DROPOUT):
        super().__init__()
        self.rnn      = nn.LSTM(n_seq_feats, rnn_units,
                                num_layers=2,       # KEY CHANGE
                                batch_first=True,
                                dropout=dropout)
        self.rnn_drop = nn.Dropout(dropout)

        self.ctx_fc   = nn.Linear(n_ctx_feats, 32)
        self.ctx_relu = nn.ReLU()
        self.ctx_drop = nn.Dropout(dropout)

        self.fc1      = nn.Linear(rnn_units + 32, 64)
        self.fc1_relu = nn.ReLU()
        self.fc1_drop = nn.Dropout(dropout)
        self.out      = nn.Linear(64, 1)

    def forward(self, seq_x, ctx_x):
        rnn_out, _ = self.rnn(seq_x)
        rnn_out    = self.rnn_drop(rnn_out[:, -1, :])
        ctx_out    = self.ctx_drop(self.ctx_relu(self.ctx_fc(ctx_x)))
        merged     = torch.cat([rnn_out, ctx_out], dim=1)
        out        = self.fc1_drop(self.fc1_relu(self.fc1(merged)))
        return self.out(out).squeeze(1)


model      = ImprovedLSTM(n_seq_feats, len(CONTEXT_FEATURES)).to(DEVICE)
total_p    = sum(p.numel() for p in model.parameters())
optimizer  = torch.optim.Adam(model.parameters(), lr=LR)
criterion  = nn.HuberLoss(delta=1.0)   # KEY CHANGE: L1Loss -> HuberLoss

print(f"\nModel: ImprovedLSTM | Parametreler: {total_p:,}")
print(f"Loss : HuberLoss(delta=1.0)  [Baseline: L1Loss]")
print(f"Hedef: log1p(y)              [Baseline: y]")

# ── Egitim ────────────────────────────────────────────────────────────────────
Xs_tr = torch.tensor(X_seq_tr_n, dtype=torch.float32)
Xc_tr = torch.tensor(X_ctx_tr_n, dtype=torch.float32)
y_tr  = torch.tensor(y_tr_log,   dtype=torch.float32)

dataset = TensorDataset(Xs_tr, Xc_tr, y_tr)
loader  = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)

val_Xs = torch.tensor(X_seq_te_n, dtype=torch.float32).to(DEVICE)
val_Xc = torch.tensor(X_ctx_te_n, dtype=torch.float32).to(DEVICE)
val_y  = torch.tensor(y_te_log,   dtype=torch.float32).to(DEVICE)

best_val_loss  = float("inf")
best_state     = None
patience_count = 0
history        = {"train": [], "val": []}

print(f"\nEgitim basliyor... (epoch={EPOCHS}, batch={BATCH_SIZE}, patience={PATIENCE})")
for epoch in range(EPOCHS):
    model.train()
    epoch_loss = 0.0
    for Xsb, Xcb, yb in loader:
        Xsb, Xcb, yb = Xsb.to(DEVICE), Xcb.to(DEVICE), yb.to(DEVICE)
        optimizer.zero_grad()
        pred = model(Xsb, Xcb)
        loss = criterion(pred, yb)
        loss.backward()
        optimizer.step()
        epoch_loss += loss.item() * len(yb)

    train_loss = epoch_loss / len(y_tr)

    model.eval()
    with torch.no_grad():
        val_loss = criterion(model(val_Xs, val_Xc), val_y).item()

    history["train"].append(train_loss)
    history["val"].append(val_loss)

    if (epoch + 1) % 5 == 0:
        print(f"  Epoch {epoch+1:3d}: train={train_loss:.4f}  val={val_loss:.4f}")

    if val_loss < best_val_loss:
        best_val_loss  = val_loss
        best_state     = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        patience_count = 0
    else:
        patience_count += 1
        if patience_count >= PATIENCE:
            print(f"  Early stopping: epoch {epoch+1}")
            break

model.load_state_dict(best_state)

# ── Degerlendirme ─────────────────────────────────────────────────────────────
model.eval()
with torch.no_grad():
    y_pred_log = model(val_Xs, val_Xc).cpu().numpy()

# Log-transform geri al
y_pred = np.expm1(y_pred_log)
y_pred = np.clip(y_pred, 0, None)

mae  = mean_absolute_error(y_te_orig, y_pred)
rmse = np.sqrt(mean_squared_error(y_te_orig, y_pred))
r2   = r2_score(y_te_orig, y_pred)
mask = y_te_orig > 0.01
mape = np.mean(np.abs((y_te_orig[mask] - y_pred[mask]) / y_te_orig[mask])) * 100

print(f"\n{'='*60}")
print("IMPROVED LSTM — SONUCLAR")
print(f"{'='*60}")
print(f"MAE  : {mae:.4f} dk")
print(f"RMSE : {rmse:.4f} dk")
print(f"MAPE : {mape:.2f}%")
print(f"R2   : {r2:.4f}")

# Baseline ile karsilastirma — referans degerler SADECE 502 icin gecerli
# (Baseline LSTM yalnizca 502 verisinde egitilmisti; 268/565 icin karsilastirma yapilmaz)
BASE_MAE, BASE_MAPE, BASE_R2 = 0.4138, 42.11, 0.0484
if ROUTE_ID == 502:
    print(f"\n--- Baseline LSTM ile Karsilastirma ---")
    print(f"MAE  : {BASE_MAE:.4f} -> {mae:.4f}  ({mae - BASE_MAE:+.4f} dk, {(mae - BASE_MAE)/BASE_MAE*100:+.1f}%)")
    print(f"MAPE : {BASE_MAPE:.2f}% -> {mape:.2f}%  ({mape - BASE_MAPE:+.2f}%)")
    print(f"R2   : {BASE_R2:.4f} -> {r2:.4f}  ({r2 - BASE_R2:+.4f})")

# ── Sonuclari kaydet ──────────────────────────────────────────────────────────
_rows = [{"model": "Improved LSTM", "MAE (dk)": round(mae, 4), "RMSE (dk)": round(rmse, 4),
          "MAPE (%)": round(mape, 2), "R2": round(r2, 4)}]
if ROUTE_ID == 502:
    _rows.append({"model": "Baseline LSTM", "MAE (dk)": BASE_MAE, "RMSE (dk)": 0.6914,
                  "MAPE (%)": BASE_MAPE, "R2": BASE_R2})
results_df = pd.DataFrame(_rows)
suffix = "" if ROUTE_ID == 502 else f"_route_{ROUTE_ID}"
results_path = os.path.join(RESULTS_DIR, "tables", f"improved_lstm_results{suffix}.csv")
results_df.to_csv(results_path, index=False)
print(f"\nSonuclar kaydedildi: {results_path}")

# ── Modeli kaydet ─────────────────────────────────────────────────────────────
model_path = os.path.join(MODELS_DIR, f"improved_lstm{suffix}.pt")
torch.save({
    "model_state_dict"  : best_state,
    "n_seq_feats"       : n_seq_feats,
    "n_ctx_feats"       : len(CONTEXT_FEATURES),
    "window_size"       : WINDOW_SIZE,
    "sequence_features" : SEQUENCE_FEATURES,
    "context_features"  : CONTEXT_FEATURES,
    "scaler_seq"        : scaler_seq,
    "scaler_ctx"        : scaler_ctx,
    "results"           : {"mae": mae, "rmse": rmse, "mape": mape, "r2": r2},
}, model_path)
print(f"Model kaydedildi  : {model_path}")
