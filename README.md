# SmartSearch Backend

Minimal Flask backend that acts as a middle layer between a frontend UI and a FAISS-based retrieval pipeline.

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
Search for products using FAISS retrieval.

**Request:**
```json
{
  "raw_text": "red smartphone under 500",
  "corrected_text": "red smartphone under $500",
  "pipeline_hint": "text"
}
```

**Response:**
```json
{
  "query_id": "uuid",
  "results": [
    {
      "product_id": "uuid",
      "rank": 1,
      "score": 0.89,
      "pipeline": "text",
      "explain": {"reason": "semantic match", "similarity": 0.89}
    }
  ]
}
```

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

### 4. GET /api/metrics
Get usage statistics.

**Response:**
```json
{
  "total_queries": 4,
  "total_feedbacks": 12,
  "total_clicks": 8,
  "avg_results_per_query": 10
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
├── services/
│   └── faiss_service.py        # FAISS search logic (currently mocked)
├── data/
│   ├── mock_products.json      # Mock product data
│   ├── feedback.json           # Stored feedback (created at runtime)
│   └── clicks.json             # Stored clicks (created at runtime)
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## 🧪 Testing with cURL

```bash
# Search
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"raw_text": "red smartphone", "corrected_text": "red smartphone", "pipeline_hint": "text"}'

# Feedback
curl -X POST http://localhost:5000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{"query_id": "YOUR_QUERY_ID", "product_id": "YOUR_PRODUCT_ID", "is_ok": true}'

# Click
curl -X POST http://localhost:5000/api/click \
  -H "Content-Type: application/json" \
  -d '{"query_id": "YOUR_QUERY_ID", "product_id": "YOUR_PRODUCT_ID"}'

# Metrics
curl http://localhost:5000/api/metrics

# Health
curl http://localhost:5000/health
```

## 🔮 Future Integration

The `services/faiss_service.py` is currently stubbed with mock data. To integrate real FAISS:

1. Install FAISS: `pip install faiss-cpu` (or `faiss-gpu`)
2. Build or load a FAISS index
3. Update `run_search()` to use actual vector search
4. Add sentence transformers for query encoding

Example integration points are documented in `services/faiss_service.py`.

## 📊 Data Storage

- **In-memory**: Query data stored in Python dictionaries during runtime
- **File-based**: Feedback and clicks persisted to JSON files in `data/` directory
- **No database required**: Simple JSON files for temporary storage

## 🛠️ Development

```bash
# Run in debug mode (auto-reload enabled)
python app.py

# The server runs on http://0.0.0.0:5000 by default
```

## 📝 Notes

- CORS is enabled for frontend integration
- All timestamps use ISO 8601 format
- UUIDs are generated for query and product IDs
- Pipeline hints: "text", "multimodal", or "hybrid"
