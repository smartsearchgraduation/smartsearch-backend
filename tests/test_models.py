import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from models import db, Product, Category, Brand, ProductImage


class TestProductToDict:

    def test_product_to_dict_all_fields(self, db_session):
        product = Product(name='Test Product', price=99.99, description='A test')
        db_session.add(product)
        db_session.flush()
        result = product.to_dict()
        assert result['product_id'] == product.product_id
        assert result['name'] == 'Test Product'
        assert result['price'] == 99.99

    def test_product_to_dict_include_brand_true(self, db_session):
        brand = Brand(name='Test Brand')
        db_session.add(brand)
        db_session.flush()
        product = Product(name='Branded Product', price=49.99, brand_id=brand.brand_id)
        db_session.add(product)
        db_session.flush()
        result = product.to_dict(include_brand=True)
        assert 'brand' in result
        assert result['brand']['name'] == 'Test Brand'

    def test_product_to_dict_include_brand_false(self, db_session):
        brand = Brand(name='Hidden Brand')
        db_session.add(brand)
        db_session.flush()
        product = Product(name='No Brand Shown', price=10.00, brand_id=brand.brand_id)
        db_session.add(product)
        db_session.flush()
        result = product.to_dict(include_brand=False)
        assert 'brand' not in result

    def test_product_to_dict_include_images_true(self, db_session):
        product = Product(name='Product With Images', price=25.00)
        db_session.add(product)
        db_session.flush()
        img = ProductImage(product_id=product.product_id, url='/uploads/products/test.jpg')
        db_session.add(img)
        db_session.flush()
        result = product.to_dict(include_images=True)
        assert 'images' in result
        assert len(result['images']) > 0

    def test_product_to_dict_include_images_false(self, db_session):
        product = Product(name='Product No Images', price=15.00)
        db_session.add(product)
        db_session.flush()
        img = ProductImage(product_id=product.product_id, url='/uploads/products/test.jpg')
        db_session.add(img)
        db_session.flush()
        result = product.to_dict(include_images=False)
        assert 'images' not in result

    def test_product_to_dict_include_categories_true(self, db_session):
        cat = Category(name='Electronics')
        db_session.add(cat)
        db_session.flush()
        product = Product(name='Gadget', price=199.99)
        db_session.add(product)
        db_session.flush()
        product.categories.append(cat)
        db_session.flush()
        result = product.to_dict(include_categories=True)
        assert 'categories' in result
        assert len(result['categories']) > 0

    def test_product_to_dict_include_categories_false(self, db_session):
        cat = Category(name='Books')
        db_session.add(cat)
        db_session.flush()
        product = Product(name='Novel', price=12.99)
        db_session.add(product)
        db_session.flush()
        product.categories.append(cat)
        db_session.flush()
        result = product.to_dict(include_categories=False)
        assert 'categories' not in result


class TestCategoryToDict:

    def test_category_to_dict_flat(self, db_session):
        cat = Category(name='Root Category')
        db_session.add(cat)
        db_session.flush()
        result = cat.to_dict()
        assert result['name'] == 'Root Category'
        assert result['parent_category_id'] is None

    def test_category_to_dict_with_parent(self, db_session):
        parent = Category(name='Parent')
        db_session.add(parent)
        db_session.flush()
        child = Category(name='Child', parent_category_id=parent.category_id)
        db_session.add(child)
        db_session.flush()
        result = child.to_dict(include_parent=True)
        assert 'parent' in result
        assert result['parent']['name'] == 'Parent'

    def test_category_to_dict_with_children(self, db_session):
        parent = Category(name='Family')
        db_session.add(parent)
        db_session.flush()
        child = Category(name='Member', parent_category_id=parent.category_id)
        db_session.add(child)
        db_session.flush()
        result = parent.to_dict(include_children=True)
        assert 'children' in result
        assert any(c['name'] == 'Member' for c in result['children'])

    def test_category_self_referencing_multi_level(self, db_session):
        grandparent = Category(name='Grandparent')
        db_session.add(grandparent)
        db_session.flush()
        parent = Category(name='Parent', parent_category_id=grandparent.category_id)
        db_session.add(parent)
        db_session.flush()
        child = Category(name='Child', parent_category_id=parent.category_id)
        db_session.add(child)
        db_session.flush()
        result = child.to_dict(include_parent=True)
        parent_dict = result['parent']
        assert parent_dict['name'] == 'Parent'
        grandparent_dict = parent.to_dict(include_parent=True)
        assert grandparent_dict['parent']['name'] == 'Grandparent'


class TestSearchQueryModel:

    def test_repr(self, db_session):
        from models.search_query import SearchQuery
        sq = SearchQuery(raw_text='test query', corrected_text='test query')
        db_session.add(sq)
        db_session.flush()
        rep = repr(sq)
        assert 'SearchQuery' in rep
        assert str(sq.search_id) in rep

    def test_to_dict_basic(self, db_session):
        from models.search_query import SearchQuery
        sq = SearchQuery(raw_text='hello', corrected_text='world')
        db_session.add(sq)
        db_session.flush()
        d = sq.to_dict()
        assert d['raw_text'] == 'hello'
        assert d['corrected_text'] == 'world'

    def test_to_dict_with_results(self, db_session):
        from models.search_query import SearchQuery
        from models.retrieve import Retrieve
        sq = SearchQuery(raw_text='test', corrected_text='test')
        db_session.add(sq)
        db_session.flush()
        p = Product(name='P', price=10.0)
        db_session.add(p)
        db_session.flush()
        r = Retrieve(search_id=sq.search_id, product_id=p.product_id, rank=1)
        db_session.add(r)
        db_session.commit()
        d = sq.to_dict(include_results=True)
        assert 'results' in d
        assert len(d['results']) == 1


class TestBrandModel:

    def test_repr(self, db_session):
        from models.brand import Brand
        b = Brand(name='TestBrand')
        rep = repr(b)
        assert 'TestBrand' in rep


class TestProductModel:

    def test_repr(self, db_session):
        from models.product import Product
        p = Product(name='TestProd', price=10.0)
        rep = repr(p)
        assert 'TestProd' in rep
