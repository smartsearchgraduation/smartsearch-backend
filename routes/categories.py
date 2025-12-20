"""
API routes for managing product categories.
"""
from flask import Blueprint, request, jsonify

from models import db, Category

categories_bp = Blueprint('categories', __name__, url_prefix='/api')


@categories_bp.route('/categories', methods=['GET'])
def get_categories():
    """
    List all categories, optionally as a tree structure.
    
    Use ?tree=true to get a nested hierarchy, or ?parent_id=X to get
    children of a specific category.
    """
    try:
        parent_id = request.args.get('parent_id')
        tree = request.args.get('tree', 'false').lower() == 'true'
        
        if tree:
            # Return hierarchical tree structure
            root_categories = Category.query.filter(
                Category.parent_category_id == None
            ).order_by(Category.name).all()
            
            return jsonify({
                'categories': [c.to_dict(include_children=True) for c in root_categories],
                'total': Category.query.count()
            }), 200
        
        # Flat list with optional parent filter
        query = Category.query
        
        if parent_id is not None:
            if parent_id in ('0', 'null', ''):
                query = query.filter(Category.parent_category_id == None)
            else:
                query = query.filter(Category.parent_category_id == int(parent_id))
        
        categories = query.order_by(Category.name).all()
        
        return jsonify({
            'categories': [c.to_dict() for c in categories],
            'total': len(categories)
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@categories_bp.route('/categories/<int:category_id>', methods=['GET'])
def get_category(category_id):
    """Get a single category with its parent and children info."""
    try:
        category = Category.query.get(category_id)
        if not category:
            return jsonify({"error": "Category not found"}), 404
        
        return jsonify(category.to_dict(include_parent=True, include_children=True)), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@categories_bp.route('/categories', methods=['POST'])
def create_category():
    """
    Create a new category.
    
    Send a name, and optionally a parent_category_id to make it a subcategory.
    """
    try:
        data = request.get_json()
        
        if not data or 'name' not in data:
            return jsonify({"error": "Missing required field: name"}), 400
        
        # Validate parent exists if provided
        parent_id = data.get('parent_category_id')
        if parent_id:
            parent = Category.query.get(parent_id)
            if not parent:
                return jsonify({"error": "Parent category not found"}), 400
        
        category = Category(
            name=data['name'],
            parent_category_id=parent_id
        )
        db.session.add(category)
        db.session.commit()
        
        return jsonify(category.to_dict()), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@categories_bp.route('/categories/<int:category_id>', methods=['PUT'])
def update_category(category_id):
    """Update a category's name or parent."""
    try:
        category = Category.query.get(category_id)
        if not category:
            return jsonify({"error": "Category not found"}), 404
        
        data = request.get_json()
        
        if 'name' in data:
            category.name = data['name']
        
        if 'parent_category_id' in data:
            parent_id = data['parent_category_id']
            # Prevent setting self as parent
            if parent_id == category_id:
                return jsonify({"error": "Category cannot be its own parent"}), 400
            # Validate parent exists if provided
            if parent_id:
                parent = Category.query.get(parent_id)
                if not parent:
                    return jsonify({"error": "Parent category not found"}), 400
            category.parent_category_id = parent_id
        
        db.session.commit()
        
        return jsonify(category.to_dict()), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@categories_bp.route('/categories/<int:category_id>', methods=['DELETE'])
def delete_category(category_id):
    """Remove a category from the system."""
    try:
        category = Category.query.get(category_id)
        if not category:
            return jsonify({"error": "Category not found"}), 404
        
        db.session.delete(category)
        db.session.commit()
        
        return jsonify({"ok": True, "message": "Category deleted"}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
