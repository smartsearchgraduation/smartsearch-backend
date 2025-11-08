"""
Test script to demonstrate the search endpoint with product enrichment
NOTE: FAISS API integration is pending - currently returns empty results
"""
import requests
import json

# Test search endpoint
print("🔍 Testing /api/search endpoint...\n")
print("⚠️  Note: FAISS API not integrated yet - expecting empty product list\n")

search_data = {
    "raw_text": "red smartphone under 500",
    "pipeline_hint": "text"
}

response = requests.post('http://localhost:5000/api/search', json=search_data)

if response.status_code == 200:
    result = response.json()
    print(f"✅ Query ID: {result['query_id']}")
    print(f"📝 Corrected Text: {result.get('corrected_text', 'N/A')}\n")
    
    products = result.get('products', [])
    print(f"📦 Found {len(products)} products (FAISS ranking order)")
    
    if len(products) == 0:
        print("   (Empty - waiting for FAISS API integration)")
    else:
        print()
        for i, p in enumerate(products[:3], 1):  # Show first 3 products
            name = p.get('name', '<no name>')
            price = p.get('price')
            category = p.get('category')
            color = p.get('color')
            pid = p.get('product_id')
            print(f"{i}. {name}")
            if price is not None:
                print(f"   Price: ${price}")
            if category:
                print(f"   Category: {category}")
            if color:
                print(f"   Color: {color}")
            print(f"   Product ID: {pid}")
            print()
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text)
