# SmartSearch Backend - Sistem Özeti

> **Son Güncelleme:** 3 Aralık 2025  
> **Versiyon:** 1.1.0

---

## 🎯 Proje Amacı

SmartSearch Backend, frontend UI ile FAISS tabanlı ürün retrieval sistemi arasında köprü görevi gören bir **Flask REST API**'sidir.

**Temel Görevler:**
- Text Corrector'dan yazım düzeltmesi al
- FAISS'ten sıralı ürün ID'lerini al
- Ürünleri DB'den çekip sırayı koruyarak frontend'e gönder
- Kullanıcı etkileşimlerini (click, feedback) kaydet

---

## 🏗️ Mimari Yapı

```
smartsearch-backend/
├── app.py                  # Flask uygulama factory
├── config.py               # Konfigürasyon ayarları
├── requirements.txt        # Python bağımlılıkları
│
├── models/                 # SQLAlchemy modelleri
│   ├── brand.py           # Marka modeli
│   ├── category.py        # Kategori modeli (hiyerarşik)
│   ├── product.py         # Ürün modeli
│   ├── product_image.py   # Ürün görseli modeli
│   ├── product_category.py # Many-to-many ilişki tablosu
│   ├── search_query.py    # Arama sorgusu modeli
│   └── retrieve.py        # Arama sonuçları modeli
│
├── routes/                 # API endpoint'leri
│   ├── brands.py          # /api/brands
│   ├── categories.py      # /api/categories
│   ├── products.py        # /api/products
│   ├── search.py          # /api/search
│   ├── feedback.py        # /api/feedback, /api/click, /api/metrics
│   └── health.py          # /health
│
├── services/               # İş mantığı servisleri
│   ├── product_service.py # Ürün işlemleri
│   └── search_service.py  # Arama işlemleri
│
├── uploads/                # Yüklenen dosyalar
│   └── products/          # Ürün görselleri
│
└── data/                   # Mock/test verileri
    └── mock_products.json
```

---

## 📊 Veritabanı Şeması

### Tablolar

| Tablo | Açıklama |
|-------|----------|
| `brand` | Ürün markaları |
| `category` | Kategori hiyerarşisi (self-referencing) |
| `product` | Ana ürün tablosu |
| `product_image` | Ürün görselleri (lokal dosya yolu) |
| `product_category` | Ürün-kategori ilişkisi (M:N) |
| `search_query` | Arama sorguları |
| `retrieve` | Arama sonuçları ve kullanıcı etkileşimleri |

### Entity Relationship

```
Brand (1) ──────────────── (N) Product
                                │
                                ├──── (N) ProductImage
                                │
                                └──── (M:N) Category
                                        │
                                        └── (parent-child) Category

SearchQuery (1) ────────── (N) Retrieve ──── (N:1) Product
```

---

## 🔌 API Endpoint'leri

### Ürün Yönetimi

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| `GET` | `/api/products` | Ürünleri listele (filtreleme, pagination) |
| `POST` | `/api/products` | Yeni ürün ekle |
| `GET` | `/api/products/<id>` | Ürün detayı |
| `PUT` | `/api/products/<id>` | Ürün güncelle |
| `DELETE` | `/api/products/<id>` | Ürün sil |

### Ürün Görselleri (Sadece File Upload)

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| `GET` | `/api/products/<id>/images` | Ürün görsellerini listele |
| `POST` | `/api/products/<id>/images` | Görsel yükle (form-data: `file`) |
| `DELETE` | `/api/products/<id>/images/<image_no>` | Görsel sil |
| `GET` | `/uploads/products/<filename>` | Görseli serve et |

**Görsel Yükleme Detayları:**
- **Dosya Depolama:** `uploads/products/` klasöründe
- **DB'de Saklanan:** Dosya yolu (`/uploads/products/filename.jpg`)
- **SHA256 Hash:** Otomatik hesaplanır
- **Max Boyut:** 16MB
- **İzin Verilen Formatlar:** png, jpg, jpeg, gif, webp

### Marka & Kategori

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| `GET` | `/api/brands` | Markaları listele |
| `POST` | `/api/brands` | Marka ekle |
| `GET` | `/api/categories` | Kategorileri listele |
| `POST` | `/api/categories` | Kategori ekle |

### Arama

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| `POST` | `/api/search` | Arama yap |
| `GET` | `/api/search/<id>` | Arama sonuçlarını getir |

**Arama Request:**
```json
{
  "raw_text": "kırmızı telefon",
  "pipeline_hint": "text"  // text|voice|image|multimodal
}
```

**Arama Response:**
```json
{
  "query_id": 123,
  "corrected_text": "kırmızı telefon",
  "products": [...]
}
```

### Feedback & Analytics

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| `POST` | `/api/feedback` | Beğeni/beğenmeme geri bildirimi |
| `POST` | `/api/click` | Tıklama kaydı |
| `GET` | `/api/metrics` | Metrikler |

**Feedback Request:**
```json
{
  "query_id": 123,
  "product_id": 456,
  "is_ok": true
}
```

**Metrics Response:**
```json
{
  "total_searches": 100,
  "total_clicks": 50,
  "total_feedback": 30,
  "positive_feedback": 25,
  "negative_feedback": 5,
  "click_through_rate": 0.5,
  "avg_retrieval_time_ms": 150
}
```

### Health Check

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| `GET` | `/health` | Sistem sağlık kontrolü |

---

## ⚙️ Konfigürasyon

### Ortam Değişkenleri (.env)

```env
# Flask
SECRET_KEY=your-secret-key
FLASK_DEBUG=True
FLASK_ENV=development

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=smartsearch
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password

# Optional
SQLALCHEMY_ECHO=False
DATA_DIR=data
```

### Upload Ayarları

| Ayar | Değer |
|------|-------|
| `UPLOAD_FOLDER` | `uploads/products/` |
| `MAX_CONTENT_LENGTH` | 16MB |
| `ALLOWED_EXTENSIONS` | png, jpg, jpeg, gif, webp |

---

## 🚀 Çalıştırma

### Geliştirme Ortamı

```bash
# Virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/Mac

# Bağımlılıklar
pip install -r requirements.txt

# Çalıştır
python app.py
# → http://localhost:5000
```

### Bağımlılıklar

| Paket | Versiyon | Açıklama |
|-------|----------|----------|
| Flask | 3.0.0 | Web framework |
| flask-cors | 4.0.0 | CORS desteği |
| Flask-SQLAlchemy | 3.1.1 | ORM |
| psycopg2-binary | 2.9.9 | PostgreSQL driver |
| python-dotenv | 1.0.0 | Env değişkenleri |
| requests | 2.31.0 | HTTP client (external services) |

---

## 🔄 Arama Akışı (Search Flow)

```
┌─────────────┐                           ┌─────────────────┐
│   Frontend  │  POST /api/search         │  Flask Backend  │
│     (UI)    │  {raw_text: "iphnoe"}     │   (port 5000)   │
└──────┬──────┘                           └────────┬────────┘
       │                                           │
       │                                           ▼
       │                                  ┌────────────────┐
       │                                  │ Text Corrector │
       │                                  │  (port 5001)   │
       │                                  │ smartsearch--- │
       │                                  │   correction   │
       │                                  └────────┬───────┘
       │                                           │ 
       │                         "iphone" ─────────┘
       │                                           │
       │                                           ▼
       │                                  ┌────────────────┐
       │                                  │     FAISS      │
       │                                  │  (port 5002)   │
       │                                  │ Semantic Search│
       │                                  └────────┬───────┘
       │                                           │
       │         [{product_id: 5, score: 0.95},   │
       │          {product_id: 12, score: 0.87}]  │
       │                                           │
       │                                           ▼
       │                                  ┌────────────────┐
       │                                  │   PostgreSQL   │
       │                                  │   (Database)   │
       │                                  │  Ürün detayları│
       │                                  └────────┬───────┘
       │                                           │
       │   {query_id, corrected_text,              │
       │    products: [sıralı ürünler]}            │
       └◀──────────────────────────────────────────┘
```

### Adım Adım Akış

| Adım | İşlem | Detay |
|------|-------|-------|
| 1 | Frontend → Backend | `POST /api/search` ile `raw_text` gönderir |
| 2 | Backend → Text Corrector | Yazım hatalarını düzeltir (`iphnoe` → `iphone`) |
| 3 | Backend → FAISS | `corrected_text` ile semantic search yapar |
| 4 | FAISS → Backend | Sıralı `product_id` listesi döner (en alakalı ilk sırada) |
| 5 | Backend → DB | Product ID'lerle ürün detaylarını çeker (**FAISS sırasını korur!**) |
| 6 | Backend → Frontend | `query_id`, `corrected_text`, sıralı `products` döner |

### ⚠️ Kritik: FAISS Sıralaması

FAISS'in döndüğü sıra = **relevance sıralaması**. Backend bu sırayı **mutlaka koruyor**:

```python
# FAISS'ten gelen sıra
faiss_results = [
    {"product_id": 5, "score": 0.95},   # En alakalı
    {"product_id": 12, "score": 0.87},  # 2. en alakalı
    {"product_id": 3, "score": 0.82}    # 3. en alakalı
]

# DB'den çekip sırayı koruyoruz
for pid in [5, 12, 3]:  # FAISS sırası
    products.append(db.get(pid))
```

---

## 🔌 External Services

### Text Corrector Service (smartsearch---correction projesi)

| Ayar | Değer |
|------|-------|
| URL | `TEXT_CORRECTOR_URL` (default: `http://localhost:5001/api/correct`) |
| Method | POST |
| Input | `{"query": "raw query"}` |
| Output | `{"original_query": "...", "normalized_query": "...", "changed": true, "tokens": [...]}` |

**Not:** Text Corrector ayrı bir projede çalışıyor: `smartsearch---correction`

### FAISS Service

| Ayar | Değer |
|------|-------|
| URL | `FAISS_SERVICE_URL` (default: `http://localhost:5002/api/retrieval/search`) |
| Method | POST |
| Input | `{"query": "corrected text", "pipeline": "text", "top_k": 20}` |
| Output | `{"results": [{"product_id": 1, "score": 0.95}, {"product_id": 5, "score": 0.87}...]}` |

**Kritik:** FAISS'ten dönen `results` listesi zaten **relevance sırasına göre** sıralı. Backend bu sırayı koruyarak ürünleri DB'den çekiyor.

---

## 📈 Gelecek Geliştirmeler

- [ ] Multimodal arama (görsel + metin)
- [ ] Voice search desteği
- [ ] Öneri sistemi
- [ ] Caching (Redis)
- [ ] Rate limiting

---

## 📝 Notlar

1. **Görsel sistemi tamamen file-based** - URL ile görsel ekleme yok
2. **Search akışı tamamlandı** - Text Corrector → FAISS → DB → Frontend
3. **FAISS sıralaması korunuyor** - Relevance order bozulmadan frontend'e iletiliyor
4. **Kategori hiyerarşik** - parent_category_id ile alt kategoriler
5. **Retrieve tablosu** hem sonuçları hem de kullanıcı etkileşimlerini tutuyor

---

*Bu döküman TaskSync V5 Protocol ile otomatik oluşturulmuştur.*
