"""
Test script for the /api/retrieval/add-product endpoint.
Demonstrates how to add products to FAISS indices.
"""
import requests
import json

# Base URL
BASE_URL = "http://localhost:5000"

def test_add_product():
    """Test adding a product to FAISS."""
    
    # Example product data
    product_data = {
        "id": "1",
        "name": "Premium Leather Handbag",
        "description": "Elegant handcrafted leather bag",
        "brand": "LuxuryBrand",
        "category": "Accessories",
        "price": 299.99,
        "images": [
            "C:/Users/Semih/smartsearch-backend/uploads/products/4_1d8beed55b41491799dcef984be6f69b.webp",
            "C:/Users/Semih/smartsearch-backend/uploads/products/5_ca5004c12cfe45328af37c83e7cd0add.webp"
        ],
        "textual_model_name": "ViT-B/32",
        "visual_model_name": "ViT-B/32",
        "fused_model_name": "ViT-B/32"
    }
    
    print("🔍 Testing FAISS Add Product Endpoint")
    print("=" * 60)
    print(f"\n📤 Request:")
    print(f"POST {BASE_URL}/api/retrieval/add-product")
    print(f"\nPayload:")
    print(json.dumps(product_data, indent=2))
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/retrieval/add-product",
            json=product_data,
            timeout=30
        )
        
        print(f"\n📥 Response:")
        print(f"Status Code: {response.status_code}")
        print(f"\nBody:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                print("\n✅ Product successfully added to FAISS!")
                details = result.get('details', {})
                print(f"   Product ID: {details.get('product_id')}")
                print(f"   Textual Vector ID: {details.get('textual_vector_id')}")
                print(f"   Visual Vector IDs: {details.get('visual_vector_ids')}")
                print(f"   Images Processed: {details.get('images_processed')}")
            else:
                print(f"\n❌ Error: {result.get('error')}")
        else:
            print(f"\n❌ Request failed with status {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to backend server.")
        print("   Make sure the server is running at http://localhost:5000")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")


def test_add_product_missing_field():
    """Test validation by omitting required field."""
    
    product_data = {
        "id": "product_002",
        # Missing "name" field
        "description": "Test product",
        "brand": "TestBrand",
        "category": "Test",
        "price": 99.99,
        "images": ["C:/test.jpg"]
    }
    
    print("\n\n🔍 Testing Validation (Missing Name)")
    print("=" * 60)
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/retrieval/add-product",
            json=product_data,
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response:")
        print(json.dumps(response.json(), indent=2))
        
        if response.status_code == 400:
            print("\n✅ Validation working correctly - rejected invalid request")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  FAISS Add Product Endpoint Test Suite")
    print("="*60 + "\n")
    
    # Test 1: Valid product
    test_add_product()
    
    # Test 2: Validation
    test_add_product_missing_field()
    
    print("\n" + "="*60)
    print("  Tests Complete")
    print("="*60 + "\n")
