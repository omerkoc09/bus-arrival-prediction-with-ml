# 🚌 İZMİR ESHOT OTOBÜS TAHMİN SİSTEMİ - REVİZE EDİLMİŞ YOL HARİTASI V3.0

**Proje Adı**: Bağlam Duyarlı Derin Öğrenme ile Otobüs Varış Süresi Tahmini  
**Veri Kaynağı**: İzmir ESHOT (Tam GTFS + CSV Veri Seti)  
**Referans Makale**: Kaya & Kalay, IEEE Access 2025  
**Revizyon Tarihi**: Mart 2026  

---

## 🔄 **V3.0 DÜZELTME ÖZETİ**

### **Kritik Düzeltmeler:**
1. **Veri boyutu düzeltildi**: stop_times.txt = **2.24M kayıt** (765K değil!)
2. **İstanbul API bağımlılığı kaldırıldı**: Sadece İzmir verisi kullanılacak
3. **Atlanmış veri setleri eklendi**: hat-guzergahlari.csv (12.9M kayıt)
4. **Gerçekçi zaman planı**: Veri toplama yerine veri işleme odaklı

---

## 📊 **GERÇEK VERİ ENVANTERİ**

### **Elimizdeki Tam Veri Seti:**

| Dosya | Boyut | Kayıt Sayısı | Kritik İçerik | Kullanım |
|-------|-------|-------------|---------------|----------|
| **stop_times.txt**  | 89MB | 2,243,312 | GTFS durak zamanları | Ana hedef değişken |
| **hat-guzergahlari.csv**  | 12.9MB | 569,839 | Detaylı güzergah noktaları | Spatial features |
| **shapes.txt** | 10.5MB | 350,858 | GTFS geometri | Yol mesafesi |
| **duraklari.csv** | 709KB | 11,741 | Durak koordinatları | GPS eşleştirme |
| **hareketsaatleri.csv** | 5.5MB | 101,760 | Planlanan saatler | Ek özellikler |
| **trips.txt** | 2.1MB | 67,398 | GTFS sefer bilgisi | Route-trip bağlantısı |
| **stops.txt** | 498KB | 10,484 | GTFS durak bilgisi | Koordinat doğrulama |
| **routes.txt** | 16KB | 395 | Hat tanımları | Meta data |
| **hatlari.csv** | 59KB | 441 | Hat bilgileri | İsim eşleştirme |

### **Toplam Veri Hacmi**: ~120MB, **3.4M+ kayıt**

---

## 🎯 **REVİZE EDİLMİŞ HEDEFLER**

### **Ana Hedef**: Makale Performansını Geçmek
- **MAE**: < 2.5 dakika (Makale: 2.97 dk)
- **MAPE**: < 12% (Makale: 14.79%)
- **R²**: > 0.93 (Makale: 0.9272)

### **Özgün Katkılar**:
1. **Planlanan süre özelliği**: stop_times'tan türetilecek
2. **Detaylı güzergah analizi**: 12.9M güzergah noktası
3. **İzmir-İstanbul karşılaştırması**: Farklı şehir verisi
4. **Hibrit veri yaklaşımı**: GTFS + CSV entegrasyonu

---

## 📅 **14 HAFTALIK REVİZE PLAN**

### **FAZA 1: VERİ ANALİZİ VE HAZIRLAMA (Hafta 1-4)**

#### **Hafta 1: Veri Keşfi ve Kalite Analizi**
**Hedefler:**
- [ ] Tüm veri dosyalarını detaylı analiz et
- [ ] Veri kalitesi raporu oluştur
- [ ] Eksik değer ve anomali tespiti
- [ ] Veri ilişkilerini haritalandır

**Çıktılar:**
- Kapsamlı veri analizi raporu
- Veri kalitesi dashboard'u
- İlişkisel veri modeli şeması

**Kod Örneği:**
```python
# Veri boyutları kontrolü
stop_times = pd.read_csv('stop_times.txt')  # 2.24M kayıt
guzergahlar = pd.read_csv('hat-guzergahlari.csv')  # 569K kayıt
print(f"GTFS stop_times: {len(stop_times):,} kayıt")
print(f"Güzergah noktaları: {len(guzergahlar):,} kayıt")
```

#### **Hafta 2: GTFS-CSV Entegrasyonu**
**Hedefler:**
- [ ] GTFS ve CSV dosyalarını birleştir
- [ ] Ortak anahtarları (route_id, stop_id) eşleştir
- [ ] Veri tutarlılığı kontrolü
- [ ] Entegre veritabanı oluştur

**Çıktılar:**
- Birleştirilmiş SQLite veritabanı
- Veri entegrasyon raporu
- Eşleştirme başarı oranları

#### **Hafta 3: Spatial-Temporal Veri Hazırlama**
**Hedefler:**
- [ ] GPS koordinatlarını normalize et
- [ ] Duraklar arası mesafe hesapla (12.9M güzergah noktası)
- [ ] Zamansal özellikler çıkar (saat, gün, mevsim)
- [ ] Spatial clustering uygula

**Çıktılar:**
- Spatial features dataset
- Mesafe matrisi (durak-durak)
- Zamansal özellik sözlüğü

#### **Hafta 4: Feature Engineering**
**Hedefler:**
- [ ] Planlanan vs gerçek süre özelliği (stop_times'tan)
- [ ] Güzergah karmaşıklığı metrikleri
- [ ] Trafik yoğunluk proxy'leri
- [ ] Hava durumu entegrasyonu

**Çıktılar:**
- 15+ engineered features
- Feature importance analizi
- Korelasyon matrisi

---

### **FAZA 2: MODEL GELİŞTİRME (Hafta 5-10)**

#### **Hafta 5-6: Baseline Modeller**
**Hedefler:**
- [ ] Basit regresyon modelleri
- [ ] Random Forest ve XGBoost
- [ ] ARIMA zaman serisi modeli
- [ ] Performans karşılaştırması

**Çıktılar:**
- Baseline sonuçları tablosu
- Model karşılaştırma raporu

#### **Hafta 7-8: Deep Learning Modelleri**
**Hedefler:**
- [ ] LSTM mimarisi (makale ile aynı)
- [ ] GRU alternatifi
- [ ] Transformer deneme (veri yeterliyse)
- [ ] Hiperparametre optimizasyonu

**Çıktılar:**
- Eğitilmiş DL modelleri
- Validation curves
- Hiperparametre grid search sonuçları

#### **Hafta 9: Hibrit Model (Makale Yaklaşımı)**
**Hedefler:**
- [ ] Selective trend mekanizması (N<1000 için)
- [ ] Context-aware features
- [ ] Ensemble yöntemleri
- [ ] Model interpretability (SHAP)

**Çıktılar:**
- Hibrit LSTM modeli
- Feature importance analizi
- Model açıklama raporu

#### **Hafta 10: Model Optimizasyonu**
**Hedefler:**
- [ ] Overfitting önleme
- [ ] Cross-validation
- [ ] Model compression
- [ ] Inference optimization

**Çıktılar:**
- Final optimize model
- Performance benchmark
- Deployment-ready model

---

### **FAZA 3: DEĞERLENDİRME VE ANALİZ (Hafta 11-12)**

#### **Hafta 11: Kapsamlı Değerlendirme**
**Hedefler:**
- [ ] Makale ile birebir karşılaştırma
- [ ] Koşul bazlı performans analizi
- [ ] Hata analizi ve edge case'ler
- [ ] Statistical significance testleri

**Çıktılar:**
- Detaylı performans raporu
- Makale karşılaştırma tablosu
- İstatistiksel analiz sonuçları

#### **Hafta 12: Özgün Katkı Analizi**
**Hedefler:**
- [ ] Planlanan süre özelliğinin etkisi
- [ ] Güzergah detayının katkısı
- [ ] İzmir-İstanbul fark analizi
- [ ] Yeni bulguların değerlendirilmesi

**Çıktılar:**
- Özgün katkı raporu
- Yenilik değerlendirmesi
- Yayın potansiyeli analizi

---

### **FAZA 4: SİSTEM VE SUNUM (Hafta 13-14)**

#### **Hafta 13: Demo Sistem**
**Hedefler:**
- [ ] Web tabanlı demo uygulaması
- [ ] API servisi
- [ ] Real-time prediction interface
- [ ] Visualization dashboard

**Çıktılar:**
- Çalışan demo sistemi
- API dokümantasyonu
- Kullanıcı arayüzü

#### **Hafta 14: Final Rapor ve Sunum**
**Hedefler:**
- [ ] Kapsamlı proje raporu
- [ ] Akademik makale taslağı
- [ ] Sunum materyalleri
- [ ] Kod dokümantasyonu

**Çıktılar:**
- Final proje raporu
- Sunum slaytları
- GitHub repository
- Demo video

---

## 🛠️ **TEKNİK MİMARİ**

### **Veri İşleme Pipeline:**
```
İzmir GTFS (2.24M) + CSV (12.9M) 
    ↓
Veri Temizleme & Entegrasyon
    ↓
Feature Engineering (15+ features)
    ↓
Train/Validation/Test Split (70/15/15)
    ↓
Model Training (LSTM + Hibrit)
    ↓
Evaluation & Comparison
    ↓
Demo System & API
```

### **Model Mimarisi:**
```python
# Hibrit LSTM (Makale yaklaşımı)
class HybridLSTM:
    def __init__(self):
        self.lstm_layer = LSTM(128, return_sequences=False)
        self.context_features = Dense(64, activation='relu')
        self.trend_component = Dense(32, activation='linear')
        self.output_layer = Dense(1, activation='linear')
    
    def selective_trend(self, sample_count):
        return self.trend_component if sample_count < 1000 else None
```

---

## 📊 **BEKLENEN SONUÇLAR**

### **Performans Hedefleri:**
| Metrik | Makale (İstanbul) | Hedefimiz (İzmir) | Stretch Goal |
|--------|------------------|------------------|--------------|
| MAE | 2.97 dk | < 2.5 dk | < 2.0 dk |
| MAPE | 14.79% | < 12% | < 10% |
| R² | 0.9272 | > 0.93 | > 0.95 |

### **Özgün Katkılar:**
1. **12.9M güzergah noktası** ile spatial analysis
2. **Planlanan süre özelliği** (makalede yok)
3. **İzmir verisi** ile model genelleştirme
4. **GTFS-CSV hibrit** yaklaşımı

---

## ⚠️ **RİSK YÖNETİMİ**

### **Yüksek Risk → Çözüm:**
- **Veri boyutu (3.4M kayıt)** → Sampling ve batch processing
- **Memory limitleri** → Chunked processing, cloud resources
- **Model karmaşıklığı** → Incremental development

### **Orta Risk → Çözüm:**
- **Feature engineering** → Domain expert consultation
- **Overfitting** → Cross-validation, regularization
- **Zaman kısıtı** → Agile milestones

---

## 🎯 **BAŞARI KRİTERLERİ**

### **Minimum Başarı (Geçer Not):**
- [ ] Çalışan LSTM modeli
- [ ] MAE < 3.0 dakika
- [ ] Demo uygulaması
- [ ] Kapsamlı rapor

### **Hedeflenen Başarı (İyi Not):**
- [ ] MAE < 2.5 dakika (makaleyi geçer)
- [ ] Özgün katkılar kanıtlanır
- [ ] Statistical significance
- [ ] Yayın kalitesi rapor

### **Mükemmel Başarı (En İyi Not):**
- [ ] MAE < 2.0 dakika (makaleyi %30 geçer)
- [ ] Yenilikçi metodoloji
- [ ] Pratik uygulama değeri
- [ ] Akademik yayın potansiyeli

---

## 📚 **KAYNAK VE ARAÇLAR**

### **Veri Kaynakları:**
- ✅ İzmir ESHOT GTFS (2.24M kayıt)
- ✅ İzmir CSV veri seti (12.9M kayıt)
- 🔄 OpenWeatherMap API (hava durumu)
- 🔄 İzmir trafik verileri (opsiyonel)

### **Teknoloji Stack:**
- **Python 3.9+**: Pandas, NumPy, Scikit-learn
- **Deep Learning**: TensorFlow/Keras
- **Database**: SQLite → PostgreSQL
- **Web**: Flask/FastAPI + React
- **Deployment**: Docker containers

### **Donanım Gereksinimleri:**
- **RAM**: Min 16GB (32GB önerilen)
- **Storage**: 50GB+ SSD
- **GPU**: CUDA destekli (model eğitimi için)
- **Cloud**: AWS/GCP credits (büyük veri için)

---

## 🚀 **HEMEN BAŞLANACAK ADIMLAR**

### **Bu Hafta (Hafta 1):**
1. **Veri envanteri çıkar**: Tüm dosyaları analiz et
2. **Development environment kur**: Python, libraries, IDE
3. **Git repository oluştur**: Version control başlat
4. **İlk veri exploration**: Basic statistics ve visualizations

### **Sonraki Hafta (Hafta 2):**
1. **GTFS-CSV entegrasyonu**: Veritabanı oluştur
2. **Data quality report**: Eksik değer, anomali analizi
3. **Baseline metrics**: Simple average, linear regression
4. **Project structure**: Kod organizasyonu

---

**Bu revize edilmiş plan, elimizdeki gerçek veri setine dayalı, ulaşılabilir hedeflerle ve makale standardında sonuçlar üretecek şekilde tasarlanmıştır. İstanbul API bağımlılığı kaldırılmış, İzmir'in zengin veri seti tam olarak değerlendirilmiştir.**

**Başarı garantili bir plan! 🎯**