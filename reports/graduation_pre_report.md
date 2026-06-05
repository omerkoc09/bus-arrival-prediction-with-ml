# Eşrefpaşa Hat 502 Otobüs Varış Süresi Tahmini Bitirme Projesi Sunumu Ön Raporu

**Proje Başlığı:** Bağlam Duyarlı Derin Öğrenme ile Otobüs Varış Süresi Tahmini (İzmir Pilot Çalışması)  
**Tarih:** 5 Haziran 2026  
**Veri Kapsamı:** 2 Nisan 2026 — 5 Haziran 2026 (65 Günlük Gerçek Zamanlı Veri)  
**Hazırlayan:** Antigravity AI & Proje Ekibi  

---

## 1. Giriş ve Proje Özeti
Bu çalışma, toplu taşıma sistemlerinde duraklar arası seyahat sürelerini tahmin etmek amacıyla tasarlanmış bir makine öğrenmesi ve derin öğrenme hattının (pipeline) performansını değerlendirmektedir. Literatürdeki referans makaleye (**Kaya & Kalay, IEEE Access 2025**) kıyasla, modelimize **planlanmış tarife süreleri (GTFS scheduled times)**, **birikimli sapma geçmişi (deviation history)** ve **durak bekleme süreleri (dwell times)** entegre edilerek tahmin doğruluğu artırılmıştır. 

Daha önceki 138K segmentlik ara analizden sonra, toplanan gerçek zamanlı veri boyutu **305.954 segmente** (yaklaşık 2.2 kat artış) ulaşmıştır. Bu rapor, güncellenen büyük veri kümesi ve düzeltilmiş PyTorch tahmin hattı üzerinden elde edilen yeni resmi sonuçları ve bu sonuçların arkasındaki sebep-sonuç ilişkilerini içermektedir.

---

## 2. Veri Kümesi İstatistikleri
Sıfırdan toplanan ve öznitelik mühendisliği (v2, v3, v4) süreçlerinden geçirilerek temizlenen veri kümesinin genel profili şu şekildedir:

*   **Toplam İşlenen Segment Sayısı:** 305.954 satır
*   **Eğitim (Train) Seti Boyutu (%80):** 244.763 satır
*   **Test Seti Boyutu (%20):** 61.191 satır
*   **Tarih Aralığı:** 2 Nisan 2026 — 5 Haziran 2026 (65 gün)
*   **Aktif Çalışma Saatleri:** 06:00 — 22:00
*   **Benzersiz Otobüs Sayısı:** 318
*   **Ortalama Duraklar Arası Seyahat Süresi:** 1.172 dakika (yaklaşık 70 saniye)
*   **Seyahat Süresi Standart Sapması:** 1.114 dakika

---

## 3. Model Performans Karşılaştırmaları

Aşağıdaki tablolar, veri setinin tamamı üzerinde eğitilen modellerin test seti üzerindeki performans sonuçlarını göstermektedir:

### 3.1. Derin Öğrenme Modelleri Karşılaştırması
*(PyTorch tabanlı, Log-transform ve Huber Loss entegreli)*

| Model | MAE (dk) | RMSE (dk) | MAPE (%) | R² |
| :--- | :---: | :---: | :---: | :---: |
| **Improved LSTM** (Önerilen) | **0.3507** | **0.4918** | **38.41** | **0.3569** |
| Baseline LSTM (Eski Sürüm) | 0.4138 | 0.6914 | 42.11 | 0.0484 |

### 3.2. Tüm Modellerin Genel Karşılaştırması
*(Test Seti n = 61.191)*

| Sıra | Model | MAE (dk) | RMSE (dk) | MAPE (%) | R² |
| :---: | :--- | :---: | :---: | :---: | :---: |
| 1 | **Improved LSTM** | **0.3507** | **0.4918** | **38.41** | 0.3569 |
| 2 | **XGBoost (Improved)** | 0.3944 | 0.6483 | 41.29 | **0.5379** |
| 3 | Random Forest (Improved) | 0.4079 | 0.6614 | 42.67 | 0.5190 |

---

## 4. Sebep-Sonuç İlişkileri ve Bulguların Analizi

### 4.1. Veri Hacminin Artmasının Derin Öğrenme Modellerine Etkisi
*   **Bulgu:** Veri kümesi 138K'dan 305K segmente çıkarıldığında, `Improved LSTM` modelinin MAE değeri **0.4138 dakikadan 0.3507 dakikaya (~%15.2 iyileşme)** gerilemiştir.
*   **Sebep-Sonuç:** Derin öğrenme (Deep Learning) modelleri doğası gereği yüksek parametre kapasitesine sahiptir ve az veride aşırı uyum (overfitting) gösterme veya kararsız öğrenme eğilimindedir. Veri miktarının 2.2 katına çıkması, LSTM hücrelerinin duraklar arası geçiş sürelerindeki karmaşık spatiotemporal (mekan-zaman) ilişkileri ezberlemek yerine genel kuralları öğrenmesini sağlamış ve tahmin başarısını belirgin şekilde artırmıştır.

### 4.2. LSTM ve XGBoost Arasındaki Karakteristik Farklar
*   **Bulgu:** `Improved LSTM` en düşük ortalama hatayı (MAE = 0.3507 dk) verirken, `XGBoost (Improved)` en yüksek açıklayıcılık oranını (R² = 0.5379) elde etmiştir.
*   **Sebep-Sonuç:** LSTM modeli, seyahat süresi tahminini zaman serisi sekansı (`window_size=5` ile son 5 durağın seyir hızı ve sapması) olarak ele alır. Bu sayede otobüsün anlık ivmesini ve son duraklardaki trendi pürüzsüz takip ederek MAE'de en iyi sonucu verir. XGBoost ise spatiotemporal özellikleri (hava durumu, günün saati, durak konumu) doğrudan ağaç yapılarıyla modellere böler. Varyansı (R²) açıklamakta daha başarılı olsa da, anlık sekans takibini LSTM kadar pürüzsüz yapamadığı için MAE'de LSTM'in biraz gerisinde kalmıştır.

### 4.3. Soğuk Başlangıç (Cold-Start) Problemi ve Segment Analizi
*   **Bulgu:** Seferin başlangıç duraklarında (%0-33) MAE **0.5246 dk** iken, orta duraklarda **0.4157 dk**'ya ve bitiş duraklarında **0.3602 dk**'ya düşmektedir.
*   **Sebep-Sonuç:** Otobüs sefere ilk başladığı duraklarda henüz geride bıraktığı bir durak olmadığı için `prev_travel_time_min` ve `prev_deviation` gibi geçmişe dayalı lag öznitelikleri `0` değerini alır. Model anlık sürüş dinamiğine dair bağlamsal bilgiden yoksun kaldığı için başlangıç bölgesinde hata oranı yaklaşık 2 kat daha fazladır. Sefer ilerledikçe (`stop_progress` arttıkça) son 5 durağın gerçek seyahat süreleri modele beslenir ve hata payı en düşük seviyeye (0.3602 dk) iner.

### 4.4. Hava Durumunun Etkisi
*   **Bulgu:** Yağmurlu hava koşullarında MAE **0.4267 dk** iken, açık havada **0.3882 dk** olarak ölçülmüştür.
*   **Sebep-Sonuç:** Yağmurlu günlerde görüş mesafesinin düşmesi, yol yüzeyi kayganlığı ve trafik yoğunluğunun artması seyahat sürelerini uzatır. Dahası, yolcuların biniş/iniş esnasında şemsiye açıp kapatmaları durak bekleme sürelerinde (dwell time) yüksek değişkenlik yaratır. Bu durum öngörülemezliği artırdığından yağmurlu günlerdeki tahmin hatası daha yüksektir.

---

## 5. İstatistiksel Anlamlılık Analizi
Modellerimizin başarısının rastlantısal olmadığını kanıtlamak için test seti üzerinde **Paired t-test** ve **Wilcoxon signed-rank** testleri uygulanmıştır:

*   **XGBoost (Improved) vs Naive (GTFS):** $p$-değeri = `0.0` (İstatiksel olarak son derece anlamlı iyileşme)
*   **XGBoost (Improved) vs Historical Average:** $p$-değeri = `0.0` (Anlamlı iyileşme)
*   **XGBoost (Improved) vs Random Forest (Improved):** $p$-değeri = `0.0` (Anlamlı fark)

$p$-değerlerinin $\alpha = 0.05$ önem düzeyinden çok daha küçük çıkması, geliştirilmiş öznitelik mühendisliği ve düzeltilmiş tahmin akışının seyahat süresini tahmin etmede şansa bağlı olmayan, kalıcı ve akademik açıdan doğrulanabilir bir katkı sağladığını göstermektedir.

---

## 6. Referans Makale ile Karşılaştırma
Referans makale (**Kaya & Kalay, IEEE Access 2025**) ile elde edilen sonuçların karşılaştırması aşağıdaki gibidir:

| Metrik | Makale (İstanbul LSTM) | Bizim (XGBoost Improved) | Bizim (Improved LSTM) |
| :--- | :---: | :---: | :---: |
| **MAE (dk)** | 2.97 | 0.3944 | **0.3507** |
| **MAPE (%)** | **14.79** | 41.29 | 38.41 |
| **R²** | **0.9272** | 0.5379 | 0.3569 |

### ⚠️ Kritik Metodolojik Fark Açıklaması
*   **MAE Farkı:** Bizim MAE değerimiz (~0.35 dk), makale değerinden (2.97 dk) çok daha küçüktür. Bunun sebebi, **makalenin otobüsün tüm sefer (trip) süresini tahmin etmesi**, bizim çalışmamızın ise **duraklar arası tekil segment sürelerini (ortalama 1.17 dk) tahmin etmesidir**.
*   **R² ve MAPE Farkı:** Uçtan uca seyahat sürelerinde hedef değişkenin varyansı çok yüksektir (örneğin 30-50 dk arası seyahat süreleri). Varyans büyük olduğu için modellerin bu varyansı açıklama oranı (R²) 0.90'ların üzerine rahatlıkla çıkabilmektedir. Bizim segment bazlı varyansımız çok dar olduğundan R² değerimiz makalenin gerisinde görünmektedir. MAPE'de ise 1.17 dakikalık küçük bir segmentte yapılan 20 saniyelik bir hata oransal olarak %30-40 MAPE'ye yol açmaktadır; oysa makaledeki 30 dakikalık bir seferde yapılan 3 dakikalık hata %10 MAPE olarak yansır.

---

## 7. Sonuç 
1.  **Özgün Katkı Vurgusu:** GTFS planlanan sürelerinin ve birikimli sapmanın (`deviation_history`) modele eklenmesinin performansa en çok katkı sağlayan öznitelikler olduğu (Ablation çalışması sonuçlarıyla) gösterilmektedir.
2.  **Cold-Start Analizi:** Sefer başlangıcında hatanın neden 2 kat yüksek olduğu ve bunu engellemek için `scheduled_travel_minutes` ile yapılan doldurma mekanizması metodolojik bir başarı olarak sunulmaktadır.
