# SmartSearch Backend - Yeni Güncelleme (27 Mart 2026)

## 📋 Genel Bakış

Bu dokümantasyon, 27 Mart 2026 tarihinde yapılan retrieval sistemi ve diğer önemli güncellemeleri özetlemektedir.

---

## 🎯 Yapılan Değişiklikler

### 1. Yeni Retrieval Endpoint'leri

#### `POST /api/retrieval/add-product`
**Amaç:** Sadece belirtilen model için ürün ekleme.

**Request:**
```json
{
  "id": "product_001",
  "name": "Premium Leather Handbag",
  "description": "Elegant handcrafted leather bag",
  "brand": "LuxuryBrand",
  "category": "Accessories",
  "price": 299.99,
  "images": ["C:/absolute/path/to/image1.jpg", "C:/absolute/path/to/image2.jpg"],
  "textual_model_name": "ViT-B/32",
  "visual_model_name": "ViT-B/32"
}
```

**Response (Yeni Ürün):**
```json
{
  "status": "success",
  "message": "Product product_001 added successfully",
  "details": {
    "product_id": "product_001",
    "textual_vector_id": 0,
    "visual_vector_ids": [0, 1],
    "images_processed": 2
  }
}
```

**Response (Varolan Ürün):**
```json
{
  "status": "success",
  "message": "Product product_001 already has embeddings for this model, skipping",
  "details": {
    "product_id": "product_001",
    "skipped": true
  }
}
```

#### `PUT /api/retrieval/update-product/<product_id>`
**Amaç:** Ürünü güncelleme, eski embeddingleri tüm modellerden silme ve yeniden indeksleme.

**Request:**
```json
{
  "name": "Updated Leather Handbag",
  "description": "Premium handmade leather bag with gold buckle",
  "brand": "LuxuryBrand",
  "category": "Accessories",
  "price": 349.99,
  "images": ["C:/absolute/path/to/new_image.jpg"],
  "textual_model_name": "BAAI/bge-large-en-v1.5",
  "visual_model_name": "ViT-B/32"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Product product_001 updated successfully",
  "details": {
    "product_id": "product_001",
    "removed_counts": {
      "bge-large-en-v1.5_1024_embeddings": { "textual": 1, "visual": 0, "fused": 0 },
      "ViT-B-32_512_embeddings": { "textual": 0, "visual": 2, "fused": 0 }
    },
    "textual_vector_id": 2,
    "visual_vector_ids": [3],
    "images_processed": 1
  }
}
```

#### `DELETE /api/retrieval/delete-product/<product_id>`
**Amaç:** Ürünü tüm modellerden silme.

**Response:**
```json
{
  "status": "success",
  "message": "Product product_001 deleted successfully",
  "details": {
    "product_id": "product_001",
    "removed_counts": {
      "bge-large-en-v1.5_1024_embeddings": { "textual": 1, "visual": 0, "fused": 0 },
      "ViT-B-32_512_embeddings": { "textual": 0, "visual": 2, "fused": 0 }
    },
    "total_removed": 3
  }
}
```

---

### 2. İstatistik Endpoint'leri

#### `GET /api/retrieval/index-stats`
**Amaç:** Tüm modeller için indeks istatistikleri.

**Response:**
```json
{
  "status": "success",
  "indices": {
    "bge-large-en-v1.5_1024_embeddings": {
      "textual": 100,
      "visual": 0,
      "fused": 0
    },
    "ViT-B-32_512_embeddings": {
      "textual": 0,
      "visual": 250,
      "fused": 0
    }
  }
}
```

#### `GET /api/retrieval/stats`
**Amaç:** Sistem genelindeki tüm istatistikleri alma.

**Response:**
```json
{
  "status": "success",
  "data": {
    "index_stats": {},
    "available_models": {},
    "selected_models": {
      "textual_model": "BAAI/bge-large-en-v1.5",
      "visual_model": "ViT-B/32",
      "last_updated": "2026-03-26T10:00:00Z"
    },
    "service_status": "healthy"
  }
}
```

---

### 3. Model Bilgisi Endpoint'i

#### `GET /api/retrieval/models`
**Amaç:** Kullanılabilir modelleri alma.

**Response:**
```json
{
  "status": "success",
  "data": {
    "textual_models": [
      { "name": "ViT-B/32", "dimension": 512 },
      { "name": "BAAI/bge-large-en-v1.5", "dimension": 1024 },
      { "name": "Qwen/Qwen3-Embedding-8B", "dimension": 4096 }
    ],
    "visual_models": [
      { "name": "ViT-B/32", "dimension": 512 }
    ],
    "defaults": {
      "textual": "BAAI/bge-large-en-v1.5",
      "visual": "ViT-B/32"
    }
  }
}
```

---

### 4. Database Kolonları (Retrieve Tablosu)

#### Yeni Eklenen Kolonlar

| Kolon Adı | Veri Tipi | Açıklama |
|-----------|-----------|----------|
| `textual_model_name` | VARCHAR(100) | Kullanılan metin modeli (ViT-B/32, BAAI/bge-large-en-v1.5, etc.) |
| `visual_model_name` | VARCHAR(100) | Kullanılan görsel modeli (ViT-B/32, etc.) |
| `correction_engine` | VARCHAR(50) | Kullanılan düzeltme motoru (symspell_keyboard, byt5, rawtext) |

#### Migration Komutları

```bash
# Model kolonları için
python scripts/migrate_add_model_columns_to_retrieve.py

# Correction engine için
python scripts/migrate_add_correction_engine_to_retrieve.py
```

Veya manuel SQL:
```sql
ALTER TABLE retrieve ADD COLUMN textual_model_name VARCHAR(100);
ALTER TABLE retrieve ADD COLUMN visual_model_name VARCHAR(100);
ALTER TABLE retrieve ADD COLUMN correction_engine VARCHAR(50);
```

#### Örnek Sorgular

```sql
-- Hangi text modeli ne kadar kullanılmış?
SELECT textual_model_name, COUNT(*) as search_count
FROM retrieve
GROUP BY textual_model_name;

-- Correction engine dağılımı
SELECT correction_engine, COUNT(*) as count
FROM retrieve
GROUP BY correction_engine;

-- Model + Correction kombinasyonları
SELECT
  textual_model_name,
  correction_engine,
  COUNT(*) as count
FROM retrieve
GROUP BY textual_model_name, correction_engine;
```

---

### 5. Correction Model Seçimi

#### `GET /api/correction/models`
**Amaç:** Kullanılabilir correction modellerini listeleme.

**Response:**
```json
{
  "status": "success",
  "data": {
    "engines": [
      { "name": "symspell_keyboard", "description": "Keyboard typo correction" },
      { "name": "byt5", "description": "Neural correction engine" },
      { "name": "rawtext", "description": "No correction applied" }
    ],
    "defaults": {
      "engine": "symspell_keyboard"
    }
  }
}
```

#### Correction Motorunun Kaydı

- Correction motoru her search işleminde `retrieve` tablosuna kaydedilir
- `correction_engine` kolonunda saklanır
- Bu sayede hangi correction motorunun ne kadar etkili olduğu analiz edilebilir

---

## 📁 Değiştirilen Dosyalar

### Model Dosyaları
- `models/retrieve.py` - 3 yeni kolon + to_dict() güncelleme

### Service Dosyaları
- `services/search_service.py` - Model tracking + correction engine kaydı
- `services/faiss_retrieval_service.py` - Yeni metodlar eklendi

### Route Dosyaları
- `routes/retrieval.py` - Yeni endpoint'ler eklendi
- `routes/correction.py` - Correction model listesi endpoint'i

### Migration Script'leri
- `scripts/migrate_add_model_columns_to_retrieve.py` (YENİ)
- `scripts/migrate_add_correction_engine_to_retrieve.py` (YENİ)

### Config Dosyaları
- `config/models.py` - get_selected_models(), save_selected_models()
- `config/selected_models.json` (YENİ) - Model seçimi saklama

### Dokümantasyon
- `docs/API_JSON_TEMPLATES.json` - Yeni endpoint şablonları eklendi
- `docs/CHANGELOG_2026_03_26_UPDATED.md` - Bu dosya

---

## 📊 Endpoint Özeti

| Endpoint | Metod | Açıklama |
|----------|-------|----------|
| `/api/retrieval/add-product` | POST | Yeni ürün ekleme |
| `/api/retrieval/update-product/<product_id>` | PUT | Ürün güncelleme |
| `/api/retrieval/delete-product/<product_id>` | DELETE | Ürün silme |
| `/api/retrieval/index-stats` | GET | İndeks istatistikleri |
| `/api/retrieval/stats` | GET | Sistem istatistikleri |
| `/api/retrieval/models` | GET | Kullanılabilir modeller |
| `/api/correction/models` | GET | Correction motorları |
| `/api/retrieval/selected-models` | GET/POST | Seçili modeller |

---

## 🚀 Özellikler

✅ **Model Bazlı Ekleme** - Sadece belirtilen model için embedding oluşturulur  
✅ **Tüm Modellerden Silme** - Ürün silindiğinde tüm modellerden silinir  
✅ **Güncellemede Temizlik** - Güncelleme önce eski embeddingleri siler  
✅ **İstatistik Takibi** - Her model için ayrı ayrı istatistikler  
✅ **JSON Şablonları** - Tüm endpoint'ler için örnek şablonlar  
✅ **Database İzleme** - Model ve correction motoru takibi  
✅ **Correction Seçimi** - Farklı correction motorları desteği  
✅ **Model Kaydı** - Kullanılan modellerin veritabanında izlenmesi  

---

## 📝 Notlar

- Tüm endpoint'ler RESTful kurallarına uygundur
- Hata yönetimi tüm endpoint'lerde tutarlıdır
- FAISS servisi bağımsız olarak port 5002'de çalışır
- Backend, istemciler ile FAISS servisi arasında koordinasyon sağlar
- Correction motoru ve model bilgileri retrieve tablosuna kaydedilir
- Admin panel için model seçimi artık doğrudan endpoint'lerle yapılır