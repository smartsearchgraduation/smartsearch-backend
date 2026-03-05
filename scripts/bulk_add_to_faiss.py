"""
Script to bulk add all products from database to FAISS index.
Run this script to populate FAISS with all products.

Usage:
    python bulk_add_to_faiss.py
"""
import os
import sys
import time
import requests

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from app import create_app
from models.product import Product

# ============================================
# MODEL CONFIGURATION - EDIT HERE
# ============================================
TEXTUAL_MODEL = "BAAI/bge-large-en-v1.5"  # Model for text embeddings
VISUAL_MODEL = "ViT-B/32"   # Model for image embeddings

# FAISS service URL
FAISS_ADD_PRODUCT_URL = "http://localhost:5002/api/retrieval/add-product"

# Upload folder for images
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads', 'products')
# ============================================


def add_product_to_faiss(product_data: dict) -> dict:
    """Send a product to FAISS service for indexing."""
    try:
        response = requests.post(
            FAISS_ADD_PRODUCT_URL,
            json=product_data,
            timeout=120
        )
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"status": "error", "error": "FAISS service not available at " + FAISS_ADD_PRODUCT_URL}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def main():
    print("=" * 60)
    print("🚀 FAISS Bulk Product Import")
    print("=" * 60)
    print(f"📝 Textual Model: {TEXTUAL_MODEL}")
    print(f"🖼️  Visual Model: {VISUAL_MODEL}")
    print(f"🔗 FAISS URL: {FAISS_ADD_PRODUCT_URL}")
    print("=" * 60)
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        # Get all active products
        products = Product.query.filter_by(is_active=True).all()
        
        if not products:
            print("❌ No products found in database!")
            return
        
        total = len(products)
        print(f"\n📦 Found {total} products in database\n")
        
        successful = 0
        failed = 0
        start_time = time.time()
        
        for i, product in enumerate(products, 1):
            # Get brand name
            brand_name = product.brand.name if product.brand else ""
            
            # Get first category name
            categories = list(product.categories)
            category_name = categories[0].name if categories else ""
            
            # Get image paths
            image_paths = []
            for img in product.images:
                if os.path.isabs(img.url):
                    image_path = img.url
                else:
                    image_path = os.path.join(UPLOAD_FOLDER, os.path.basename(img.url))
                
                if os.path.exists(image_path):
                    image_paths.append(image_path)
            
            # Prepare product data
            product_data = {
                "id": str(product.product_id),
                "name": product.name,
                "description": product.description or "",
                "brand": brand_name,
                "category": category_name,
                "price": float(product.price) if product.price else 0.0,
                "images": image_paths,
                "textual_model_name": TEXTUAL_MODEL,
                "visual_model_name": VISUAL_MODEL
            }
            
            # Send to FAISS
            print(f"[{i}/{total}] Adding: {product.name[:40]}...", end=" ")
            result = add_product_to_faiss(product_data)
            
            if result.get("status") == "success" or result.get("success"):
                print("✅")
                successful += 1
            else:
                print(f"❌ {result.get('error', 'Unknown error')}")
                failed += 1
        
        # Summary
        elapsed = time.time() - start_time
        print("\n" + "=" * 60)
        print("📊 SUMMARY")
        print("=" * 60)
        print(f"✅ Successful: {successful}/{total}")
        print(f"❌ Failed: {failed}/{total}")
        print(f"⏱️  Time: {elapsed:.2f} seconds")
        print("=" * 60)


if __name__ == "__main__":
    main()
