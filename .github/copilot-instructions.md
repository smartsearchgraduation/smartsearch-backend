# SmartSearch Backend - AI Coding Instructions

## Project Overview
Flask-based REST API serving as a middle layer between frontend UI and FAISS-based product retrieval. No database—uses in-memory dictionaries and JSON files for temporary storage.

## Architecture

**Service Pattern**: Thin Flask API + Service Layer
- `app.py`: Flask routes, request validation, in-memory state management
- `services/faiss_retrieval_service.py`: Search logic and FAISS integration
- `data/`: JSON files for mock products and persistent feedback/clicks

**Data Flow**:
1. Frontend → POST `/api/search` → `faiss_service.run_search()` → returns ranked products with UUIDs
2. User interactions → POST `/api/feedback` or `/api/click` → append to JSON files
3. Analytics → GET `/api/metrics` → aggregates in-memory query data + file-based events

**State Management**:
- **In-memory**: `queries` dict holds search sessions (query_id → {raw_text, results, timestamp})
- **File-based**: `data/feedback.json` and `data/clicks.json` persist user interactions
- Files loaded on startup, appended on each event

## Development Workflow

### Getting Started
```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### Running Locally
```bash
python app.py
# Server starts at http://localhost:5000
# Debug mode enabled (auto-reload on file changes)
```

### Testing Endpoints
```bash
# Search
curl -X POST http://localhost:5000/api/search -H "Content-Type: application/json" -d "{\"raw_text\": \"red smartphone\", \"corrected_text\": \"red smartphone\", \"pipeline_hint\": \"text\"}"

# Metrics
curl http://localhost:5000/api/metrics
```

## Code Conventions

### API Response Pattern
All endpoints return JSON. Success = 200 + data object. Error = 4xx/5xx + `{"error": "message"}`.

**Search endpoint** must return:
```json
{"query_id": "uuid", "results": [{"product_id": "uuid", "rank": 1, "score": 0.89, ...}]}
```

### Error Handling
Wrap route logic in `try/except`, return `jsonify({"error": str(e)})` with appropriate status code. No custom exception classes yet.

### Service Layer
`services/faiss_retrieval_service.py` handles FAISS operations. `services/search_service.py` orchestrates the search flow (correction -> FAISS -> DB fallback).

### File I/O
Use `load_json_file()` and `save_json_file()` helpers in `app.py`. Always check `os.path.exists()` before reading. Files in `data/` are auto-created by `save_json_file()`.

## Key Dependencies
- **Flask 3.0.0**: Core web framework
- **flask-cors 4.0.0**: Enable cross-origin requests for frontend
- **uuid, json, datetime**: Stdlib for ID generation, serialization, timestamps
- **faiss** (future): Not yet installed—`faiss_service.py` is currently stubbed with random mock results

## Common Tasks

### Adding a New Endpoint
1. Define route in `app.py` with `@app.route('/api/<name>', methods=['POST'])`
2. Extract JSON: `data = request.get_json()`
3. Validate required fields, return 400 if missing
4. If search-related, call `services/faiss_service.py`; if event-related, append to `feedbacks` or `clicks` list
5. Return `jsonify({...})` with 200 or error status

### Integrating Real FAISS
1. `pip install faiss-cpu sentence-transformers`
2. In `faiss_service.py`, replace `run_search()` body:
   - Load FAISS index (one-time on import)
   - Encode `query_text` to vector using sentence transformer
   - Call `index.search(query_vector, k=10)`
   - Map FAISS IDs to product IDs from `data/mock_products.json`
3. Keep return format: list of `{"product_id", "rank", "score", "explain"}` dicts

### Debugging Search Results
Check `queries` dict in `app.py` (in-memory). Each query_id maps to full search context. Use `/api/metrics` to verify query count. For FAISS debugging, add print statements in `faiss_service.py`—output shows in Flask console.

---
**Note**: Pipeline hints ("text", "multimodal", "hybrid") affect mock `explain` structure but don't change search logic yet. Real FAISS integration should route to different indexes or encoders based on hint.
