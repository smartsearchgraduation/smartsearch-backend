
import requests
import json

BASE_URL = "http://localhost:5000"

def test_text_search():
    print("\n🔍 Testing Text Search")
    print("=" * 60)
    
    payload = {
        "text": "leather bag",
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
    
    # Use one of the images we added
    image_path = "C:/Users/Semih/smartsearch-backend/uploads/products/4_1d8beed55b41491799dcef984be6f69b.webp"
    
    payload = {
        "text": "leather bag",
        "image": image_path,
        "text_weight": 0.5,
        "textual_model_name": "ViT-B/32",
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

if __name__ == "__main__":
    test_text_search()
    test_late_fusion_search()
