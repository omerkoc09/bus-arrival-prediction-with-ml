# Active Context

**Son Guncelleme:** 2026-06-13

---

## Aktif Calisma Alanlari

### 0. Iyilestirme Programi ✅ TAMAMLANDI (2026-06-13 — 6 adim, 6 commit)
A/B-gudumlu 6 adimli program (detay: progress.md §Iyilestirme Programi). Ozet:
- **Kod kalitesi:** hardcoded durak blogu silindi (GTFS tek kaynak); ML feature 29→16
  + tekrar kolon temizligi; LSTM reproducible (`--seed`); `--target/--coldstart/--window`
  CLI knob'lari (deney altyapisi + A/B kaniti). Feature eng. artik build_features_route.py
  (eski add_dwell_features.py vb. silinmisti).
- **3 negatif/notr A/B (metodolojik deger):** deviation reframing, GPS interpolasyon,
  HP tuning — hicbiri MAE'yi iyilestirmedi → *"MAE ~21s polling kuantalama tabaninda"* +
  *"daha sofistike != daha iyi"* temalari ampirik kanitlandi (final raporda guclu anlati).
- **Kucuk gercek kazanclar:** feature selection, cold-start none+is_trip_start, window=7 (R2 +0.02).
- **Adil model siralamasi (ayni test seti, route 502, 81.575 segment): XGBoost ≈ LSTM > RF.**
  XGBoost 0.4327 ≈ LSTM 0.4345 (hibrit) ≈ RF 0.4378; XGBoost vs LSTM p=0.38 (fark yok),
  XGBoost vs RF p=0.0055 & LSTM vs RF p=0.0014 (ikisi de RF'den anlamli iyi). **XGBoost en pratik
  tek model** (en dusuk MAE + fallback yok); **LSTM en iyi R2/RMSE** (0.636/0.891). LSTM standalone
  0.3532 ama farkli/kolay test seti → "LSTM acik ara en iyi" onceki iddia artefaktti.

### 1. Final Teslim Paketleme (KRITIK - DEVAM EDIYOR)
- **Durum:** Teknik pipeline tamam, modeller yeniden calistirildi ve leakage duzeltmesi sonrasi gecerli sonuclar uretildi.
- **Odak:** Sonuclarin rapor, sunum ve varsa demo artefaktlarina donusturulmesi.
- **Aksiyon:** Final rapor bolumlerini tamamla, metrikleri tek terminolojiyle senkronize et, sunum notlarini kapat.

### 2. Sunum Hazirligi (AKTIF)
- `omer_faruk_koc.pdf` incelendi; 6. ve 7. slaytlar icin konusma akisi cikarildi.
- Ana mesajlar (DURUST cerceve): XGBoost ≈ LSTM > RF (XGBoost en pratik, LSTM en iyi R2),
  "daha sofistike != daha iyi" + kuantalama tabani bulgulari, 3-hat genelleme, veri kapsami sinirlari.
- Kalan is: bu notlari nihai sunum dosyasina/konusmaci notlarina tasimak.

### 3. Demo Sistemi (ORTA ONCELIK)
- Eski `web_dashboard.py` 2026-06-05 refaktorunde silindi (modele hic baglanmamisti). Demo sifirdan kurulmali.
- Teslimde canli gosterim bekleniyorsa entegrasyon zaman riski tasiyor.

### 4. Veri Toplama ve Modelleme ✅ TAMAMLANDI
- Collector 27 gun calisti; 138.282 segmentlik veriyle pipeline yeniden uretildi.
- LSTM/GRU ve klasik modellerin sonuclari gecerlesti; leakage duzeltmesi kayda girdi.

---

## Bloklayicilar

| # | Bloklayici | Etki | Cozum |
|---|-----------|------|-------|
| 1 | **Yagisli/kis kosullari verisi yok** | Hava durumu feature etkisi guclu sekilde savunulamiyor | Yagisli donemde veri topla veya bunu acik sinirlilik olarak raporla |
| 2 | **Demo sistemi yok** | Canli gosterim/planned deployment zayif kaliyor | Demo'yu sifirdan kur, `models/improved_lstm*.pt` ile entegre et (eski web_dashboard.py silindi) |
| 3 | **Sunum ve final rapor tam kapanmadi** | Teknik calisma teslim artefaktina donusmeyebilir | Sunum metni, rapor bolumleri ve sekil/tablo referanslarini tamamla |
| 4 | ✅ **LSTM vs RF anlamlilik testi (COZULDU 2026-06-13)** | Adil test: XGBoost ≈ LSTM > RF (XGB vs LSTM p=0.38; ikisi de RF'den anlamli iyi). XGBoost en pratik. "LSTM en iyi" artefaktti | evaluation.ipynb → lstm_vs_ml_significance.csv |

---

## Yakin Vadeli Oncelikler (Sirali)

1. **Final rapor yazimi** — Sonuclar, sinirliliklar ve ozgun katkilari tek bir dille kapat
2. **Sunum sonlandirma** — Slayt anlatim akisi, konusmaci notlari ve sure yonetimini tamamla
3. ~~LSTM vs RF istatistiksel testi~~ ✅ TAMAMLANDI (2026-06-13) — adil test: modeller esdeger, XGBoost en pratik tek model
4. **Demo sistemi** — Zaman kalirsa demo'yu sifirdan kurup `models/improved_lstm*.pt` ile bagla

---

## Acik Sorular

- Collector suresi: 1 hafta yeterli mi yoksa 2-4 hafta mi beklenecek?
- Hava durumu: Gercek API key alinacak mi yoksa mock ile devam mi?
- Demo zorunlu mu yoksa opsiyonel mi (juri beklentisi)?
- Baska rotalar (599, 585, 268, 171) eklenecek mi yoksa sadece 502 mi kalacak?

---

## 2026-04-29 Durum Degerlendirmesi

> ⚠️ **TARIHSEL — kismen gecersiz.** Bu blok 2026-04-29 tarihlidir. Asagidaki
> "LSTM en iyi model" gozlemi (Kritik Gozlemler #1) 2026-06-13 adil anlamlilik
> testiyle CURUTULDU: modeller esdeger, XGBoost en pratik (bkz. Bolum 0 + progress.md).

### Genel Sonuc
- Proje su anda "teknik calisma tamam, teslim artefaktlari kapatiliyor" asamasinda.
- 27 gunluk veri ve leakage duzeltmesi sonrasi sonuclar savunulabilir; ana risk artik veri eksikligi degil, sonuclarin iyi paketlenmesi.
- Sunum, rapor ve varsa demo entegrasyonu son kilometre isleri olarak one cikti.

### Kritik Gozlemler
1. LSTM en iyi model olarak ayrisiyor; bu mesaj sunumun merkezinde olmali.
2. Cold-start ve sabah pik saati bulgulari metodolojik katkilar olarak vurgulanmali.
3. Yagisli/kis verisinin eksikligi acik sinirlilik olarak korunmali; fazla genelleme yapilmamali.
4. Demo ve final rapor tamamlanmadigi surece teknik ilerleme teslim avantajina tam donusmez.

### Dokumantasyon Tutarliligi Riski
- Raporlarin bir kismi Mart sonu, bir kismi Nisan basi tarihli; durum ozetleri yeniden senkronize edilmeli.
- Bazi raporlarda eski notebook veya veritabani isimleri geciyor; final teslim oncesi tek bir kanonik isimlendirme seti belirlenmeli.

### Bu Asamadaki Dogru Odak
1. Final rapor metnini ve gorsel referanslarini tamamlamak.
2. Sunum notasini netlestirmek; her slaytin tek ana mesaji olmasini saglamak.
3. Gerekirse LSTM vs RF anlamlilik testini ekleyip en iyi model sonucunu daha guclu savunmak.
4. Zaman kalirsa demo entegrasyonunu tamamlamak.
