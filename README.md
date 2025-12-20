# 🔍 SmartSearch Backend

Flask-based REST API serving as a middle layer between frontend UI and FAISS-based product retrieval pipeline. Uses PostgreSQL for data persistence with SQLAlchemy ORM.

---

## 📋 Table of Contents

- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Database Schema](#-database-schema)
- [Getting Started](#-getting-started)
- [Configuration](#-configuration)
- [API Reference](#-api-reference)
  - [Search](#search)
  - [Products](#products)
  - [Brands](#brands)
  - [Categories](#categories)
  - [Feedback & Analytics](#feedback--analytics)
  - [Health](#health)
- [Services](#-services)
- [Project Structure](#-project-structure)

---

## 🏗 Architecture

```
┌──────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│   Frontend   │────▶│  SmartSearch API    │────▶│    PostgreSQL    │
│    (React)   │◀────│   (Flask + ORM)     │◀────│                  │
└──────────────┘     └─────────────────────┘     └──────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
           ┌────────────────┐   ┌────────────────┐
           │ Text Corrector │   │  FAISS Service │
           │   (Port 5001)  │   │   (Port 5002)  │
           └────────────────┘   └────────────────┘
```

### Search Flow

1. **Frontend** → `POST /api/search` with `raw_text`
2. **Text Corrector** → Typo correction (`raw_text` → `corrected_text`)
3. **FAISS Service** → Vector similarity search → ranked `product_ids`
4. If FAISS fails → **Fallback to DB** (`ILIKE` search)
5. Insert `search_query` + `retrieve` records
6. Return `search_id` to frontend
7. **Frontend** → `GET /api/search/{id}` for full results with product details

---

## 🛠 Tech Stack

| Component | Technology |
|-----------|------------|
| **Framework** | Flask 3.0.0 |
| **ORM** | Flask-SQLAlchemy 3.1.1 |
| **Database** | PostgreSQL (psycopg2-binary) |
| **CORS** | flask-cors 4.0.0 |
| **HTTP Client** | requests 2.31.0 |
| **Config** | python-dotenv 1.0.0 |

---

## 🗄 Database Schema

### Entity Relationship Diagram

```
┌─────────────┐       ┌──────────────┐       ┌─────────────────┐
│   brand     │       │   product    │       │  product_image  │
├─────────────┤       ├──────────────┤       ├─────────────────┤
│ brand_id PK │◀──┐   │ product_id PK│◀──────│ image_no PK     │
│ name        │   └───│ brand_id FK  │       │ product_id FK   │
└─────────────┘       │ name         │       │ url             │
                      │ description  │       │ uploaded_at     │
                      │ price        │       └─────────────────┘
                      │ is_active    │
                      │ created_at   │
                      │ updated_at   │
                      └──────┬───────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
┌──────────────────┐  ┌──────────────────┐  ┌─────────────┐
│ product_category │  │    retrieve      │  │  category   │
├──────────────────┤  ├──────────────────┤  ├─────────────┤
│ product_id PK,FK │  │ search_id PK,FK  │  │category_id  │
│ category_id PK,FK│  │ product_id PK,FK │  │parent_cat_id│
└──────────────────┘  │ rank             │  │ name        │
                      │ weight (score)   │  └─────────────┘
                      │ explain          │        ▲
                      │ is_relevant      │        │ self-ref
                      │ is_clicked       │        └────────
                      │ embedding_id     │
                      └────────┬─────────┘
                               │
                               ▼
                      ┌──────────────────┐
                      │  search_query    │
                      ├──────────────────┤
                      │ search_id PK     │
                      │ raw_text         │
                      │ corrected_text   │
                      │ type             │
                      │ time_to_retrieve │
                      │ timestamp        │
                      └──────────────────┘
```

### Tables

#### `brand`
| Column | Type | Description |
|--------|------|-------------|
| `brand_id` | BIGINT PK | Auto-increment ID |
| `name` | VARCHAR(255) | Brand name |

#### `category`
| Column | Type | Description |
|--------|------|-------------|
| `category_id` | BIGINT PK | Auto-increment ID |
| `parent_category_id` | BIGINT FK NULL | Self-reference for hierarchy |
| `name` | VARCHAR(255) | Category name |

#### `product`
| Column | Type | Description |
|--------|------|-------------|
| `product_id` | BIGINT PK | Auto-increment ID |
| `brand_id` | BIGINT FK NULL | Reference to brand |
| `name` | VARCHAR(255) | Product name |
| `description` | TEXT NULL | Product description |
| `price` | NUMERIC(12,2) | Product price |
| `is_active` | BOOLEAN | Soft delete flag |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Last update time |

#### `product_image`
| Column | Type | Description |
|--------|------|-------------|
| `image_no` | BIGINT PK | Auto-increment, defines display order |
| `product_id` | BIGINT FK | Reference to product |
| `url` | TEXT | Image URL or local path |
| `uploaded_at` | TIMESTAMP | Upload time |

#### `product_category`
| Column | Type | Description |
|--------|------|-------------|
| `product_id` | BIGINT PK,FK | Reference to product |
| `category_id` | BIGINT PK,FK | Reference to category |

#### `search_query`
| Column | Type | Description |
|--------|------|-------------|
| `search_id` | BIGINT PK | Auto-increment ID |
| `raw_text` | TEXT | Original search query |
| `corrected_text` | TEXT NULL | Typo-corrected query |
| `type` | VARCHAR(50) NULL | Query type: text, voice, image |
| `time_to_retrieve` | INT NULL | Retrieval time in ms |
| `timestamp` | TIMESTAMP | Query time |

#### `retrieve`
| Column | Type | Description |
|--------|------|-------------|
| `search_id` | BIGINT PK,FK | Reference to search_query |
| `product_id` | BIGINT PK,FK | Reference to product |
| `rank` | INT | Result ranking (1 = best) |
| `weight` | FLOAT NULL | Similarity score |
| `explain` | TEXT NULL | Explanation JSON |
| `is_relevant` | BOOLEAN NULL | User feedback (thumbs up/down) |
| `is_clicked` | BOOLEAN NULL | Click tracking |
| `embedding_id` | VARCHAR(100) NULL | FAISS embedding reference |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL 13+
- (Optional) Text Corrector service on port 5001
- (Optional) FAISS service on port 5002

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/smartsearch-backend.git
cd smartsearch-backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Database Setup

```sql
-- Create database
CREATE DATABASE smartsearch;

-- Connect and create tables (or use Flask migrations)
-- Tables are defined in models/ directory
```

### Run the Server

**⚠️ IMPORTANT: Always activate the virtual environment before running the server!**

```bash
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

#### Development Mode
```bash
# Development mode with auto-reload
python app.py

# Or with Flask CLI
flask run --host=0.0.0.0 --port=5000 --debug
```

#### Production Mode (Waitress)
For production use, run with Waitress:
```bash
python run_waitress.py
```

Server starts at `http://localhost:5000`

---

## ⚙ Configuration

Create a `.env` file in the project root:

```env
# Flask
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=your-super-secret-key-change-in-production

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=smartsearch
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password

# External Services
CORRECTION_SERVICE_URL=http://localhost:5001/api/correct
FAISS_SERVICE_URL=http://localhost:5002/api/retrieval/search

# SQLAlchemy
SQLALCHEMY_ECHO=False
```

### Configuration Classes

| Environment | Class | Features |
|-------------|-------|----------|
| `development` | `DevelopmentConfig` | DEBUG=True, SQL logging enabled |
| `production` | `ProductionConfig` | DEBUG=False, SQL logging disabled |
| `testing` | `TestingConfig` | SQLite in-memory |

---

## 📚 API Reference

Base URL: `http://localhost:5000`

### Search

#### `POST /api/search`

Execute a search query.

**Request:**
```json
{
  "raw_text": "iphone 15 pro"
}
```

**Response (201):**
```json
{
  "search_id": 123
}
```

**Flow:**
1. Calls Text Corrector service
2. Calls FAISS service (or falls back to DB)
3. Records query and results
4. Returns only `search_id`

---

#### `GET /api/search/{search_id}`

Get search results with full product details.

**Response (200):**
```json
{
  "search_id": 123,
  "corrected_text": "iphone 15 pro",
  "results": [
    {
      "product_id": 456,
      "name": "iPhone 15 Pro",
      "price": 54999.90,
      "rank": 1,
      "score": 0.98,
      "brand": "Apple",
      "image_url": "https://cdn.example.com/iphone15.jpg",
      "categories": ["Elektronik", "Akıllı Telefon"]
    }
  ]
}
```

---

### Products

#### `GET /api/products`

List products with filters and pagination.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `category_id` | int | Filter by category |
| `brand_id` | int | Filter by brand |
| `min_price` | float | Minimum price |
| `max_price` | float | Maximum price |
| `is_active` | bool | Filter by active status |
| `page` | int | Page number (default: 1) |
| `per_page` | int | Items per page (default: 20) |

**Response (200):**
```json
{
  "products": [...],
  "total": 150,
  "page": 1,
  "per_page": 20,
  "pages": 8
}
```

---

#### `GET /api/products/{product_id}`

Get a single product with all details.

**Response (200):**
```json
{
  "product_id": 1,
  "name": "iPhone 15 Pro",
  "description": "128 GB, Blue Titanium",
  "price": 54999.90,
  "is_active": true,
  "brand": {
    "brand_id": 1,
    "name": "Apple"
  },
  "categories": [
    {"category_id": 1, "name": "Elektronik"},
    {"category_id": 7, "name": "Akıllı Telefon"}
  ],
  "images": [
    {"image_no": 1, "product_id": 1, "url": "/uploads/products/1_abc.jpg", "uploaded_at": "2024-01-15T10:30:00"},
    {"image_no": 2, "product_id": 1, "url": "/uploads/products/1_def.jpg", "uploaded_at": "2024-01-15T10:31:00"},
    {"image_no": 3, "product_id": 1, "url": "/uploads/products/1_ghi.jpg", "uploaded_at": "2024-01-15T10:32:00"}
  ],
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:30:00"
}
```

---

#### `POST /api/products`

Create a new product with brand, categories, and images.

**Images can be sent as:**
- **Base64 encoded** (recommended for frontend uploads): `"data:image/jpeg;base64,/9j/4AAQSkZJRg..."`
- **Raw base64** (without data URI prefix)
- **URL** (stored as-is, not downloaded): `"https://example.com/image.jpg"`

**Request with Base64 Images:**
```json
{
  "name": "iPhone 15 Pro",
  "description": "128 GB, Blue Titanium",
  "price": 54999.90,
  "brand": "Apple",
  "category_ids": [1, 7],
  "images": [
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD...",
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUA..."
  ]
}

```

**Required Fields:** `name`, `price`, `brand`, `images` (non-empty array)

**Response (201):**
```json
{
  "product_id": 1,
  "name": "iPhone 15 Pro",
  "brand": "Apple",
  "category_ids": [1, 7],
  "images": [
    "/uploads/products/1_a8b3c4d5.jpg",
    "/uploads/products/1_e6f7g8h9.png"
  ]
}
```

**Notes:**
- Brand is created if it doesn't exist
- All operations are in a single transaction
- Images are stored in order (first = primary)
- Base64 images are decoded and saved to `uploads/products/`
- Supported formats: PNG, JPG, JPEG, GIF, WebP
- Max request size: 16MB (configurable)

---

#### `PUT /api/products/{product_id}`

Update an existing product.

**Request (partial update):**
```json
{
  "name": "iPhone 15 Pro Max",
  "price": 64999.90,
  "category_ids": [1, 7, 8]
}
```

---

#### `DELETE /api/products/{product_id}`

Delete a product (cascades to images and category links).

---

#### `POST /api/products/{product_id}/images`

Upload an image file.

**Request:** `multipart/form-data` with `file` field

**Allowed formats:** PNG, JPG, JPEG, GIF, WebP

**Max size:** 16 MB

**Response (201):**
```json
{
  "image_no": 5,
  "product_id": 1,
  "url": "/uploads/products/1_abc123.jpg",
  "filename": "1_abc123.jpg",
  "original_filename": "photo.jpg"
}
```

---

#### `GET /api/products/{product_id}/images`

List all images for a product.

---

#### `DELETE /api/products/{product_id}/images/{image_no}`

Delete a specific image (removes file from disk).

---

### Brands

#### `GET /api/brands`

List all brands.

```json
{
  "brands": [
    {"brand_id": 1, "name": "Apple"},
    {"brand_id": 2, "name": "Samsung"}
  ],
  "total": 2
}
```

---

#### `POST /api/brands`

Create a new brand.

```json
{"name": "Xiaomi"}
```

---

#### `GET /api/brands/{brand_id}`
#### `PUT /api/brands/{brand_id}`
#### `DELETE /api/brands/{brand_id}`

Standard CRUD operations.

---

### Categories

#### `GET /api/categories`

List categories.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `parent_id` | int | Filter by parent (0 or null for root) |
| `tree` | bool | Return hierarchical structure |

**Tree Response:**
```json
{
  "categories": [
    {
      "category_id": 1,
      "name": "Elektronik",
      "parent_category_id": null,
      "children": [
        {"category_id": 7, "name": "Akıllı Telefon", "children": []}
      ]
    }
  ],
  "total": 15
}
```

---

#### `POST /api/categories`

Create a new category.

```json
{
  "name": "Tablet",
  "parent_category_id": 1
}
```

---

### Feedback & Analytics

#### `POST /api/feedback`

Submit relevance feedback (thumbs up/down).

**Request:**
```json
{
  "query_id": 123,
  "product_id": 456,
  "is_ok": true
}
```

---

#### `POST /api/click`

Track product click.

**Request:**
```json
{
  "query_id": 123,
  "product_id": 456
}
```

---

#### `GET /api/metrics`

Get analytics metrics.

**Response:**
```json
{
  "total_searches": 1500,
  "total_clicks": 450,
  "total_feedback": 120,
  "positive_feedback": 98,
  "negative_feedback": 22,
  "click_through_rate": 0.3,
  "avg_retrieval_time_ms": 145.5
}
```

---

### Health

#### `GET /health`

Health check endpoint.

**Response (200):**
```json
{
  "status": "healthy",
  "service": "smartsearch-backend",
  "database": "healthy",
  "timestamp": "2024-01-15T10:30:00"
}
```

**Response (503):** Database connection failed

---

## 🔧 Services

### SearchService (`services/search_service.py`)

Orchestrates the full search flow:

1. **Text Correction** → Calls external Text Corrector service
2. **FAISS Retrieval** → Calls external FAISS service
3. **DB Fallback** → `ILIKE` search if FAISS unavailable
4. **Logging** → Records search queries and results

### External Services (`services/external_services.py`)

HTTP client for Text Corrector microservice:

| Client | Service | Endpoint |
|--------|---------|----------|
| `TextCorrectorClient` | Typo correction | `POST /api/correct` |

Gracefully handles connection failures and returns fallback responses.

### FAISS Retrieval Service (`services/faiss_retrieval_service.py`)

Unified service for all FAISS operations:

| Method | Description |
|--------|-------------|
| `search()` | Basic search with query text |
| `search_text()` | Text-only search |
| `search_late_fusion()` | Text + image fusion search |
| `add_product()` | Add product to FAISS indices |

### ProductService (`services/product_service.py`)

Business logic layer for product operations:

- CRUD operations
- Filtering and pagination
- Image management
- Text search (fallback)

---

## 📁 Project Structure

```
smartsearch-backend/
├── app.py                 # Application factory & entry point
├── config.py              # Configuration classes
├── requirements.txt       # Python dependencies
├── README.md              # This file
│
├── models/                # SQLAlchemy ORM models
│   ├── __init__.py        # db instance & model exports
│   ├── brand.py           # Brand model
│   ├── category.py        # Category model (self-referencing)
│   ├── product.py         # Product model
│   ├── product_image.py   # ProductImage model
│   ├── product_category.py# M2M association table
│   ├── search_query.py    # SearchQuery model
│   └── retrieve.py        # Retrieve model (search results)
│
├── routes/                # Flask blueprints
│   ├── __init__.py        # Blueprint exports
│   ├── search.py          # /api/search endpoints
│   ├── products.py        # /api/products endpoints
│   ├── brands.py          # /api/brands endpoints
│   ├── categories.py      # /api/categories endpoints
│   ├── feedback.py        # /api/feedback, /api/click, /api/metrics
│   └── health.py          # /health endpoint
│
├── services/              # Business logic layer
│   ├── __init__.py
│   ├── search_service.py  # Search orchestration
│   ├── external_services.py # Text Corrector client
│   ├── faiss_retrieval_service.py # FAISS search & indexing
│   └── product_service.py # Product business logic
│
└── uploads/               # Uploaded files
    └── products/          # Product images
```

---

## 🧪 Testing

```bash
# Test endpoints manually
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"raw_text": "iphone"}'

curl http://localhost:5000/api/products

curl http://localhost:5000/health
```

---

## 📝 License

MIT License - See LICENSE file for details.

---
