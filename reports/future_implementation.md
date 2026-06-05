# Yapılacaklar Listesi

**Son Güncelleme:** 2026-04-29
**Bağlam:** 138K segment ile leakage düzeltmesi sonrası geçerli sonuçlar üretildi. Bundan sonraki adımlar bu dosyada izleniyor.

---

## Yüksek Öncelik

### 1. Final Akademik Makale Taslağı
**Neden:** Proje teknik bakımdan tamamlandı; teslim için yazılı çıktı eksik.

**Kapsam:**
- **En iyi model olarak LSTM** raporlanmalı (MAE 0.4138 dk, RMSE 0.6914 dk, R² 0.05).
- **Özgün katkı somut delili:** `scheduled_travel_minutes` ablation'da en kritik feature olduğu (+0.0142 MAE çıkarınca) gösterilmeli. Bu, GTFS-tabanlı yaklaşımımızın kanıtı.
- **Cold-start bulgusu:** Hat başlangıcında MAE 2× kötü (0.83 vs 0.41) — metodolojik alt başlık olarak ele alınmalı.
- **Negatif bulgu olarak Enhanced XGBoost:** "Daha çok feature = daha iyi" hipotezinin reddedildiği dürüstçe raporlanmalı (Enhanced 0.51 vs vanilla 0.48).
- **Hava durumu feature'larının zayıflığı:** Yağışsız 27 günlük veride bu feature'lar gürültü ekliyor (ablation kanıtı). "İleri çalışma" olarak konumlandırılmalı.
- **Makale ile karşılaştırma metodolojik şartla:** %86 MAE avantajı segment vs trip ölçek farkından kaynaklanıyor olabilir; açıkça belgelenmeli.

**Çıktı:** `reports/paper_draft.md` veya LaTeX dosyası.

---

### 2. Demo Dashboard
**Neden:** Teslim kriterlerinde "çalışan demo uygulaması" var. (Eski `web_dashboard.py` 2026-06-05 refaktöründe silindi — güncel modele hiç bağlanmamıştı; demo sıfırdan, `improved_lstm.py` ürettiği `models/improved_lstm*.pt` üzerine kurulmalı.)

**Kapsam:**
- LSTM modeline (`models/lstm_model.pt`) bağlanmalı.
- API endpoint: `GET /predict?stop_id=X&hour=Y&day_type=Z` gibi.
- Route 502 harita görünümü + anlık otobüs konumları.
- Son 24 saat performans metrikleri.

**Bağımlılık:** LSTM scaler ve config (`models/scalers.pkl`) gerekli.

---

### 3. DL Modellerini İstatistiksel Testlere Dahil Et
**Neden:** Şu an [notebooks/evaluation.ipynb](notebooks/evaluation.ipynb)'in `predictions` dict'i LSTM/GRU içermiyor. Sonuç: en iyi model olduğu halde LSTM vs RF karşılaştırması yapılamıyor; istatistiksel anlamlılık kanıtlanamıyor.

**Yapılacak:**
- `evaluation.ipynb`'e sequence input hazırlama bloğu eklenmeli (deep_learning.ipynb'deki `create_sequences` mantığı).
- LSTM ve GRU `predictions` dict'ine eklenmeli.
- En iyi model otomatik LSTM seçilecek; istatistiksel testler LSTM referanslı yeniden üretilecek.
- `paper_comparison.csv` LSTM ile güncellenmeli (RF değil).

---

## Orta Öncelik

### 4. Yağışlı/Karlı Hava Verisi Toplama
**Neden:** 27 günlük veride sadece `clear` ve `cloudy` gözlemlendi. `weather_category` etkisi kanıtlanamıyor; ablation'da bu feature'lar MAE'yi kötüleştiriyor.

**Yapılacak:**
- Veri toplama kış mevsimine uzatılsın (en az Aralık-Şubat).
- Yağışlı/karlı günler için ayrı analiz raporlansın.
- Hâlâ kanıt yetersizse, makalede `weather_category` "ileri çalışma" olarak konumlandırılsın.

---

### 5. Cold-Start Çözümü Denemesi
**Neden:** Hat başlangıcında MAE 2× kötü. Olası sebep: trip başında lag feature'lar (`prev_travel_time_min`, `prev_deviation`) 0.

**Denenecek yaklaşımlar:**
- Lag feature'ları `0` yerine **(yön, from_stop_seq) grup ortalaması** ile fillna et.
- Trip-başlangıç-flag feature ekle (`is_trip_start`).
- İlk 3 segmentte ayrı bir model (örn. Historical Avg fallback) kullan.

**Beklenti:** Başlangıç MAE 0.83 → 0.50 civarına inebilir.

---

### 6. LSTM Hyperparameter Tuning
**Neden:** Şu an `window_size=3`, `dropout=0.2`, `epochs=30` sabit ayarlarla çalışıyor. Sweep yapılmadı.

**Denenecek aralıklar:**
- `window_size`: 2, 3, 5, 7
- `dropout`: 0.1, 0.2, 0.3, 0.4
- `rnn_units`: 64, 128, 256
- `learning_rate`: 0.0001, 0.0005, 0.001, 0.003

**Yöntem:** Grid search veya Optuna. Validation set kronolojik split'in son %10'u olabilir.

**Beklenti:** MAE 0.41 → 0.35-0.38 aralığına inebilir.

---

## Düşük Öncelik

### 7. SHAP Feature Importance
**Neden:** Final Enhanced XGBoost (16 feature, leakage'sız) için kanıt göstergesi.

**Yapılacak:**
```bash
pip install shap
```
Sonra [notebooks/hybrid_model.ipynb](notebooks/hybrid_model.ipynb)'in §7 hücresi otomatik çalışır. Çıktı: `results/figures/shap_summary.png`.

---

### 8. SHAP Beeswarm + Force Plot
**Neden:** Akademik yayında feature etkileşimlerini görselleştirir. SHAP kuruluysa marjinal ek iş.

**Çıktı:** `results/figures/shap_beeswarm.png`, `results/figures/shap_force_top5.png`.

---

### 9. Sunum Slaytları
**Neden:** GTU sunumu için. Şu anda yok.

**Kapsam:**
- Problem tanımı (1-2 slayt)
- Veri ve metodoloji (3-4 slayt)
- Sonuçlar (3-4 slayt: model karşılaştırması, ablation, koşul bazlı analiz, cold-start)
- Özgün katkı (1 slayt: GTFS + ablation kanıtı)
- Demo (1 slayt: ekran görüntüsü)

**Çıktı:** `presentations/final_defense.pptx`.

---

## Bilinen Sınırlılıklar (Yayınlanırken Belgelenecek)

1. **Tek hat (Route 502)** — Genelleme için diğer hatlara uygulanması "ileri çalışma".
2. **27 günlük veri** — Mevsimsel etkiler (yaz/kış, okul açık/kapalı) gözlemlenmedi.
3. **Yağışsız 27 gün** — Hava durumu feature'larının kapsamlı testi yapılamadı.
4. **Saat aralığı 06:00–22:00** — Gece hizmetlerinin (varsa) modellenmemiş.
5. **Segment-bazlı tahmin** — Uçtan-uca trip tahmini doğrudan yapılmıyor; segment toplamı hata kümülatif olabilir.
6. **Tek şehir (İzmir)** — İstanbul makalesi ile doğrudan karşılaştırma sınırlı.

---

## Referanslar

- [reports/results_analysis.md](results_analysis.md) — Detaylı sonuç analizi
- [reports/progress.md](progress.md) — Genel ilerleme durumu
- [reports/feature_engineering_plan.md](feature_engineering_plan.md) — Feature seti gerekçeleri
- Kaya & Kalay, IEEE Access 2025 — Karşılaştırma referansı
