"""
Search service for handling search queries.
Orchestrates Text Corrector → FAISS → Database flow.
"""
import logging
import base64
import os
import time
import mimetypes
from typing import Dict, Any, List, Optional

from flask import current_app
from models import db, SearchQuery, Retrieve, Product
from .external_services import text_corrector
from .faiss_retrieval_service import FAISSRetrievalService

logger = logging.getLogger(__name__)


class SearchService:
    """
    Service class for search-related operations.
    
    Search Flow:
    1. Receive raw_text from frontend
    2. Send to Text Corrector → get corrected_text
    3. Send corrected_text to FAISS → get product_ids with scores
    4. If FAISS fails or returns empty, fallback to DB search
    5. Insert search_query record
    6. Insert retrieve records for each result
    7. Return search_id
    """
    
    @staticmethod
    def execute_search(raw_text: str, image: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a search query through Text Corrector and FAISS pipeline.
        
        Flow per work.txt spec:
        1. Call correction service: POST { "text": raw_text } -> { "corrected_text": "..." }
        2. Call FAISS service: 
           - If image provided: search_late_fusion
           - Else: search_text
        3. If FAISS fails or returns empty, fallback to DB: 
           SELECT product_id, name, price FROM product WHERE name ILIKE %corrected_text% ORDER BY name LIMIT 20
        4. INSERT INTO search_query(raw_text, corrected_text) RETURNING search_id
        5. For each product, INSERT INTO retrieve(search_id, product_id, rank, score)
        6. Return { "search_id": <number> }
        
        Args:
            raw_text: Raw search query from user
            image: Optional image path for late fusion search
        
        Returns:
            dict with search_id only (per work.txt spec)
        """
        start_total = time.time()
        logger.info(f"[Search] Starting search for raw_text: '{raw_text}', image: {image}")
        print(f"DEBUG [SearchService]: execute_search called with raw_text='{raw_text}', image='{image}'")
        
        try:
            # ============================================================
            # STEP 1: Text Correction
            # ============================================================
            print("DEBUG [SearchService]: Calling text_corrector.correct...")
            correction_result = text_corrector.correct(raw_text)
            print(f"DEBUG [SearchService]: Correction result: {correction_result}")
            corrected_text = correction_result.get('corrected_text', raw_text)
            print(f"DEBUG [SearchService]: Using corrected_text='{corrected_text}'")
            
            # ============================================================
            # STEP 2: Try FAISS Retrieval
            # ============================================================
            if image:
                logger.info(f"[Search] Using Late Fusion search with image: {image}")
                print(f"DEBUG [SearchService]: Image present, calling FAISSRetrievalService.search_late_fusion...")
                faiss_result = FAISSRetrievalService.search_late_fusion(
                    text=corrected_text,
                    image_path=image,
                    top_k=10
                )
            else:
                logger.info(f"[Search] Using Text-only search")
                print(f"DEBUG [SearchService]: No image, calling FAISSRetrievalService.search_text...")
                faiss_result = FAISSRetrievalService.search_text(
                    text=corrected_text,
                    top_k=10
                )
            
            print(f"DEBUG [SearchService]: FAISS result: {faiss_result}")
            
            # Handle different response formats (products vs results, success vs status)
            faiss_products = faiss_result.get('products') or faiss_result.get('results') or []
            is_success = faiss_result.get('success') is True or faiss_result.get('status') == 'success'
            
            faiss_success = is_success and len(faiss_products) > 0
            print(f"DEBUG [SearchService]: faiss_success={faiss_success}, product_count={len(faiss_products)}")
            
            # ============================================================
            # STEP 3: Build products list (FAISS or fallback)
            # ============================================================
            if faiss_success:
                # FAISS returned results - use them
                print("DEBUG [SearchService]: Using FAISS results")
                products = [
                    {'product_id': p['product_id'], 'score': p.get('score', 1.0)}
                    for p in faiss_products
                ]
                logger.info(f"[Search] FAISS returned {len(products)} products")
            else:
                # FAISS failed or empty - fallback to DB search
                # Spec: SELECT product_id, name, price FROM product 
                #       WHERE name ILIKE %corrected_text% ORDER BY name ASC LIMIT 20
                logger.info(f"[Search] FAISS unavailable, falling back to DB search")
                print("DEBUG [SearchService]: FAISS unavailable/empty, falling back to DB search")
                start_db = time.time()
                search_term = f"%{corrected_text}%"
                print(f"DEBUG [SearchService]: DB search term: '{search_term}'")
                
                db_products = Product.query.filter(
                    Product.name.ilike(search_term)
                ).order_by(Product.name.asc()).limit(20).all()
                
                print(f"DEBUG [SearchService]: DB returned {len(db_products)} products")
                
                # Use fake score = 1.0 for fallback results per spec
                products = [
                    {'product_id': p.product_id, 'score': 1.0}
                    for p in db_products
                ]
                db_duration = (time.time() - start_db) * 1000
                logger.info(f"[Search] DB fallback returned {len(products)} products (took {db_duration:.2f}ms)")
            
            # ============================================================
            # STEP 4: Insert search_query record
            # ============================================================
            print("DEBUG [SearchService]: Saving search_query to DB...")
            search_query = SearchQuery(
                raw_text=raw_text,
                corrected_text=corrected_text
            )
            db.session.add(search_query)
            db.session.flush()  # Get search_id
            print(f"DEBUG [SearchService]: Generated search_id={search_query.search_id}")
            
            # ============================================================
            # STEP 5: Insert retrieve records
            # ============================================================
            print(f"DEBUG [SearchService]: Saving {len(products)} retrieve records...")
            for rank, product_info in enumerate(products, start=1):
                retrieve = Retrieve(
                    search_id=search_query.search_id,
                    product_id=product_info['product_id'],
                    rank=rank,
                    weight=product_info['score']
                )
                db.session.add(retrieve)
            
            db.session.commit()
            print("DEBUG [SearchService]: DB commit successful")
            
            total_duration = (time.time() - start_total) * 1000
            logger.info(f"[Search] Completed search_id={search_query.search_id} in {total_duration:.2f}ms")
            
            return {
                'search_id': search_query.search_id
            }
            
        except Exception as e:
            print(f"DEBUG [SearchService]: EXCEPTION: {e}")
            db.session.rollback()
            total_duration = (time.time() - start_total) * 1000
            logger.error(f"[Search] Error executing search: {e} (failed after {total_duration:.2f}ms)")
            raise
    
    @staticmethod
    def get_search_by_id(search_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a search query with its full results.
        
        Returns the search with all product details including:
        - brand name
        - first image URL
        - category names list
        
        SQL per work.txt spec:
            SELECT q.corrected_text, r.rank, r.score, p.product_id, p.name, p.price,
                   b.name AS brand_name, img.url AS image_url,
                   ARRAY_REMOVE(ARRAY_AGG(DISTINCT c.name), NULL) AS category_names
            FROM retrieve r
            JOIN search_query q ON q.search_id = r.search_id
            JOIN product p ON p.product_id = r.product_id
            LEFT JOIN brand b ON b.brand_id = p.brand_id
            LEFT JOIN LATERAL (SELECT url FROM product_image pi 
                               WHERE pi.product_id = p.product_id 
                               ORDER BY pi.image_no ASC LIMIT 1) AS img ON TRUE
            LEFT JOIN product_category pc ON pc.product_id = p.product_id
            LEFT JOIN category c ON c.category_id = pc.category_id
            WHERE r.search_id = %s
            GROUP BY q.corrected_text, r.rank, r.score, p.product_id, p.name, p.price, b.name, img.url
            ORDER BY r.rank ASC;
        
        Returns:
            dict with search_id, corrected_text, and results list
        """
        try:
            # Check if search exists
            search_query = SearchQuery.query.get(search_id)
            if not search_query:
                return None
            
            # Execute the complex query using raw SQL for efficiency
            sql = """
                SELECT
                    q.corrected_text,
                    r.rank,
                    r.weight AS score,
                    p.product_id,
                    p.name,
                    p.price,
                    b.name AS brand_name,
                    b.brand_id AS brand_id,
                    ARRAY_REMOVE(ARRAY_AGG(pi.url ORDER BY pi.image_no ASC), NULL) AS images,
                    r.is_relevant
                FROM retrieve r
                JOIN search_query q ON q.search_id = r.search_id
                JOIN product p ON p.product_id = r.product_id
                LEFT JOIN brand b ON b.brand_id = p.brand_id
                LEFT JOIN product_image pi ON pi.product_id = p.product_id
                WHERE r.search_id = :search_id
                GROUP BY
                    q.corrected_text,
                    r.rank, r.weight,
                    p.product_id, p.name, p.price,
                    b.name, b.brand_id,
                    r.is_relevant
                ORDER BY r.rank ASC;
            """
            
            result = db.session.execute(db.text(sql), {'search_id': search_id})
            rows = result.fetchall()
            
            if not rows:
                # Search exists but has no results
                return {
                    'search_id': search_id,
                    'raw_text': search_query.raw_text,
                    'corrected_text': search_query.corrected_text,
                    'products': []
                }
            
            # Build response
            corrected_text = rows[0][0]  # Same for all rows
            products = []
            
            # Get upload folder path
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads/products')
            
            for row in rows:
                # Convert image paths to base64
                image_paths = row[8] if row[8] else []
                images_base64 = []
                
                for img_path in image_paths:
                    # img_path is like "/uploads/products/filename.jpg"
                    filename = os.path.basename(img_path)
                    file_path = os.path.join(upload_folder, filename)
                    
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, 'rb') as f:
                                img_data = f.read()
                            
                            # Get mimetype
                            mimetype, _ = mimetypes.guess_type(file_path)
                            if not mimetype:
                                mimetype = 'image/jpeg'
                            
                            # Encode to base64
                            b64_data = base64.b64encode(img_data).decode('utf-8')
                            images_base64.append(f"data:{mimetype};base64,{b64_data}")
                        except Exception as e:
                            logger.warning(f"[Search] Failed to read image {file_path}: {e}")
                
                products.append({
                    'product_id': row[3],
                    'name': row[4],
                    'price': float(row[5]) if row[5] else None,
                    'rank': row[1],
                    'score': float(row[2]) if row[2] else None,
                    'brand': {'brand_id': row[7], 'name': row[6]} if row[6] else None,
                    'images': images_base64,
                    'is_relevant': row[9]
                })
            
            return {
                'search_id': search_id,
                'raw_text': search_query.raw_text,
                'corrected_text': corrected_text,
                'products': products
            }
            
        except Exception as e:
            logger.error(f"[Search] Error getting search by id: {e}")
            raise
    
    @staticmethod
    def record_click(search_id: int, product_id: int) -> bool:
        """Record a click on a search result."""
        retrieve = Retrieve.query.filter_by(
            search_id=search_id,
            product_id=product_id
        ).first()
        
        if not retrieve:
            return False
        
        retrieve.is_clicked = True
        db.session.commit()
        return True
    
    @staticmethod
    def record_feedback(search_id: int, product_id: int, is_relevant: bool) -> bool:
        """Record feedback on a search result."""
        retrieve = Retrieve.query.filter_by(
            search_id=search_id,
            product_id=product_id
        ).first()
        
        if not retrieve:
            return False
        
        retrieve.is_relevant = is_relevant
        db.session.commit()
        return True
    
    @staticmethod
    def get_metrics() -> Dict[str, Any]:
        """Get search and feedback metrics."""
        total_searches = SearchQuery.query.count()
        total_clicks = Retrieve.query.filter(Retrieve.is_clicked == True).count()
        positive_feedback = Retrieve.query.filter(Retrieve.is_relevant == True).count()
        negative_feedback = Retrieve.query.filter(Retrieve.is_relevant == False).count()
        total_feedback = positive_feedback + negative_feedback
        
        total_results = Retrieve.query.count()
        ctr = total_clicks / total_results if total_results > 0 else 0
        
        avg_time = db.session.query(
            db.func.avg(SearchQuery.time_to_retrieve)
        ).scalar() or 0
        
        return {
            "total_searches": total_searches,
            "total_clicks": total_clicks,
            "total_feedback": total_feedback,
            "positive_feedback": positive_feedback,
            "negative_feedback": negative_feedback,
            "click_through_rate": round(ctr, 4),
            "avg_retrieval_time_ms": round(float(avg_time), 2)
        }
