# FAISS Bulk Import ve Rebuild Workflow Dokümantasyonu

## 📋 Genel Bakış

Bu dokümantasyon, FAISS index'ini toplu olarak yönetmek için kullanılan endpoint'leri ve workflow'ları açıklar.

---

## 🎯 Kullanım Senaryoları

### Senaryo 1: FAISS Model Değişimi
Yeni embedding modellerine geçiş yapıldığında:
1. Mevcut index'i temizle
2. Test ürünü ekle ve FAISS'in hazır olmasını bekle
3. Tüm ürünleri yeni modellerle indeksle

### Senaryo 2: İlk Kurulum
Sistem ilk kez kurulduğunda tüm ürünleri FAISS'e eklemek için.

### Senaryo 3: Index Yeniden Build
FAISS index'i bozulduğunda veya optimize edilmesi gerektiğinde.

---

## 📚 Yeni Endpoint'ler

### 1. GET /api/retrieval/models

FAISS service'te kullanılabilir textual ve visual modelleri listeler.

**Request:**
```http
GET /api/retrieval/models HTTP/1.1
```

**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "textual_models": [
      {
        "id": "ViT-B/32",
        "name": "ViT-B/32 (Varsayılan - Hızlı)"
      },
      {
        "id": "ViT-B/16",
        "name": "ViT-B/16 (Daha Doğru)"
      },
      {
        "id": "BAAI/bge-large-en-v1.5",
        "name": "BAAI/bge-large-en-v1.5 (Büyük Model)"
      }
    ],
    "visual_models": [...],
    "defaults": {
      "textual": "BAAI/bge-large-en-v1.5",
      "visual": "ViT-B/32"
    }
  },
  "source": "faiss_service"
}
```

**Kaynaklar:**
- `source`: `"faiss_service"` (FAISS'ten alındı) veya `"local_config"` (fallback)

---

### 2. DELETE /api/retrieval/clear-index

FAISS index'ini tamamen temizler.

**Request:**
```http
DELETE /api/retrieval/clear-index HTTP/1.1
```

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "FAISS index cleared successfully",
  "details": {
    "deleted_count": 1500,
    "duration_ms": 234.56
  }
}
```

**Kullanım:**
```bash
curl -X DELETE http://localhost:5000/api/retrieval/clear-index
```

---

### 3. POST /api/retrieval/test-product

Test ürünü ekleyerek FAISS servisinin çalıştığını doğrular.

**Request:**
```http
POST /api/retrieval/test-product HTTP/1.1
Content-Type: application/json

{
  "product_id": "test-001"
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Test product test-001 added successfully",
  "details": {
    "product_id": "test-001",
    "textual_vector_id": 123,
    "visual_vector_ids": [124, 125]
  }
}
```

**Kullanım:**
```bash
curl -X POST http://localhost:5000/api/retrieval/test-product \
  -H "Content-Type: application/json" \
  -d '{"product_id": "test-001"}'
```

---

### 4. POST /api/bulk-faiss/add-all

Tüm ürünleri veritabanından FAISS index'ine ekler.

**Request:**
```http
POST /api/bulk-faiss/add-all HTTP/1.1
Content-Type: application/json

{
  "textual_model_name": "ViT-B/32",
  "visual_model_name": "ViT-B/32",
  "wait_after_first": true,
  "wait_duration_seconds": 60,
  "delay_between_products_ms": 0
}
```

**Parametreler:**

| Parametre | Tip | Varsayılan | Açıklama |
|-----------|-----|------------|----------|
| `textual_model_name` | string | `"BAAI/bge-large-en-v1.5"` | Text embedding modeli |
| `visual_model_name` | string | `"ViT-B/32"` | Görsel embedding modeli |
| `wait_after_first` | boolean | `true` | İlk üründen sonra FAISS init için bekle |
| `wait_duration_seconds` | integer | `60` | Bekleme süresi (saniye) |
| `delay_between_products_ms` | integer | `0` | Ürünler arası ek delay (ms) |

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Bulk import completed: 1498 products added",
  "details": {
    "total_products": 1500,
    "successful_count": 1498,
    "failed_count": 2,
    "total_time_ms": 125678.90,
    "textual_model_name": "ViT-B/32",
    "visual_model_name": "ViT-B/32",
    "wait_applied": true,
    "wait_duration_seconds": 60,
    "delay_between_products_ms": 0,
    "errors": [
      {
        "product_id": 42,
        "error": "Image not found: /path/to/missing.jpg"
      }
    ]
  }
}
```

**Kullanım:**
```bash
# Varsayılan ayarlarla (60 sn bekleme)
curl -X POST http://localhost:5000/api/bulk-faiss/add-all \
  -H "Content-Type: application/json" \
  -d '{
    "textual_model_name": "ViT-B/32",
    "visual_model_name": "ViT-B/32"
  }'

# Bekleme olmadan
curl -X POST http://localhost:5000/api/bulk-faiss/add-all \
  -H "Content-Type: application/json" \
  -d '{"wait_after_first": false}'

# Uzun bekleme (2 dakika) + ürünler arası delay
curl -X POST http://localhost:5000/api/bulk-faiss/add-all \
  -H "Content-Type: application/json" \
  -d '{
    "wait_duration_seconds": 120,
    "delay_between_products_ms": 100
  }'
```

---

### 5. POST /api/bulk-faiss/rebuild-with-test

Tam workflow: Clear → Test → Bulk Add

**Request:**
```http
POST /api/bulk-faiss/rebuild-with-test HTTP/1.1
Content-Type: application/json

{
  "textual_model_name": "ViT-L/14",
  "visual_model_name": "ViT-L/14",
  "test_product_id": "test-001",
  "wait_after_first": true,
  "wait_duration_seconds": 60,
  "delay_between_products_ms": 0
}
```

**Response (200 OK - Tüm Adımlar Başarılı):**
```json
{
  "status": "success",
  "workflow": "rebuild_with_test",
  "message": "Rebuild completed in 135234.56ms",
  "steps": [
    {
      "step": "clear_index",
      "status": "success",
      "details": {
        "deleted_count": 1500
      },
      "duration_ms": 234.56
    },
    {
      "step": "test_product",
      "status": "success",
      "details": {
        "product_id": "test-001",
        "textual_vector_id": 1
      },
      "attempts": 1,
      "duration_ms": 1234.56
    },
    {
      "step": "bulk_add",
      "status": "success",
      "details": {
        "total_products": 1500,
        "successful_count": 1500,
        "failed_count": 0
      },
      "duration_ms": 133765.44
    }
  ],
  "summary": {
    "total_duration_ms": 135234.56,
    "all_steps_successful": true
  }
}
```

**Response (207 - Kısmi Başarı):**
```json
{
  "status": "partial",
  "workflow": "rebuild_with_test",
  "message": "Rebuild completed in 135234.56ms",
  "steps": [...],
  "summary": {
    "total_duration_ms": 135234.56,
    "all_steps_successful": false
  }
}
```

**Kullanım:**
```bash
# Tam workflow (önerilen)
curl -X POST http://localhost:5000/api/bulk-faiss/rebuild-with-test \
  -H "Content-Type: application/json" \
  -d '{
    "textual_model_name": "ViT-L/14",
    "visual_model_name": "ViT-L/14"
  }'

# Test ürün ID'si özelleştirilmiş
curl -X POST http://localhost:5000/api/bulk-faiss/rebuild-with-test \
  -H "Content-Type: application/json" \
  -d '{
    "test_product_id": "my-test-123",
    "wait_duration_seconds": 90
  }'
```

---

## 🔧 Optimizasyonlar

### 1. Database Eager Loading

N+1 query problemi çözüldü:

```python
# Optimize edilmiş (tek query):
products = (Product.query
    .filter_by(is_active=True)
    .options(
        joinedload(Product.brand),
        joinedload(Product.categories),
        joinedload(Product.images)
    )
    .all())
```

**Fayda:** 1500 ürün için ~1500 query yerine sadece 1 query.

### 2. FAISS Init Bekleme

İlk ürün eklendikten sonra FAISS index'in hazırlanması için otomatik bekleme:

```python
if result.get('status') == 'success':
    successful_count += 1
    
    if wait_after_first and not waited_after_first:
        waited_after_first = True
        logger.info(f"⏳ Waiting {wait_duration_seconds}s for FAISS init...")
        time.sleep(wait_duration_seconds)
```

**Neden?** FAISS service ilk embedding'den sonra index'i initialize ediyor. Bu süre içinde gelen istekler başarısız olabilir.

### 3. Ürünler Arası Delay (Opsiyonel)

Her ürün eklemesi arasında ekstra delay:

```python
if delay_between_products_ms > 0:
    time.sleep(delay_between_products_ms / 1000.0)
```

**Kullanım:** FAISS service çok yavaş yanıt veriyorsa rate limiting için.

---

## 📊 Log Örnekleri

### Bulk Import Log
```
[BulkFAISS] Using models - Textual: ViT-B/32, Visual: ViT-B/32
[BulkFAISS] Wait after first: True (60s)
[BulkFAISS] Starting bulk import of 1500 products
[BulkFAISS] Adding product 1: Laptop
[BulkFAISS] ✅ Product 1 added successfully
[BulkFAISS] ⏳ Waiting 60s for FAISS index initialization...
[BulkFAISS] ✅ Wait completed, continuing with bulk import
[BulkFAISS] Adding product 2: Mouse
[BulkFAISS] ✅ Product 2 added successfully
[BulkFAISS] Adding product 3: Keyboard
...
[BulkFAISS] Bulk import completed: 1498/1500 successful in 125678.90ms
```

### Rebuild Workflow Log
```
[BulkFAISS] Starting rebuild workflow with models - Textual: ViT-L/14, Visual: ViT-L/14
[BulkFAISS] Step 1/3: Clearing FAISS index
[BulkFAISS] Step 1 completed: Index cleared in 234.56ms
[BulkFAISS] Step 2/3: Adding test product test-001
[BulkFAISS] Step 2 completed on attempt 1: Test product added
[BulkFAISS] Step 3/3: Adding all products from database
[BulkFAISS] ⏳ Waiting 60s for FAISS index initialization...
[BulkFAISS] ✅ Wait completed, continuing with bulk import
[BulkFAISS] Step 3 completed: 1500/1500 products added in 133765.44ms
[BulkFAISS] Rebuild workflow completed in 135234.56ms
```

---

## 🚀 Önerilen Kullanım

### Model Değişimi İçin (Önerilen Workflow)

```bash
# Tek komut ile tam workflow
curl -X POST http://localhost:5000/api/bulk-faiss/rebuild-with-test \
  -H "Content-Type: application/json" \
  -d '{
    "textual_model_name": "ViT-L/14",
    "visual_model_name": "ViT-L/14",
    "wait_after_first": true,
    "wait_duration_seconds": 60
  }'
```

### Manuel Adım Adım

```bash
# 1. Index'i temizle
curl -X DELETE http://localhost:5000/api/retrieval/clear-index

# 2. Test ürünü ekle
curl -X POST http://localhost:5000/api/retrieval/test-product \
  -H "Content-Type: application/json" \
  -d '{"product_id": "test-001"}'

# 3. Tüm ürünleri ekle
curl -X POST http://localhost:5000/api/bulk-faiss/add-all \
  -H "Content-Type: application/json" \
  -d '{
    "textual_model_name": "ViT-L/14",
    "visual_model_name": "ViT-L/14",
    "wait_after_first": true,
    "wait_duration_seconds": 60
  }'
```

---

## ⚠️ Önemli Notlar

### 1. Varsayılan Bekleme Süresi
- **60 saniye** (1 dakika) olarak ayarlandı
- İlk üründen sonra otomatik uygulanır
- `wait_after_first: false` ile devre dışı bırakılabilir

### 2. Model Validasyonu
Geçersiz model isimleri 400 hatası döner:
```json
{
  "status": "error",
  "error": "Invalid textual model: invalid-model. Available: ['ViT-B/32', 'ViT-B/16', ...]"
}
```

### 3. Hata Yönetimi
- İlk ürün başarısız olursa workflow durur
- Test ürünü 3 kez denenir (retry logic)
- Hatalar `errors` array'inde toplanır (max 10)

### 4. Performans
- **Eager loading** ile DB sorguları optimize edildi
- **Wait mechanism** ile FAISS init süresi bekleniyor
- **Delay** ile rate limiting yapılabilir

---

## 📁 Değiştirilen Dosyalar

1. **services/faiss_retrieval_service.py**
   - `clear_index()` metodu
   - `add_test_product()` metodu
   - `get_available_models()` metodu
   - `FAISS_CLEAR_INDEX_URL` constant

2. **services/text_corrector_service.py**
   - `get_available_models()` metodu
   - `CORRECTION_MODELS_URL` constant
   - `AVAILABLE_CORRECTION_MODELS` dictionary

3. **routes/retrieval.py**
   - `DELETE /clear-index` endpoint
   - `POST /test-product` endpoint
   - `GET /models` endpoint

4. **routes/correction.py** (YENİ)
   - `GET /models` endpoint

5. **routes/bulk_faiss.py**
   - `POST /rebuild-with-test` endpoint
   - `add-all` endpoint'ine wait logic
   - Eager loading optimizasyonu

6. **routes/__init__.py**
   - `correction_bp` blueprint

7. **app.py**
   - Blueprint kayıtları
   - Startup logları

---

## 🔗 İlgili Dokümantasyon

- [FAISS Add Product API](./FAISS_ADD_PRODUCT_API.md)
- [System Overview](./SYSTEM_OVERVIEW.md)
- [README.md](../README.md)

---

## 📞 Destek

Sorularınız için:
- GitHub Issues: [smartsearch-backend/issues](https://github.com/your-repo/issues)
- Dokümantasyon: `/docs` klasörü
