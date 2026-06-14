# Progress

**Son Guncelleme:** 2026-06-13

---

## 🔧 2026-06-13 — Iyilestirme Programi (6 adim)

Kod kalitesi + model dogrulugu icin adim adim, her adim ayri commit:

1. **[x] config.py temizligi (TAMAMLANDI)** — Hardcoded `STOPS_DIR0/DIR1` ve kullanilmayan
   `ALL_STOP_IDS` kaldirildi; durak listeleri artik tamamen GTFS kaynakli (tek dogruluk
   kaynagi). GTFS yuklenemezse acik `RuntimeError`. `collector.py`, `trip_extractor.py`,
   `build_features_route.py` ROUTES'a tasindi. Dogrulama: GTFS'ten 502 dir0=32/dir1=28
   (eski hardcoded ile birebir ayni) → veri kaybi yok.
2. **[x] Feature selection + dedup (TAMAMLANDI)** — ML feature seti 29→16 (%45 azalma):
   fazlalik zaman kodlamasi (sin/cos, time_block, day_type) + 7 hava/trafik feature'i
   cikarildi. LSTM context 15→11 (4 hava feature). Tekrar kolon `cumulative_deviation`
   build_features_route.py'den kaldirildi. **A/B sonuc:** ML MAE her modelde iyilesti
   (XGBoost 0.4388→0.4327, RF Improved 0.4591→0.4395, RF MoE 0.4402→0.4373);
   LSTM MAE sabit (0.3601→0.3600), MAPE 39.66→39.21. Daha az feature, daha iyi/esit
   MAE → "daha karmasik degil, daha temiz" kaniti.
3. **[~] Etiket hassasiyeti — ARASTIRILDI, A/B kapisinda GERI ALINDI (limitation)**
   GPS along-track interpolasyon prototiplendi (durak konumunu koprule yen iki ping'ten
   gecis anini lineer interpolasyon). **Bulgu:** interpolasyon mumkun oldugunda etiketi
   gercekten temizliyor (within-group std 0.91 -> 0.70), AMA **kapsama yalnizca ~%8**
   (480/6316 segment, 3 gun ornek). Sebep fundamental: halka acik API'nin **30s polling'i**
   sehir ici otobus hizinda (~165m/poll) cogu durak icin tek ping birakiyor; yogun-pingli
   gecisler azinlik. %8 kapsama model MAE'sini anlamli iyilestiremez + dense-ping secimi
   yavas/tikanik bolgelere onyargili (confound). Karar: pipeline'a entegre edilmedi,
   prototip silindi. **Bu, ~20s MAE'nin polling kuantalama tabaninda oldugunun AMPIRIK
   kanitidir** → final rapor "Limitations": *daha ince etiket, public API'den daha yogun
   GPS gerektirir (GTFS-RT yok).*
4. **[~] Hedefi sapmaya cevirme — A/B yapildi, KAZANMADI (travel kaldi)**
   `--target {travel,deviation}` eklendi (improved_ml.py + improved_lstm.py). A/B (route 502):
   | Model | travel (mevcut) | deviation |
   |---|---|---|
   | XGBoost | MAE 0.4327 / R2 0.629 | 0.4821 / 0.515 |
   | RF Improved | 0.4395 / 0.631 | 0.4868 / 0.522 |
   | LSTM | 0.3573 / 0.349 | 0.3595 / 0.350 |
   Agac modellerinde deviation **belirgin kotu** (MAE +%11), LSTM'de notr. **Sebep:**
   (1) `scheduled_travel_min` ZATEN input feature → baz cizgi modelde mevcut, hedeften
   cikarmak bilgi katmiyor; (2) travel'in log1p donusumu sag-carpik dagilimi stabilize
   ediyor, deviation'in lineer olcegi bunu kaybediyor. `--target` knob'u kodda kaldi
   (default=travel). Metodolojik tema (Adim 2 ile ayni): **"daha sofistike != daha iyi."**
5. **[x] Cold-start tam cozumu (TAMAMLANDI)** — 5 konfigurasyon A/B'si (improved_ml.py
   `--coldstart {scheduled,none,hist}` + `--tripstart-feat`):
   | Config | XGB MAE | R2 | cold-start MAE (ilk%33) |
   |---|---|---|---|
   | scheduled (eski) | 0.4327 | 0.629 | 0.5404 |
   | none+is_trip_start (**yeni default**) | **0.4304** | **0.636** | **0.5359** |
   **Bulgular:** (1) Hipotez CURUDU — scheduled-fill zarar vermiyor (none ile ~ayni);
   0.39↔0.43 farki cold-start'tan degil. (2) `is_trip_start` bayragi kucuk ama tutarli
   ML kazanci; sentetik doldurma yerine trip-basi sinyalini durustce gosteriyor.
   (3) **Cold-start gap ~1.5x ICSEL** — hicbir fill stratejisi kapatmiyor (raporun "2x"
   iddiasi temiz setupta 1.5x). LSTM'de strateji gurultu icinde (0.3590 vs 0.3565);
   tutarlilik icin none+is_trip_start uniform uygulandi. is_trip_start LSTM context'e (12).
6. **[x] Reproducibility + LSTM hiperparametre sweep (TAMAMLANDI)** —
   `--seed` (torch+numpy) eklendi → LSTM artik tekrarlanabilir (onceden ±0.005 oynuyordu;
   ayni seed iki kez tam 0.3586 verdi). HP'ler CLI arg: `--window/--units/--dropout/--lr`.
   Grid (window×units) + 3-seed dogrulama:
   | Config | MAE ort. (3 seed) | R2 ort. |
   |---|---|---|
   | w5/u128 (eski default) | 0.3588 | 0.344 |
   | **w7/u128 (yeni default)** | **0.3585** | **0.3645** |
   | w7/u64 | 0.3587 | 0.366 |
   **Bulgu:** Hicbir config MAE'yi hareket ettirmedi → **Adim 3'un kuantalama tabani
   bulgusunu dogruluyor** (mimari MAE tabanini asamaz). window=7 R2'yi tutarli +0.02
   iyilestiriyor (daha fazla gecmis). w7/u128 adapte edildi (checkpoint-guvenli; units
   degismedi). checkpoint artik rnn_units/dropout da kaydediyor (self-describing).

---

## ✅ Iyilestirme Programi TAMAMLANDI (6/6) — 2026-06-13

6 adim, her biri ayri commit + A/B kapisi. Ozet:
- **Kod kalitesi:** hardcoded durak blogu silindi (GTFS tek kaynak); 29→16 feature; tekrar
  kolon temizlendi; LSTM reproducible (seed).
- **3 negatif/notr A/B bulgusu** (metodolojik deger): deviation reframing, GPS interpolasyon,
  HP tuning hicbiri MAE'yi iyilestirmedi → "kuantalama tabani" + "daha sofistike != daha iyi"
  temalarini ampirik kanitladi.
- **Kucuk gercek kazanclar:** feature selection, cold-start none+is_trip_start, window=7 (R2 +0.02).
- **Model siralamasi (adil, ayni segment test seti, route 502, 81.575 segment): XGBoost ≈ LSTM > RF.**
  XGBoost vs LSTM p=0.38 (fark yok); XGBoost vs RF p=0.0055 ve LSTM vs RF p=0.0014 (ikisi de RF'den
  anlamli iyi). **XGBoost Improved en pratik tek model** (tam sette en dusuk MAE 0.4327, fallback yok);
  **LSTM en iyi R2/RMSE** (0.636/0.891). Onceki "LSTM acik ara en iyi" iddiasi test-seti artefakti idi.

---

## ⚠️ 2026-06-05 — Multi-Route Genelleme + Veri Butunlugu Duzeltmesi

### Kritik Bulgu: Eski sonuclar 3 hat karisikti
`feature_engineering_v2.ipynb`'deki `build_segments()` route_id filtresi yapmiyordu. DB'deki
3 hat (502, 268, 565) birlikte islenip hepsine 502'nin GTFS tarifesi + durak koordinatlari
atanmisti. Eski "route_502" v2 (138.282 satir) aslinda **268: 48.7k, 565: 47.6k, 502: 41.9k**
karisimi idi; 268/565 segmentlerine yanlis scheduled/distance degerleri verilmisti.

### Duzeltme
- [x] `scripts/build_features_route.py` — hat-parametrik feature engineering (her hat kendi
      GTFS + durak verisiyle). `config.ROUTES[route_id]` kullanir.
- [x] `improved_ml.py` ve `improved_lstm.py` `--route` argumani alacak sekilde guncellendi.
- [x] `scripts/build_multi_route_comparison.py` — 3 hatti yan yana getiren ozet tablo.
- [x] Uc hat icin temiz veri uretildi: 502 (75.6k), 268 (115.8k), 565 (114.6k segment).

### Multi-Route Sonuclar (temiz veri, GENELLEME KANITI)

| Hat | Segment | Ort. sure | CV | XGBoost MAE | XGBoost R2 | LSTM MAE | LSTM R2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 502 | 75.579 | 1.21 dk | 1.28 | 0.439 | **0.637** | 0.360 | 0.337 |
| 268 | 115.803 | 1.23 dk | 0.79 | 0.379 | 0.533 | 0.323 | 0.407 |
| 565 | 114.572 | 1.09 dk | 0.80 | 0.308 | 0.479 | **0.295** | **0.531** |

**Sonuc:** Yontem 3 hatta da tutarli calisiyor → genelleme kanitlandi (makaleye girecek en
guclu argumanlardan biri). Temiz 502 verisi karisik veriye gore R2'yi 0.538 → 0.637'ye cikardi.
Improved LSTM uc hatta da en dusuk MAE'yi veriyor.

Detay: [reports/results_analysis.md](reports/results_analysis.md) §0 ve §11.

---

## Tamamlanan Isler

### Asama 0 — Veri Toplama Altyapisi ✅
- [x] Izmir Teknoloji API kesfedildi ve test edildi (anonim erisim, JSON)
- [x] `data_collector/config.py` — Route 502 durak listesi (32 gidis + 28 donus), API endpointleri
- [x] `data_collector/collector.py` — GPS polling (30sn), hava durumu (saatlik), trafik (20dk), SQLite kayit, trip event detection
- [x] OpenWeatherMap entegrasyonu (gercek + mock fallback)
- [x] TomTom Traffic Flow API entegrasyonu (31 segment, congestion_ratio, 20dk aralik)
- [x] Graceful shutdown (SIGINT/SIGTERM), loglama, test modu

### Asama 1 — Ham Veri Cikarma ✅
- [x] `data_collector/trip_extractor.py` — trip_events'ten sefer ve segment cikarma
- [x] CSV export: `route_502_segments.csv`, `route_502_trips.csv`
- [x] Kalite kontrol: travel_minutes aralik filtresi (0.33–15 dk), seq tutarliligi
- [x] Istatistik goruntuleyici (`--stats`)

### Asama 2 — Feature Engineering ✅
- [x] `notebooks/feature_engineering.ipynb`
- [x] Zamansal: hour, day_of_week, is_weekend, time_block
- [x] Mekansal: distance_m (Haversine), stop_progress (0-1)
- [x] GTFS: scheduled_travel_minutes, deviation_minutes (ozgun katki)
- [x] Hava durumu: 7 feature (temperature, humidity, precipitation, wind_speed, visibility, weather_category, is_rainy)
- [x] Cikti: `route_502_features.csv` (27 kolon)

### Asama 3 — Baseline Modeller ✅
- [x] `notebooks/baseline_models.ipynb`
- [x] Naive GTFS (planlanmis sure = tahmin)
- [x] Historical Average (saat x gun_tipi x durak)
- [x] Linear Regression
- [x] Random Forest (100 agac, max_depth=10)
- [x] XGBoost (n_estimators=200, lr=0.05)
- [x] Cikti: `results/tables/baseline_results.csv`

### Asama 4 — Deep Learning ✅
- [x] `notebooks/deep_learning.ipynb`
- [x] Cift girdili LSTM (sequence 128 unit + context Dense 32)
- [x] GRU varyanti
- [x] Sliding window (onceki N durak → sonraki durak seyahat suresi)
- [x] Cikti: model dosyalari (.keras, .pkl) + `results/tables/dl_results.csv`

### Asama 4b — Dwell Time Feature Muhendisligi ✅
- [x] `scripts/add_dwell_features.py` — `bus_positions` GPS verisinden dwell_time_sec hesaplama
- [x] `collected_data/route_502_features_v4.csv` — 138.282 satir, 40 kolon (+2 yeni feature)
- [x] `dwell_time_sec`: Otobusun duraga ≤50m mesafede kaldigi sure (10-600 sn)
- [x] `prev_dwell_time_sec`: Trip icinde bir onceki duragin dwell suresi
- [x] Ablasyon: RF baseline MAE 0.4324 → +dwell 0.4166 dk (%3.7 iyilesme, R2 0.4748→0.5286)
- [x] `dwell_time_sec` feature onem siralamasinda 3. sirada (%11.6)
- [x] `notebooks/feature_engineering_v2.ipynb` Adim 9 bolumu eklendi

### Asama 5 — Hibrit Model ✅
- [x] `notebooks/hybrid_model.ipynb`
- [x] Selective Trend mekanizmasi (az verili kombinasyonlar icin GTFS + sapma)
- [x] Enhanced XGBoost (17 feature, deviation_history, schedule_ratio, hour_sin/cos)
- [x] LSTM (sliding window temporal pattern)
- [x] Ridge Stacking meta-model
- [x] SHAP analizi kodu (shap kuruluysa calisir)
- [x] Ablation study: scheduled_travel_minutes ve deviation_history kaldirinca performans dususu kanitlandi
- [x] Cikti: `results/tables/hybrid_results.csv`, `ablation_study.csv`, `all_model_results.csv`

### Asama 6 — Kapsamli Degerlendirme ✅
- [x] `notebooks/evaluation.ipynb`
- [x] Makale karsilastirmasi (Kaya & Kalay IEEE 2025)
- [x] Kosul bazli performans (yon, zaman dilimi, hava durumu, durak pozisyonu)
- [x] Istatistiksel testler (paired t-test, Wilcoxon signed-rank)
- [x] Hata analizi (bias, residual dagilimi)
- [x] Cikti: `results/tables/full_comparison_table.csv`, `statistical_tests.csv`

### Proje Yonetimi ✅
- [x] GTFS statik veri temin edildi (`data/bus-eshot-gtfs/`)
- [x] ESHOT acik veri CSV'leri temin edildi (`data/eshot-otobus-*.csv`)
- [x] Proje dosya yapisi temizlendi ve duzenlendi
- [x] `EXECUTION_PLAN.md` ve `ROUTE_502_PILOT_PLAN.md` guncel

---

## Kalan Isler

### Asama 0b — Veri Toplama Yurutme ✅
- [x] `collector.py` 27 gun calistirildi (2026-04-02 → 2026-04-28)
- [x] 1.979.941 GPS kaydi, 138.282 segment, 46.473 trip
- [x] OpenWeatherMap entegrasyonu calisir (clear + cloudy gozlemlendi; yagis henuz yok)
- [x] TomTom entegrasyonu calisir (congestion_ratio kolonu mevcut)

### Asama 3-6 Tekrar — Yeni Veri ile ✅
- [x] Tum notebook'lar `features_v2.csv` (138K satir) ile yeniden calistirildi (2026-04-29)
- [x] LSTM/GRU calisir durumda — MAE 0.41 dk (pilot 0.89'dan iyilesme)
- [x] Random Forest / XGBoost: MAE 0.47 / 0.48 dk
- [x] Train/Test: 110.625 / 27.657 — istatistiksel testler guvenilir
- [x] **Target leakage duzeltildi:** `schedule_ratio` feature'i hybrid_model ve evaluation
      notebook'larindan cikarildi; iki notebook yeniden calistirildi
- [x] Enhanced XGBoost yeni MAE: 0.5064 dk (gecerli sonuc)
- [x] Hybrid Stacking yeni MAE: 0.5003 dk (gecerli sonuc)
- [x] Ablation, statistical_tests, paper_comparison leakage olmadan yeniden uretildi
- [x] Hedef: MAE < 2.5 dk asildi (LSTM 0.41 dk; segment vs trip olcek farki kosulluyla)

### Asama 7 — Demo Sistemi ⬜ (OPSIYONEL)
- [ ] `scripts/web_dashboard.py` hibrit modelle entegre edilecek
- [ ] API endpoint: `GET /predict?stop_id=30286&hour=8&day_type=weekday`
- [ ] Route 502 harita gorunumu + anlik otobus konumlari
- [ ] Son 24 saat performans metrikleri

### Asama 8 — Final Rapor ve Sunum ⬜
- [ ] Giris: Problem tanimi, motivasyon
- [ ] Ilgili Calismalar: Makale analizi + literatur
- [ ] Metodoloji: Veri toplama, feature engineering, model mimarisi
- [ ] Sonuclar: Tum metrikler, gorsellestirmeler
- [ ] Ozgun Katkilar: Scheduled time feature, Izmir verisi, GTFS+API hibrit yaklasim
- [ ] Sonuc ve Gelecek Calismalar
- [ ] GTU sunum sablonuyla sunum hazirlanacak
- [x] `omer_faruk_koc.pdf` incelendi; 6. ve 7. slaytlar icin ~3 dakikalik konusma metni hazirlandi (2026-04-29)

---

## Guncel Sonuclar (138.282 segment, 27 gun — iyilestirme programi sonrasi)

### Tum Modeller — ADIL karsilastirma (ayni segment test seti, 2026-06-13, reproducible)

evaluation.ipynb tum modelleri AYNI segment test setinde satir-hizali kiyaslar
(full_comparison_table.csv) — tek dogru model-karsilastirma budur. seed=42, route 502 (81.575 segment).

| Sira | Model | MAE (dk) | RMSE (dk) | MAPE (%) | R2 | Not |
|---|-------|---------:|----------:|---------:|---:|---|
| 1 | **XGBoost Improved** | **0.4327** | 0.903 | 41.1 | 0.626 | en pratik (cold-start fallback yok) |
| 2 | LSTM (hibrit) | 0.4345 | **0.891** | 40.7 | **0.636** | en iyi R2/RMSE; cold-start'ta RF fallback |
| 3 | RF Improved | 0.4378 | 0.896 | 41.6 | 0.633 | lean, log-transform |
| — | Historical Average | 0.645 | 1.317 | 62.7 | 0.206 | baseline |
| — | Naive (GTFS) | 0.734 | 1.516 | 68.2 | -0.05 | baseline |

> **NOT:** Improved LSTM *standalone* (kendi sequence test setinde, cold-start haric) MAE=0.3532
> verir — ama bu daha kolay/farkli bir test seti oldugundan ML ile DOGRUDAN karsilastirilamaz.
> Adil kiyas yukaridaki tablodur. (Onceki raporlarin 0.3449/0.3587'si bu artefakttan kaynaklaniyordu.)

### Istatistiksel anlamlilik — XGBoost ≈ LSTM > RF (Eksik 2, 2026-06-13)

Ayni test setinde paired t-test + Wilcoxon (referans = en dusuk MAE'li XGBoost):
- **XGBoost vs LSTM: p=0.38 → FARK YOK** (iki en iyi model istatistiksel olarak esdeger).
- **XGBoost vs RF: p=0.0055** ve **LSTM vs RF (temiz satirlar): p=0.0014** → ikisi de RF'den ANLAMLI iyi.

**Sonuc: XGBoost ≈ LSTM > RF.** XGBoost en pratik tek model (en dusuk MAE + cold-start fallback
gerektirmez); LSTM en iyi R2/RMSE. "LSTM acik ara en iyi" onceki iddia bir test-seti artefakti idi
(LSTM yalnizca kolay non-cold-start satirlarda olculuyordu). Cikti: `lstm_vs_ml_significance.csv`,
`statistical_tests.csv`. Bu, "daha sofistike != daha iyi" + Adim 3 kuantalama tabani temalariyla tutarli.

### Surum Tarihcesi

| Surum | Tarih | En iyi MAE | Bilimsel Gecerlilik |
|-------|-------|----------:|---------------------|
| Pilot (61 satir) | 2026-04-28 | 0.89 (LSTM) | Dusuk (n=13) |
| 138K leakage'li | 2026-04-29 sabah | 0.02 (leakage!) | Yok |
| 138K duzeltilmis | 2026-04-29 ogleden sonra | 0.41 (LSTM) | Yuksek |
| 138K + dwell + improved | 2026-06-05 | 0.3449 (LSTM, seed yok) | Yuksek ama tekrar uretilemez |
| **Iyilestirme programi** | **2026-06-13** | **0.4327 (XGB, adil) / 0.3532 (LSTM standalone)** | **Yuksek + reproducible** |

> Adil kiyas (ayni test seti): XGBoost 0.4327 ≈ LSTM 0.4345 > RF 0.4378; baseline Naive 0.734.
> XGBoost'un Naive'e gore iyilesmesi: %41 (0.734 → 0.4327). LSTM standalone (kolay set): 0.3532.
> Tum sonuclar artik seed=42 ile tekrarlanabilir (Adim 6).

---

## Teslim Kriterleri Durumu

### Minimum Teslim (Gecer Not)
- [x] Calisan veri toplama sistemi
- [x] Trip extractor calisiyor
- [x] Feature engineering pipeline
- [x] 5 baseline model calisiyor
- [x] **27 gunluk gercek veri (138.282 segment)**
- [x] **MAE < 3.5 dakika** (LSTM 0.41 dk)
- [ ] Kapsamli rapor

### Hedeflenen Teslim (Iyi Not)
- [x] LSTM/GRU modelleri calisiyor (MAE 0.41 dk)
- [x] Hibrit stacking ensemble (kod hazir; sonuclar leakage nedeniyle yeniden uretilmeli)
- [x] Ablation calismasi (kod hazir; sonuclar leakage nedeniyle yeniden uretilmeli)
- [x] Istatistiksel anlamlilik testleri (kod hazir; sonuclar leakage nedeniyle yeniden uretilmeli)
- [x] **MAE < 2.5 dk** (gecerli modellerin tumu ulasti)
- [ ] Hava durumu feature etkisi kanitlandi (yagisli gun verisi yok)

### Mukemmel Teslim (En Iyi Not)
- [x] SHAP analizi kodu hazir
- [ ] Hibrit model MAE < 2.0 dk (leakage duzeltmesi sonrasi yeniden olculecek)
- [ ] Calisan demo uygulamasi
- [ ] Akademik yayin taslagi

---

## 2026-04-29 Yonetici Ozeti (leakage duzeltmesi sonrasi)

### Mevcut Asama
- Proje teknik bakimdan **tamamlanmis ve sonuclari bilimsel olarak savunulabilir.** 138K segmentlik
  gercek veri uzerinde tum modeller calistirildi; target leakage tespit edilip duzeltildi.
- Final teslim icin kalanlar: makale yazimi, demo dashboard, sunum hazirligi.

### Teknik Durum Degerlendirmesi
1. Veri toplama operasyonu stabilize oldu — 27 gun, 1.98M GPS kaydi, 138K segment.
2. **LSTM en iyi model** (MAE 0.41 dk). DL'in yeterli veri ile bask in oldugu dogrulandi.
3. **Enhanced XGBoost beklenenden kotu** (0.51 vs vanilla XGBoost 0.48). Ek feature'lar 138K'da
   gurultu olarak davraniyor; "daha karmasik = daha iyi" reddedildi. Bu, makaleye girecek
   metodolojik bir bulgu.
4. **Hava durumu feature'lari ablation'da MAE'yi kotulestiriyor** (0.4818 → 0.5064 ekleyince).
   Yagissiz veri kanitlayici test sunmuyor.
5. **`scheduled_travel_minutes` ablation'da en kritik feature** — projenin GTFS-tabanli ozgun
   katkisinin somut delili.
6. **Hat baslangicinda MAE 2× kotu** (0.83 vs 0.41) — cold-start lag eksikliginden suphelenilen
   metodolojik bulgu, makalede ayri alt baslik hak ediyor.

### Kalan Riskler
1. Yagisli/karli hava verisi yok — `weather_category` etkisi kanitlanamiyor; makalede "ileri
   calisma" olarak raporlanmali.
2. Demo dashboard hazir degil; teslimde "calisan sistem" bekleniyorsa zaman riski.
3. Final akademik makale ve sunum hala yazilmadi.
4. evaluation notebook'undaki istatistiksel testler DL modellerini icermiyor; LSTM'in RF'den
   anlamli sekilde iyi oldugu gosterilmeli.
5. Dwell time feature'lari yalnizca RF ile test edildi; LSTM/XGBoost modellerine entegrasyon
   (features_v4.csv kullanilarak) yapilirsa ek iyilesme beklenmektedir.

### Net Karar
- Oncelik 1: **Final akademik makale taslagi.** En iyi model LSTM (MAE 0.41 dk, %86 makale
  uzerinde). Segment vs trip olcek farki acikca belgelensin.
- Oncelik 2: Demo dashboard — LSTM modeline baglanmali.
- Oncelik 3: Sunum ve teslim hazirligi.
