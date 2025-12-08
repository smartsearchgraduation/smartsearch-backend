"""
Test script for the new search endpoints.
"""
import requests
import json

BASE_URL = "http://localhost:5000"

def test_text_search():
    print("\n🔍 Testing Text Search")
    print("=" * 60)
    
    payload = {
        "text": "red leather handbag",
        "textual_model_name": "ViT-B/32",
        "top_k": 5
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/retrieval/search/text",
            json=payload,
            timeout=10
        )
        print(f"Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

def test_late_fusion_search():
    print("\n🔍 Testing Late Fusion Search")
    print("=" * 60)
    
    # Note: This requires a valid image path on the server
    payload = {
        "text": "red leather handbag",
        "textual_model_name": "ViT-B/32",
        "text_weight": 0.5,
        "image": "C:/Users/Semih/smartsearch-backend/uploads/products/test_image.jpg", # Adjust path as needed
        "visual_model_name": "ViT-B/32",
        "top_k": 5
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/retrieval/search/late",
            json=payload,
            timeout=10
        )
        print(f"Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

def test_late_fusion_missing_text():
    print("\n🔍 Testing Late Fusion (Missing Text - Should Fail)")
    print("=" * 60)
    
    payload = {
        "image": "C:/path/to/image.jpg",
        "top_k": 5
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/retrieval/search/late",
            json=payload,
            timeout=10
        )
        print(f"Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_text_search()
    test_late_fusion_search()
    test_late_fusion_missing_text()
