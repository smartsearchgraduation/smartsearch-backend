# SmartSearch Backend

Minimal Flask backend that acts as a middle layer between frontend UI and external FAISS-based retrieval service.

**Key Responsibilities:**
- Receive search queries from frontend (`raw_text`)
- Forward to external FAISS service (returns `corrected_text` + ranked `product_ids`)
- Enrich product IDs with full details from catalog
- Return enriched products to frontend



## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- pip

### Installation

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Server

```bash
python app.py
```

Server will start on `http://localhost:5000`

## 📡 API Endpoints

### 1. POST /api/search
Search for products via external FAISS service.

**Request:**
```json
{
  "raw_text": "red smartphone under 500",
  "pipeline_hint": "text"  // optional: "text" | "multimodal" | "hybrid"
}
```

**Response:**
```json
{
  "query_id": "uuid",
  "corrected_text": "red smartphone under $500",  // from FAISS
  "products": [
    {
      "product_id": "prod-001",
      "name": "Red Smartphone X Pro",
      "price": 499.99,
      "category": "Electronics",
      "description": "High-performance smartphone...",
      "color": "red",
      "brand": "TechCorp",
      "in_stock": true
    }
  ]
}
```

**Note:** Products are returned in FAISS ranking order. FAISS API integration is pending.

### 2. POST /api/feedback
Submit user feedback on search results.

**Request:**
```json
{
  "query_id": "uuid",
  "product_id": "uuid",
  "is_ok": true
}
```

**Response:**
```json
{
  "ok": true
}
```

### 3. POST /api/click
Track product clicks.

**Request:**
```json
{
  "query_id": "uuid",
  "product_id": "uuid"
}
```

**Response:**
```json
{
  "ok": true
}
```


### 5. GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "smartsearch-backend",
  "timestamp": "2025-11-09T20:30:00"
}
```

## 📁 Project Structure

```
smartsearch-backend/
├── app.py                      # Flask application with API endpoints
├── data/
│   ├── mock_products.json      # Mock product catalog
│   ├── feedback.json           # User feedback (created at runtime)
│   └── clicks.json             # Click tracking (created at runtime)
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```


## 🧪 Testing with cURL

```bash
# Search
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"raw_text": "red smartphone", "pipeline_hint": "text"}'

# Feedback
curl -X POST http://localhost:5000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{"query_id": "YOUR_QUERY_ID", "product_id": "YOUR_PRODUCT_ID", "is_ok": true}'

# Click
curl -X POST http://localhost:5000/api/click \
  -H "Content-Type: application/json" \
  -d '{"query_id": "YOUR_QUERY_ID", "product_id": "YOUR_PRODUCT_ID"}'

# Products
curl http://localhost:5000/api/products

# Metrics
curl http://localhost:5000/api/metrics

# Health
curl http://localhost:5000/health
```


## 🛠️ Development

```bash
# Run in debug mode (auto-reload enabled)
python app.py

# The server runs on http://0.0.0.0:5000 by default
```

