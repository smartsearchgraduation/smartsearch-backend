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
from models import db, SearchQuery, Retrieve, Product, SearchTime
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
    def execute_search(raw_text: str, image: Optional[str] = None, engine: Optional[str] = None) -> Dict[str, Any]:
        """
        Run a complete search from start to finish.
        
        This is the main entry point for searches. It handles the entire flow:
        spell correction, FAISS lookup, database fallback, and logging.
        
        Args:
            raw_text: What the user typed into the search box
            image: Optional path to an uploaded image for visual search
            engine: Optional correction engine to use
        
        Returns:
            A dict with 'search_id' that can be used to fetch the results
        """
        start_total = time.time()
        logger.info(f"")
        logger.info(f"{'='*60}")
        logger.info(f"[Search] 🔍 NEW SEARCH REQUEST")
        logger.info(f"{'='*60}")
        logger.info(f"[Search] 📝 Raw Text: '{raw_text}'")
        logger.info(f"[Search] 🖼️  Image: {image if image else 'None'}")
        logger.info(f"[Search] 🔧 Engine: {engine if engine else 'Default'}")
        
        try:
            # Step 1: Text Correction
            logger.info(f"")
            logger.info(f"[Search] ━━━ STEP 1: TEXT CORRECTION ━━━")
            correction_result = text_corrector_service.correct(raw_text, engine=engine)
            corrected_text = correction_result.get('corrected_text', raw_text)
            actual_engine = correction_result.get('engine', engine or 'UNKNOWN')
            correction_latency = correction_result.get('latency_ms', 0)  # Time from the correction service response
            
            logger.info(f"[Search] 📥 Input:     '{raw_text}'")
            logger.info(f"[Search] 📤 Output:    '{corrected_text}'")
            logger.info(f"[Search] 🔧 Engine:    {actual_engine}")
            logger.info(f"[Search] ⏱️  Duration:  {correction_latency:.2f}ms")
            logger.info(f"[Search] ✏️  Changed:   {raw_text != corrected_text}")
            
            # Step 2: FAISS Search
            logger.info(f"")
            logger.info(f"[Search] ━━━ STEP 2: FAISS RETRIEVAL ━━━")
            start_faiss = time.time()
            
            if image:
                logger.info(f"[Search] 🔀 Mode: Late Fusion (Text + Image)")
                faiss_result = faiss_service.search_late_fusion(
                    text=corrected_text,
                    image_path=image,
                    top_k=10
                )
            else:
                logger.info(f"[Search] 📝 Mode: Text-only Search")
                faiss_result = faiss_service.search_text(
                    text=corrected_text,
                    top_k=10
                )
            
            faiss_duration = (time.time() - start_faiss) * 1000
            
            # Log FAISS response details
            logger.info(f"[Search] 📊 FAISS Response Keys: {list(faiss_result.keys())}")
            logger.info(f"[Search] ✅ Status: {faiss_result.get('status', faiss_result.get('success', 'unknown'))}")

            # Parse FAISS results and extract model info
            faiss_products = faiss_result.get('products') or faiss_result.get('results') or []
            is_success = faiss_result.get('success') is True or faiss_result.get('status') == 'success'
            faiss_success = is_success and len(faiss_products) > 0
            
            # Extract model information from FAISS response
            textual_model_used = faiss_result.get('textual_model_name')
            visual_model_used = faiss_result.get('visual_model_name')

            logger.info(f"[Search] 📦 Products Found: {len(faiss_products)}")
            logger.info(f"[Search] ⏱️  Duration: {faiss_duration:.2f}ms")
            
            # Step 3: Process Results
            logger.info(f"")
            logger.info(f"[Search] ━━━ STEP 3: PROCESS RESULTS ━━━")
            
            if faiss_success:
                logger.info(f"[Search] ✅ Using FAISS results")
                products = [
                    {'product_id': p['product_id'], 'score': p.get('score', 1.0)}
                    for p in faiss_products
                ]
                
                # Log top 5 results with scores
                logger.info(f"[Search] 🏆 Top Results:")
                for i, p in enumerate(products[:5], 1):
                    logger.info(f"[Search]    {i}. product_id={p['product_id']}, score={p['score']:.6f}")
            else:
                logger.info(f"[Search] ⚠️  FAISS failed/empty, falling back to DB search")
                start_db = time.time()
                search_term = f"%{corrected_text}%"
                
                db_products = Product.query.filter(
                    Product.name.ilike(search_term)
                ).order_by(Product.name.asc()).limit(20).all()
                
                products = [
                    {'product_id': p.product_id, 'score': 1.0}
                    for p in db_products
                ]
                db_duration = (time.time() - start_db) * 1000
                logger.info(f"[Search] 📂 DB returned {len(products)} products (took {db_duration:.2f}ms)")
            
            # Step 4: Save to Database
            logger.info(f"")
            logger.info(f"[Search] ━━━ STEP 4: SAVE TO DATABASE ━━━")
            start_db_save = time.time()
            
            search_query = SearchQuery(
                raw_text=raw_text,
                corrected_text=corrected_text
            )
            db.session.add(search_query)
            db.session.flush()
            
            logger.info(f"[Search] 🆔 Search ID: {search_query.search_id}")
            logger.info(f"[Search] 💾 Saving {len(products)} retrieve records...")
            
            for rank, product_info in enumerate(products, start=1):
                retrieve = Retrieve(
                    search_id=search_query.search_id,
                    product_id=product_info['product_id'],
                    rank=rank,
                    weight=product_info['score'],
                    textual_model_name=textual_model_used,
                    visual_model_name=visual_model_used,
                    correction_engine=actual_engine
                )
                db.session.add(retrieve)
            
            db.session.commit()
            db_save_duration = (time.time() - start_db_save) * 1000
            
            # Save SearchTime metrics
            backend_total_duration = (time.time() - start_total) * 1000
            
            search_time = SearchTime(
                search_id=search_query.search_id,
                correction_time=correction_latency,
                faiss_time=faiss_duration,
                db_time=db_save_duration,
                backend_total_time=backend_total_duration
            )
            db.session.add(search_time)
            db.session.commit()
            
            logger.info(f"[Search] ✅ Saved successfully in {db_save_duration:.2f}ms")
            
            # Final Summary
            total_duration = (time.time() - start_total) * 1000
            logger.info(f"")
            logger.info(f"[Search] ━━━ SEARCH COMPLETE ━━━")
            logger.info(f"[Search] 🆔 Search ID: {search_query.search_id}")
            logger.info(f"[Search] 📦 Total Products: {len(products)}")
            logger.info(f"[Search] ⏱️  Total Time: {total_duration:.2f}ms")
            logger.info(f"[Search]    ├─ Correction: {correction_latency:.2f}ms")
            logger.info(f"[Search]    ├─ FAISS:      {faiss_duration:.2f}ms")
            logger.info(f"[Search]    └─ DB Save:    {db_save_duration:.2f}ms")
            logger.info(f"{'='*60}")
            
            return {
                'search_id': search_query.search_id
            }
            
        except Exception as e:
            db.session.rollback()
            total_duration = (time.time() - start_total) * 1000
            logger.error(f"[Search] ❌ Error executing search: {e} (failed after {total_duration:.2f}ms)")
            raise
    
    @staticmethod
    def execute_rawtext_search(original_search_id: int, image: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a search using raw text from the original search (without correction).
        
        This is called when the user clicks "search with raw text" button in frontend.
        It retrieves the original search's raw_text and searches FAISS directly
        without spell correction.
        
        Args:
            original_search_id: The ID of the original search to get raw_text from
            image: Optional path to an uploaded image for visual search
        
        Returns:
            A dict with 'new_search_id' that can be used to fetch the results
        """
        start_total = time.time()
        
        # Ensure original_search_id is an integer to avoid DB type mismatch
        try:
            original_search_id = int(original_search_id)
        except (ValueError, TypeError):
             raise ValueError(f"Invalid original_search_id: {original_search_id}")

        logger.info(f"")
        logger.info(f"{'='*60}")
        logger.info(f"[Search] 🔍 NEW RAW TEXT SEARCH REQUEST")
        logger.info(f"{'='*60}")
        logger.info(f"[Search] 🆔 Original Search ID: {original_search_id}")
        logger.info(f"[Search] 🖼️  Image: {image if image else 'None'}")
        
        try:
            # Step 1: Retrieve Original Query
            logger.info(f"")
            logger.info(f"[Search] ━━━ STEP 1: RETRIEVE ORIGINAL QUERY ━━━")
            original_search = SearchQuery.query.get(original_search_id)
            if not original_search:
                raise ValueError(f"Original search with id {original_search_id} not found")
            
            raw_text = original_search.raw_text
            logger.info(f"[Search] 📝 Found Raw Text: '{raw_text}'")
            logger.info(f"[Search] ℹ️  Skipping spell correction")
            
            # Step 2: Search EXECUTION
            logger.info(f"")
            logger.info(f"[Search] ━━━ STEP 2: SEARCH EXECUTION ━━━")
            start_search = time.time()
            
            # Search FAISS with raw text (no correction)
            if image:
                logger.info(f"[Search] 🔀 Mode: Late Fusion (Text + Image)")
                faiss_result = faiss_service.search_late_fusion(
                    text=raw_text,
                    image_path=image,
                    top_k=10
                )
            else:
                logger.info(f"[Search] 📝 Mode: Text-only Search")
                faiss_result = faiss_service.search_text(
                    text=raw_text,
                    top_k=10
                )
            
            search_duration = (time.time() - start_search) * 1000

            # FAISS can return results in different formats, so handle both
            faiss_products = faiss_result.get('products') or faiss_result.get('results') or []
            is_success = faiss_result.get('success') is True or faiss_result.get('status') == 'success'

            faiss_success = is_success and len(faiss_products) > 0
            
            # Extract model information from FAISS response
            textual_model_used = faiss_result.get('textual_model_name')
            visual_model_used = faiss_result.get('visual_model_name')

            logger.info(f"[Search] 📊 FAISS Response Keys: {list(faiss_result.keys())}")
            logger.info(f"[Search] ✅ Status: {faiss_result.get('status', faiss_result.get('success', 'unknown'))}")
            logger.info(f"[Search] 📦 Products Found: {len(faiss_products)}")
            logger.info(f"[Search] ⏱️  Search Duration: {search_duration:.2f}ms")
            
            # Use FAISS results if we got them, otherwise fall back to database search
            if faiss_success:
                logger.info(f"[Search] ✅ Using FAISS results")
                products = [
                    {'product_id': p['product_id'], 'score': p.get('score', 1.0)}
                    for p in faiss_products
                ]
                
                # Log top 5 results with scores
                logger.info(f"[Search] 🏆 Top Results:")
                for i, p in enumerate(products[:5], 1):
                    logger.info(f"[Search]    {i}. product_id={p['product_id']}, score={p['score']:.6f}")
                    
            else:
                # FAISS failed or empty - fallback to DB search
                logger.info(f"[Search] ⚠️  FAISS unavailable/empty, falling back to DB search")
                start_db = time.time()
                search_term = f"%{raw_text}%"
                
                db_products = Product.query.filter(
                    Product.name.ilike(search_term)
                ).order_by(Product.name.asc()).limit(20).all()
                
                products = [
                    {'product_id': p.product_id, 'score': 1.0}
                    for p in db_products
                ]
                db_fallback_duration = (time.time() - start_db) * 1000
                logger.info(f"[Search] 📂 DB fallback returned {len(products)} products (took {db_fallback_duration:.2f}ms)")
            
            # Step 3: Save to Database
            logger.info(f"")
            logger.info(f"[Search] ━━━ STEP 3: SAVE TO DATABASE ━━━")
            start_db_save = time.time()
            
            # Create a new search record with raw_text = corrected_text (since no correction)
            new_search_query = SearchQuery(
                raw_text=raw_text,
                corrected_text=raw_text  # Same as raw_text since we skip correction
            )
            db.session.add(new_search_query)
            db.session.flush()  # Need the search_id before we can save results
            
            logger.info(f"[Search] 🆔 New Search ID: {new_search_query.search_id}")
            logger.info(f"[Search] 💾 Saving {len(products)} retrieve records...")
            
            # Save each product result with its rank and score
            for rank, product_info in enumerate(products, start=1):
                retrieve = Retrieve(
                    search_id=new_search_query.search_id,
                    product_id=product_info['product_id'],
                    rank=rank,
                    weight=product_info['score'],
                    textual_model_name=textual_model_used,
                    visual_model_name=visual_model_used,
                    correction_engine='rawtext'  # No correction applied
                )
                db.session.add(retrieve)
            
            logger.info(f"[Search] 🔄 Updating original search (ID: {original_search_id}) links...")
            
            # Update original search's retrieve records to mark rawtext_used and link new_search_id
            original_retrieves = Retrieve.query.filter_by(search_id=original_search_id).all()
            for retrieve in original_retrieves:
                retrieve.rawtext_used = True
                retrieve.new_search_id = new_search_query.search_id
            
            db.session.commit()
            
            db_save_duration = (time.time() - start_db_save) * 1000
            
            # Save SearchTime metrics
            backend_total_duration = (time.time() - start_total) * 1000
            
            search_time = SearchTime(
                search_id=new_search_query.search_id,
                correction_time=0,  # No correction for raw search
                faiss_time=search_duration, # Using search_duration as faiss_time here
                db_time=db_save_duration,
                backend_total_time=backend_total_duration
            )
            db.session.add(search_time)
            db.session.commit()

            logger.info(f"[Search] ✅ Saved successfully in {db_save_duration:.2f}ms")
            
            total_duration = (time.time() - start_total) * 1000
            
            # Final Summary
            logger.info(f"")
            logger.info(f"[Search] ━━━ RAW SEARCH COMPLETE ━━━")
            logger.info(f"[Search] 🆔 New Search ID: {new_search_query.search_id}")
            logger.info(f"[Search] 📦 Total Products: {len(products)}")
            logger.info(f"[Search] ⏱️  Total Time: {total_duration:.2f}ms")
            logger.info(f"[Search]    ├─ Search:     {search_duration:.2f}ms")
            logger.info(f"[Search]    └─ DB Save:    {db_save_duration:.2f}ms")
            logger.info(f"{'='*60}")
            
            return {
                'new_search_id': new_search_query.search_id,
                'original_search_id': original_search_id
            }
            
        except Exception as e:
            db.session.rollback()
            total_duration = (time.time() - start_total) * 1000
            logger.error(f"[Search] ❌ Error executing raw text search: {e} (failed after {total_duration:.2f}ms)")
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
                score = float(row[2]) if row[2] else None
                if score is not None and score <= 0.465:
                    continue

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
    def update_client_metrics(search_id: int, search_duration: float, product_load_duration: float) -> bool:
        """
        Update client-side performance metrics for a search.
        
        Args:
            search_id: The ID of the search to update.
            search_duration: Time taken for the search request (ms).
            product_load_duration: Time taken to load product resources (ms).
            
        Returns:
            bool: True if updated successfully, False otherwise.
        """
        try:
            search_time = SearchTime.query.get(search_id)
            if not search_time:
                # Iterate to try and find if it was created but not committed yet? No, it should be there.
                # Maybe create it if missing? For now just log warning.
                logger.warning(f"[Analytics] SearchTime not found for search_id={search_id}")
                return False
                
            search_time.search_duration = search_duration
            search_time.product_load_duration = product_load_duration
            db.session.commit()
            
            logger.info(f"[Analytics] 📊 Updated client metrics for search {search_id}")
            return True
        except Exception as e:
            logger.error(f"[Analytics] ❌ Error updating client metrics: {e}")
            return False

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
        
        # Also get avg backend total time from new table
        avg_backend = db.session.query(
            db.func.avg(SearchTime.backend_total_time)
        ).scalar() or 0
        
        return {
            "total_searches": total_searches,
            "total_clicks": total_clicks,
            "total_feedback": total_feedback,
            "positive_feedback": positive_feedback,
            "negative_feedback": negative_feedback,
            "click_through_rate": round(ctr, 4),
            "avg_retrieval_time_ms": round(float(avg_time), 2),
            "avg_backend_total_time_ms": round(float(avg_backend), 2)
        }

