# Route 502 — Bitirme Projesi Uygulama Planı

**Proje:** Bağlam Duyarlı Derin Öğrenme ile Otobüs Varış Süresi Tahmini
**Referans Makale:** Kaya & Kalay, IEEE Access 2025 (MAE: 2.97 dk, MAPE: 14.79%, R²: 0.9272)
**Hedef:** MAE < 2.5 dk ile makaleyi geçmek

**Son Güncelleme:** 2026-03-26

---

## Mevcut Durum Özeti

| Bileşen | Durum | Dosya |
|---------|-------|-------|
| Veri toplama (GPS + Hava) | ✅ Hazır | `data_collector/collector.py` |
| Route 502 konfigürasyonu | ✅ Hazır | `data_collector/config.py` |
| Trip/segment çıkarma | ✅ Hazır | `data_collector/trip_extractor.py` |
| Feature engineering | ✅ Yazıldı & Test Edildi | `notebooks/feature_engineering.ipynb` |
| Baseline modeller | ✅ Yazıldı & Test Edildi | `notebooks/baseline_models.ipynb` |
| LSTM / GRU modelleri | ✅ Yazıldı & Test Edildi | `notebooks/deep_learning.ipynb` |
| Hibrit model + SHAP | ✅ Yazıldı & Test Edildi | `notebooks/hybrid_model.ipynb` |
| Kapsamlı değerlendirme | ✅ Yazıldı & Test Edildi | `notebooks/evaluation.ipynb` |
| GTFS statik veri | ✅ Mevcut | `data/bus-eshot-gtfs/` |
| Demo sistemi | ⬜ Yapılacak | `web_dashboard.py` |
| Final rapor | ⬜ Yapılacak | — |

**Pipeline 20 dakikalık veri (61 segment) ile test edilmiştir. Tüm kod çalışmaktadır.**
**Şu an yapılması gereken: daha fazla veri toplamak ve notebook'ları yeniden çalıştırmak.**

---

## Veritabanı Yapısı

```
data_collector/collected_data/route_502_realtime.db
├── bus_positions      → Her 30 sn'de otobüs GPS konumları
├── stop_arrivals      → Duraklara yaklaşan otobüsler
├── trip_events        → Tespit edilen durak geçişleri
└── weather_readings   → Her 1 saatte bir hava durumu (OpenWeatherMap veya mock)
```

---

## AŞAMA 0 — Veri Toplama ✅ TAMAMLANDI (ilk test verisi)

### Dosyalar

| Dosya | Açıklama |
|-------|----------|
| `data_collector/collector.py` | Ana veri toplama scripti (hava durumu entegre) |
| `data_collector/config.py` | Route 502 durak listesi ve API adresleri |

### Komutlar

```bash
cd data_collector/

# 1. API ve hava durumu bağlantısını test et
python collector.py --test

# 2. Belirli süre çalıştır (örn. 3 saat = 10800 saniye)
python collector.py --duration 10800

# 3. Süresiz çalıştır (Ctrl+C ile durdur)
python collector.py --interval 30
```

### Hava Durumu API Anahtarı (Opsiyonel)

```bash
# Windows
set OPENWEATHER_API_KEY=your_key_here
python collector.py

# Linux/Mac
export OPENWEATHER_API_KEY=your_key_here
python collector.py
```

> API key yoksa deterministik mock veri kaydedilir.

### Ne Kadar Veri Gerekli?

| Süre | Segment (~) | Yeterlilik |
|------|-------------|-----------|
| 20 dk | ~60 | Pipeline testi (yapıldı ✅) |
| 1 gün | ~500 | İlk anlamlı sonuçlar |
| **1 hafta** | **~3000** | **LSTM için minimum (hedef)** |
| 4 hafta | ~12000 | Makale kalitesi karşılaştırma |

---

## AŞAMA 1 — Ham Veri Çıkarma ✅ TAMAMLANDI

### Dosya

| Dosya | Açıklama |
|-------|----------|
| `data_collector/trip_extractor.py` | GPS verisinden trip ve segment çıkarır |

### Komutlar

```bash
cd data_collector/

# Veritabanı istatistiklerini gör
python trip_extractor.py --stats

# Trip ve segment CSV'lerini oluştur
python trip_extractor.py
```

### Çıktılar

```
data_collector/collected_data/extracted_trips/
├── route_502_segments.csv   ← Duraklar arası gerçek seyahat süreleri
└── route_502_trips.csv      ← Sefer özet bilgileri
```

### Kalite Kontrol

- `travel_minutes` genellikle 0.5–5 dk arasında mı?
- `from_stop_seq` ve `to_stop_seq` farkı 1 mi?
- Negatif değer yok mu?

---

## AŞAMA 2 — Feature Engineering ✅ TAMAMLANDI

### Dosya

```
notebooks/feature_engineering.ipynb
```

### Ne Yapıyor?

`route_502_segments.csv` + GTFS scheduled times + weather_readings → `route_502_features.csv`

Eklenen özellikler:
- **Zamansal:** hour, day_of_week, is_weekend, time_block (morning_peak/off_peak/evening_peak/night)
- **GTFS (özgün katkı):** scheduled_travel_minutes, deviation_minutes
- **Mekansal:** distance_m (Haversine), stop_progress (0–1)
- **Hava durumu:** temperature, humidity, precipitation, wind_speed, visibility, weather_category, is_rainy

### Çıktı

```
data_collector/collected_data/extracted_trips/route_502_features.csv  (27 kolon)
```

---

## AŞAMA 3 — Baseline Modeller ✅ TAMAMLANDI

### Dosya

```
notebooks/baseline_models.ipynb
```

### Modeller

| Model | Açıklama |
|-------|----------|
| Naive (GTFS Scheduled) | Planlanan süreyi doğrudan tahmin olarak kullan |
| Historical Average | (saat × gün_tipi × durak) bazlı ortalama |
| Linear Regression | Tüm sayısal özellikler |
| Random Forest | 100 ağaç, max_depth=10 |
| XGBoost | n_estimators=200, learning_rate=0.05 |

### Çıktılar

```
results/tables/baseline_results.csv
results/figures/baseline_comparison.png
```

---

## AŞAMA 4 — LSTM ve Deep Learning ✅ TAMAMLANDI

### Dosya

```
notebooks/deep_learning.ipynb
```

### Mimari

- **Çift girdili model:** Sequence branch (LSTM/GRU 128 unit) + Context branch (Dense 32)
- **Sliding window:** Önceki N durağın bilgisi → sonraki durağın seyahat süresi
- **Sequence features:** travel_minutes, scheduled_travel_minutes, deviation_minutes, distance_m, stop_progress
- **Context features:** hour, day_of_week, is_weekend, time_block_enc, temperature, humidity, precipitation, is_rainy, weather_enc

### Çıktılar

```
models/lstm_model.keras
models/gru_model.keras
models/scalers.pkl
results/tables/dl_results.csv
results/figures/dl_comparison.png
```

---

## AŞAMA 5 — Hibrit Model (Özgün Katkı) ✅ TAMAMLANDI

### Dosya

```
notebooks/hybrid_model.ipynb
```

### Bileşenler

1. **Selective Trend** — Az verili (saat, gün, yön) kombinasyonları için GTFS + sapma trendi
2. **Enhanced XGBoost** — 17 özellik (deviation_history, schedule_ratio, hour_sin/cos dahil)
3. **LSTM** — Sliding window temporal pattern
4. **Ridge Stacking Meta-Model** — Tüm tahminleri optimal birleştirir
5. **SHAP Analizi** — Feature importance kanıtı (shap kuruluysa)
6. **Ablation Çalışması** — scheduled_travel_minutes ve deviation_history kaldırılınca performans düşüşü

### Ek Feature'lar (sadece bu notebook'ta)

| Feature | Açıklama |
|---------|----------|
| `deviation_history` | Aynı (yön, durak) için geçmiş seferlerin ortalama sapması |
| `schedule_ratio` | travel_minutes / scheduled_travel_minutes |
| `hour_sin`, `hour_cos` | Saatin dairesel encoding'i |

### Çıktılar

```
models/hybrid_model.pkl
models/lstm_hybrid.keras
models/scalers_hybrid.pkl
results/tables/hybrid_results.csv
results/tables/ablation_study.csv
results/tables/all_model_results.csv
results/figures/hybrid_analysis.png
results/figures/shap_summary.png (shap kuruluysa)
results/figures/feature_importance_enhanced.png
```

---

## AŞAMA 6 — Kapsamlı Değerlendirme ✅ TAMAMLANDI

### Dosya

```
notebooks/evaluation.ipynb
```

### Analizler

1. **Makale karşılaştırması** — Kaya & Kalay IEEE Access 2025 ile metrik karşılaştırması
2. **Koşul bazlı performans** — Yön, zaman dilimi, hava durumu, durak pozisyonu
3. **İstatistiksel testler** — Paired t-test, Wilcoxon signed-rank (p < 0.05)
4. **Hata analizi** — Bias, residual dağılımı, büyük hataların incelenmesi
5. **Feature korelasyonları** — Tüm özelliklerin hedefle korelasyonu
6. **Özgün katkı kanıtı** — scheduled_travel_minutes ve deviation_history etkisi

### Çıktılar

```
results/tables/full_comparison_table.csv
results/tables/paper_comparison.csv
results/tables/condition_analysis.csv
results/tables/statistical_tests.csv
results/tables/data_summary.csv
results/figures/comprehensive_evaluation.png
results/figures/weather_time_impact.png
```

---

## AŞAMA 7 — Demo Sistem (Opsiyonel) ⬜ YAPILACAK

> **Ön koşul:** Aşama 5'te model kaydedildi, yeterli veri var

### Yapılacaklar

- `web_dashboard.py`'yi hibrit model ile entegre et
- API endpoint: `GET /predict?stop_id=30286&hour=8&day_type=weekday`
- Harita: Route 502 güzergahı + anlık otobüs konumları
- Dashboard: Son 24 saatin performans metrikleri

---

## AŞAMA 8 — Final Rapor ve Sunum ⬜ YAPILACAK

### Rapor Yapısı

1. **Giriş:** Problem tanımı, motivasyon
2. **İlgili Çalışmalar:** Makale analizi + literatür
3. **Metodoloji:** Veri toplama, feature engineering, model mimarisi
4. **Sonuçlar:** Tüm metrikler, görselleştirmeler
5. **Özgün Katkılar:** Scheduled time feature, İzmir verisi, GTFS+API hibrit yaklaşım
6. **Sonuç ve Gelecek Çalışmalar**

---

## Veri Toplandıktan Sonra Çalıştırma Rehberi

Collector yeterli veri topladıktan sonra (en az 1 hafta önerilir),
aşağıdaki komutları **sırayla** çalıştırarak tüm pipeline'ı yeniden işletin.

### Adım 1: Collector'ı Durdur

```bash
# Ctrl+C ile collector'ı durdur
# Veya duration süresi bittiyse zaten durmuştur
```

### Adım 2: Trip/Segment Çıkarma

```bash
cd data_collector/

# Toplanan veriyi kontrol et
python trip_extractor.py --stats

# Çıktı örneği:
#   trip_events: 15000 kayıt
#   weather_readings: 168 kayıt (1 hafta)
#   Trips: 450, Segments: 3200

# CSV'leri oluştur (önceki CSV'lerin üzerine yazar)
python trip_extractor.py
```

**Kontrol:** `collected_data/extracted_trips/route_502_segments.csv` dosyasını aç,
`travel_minutes` değerlerinin 0.5–5 dk arasında olduğunu doğrula.

### Adım 3: Notebook'ları Sırayla Çalıştır

Jupyter Notebook veya VS Code'da açıp **Run All** yapın.
Her notebook bir öncekinin çıktısına bağlıdır, bu yüzden sıra önemlidir.

```
Sıra  Notebook                       Girdi                          Çıktı
─────────────────────────────────────────────────────────────────────────────
 1    feature_engineering.ipynb       route_502_segments.csv         route_502_features.csv
                                     + GTFS stop_times.txt
                                     + weather_readings (DB)

 2    baseline_models.ipynb           route_502_features.csv         results/tables/baseline_results.csv
                                                                    results/figures/baseline_comparison.png

 3    deep_learning.ipynb             route_502_features.csv         models/lstm_model.keras
                                                                    models/gru_model.keras
                                                                    models/scalers.pkl
                                                                    results/tables/dl_results.csv

 4    hybrid_model.ipynb              route_502_features.csv         models/hybrid_model.pkl
                                     + baseline_results.csv         models/lstm_hybrid.keras
                                                                    results/tables/hybrid_results.csv
                                                                    results/tables/ablation_study.csv
                                                                    results/tables/all_model_results.csv

 5    evaluation.ipynb                route_502_features.csv         results/tables/full_comparison_table.csv
                                     + ablation_study.csv           results/tables/paper_comparison.csv
                                                                    results/tables/statistical_tests.csv
                                                                    results/tables/condition_analysis.csv
                                                                    results/figures/comprehensive_evaluation.png
```

### Alternatif: Komut Satırından Çalıştırma (Jupyter olmadan)

Notebook'ları doğrudan Python scripti olarak da çalıştırabilirsiniz:

```bash
# Proje kök dizininde olduğunuzdan emin olun
cd CSE496-Graduation-Project/

# jupyter nbconvert ile sırayla çalıştır
jupyter nbconvert --to notebook --execute notebooks/feature_engineering.ipynb --output feature_engineering.ipynb
jupyter nbconvert --to notebook --execute notebooks/baseline_models.ipynb --output baseline_models.ipynb
jupyter nbconvert --to notebook --execute notebooks/deep_learning.ipynb --output deep_learning.ipynb
jupyter nbconvert --to notebook --execute notebooks/hybrid_model.ipynb --output hybrid_model.ipynb
jupyter nbconvert --to notebook --execute notebooks/evaluation.ipynb --output evaluation.ipynb
```

### Adım 4: Sonuçları Kontrol Et

```bash
# Tüm model sonuçlarını gör
cat results/tables/all_model_results.csv

# Beklenen çıktı (1 hafta veri ile tahmini):
#   model,MAE (dk),RMSE (dk),MAPE (%),R2
#   Hybrid Stacking,0.80,1.10,15.00,0.85
#   Enhanced XGBoost,0.85,1.15,16.00,0.82
#   ...
#   Makale referans: MAE=2.97, MAPE=14.79, R2=0.9272

# Makale karşılaştırmasını gör
cat results/tables/paper_comparison.csv

# İstatistiksel testleri kontrol et
cat results/tables/statistical_tests.csv
```

### Adım 5: Görselleri İncele

Oluşan görseller `results/figures/` altındadır:

```
results/figures/
├── baseline_comparison.png         ← Baseline model MAE karşılaştırması
├── dl_comparison.png               ← LSTM/GRU training curves + karşılaştırma
├── hybrid_analysis.png             ← Hibrit model + ablation + meta-model ağırlıkları
├── comprehensive_evaluation.png    ← 6 panelli kapsamlı analiz
├── weather_time_impact.png         ← Hava durumu ve zaman dilimi etkisi
├── feature_importance_enhanced.png ← XGBoost feature importance
└── shap_summary.png                ← SHAP beeswarm plot (shap kuruluysa)
```

---

## Opsiyonel Kurulumlar

### SHAP (Feature importance görselleştirme)

```bash
pip install shap
```

Bu kuruluysa `hybrid_model.ipynb` SHAP beeswarm plot üretir.
Kurulu değilse XGBoost'un kendi feature importance'ını kullanır.

### OpenWeatherMap API Key (Gerçek hava verisi)

1. https://openweathermap.org/api adresinden ücretsiz üyelik
2. API key al (anında aktif)
3. Collector çalıştırırken:

```bash
set OPENWEATHER_API_KEY=your_key_here   # Windows
export OPENWEATHER_API_KEY=your_key_here # Linux/Mac
python collector.py --interval 30
```

---

## Proje Teslim Kriterleri

### Minimum Teslim (Geçer Not)

- [x] Çalışan veri toplama sistemi (collector.py + hava durumu)
- [x] Trip extractor çalışıyor
- [x] Feature engineering pipeline
- [x] 5 baseline model çalışıyor
- [ ] En az 1 haftalık gerçek veri
- [ ] MAE < 3.5 dakika
- [ ] Kapsamlı rapor

### Hedeflenen Teslim (İyi Not)

- [x] LSTM/GRU modelleri çalışıyor
- [x] Hibrit stacking ensemble
- [x] Ablation çalışması (scheduled time katkısı kanıtlandı)
- [x] İstatistiksel anlamlılık testleri yazıldı
- [ ] MAE < 2.5 dk (yeterli veri ile)
- [ ] Hava durumu feature etkisi yeterli veri ile kanıtlandı

### Mükemmel Teslim (En İyi Not)

- [x] SHAP analizi kodu hazır
- [ ] Hibrit model MAE < 2.0 dk
- [ ] Çalışan demo uygulaması
- [ ] Akademik yayın taslağı

---

## İlk Test Sonuçları (20 dk / 61 segment)

> Bu sonuçlar pipeline doğrulama amaçlıdır. Yeterli veri ile değişecektir.

| Model | MAE (dk) | MAPE (%) | R² |
|-------|----------|----------|-----|
| Enhanced XGBoost | 0.37 | 21.4 | 0.49 |
| Hybrid Stacking | 0.37 | 21.7 | 0.49 |
| Historical Average | 0.58 | 38.1 | -0.04 |
| Naive (GTFS) | 0.59 | 42.1 | 0.03 |
| Random Forest | 0.61 | 49.5 | 0.05 |
| XGBoost | 0.67 | 51.3 | 0.03 |
| LSTM | 0.95 | 70.0 | -0.33 |
| GRU | 0.97 | 73.9 | -0.42 |

**Not:** LSTM/GRU az veriyle kötü performans gösterir. 1000+ segment ile baseline'ları geçmesi beklenir.

---

## Dosya Yapısı

```
CSE496-Graduation-Project/
├── data_collector/
│   ├── collector.py                ✅ Hazır (hava durumu entegre)
│   ├── config.py                   ✅ Hazır
│   ├── trip_extractor.py           ✅ Hazır
│   └── collected_data/
│       ├── route_502_realtime.db   ✅ Veri toplanıyor
│       └── extracted_trips/
│           ├── route_502_segments.csv   ✅ 61 segment (test)
│           ├── route_502_trips.csv      ✅ 7 trip (test)
│           └── route_502_features.csv   ✅ 61 satır, 27 kolon (test)
├── notebooks/
│   ├── feature_engineering.ipynb   ✅ Yazıldı & Test Edildi
│   ├── baseline_models.ipynb       ✅ Yazıldı & Test Edildi
│   ├── deep_learning.ipynb         ✅ Yazıldı & Test Edildi
│   ├── hybrid_model.ipynb          ✅ Yazıldı & Test Edildi
│   └── evaluation.ipynb            ✅ Yazıldı & Test Edildi
├── models/
│   ├── lstm_model.keras            ✅ Test modeli kaydedildi
│   ├── gru_model.keras             ✅ Test modeli kaydedildi
│   ├── hybrid_model.pkl            ✅ Test modeli kaydedildi
│   ├── lstm_hybrid.keras           ✅ Test modeli kaydedildi
│   ├── scalers.pkl                 ✅ Test scalers
│   └── scalers_hybrid.pkl          ✅ Test scalers
├── results/
│   ├── tables/
│   │   ├── baseline_results.csv         ✅
│   │   ├── dl_results.csv               ✅
│   │   ├── hybrid_results.csv           ✅
│   │   ├── all_model_results.csv        ✅
│   │   ├── ablation_study.csv           ✅
│   │   ├── full_comparison_table.csv    ✅
│   │   ├── paper_comparison.csv         ✅
│   │   ├── condition_analysis.csv       ✅
│   │   ├── statistical_tests.csv        ✅
│   │   └── data_summary.csv             ✅
│   └── figures/
│       ├── baseline_comparison.png      ✅
│       ├── dl_comparison.png            ✅
│       ├── hybrid_analysis.png          ✅
│       ├── comprehensive_evaluation.png ✅
│       └── weather_time_impact.png      ✅
├── data/bus-eshot-gtfs/            ✅ Mevcut (2.24M kayıt)
├── izmir_hybrid_lstm.py            ← Kullanılmıyor (notebook'lar yerine geçti)
├── web_dashboard.py                ← Aşama 7'de entegre edilecek
└── EXECUTION_PLAN.md               ✅ Bu dosya
```
