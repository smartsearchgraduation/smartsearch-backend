"""
API routes for managing products in the catalog.
Includes endpoints for creating, reading, updating, and deleting products,
as well as handling product images.
"""
import os
import sys
import uuid
import base64
import mimetypes
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from werkzeug.utils import secure_filename

from models import db, Product, Brand, Category, ProductImage
from services.faiss_retrieval_service import faiss_service


def allowed_file(filename):
    """Make sure the uploaded file has an allowed image extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp'})


def save_uploaded_image(file, product_id):
    """
    Save an uploaded image to our products folder.
    
    Takes care of all the boring stuff: validating the file, generating a
    unique filename so nothing gets overwritten, creating directories if
    needed, and actually saving the file.
    
    Args:
        file: The uploaded file from the request
        product_id: We use this to prefix the filename for easier debugging
    
    Returns:
        The URL path to access the saved image, or None if something went wrong
    """
    try:
        if not file or file.filename == '':
            return None
        
        if not allowed_file(file.filename):
            return None
        
        # Get file extension
        original_filename = secure_filename(file.filename)
        file_ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else 'jpg'
        
        # Use UUID in filename so we never overwrite existing files
        unique_filename = f"{product_id}_{uuid.uuid4().hex}.{file_ext}"
        
        # Create the upload folder if it doesn't exist yet
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads/products')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Actually save the file
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        # Return a URL the frontend can use to display this image
        return f"/uploads/products/{unique_filename}"
        
    except Exception as e:
        print(f"Error saving uploaded image: {e}", file=sys.stderr)
        return None


def get_image_as_base64(img_path):
    """
    Convert an image file to a base64 data URI.
    
    This lets us embed images directly in JSON responses instead of
    requiring the frontend to make separate requests for each image.
    
    Args:
        img_path: The image path like "/uploads/products/filename.jpg"
    
    Returns:
        A data URI string like "data:image/jpeg;base64,..." or None if the file doesn't exist
    """
    try:
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads/products')
        filename = os.path.basename(img_path)
        file_path = os.path.join(upload_folder, filename)
        
        if not os.path.exists(file_path):
            return None
        
        with open(file_path, 'rb') as f:
            img_data = f.read()
        
        mimetype, _ = mimetypes.guess_type(file_path)
        if not mimetype:
            mimetype = 'image/jpeg'
        
        b64_data = base64.b64encode(img_data).decode('utf-8')
        return f"data:{mimetype};base64,{b64_data}"
    except Exception as e:
        print(f"Error reading image as base64: {e}", file=sys.stderr)
        return None


products_bp = Blueprint('products', __name__, url_prefix='/api')


@products_bp.route('/products', methods=['GET'])
def get_products():
    """
    List all products, with optional filtering.
    
    You can filter by category, brand, price range, or active status.
    All filters are optional - omit them to get everything.
    """
    try:
        # Build query
        query = Product.query
        
        # Apply filters
        category_id = request.args.get('category_id', type=int)
        brand_id = request.args.get('brand_id', type=int)
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        is_active = request.args.get('is_active')
        
        if category_id:
            query = query.filter(Product.categories.any(Category.category_id == category_id))
        
        if brand_id:
            query = query.filter(Product.brand_id == brand_id)
        
        if min_price is not None:
            query = query.filter(Product.price >= min_price)
        
        if max_price is not None:
            query = query.filter(Product.price <= max_price)
        
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            query = query.filter(Product.is_active == is_active_bool)
        
        products = query.order_by(Product.created_at.desc()).all()
        
        return jsonify({
            'products': [p.to_dict() for p in products],
            'total': len(products)
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@products_bp.route('/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """Fetch a single product with all its details and images (base64 encoded)."""
    try:
        product = Product.query.get(product_id)
        if not product:
            return jsonify({"error": "Product not found"}), 404
        
        # Get product dict and convert images to base64
        product_dict = product.to_dict()
        
        # Get images from database and convert to base64
        images = ProductImage.query.filter_by(product_id=product_id).order_by(ProductImage.image_no).all()
        images_base64 = []
        for img in images:
            b64 = get_image_as_base64(img.url)
            if b64:
                images_base64.append(b64)
        
        product_dict['images'] = images_base64
        
        return jsonify(product_dict), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@products_bp.route('/products', methods=['POST'])
def create_product():
    """
    Create a new product.
    
    Send this as multipart/form-data with:
    - name: Product name (required)
    - price: Product price (required)  
    - brand: Brand name - creates a new brand if it doesn't exist (required)
    - description: Product description (optional)
    - category_ids: Comma-separated category IDs like "1,7" (optional)
    - images: One or more image files (required)
    
    The product will automatically be indexed in FAISS for search.
    """
    try:
        # Get form data
        name = request.form.get('name')
        price_str = request.form.get('price')
        brand_name = request.form.get('brand')
        description = request.form.get('description')
        category_ids_str = request.form.get('category_ids', '')
        
        # Get all uploaded images
        images = request.files.getlist('images')
        
        # Validate required fields
        missing_fields = []
        if not name:
            missing_fields.append('name')
        if not price_str:
            missing_fields.append('price')
        if not brand_name:
            missing_fields.append('brand')
        if not images or len(images) == 0 or (len(images) == 1 and images[0].filename == ''):
            missing_fields.append('images')
        
        if missing_fields:
            return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400
        
        # Validate price
        try:
            price = float(price_str)
            if price < 0:
                return jsonify({"error": "Price must be a non-negative number"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "Price must be a valid number"}), 400
        
        # Parse category_ids
        category_ids = []
        if category_ids_str:
            try:
                category_ids = [int(x.strip()) for x in category_ids_str.split(',') if x.strip()]
            except ValueError:
                return jsonify({"error": "category_ids must be comma-separated integers"}), 400
        
        # Validate image files
        for img in images:
            if img.filename and not allowed_file(img.filename):
                allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp'})
                return jsonify({"error": f"File type not allowed. Allowed types: {', '.join(allowed)}"}), 400
        
        # Find or create brand
        brand = Brand.query.filter_by(name=brand_name).first()
        if not brand:
            brand = Brand(name=brand_name)
            db.session.add(brand)
            db.session.flush()
        
        # Create product
        product = Product(
            name=name,
            description=description,
            price=price,
            brand_id=brand.brand_id
        )
        db.session.add(product)
        db.session.flush()
        
        # Add categories
        if category_ids:
            categories = Category.query.filter(Category.category_id.in_(category_ids)).all()
            product.categories = categories
        
        # Process and save images
        saved_image_urls = []
        for img_file in images:
            if img_file.filename:
                url = save_uploaded_image(img_file, product.product_id)
                if url is None:
                    db.session.rollback()
                    return jsonify({"error": "Failed to save image file."}), 400
                
                image = ProductImage(
                    product_id=product.product_id,
                    url=url
                )
                db.session.add(image)
                saved_image_urls.append(url)
        
        db.session.commit()
        
        # Add to FAISS
        try:
            # Construct absolute image paths
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads/products')
            abs_upload_folder = os.path.abspath(upload_folder)
            
            absolute_image_paths = []
            for url in saved_image_urls:
                # url is like /uploads/products/filename.ext
                filename = os.path.basename(url)
                abs_path = os.path.join(abs_upload_folder, filename)
                absolute_image_paths.append(abs_path)
            
            # Get category names
            category_names = [c.name for c in product.categories]
            category_str = ", ".join(category_names) if category_names else ""
            
            # Index the new product in FAISS so it shows up in searches
            faiss_result = faiss_service.add_product(
                product_id=str(product.product_id),
                name=name,
                description=description or "",
                brand=brand_name,
                category=category_str,
                price=price,
                images=absolute_image_paths
            )
            
            if faiss_result.get('status') == 'error':
                print(f"Warning: Added to DB but failed to add to FAISS: {faiss_result.get('error')}", file=sys.stderr)
        except Exception as e:
             print(f"Error adding to FAISS: {e}", file=sys.stderr)
        
        return jsonify({
            "product_id": product.product_id,
            "name": name,
            "brand": brand_name,
            "category_ids": category_ids,
            "images": saved_image_urls
        }), 201
    
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_product: {e}", file=sys.stderr)
        return jsonify({"error": "An error occurred while creating the product"}), 500


@products_bp.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """Update an existing product's details."""
    try:
        product = Product.query.get(product_id)
        if not product:
            return jsonify({"error": "Product not found"}), 404
        
        data = request.get_json()
        
        # Only update the fields that were actually sent
        if 'name' in data:
            product.name = data['name']
        if 'description' in data:
            product.description = data['description']
        if 'price' in data:
            product.price = data['price']
        if 'brand_id' in data:
            product.brand_id = data['brand_id']
        if 'is_active' in data:
            product.is_active = data['is_active']
        if 'category_ids' in data:
            categories = Category.query.filter(
                Category.category_id.in_(data['category_ids'])
            ).all()
            product.categories = categories
        
        product.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify(product.to_dict()), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@products_bp.route('/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """Remove a product and all its associated data."""
    try:
        product = Product.query.get(product_id)
        if not product:
            return jsonify({"error": "Product not found"}), 404
        
        db.session.delete(product)
        db.session.commit()
        
        return jsonify({"ok": True, "message": "Product deleted"}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@products_bp.route('/products/<int:product_id>/images', methods=['POST'])
def upload_product_image(product_id):
    """
    Add a new image to an existing product.
    
    Send the image as form-data with key "file". The image will be saved
    to disk and a database record created to track it.
    """
    try:
        product = Product.query.get(product_id)
        if not product:
            return jsonify({"error": "Product not found"}), 404
        
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        
        # Check if file is selected
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Check if file type is allowed
        if not allowed_file(file.filename):
            allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp'})
            return jsonify({"error": f"File type not allowed. Allowed types: {', '.join(allowed)}"}), 400
        
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        file_ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else 'jpg'
        unique_filename = f"{product_id}_{uuid.uuid4().hex}.{file_ext}"
        
        # Ensure upload directory exists
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads/products')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Save file
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        # Create relative URL path for serving
        relative_url = f"/uploads/products/{unique_filename}"
        
        # Create database record
        image = ProductImage(
            product_id=product_id,
            url=relative_url
        )
        
        db.session.add(image)
        db.session.commit()
        
        return jsonify({
            **image.to_dict(),
            "filename": unique_filename,
            "original_filename": original_filename
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@products_bp.route('/products/<int:product_id>/images/<int:image_no>', methods=['DELETE'])
def delete_product_image(product_id, image_no):
    """
    Remove a specific image from a product.
    
    This deletes both the file on disk and the database record.
    """
    try:
        image = ProductImage.query.filter_by(
            product_id=product_id,
            image_no=image_no
        ).first()
        
        if not image:
            return jsonify({"error": "Image not found"}), 404
        
        # Clean up the actual file from disk
        file_path = os.path.join(
            current_app.config.get('UPLOAD_FOLDER', 'uploads/products'),
            os.path.basename(image.url)
        )
        if os.path.exists(file_path):
            os.remove(file_path)
        
        db.session.delete(image)
        db.session.commit()
        
        return jsonify({"ok": True, "message": "Image deleted"}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@products_bp.route('/products/<int:product_id>/images', methods=['GET'])
def get_product_images(product_id):
    """List all images for a product."""
    try:
        product = Product.query.get(product_id)
        if not product:
            return jsonify({"error": "Product not found"}), 404
        
        images = ProductImage.query.filter_by(product_id=product_id).all()
        
        return jsonify({
            "product_id": product_id,
            "images": [img.to_dict() for img in images],
            "total": len(images)
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
