import pytest
import os
import sys
import base64
import unittest
from unittest.mock import patch, MagicMock

# Ensure the root directory is in sys.path so 'services' can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

app_mock = MagicMock()
app_mock.config.get.return_value = "mock_uploads"

# Pulling in the SearchService. We've mocked out its dependencies (DB, Flask, etc.) 
# so we can test the logic in isolation without any side effects.
from services.search_service import SearchService

@pytest.fixture
def mock_db():
    # Setting up a mock database session. This keeps our tests isolated and fast 
    # by preventing any real database interactions.
    with patch('services.search_service.db') as mock:
        yield mock

@pytest.fixture
def mock_text_corrector():
    # This mocks the "Did you mean..." spell correction logic. 
    # We want to ensure the service handles corrected queries properly.
    with patch('services.search_service.text_corrector_service') as mock:
        mock.correct.return_value = {
            'corrected_text': 'corrected query',
            'engine': 'mock_engine',
            'latency_ms': 10
        }
        yield mock

@pytest.fixture
def mock_faiss():
    # Fooling the system into thinking FAISS (our vector engine) is running.
    # We provide canned search results to test how the service processes them.
    with patch('services.search_service.faiss_service') as mock:
        mock.search_text.return_value = {
            'products': [
                {'product_id': 1, 'score': 0.95},
                {'product_id': 2, 'score': 0.85}
            ],
            'success': True,
            'status': 'success'
        }
        mock.search_late_fusion.return_value = {
            'products': [
                {'product_id': 3, 'score': 0.99}
            ],
            'success': True,
            'status': 'success'
        }
        yield mock

@pytest.fixture
def mock_product_query():
    # The "Plan B" mock: This simulates a generic SQL fallback when 
    # the advanced vector search (FAISS) doesn't find anything.
    with patch('services.search_service.Product') as mock_product:
        mock_q = MagicMock()
        mock_product.query.filter.return_value = mock_q
        mock_q.order_by.return_value = mock_q
        mock_q.limit.return_value = mock_q
        
        p1 = MagicMock()
        p1.product_id = 101
        
        mock_q.all.return_value = [p1]
        yield mock_product

class TestSearchService:

    @patch('services.search_service.get_selected_models')
    @patch('services.search_service.SearchTime')
    @patch('services.search_service.Retrieve')
    @patch('services.search_service.SearchQuery')
    def test_execute_search_persists_query_image_path(
        self,
        MockSearchQuery,
        MockRetrieve,
        MockSearchTime,
        mock_get_selected_models,
        mock_db,
        mock_text_corrector,
        mock_faiss,
    ):
        mock_sq_instance = MagicMock()
        mock_sq_instance.search_id = 321
        MockSearchQuery.return_value = mock_sq_instance
        mock_get_selected_models.return_value = {
            'fusion_endpoint': 'late',
            'textual_model': 'text-model',
            'visual_model': 'vision-model',
        }

        result = SearchService.execute_search(
            "text with image",
            image="uploads/products/query.jpg",
        )

        assert result == {'search_id': 321}
        assert MockSearchQuery.call_args.kwargs['query_image_path'] == "uploads/products/query.jpg"

    @patch('services.search_service.get_selected_models')
    @patch('services.search_service.convert_to_jpg', return_value='uploads/products/query.jpg')
    @patch('services.search_service.SearchTime')
    @patch('services.search_service.Retrieve')
    @patch('services.search_service.SearchQuery')
    def test_execute_search_uses_configured_fused_model_for_early_fusion(
        self,
        MockSearchQuery,
        MockRetrieve,
        MockSearchTime,
        mock_convert_to_jpg,
        mock_get_selected_models,
        mock_db,
        mock_text_corrector,
        mock_faiss,
    ):
        mock_sq_instance = MagicMock()
        mock_sq_instance.search_id = 322
        MockSearchQuery.return_value = mock_sq_instance
        mock_faiss.search_early_fusion.return_value = {
            'products': [{'product_id': 7, 'score': 0.91}],
            'success': True,
            'status': 'success',
        }
        mock_get_selected_models.return_value = {
            'fusion_endpoint': 'early',
            'textual_model': 'text-model',
            'visual_model': 'vision-model',
            'fused_model': 'fused-model',
        }

        SearchService.execute_search(
            "text with image",
            image="uploads/products/query.png",
        )

        mock_faiss.search_early_fusion.assert_called_once_with(
            text='corrected query',
            image_path='uploads/products/query.jpg',
            fused_model_name='fused-model',
            top_k=10,
        )

    @patch('services.search_service.build_query_image_response')
    @patch('services.search_service.SearchQuery')
    def test_get_search_by_id_returns_persisted_query_image(
        self,
        MockSearchQuery,
        mock_build_query_image_response,
        mock_db,
    ):
        mock_sq = MagicMock()
        mock_sq.raw_text = "telefon"
        mock_sq.corrected_text = "telefon"
        mock_sq.query_image_path = "uploads/products/query.jpg"
        MockSearchQuery.query.get.return_value = mock_sq
        mock_build_query_image_response.return_value = {
            "filename": "query.jpg",
            "url": "/uploads/products/query.jpg",
            "data_url": "data:image/jpeg;base64,ZmFrZQ==",
        }

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.session.execute.return_value = mock_result

        result = SearchService.get_search_by_id(77)

        assert result is not None
        assert result["query_image"] == {
            "filename": "query.jpg",
            "url": "/uploads/products/query.jpg",
            "data_url": "data:image/jpeg;base64,ZmFrZQ==",
        }
        mock_build_query_image_response.assert_called_once_with(
            "uploads/products/query.jpg"
        )

    @patch('services.search_service.SearchTime')
    @patch('services.search_service.Retrieve')
    @patch('services.search_service.SearchQuery')
    def test_execute_search_faiss_success(self, MockSearchQuery, MockRetrieve, MockSearchTime, mock_db, mock_text_corrector, mock_faiss):
        # The "Golden Path": Testing a successful vector search where 
        # FAISS finds products and everything gets logged to the database.
        mock_sq_instance = MagicMock()
        mock_sq_instance.search_id = 123
        MockSearchQuery.return_value = mock_sq_instance

        result = SearchService.execute_search("test query", engine="test_engine")

        # Let's see if we actually got ID 123 back
        assert result == {'search_id': 123}
        
        # Did our text corrector work correctly?
        mock_text_corrector.correct.assert_called_once_with("test query", engine="test_engine")
        
        # Did we knock on FAISS's door?
        mock_faiss.search_text.assert_called_once_with(text="corrected query", top_k=10)
        
        # Are our DB records straight? Should be 1 SearchQuery, 2 Retrieves, and 1 SearchTime.
        assert mock_db.session.add.call_count == 4 
        mock_db.session.flush.assert_called_once()
        assert mock_db.session.commit.call_count == 2
        
        # Let's be certain about the scores of the saved products
        MockRetrieve.assert_any_call(search_id=123, product_id=1, rank=1, weight=0.95)
        MockRetrieve.assert_any_call(search_id=123, product_id=2, rank=2, weight=0.85)

    @patch('services.search_service.SearchTime')
    @patch('services.search_service.Retrieve')
    @patch('services.search_service.SearchQuery')
    def test_execute_search_faiss_fallback(self, MockSearchQuery, MockRetrieve, MockSearchTime, mock_db, mock_text_corrector, mock_faiss, mock_product_query):
        # Testing the fallback mechanism: If FAISS strikes out or errors, 
        # we need to make sure the service automatically switches to a standard SQL search.
        mock_sq_instance = MagicMock()
        mock_sq_instance.search_id = 999
        MockSearchQuery.return_value = mock_sq_instance
        
        # Let's make FAISS fail us here
        mock_faiss.search_text.return_value = {'success': False, 'products': []}
        
        result = SearchService.execute_search("db fallback query")
        
        assert result == {'search_id': 999}
        mock_faiss.search_text.assert_called_once()
        
        # Plan B activated: Did we query the Product table?
        mock_product_query.query.filter.assert_called_once()
        
        # Let's test if the fallback result made it to the Retrieve table
        MockRetrieve.assert_any_call(search_id=999, product_id=101, rank=1, weight=1.0)

    @patch('services.search_service.SearchTime')
    @patch('services.search_service.Retrieve')
    @patch('services.search_service.SearchQuery')
    def test_execute_search_late_fusion(self, MockSearchQuery, MockRetrieve, MockSearchTime, mock_db, mock_text_corrector, mock_faiss):
        # Multimodal testing: Uploading an image along with text should 
        # trigger the 'Late Fusion' logic instead of a standard text search.
        mock_sq_instance = MagicMock()
        mock_sq_instance.search_id = 456
        MockSearchQuery.return_value = mock_sq_instance
        
        result = SearchService.execute_search("text with image", image="path/to/image.jpg")
        
        assert result == {'search_id': 456}
        
        # We should be calling the late fusion method directly instead of normal text search
        mock_faiss.search_late_fusion.assert_called_once_with(text="corrected query", image_path="path/to/image.jpg", top_k=10)
        mock_faiss.search_text.assert_not_called()
        
        # Checking if the product was nicely written to the Retrieve table
        MockRetrieve.assert_any_call(search_id=456, product_id=3, rank=1, weight=0.99)
        
    @patch('services.search_service.SearchQuery')
    def test_execute_search_exception_rollback(self, MockSearchQuery, mock_db, mock_text_corrector, mock_faiss):
        # What if the database hiccups mid-save? We expect the service 
        # to trigger a rollback so we don't end up with partial or corrupted data.
        mock_sq_instance = MagicMock()
        MockSearchQuery.return_value = mock_sq_instance
        
        # Intentionally forcing a crash during session flush
        mock_db.session.flush.side_effect = Exception("DB go boom!")
        
        with pytest.raises(Exception) as exc_info:
            SearchService.execute_search("query meant to fail")
            
        assert "DB go boom!" in str(exc_info.value)
        # Ensuring a rollback is triggered the moment it faults
        mock_db.session.rollback.assert_called_once()

    @patch('services.search_service.SearchTime')
    @patch('services.search_service.Retrieve')
    @patch('services.search_service.SearchQuery')
    def test_execute_rawtext_search(self, MockSearchQuery, MockRetrieve, MockSearchTime, mock_db, mock_faiss):
        # Edge case: If the user specifically wants a raw text search, 
        # we skip the fancy AI spell correction and search exactly what they typed.
        mock_orig_sq = MagicMock()
        mock_orig_sq.raw_text = "original raw query"
        MockSearchQuery.query.get.return_value = mock_orig_sq
        
        mock_new_sq = MagicMock()
        mock_new_sq.search_id = 888
        MockSearchQuery.return_value = mock_new_sq
        
        # Mocking the previous retrieve records so they can be updated later
        mock_orig_retrieve = MagicMock()
        MockRetrieve.query.filter_by.return_value.all.return_value = [mock_orig_retrieve]

        result = SearchService.execute_rawtext_search(original_search_id=111)
        
        assert result == {'new_search_id': 888, 'original_search_id': 111}
        
        # Making sure it didn't even look at the corrector and went to FAISS with the original raw query
        mock_faiss.search_text.assert_called_once_with(text="original raw query", top_k=10)
        
        # Hope we didn't forget to mark the old records as "hey, we used raw text for this"
        assert mock_orig_retrieve.rawtext_used is True
        assert mock_orig_retrieve.new_search_id == 888

    def test_execute_rawtext_search_invalid_id(self, mock_db):
        # Safety check: Ensuring the service rejects non-numeric or malformed 
        # search IDs instead of crashing the backend.
        with pytest.raises(ValueError) as exc_info:
            SearchService.execute_rawtext_search(original_search_id="nonsense_id_string")
        assert "Invalid original_search_id" in str(exc_info.value)

    @patch('services.search_service.SearchQuery')
    def test_execute_rawtext_search_not_found(self, MockSearchQuery, mock_db):
        # Error handling: If the frontend asks for a search ID that 
        # doesn't exist in our logs, we should raise a clear error and roll back.
        MockSearchQuery.query.get.return_value = None
        
        with pytest.raises(ValueError) as exc_info:
            SearchService.execute_rawtext_search(original_search_id=999)
        assert "not found" in str(exc_info.value).lower()
        # Guaranteeing that a rollback is called since the record wasn't found
        mock_db.session.rollback.assert_called_once()

    @patch('services.search_service.SearchQuery')
    def test_get_search_by_id_success(self, MockSearchQuery, mock_db):
        # Success story: Fetching historical search results and serving them 
        # back to the user's dashboard with correct product details.
        mock_sq = MagicMock()
        mock_sq.raw_text = "test raw"
        mock_sq.corrected_text = "test corrected"
        MockSearchQuery.query.get.return_value = mock_sq
        
        # For the test, let's have one entry with a really low score (0.10) so it gets filtered out (since the limit is >0.465).
        mock_row_1 = [
            "test corrected", # corrected_text
            1,                # rank
            0.95,             # weight/score (passes)
            201,              # product_id
            "Awesome Product",# name
            99.99,            # price
            "Test Brand",     # brand_name
            10,               # brand_id
            ["/uploads/products/test.jpg"], # images
            True              # is_relevant
        ]
        mock_row_2 = [
            "test corrected",
            2,
            0.10,             # weight/score (Waaaay too low, should be filtered!)
            202,
            "Irrelevant Product",
            10.00,
            "Another Brand",
            11,
            [],
            None
        ]
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row_1, mock_row_2]
        mock_db.session.execute.return_value = mock_result
        
        from flask import Flask
        app = Flask(__name__)
        app.config['UPLOAD_FOLDER'] = 'fake_upload_folder'
        
        # Opening up a fake application context
        with app.app_context(), \
             patch('os.path.exists', return_value=True), \
             patch('builtins.open', unittest.mock.mock_open(read_data=b'fake_image_data')), \
             patch('mimetypes.guess_type', return_value=('image/jpeg', None)):
            
            result = SearchService.get_search_by_id(777)
            
            # Let's see if everything is in order
            assert result is not None
            assert result['search_id'] == 777
            # 2nd product had a terrible score so it should've been filtered out, leaving us with 1.
            assert len(result['products']) == 1
            
            prod = result['products'][0]
            assert prod['product_id'] == 201
            assert prod['name'] == "Awesome Product"
            assert prod['price'] == 99.99
            
            # Crucial check: Did our images correctly convert to Base64 strings 
            # so the frontend can display them immediately?
            assert len(prod['images']) == 1
            assert prod['images'][0].startswith('data:image/jpeg;base64,')

    @patch('services.search_service.SearchQuery')
    def test_get_search_by_id_empty_results(self, MockSearchQuery, mock_db):
        # Ghost search: If a search query exists but its product results were 
        # cleared out, we should return an empty list gracefully, not an error.
        mock_sq = MagicMock()
        mock_sq.raw_text = "ghost word"
        mock_sq.corrected_text = "ghost word"
        MockSearchQuery.query.get.return_value = mock_sq
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [] # SQL returned nothing
        mock_db.session.execute.return_value = mock_result
        
        result = SearchService.get_search_by_id(777)
        
        # It should still return an object, just with an empty "products" array.
        assert result is not None
        assert result['raw_text'] == "ghost word"
        assert len(result['products']) == 0

    @patch('services.search_service.SearchQuery')
    def test_get_search_by_id_not_found(self, MockSearchQuery, mock_db):
        # We quietly return None if we get a search ID that simply isn't there...
        MockSearchQuery.query.get.return_value = None
        result = SearchService.get_search_by_id(999)
        assert result is None

    @patch('services.search_service.Retrieve')
    def test_record_click(self, MockRetrieve, mock_db):
        # Analytics check: When a user clicks a product, we need to log it 
        # precisely to improve our future search rankings.
        mock_ret = MagicMock()
        MockRetrieve.query.filter_by.return_value.first.return_value = mock_ret
        
        success = SearchService.record_click(search_id=1, product_id=2)
        
        assert success is True
        assert mock_ret.is_clicked is True
        mock_db.session.commit.assert_called_once()
        
    @patch('services.search_service.Retrieve')
    def test_record_click_not_found(self, MockRetrieve, mock_db):
        # Sometimes the frontend goes wild and tells us something was clicked when it doesn't exist. Let's return False without crashing.
        MockRetrieve.query.filter_by.return_value.first.return_value = None
        
        success = SearchService.record_click(search_id=1, product_id=999)
        assert success is False

    @patch('services.search_service.Retrieve')
    def test_record_feedback(self, MockRetrieve, mock_db):
        # Good for us, the guy found the search result helpful and gave it a thumbs up!
        mock_ret = MagicMock()
        MockRetrieve.query.filter_by.return_value.first.return_value = mock_ret
        
        success = SearchService.record_feedback(search_id=1, product_id=2, is_relevant=True)
        
        assert success is True
        assert mock_ret.is_relevant is True
        mock_db.session.commit.assert_called_once()
        
    @patch('services.search_service.Retrieve')
    def test_record_feedback_not_found(self, MockRetrieve, mock_db):
        # Awesome, the guy gave a thumbs up... but the product doesn't exist. Bummer.
        MockRetrieve.query.filter_by.return_value.first.return_value = None
        
        success = SearchService.record_feedback(search_id=1, product_id=2, is_relevant=True)
        assert success is False

    @patch('services.search_service.SearchTime')
    def test_update_client_metrics(self, MockSearchTime, mock_db):
        # Performance monitoring: Logging how many milliseconds the frontend 
        # took to render products helps us spot and fix bottlenecks.
        mock_st = MagicMock()
        MockSearchTime.query.get.return_value = mock_st
        
        success = SearchService.update_client_metrics(search_id=1, search_duration=150.0, product_load_duration=200.0)
        
        assert success is True
        assert mock_st.search_duration == 150.0
        assert mock_st.product_load_duration == 200.0
        # If we forget to commit, people will be angry. Let's make sure we did.
        mock_db.session.commit.assert_called_once()
        
    @patch('services.search_service.SearchTime')
    def test_update_client_metrics_not_found(self, MockSearchTime, mock_db):
        # If the search object vanished into thin air, just return False silently and move on. Nobody has to know :)
        MockSearchTime.query.get.return_value = None
        success = SearchService.update_client_metrics(search_id=1, search_duration=150.0, product_load_duration=200.0)
        assert success is False

    @patch('services.search_service.SearchTime')
    def test_update_client_metrics_exception(self, MockSearchTime, mock_db):
        # If the DB dies on us (Exception), gracefully return False.
        MockSearchTime.query.get.return_value = MagicMock()
        mock_db.session.commit.side_effect = Exception("Houston we have a problem!")
        success = SearchService.update_client_metrics(search_id=1, search_duration=150.0, product_load_duration=200.0)
        assert success is False

    @patch('services.search_service.SearchTime')
    @patch('services.search_service.Retrieve')
    @patch('services.search_service.SearchQuery')
    def test_get_metrics(self, MockSearchQuery, MockRetrieve, MockSearchTime, mock_db):
        # The Big Picture: Aggregating all logs to calculate KPIs like 
        # Click-Through Rate (CTR) and average retrieval speeds.
        MockSearchQuery.query.count.return_value = 1000
        
        mock_filter = MagicMock()
        MockRetrieve.query.filter.return_value = mock_filter
        
        # Faking the count replies for our filters
        # In order: total_clicks, positive_feedback, negative_feedback
        mock_filter.count.side_effect = [500, 200, 50] 
        MockRetrieve.query.count.return_value = 2000
        
        # Spoofing the SQL query that calculates the average times
        mock_db.session.query.return_value.scalar.side_effect = [300.5, 350.5] # avg_time, avg_backend
        
        result = SearchService.get_metrics()
        
        # Let's see if the math checks out on our stats:
        assert result['total_searches'] == 1000
        assert result['total_clicks'] == 500
        assert result['positive_feedback'] == 200
        assert result['negative_feedback'] == 50
        assert result['total_feedback'] == 250
        
        # 500 clicks / 2000 results = 0.25 (Not too shabby for a Click-Through-Rate!)
        assert result['click_through_rate'] == 0.25 
        assert result['avg_retrieval_time_ms'] == 300.5
        assert result['avg_backend_total_time_ms'] == 350.5
