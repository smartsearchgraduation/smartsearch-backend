"""
Brands routes blueprint.
"""
from flask import Blueprint, request, jsonify

from models import db, Brand

brands_bp = Blueprint('brands', __name__, url_prefix='/api')


@brands_bp.route('/brands', methods=['GET'])
def get_brands():
    """Get all brands."""
    try:
        brands = Brand.query.order_by(Brand.name).all()
        return jsonify({
            'brands': [b.to_dict() for b in brands]
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@brands_bp.route('/brands/<int:brand_id>', methods=['GET'])
def get_brand(brand_id):
    """Get a specific brand by ID."""
    try:
        brand = Brand.query.get(brand_id)
        if not brand:
            return jsonify({"error": "Brand not found"}), 404
        
        return jsonify(brand.to_dict()), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@brands_bp.route('/brands', methods=['POST'])
def create_brand():
    """
    Create a new brand.
    
    Request body:
    {
        "name": "Brand Name"
    }
    """
    try:
        data = request.get_json()
        
        if not data or 'name' not in data:
            return jsonify({"error": "Missing required field: name"}), 400
        
        brand = Brand(name=data['name'])
        db.session.add(brand)
        db.session.commit()
        
        return jsonify(brand.to_dict()), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@brands_bp.route('/brands/<int:brand_id>', methods=['PUT'])
def update_brand(brand_id):
    """Update an existing brand."""
    try:
        brand = Brand.query.get(brand_id)
        if not brand:
            return jsonify({"error": "Brand not found"}), 404
        
        data = request.get_json()
        
        if 'name' in data:
            brand.name = data['name']
        
        db.session.commit()
        
        return jsonify(brand.to_dict()), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@brands_bp.route('/brands/<int:brand_id>', methods=['DELETE'])
def delete_brand(brand_id):
    """Delete a brand."""
    try:
        brand = Brand.query.get(brand_id)
        if not brand:
            return jsonify({"error": "Brand not found"}), 404
        
        db.session.delete(brand)
        db.session.commit()
        
        return jsonify({"ok": True, "message": "Brand deleted"}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
