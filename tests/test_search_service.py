import pytest, os, sys, unittest
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from services.search_service import SearchService

@pytest.fixture
def mock_db():
    with patch('services.search_service.db') as m: yield m

@pytest.fixture
def mock_corrector():
    with patch('services.search_service.text_corrector_service') as m:
        m.correct.return_value = {'corrected_text': 'corrected query', 'engine': 'mock', 'latency_ms': 10}
        yield m

@pytest.fixture
def mock_faiss():
    with patch('services.search_service.faiss_service') as m:
        m.search_text.return_value = {'products': [{'product_id':1,'score':0.95}], 'success': True, 'status': 'success'}
        m.search_late_fusion.return_value = {'products': [{'product_id':3,'score':0.99}], 'success': True, 'status': 'success'}
        yield m

@pytest.fixture
def mock_models():
    with patch('services.search_service.get_selected_models') as m:
        m.return_value = {'fusion_endpoint':'late','textual_model':'m','visual_model':'m','fused_model':'m'}
        yield m

class TestSearchService:
    def test_execute_search_basic(self, mock_db, mock_corrector, mock_faiss, mock_models):
        with patch('services.search_service.SearchQuery') as MQS, \
             patch('services.search_service.Retrieve'), \
             patch('services.search_service.SearchTime'):
            sq = MagicMock(); sq.search_id = 123; MQS.return_value = sq
            r = SearchService.execute_search("test query")
            assert r == {'search_id': 123}

    def test_execute_search_late_fusion(self, mock_db, mock_corrector, mock_faiss, mock_models):
        with patch('services.search_service.SearchQuery') as MQS, \
             patch('services.search_service.Retrieve'), \
             patch('services.search_service.SearchTime'):
            sq = MagicMock(); sq.search_id = 456; MQS.return_value = sq
            SearchService.execute_search("text", image="path/to/i.jpg")
            mock_faiss.search_late_fusion.assert_called_once()
            mock_faiss.search_text.assert_not_called()

    def test_execute_search_fallback(self, mock_db, mock_corrector, mock_faiss, mock_models):
        mock_faiss.search_text.return_value = {'success': False, 'products': []}
        with patch('services.search_service.SearchQuery') as MQS, \
             patch('services.search_service.Retrieve'), \
             patch('services.search_service.SearchTime'):
            sq = MagicMock(); sq.search_id = 999; MQS.return_value = sq
            assert SearchService.execute_search("query") == {'search_id': 999}

    def test_execute_rawtext_search(self, mock_db, mock_faiss, mock_models):
        with patch('services.search_service.SearchQuery') as MQS, \
             patch('services.search_service.Retrieve') as MRet, \
             patch('services.search_service.SearchTime'):
            orig = MagicMock(); orig.raw_text = "original raw query"
            MQS.query.get.return_value = orig
            new_sq = MagicMock(); new_sq.search_id = 888; MQS.return_value = new_sq
            ret = MagicMock(); MRet.query.filter_by.return_value.all.return_value = [ret]
            r = SearchService.execute_rawtext_search(original_search_id=111)
            assert r == {'new_search_id': 888, 'original_search_id': 111}
            assert ret.rawtext_used is True

    def test_get_search_by_id(self, mock_db):
        with patch('services.search_service.SearchQuery') as MQS:
            sq = MagicMock(); sq.raw_text="x"; sq.corrected_text="y"; sq.search_mode="std"; sq.correction_enabled=True
            MQS.query.get.return_value = sq
            mr = MagicMock(); mr.fetchall.return_value = []; mock_db.session.execute.return_value = mr
            assert SearchService.get_search_by_id(1) is not None
            MQS.query.get.return_value = None
            assert SearchService.get_search_by_id(999) is None

    def test_record_click_and_feedback(self, mock_db):
        with patch('services.search_service.Retrieve') as MR:
            ret = MagicMock(); MR.query.filter_by.return_value.first.return_value = ret
            assert SearchService.record_click(1, 2) is True and ret.is_clicked is True
            assert SearchService.record_feedback(1, 2, True) is True and ret.is_relevant is True
            MR.query.filter_by.return_value.first.return_value = None
            assert SearchService.record_click(1, 999) is False

    def test_update_client_metrics(self, mock_db):
        with patch('services.search_service.SearchTime') as MST:
            st = MagicMock(); MST.query.get.return_value = st
            assert SearchService.update_client_metrics(1, 150.0, 200.0) is True
            MST.query.get.return_value = None
            assert SearchService.update_client_metrics(1, 150.0, 200.0) is False

    def test_get_metrics(self, mock_db):
        with patch('services.search_service.SearchQuery') as MQS, \
             patch('services.search_service.Retrieve') as MR, \
             patch('services.search_service.SearchTime'):
            MQS.query.count.return_value = 1000
            mf = MagicMock(); mf.count.side_effect = [500, 200, 50]
            MR.query.filter.return_value = mf; MR.query.count.return_value = 2000
            mock_db.session.query.return_value.scalar.side_effect = [300.5, 350.5]
            r = SearchService.get_metrics()
            assert r['total_searches'] == 1000 and r['click_through_rate'] == 0.25

    def test_convert_to_jpg(self):
        from services.search_service import convert_to_jpg
        import tempfile, os
        from PIL import Image
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tf:
            png_path = tf.name
        Image.new('RGB', (1,1), color='red').save(png_path, 'PNG')
        result = convert_to_jpg(png_path)
        assert result.endswith('.jpg')
        for f in [result, png_path]:
            try: os.unlink(f)
            except: pass

    def test_execute_iwt_cross_modal(self, mock_db, mock_corrector, mock_faiss, mock_models):
        with patch('services.search_service.SearchQuery') as MQS, \
             patch('services.search_service.Retrieve'), \
             patch('services.search_service.SearchTime'):
            sq = MagicMock(); sq.search_id = 777; MQS.return_value = sq
            mock_faiss.search_image_by_text.return_value = {'products':[{'product_id':5,'score':0.9}],'success':True}
            SearchService.execute_search("text", search_mode="iwt")
            mock_faiss.search_image_by_text.assert_called_once()

    def test_execute_twi_cross_modal(self, mock_db, mock_corrector, mock_faiss, mock_models):
        with patch('services.search_service.SearchQuery') as MQS, \
             patch('services.search_service.Retrieve'), \
             patch('services.search_service.SearchTime'):
            sq = MagicMock(); sq.search_id = 778; MQS.return_value = sq
            mock_faiss.search_text_by_image.return_value = {'products':[{'product_id':6,'score':0.8}],'success':True}
            SearchService.execute_search("text", image="/t.jpg", search_mode="twi")
            mock_faiss.search_text_by_image.assert_called_once()

    def test_execute_search_with_image(self, mock_db, mock_corrector, mock_faiss, mock_models):
        with patch('services.search_service.SearchQuery') as MQS, \
             patch('services.search_service.Retrieve'), \
             patch('services.search_service.SearchTime'):
            sq = MagicMock(); sq.search_id = 321; MQS.return_value = sq
            r = SearchService.execute_search("text", image="uploads/q.jpg", correction_enabled=False, search_mode="std")
            assert r == {'search_id': 321}
            assert MQS.call_args.kwargs['query_image_path'] == "uploads/q.jpg"

    def test_timing_persisted(self, mock_db, mock_corrector, mock_faiss, mock_models):
        with patch('services.search_service.SearchQuery') as MQS, \
             patch('services.search_service.Retrieve'), \
             patch('services.search_service.SearchTime') as MST:
            sq = MagicMock(); sq.search_id = 555; MQS.return_value = sq
            SearchService.execute_search("timing test", correction_enabled=True)
            kwargs = MST.call_args.kwargs
            assert kwargs['search_id'] == 555
            assert 'correction_time' in kwargs and 'faiss_time' in kwargs

    def test_record_feedback_not_found(self, mock_db):
        with patch('services.search_service.Retrieve') as MR:
            MR.query.filter_by.return_value.first.return_value = None
            assert SearchService.record_feedback(1, 2, True) is False

    def test_update_client_metrics_exception(self, mock_db):
        with patch('services.search_service.SearchTime') as MST:
            MST.query.get.return_value = MagicMock()
            mock_db.session.commit.side_effect = Exception()
            assert SearchService.update_client_metrics(1, 1, 1) is False

    def test_rawtext_search_invalid_id(self, mock_db):
        with pytest.raises(ValueError, match="Invalid original_search_id"):
            SearchService.execute_rawtext_search(original_search_id="abc")

    def test_rawtext_search_not_found(self, mock_db):
        with patch('services.search_service.SearchQuery') as MQS:
            MQS.query.get.return_value = None
            with pytest.raises(ValueError, match="not found"):
                SearchService.execute_rawtext_search(original_search_id=999)

    def test_execute_search_exception_rollback(self, mock_db, mock_corrector, mock_faiss, mock_models):
        with patch('services.search_service.SearchQuery') as MQS:
            MQS.return_value = MagicMock()
            mock_db.session.flush.side_effect = Exception("DB error")
            with pytest.raises(Exception):
                SearchService.execute_search("query")
            mock_db.session.rollback.assert_called_once()

    def test_get_search_by_id_empty(self, mock_db):
        with patch('services.search_service.SearchQuery') as MQS:
            sq = MagicMock(); sq.raw_text="x"; sq.corrected_text="y"; sq.search_mode="std"; sq.correction_enabled=True
            MQS.query.get.return_value = sq
            mr = MagicMock(); mr.fetchall.return_value = []; mock_db.session.execute.return_value = mr
            r = SearchService.get_search_by_id(1)
            assert r is not None and len(r['products']) == 0

    def test_get_search_by_id_with_products(self, mock_db):
        with patch('services.search_service.SearchQuery') as MQS:
            sq = MagicMock(); sq.raw_text="x"; sq.corrected_text="y"; sq.search_mode="std"; sq.correction_enabled=True
            sq.query_image_path = None
            MQS.query.get.return_value = sq
            row = ["y","x",1,0.95,0.9,0.8,0.85,"late_fusion","tm","vm",201,"P",99.99,"B",10,["/u/t.jpg"],True]
            mr = MagicMock(); mr.fetchall.return_value = [row]; mock_db.session.execute.return_value = mr
            with patch('flask.current_app') as ca:
                ca.config.get.return_value = '/tmp'
                with patch('os.path.exists', return_value=True), \
                     patch('builtins.open', unittest.mock.mock_open(read_data=b'img')), \
                     patch('mimetypes.guess_type', return_value=('image/jpeg', None)):
                    r = SearchService.get_search_by_id(1)
                    assert r is not None and len(r['products']) == 1

    def test_db_fallback_search(self, mock_db):
        with patch('services.search_service.SearchQuery') as MQS:
            sq = MagicMock(); sq.raw_text = "test phone"; MQS.query.get.return_value = sq
            mp1 = MagicMock(spec=['product_id','name','price','description','brand','images'])
            mp1.product_id=1; mp1.name="Test Phone"; mp1.price=299.99; mp1.description="desc"; mp1.brand=None; mp1.images=[]
            with patch('services.search_service.Product') as RealP:
                from models.product import Product as P
                RealP.name = P.name; RealP.description = P.description; RealP.brand = P.brand; RealP.images = P.images
                mf = MagicMock(); mf.options.return_value.order_by.return_value.all.return_value = [mp1]
                RealP.query.filter.return_value = mf
                with patch('flask.current_app') as ca:
                    ca.config.get.return_value = '/tmp'
                    r = SearchService.execute_db_fallback_search(123)
                    assert r['original_search_id'] == 123 and len(r['products']) == 1

    def test_graceful_degradation(self, mock_db, mock_faiss, mock_models):
        with patch('services.search_service.text_corrector_service') as mc:
            mc.correct.return_value = {'corrected_text':'raw query','success':False,'changed':False,'latency_ms':0}
            with patch('services.search_service.SearchQuery') as MQS, \
                 patch('services.search_service.Retrieve'), \
                 patch('services.search_service.SearchTime'):
                sq = MagicMock(); sq.search_id = 666; MQS.return_value = sq
                assert SearchService.execute_search("raw query", correction_enabled=True)['search_id'] == 666
