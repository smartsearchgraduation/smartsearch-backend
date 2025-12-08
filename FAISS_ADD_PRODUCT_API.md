# FAISS Add Product Endpoint Documentation

## Overview
The `/api/retrieval/add-product` endpoint allows you to add products to FAISS indices for both textual and visual search capabilities.

## Endpoint Details

**URL:** `POST /api/retrieval/add-product`

**Content-Type:** `application/json`

## Request Format

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique product identifier |
| `name` | string | Product name (required, non-empty) |
| `images` | array[string] | List of absolute image paths (at least 1 required) |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `description` | string | `""` | Product description |
| `brand` | string | `""` | Brand name |
| `category` | string | `""` | Category name |
| `price` | float | `0.0` | Product price |
| `textual_model_name` | string | `"ViT-B/32"` | Model for text embedding |
| `visual_model_name` | string | `"ViT-B/32"` | Model for image embedding |

### Example Request

```json
{
    "id": "product_001",
    "name": "Premium Leather Handbag",
    "description": "Elegant handcrafted leather bag",
    "brand": "LuxuryBrand",
    "category": "Accessories",
    "price": 299.99,
    "images": [
        "C:/absolute/path/to/image1.jpg",
        "C:/absolute/path/to/image2.jpg"
    ],
    "textual_model_name": "ViT-B/32",
    "visual_model_name": "ViT-B/32"
}
```

## Response Format

### Success Response (200 OK)

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

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Always `"success"` for successful operations |
| `message` | string | Human-readable success message |
| `details.product_id` | string | Echo of the product ID |
| `details.textual_vector_id` | integer | FAISS index ID for text embedding |
| `details.visual_vector_ids` | array[integer] | FAISS index IDs for each image embedding |
| `details.images_processed` | integer | Count of successfully processed images |

### Error Responses

#### 400 Bad Request - Missing Required Field

```json
{
    "status": "error",
    "error": "Missing required field: name"
}
```

#### 400 Bad Request - Invalid Images

```json
{
    "status": "error",
    "error": "Missing or invalid field: images (must be non-empty list)"
}
```

#### 500 Internal Server Error - FAISS Service Unavailable

```json
{
    "status": "error",
    "error": "FAISS service not available"
}
```

#### 500 Internal Server Error - No Valid Images

```json
{
    "status": "error",
    "error": "No valid image paths found"
}
```

## Processing Flow

1. **Request Validation**
   - Validates required fields (`id`, `name`, `images`)
   - Checks that `images` is a non-empty array
   - Validates `price` is a valid float

2. **Image Path Validation**
   - Verifies each image path exists on the filesystem
   - Filters out non-existent paths
   - Returns error if no valid images remain

3. **Textual Content Preparation**
   - Concatenates: `name + description + brand + category`
   - Sent to FAISS for text embedding generation

4. **FAISS Service Call**
   - Sends product data to FAISS service
   - FAISS encodes text using specified model
   - FAISS encodes each image using specified model
   - Embeddings stored in FAISS indices

5. **Response Generation**
   - Returns vector IDs for tracking
   - Includes count of processed images

## Usage Examples

### Python (requests)

```python
import requests

product = {
    "id": "prod_123",
    "name": "Wireless Headphones",
    "description": "Noise-cancelling Bluetooth headphones",
    "brand": "AudioTech",
    "category": "Electronics",
    "price": 149.99,
    "images": [
        "/home/user/products/headphones_1.jpg",
        "/home/user/products/headphones_2.jpg"
    ]
}

response = requests.post(
    "http://localhost:5000/api/retrieval/add-product",
    json=product,
    timeout=30
)

print(response.json())
```

### cURL

```bash
curl -X POST http://localhost:5000/api/retrieval/add-product \
  -H "Content-Type: application/json" \
  -d '{
    "id": "prod_123",
    "name": "Wireless Headphones",
    "description": "Noise-cancelling Bluetooth headphones",
    "brand": "AudioTech",
    "category": "Electronics",
    "price": 149.99,
    "images": [
      "/home/user/products/headphones_1.jpg",
      "/home/user/products/headphones_2.jpg"
    ]
  }'
```

### JavaScript (fetch)

```javascript
const product = {
  id: "prod_123",
  name: "Wireless Headphones",
  description: "Noise-cancelling Bluetooth headphones",
  brand: "AudioTech",
  category: "Electronics",
  price: 149.99,
  images: [
    "C:/Users/Products/headphones_1.jpg",
    "C:/Users/Products/headphones_2.jpg"
  ]
};

fetch("http://localhost:5000/api/retrieval/add-product", {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify(product)
})
  .then(res => res.json())
  .then(data => console.log(data))
  .catch(err => console.error(err));
```

## Important Notes

### Image Paths
- Must be **absolute paths** (not relative)
- Platform-specific format:
  - Windows: `C:/path/to/image.jpg` or `C:\\path\\to\\image.jpg`
  - Linux/Mac: `/home/user/path/to/image.jpg`
- Images must exist at the specified path before calling the endpoint
- Non-existent images are filtered out (logged as warnings)

### Model Names
- Default model: `"ViT-B/32"` (CLIP model)
- Must match models available in the FAISS service
- Both textual and visual can use different models

### Timeout
- Default timeout: 30 seconds
- Processing time depends on:
  - Number of images
  - Image sizes
  - Model complexity
  - FAISS service load

### FAISS Service Dependency
- Endpoint requires external FAISS service running
- Default URL: `http://localhost:5002/api/retrieval/add-product`
- Configure via `FAISS_ADD_PRODUCT_URL` environment variable

## Configuration

Set environment variables in `.env` file:

```bash
# FAISS service URL for adding products
FAISS_ADD_PRODUCT_URL=http://localhost:5002/api/retrieval/add-product

# FAISS service URL for search (existing)
FAISS_SERVICE_URL=http://localhost:5002/api/retrieval/search
```

## Error Handling

The endpoint implements comprehensive error handling:

1. **Validation Errors** (400) - Missing or invalid fields
2. **File System Errors** - Non-existent image paths logged, filtered
3. **FAISS Service Errors** (500) - Service unavailable or timeout
4. **Network Errors** - Connection failures with detailed logging

All errors are logged with timestamps and context for debugging.

## Testing

Run the included test script:

```bash
python test_add_product.py
```

This tests:
- ✅ Valid product addition
- ✅ Validation for missing fields
- ✅ Error handling

## Integration with Search

Once products are added via this endpoint:

1. Textual embeddings enable semantic text search
2. Visual embeddings enable image-based search
3. Products become searchable via `/api/search` endpoint
4. Results ranked by similarity scores from FAISS

## Performance Considerations

- **Batch Operations**: For multiple products, consider implementing a batch endpoint
- **Image Size**: Larger images take longer to process - consider resizing
- **Concurrent Requests**: FAISS service should handle concurrent indexing
- **Index Persistence**: FAISS service should periodically save indices to disk
