# SmartSearch Backend Dokümantasyon

Bu klasör, SmartSearch Backend API ve servisleri için teknik dokümantasyonları içerir.

---

## 📚 Dokümantasyonlar

### Genel Bakış
- **[SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md)** - Sistem mimarisi, akış diyagramları ve servis detayları

### FAISS API
- **[FAISS_ADD_PRODUCT_API.md](./FAISS_ADD_PRODUCT_API.md)** - `/api/retrieval/add-product` endpoint detayları
- **[FAISS_BULK_IMPORT_WORKFLOW.md](./FAISS_BULK_IMPORT_WORKFLOW.md)** - Bulk import ve rebuild workflow dokümantasyonu
  - `GET /api/retrieval/models`
  - `DELETE /api/retrieval/clear-index`
  - `POST /api/retrieval/test-product`
  - `POST /api/bulk-faiss/add-all`
  - `POST /api/bulk-faiss/rebuild-with-test`

### Correction API
- **[CORRECTION_MODELS_API.md](./CORRECTION_MODELS_API.md)** - Text correction models endpoint
  - `GET /api/correction/models`

---

## 🔗 Hızlı Başlangıç

### FAISS Index Yeniden Build
```bash
# Tek komut ile tam workflow (önerilen)
curl -X POST http://localhost:5000/api/bulk-faiss/rebuild-with-test \
  -H "Content-Type: application/json" \
  -d '{
    "textual_model_name": "ViT-L/14",
    "visual_model_name": "ViT-L/14",
    "wait_after_first": true,
    "wait_duration_seconds": 60
  }'
```

### Modelleri Listele
```bash
# FAISS modelleri
curl http://localhost:5000/api/retrieval/models

# Correction modelleri
curl http://localhost:5000/api/correction/models
```

### Index'i Temizle
```bash
curl -X DELETE http://localhost:5000/api/retrieval/clear-index
```

---

## 📋 Önemli Konseptler

### 1. FAISS Init Bekleme
İlk ürün eklendikten sonra FAISS index hazırlığı için **varsayılan 60 saniye** beklenir.

**Neden?**
- FAISS service ilk embedding'den sonra index'i initialize ediyor
- Bu süre içinde gelen istekler başarısız olabilir
- `wait_after_first: false` ile devre dışı bırakılabilir

### 2. Database Eager Loading
N+1 query problemini önler:
```python
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

### 3. Workflow Steps
`rebuild-with-test` endpoint'i 3 adım içerir:
1. **Clear Index** - Tüm veriyi temizle
2. **Test Product** - FAISS'in çalıştığını doğrula
3. **Bulk Add** - Tüm ürünleri ekle

Her adımın sonucu `steps` array'inde detaylandırılır.

---

## 🛠️ Servis Bağımlılıkları

| Servis | Port | Endpoint | Açıklama |
|--------|------|----------|----------|
| Text Corrector | 5001 | `http://localhost:5001/correct` | Spell-checking ve typo correction |
| Text Corrector Models | 5001 | `http://localhost:5001/models` | Kullanılabilir correction modelleri |
| FAISS | 5002 | `http://localhost:5002/api/retrieval/*` | Vector search ve indexing |

---

## 📊 Monitoring ve Debugging

### Log Pattern'leri

**Bulk Import:**
```
[BulkFAISS] Using models - Textual: ViT-B/32, Visual: ViT-B/32
[BulkFAISS] Wait after first: True (60s)
[BulkFAISS] Starting bulk import of 1500 products
[BulkFAISS] ⏳ Waiting 60s for FAISS index initialization...
[BulkFAISS] Bulk import completed: 1498/1500 successful
```

**Rebuild Workflow:**
```
[BulkFAISS] Starting rebuild workflow with models
[BulkFAISS] Step 1/3: Clearing FAISS index
[BulkFAISS] Step 2/3: Adding test product
[BulkFAISS] Step 3/3: Adding all products from database
[BulkFAISS] Rebuild workflow completed in 135234.56ms
```

### Hata Senaryolaru

| Hata | Sebep | Çözüm |
|------|-------|-------|
| `FAISS service not available` | Port 5002'de servis yok | FAISS service'i başlat |
| `Invalid textual model` | Geçersiz model ismi | `GET /api/retrieval/models` ile geçerli modelleri al |
| `No products found in database` | Database boş | Ürün ekle |

---

## 📁 Dosya Yapısı

```
docs/
├── README.md                      # Bu dosya
├── SYSTEM_OVERVIEW.md             # Genel sistem bakışı
├── FAISS_ADD_PRODUCT_API.md       # Add product endpoint
├── FAISS_BULK_IMPORT_WORKFLOW.md  # Bulk import workflows
└── CORRECTION_MODELS_API.md       # Correction models API
```

---

## 🔄 Güncellemeler

### Son Eklenenler (2026)
- ✅ `GET /api/retrieval/models` - FAISS model listesi
- ✅ `DELETE /api/retrieval/clear-index` - Index temizleme
- ✅ `POST /api/retrieval/test-product` - Test ürünü
- ✅ `POST /api/bulk-faiss/rebuild-with-test` - Tam workflow
- ✅ `GET /api/correction/models` - Correction modelleri
- ✅ Eager loading optimizasyonu (N+1 query fix)
- ✅ FAISS init bekleme mekanizması (60s default)

---

## 📞 Destek

- **GitHub Issues:** [smartsearch-backend/issues](https://github.com/your-repo/issues)
- **Ana README:** [../README.md](../README.md)
