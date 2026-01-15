"""
One-time import script for loading products from 'New folder'.
This script:
1. Reads product data from JSON files
2. Resizes images to smaller dimensions (frontend normally does this)
3. Saves resized images to uploads/products folder
4. Adds products to the database
5. Indexes products in FAISS for search

Usage:
    python import_products.py
"""
import os
import sys
import json
import uuid
from PIL import Image
from io import BytesIO

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, Product, ProductImage, Brand, Category
from services.faiss_retrieval_service import faiss_service


# Configuration
MAX_IMAGE_SIZE = 800  # Max width or height in pixels
IMAGE_QUALITY = 85    # JPEG quality (1-100)
NEW_FOLDER_PATH = os.path.join(os.path.dirname(__file__), 'New folder')

# Map category names to category IDs (you may need to adjust these based on your DB)
CATEGORY_MAP = {
    'Telephone': 'Telephone',
    'Laptop': 'Laptop', 
    'Desktop': 'Desktop',
    'Tablet': 'Tablet'
}


def resize_image(input_path: str, max_size: int = MAX_IMAGE_SIZE) -> BytesIO:
    """
    Resize an image to fit within max_size while maintaining aspect ratio.
    
    Args:
        input_path: Path to the input image
        max_size: Maximum width or height in pixels
        
    Returns:
        BytesIO object containing the resized image
    """
    with Image.open(input_path) as img:
        # Convert to RGB if necessary (for RGBA images, etc.)
        if img.mode in ('RGBA', 'P'):
            # Create a white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Calculate new dimensions
        width, height = img.size
        if width > max_size or height > max_size:
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            
            img = img.resize((new_width, new_height), Image.LANCZOS)
        
        # Save to BytesIO
        output = BytesIO()
        img.save(output, format='JPEG', quality=IMAGE_QUALITY, optimize=True)
        output.seek(0)
        
        return output


def save_resized_image(image_data: BytesIO, product_id: int, upload_folder: str) -> str:
    """
    Save a resized image to disk.
    
    Args:
        image_data: BytesIO object containing the image
        product_id: Product ID for filename prefix
        upload_folder: Target folder for uploads
        
    Returns:
        Relative URL path to the saved image
    """
    os.makedirs(upload_folder, exist_ok=True)
    
    unique_filename = f"{product_id}_{uuid.uuid4().hex}.jpg"
    file_path = os.path.join(upload_folder, unique_filename)
    
    with open(file_path, 'wb') as f:
        f.write(image_data.getvalue())
    
    return f"/uploads/products/{unique_filename}"


def parse_price(price_str: str) -> float:
    """
    Parse a price string to float.
    Handles formats like "1,226" or "896".
    """
    if isinstance(price_str, (int, float)):
        return float(price_str)
    # Remove commas and convert
    cleaned = price_str.replace(',', '').replace(' ', '')
    return float(cleaned)


def get_or_create_brand(brand_name: str) -> Brand:
    """Get existing brand or create new one."""
    brand = Brand.query.filter_by(name=brand_name).first()
    if not brand:
        brand = Brand(name=brand_name)
        db.session.add(brand)
        db.session.flush()
        print(f"  ✓ Created brand: {brand_name}")
    return brand


def get_or_create_category(category_name: str) -> Category:
    """Get existing category or create new one."""
    category = Category.query.filter_by(name=category_name).first()
    if not category:
        category = Category(name=category_name)
        db.session.add(category)
        db.session.flush()
        print(f"  ✓ Created category: {category_name}")
    return category


def import_products_from_folder(folder_name: str, json_filename: str, app):
    """
    Import products from a specific category folder.
    
    Args:
        folder_name: Name of the folder containing product images (e.g., 'phone_products')
        json_filename: Name of the JSON file with product data (e.g., 'phone_products.json')
        app: Flask application instance
    """
    json_path = os.path.join(NEW_FOLDER_PATH, json_filename)
    images_folder = os.path.join(NEW_FOLDER_PATH, folder_name)
    
    if not os.path.exists(json_path):
        print(f"⚠ JSON file not found: {json_path}")
        return
    
    if not os.path.isdir(images_folder):
        print(f"⚠ Images folder not found: {images_folder}")
        return
    
    print(f"\n{'='*60}")
    print(f"📦 Importing from: {folder_name}")
    print(f"{'='*60}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        products_data = json.load(f)
    
    upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads/products')
    
    # Get subfolders (each product has its own numbered folder)
    subfolders = sorted([d for d in os.listdir(images_folder) if os.path.isdir(os.path.join(images_folder, d))],
                       key=lambda x: int(x) if x.isdigit() else 0)
    
    for idx, product_data in enumerate(products_data):
        product_idx = idx + 1
        
        print(f"\n  📱 [{product_idx}/{len(products_data)}] {product_data['name'][:50]}...")
        
        try:
            # Get or create brand
            brand = get_or_create_brand(product_data['brand'])
            
            # Get or create category
            category = get_or_create_category(product_data['category'])
            
            # Parse price
            price = parse_price(product_data['price'])
            
            # Create product
            product = Product(
                name=product_data['name'],
                description=product_data.get('description', ''),
                price=price,
                brand_id=brand.brand_id
            )
            db.session.add(product)
            db.session.flush()  # Get product_id
            
            # Assign category
            product.categories = [category]
            
            # Process images
            saved_image_urls = []
            absolute_image_paths = []
            
            # Determine which folder contains this product's images
            if str(product_idx) in subfolders:
                product_images_folder = os.path.join(images_folder, str(product_idx))
            elif product_idx <= len(subfolders):
                product_images_folder = os.path.join(images_folder, subfolders[product_idx - 1])
            else:
                print(f"    ⚠ No image folder found for product index {product_idx}")
                product_images_folder = None
            
            if product_images_folder and os.path.isdir(product_images_folder):
                # Get all image files in the product folder
                image_files = [f for f in os.listdir(product_images_folder) 
                              if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.jfif'))]
                
                for img_filename in image_files:
                    img_path = os.path.join(product_images_folder, img_filename)
                    
                    try:
                        # Resize the image
                        resized_data = resize_image(img_path)
                        
                        # Save resized image
                        url = save_resized_image(resized_data, product.product_id, upload_folder)
                        
                        # Create ProductImage record
                        product_image = ProductImage(
                            product_id=product.product_id,
                            url=url
                        )
                        db.session.add(product_image)
                        saved_image_urls.append(url)
                        
                        # Get absolute path for FAISS
                        abs_path = os.path.join(os.path.abspath(upload_folder), os.path.basename(url))
                        absolute_image_paths.append(abs_path)
                        
                    except Exception as e:
                        print(f"    ⚠ Error processing image {img_filename}: {e}")
            
            db.session.commit()
            
            print(f"    ✓ Created product ID: {product.product_id} with {len(saved_image_urls)} images")
            
            # Add to FAISS
            if absolute_image_paths:
                try:
                    faiss_result = faiss_service.add_product(
                        product_id=str(product.product_id),
                        name=product_data['name'],
                        description=product_data.get('description', ''),
                        brand=product_data['brand'],
                        category=product_data['category'],
                        price=price,
                        images=absolute_image_paths
                    )
                    
                    if faiss_result.get('status') == 'success':
                        print(f"    ✓ Added to FAISS")
                    else:
                        print(f"    ⚠ FAISS error: {faiss_result.get('error', 'Unknown error')}")
                except Exception as e:
                    print(f"    ⚠ FAISS error: {e}")
            
        except Exception as e:
            db.session.rollback()
            print(f"    ✗ Error: {e}")


def main():
    """Main entry point for the import script."""
    print("=" * 60)
    print("  SmartSearch Product Import Script")
    print("  One-time import from 'New folder'")
    print("=" * 60)
    
    # Create Flask app with context
    app = create_app()
    
    with app.app_context():
        # Define folders to import
        folders_to_import = [
            ('phone_products', 'phone_products.json'),
            ('laptop_products', 'laptop_products.json'),
            ('desktop_products', 'desktop_products.json'),
            ('tablet_products', 'tablet_products.json'),
        ]
        
        total_before = Product.query.count()
        print(f"\n📊 Products before import: {total_before}")
        
        for folder_name, json_filename in folders_to_import:
            import_products_from_folder(folder_name, json_filename, app)
        
        total_after = Product.query.count()
        print(f"\n{'='*60}")
        print(f"✅ Import complete!")
        print(f"   Products before: {total_before}")
        print(f"   Products after:  {total_after}")
        print(f"   New products:    {total_after - total_before}")
        print(f"{'='*60}")


if __name__ == '__main__':
    main()
