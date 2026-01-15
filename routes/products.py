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
from flask import Blueprint, request, jsonify, current_app, send_file
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


def save_base64_image(base64_string, product_id):
    """
    Save a base64 encoded image to our products folder.
    
    Args:
        base64_string: The base64 data URI like "data:image/jpeg;base64,/9j/4AAQ..."
        product_id: We use this to prefix the filename for easier debugging
    
    Returns:
        The URL path to access the saved image, or None if something went wrong
    """
    try:
        if not base64_string or not base64_string.startswith('data:'):
            print(f"[DEBUG] Invalid base64 string format", file=sys.stderr)
            return None
        
        # Parse the data URI
        # Format: data:image/jpeg;base64,/9j/4AAQ...
        header, data = base64_string.split(',', 1)
        
        # Extract mime type
        mime_match = header.split(':')[1].split(';')[0] if ':' in header else 'image/jpeg'
        
        # Determine file extension from mime type
        ext_map = {
            'image/jpeg': 'jpg',
            'image/jpg': 'jpg',
            'image/png': 'png',
            'image/gif': 'gif',
            'image/webp': 'webp'
        }
        file_ext = ext_map.get(mime_match, 'jpg')
        
        # Generate unique filename
        unique_filename = f"{product_id}_{uuid.uuid4().hex}.{file_ext}"
        
        # Create the upload folder if it doesn't exist yet
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads/products')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Decode and save the file
        file_path = os.path.join(upload_folder, unique_filename)
        img_data = base64.b64decode(data)
        
        with open(file_path, 'wb') as f:
            f.write(img_data)
        
        print(f"[DEBUG] Saved base64 image: {unique_filename} ({len(img_data)} bytes)", file=sys.stderr)
        
        # Return a URL the frontend can use to display this image
        return f"/uploads/products/{unique_filename}"
        
    except Exception as e:
        print(f"Error saving base64 image: {e}", file=sys.stderr)
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
    """
    Update an existing product's details and optionally replace all images.
    
    Send this as multipart/form-data with:
    - name: Product name (optional)
    - price: Product price (optional)
    - brand: Brand name (optional) - creates new brand if doesn't exist
    - description: Product description (optional)
    - category_ids: Comma-separated category IDs like "1,7" (optional)
    - is_active: "true" or "false" (optional)
    - images: One or more image files (optional) - if provided, ALL existing images will be deleted and replaced
    
    The product will be re-indexed in FAISS if images are changed.
    """
    try:
        # DEBUG: Log incoming request
        print(f"[DEBUG] PUT /api/products/{product_id}", file=sys.stderr)
        print(f"[DEBUG] Content-Type: {request.content_type}", file=sys.stderr)
        print(f"[DEBUG] Form data: {dict(request.form)}", file=sys.stderr)
        print(f"[DEBUG] Files: {list(request.files.keys())}", file=sys.stderr)
        
        product = Product.query.get(product_id)
        if not product:
            print(f"[DEBUG] Product {product_id} not found", file=sys.stderr)
            return jsonify({"error": "Product not found"}), 404
        
        # Get form data
        name = request.form.get('name')
        price_str = request.form.get('price')
        brand_name = request.form.get('brand')
        description = request.form.get('description')
        category_ids_str = request.form.get('category_ids', '')
        is_active_str = request.form.get('is_active')
        
        print(f"[DEBUG] Parsed - name: {name}, price: {price_str}, brand: {brand_name}, is_active: {is_active_str}", file=sys.stderr)
        
        # Get all uploaded images
        images = request.files.getlist('images')
        print(f"[DEBUG] Images count: {len(images)}, filenames: {[img.filename for img in images]}", file=sys.stderr)
        
        # Update name
        if name:
            product.name = name
        
        # Update description
        if description is not None:
            product.description = description
        
        # Update price
        if price_str:
            try:
                price = float(price_str)
                if price < 0:
                    print(f"[DEBUG] ERROR: Negative price: {price}", file=sys.stderr)
                    return jsonify({"error": "Price must be a non-negative number"}), 400
                product.price = price
            except (ValueError, TypeError) as e:
                print(f"[DEBUG] ERROR: Invalid price '{price_str}': {e}", file=sys.stderr)
                return jsonify({"error": "Price must be a valid number"}), 400
        
        # Update brand
        if brand_name:
            brand = Brand.query.filter_by(name=brand_name).first()
            if not brand:
                brand = Brand(name=brand_name)
                db.session.add(brand)
                db.session.flush()
            product.brand_id = brand.brand_id
        
        # Update is_active
        if is_active_str is not None:
            product.is_active = is_active_str.lower() == 'true'
        
        # Update categories
        if category_ids_str:
            try:
                category_ids = [int(x.strip()) for x in category_ids_str.split(',') if x.strip()]
                categories = Category.query.filter(Category.category_id.in_(category_ids)).all()
                product.categories = categories
            except ValueError as e:
                print(f"[DEBUG] ERROR: Invalid category_ids '{category_ids_str}': {e}", file=sys.stderr)
                return jsonify({"error": "category_ids must be comma-separated integers"}), 400
        
        # Handle images - if new images provided, delete old ones and add new
        saved_image_urls = []
        images_updated = False
        
        # Check for base64 images from images_base64 field
        images_base64_str = request.form.get('images_base64', '')
        base64_images = []
        
        if images_base64_str:
            try:
                import json
                base64_images = json.loads(images_base64_str)
                if not isinstance(base64_images, list):
                    base64_images = [base64_images]
                print(f"[DEBUG] Base64 images from images_base64 field: {len(base64_images)}", file=sys.stderr)
            except json.JSONDecodeError as e:
                print(f"[DEBUG] ERROR: Invalid images_base64 JSON: {e}", file=sys.stderr)
                return jsonify({"error": "images_base64 must be a valid JSON array of base64 strings"}), 400
        
        # Process uploaded files - check if they're actual files or base64 data
        valid_images = []
        for img in images:
            if not img or not img.filename:
                continue
            
            # Check if filename has extension (real file) or not (might be base64 or raw binary)
            if '.' in img.filename:
                # This looks like a real file with extension
                valid_images.append(img)
                print(f"[DEBUG] Valid file upload: {img.filename}", file=sys.stderr)
            else:
                # No extension - read content and detect type
                try:
                    content = img.read()
                    img.seek(0)  # Reset file pointer
                    
                    # First try: check if it's a text base64 data URI
                    try:
                        content_str = content.decode('utf-8')
                        if content_str.startswith('data:image'):
                            # This is base64 data URI
                            base64_images.append(content_str)
                            print(f"[DEBUG] Detected base64 data URI in file: {img.filename}", file=sys.stderr)
                            continue
                    except UnicodeDecodeError:
                        pass  # Not text, might be binary image
                    
                    # Second try: check magic bytes to detect image type
                    ext = None
                    if content[:2] == b'\xff\xd8':
                        ext = 'jpg'
                    elif content[:8] == b'\x89PNG\r\n\x1a\n':
                        ext = 'png'
                    elif content[:6] in (b'GIF87a', b'GIF89a'):
                        ext = 'gif'
                    elif content[:4] == b'RIFF' and content[8:12] == b'WEBP':
                        ext = 'webp'
                    
                    if ext:
                        # It's a valid image! Create a wrapper to save it
                        print(f"[DEBUG] Detected {ext} image from binary (filename was: {img.filename})", file=sys.stderr)
                        # Save directly since we already have the content
                        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads/products')
                        os.makedirs(upload_folder, exist_ok=True)
                        unique_filename = f"{product_id}_{uuid.uuid4().hex}.{ext}"
                        file_path = os.path.join(upload_folder, unique_filename)
                        with open(file_path, 'wb') as f:
                            f.write(content)
                        # Add to saved list (we'll process this specially)
                        saved_image_urls.append(f"/uploads/products/{unique_filename}")
                        print(f"[DEBUG] Saved binary image as: {unique_filename}", file=sys.stderr)
                    else:
                        print(f"[DEBUG] Skipping unknown file format: {img.filename} (first bytes: {content[:10]})", file=sys.stderr)
                        
                except Exception as e:
                    print(f"[DEBUG] Error reading file {img.filename}: {e}", file=sys.stderr)
        
        print(f"[DEBUG] Total base64 images: {len(base64_images)}, valid file uploads: {len(valid_images)}, pre-saved binary: {len(saved_image_urls)}", file=sys.stderr)
        
        # Process if we have any new images (base64, file uploads, or pre-saved binary)
        if base64_images or valid_images or saved_image_urls:
            images_updated = True
            
            # Delete old images from disk and database
            old_images = ProductImage.query.filter_by(product_id=product_id).all()
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads/products')
            print(f"[DEBUG] Deleting {len(old_images)} old images", file=sys.stderr)
            
            for old_img in old_images:
                # Delete file from disk
                file_path = os.path.join(upload_folder, os.path.basename(old_img.url))
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"Warning: Could not delete old image file {file_path}: {e}", file=sys.stderr)
                # Delete from database
                db.session.delete(old_img)
            
            # Add pre-saved binary images to database (they're already saved to disk)
            for url in saved_image_urls:
                image = ProductImage(
                    product_id=product.product_id,
                    url=url
                )
                db.session.add(image)
                print(f"[DEBUG] Added pre-saved binary to DB: {url}", file=sys.stderr)
            
            # Save base64 images
            for idx, b64_img in enumerate(base64_images):
                url = save_base64_image(b64_img, product.product_id)
                if url is None:
                    print(f"[DEBUG] ERROR: Failed to save base64 image {idx}", file=sys.stderr)
                    db.session.rollback()
                    return jsonify({"error": f"Failed to save base64 image {idx}"}), 400
                
                image = ProductImage(
                    product_id=product.product_id,
                    url=url
                )
                db.session.add(image)
                saved_image_urls.append(url)
            
            # Save file uploads (if any valid ones exist)
            for img_file in valid_images:
                if not allowed_file(img_file.filename):
                    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp'})
                    print(f"[DEBUG] ERROR: File type not allowed: {img_file.filename}", file=sys.stderr)
                    db.session.rollback()
                    return jsonify({"error": f"File type not allowed. Allowed types: {', '.join(allowed)}"}), 400
                
                url = save_uploaded_image(img_file, product.product_id)
                if url is None:
                    print(f"[DEBUG] ERROR: Failed to save image: {img_file.filename}", file=sys.stderr)
                    db.session.rollback()
                    return jsonify({"error": "Failed to save image file."}), 400
                
                image = ProductImage(
                    product_id=product.product_id,
                    url=url
                )
                db.session.add(image)
                saved_image_urls.append(url)
        
        product.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Update FAISS index if images were changed
        if images_updated:
            try:
                upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads/products')
                abs_upload_folder = os.path.abspath(upload_folder)
                
                absolute_image_paths = []
                for url in saved_image_urls:
                    filename = os.path.basename(url)
                    abs_path = os.path.join(abs_upload_folder, filename)
                    absolute_image_paths.append(abs_path)
                
                # Get category names
                category_names = [c.name for c in product.categories]
                category_str = ", ".join(category_names) if category_names else ""
                
                # Get brand name
                brand_name_for_faiss = product.brand.name if product.brand else ""
                
                # Re-index the product in FAISS (add with same ID should update)
                faiss_result = faiss_service.add_product(
                    product_id=str(product.product_id),
                    name=product.name,
                    description=product.description or "",
                    brand=brand_name_for_faiss,
                    category=category_str,
                    price=float(product.price) if product.price else 0.0,
                    images=absolute_image_paths
                )
                
                if faiss_result.get('status') == 'error':
                    print(f"Warning: Updated DB but failed to update FAISS: {faiss_result.get('error')}", file=sys.stderr)
            except Exception as e:
                print(f"Error updating FAISS: {e}", file=sys.stderr)
        
        return jsonify({
            "message": "Product updated successfully",
            "product_id": product.product_id,
            "name": product.name,
            "brand": product.brand.name if product.brand else None,
            "images": saved_image_urls if images_updated else None,
            "images_updated": images_updated
        }), 200
    
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_product: {e}", file=sys.stderr)
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
    """
    List all images for a product as base64.
    
    Returns all images as base64 data URI strings.
    """
    try:
        product = Product.query.get(product_id)
        if not product:
            return jsonify({"error": "Product not found"}), 404
        
        images = ProductImage.query.filter_by(product_id=product_id).order_by(ProductImage.image_no).all()
        
        images_base64 = []
        for img in images:
            b64 = get_image_as_base64(img.url)
            if b64:
                images_base64.append({
                    "image_no": img.image_no,
                    "image": b64
                })
        
        return jsonify({
            "product_id": product_id,
            "images": images_base64,
            "total": len(images_base64)
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@products_bp.route('/products/<int:product_id>/image', methods=['GET'])
def get_product_first_image(product_id):
    """
    Get the first image of a product as base64.
    
    Returns the image as a base64 data URI string in JSON format.
    """
    try:
        # Check if product exists
        product = Product.query.get(product_id)
        if not product:
            return jsonify({"error": "Product not found"}), 404
        
        # Get the first image (ordered by image_no)
        image = ProductImage.query.filter_by(product_id=product_id).order_by(ProductImage.image_no).first()
        
        if not image:
            return jsonify({"error": "No image found for this product"}), 404
        
        # Convert to base64
        base64_image = get_image_as_base64(image.url)
        
        if not base64_image:
            return jsonify({"error": "Image file not found on disk"}), 404
        
        return jsonify({
            "product_id": product_id,
            "image": base64_image
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
