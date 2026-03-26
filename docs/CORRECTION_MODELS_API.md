# Text Correction Models API Dokümantasyonu

## 📋 Genel Bakış

Text Correction Service, arama sorgularındaki yazım hatalarını düzeltmek için kullanılır. Bu dokümantasyon, kullanılabilir correction modellerini listeyen endpoint'i açıklar.

---

## 🎯 Kullanım Senaryoları

### Senaryo 1: UI Dropdown Doldurma
Frontend'de kullanıcıya model seçimi sunmak için kullanılabilir modelleri almak.

### Senaryo 2: Model Validasyonu
Kullanıcının seçtiği modelin geçerli olup olmadığını kontrol etmek.

### Senaryo 3: Debug ve Test
Correction service'in doğru modelleri sunduğunu doğrulamak.

---

## 📚 Endpoint

### GET /api/correction/models

Correction service'te kullanılabilir text correction modellerini listeler.

**Request:**
```http
GET /api/correction/models HTTP/1.1
```

**Response (200 OK):**
```json
{
  "status": "success",
  "data": {
    "models": [
      {
        "id": "symspell_keyboard",
        "name": "SymSpell (Hızlı - Keyboard Based)"
      },
      {
        "id": "byt5",
        "name": "ByT5 Finetuned (ML Model - Daha Doğru)"
      }
    ],
    "default": "byt5"
  },
  "source": "correction_service"
}
```

**Response Alanları:**

| Alan | Tip | Açıklama |
|------|-----|----------|
| `status` | string | `"success"` veya `"error"` |
| `data.models` | array[] | Kullanılabilir modeller listesi |
| `data.models[].id` | string | Model ID (API'de kullanılan) |
| `data.models[].name` | string | Model görünen adı |
| `data.default` | string | Varsayılan model ID |
| `source` | string | `"correction_service"` veya `"local_config"` |

---

## 🔧 Kullanım Örnekleri

### cURL
```bash
curl http://localhost:5000/api/correction/models
```

### JavaScript/React
```javascript
const response = await fetch('http://localhost:5000/api/correction/models');
const data = await response.json();

// Modelleri dropdown'da göster
data.data.models.map(model => (
  <option value={model.id} key={model.id}>
    {model.name}
  </option>
));
```

### Python
```python
import requests

response = requests.get('http://localhost:5000/api/correction/models')
data = response.json()

print("Kullanılabilir modeller:")
for model in data['data']['models']:
    print(f"  - {model['id']}: {model['name']}")

print(f"Varsayılan: {data['data']['default']}")
```

---



## ⚠️ Hata Durumları

### Correction Service Erişilemez (Fallback)

Eğer correction service (port 5001) erişilemezse, local config'den fallback yapılır:

```json
{
  "status": "success",
  "data": {
    "models": [
      {
        "id": "symspell_keyboard",
        "name": "SymSpell (Hızlı - Keyboard Based)"
      },
      {
        "id": "byt5",
        "name": "ByT5 Finetuned (ML Model - Daha Doğru)"
      }
    ],
    "default": "byt5"
  },
  "source": "local_config"
}
```

**Not:** `source` alanı `"local_config"` olarak değişir.

---

## 🔍 Model Detayları

### SymSpell (symspell_keyboard)

**Özellikler:**
- Hızlı, dictionary-based correction
- Klavye düzenini kullanarak typo detection
- Düşük latency

**Kullanım:**
- Gerçek zamanlı arama
- Yüksek throughput gerektiren senaryolar

### ByT5 Finetuned (byt5)

**Özellikler:**
- ML-based correction (fine-tuned ByT5 model)
- Daha doğru typo detection
- Context-aware correction

**Kullanım:**
- Kalite öncelikli senaryolar
- Karmaşık yazım hataları için

---

## 📊 Log Örnekleri

### Başarılı Fetch (Service'ten)
```
[Correction] Fetching available models
[Correction] Successfully fetched models from correction_service
```

### Fallback (Local Config)
```
[Correction] Fetching available models
[Correction] Service not available at http://localhost:5001/models, using local config
[Correction] Successfully fetched models from local_config
```

---

## 🔗 İlgili Endpoint'ler

### Search API ile Kullanım

```bash
# Correction modeli ile arama
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "raw_text": "iphnoe",
    "correction_engine": "byt5"
  }'
```

---

## 📁 Değiştirilen Dosyalar

1. **services/text_corrector_service.py**
   - `get_available_models()` metodu
   - `_get_local_models()` helper metodu
   - `CORRECTION_MODELS_URL` constant
   - `AVAILABLE_CORRECTION_MODELS` dictionary

2. **routes/correction.py** (YENİ)
   - `GET /models` endpoint

3. **routes/__init__.py**
   - `correction_bp` blueprint

4. **app.py**
   - `correction_bp` blueprint kaydı
   - Startup loglarına ekleme

---

## 🌐 Environment Variables

```bash
# Correction service URL
CORRECTION_SERVICE_URL=http://localhost:5001/correct

# Correction models endpoint URL
CORRECTION_MODELS_URL=http://localhost:5001/models
```

---

## 📞 Destek

- Dokümantasyon: `/docs` klasörü
