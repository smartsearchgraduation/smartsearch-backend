
import requests
import json
import os

BASE_URL = "http://localhost:5000"

def test_create_product_with_faiss():
    print("\n🔍 Testing Create Product (DB + FAISS)")
    print("=" * 60)
    
    # Create dummy image files
    with open("test_image1.jpg", "wb") as f:
        f.write(b"fake image content")
    with open("test_image2.jpg", "wb") as f:
        f.write(b"fake image content 2")
        
    try:
        files = [
            ('images', ('test_image1.jpg', open('test_image1.jpg', 'rb'), 'image/jpeg')),
            ('images', ('test_image2.jpg', open('test_image2.jpg', 'rb'), 'image/jpeg'))
        ]
        
        data = {
            'name': 'Integration Test Product',
            'price': '199.99',
            'brand': 'TestBrand',
            'description': 'Product created via API and synced to FAISS',
            'category_ids': '' # Assuming no categories for simplicity or valid IDs if known
        }
        
        print("Sending POST /api/products...")
        response = requests.post(
            f"{BASE_URL}/api/products",
            data=data,
            files=files,
            timeout=30
        )
        
        print(f"Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        if os.path.exists("test_image1.jpg"):
            os.remove("test_image1.jpg")
        if os.path.exists("test_image2.jpg"):
            os.remove("test_image2.jpg")

if __name__ == "__main__":
    test_create_product_with_faiss()
