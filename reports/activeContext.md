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
- **Kucuk gercek kazanclar:** feature selection (XGB 0.4388→0.4327), cold-start
  none+is_trip_start (→0.4304), window=7 (R2 +0.02).
- **Guncel reproducible (seed=42):** Improved LSTM MAE=**0.3587**/R2=0.367,
  XGBoost MAE=**0.4304**/R2=0.636. (Eski 0.3449/0.3907 tekrar uretilemedi — bkz. progress.md.)

### 1. Final Teslim Paketleme (KRITIK - DEVAM EDIYOR)
- **Durum:** Teknik pipeline tamam, modeller yeniden calistirildi ve leakage duzeltmesi sonrasi gecerli sonuclar uretildi.
- **Odak:** Sonuclarin rapor, sunum ve varsa demo artefaktlarina donusturulmesi.
- **Aksiyon:** Final rapor bolumlerini tamamla, metrikleri tek terminolojiyle senkronize et, sunum notlarini kapat.

### 2. Sunum Hazirligi (AKTIF)
- `omer_faruk_koc.pdf` incelendi; 6. ve 7. slaytlar icin konusma akisi cikarildi.
- Ana mesajlar: LSTM'in en iyi model olmasi, cold-start bulgusu, veri kapsami sinirlari ve sonraki adimlar.
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
| 4 | **LSTM vs Random Forest anlamlilik testi eksik** | En iyi model iddiasi istatistiksel acidan eksik kalabilir | Evaluation notebook'una DL karsilastirmasini ekle |

---

## Yakin Vadeli Oncelikler (Sirali)

1. **Final rapor yazimi** — Sonuclar, sinirliliklar ve ozgun katkilari tek bir dille kapat
2. **Sunum sonlandirma** — Slayt anlatim akisi, konusmaci notlari ve sure yonetimini tamamla
3. **LSTM vs RF istatistiksel testi** — En iyi model iddiasini formal olarak destekle
4. **Demo sistemi** — Zaman kalirsa demo'yu sifirdan kurup `models/improved_lstm*.pt` ile bagla

---

## Acik Sorular

- Collector suresi: 1 hafta yeterli mi yoksa 2-4 hafta mi beklenecek?
- Hava durumu: Gercek API key alinacak mi yoksa mock ile devam mi?
- Demo zorunlu mu yoksa opsiyonel mi (juri beklentisi)?
- Baska rotalar (599, 585, 268, 171) eklenecek mi yoksa sadece 502 mi kalacak?

---

## 2026-04-29 Durum Degerlendirmesi

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
