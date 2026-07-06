# Bağlam Duyarlı Derin Öğrenme ile Otobüs Varış Süresi Tahmini

**CSE496 Bitirme Projesi** — Gebze Teknik Üniversitesi, Bilgisayar Mühendisliği

Referans makale: Kaya & Kalay, *"Spatio-Temporal Forecasting of Bus Arrival Times Using
Context-Aware Deep Learning Models in Urban Transit Systems"*, IEEE Access 2025.

[![DOI](https://zenodo.org/badge/1290911614.svg)](https://doi.org/10.5281/zenodo.21219393)
---

## Proje Özeti

İzmir ESHOT **Route 502** (Cengizhan ↔ Halkapınar Metro) hattı üzerinde, gerçek zamanlı GPS
verisi ve GTFS planlanmış zaman verisini birlikte kullanarak duraklar arası otobüs varış
sürelerini tahmin eden uçtan uca bir makine öğrenmesi sistemi.

Projenin özgün katkısı, **GTFS scheduled time**'ı bir model feature'ı olarak kullanmak ve
İzmir özelinde toplanan gerçek zamanlı veriyle makale sonuçlarını geçmeyi hedeflemektir
(makale MAE: 2.97 dk).

veri toplama sonucunda **1.98M GPS kaydı** ve **138.282 segment** üzerinde
eğitilen modeller, adil (aynı test seti) karşılaştırmada **XGBoost ≈ LSTM > Random Forest**
sonucunu vermiştir; en iyi MAE **0.43 dakika** (XGBoost), en iyi R²/RMSE ise LSTM'e aittir.

---

## Mimari

```
[İzmir Teknoloji API]          [OpenWeatherMap API]        [TomTom Traffic API]
  (GPS, her 30sn)                 (hava, saatlik)            (trafik, 20dk)
        |                              |                          |
        v                              v                          v
                        +-----------------------+
                        |   collector.py         |
                        +-----------------------+
                                      |
                                      v
                              +--------------+
                              |   SQLite DB   |
                              +--------------+
                                      |
                                      v
                              +----------------+
                              | trip_extractor |
                              +----------------+
                                      |
                                      v
                              +--------------------+
                              | build_features_     |
                              | route.py (hat bazlı) |
                              +--------------------+
                                      |
                    +-----------------+-----------------+
                    |                 |                 |
                    v                 v                 v
             +-----------+   +-------------+   +------------+
             | Baseline  |   | LSTM / GRU  |   | Hibrit     |
             | Modeller  |   | (improved_  |   | Stacking   |
             | (RF/XGB)  |   |  lstm.py)   |   | Ensemble   |
             +-----------+   +-------------+   +------------+
                    |                 |                 |
                    v                 v                 v
              +------------------------------------------+
              |     Değerlendirme (evaluation.ipynb)       |
              |  makale karşılaştırma, istatistiksel test  |
              +------------------------------------------+
                                      |
                                      v
                              +----------------+
                              | Demo (harita.  |
                              | html + predict_|
                              | server.py)     |
                              +----------------+
```

---

## Özellikler

1. **Gerçek Zamanlı Veri Toplama** — ESHOT GPS API'den 30sn aralıkla otobüs konumu, saatlik
   hava durumu (OpenWeatherMap), 20dk aralıkla trafik akışı (TomTom)
2. **Trip Extraction** — GPS olaylarından sefer/segment tespiti
3. **Hat-Parametrik Feature Engineering** — GTFS'ten türetilen zamansal, mekânsal, hava
   durumu ve GTFS scheduled-time feature'ları; 502/268/565 hatlarına genelleyebilir
4. **Baseline Modeller** — Naive GTFS, Historical Average, Linear Regression, Random Forest,
   XGBoost
5. **Derin Öğrenme** — Çift girdili LSTM/GRU (sequence branch + context branch)
6. **Hibrit Stacking Ensemble** — Selective Trend + Enhanced XGBoost + LSTM + Ridge meta-model
7. **SHAP / Ablation Analizi** — Feature importance ve GTFS-feature katkısının kanıtı
8. **Kapsamlı Değerlendirme** — Makale karşılaştırması, paired t-test / Wilcoxon anlamlılık
   testleri, koşul bazlı analiz (yön, saat dilimi, hava durumu)
9. **Canlı Demo** — Leaflet tabanlı harita (`demo/harita.html`) + LSTM tahmin sunucusu
   (`demo/predict_server.py`), gerçek ESHOT otobüs konumları üzerinde canlı ETA gösterimi

---

## Güncel Sonuçlar

Adil karşılaştırma (aynı segment test seti, route 502, 81.575 segment, seed=42):

| Sıra | Model | MAE (dk) | RMSE (dk) | R² | Not |
|---|---|---:|---:|---:|---|
| 1 | **XGBoost Improved** | **0.433** | 0.903 | 0.626 | En pratik (cold-start fallback gerekmez) |
| 2 | LSTM (hibrit) | 0.435 | **0.891** | **0.636** | En iyi R²/RMSE |
| 3 | RF Improved | 0.438 | 0.896 | 0.633 | |
| — | Historical Average | 0.645 | 1.317 | 0.206 | baseline |
| — | Naive (GTFS) | 0.734 | 1.516 | -0.05 | baseline |

İstatistiksel olarak XGBoost ile LSTM eşdeğerdir (p=0.38); ikisi de Random Forest'tan anlamlı
şekilde daha iyidir (p<0.01). Detaylı analiz ve 3-hat (502/268/565) genelleme kanıtı için
[reports/progress.md](reports/progress.md) ve [reports/results_analysis.md](reports/results_analysis.md).

---

## Dizin Yapısı

```
├── data/                    # GTFS statik veri + ESHOT açık veri CSV'leri
├── data_collector/          # collector.py, trip_extractor.py, config.py, SQLite DB
├── notebooks/               # feature_engineering, baseline_models, deep_learning,
│                            # hybrid_model, evaluation (sırayla çalıştırılır)
├── scripts/                 # build_features_route.py, improved_ml.py, improved_lstm.py,
│                            # build_multi_route_comparison.py
├── results/tables/          # Model çıktı CSV'leri (baseline, dl, hybrid, ablation, ...)
├── demo/                    # harita.html (Leaflet canlı harita) + predict_server.py (LSTM ETA)
├── reports/                 # Proje dokümantasyonu (bkz. aşağıda)
├── papers/                  # Referans makale (PDF)
├── presentations/           # Sunum şablonu
├── guides/                  # Teknik dokümantasyon (İztek API guide)
```

---

## Kurulum ve Çalıştırma

```bash
pip install -r requirements.txt   # pandas, numpy, scikit-learn, xgboost, torch, jupyter, ...

# 1. Veri toplama (gerçek zamanlı, sürekli çalışır)
python data_collector/collector.py --interval 30

# 2. Ham veriden sefer/segment çıkarma
python data_collector/trip_extractor.py --stats

# 3. Hat-bazlı feature engineering
python scripts/build_features_route.py --route 502

# 4. Model eğitimi
python scripts/improved_ml.py --route 502
python scripts/improved_lstm.py --route 502 --seed 42

# 5. Notebook pipeline (baseline → deep learning → hibrit → değerlendirme)
jupyter notebook notebooks/

# 6. Canlı demo
python demo/predict_server.py   # http://localhost:8000
```

Hava durumu API anahtarı yoksa `OPENWEATHER_API_KEY` ortam değişkeni boş bırakılabilir;
sistem deterministik mock veriye düşer.

---

## Proje Dokümantasyonu (`/reports`)

Bu proje, ilerleyişini `/reports` klasöründeki yaşayan raporlarla takip eder:

| Rapor | İçerik |
|---|---|
| [projectBrief.md](reports/projectBrief.md) | Projenin ne olduğu, hedef kitle, üst seviye mimari |
| [productContext.md](reports/productContext.md) | Kullanıcı personaları, feature öncelikleri, user story'ler |
| [systemPatterns.md](reports/systemPatterns.md) | DB şeması, tasarım desenleri, veri akışları, güvenlik |
| [techContext.md](reports/techContext.md) | Teknoloji stack, dizin yapısı, API endpoint'leri, teknik kararlar |
| [activeContext.md](reports/activeContext.md) | Şu an aktif çalışılan konular ve bloklayıcılar |
| [progress.md](reports/progress.md) | Tamamlanan/kalan işler, deney sonuçları, sürüm tarihçesi |
| [results_analysis.md](reports/results_analysis.md) | Detaylı model sonuç analizi, çok-hat genelleme |
| [graduation_pre_report(_v2/_en).md](reports/graduation_pre_report.md) | Ön rapor taslakları (TR/EN) |

---

## Durum

Teknik pipeline (veri toplama → feature engineering → model eğitimi → değerlendirme) uçtan
uca çalışır durumda ve sonuçlar bilimsel olarak savunulabilir düzeydedir. Canlı demo
kurulmuştur. Kalan öncelik final akademik rapor ve sunumun tamamlanmasıdır — güncel durum
için [reports/activeContext.md](reports/activeContext.md).
