"""
SmartSearch Backend - Flask API
Minimal middle layer between frontend UI and FAISS-based retrieval pipeline.
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import uuid
import json
import os
import random

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend requests

# In-memory storage for runtime testing
queries = {}  # {query_id: {raw_text, corrected_text, timestamp, results}}
feedbacks = []  # [{query_id, product_id, is_ok, timestamp}]
clicks = []  # [{query_id, product_id, timestamp}]

# File paths for persistent storage
DATA_DIR = "data"
FEEDBACK_FILE = os.path.join(DATA_DIR, "feedback.json")
CLICKS_FILE = os.path.join(DATA_DIR, "clicks.json")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)


def load_json_file(filepath):
    """Load JSON file if it exists, otherwise return empty list."""
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return []


def save_json_file(filepath, data):
    """Save data to JSON file."""
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


# Load existing data on startup
feedbacks = load_json_file(FEEDBACK_FILE)
clicks = load_json_file(CLICKS_FILE)


@app.route('/api/search', methods=['POST'])
def search():
    """
    Handle search query from frontend.
    
    Request body:
    {
        "raw_text": "red smartphone under 500",
        "pipeline_hint": "text|multimodal"  (optional, defaults to "text")
    }
    
    Response:
    {
        "query_id": "uuid",
        "corrected_text": "red smartphone under $500",  // from FAISS
        "products": [
            {
                "product_id": "prod-001",
                "name": "Red Smartphone X Pro",
                "price": 499.99,
                "category": "Electronics",
                "description": "...",
                "color": "red",
                "brand": "TechCorp",
                "in_stock": true
            },
            ...
        ]
    }
    
    Note: Products are returned in FAISS ranking order (sorted by relevance score).
    """
    try:
        data = request.get_json()

        # Validate request
        if not data or 'raw_text' not in data:
            return jsonify({"error": "Missing 'raw_text' in request body"}), 400

        # Extract query parameters (frontend only sends raw_text)
        raw_text = data.get('raw_text', '')
        pipeline_hint = data.get('pipeline_hint', 'text')
        
        # Generate unique query ID
        query_id = str(uuid.uuid4())
        
        # Load products data
        products_file = os.path.join(DATA_DIR, "mock_products.json")
        all_products = load_json_file(products_file)
        
        # Create product lookup dictionary
        products_dict = {p['product_id']: p for p in all_products}

        # TODO: Call external FAISS service API
        # Example:
        # response = requests.post(FAISS_API_URL, json={"query": raw_text, "pipeline": pipeline_hint})
        # faiss_response = response.json()
        
        # PLACEHOLDER: Mock FAISS response until external API is ready
        # Expected format: {"corrected_text": str, "results": [{"product_id": str, "rank": int, "score": float, ...}]}
        faiss_response = {
            "corrected_text": raw_text,  # FAISS will return corrected query
            "results": []  # FAISS will return ranked product IDs
        }
        
        corrected_text = faiss_response.get('corrected_text', raw_text)
        faiss_results = faiss_response.get('results', [])        # Enrich results with full product details and build product list to send to frontend
        enriched_results = []
        products_to_send = []
        for result in faiss_results:
            product_id = result['product_id']
            # Find product details
            product_details = products_dict.get(product_id)

            # Build enriched result (keeps FAISS metadata for internal use)
            enriched_result = {
                **result,  # rank, score, pipeline, explain
                'product': product_details if product_details else None
            }
            enriched_results.append(enriched_result)

            # Build product payload for frontend: just product fields, no search_meta yet
            # TODO: Add search_meta when saving to database (rank, score, pipeline, explain)
            if product_details:
                product_payload = dict(product_details)  # shallow copy
            else:
                # If product not found in local catalog, send minimal payload
                product_payload = {
                    'product_id': product_id
                }

            products_to_send.append(product_payload)

        # Store query in memory
        queries[query_id] = {
            'query_id': query_id,
            'raw_text': raw_text,
            'corrected_text': corrected_text,
            'pipeline_hint': pipeline_hint,
            'timestamp': datetime.now().isoformat(),
            'results': enriched_results,
            'products_sent': products_to_send
        }

        # Return results to frontend
        return jsonify({
            'query_id': query_id,
            'corrected_text': corrected_text,  # corrected text from FAISS
            'products': products_to_send        # enriched product list
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/feedback', methods=['POST'])
def feedback():
    """
    Receive thumbs up/down feedback from frontend.
    
    Request body:
    {
        "query_id": "uuid",
        "product_id": "uuid",
        "is_ok": true
    }
    
    Response:
    {
        "ok": true
    }
    """
    try:
        data = request.get_json()
        
        # Validate request
        if not data or 'query_id' not in data or 'product_id' not in data or 'is_ok' not in data:
            return jsonify({"error": "Missing required fields: query_id, product_id, is_ok"}), 400
        
        # Create feedback record
        feedback_record = {
            'query_id': data['query_id'],
            'product_id': data['product_id'],
            'is_ok': data['is_ok'],
            'timestamp': datetime.now().isoformat()
        }
        
        # Store in memory and file
        feedbacks.append(feedback_record)
        save_json_file(FEEDBACK_FILE, feedbacks)
        
        return jsonify({"ok": True}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/click', methods=['POST'])
def click():
    """
    Mark that a product was clicked.
    
    Request body:
    {
        "query_id": "uuid",
        "product_id": "uuid"
    }
    
    Response:
    {
        "ok": true
    }
    """
    try:
        data = request.get_json()
        
        # Validate request
        if not data or 'query_id' not in data or 'product_id' not in data:
            return jsonify({"error": "Missing required fields: query_id, product_id"}), 400
        
        # Create click record
        click_record = {
            'query_id': data['query_id'],
            'product_id': data['product_id'],
            'timestamp': datetime.now().isoformat()
        }
        
        # Store in memory and file
        clicks.append(click_record)
        save_json_file(CLICKS_FILE, clicks)
        
        return jsonify({"ok": True}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/products', methods=['GET'])
def get_products():
    """
    bunu dumenden koydum
    
    Query parameters (optional):
        category: Filter by category
        color: Filter by color
        min_price: Minimum price
        max_price: Maximum price
        in_stock: Filter by stock status (true/false)
    
    Response:
    {
        "products": [...],
        "total": 10
    }
    """
    try:
        # Load products from JSON file
        products_file = os.path.join(DATA_DIR, "mock_products.json")
        products = load_json_file(products_file)
        
        # Apply filters if provided
        category = request.args.get('category')
        color = request.args.get('color')
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        in_stock = request.args.get('in_stock')
        
        filtered_products = products
        
        if category:
            filtered_products = [p for p in filtered_products if p.get('category', '').lower() == category.lower()]
        
        if color:
            filtered_products = [p for p in filtered_products if p.get('color', '').lower() == color.lower()]
        
        if min_price is not None:
            filtered_products = [p for p in filtered_products if p.get('price', 0) >= min_price]
        
        if max_price is not None:
            filtered_products = [p for p in filtered_products if p.get('price', 0) <= max_price]
        
        if in_stock is not None:
            in_stock_bool = in_stock.lower() == 'true'
            filtered_products = [p for p in filtered_products if p.get('in_stock', False) == in_stock_bool]
        
        return jsonify({
            'products': filtered_products,
            'total': len(filtered_products)
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'smartsearch-backend',
        'timestamp': datetime.now().isoformat()
    }), 200


if __name__ == '__main__':
    print("🚀 Starting SmartSearch Backend...")
    print("📍 Available endpoints:")
    print("   POST   /api/search")
    print("   POST   /api/feedback")
    print("   POST   /api/click")
    print("   GET    /api/products")
    print("   GET    /api/metrics")
    print("   GET    /health")
    app.run(debug=True, host='0.0.0.0', port=5000)
