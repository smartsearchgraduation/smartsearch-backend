"""
The main search orchestrator for handling user queries.
This service coordinates the entire search flow: it first corrects any typos,
then retrieves relevant products from FAISS, and falls back to database search
if FAISS is unavailable.
"""
import logging
import base64
import os
import time
import mimetypes
from typing import Dict, Any, List, Optional

from flask import current_app
from models import db, SearchQuery, Retrieve, Product
from .text_corrector_service import text_corrector_service
from .faiss_retrieval_service import faiss_service

logger = logging.getLogger(__name__)


class SearchService:
    """
    The heart of our search functionality.
    
    When a user searches for something, this service:
    1. Fixes any typos in their query
    2. Asks FAISS for the most relevant products
    3. Falls back to a simple database search if FAISS is down
    4. Saves everything to the database for analytics
    """
    
    @staticmethod
    def execute_search(raw_text: str, image: Optional[str] = None) -> Dict[str, Any]:
        """
        Run a complete search from start to finish.
        
        This is the main entry point for searches. It handles the entire flow:
        spell correction, FAISS lookup, database fallback, and logging.
        
        Args:
            raw_text: What the user typed into the search box
            image: Optional path to an uploaded image for visual search
        
        Returns:
            A dict with 'search_id' that can be used to fetch the results
        """
        start_total = time.time()
        logger.info(f"[Search] Starting search for raw_text: '{raw_text}', image: {image}")
        
        
        try:
            # First, fix any typos in the search query
            correction_result = text_corrector_service.correct(raw_text)
            corrected_text = correction_result.get('corrected_text', raw_text)
            
            # Now search FAISS - use late fusion if we have an image
            if image:
                logger.info(f"[Search] Using Late Fusion search with image: {image}")
                faiss_result = faiss_service.search_late_fusion(
                    text=corrected_text,
                    image_path=image,
                    top_k=10
                )
            else:
                logger.info(f"[Search] Using Text-only search")
                faiss_result = faiss_service.search_text(
                    text=corrected_text,
                    top_k=10
                )
            
            # FAISS can return results in different formats, so handle both
            faiss_products = faiss_result.get('products') or faiss_result.get('results') or []
            is_success = faiss_result.get('success') is True or faiss_result.get('status') == 'success'
            
            faiss_success = is_success and len(faiss_products) > 0
            
            # Use FAISS results if we got them, otherwise fall back to database search
            if faiss_success:
                # Great, FAISS gave us results!
                products = [
                    {'product_id': p['product_id'], 'score': p.get('score', 1.0)}
                    for p in faiss_products
                ]
                logger.info(f"[Search] FAISS returned {len(products)} products")
            else:
                # FAISS failed or empty - fallback to DB search
                logger.info(f"[Search] FAISS unavailable, falling back to DB search")
                start_db = time.time()
                search_term = f"%{corrected_text}%"
                
                db_products = Product.query.filter(
                    Product.name.ilike(search_term)
                ).order_by(Product.name.asc()).limit(20).all()
                
                # For database results, we don't have real scores so just use 1.0
                products = [
                    {'product_id': p.product_id, 'score': 1.0}
                    for p in db_products
                ]
                db_duration = (time.time() - start_db) * 1000
                logger.info(f"[Search] DB fallback returned {len(products)} products (took {db_duration:.2f}ms)")
            
            # Save this search to the database for analytics
            search_query = SearchQuery(
                raw_text=raw_text,
                corrected_text=corrected_text
            )
            db.session.add(search_query)
            db.session.flush()  # Need the search_id before we can save results
            
            # Save each product result with its rank and score
            for rank, product_info in enumerate(products, start=1):
                retrieve = Retrieve(
                    search_id=search_query.search_id,
                    product_id=product_info['product_id'],
                    rank=rank,
                    weight=product_info['score']
                )
                db.session.add(retrieve)
            
            db.session.commit()
            
            total_duration = (time.time() - start_total) * 1000
            logger.info(f"[Search] Completed search_id={search_query.search_id} in {total_duration:.2f}ms")
            
            return {
                'search_id': search_query.search_id
            }
            
        except Exception as e:
            db.session.rollback()
            total_duration = (time.time() - start_total) * 1000
            logger.error(f"[Search] Error executing search: {e} (failed after {total_duration:.2f}ms)")
            raise
    
    @staticmethod
    def get_search_by_id(search_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch a previous search and all its results.
        
        This returns everything the frontend needs to display search results:
        product details, images (as base64), brand info, and relevance feedback.
        
        Args:
            search_id: The ID returned from execute_search()
        
        Returns:
            Full search data with products, or None if the search doesn't exist
        """
        try:
            # First make sure this search actually exists
            search_query = SearchQuery.query.get(search_id)
            if not search_query:
                return None
            
            # Use raw SQL here since we need some complex joins and aggregations
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
        """Mark that a user clicked on a specific search result."""
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
        """Save whether a user found a search result helpful (thumbs up/down)."""
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
        """Get overall search performance stats (clicks, feedback, response times)."""
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
