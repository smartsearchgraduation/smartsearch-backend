"""
A helper script to populate the database with sample data.
Useful for testing and development.
"""
from datetime import datetime, timezone
from app import create_app
from models import db
from models.brand import Brand
from models.category import Category
from models.product import Product
from models.product_category import ProductCategory
from models.product_image import ProductImage
from models.search_query import SearchQuery
from models.retrieve import Retrieve


def get_next_id(model, id_column):
    """Find the next available ID for a table (to avoid conflicts)."""
    max_id = db.session.query(db.func.max(id_column)).scalar()
    return (max_id or 0) + 1


def seed_database():
    """Fill the database with some sample data to play around with."""
    
    app = create_app()
    
    with app.app_context():
        print("🌱 Starting database seeding...")
        
        # Figure out what IDs to use so we don't conflict with existing data
        brand_id = get_next_id(Brand, Brand.brand_id)
        parent_cat_id = get_next_id(Category, Category.category_id)
        child_cat_id = parent_cat_id + 1
        product_id = get_next_id(Product, Product.product_id)
        image_no = get_next_id(ProductImage, ProductImage.image_no)
        search_id = get_next_id(SearchQuery, SearchQuery.search_id)
        
        now = datetime.now(timezone.utc)
        
        # First, let's create a brand
        print("   Creating brand...")
        brand = Brand(
            brand_id=brand_id,
            name="AudioMax"
        )
        db.session.add(brand)
        db.session.flush()
        print(f"   ✅ Brand created: {brand.name} (ID: {brand_id})")
        
        # Now add some categories (parent and child)
        print("   Creating categories...")
        parent_category = Category(
            category_id=parent_cat_id,
            parent_category_id=None,
            name="Audio Equipment"
        )
        db.session.add(parent_category)
        db.session.flush()
        
        # Add a child category under the parent
        child_category = Category(
            category_id=child_cat_id,
            parent_category_id=parent_cat_id,
            name="Headphones"
        )
        db.session.add(child_category)
        db.session.flush()
        print(f"   ✅ Categories created: {parent_category.name} (ID: {parent_cat_id}), {child_category.name} (ID: {child_cat_id})")
        
        # Create a sample product
        print("   Creating product...")
        product = Product(
            product_id=product_id,
            brand_id=brand_id,
            name="Blue Wireless Headphones Pro",
            description="Premium noise-cancelling wireless headphones with 40-hour battery life, Hi-Res audio, and comfortable over-ear design",
            price=189.99,
            is_active=True,
            created_at=now,
            updated_at=now
        )
        db.session.add(product)
        db.session.flush()
        print(f"   ✅ Product created: {product.name} (ID: {product_id})")
        
        # Link the product to its category
        print("   Creating product-category association...")
        product_category = ProductCategory(
            product_id=product_id,
            category_id=child_cat_id  # Headphones
        )
        db.session.add(product_category)
        db.session.flush()
        print(f"   ✅ Product-Category association created")
        
        # Add an image for the product
        print("   Creating product image...")
        product_image = ProductImage(
            image_no=image_no,
            product_id=product_id,
            url="https://example.com/images/blue-wireless-headphones-pro.jpg",
            uploaded_at=now
        )
        db.session.add(product_image)
        db.session.flush()
        print(f"   ✅ Product image created (ID: {image_no})")
        
        # Create a sample search query
        print("   Creating search query...")
        search_query = SearchQuery(
            search_id=search_id,
            raw_text="wireless headphones",
            corrected_text="wireless headphones",
            type="text",
            time_to_retrieve=120,
            timestamp=now
        )
        db.session.add(search_query)
        db.session.flush()
        print(f"   ✅ Search query created: '{search_query.raw_text}' (ID: {search_id})")
        
        # And its search result
        print("   Creating retrieve record...")
        retrieve = Retrieve(
            search_id=search_id,
            product_id=product_id,
            rank=1,
            weight=0.92,
            explain='{"match_type": "text", "matched_fields": ["name", "description"]}',
            is_relevant=True,
            is_clicked=True,
            embedding_id=f"emb-{search_id:03d}"
        )
        db.session.add(retrieve)
        db.session.flush()
        print(f"   ✅ Retrieve record created (rank: {retrieve.rank}, weight: {retrieve.weight})")
        
        # Save everything to the database
        db.session.commit()
        
        print("\n🎉 Database seeding completed successfully!")
        print("\n📊 Summary:")
        print(f"   - Brand: {brand.name} (ID: {brand_id})")
        print(f"   - Categories: {parent_category.name} -> {child_category.name}")
        print(f"   - Product: {product.name} (ID: {product_id})")
        print(f"   - Product-Category association: ✓")
        print(f"   - Product Image: ✓ (ID: {image_no})")
        print(f"   - Search Query: '{search_query.raw_text}' (ID: {search_id})")
        print(f"   - Retrieve record: ✓")


if __name__ == '__main__':
    seed_database()
