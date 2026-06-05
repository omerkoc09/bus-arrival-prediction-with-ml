# Tech Context

## Teknoloji Stack

### Diller ve Cekirdek Kutuphaneler

| Katman | Teknoloji | Versiyon | Kullanim |
|--------|-----------|----------|----------|
| Dil | Python | 3.x | Tum proje |
| Veri isleme | pandas, numpy | — | DataFrame islemleri, numerik hesaplama |
| ML (Baseline) | scikit-learn | — | Linear Regression, Random Forest, XGBoost |
| ML (Gradient Boosting) | xgboost | — | Enhanced XGBoost modeli |
| Deep Learning | TensorFlow / Keras | — | LSTM, GRU modelleri |
| Aciklanabilirlik | shap (opsiyonel) | — | Feature importance goruntulemesi |
| Veritabani | SQLite | 3 | Gercek zamanli veri depolama |
| Hava durumu | OpenWeatherMap API | 2.5 | Saatlik hava verisi |
| Otobus verisi | Izmir Teknoloji API | — | Gercek zamanli GPS |
| Web (todo) | Flask + flask-cors | — | Demo dashboard |
| Notebook | Jupyter | — | Interaktif model gelistirme |
| Gorselestirme | matplotlib, seaborn | — | Grafik ve analizler |

### Harici API'ler

| API | Base URL | Kimlik Dogrulama | Kullanim |
|-----|----------|-----------------|----------|
| ESHOT Otobus Konumlari | `https://openapi.izmir.bel.tr/api/iztek/hatotobuskonumlari/{hatId}` | Yok (anonim) | Anlik GPS konumlari |
| ESHOT Duraga Yaklasan | `https://openapi.izmir.bel.tr/api/iztek/duragayaklasanotobusler/{durakId}` | Yok (anonim) | Kalan durak sayisi |
| ESHOT Hat+Durak | `https://openapi.izmir.bel.tr/api/iztek/hattinyaklasanotobusleri/{hatId}/{durakId}` | Yok (anonim) | Hat bazli yaklasma |
| OpenWeatherMap | `http://api.openweathermap.org/data/2.5/weather` | API Key (env var) | Hava durumu |

---

## Dizin Yapisi

```
bus_arrival/
├── data/                          # Statik veri kaynaklari
│   ├── bus-eshot-gtfs/            # GTFS verisi (7 dosya)
│   │   ├── agency.txt
│   │   ├── calendar.txt
│   │   ├── routes.txt
│   │   ├── shapes.txt             # 10MB - guzergah noktalari
│   │   ├── stop_times.txt         # 87MB - durak zamanlari (ana planlama verisi)
│   │   ├── stops.txt
│   │   └── trips.txt
│   ├── eshot-otobus-*.csv         # ESHOT acik veri CSV'leri (7 dosya)
│   ├── genel-binis-raporu_2015-2022.csv
│   ├── izbb-*.xlsx                # Izmir BB ek verileri (3 dosya)
│   ├── toplum-ulasm-genel-binis-adetleri.csv
│   └── yillara-gore-motorlu-karatasit-sayisi.csv
│
├── data_collector/                # Gercek zamanli veri toplama modulu
│   ├── config.py                  # Route 502 durak listesi, API endpointleri
│   ├── collector.py               # Ana veri toplama scripti (GPS + hava durumu)
│   ├── trip_extractor.py          # Trip/segment cikarma ve CSV export
│   └── collected_data/
│       ├── route_502_realtime.db  # SQLite veritabani (4 tablo)
│       └── extracted_trips/
│           ├── route_502_segments.csv  # ML icin ana dataset
│           ├── route_502_trips.csv     # Sefer ozet bilgileri
│           └── route_502_features.csv  # Feature engineering ciktisi (27 kolon)
│
├── notebooks/                     # Jupyter notebook'lar (sirayla calistirilir)
│   ├── feature_engineering.ipynb  # 1. GTFS + hava birlestirme → features CSV
│   ├── baseline_models.ipynb      # 2. 5 baseline model
│   ├── deep_learning.ipynb        # 3. LSTM / GRU modelleri
│   ├── hybrid_model.ipynb         # 4. Stacking ensemble + SHAP + ablation
│   └── evaluation.ipynb           # 5. Kapsamli degerlendirme + makale karsilastirma
│
├── scripts/                       # Aktif pipeline scriptleri (2026-06-05 refaktor sonrasi)
│   ├── build_features_route.py    # Hat-parametrik feature engineering (v2+v3+v4 tek script)
│   ├── improved_ml.py             # XGBoost/RF Improved (--route arg)
│   ├── improved_lstm.py           # Improved LSTM (--route arg)
│   └── build_multi_route_comparison.py  # 3 hat ozet karsilastirma tablosu
│   # Not: eski/kullanilmayan scriptler (izmir_*, web_dashboard, data_cleaning,
│   #      weather_integration, comprehensive_data_strategy, add_features_v3,
│   #      add_dwell_features, update_evaluation) 2026-06-05'te silindi.
│
├── results/                       # Model ciktilari
│   └── tables/                    # CSV sonuc tablolari
│       ├── baseline_results.csv
│       ├── dl_results.csv
│       ├── hybrid_results.csv
│       ├── ablation_study.csv
│       ├── all_model_results.csv
│       ├── full_comparison_table.csv
│       └── statistical_tests.csv
│
├── reports/                       # Proje dokumantasyonu (bu klasor)
├── papers/                        # Referans makale (PDF)
├── presentations/                 # Sunum sablonu (PPTX)
├── postman-collections/           # API test koleksiyonu
├── guides/                        # Teknik dokumantasyon (Iztek API guide)
│
├── EXECUTION_PLAN.md              # Ana yurume plani (en guncel)
├── ROUTE_502_PILOT_PLAN.md        # Route 502 pilot calisma detaylari
└── .gitignore
```

---

## API Endpointleri (Collector Tarafindan Kullanilan)

### 1. Otobus Konumlari
```
GET https://openapi.izmir.bel.tr/api/iztek/hatotobuskonumlari/502
```
**Response:** `{ HatOtobusKonumlari: [{ OtobusId, Yon, KoorX, KoorY }] }`
- Polling sikligi: Her 30 saniye
- Tipik donus: 5-10 aktif otobus

### 2. Duraga Yaklasan Otobusler
```
GET https://openapi.izmir.bel.tr/api/iztek/duragayaklasanotobusler/{durakId}
```
**Response:** `[{ OtobusId, HatNumarasi, KalanDurakSayisi, HattinYonu, KoorX, KoorY }]`
- 6 kilit durak sorgulanir: 31082, 31062, 20134, 30286, 30280, 10462
- Route 502 disindaki hatlar filtrelenir

### 3. Hava Durumu
```
GET http://api.openweathermap.org/data/2.5/weather?lat=38.46&lon=27.17&appid={key}&units=metric
```
**Response:** Standart OpenWeatherMap JSON
- Polling sikligi: Saatlik
- Fallback: Mock veri (deterministik, saat bazli)

### 4. Demo Dashboard Endpointleri (Planli - Asama 7)
```
GET /                              # Ana sayfa
GET /api/routes                    # Hat listesi
GET /api/stops/{route_id}          # Durak listesi
GET /api/predictions/{route_id}/{stop_id}  # Tahmin sonucu
GET /api/live-map                  # Canli harita verisi
```

---

## Teknik Karar Gerекceleri

| Karar | Neden | Alternatif |
|-------|-------|-----------|
| SQLite (PostgreSQL degil) | Tek kullanicili bitirme projesi, kurulum gerektirmez, tasinabilir | PostgreSQL — gereksiz karmasiklik |
| Jupyter Notebook (Python scripti degil) | Interaktif gelistirme, gorsellerle birlikte sonuc gosterme, juri icin okunabilirlik | Pure .py — goruntuleyici gerektirir |
| ESHOT API (GTFS-RT degil) | GTFS-RT mevcut degil Izmir'de; acik API anonim erisim sunuyor | Scraping — etik sorunlar |
| Ridge stacking (NN stacking degil) | Az veriyle overfitting riski dusuk, yorumlanabilir agirliklar | Neural network meta-model — overfitting |
| Sliding window LSTM (Transformer degil) | Makale ile ayni yaklasim, kisa sekanslar icin yeterli | Transformer — veri miktari yetersiz |
| Mock weather fallback | API key gerektirmeden pipeline'in calismasi | Zorunlu API key — test edilemezlik |
| 150m durak esigi | Sehir ici rotalarda makul; cok kucuk esik false negative, buyuk esik false positive uretir | 50m/300m — deneme yanilma ile secildi |
| Route 502 pilot | 608 trip, 32 durak, metro baglantisi, yogun sefer — ideal test rotasi | Rastgele hat — veri yetersizligi riski |
