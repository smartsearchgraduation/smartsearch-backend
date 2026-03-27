# Model Seçimi - Basit Anlatım 🎯

## 🤔 Bu Ne İşe Yarıyor?

Admin panel'den model seçiyorsun (örn: "ViT-L/14"), backend de bu seçimi FAISS service'e iletiyor. Sonra bulk import yaparken otomatik olarak bu seçili model kullanılıyor.

---

## 📺 Senaryo: Admin Panel'den Model Seçimi

### Adım 1: Admin Panel'de Model Seç

```
┌─────────────────────────────────┐
│  FAISS Model Ayarları           │
├─────────────────────────────────┤
│                                 │
│  Textual Model:                 │
│  [ ViT-L/14 (Büyük Model)  ▼ ] │
│                                 │
│  Visual Model:                  │
│  [ ViT-L/14 (Büyük Model)  ▼ ] │
│                                 │
│  [💾 Kaydet]                    │
└─────────────────────────────────┘
```

### Adım 2: "Kaydet" Butonuna Bas

**Ne Oluyor:**
```
Admin Panel → Backend (5000) → FAISS Service (5002)
```

**Kod:**
```javascript
// Admin panel kodu
async function saveModels() {
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
}
```

### Adım 3: Backend FAISS'e İletiyor

**Backend Kodu (Otomatik Yapıyor):**
```python
# routes/retrieval.py
faiss_response = faiss_service.save_selected_models(
    textual_model='ViT-L/14',
    visual_model='ViT-L/14'
)
```

**FAISS Service Kodu (5002'de Çalışıyor):**
```python
# FAISS service kendi içinde modeli kaydediyor
# ve index rebuild trigger'lıyor
```

### Adım 4: Başarılı! ✅

**Response:**
```json
{
  "status": "success",
  "message": "Models saved successfully",
  "data": {
    "textual_model": "ViT-L/14",
    "visual_model": "ViT-L/14"
  },
  "source": "faiss_service"
}
```

---

## 🚀 Bulk Import Yaparken Ne Oluyor?

### Senaryo 1: Model Göndermezsen (Otomatik)

**Request:**
```bash
curl -X POST http://localhost:5000/api/bulk-faiss/add-all \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Backend Ne Yapıyor:**
```python
# 1. Request'te model var mı? → Hayır
# 2. FAISS service'e sor → "ViT-L/14" kullan
# 3. Bu modelle bulk import yap
```

**Log:**
```
[BulkFAISS] Fetching models from FAISS service...
[BulkFAISS] Using models - Textual: ViT-L/14, Visual: ViT-L/14
[BulkFAISS] Step 1/2: Clearing FAISS index...
[BulkFAISS] Step 2/2: Adding all products...
```

### Senaryo 2: Model Gönderirsen (Override)

**Request:**
```bash
curl -X POST http://localhost:5000/api/bulk-faiss/add-all \
  -H "Content-Type: application/json" \
  -d '{
    "textual_model_name": "ViT-B/16",
    "visual_model_name": "ViT-B/16"
  }'
```

**Backend Ne Yapıyor:**
```python
# 1. Request'te model var mı? → Evet
# 2. O modeli kullan (FAISS'e sormuyor)
# 3. Bu modelle bulk import yap
```

**Log:**
```
[BulkFAISS] Using models - Textual: ViT-B/16, Visual: ViT-B/16
[BulkFAISS] Step 1/2: Clearing FAISS index...
[BulkFAISS] Step 2/2: Adding all products...
```

---

## 🎯 Özet: 3 Basit Adım

### 1️⃣ Model Seç (Admin Panel)
```javascript
POST /api/retrieval/selected-models
Body: { textual_model: "ViT-L/14", visual_model: "ViT-L/14" }
```

### 2️⃣ Bulk Import Yap (Model Gönderme)
```javascript
POST /api/bulk-faiss/add-all
Body: {}  // Model gönderme, otomatik seçili modeli kullanır
```

### 3️⃣ Backend Halleder
- ✅ FAISS'ten modeli çeker
- ✅ Index'i temizler
- ✅ İlk ürünü gönderir
- ✅ 60 saniye bekler
- ✅ Tüm ürünleri indeksler

---

## 📊 Akış Diyagramı

```
┌──────────────┐
│ Admin Panel  │
└──────┬───────┘
       │ 1. Model Seç
       │ POST /selected-models
       ▼
┌──────────────┐
│   Backend    │
│   (5000)     │
└──────┬───────┘
       │ 2. İlet
       │ POST /selected-models
       ▼
┌──────────────┐
│ FAISS Service│
│   (5002)     │
│ Kaydet +     │
│ Rebuild      │
└──────────────┘

--- ZAMAN ATLAR ---

┌──────────────┐
│ Admin Panel  │
└──────┬───────┘
       │ 3. Bulk Import
       │ POST /add-all (model yok)
       ▼
┌──────────────┐
│   Backend    │
│   (5000)     │
│ FAISS'te     │
│ sor → Model  │
│ al           │
└──────┬───────┘
       │ 4. Kullan
       │ POST /add-product
       ▼
┌──────────────┐
│ FAISS Service│
│   (5002)     │
│ Index'e Ekle │
└──────────────┘
```

---

## 🛠️ Pratik Örnekler

### Örnek 1: İlk Kurulum

```javascript
// 1. Admin panel modeli kaydet
await fetch('http://localhost:5000/api/retrieval/selected-models', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    textual_model: 'ViT-L/14',
    visual_model: 'ViT-L/14'
  })
});

// 2. Bulk import yap (otomatik seçili modeli kullanır)
await fetch('http://localhost:5000/api/bulk-faiss/add-all', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({})  // Model yok!
});
```

### Örnek 2: Model Değiştirme

```javascript
// 1. Yeni model kaydet
await fetch('http://localhost:5000/api/retrieval/selected-models', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    textual_model: 'ViT-B/16',  // Değişti!
    visual_model: 'ViT-B/16'    // Değişti!
  })
});

// 2. Bulk import yap (yeni modeli kullanır)
await fetch('http://localhost:5000/api/bulk-faiss/add-all', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({})
});
```

### Örnek 3: Tek Seferlik Farklı Model

```javascript
// Seçili model: ViT-L/14 (admin panel'den kaydedilmiş)
// Ama bu sefer farklı model kullan

await fetch('http://localhost:5000/api/bulk-faiss/add-all', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    textual_model_name: 'RN50',  // Override!
    visual_model_name: 'RN50'    // Override!
  })
});

// Bir sonraki bulk import yine ViT-L/14 kullanır (seçili model)
```

---

## ❓ Sık Sorulan Sorular

### S: Model seçimini nereye kaydediyor?
**C:** FAISS service (port 5002) kendi içinde saklıyor. Backend'de yok.

### S: FAISS kapalıysa ne olur?
**C:** Bulk import default modelleri kullanır (BAAI/bge-large-en-v1.5, ViT-B/32).

### S: Her bulk import'ta model göndermem lazım mı?
**C:** Hayır! Bir kez admin panel'den kaydet, sonra her seferinde otomatik kullanılır.

### S: Override edebilir miyim?
**C:** Evet! Request'te `textual_model_name` ve `visual_model_name` gönderirsen o kullanılır.

---

## 🎓 Sonuç

**Basit Mantık:**
1. Admin panel'den model seç → Kaydet
2. Bulk import yap → Otomatik seçili modeli kullanır
3. Farklı model istiyorsan → Request'te gönder

**Backend:**
- ✅ Admin panel'den gelen modeli FAISS'e iletir
- ✅ Bulk import'ta FAISS'ten modeli çeker
- ✅ Request'te model varsa onu kullanır

**FAISS Service:**
- ✅ Model seçimini saklar
- ✅ Index rebuild trigger'lar
- ✅ Available models listesini döner

**O kadar! 🎉**
