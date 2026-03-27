# API JSON Örnekleri - Model Seçimi

## 📋 Endpoint'ler

### 1. GET /api/retrieval/selected-models

**Amaç:** FAISS service'ten seçili modelleri ve available models listesini almak.

**Request:**
```http
GET /api/retrieval/selected-models HTTP/1.1
Host: localhost:5000
```

**Response (Başarılı - FAISS'ten):**
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
        "id": "ViT-L/14",
        "name": "ViT-L/14 (Büyük Model)"
      },
      {
        "id": "ViT-L/14@336px",
        "name": "ViT-L/14@336px (En Yüksek Çözünürlük)"
      },
      {
        "id": "BAAI/bge-large-en-v1.5",
        "name": "BAAI/bge-large-en-v1.5 (Büyük Model)"
      },
      {
        "id": "RN50",
        "name": "RN50 (ResNet-50)"
      },
      {
        "id": "RN101",
        "name": "RN101 (ResNet-101)"
      }
    ],
    "visual_models": [
      {
        "id": "ViT-B/32",
        "name": "ViT-B/32 (Varsayılan - Hızlı)"
      },
      {
        "id": "ViT-B/16",
        "name": "ViT-B/16 (Daha Doğru)"
      },
      {
        "id": "ViT-L/14",
        "name": "ViT-L/14 (Büyük Model)"
      }
    ],
    "defaults": {
      "textual": "ViT-L/14",
      "visual": "ViT-L/14"
    }
  },
  "source": "faiss_service"
}
```

**Response (Fallback - Local):**
```json
{
  "status": "success",
  "data": {
    "defaults": {
      "textual": "BAAI/bge-large-en-v1.5",
      "visual": "ViT-B/32"
    }
  },
  "source": "local_config",
  "message": "FAISS service unavailable, using local defaults"
}
```

---

### 2. POST /api/retrieval/selected-models

**Amaç:** Admin panel'den seçilen modelleri FAISS service'e kaydetmek.

**Request:**
```http
POST /api/retrieval/selected-models HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "textual_model": "ViT-L/14",
  "visual_model": "ViT-L/14"
}
```

**Response (Başarılı):**
```json
{
  "status": "success",
  "message": "Models saved successfully",
  "data": {
    "textual_model": "ViT-L/14",
    "visual_model": "ViT-L/14",
    "saved_at": "2026-03-26T14:30:00Z",
    "index_rebuild_triggered": true
  },
  "source": "faiss_service"
}
```

**Response (Hata - Geçersiz Model):**
```json
{
  "status": "error",
  "error": "Invalid textual model: Invalid-Model-XYZ. Available: ['ViT-B/32', 'ViT-B/16', 'ViT-L/14', ...]"
}
```

**Response (Hata - Eksik Alan):**
```json
{
  "status": "error",
  "error": "Both textual_model and visual_model are required"
}
```

**Response (Hata - FAISS Erişilemez):**
```json
{
  "status": "error",
  "error": "FAISS service not available"
}
```

---

### 3. POST /api/bulk-faiss/add-all

**Amaç:** Tüm ürünleri FAISS index'e eklemek (otomatik seçili model kullanılır).

#### Senaryo 1: Model Göndermezsen (Otomatik)

**Request:**
```http
POST /api/bulk-faiss/add-all HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{}
```

**Backend Ne Yapıyor:**
```
1. Request'te model yok → FAISS service'e sor
2. FAISS'ten "defaults" al
3. Bu modellerle bulk import yap
```

**Response (Başarılı):**
```json
{
  "status": "success",
  "message": "Bulk import completed: 1498 products added",
  "details": {
    "total_products": 1500,
    "successful_count": 1498,
    "failed_count": 2,
    "total_time_ms": 125678.90,
    "textual_model_name": "ViT-L/14",
    "visual_model_name": "ViT-L/14",
    "wait_applied": true,
    "wait_duration_seconds": 60,
    "delay_between_products_ms": 0,
    "errors": [
      {
        "product_id": 42,
        "error": "Image not found: /path/to/missing.jpg"
      },
      {
        "product_id": 127,
        "error": "FAISS timeout"
      }
    ]
  }
}
```

#### Senaryo 2: Model Gönderirsen (Override)

**Request:**
```http
POST /api/bulk-faiss/add-all HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "textual_model_name": "ViT-B/16",
  "visual_model_name": "ViT-B/16",
  "wait_duration_seconds": 90,
  "delay_between_products_ms": 100
}
```

**Backend Ne Yapıyor:**
```
1. Request'te model var → O modeli kullan
2. FAISS'e sormuyor
3. Bu modellerle bulk import yap
```

**Response (Başarılı):**
```json
{
  "status": "success",
  "message": "Bulk import completed: 1500 products added",
  "details": {
    "total_products": 1500,
    "successful_count": 1500,
    "failed_count": 0,
    "total_time_ms": 145234.56,
    "textual_model_name": "ViT-B/16",
    "visual_model_name": "ViT-B/16",
    "wait_applied": true,
    "wait_duration_seconds": 90,
    "delay_between_products_ms": 100,
    "errors": []
  }
}
```

---

### 4. POST /api/bulk-faiss/rebuild-with-test

**Amaç:** FAISS index'i tamamen yeniden build etmek (clear → test → bulk add).

#### Senaryo 1: Model Göndermezsen (Otomatik)

**Request:**
```http
POST /api/bulk-faiss/rebuild-with-test HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{}
```

**Backend Ne Yapıyor:**
```
1. Request'te model yok → FAISS'ten çek
2. Index'i temizle
3. Test ürünü gönder
4. 60 saniye bekle
5. Tüm ürünleri ekle
```

**Response (Başarılı):**
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
        "product_id": "test-product-001",
        "textual_vector_id": 1,
        "visual_vector_ids": [2, 3]
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
    "all_steps_successful": true,
    "textual_model_name": "ViT-L/14",
    "visual_model_name": "ViT-L/14"
  }
}
```

#### Senaryo 2: Model Gönderirsen (Override)

**Request:**
```http
POST /api/bulk-faiss/rebuild-with-test HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
  "textual_model_name": "ViT-L/14",
  "visual_model_name": "ViT-L/14",
  "test_product_id": "my-test-001",
  "wait_duration_seconds": 120
}
```

**Response (Başarılı):**
```json
{
  "status": "success",
  "workflow": "rebuild_with_test",
  "message": "Rebuild completed in 195234.56ms",
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
        "product_id": "my-test-001",
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
      "duration_ms": 193765.44
    }
  ],
  "summary": {
    "total_duration_ms": 195234.56,
    "all_steps_successful": true,
    "textual_model_name": "ViT-L/14",
    "visual_model_name": "ViT-L/14"
  }
}
```

---

## 🔍 Detaylı Alan Açıklamaları

### GET /api/retrieval/selected-models Response

| Alan | Tip | Açıklama |
|------|-----|----------|
| `status` | string | "success" veya "error" |
| `data.textual_models[]` | array | Kullanılabilir textual modeller |
| `data.textual_models[].id` | string | Model ID (örn: "ViT-L/14") |
| `data.textual_models[].name` | string | Model görünen adı |
| `data.visual_models[]` | array | Kullanılabilir visual modeller |
| `data.defaults.textual` | string | Varsayılan textual model |
| `data.defaults.visual` | string | Varsayılan visual model |
| `source` | string | "faiss_service" veya "local_config" |

### POST /api/retrieval/selected-models Request

| Alan | Tip | Zorunlu | Açıklama |
|------|-----|--------|----------|
| `textual_model` | string | ✅ Evet | Textual embedding model ID |
| `visual_model` | string | ✅ Evet | Visual embedding model ID |

**Örnek Değerler:**
- `"ViT-B/32"` - Hızlı, varsayılan
- `"ViT-B/16"` - Daha doğru
- `"ViT-L/14"` - Büyük model, daha yavaş
- `"BAAI/bge-large-en-v1.5"` - En doğru textual

### POST /api/bulk-faiss/add-all Request

| Alan | Tip | Zorunlu | Varsayılan | Açıklama |
|------|-----|--------|----------|----------|
| `textual_model_name` | string | ❌ Hayır | FAISS defaults | Textual model (gönderilmezse FAISS'ten) |
| `visual_model_name` | string | ❌ Hayır | FAISS defaults | Visual model (gönderilmezse FAISS'ten) |
| `wait_duration_seconds` | integer | ❌ Hayır | 60 | İlk üründen sonra bekleme süresi |
| `delay_between_products_ms` | integer | ❌ Hayır | 0 | Ürünler arası ek delay |

### POST /api/bulk-faiss/add-all Response

| Alan | Tip | Açıklama |
|------|-----|----------|
| `status` | string | "success", "partial", veya "error" |
| `message` | string | Özet mesaj |
| `details.total_products` | integer | Toplam ürün sayısı |
| `details.successful_count` | integer | Başarılı eklenenler |
| `details.failed_count` | integer | Başarısız olanlar |
| `details.total_time_ms` | float | Toplam süre (ms) |
| `details.textual_model_name` | string | Kullanılan textual model |
| `details.visual_model_name` | string | Kullanılan visual model |
| `details.wait_applied` | boolean | Bekleme uygulandı mı? |
| `details.wait_duration_seconds` | integer | Bekleme süresi |
| `details.errors[]` | array | Hata detayları (max 10) |

---

## 💡 Pratik Kullanım Örnekleri

### cURL - Model Kaydet
```bash
curl -X POST http://localhost:5000/api/retrieval/selected-models \
  -H "Content-Type: application/json" \
  -d '{
    "textual_model": "ViT-L/14",
    "visual_model": "ViT-L/14"
  }'
```

### cURL - Mevcut Modelleri Öğren
```bash
curl http://localhost:5000/api/retrieval/selected-models
```

### cURL - Bulk Import (Otomatik Model)
```bash
curl -X POST http://localhost:5000/api/bulk-faiss/add-all \
  -H "Content-Type: application/json" \
  -d '{}'
```

### cURL - Bulk Import (Override Model)
```bash
curl -X POST http://localhost:5000/api/bulk-faiss/add-all \
  -H "Content-Type: application/json" \
  -d '{
    "textual_model_name": "ViT-B/16",
    "visual_model_name": "ViT-B/16",
    "wait_duration_seconds": 90
  }'
```

### JavaScript (Fetch) - Model Kaydet
```javascript
const response = await fetch('http://localhost:5000/api/retrieval/selected-models', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    textual_model: 'ViT-L/14',
    visual_model: 'ViT-L/14'
  })
});

const result = await response.json();
console.log(result);
// { status: 'success', message: 'Models saved successfully' }
```

### JavaScript (Fetch) - Bulk Import
```javascript
// Otomatik model kullanımı
const response = await fetch('http://localhost:5000/api/bulk-faiss/add-all', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({})  // Model yok, otomatik seçili kullanılır
});

const result = await response.json();
console.log(`Imported ${result.details.successful_count} products`);
```

### Python (Requests) - Model Kaydet
```python
import requests

response = requests.post(
    'http://localhost:5000/api/retrieval/selected-models',
    json={
        'textual_model': 'ViT-L/14',
        'visual_model': 'ViT-L/14'
    }
)

result = response.json()
print(result['message'])  # Models saved successfully
```

### Python (Requests) - Bulk Import
```python
import requests

# Otomatik model
response = requests.post(
    'http://localhost:5000/api/bulk-faiss/add-all',
    json={}
)

result = response.json()
print(f"Imported {result['details']['successful_count']} products")
```

---

## ⚠️ Hata Senaryoları

### 400 Bad Request - Geçersiz Model
```json
{
  "status": "error",
  "error": "Invalid textual model: Invalid-Model. Available: ['ViT-B/32', 'ViT-B/16', ...]"
}
```

### 400 Bad Request - Eksik Alan
```json
{
  "status": "error",
  "error": "Both textual_model and visual_model are required"
}
```

### 500 Internal Server Error - FAISS Erişilemez
```json
{
  "status": "error",
  "error": "FAISS service not available"
}
```

### 500 Internal Server Error - Timeout
```json
{
  "status": "error",
  "error": "Request timeout - FAISS service did not respond"
}
```

---

## 📊 Response Code Özet

| Code | Açıklama | Ne Zaman |
|------|----------|----------|
| 200 | OK | Başarılı işlem |
| 400 | Bad Request | Geçersiz model, eksik alan |
| 500 | Internal Server Error | FAISS erişilemez, timeout |

---

**Bu dosya API'yi kullanırken referans olarak kullanılabilir!** 📚
