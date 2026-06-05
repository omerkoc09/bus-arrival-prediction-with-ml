# Pipeline Çalıştırma Rehberi

**Son güncelleme:** 2026-06-05 (refaktör sonrası)
**Amaç:** Projedeki `.py` ve `.ipynb` dosyalarının **hangi sırayla** çalıştırılması gerektiğini, her adımın **girdi/çıktısını** belgeler.

> Bu rehber 2026-06-05 refaktöründen sonra geçerlidir. O tarihte 8 eski script +
> `feature_engineering_v2.ipynb` silindi; feature engineering tek bir hat-parametrik
> scripte (`build_features_route.py`) taşındı.

---

## Genel Akış (özet)

```
[0] collector.py            → route_502_realtime.db   (canlı veri toplama — operasyonel)
         │
         ▼
[1] build_features_route.py → route_<RID>_features_v4.csv   (her hat için ayrı)
         │
         ├──────────────┬─────────────────┐
         ▼              ▼                 ▼
[2] improved_ml.py   [3] improved_lstm.py   (her ikisi de v4 CSV okur)
         │              │
         ▼              ▼
   improved_ml_*.csv   improved_lstm_*.csv  + models/improved_lstm*.pt
         │              │
         └──────┬───────┘
                ▼
[4] build_multi_route_comparison.py → multi_route_comparison.csv  (3 hattı birleştirir)

[5] notebooks/evaluation.ipynb → istatistik + makale karşılaştırma tabloları (502 odaklı)
```

---

## A) GÜNCEL PIPELINE — Hat-Parametrik (önerilen sıra)

Bu, projenin **aktif ve geçerli** akışıdır. Her komut `scripts/` klasöründen çalıştırılır:
`cd scripts`

### Adım 0 — Veri Toplama (operasyonel, normalde zaten yapıldı)

| | |
|---|---|
| **Dosya** | `data_collector/collector.py` |
| **Çalıştırma** | `python collector.py` (uzun süreli canlı toplama) |
| **Girdi** | İzmir Açık Veri API (GPS), OpenWeatherMap, TomTom Traffic |
| **Çıktı** | `data_collector/collected_data/route_502_realtime.db` (3 hat: 268, 565, 502) |
| **Not** | Bu adım veri toplama dönemi boyunca çalışır. Mevcut DB hazırsa **atlanır**. |

### Adım 1 — Feature Engineering (her hat için ayrı çalıştır)

| | |
|---|---|
| **Dosya** | `scripts/build_features_route.py` |
| **Çalıştırma** | `python build_features_route.py --route 502`<br>`python build_features_route.py --route 268`<br>`python build_features_route.py --route 565` |
| **Girdi** | `route_502_realtime.db` + `data/bus-eshot-gtfs/` (trips.txt, stop_times.txt) + `config.ROUTES` |
| **Çıktı** | `collected_data/route_<RID>_features_v2.csv` → `_v3.csv` → `_v4.csv` (üçünü de yazar) |
| **Not** | `--route` **zorunlu**. v4 modellerin okuduğu dosyadır. Durak koordinatları `config.ROUTES[route_id]`'den gelir. |

### Adım 2 — ML Modelleri (XGBoost / RF Improved)

| | |
|---|---|
| **Dosya** | `scripts/improved_ml.py` |
| **Çalıştırma** | `python improved_ml.py --route 502` (sonra `--route 268`, `--route 565`) |
| **Girdi** | `collected_data/route_<RID>_features_v4.csv` (yoksa v3/v2'ye düşer) |
| **Çıktı** | `results/tables/improved_ml_results.csv` (502)<br>`results/tables/improved_ml_results_route_<RID>.csv` (268/565) |
| **Not** | `--route` varsayılan 502. En iyi sonuç: XGBoost Improved (log-transform). |

### Adım 3 — LSTM Modeli (Improved LSTM)

| | |
|---|---|
| **Dosya** | `scripts/improved_lstm.py` |
| **Çalıştırma** | `python improved_lstm.py --route 502` (sonra `--route 268`, `--route 565`) |
| **Girdi** | `collected_data/route_<RID>_features_v4.csv` |
| **Çıktı** | `results/tables/improved_lstm_results[_route_<RID>].csv`<br>`models/improved_lstm[_route_<RID>].pt` |
| **Not** | CPU'da ~3-5 dk/hat (50 epoch). GPU varsa otomatik kullanılır. |

### Adım 4 — Multi-Route Özet Tablo

| | |
|---|---|
| **Dosya** | `scripts/build_multi_route_comparison.py` |
| **Çalıştırma** | `python build_multi_route_comparison.py` (argümansız) |
| **Girdi** | Adım 2 ve 3'ün tüm sonuç CSV'leri + `route_<RID>_features_v4.csv` (veri profili için) |
| **Çıktı** | `results/tables/multi_route_comparison.csv` |
| **Not** | 502/268/565 sonuçlarını yan yana getirir; genelleme kanıtı tablosu. Adım 2-3 üç hat için de tamamlanmış olmalı. |

---

## B) DEĞERLENDIRME NOTEBOOK'U (502 odaklı, isteğe bağlı)

### Adım 5 — Kapsamlı Değerlendirme

| | |
|---|---|
| **Dosya** | `notebooks/evaluation.ipynb` |
| **Çalıştırma** | Jupyter'de baştan sona çalıştır |
| **Girdi** | `collected_data/route_502_features_v4.csv` + `models/improved_lstm.pt` |
| **Çıktı** | `results/tables/` içine: `data_summary.csv`, `full_comparison_table.csv`, `condition_analysis.csv`, `statistical_tests.csv`, `paper_comparison.csv`, `ablation_study.csv` |
| **Not** | Şu an **502'ye odaklı**. İstatistiksel testler, koşul-bazlı analiz ve makale karşılaştırması burada üretilir. |

---

## C) ESKİ NOTEBOOK'LAR (akademik referans — güncel sonuç ÜRETMEZ)

Bu üç notebook **yerinde korunuyor** çünkü baseline/DL/hybrid metodolojisini akademik
teslimde gösteriyorlar. Ancak hâlâ **eski `route_502_features_v2.csv`** (3-hat karışım)
okurlar ve **güncel pipeline'ın parçası değildirler**. Yeniden çalıştırmak gerekmez.

| Dosya | Okur | Üretir (eski) |
|---|---|---|
| `notebooks/baseline_models.ipynb` | `route_502_features_v2.csv` | baseline modeller |
| `notebooks/deep_learning.ipynb` | `route_502_features_v2.csv` | LSTM/GRU (eski Keras/PyTorch) |
| `notebooks/hybrid_model.ipynb` | `route_502_features_v2.csv` | Enhanced XGB, Hybrid Stacking, ablation |

> ⚠️ Bu notebook'lardaki sonuçlar **3-hat karışım verisine** dayanır (eski bug). Güncel,
> bilimsel olarak geçerli sonuçlar **A) bölümündeki** hat-parametrik pipeline'dadır.
> Detay: [results_analysis.md](results_analysis.md) §0 ve §11.

---

## Sıfırdan Tam Çalıştırma (kopyala-yapıştır)

DB hazır olduğu varsayımıyla, üç hat için tüm güncel sonuçları üretmek:

```bash
cd scripts

# 1) Feature engineering (3 hat)
python build_features_route.py --route 502
python build_features_route.py --route 268
python build_features_route.py --route 565

# 2) ML modelleri (3 hat)
python improved_ml.py --route 502
python improved_ml.py --route 268
python improved_ml.py --route 565

# 3) LSTM modelleri (3 hat — yavaş, CPU'da ~15 dk toplam)
python improved_lstm.py --route 502
python improved_lstm.py --route 268
python improved_lstm.py --route 565

# 4) Özet karşılaştırma tablosu
python build_multi_route_comparison.py
```

Ardından isteğe bağlı: `notebooks/evaluation.ipynb`'i Jupyter'de çalıştır (502 istatistik + makale karşılaştırma tabloları).

---

## Bağımlılık Notları

- **GTFS gerekli:** Adım 1, `data/bus-eshot-gtfs/trips.txt` ve `stop_times.txt`'e ihtiyaç duyar (scheduled süreler için).
- **config.py:** `data_collector/config.py` → `ROUTES` sözlüğü her hattın durak koordinatlarını GTFS'ten dinamik yükler. Adım 1'in bağımlılığıdır.
- **Sıra zorunluluğu:** 1 → 2/3 → 4. Adım 2 ve 3 birbirinden bağımsız (paralel çalıştırılabilir), ama ikisi de Adım 1'in v4 çıktısına bağlıdır.
