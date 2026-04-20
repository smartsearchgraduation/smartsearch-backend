"""
API routes for bulk FAISS operations.
Provides endpoints to add all products from the database to FAISS index
and a simple web UI to trigger this operation.
"""

import os
import logging
from flask import Blueprint, request, jsonify, render_template_string, current_app
from models import db
from models.product import Product
from models.product_image import ProductImage
from sqlalchemy.orm import joinedload
from services.faiss_retrieval_service import faiss_service
from config.models import (
    AVAILABLE_MODELS,
    DEFAULT_TEXTUAL_MODEL,
    DEFAULT_VISUAL_MODEL,
    get_selected_models,
)

logger = logging.getLogger(__name__)

bulk_faiss_bp = Blueprint("bulk_faiss", __name__, url_prefix="/api/bulk-faiss")


def _get_valid_model_ids():
    """Use the FAISS-advertised model catalog when available, otherwise local config."""
    model_ids = faiss_service.get_available_model_ids()
    return model_ids or list(AVAILABLE_MODELS.keys())


# HTML template for the bulk import page
BULK_IMPORT_PAGE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FAISS Toplu Ürün Ekleme</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 50%, #0f0f23 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .container {
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            padding: 48px;
            max-width: 600px;
            width: 100%;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        }
        
        .header {
            text-align: center;
            margin-bottom: 40px;
        }
        
        .header h1 {
            color: #fff;
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 12px;
            background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .header p {
            color: rgba(255, 255, 255, 0.6);
            font-size: 14px;
        }
        
        .stats-card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 32px;
        }
        
        .stats-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        }
        
        .stats-row:last-child {
            border-bottom: none;
        }
        
        .stats-label {
            color: rgba(255, 255, 255, 0.7);
            font-size: 14px;
        }
        
        .stats-value {
            color: #60a5fa;
            font-size: 18px;
            font-weight: 600;
        }
        
        .btn-primary {
            width: 100%;
            padding: 18px 32px;
            font-size: 16px;
            font-weight: 600;
            color: #fff;
            background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            border: none;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 40px rgba(59, 130, 246, 0.4);
        }
        
        .btn-primary:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .btn-primary.loading::after {
            content: '';
            position: absolute;
            width: 20px;
            height: 20px;
            border: 2px solid transparent;
            border-top: 2px solid #fff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-left: 10px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .progress-section {
            margin-top: 32px;
            display: none;
        }
        
        .progress-section.active {
            display: block;
        }
        
        .progress-bar-container {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            height: 8px;
            overflow: hidden;
            margin-bottom: 16px;
        }
        
        .progress-bar {
            height: 100%;
            background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            border-radius: 8px;
            transition: width 0.3s ease;
            width: 0%;
        }
        
        .progress-text {
            text-align: center;
            color: rgba(255, 255, 255, 0.7);
            font-size: 14px;
        }
        
        .result-section {
            margin-top: 32px;
            display: none;
        }
        
        .result-section.active {
            display: block;
        }
        
        .result-card {
            background: rgba(34, 197, 94, 0.1);
            border: 1px solid rgba(34, 197, 94, 0.3);
            border-radius: 12px;
            padding: 20px;
        }
        
        .result-card.error {
            background: rgba(239, 68, 68, 0.1);
            border-color: rgba(239, 68, 68, 0.3);
        }
        
        .result-title {
            color: #22c55e;
            font-weight: 600;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .result-card.error .result-title {
            color: #ef4444;
        }
        
        .result-details {
            color: rgba(255, 255, 255, 0.7);
            font-size: 14px;
            line-height: 1.6;
        }
        
        .log-section {
            margin-top: 24px;
            max-height: 200px;
            overflow-y: auto;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 8px;
            padding: 16px;
            font-family: 'Consolas', monospace;
            font-size: 12px;
        }
        
        .log-entry {
            padding: 4px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .log-entry.success {
            color: #22c55e;
        }
        
        .log-entry.error {
            color: #ef4444;
        }
        
        .log-entry.info {
            color: #60a5fa;
        }
        
        .settings-card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
        }
        
        .settings-title {
            color: #fff;
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 20px;
        }
        
        .setting-row {
            margin-bottom: 16px;
        }
        
        .setting-label {
            display: block;
            color: rgba(255, 255, 255, 0.7);
            font-size: 13px;
            margin-bottom: 8px;
        }
        
        .setting-select {
            width: 100%;
            padding: 12px 16px;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            color: #fff;
            font-size: 14px;
            font-family: 'Inter', sans-serif;
            cursor: pointer;
            transition: all 0.2s ease;
            appearance: none;
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%2360a5fa' d='M6 8L1 3h10z'/%3E%3C/svg%3E");
            background-repeat: no-repeat;
            background-position: right 12px center;
        }
        
        .setting-select:hover {
            border-color: rgba(96, 165, 250, 0.5);
        }
        
        .setting-select:focus {
            outline: none;
            border-color: #60a5fa;
            box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.2);
        }
        
        .setting-select option {
            background: #1a1a3e;
            color: #fff;
            padding: 8px;
        }
        
        .setting-hint {
            color: rgba(255, 255, 255, 0.5);
            font-size: 12px;
            margin-top: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 FAISS Toplu Ürün Ekleme</h1>
            <p>Veritabanındaki tüm ürünleri FAISS index'ine ekleyin</p>
        </div>
        
        <div class="stats-card">
            <div class="stats-row">
                <span class="stats-label">Toplam Ürün Sayısı</span>
                <span class="stats-value" id="totalProducts">Yükleniyor...</span>
            </div>
            <div class="stats-row">
                <span class="stats-label">Görsel Sayısı</span>
                <span class="stats-value" id="totalImages">Yükleniyor...</span>
            </div>
            <div class="stats-row">
                <span class="stats-label">FAISS Durumu</span>
                <span class="stats-value" id="faissStatus">Kontrol ediliyor...</span>
            </div>
        </div>
        
        <div class="settings-card">
            <h3 class="settings-title">⚙️ Model Ayarları</h3>
            <div class="setting-row">
                <label class="setting-label" for="textualModel">Metin Modeli (Textual)</label>
                <select class="setting-select" id="textualModel">
                    {{ textual_options }}
                </select>
            </div>
            <div class="setting-row">
                <label class="setting-label" for="visualModel">Görsel Modeli (Visual)</label>
                <select class="setting-select" id="visualModel">
                    {{ visual_options }}
                </select>
            </div>
            <p class="setting-hint">💡 Aynı modeli kullanmak önerilir. Büyük modeller daha doğru ama daha yavaştır.</p>
        </div>
        
        <button class="btn-primary" id="startBtn" onclick="startBulkImport()">
            🔄 Tüm Ürünleri FAISS'e Ekle
        </button>
        
        <div class="progress-section" id="progressSection">
            <div class="progress-bar-container">
                <div class="progress-bar" id="progressBar"></div>
            </div>
            <p class="progress-text" id="progressText">İşlem başlıyor...</p>
        </div>
        
        <div class="result-section" id="resultSection">
            <div class="result-card" id="resultCard">
                <div class="result-title" id="resultTitle">
                    ✅ İşlem Tamamlandı
                </div>
                <div class="result-details" id="resultDetails"></div>
            </div>
        </div>
        
        <div class="log-section" id="logSection" style="display: none;"></div>
    </div>
    
    <script>
        // Sayfa yüklendiğinde istatistikleri al
        // DOMContentLoaded ve window.onload ile garantili çalıştırma
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', fetchStats);
        } else {
            // DOM zaten yüklendi, direkt çalıştır
            fetchStats();
        }
        
        async function fetchStats() {
            try {
                const response = await fetch('/api/bulk-faiss/stats');
                const data = await response.json();
                
                document.getElementById('totalProducts').textContent = data.total_products || 0;
                document.getElementById('totalImages').textContent = data.total_images || 0;
                document.getElementById('faissStatus').textContent = data.faiss_available ? '✅ Hazır' : '❌ Bağlanamadı';
            } catch (error) {
                console.error('Stats fetch error:', error);
                document.getElementById('totalProducts').textContent = 'Hata';
                document.getElementById('totalImages').textContent = 'Hata';
                document.getElementById('faissStatus').textContent = '❌ Hata';
            }
        }
        
        function addLog(message, type = 'info') {
            const logSection = document.getElementById('logSection');
            logSection.style.display = 'block';
            
            const entry = document.createElement('div');
            entry.className = 'log-entry ' + type;
            entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
            logSection.appendChild(entry);
            logSection.scrollTop = logSection.scrollHeight;
        }
        
        async function startBulkImport() {
            const btn = document.getElementById('startBtn');
            const progressSection = document.getElementById('progressSection');
            const resultSection = document.getElementById('resultSection');
            const logSection = document.getElementById('logSection');
            
            // UI'ı sıfırla
            btn.disabled = true;
            btn.classList.add('loading');
            btn.textContent = '⏳ İşlem Başlatılıyor...';
            progressSection.classList.add('active');
            resultSection.classList.remove('active');
            logSection.innerHTML = '';
            logSection.style.display = 'block';
            
            addLog('Toplu ekleme işlemi başlatılıyor...', 'info');
            
            // Model değerlerini al
            const textualModel = document.getElementById('textualModel').value;
            const visualModel = document.getElementById('visualModel').value;
            
            addLog(`Metin Modeli: ${textualModel}`, 'info');
            addLog(`Görsel Modeli: ${visualModel}`, 'info');
            
            try {
                const response = await fetch('/api/bulk-faiss/add-all', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        textual_model_name: textualModel,
                        visual_model_name: visualModel
                    })
                });
                
                const data = await response.json();
                
                if (data.status === 'success') {
                    // Başarı
                    document.getElementById('progressBar').style.width = '100%';
                    document.getElementById('progressText').textContent = 'Tamamlandı!';
                    
                    const resultCard = document.getElementById('resultCard');
                    resultCard.classList.remove('error');
                    
                    document.getElementById('resultTitle').innerHTML = '✅ İşlem Başarıyla Tamamlandı';
                    document.getElementById('resultDetails').innerHTML = `
                        <strong>Eklenen Ürün:</strong> ${data.details.successful_count}<br>
                        <strong>Başarısız:</strong> ${data.details.failed_count}<br>
                        <strong>Toplam Süre:</strong> ${(data.details.total_time_ms / 1000).toFixed(2)} saniye<br>
                        <strong>Metin Modeli:</strong> ${data.details.textual_model_name}<br>
                        <strong>Görsel Modeli:</strong> ${data.details.visual_model_name}
                    `;
                    
                    addLog(`Başarılı: ${data.details.successful_count} ürün eklendi`, 'success');
                    
                    if (data.details.failed_count > 0) {
                        addLog(`Başarısız: ${data.details.failed_count} ürün`, 'error');
                        data.details.errors.forEach(err => {
                            addLog(`  - Ürün ${err.product_id}: ${err.error}`, 'error');
                        });
                    }
                } else {
                    // Hata
                    const resultCard = document.getElementById('resultCard');
                    resultCard.classList.add('error');
                    
                    document.getElementById('resultTitle').innerHTML = '❌ Hata Oluştu';
                    document.getElementById('resultDetails').textContent = data.error || 'Bilinmeyen hata';
                    
                    addLog('Hata: ' + (data.error || 'Bilinmeyen hata'), 'error');
                }
                
                resultSection.classList.add('active');
                
            } catch (error) {
                console.error('Bulk import error:', error);
                
                const resultCard = document.getElementById('resultCard');
                resultCard.classList.add('error');
                
                document.getElementById('resultTitle').innerHTML = '❌ Bağlantı Hatası';
                document.getElementById('resultDetails').textContent = error.message;
                
                resultSection.classList.add('active');
                addLog('Bağlantı hatası: ' + error.message, 'error');
            } finally {
                btn.disabled = false;
                btn.classList.remove('loading');
                btn.textContent = '🔄 Tüm Ürünleri FAISS\'e Ekle';
            }
        }
    </script>
</body>
</html>
"""


@bulk_faiss_bp.route("/", methods=["GET"])
def bulk_import_page():
    """
    Render the bulk import web page.
    This provides a simple UI to trigger bulk FAISS import.
    Model options are dynamically loaded from config/models.py
    """
    # Generate HTML options for textual model dropdown
    textual_options = ""
    for model_id, display_name in AVAILABLE_MODELS.items():
        selected = " selected" if model_id == DEFAULT_TEXTUAL_MODEL else ""
        textual_options += f'<option value="{model_id}"{selected}>{display_name}</option>\n                    '

    # Generate HTML options for visual model dropdown
    visual_options = ""
    for model_id, display_name in AVAILABLE_MODELS.items():
        selected = " selected" if model_id == DEFAULT_VISUAL_MODEL else ""
        visual_options += f'<option value="{model_id}"{selected}>{display_name}</option>\n                    '

    # Render template with model options
    rendered_html = BULK_IMPORT_PAGE.replace("{{ textual_options }}", textual_options)
    rendered_html = rendered_html.replace("{{ visual_options }}", visual_options)

    return render_template_string(rendered_html)


@bulk_faiss_bp.route("/models", methods=["GET"])
def get_models():
    """
    Get available models for FAISS embeddings.
    Returns the model mapping from config/models.py with name and dimension.
    Format matches FAISS service response: {name, dimension}
    """
    from config.models import get_model_info

    models = [get_model_info(model_id) for model_id in AVAILABLE_MODELS.keys()]

    return jsonify(
        {
            "models": models,
            "defaults": {
                "textual": DEFAULT_TEXTUAL_MODEL,
                "visual": DEFAULT_VISUAL_MODEL,
            },
        }
    ), 200


@bulk_faiss_bp.route("/stats", methods=["GET"])
def get_stats():
    """
    Get statistics about products and FAISS availability.
    """
    try:
        from models.product_image import ProductImage

        total_products = Product.query.count()
        total_images = ProductImage.query.count()

        # Check FAISS availability by doing a simple test
        faiss_available = False
        try:
            import requests

            response = requests.get("http://localhost:5002/health", timeout=3)
            faiss_available = response.status_code == 200
        except:
            faiss_available = False

        return jsonify(
            {
                "total_products": total_products,
                "total_images": total_images,
                "faiss_available": faiss_available,
            }
        ), 200

    except Exception as e:
        logger.error(f"[BulkFAISS] Stats error: {e}")
        return jsonify(
            {
                "total_products": 0,
                "total_images": 0,
                "faiss_available": False,
                "error": str(e),
            }
        ), 500


@bulk_faiss_bp.route("/add-all", methods=["POST"])
def add_all_products():
    """
    Add all products from the database to FAISS index.

    This endpoint:
    1. Calls FAISS service to clear existing index (handled by FAISS)
    2. Adds all products from the database
    3. Waits after the first product for FAISS initialization (default: 60s)

    Request body (optional):
        - textual_model_name: Model for text embeddings (default from config)
        - visual_model_name: Model for image embeddings (default from config)
        - wait_duration_seconds: How long to wait after first product (default: 60)
        - delay_between_products_ms: Delay between each product (default: 0)
    """
    import time

    start_time = time.time()

    successful_count = 0
    failed_count = 0
    errors = []

    # Get configuration from request body
    data = request.get_json() or {}

    # Request'te model varsa onu kullan
    textual_model_name = data.get("textual_model_name")
    visual_model_name = data.get("visual_model_name")

    # Yoksa FAISS service'ten çek
    if not textual_model_name or not visual_model_name:
        faiss_models = faiss_service.get_available_models()
        if faiss_models.get("status") == "success":
            faiss_data = faiss_models.get("data", {})
            defaults = faiss_data.get("defaults", {})
            textual_model_name = textual_model_name or defaults.get("textual")
            visual_model_name = visual_model_name or defaults.get("visual")

        # Hala yoksa default kullan
        if not textual_model_name:
            textual_model_name = DEFAULT_TEXTUAL_MODEL
        if not visual_model_name:
            visual_model_name = DEFAULT_VISUAL_MODEL

    wait_duration_seconds = data.get("wait_duration_seconds", 60)
    delay_between_products_ms = data.get("delay_between_products_ms", 0)

    available_model_ids = _get_valid_model_ids()

    # Validate model names
    if textual_model_name not in available_model_ids:
        return jsonify(
            {
                "status": "error",
                "error": f"Invalid textual model: {textual_model_name}. Available: {available_model_ids}",
            }
        ), 400

    if visual_model_name not in available_model_ids:
        return jsonify(
            {
                "status": "error",
                "error": f"Invalid visual model: {visual_model_name}. Available: {available_model_ids}",
            }
        ), 400

    logger.info(
        f"[BulkFAISS] Using models - Textual: {textual_model_name}, Visual: {visual_model_name}"
    )
    logger.info(f"[BulkFAISS] Wait duration: {wait_duration_seconds}s")

    try:
        # Step 1: Clear FAISS index via FAISS service
        logger.info(f"[BulkFAISS] Step 1/2: Clearing FAISS index via service...")
        clear_start = time.time()

        clear_result = faiss_service.clear_index()

        if clear_result.get("status") == "error":
            logger.warning(
                f"[BulkFAISS] Clear index failed: {clear_result.get('error')}"
            )
            # Continue anyway - index may already be empty

        clear_duration = (time.time() - clear_start) * 1000
        logger.info(f"[BulkFAISS] Index cleared in {clear_duration:.2f}ms")

        # Step 2: Add all products
        logger.info(f"[BulkFAISS] Step 2/2: Adding all products from database...")

        # Get all active products with eager loading for brand and images relationships
        products = (
            Product.query.filter_by(is_active=True)
            .options(
                joinedload(Product.brand),
                joinedload(Product.images),
            )
            .all()
        )

        if not products:
            return jsonify(
                {"status": "error", "error": "No products found in database"}
            ), 404

        total_products = len(products)
        logger.info(f"[BulkFAISS] Starting bulk import of {total_products} products")

        upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads/products")
        logger.info(f"[BulkFAISS] Upload folder configured: {upload_folder}")
        logger.info(
            f"[BulkFAISS] Upload folder absolute: {os.path.abspath(upload_folder)}"
        )
        logger.info(
            f"[BulkFAISS] Upload folder exists: {os.path.exists(upload_folder)}"
        )

        # List first few files in upload folder for verification
        try:
            files = os.listdir(upload_folder)[:5]
            logger.info(f"[BulkFAISS] Sample files in upload folder: {files}")
        except Exception as e:
            logger.warning(f"[BulkFAISS] Could not list upload folder: {e}")

        # Track if we've waited after the first product
        waited_after_first = False
        first_product_retry_count = 0
        max_first_product_retries = 3

        for idx, product in enumerate(products):
            try:
                # Get brand name
                brand_name = product.brand.name if product.brand else ""

                # Get first category name
                categories = list(product.categories)
                category_name = categories[0].name if categories else ""

                # Get image paths with detailed logging
                image_paths = []
                product_images = list(product.images)  # Force load from relationship
                logger.info(
                    f"[BulkFAISS] Product {product.product_id} has {len(product_images)} image records in DB"
                )

                for img in product_images:
                    raw_url = img.url

                    # Handle different URL formats from database
                    # Format 1: /uploads/products/filename.jpg (web URL path)
                    # Format 2: uploads/products/filename.jpg (relative path)
                    # Format 3: filename.jpg (just filename)
                    # Format 4: C:/.../uploads/products/filename.jpg (absolute path)

                    if raw_url.startswith("/uploads/products/"):
                        # Web URL path - use config UPLOAD_FOLDER + filename
                        filename = os.path.basename(raw_url)
                        image_path = os.path.join(upload_folder, filename)
                    elif raw_url.startswith("/"):
                        # Other absolute web paths - remove leading slash and join with project root
                        relative_path = raw_url[1:]
                        image_path = os.path.join(
                            os.path.dirname(current_app.root_path), relative_path
                        )
                    elif os.path.isabs(raw_url):
                        # Already absolute file path
                        image_path = raw_url
                    else:
                        # Relative path or just filename - join with upload folder
                        image_path = os.path.join(
                            upload_folder, os.path.basename(raw_url)
                        )

                    # Normalize path
                    norm_path = os.path.normpath(image_path)
                    exists = os.path.exists(norm_path)

                    logger.info(
                        f"[BulkFAISS]   raw_url={raw_url} -> path={norm_path}, exists={exists}"
                    )

                    if exists:
                        image_paths.append(norm_path)
                        logger.info(f"[BulkFAISS]   ✓ Valid image: {norm_path}")
                    else:
                        logger.warning(
                            f"[BulkFAISS]   ✗ Image not found: {norm_path} (raw: {raw_url})"
                        )

                logger.info(
                    f"[BulkFAISS] Product {product.product_id}: {len(image_paths)}/{len(product_images)} images valid"
                )

                # Prepare product data for FAISS
                product_data = {
                    "id": str(product.product_id),
                    "name": product.name,
                    "description": product.description or "",
                    "brand": brand_name,
                    "category": category_name,
                    "price": float(product.price) if product.price else 0.0,
                    "images": image_paths,
                    "textual_model_name": textual_model_name,
                    "visual_model_name": visual_model_name,
                }

                logger.info(
                    f"[BulkFAISS] Adding product {product.product_id}: {product.name}"
                )

                # For first product, retry if fails
                max_retries = (
                    max_first_product_retries
                    if idx == 0 and not waited_after_first
                    else 1
                )
                result = None

                for attempt in range(1, max_retries + 1):
                    # Call FAISS service
                    result = faiss_service.add_product(
                        product_id=product_data["id"],
                        name=product_data["name"],
                        description=product_data["description"],
                        brand=product_data["brand"],
                        category=product_data["category"],
                        price=product_data["price"],
                        images=product_data["images"],
                        textual_model_name=product_data["textual_model_name"],
                        visual_model_name=product_data["visual_model_name"],
                    )

                    if result.get("status") == "success":
                        if attempt > 1:
                            logger.info(
                                f"[BulkFAISS] ✅ First product succeeded on attempt {attempt}"
                            )
                        break
                    else:
                        if attempt < max_retries:
                            logger.warning(
                                f"[BulkFAISS] First product attempt {attempt} failed, retrying..."
                            )
                            time.sleep(2)  # Wait before retry
                        else:
                            logger.error(
                                f"[BulkFAISS] First product failed after {max_retries} attempts"
                            )

                if result.get("status") == "success":
                    successful_count += 1
                    details = result.get("details", {})
                    visual_count = len(details.get("visual_vector_ids", []))
                    text_id = details.get("textual_vector_id", "N/A")
                    logger.info(
                        f"[BulkFAISS] ✅ Product {product.product_id} added successfully: "
                        f"text_id={text_id}, {visual_count} images embedded"
                    )

                    # Wait after first successful product
                    if not waited_after_first:
                        waited_after_first = True
                        logger.info(
                            f"[BulkFAISS] ⏳ Waiting {wait_duration_seconds}s for FAISS index initialization..."
                        )
                        time.sleep(wait_duration_seconds)
                        logger.info(
                            f"[BulkFAISS] ✅ Wait completed ({wait_duration_seconds}s), continuing with bulk import"
                        )
                elif result.get("status") == "skipped":
                    # Product already exists - count as successful but note it was skipped
                    successful_count += 1
                    logger.warning(
                        f"[BulkFAISS] ⚠️ Product {product.product_id} was skipped (already exists in index)"
                    )
                else:
                    failed_count += 1
                    error_msg = result.get("error", "Unknown error")
                    errors.append(
                        {"product_id": product.product_id, "error": error_msg}
                    )
                    logger.error(
                        f"[BulkFAISS] ❌ Product {product.product_id} failed: {error_msg}"
                    )

            except Exception as e:
                failed_count += 1
                errors.append({"product_id": product.product_id, "error": str(e)})
                logger.error(
                    f"[BulkFAISS] ❌ Product {product.product_id} exception: {e}"
                )

            # Apply delay between products if configured
            if delay_between_products_ms > 0 and idx < len(products) - 1:
                time.sleep(delay_between_products_ms / 1000.0)

        total_time = (time.time() - start_time) * 1000

        logger.info(
            f"[BulkFAISS] Bulk import completed: {successful_count}/{total_products} successful in {total_time:.2f}ms"
        )

        return jsonify(
            {
                "status": "success",
                "message": f"Bulk import completed: {successful_count} products added",
                "details": {
                    "total_products": total_products,
                    "successful_count": successful_count,
                    "failed_count": failed_count,
                    "total_time_ms": total_time,
                    "textual_model_name": textual_model_name,
                    "visual_model_name": visual_model_name,
                    "wait_applied": waited_after_first,
                    "wait_duration_seconds": wait_duration_seconds
                    if waited_after_first
                    else 0,
                    "delay_between_products_ms": delay_between_products_ms,
                    "errors": errors[:10],  # Limit errors to first 10
                },
            }
        ), 200

    except Exception as e:
        logger.error(f"[BulkFAISS] Bulk import failed: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@bulk_faiss_bp.route("/rebuild-with-test", methods=["POST"])
def rebuild_with_test():
    """
    Complete rebuild workflow: Test product → Bulk add all products.

    This endpoint performs a complete FAISS index rebuild with verification:
    1. Adds a test product and waits for successful confirmation
    2. Adds all products from the database (products already in index will be skipped)

    Use this when you need to ensure the FAISS service is working correctly
    before bulk import. Note: Existing products in FAISS will be skipped,
    not updated. To force update, use /delete-all first, then call this endpoint.

    Send JSON body with optional:
    - textual_model_name: Model for text embeddings
    - visual_model_name: Model for image embeddings
    - test_product_id: Custom ID for test product (default: test-product-001)
    - wait_after_first: Wait after first product for FAISS init (default: true)
    - wait_duration_seconds: How long to wait after first product (default: 60)
    - delay_between_products_ms: Delay between each product (default: 0)
    """
    import time

    start_time = time.time()

    workflow_steps = []
    overall_success = True

    try:
        # Get configuration from request body
        data = request.get_json() or {}

        # Request'te model varsa onu kullan
        textual_model_name = data.get("textual_model_name")
        visual_model_name = data.get("visual_model_name")

        # Yoksa FAISS service'ten çek
        if not textual_model_name or not visual_model_name:
            faiss_models = faiss_service.get_available_models()
            if faiss_models.get("status") == "success":
                faiss_data = faiss_models.get("data", {})
                defaults = faiss_data.get("defaults", {})
                textual_model_name = textual_model_name or defaults.get("textual")
                visual_model_name = visual_model_name or defaults.get("visual")

            # Hala yoksa default kullan
            if not textual_model_name:
                textual_model_name = DEFAULT_TEXTUAL_MODEL
            if not visual_model_name:
                visual_model_name = DEFAULT_VISUAL_MODEL

        test_product_id = data.get("test_product_id", "test-product-001")
        wait_duration_seconds = data.get("wait_duration_seconds", 60)
        delay_between_products_ms = data.get("delay_between_products_ms", 0)

        available_model_ids = _get_valid_model_ids()

        # Validate model names
        if textual_model_name not in available_model_ids:
            return jsonify(
                {
                    "status": "error",
                    "error": f"Invalid textual model: {textual_model_name}. Available: {available_model_ids}",
                }
            ), 400

        if visual_model_name not in available_model_ids:
            return jsonify(
                {
                    "status": "error",
                    "error": f"Invalid visual model: {visual_model_name}. Available: {available_model_ids}",
                }
            ), 400

        logger.info(
            f"[BulkFAISS] Starting rebuild workflow with models - Textual: {textual_model_name}, Visual: {visual_model_name}"
        )

        # Step 1: Add test product
        logger.info(f"[BulkFAISS] Step 1/2: Adding test product {test_product_id}")
        step1_start = time.time()

        # Retry logic for test product
        max_retries = 3
        test_success = False
        test_result = None

        for attempt in range(1, max_retries + 1):
            test_result = faiss_service.add_test_product(product_id=test_product_id)

            if test_result.get("status") == "success":
                test_success = True
                break
            else:
                if attempt < max_retries:
                    logger.warning(
                        f"[BulkFAISS] Test product attempt {attempt} failed, retrying..."
                    )
                    time.sleep(2)

        step1_duration = (time.time() - step1_start) * 1000

        if not test_success:
            logger.error(f"[BulkFAISS] Step 1 failed: Test product could not be added")
            workflow_steps.append(
                {
                    "step": "test_product",
                    "status": "error",
                    "error": test_result.get("error", "Test product failed"),
                    "attempts": max_retries,
                    "duration_ms": step1_duration,
                }
            )
            overall_success = False
        else:
            logger.info(
                f"[BulkFAISS] Step 1 completed: Test product added in {step1_duration:.2f}ms"
            )
            workflow_steps.append(
                {
                    "step": "test_product",
                    "status": "success",
                    "details": test_result.get("details", {}),
                    "attempts": max_retries
                    if not test_result.get("status") == "success"
                    else 1,
                    "duration_ms": step1_duration,
                }
            )

        # Step 2: Bulk add all products
        if overall_success:
            logger.info(f"[BulkFAISS] Step 2/2: Adding all products from database")
            step2_start = time.time()

            # Retry logic for test product
            max_retries = 3
            test_success = False
            test_result = None

            for attempt in range(1, max_retries + 1):
                test_result = faiss_service.add_test_product(product_id=test_product_id)

                if test_result.get("status") == "success":
                    test_success = True
                    logger.info(
                        f"[BulkFAISS] Step 2 completed on attempt {attempt}: Test product added"
                    )
                    break
                else:
                    logger.warning(
                        f"[BulkFAISS] Step 2 attempt {attempt} failed: {test_result.get('error')}"
                    )
                    if attempt < max_retries:
                        time.sleep(2)  # Wait before retry

            step2_duration = (time.time() - step2_start) * 1000

            if not test_success:
                logger.error(f"[BulkFAISS] Step 2 failed after {max_retries} attempts")
                workflow_steps.append(
                    {
                        "step": "test_product",
                        "status": "error",
                        "error": test_result.get("error", "Unknown error"),
                        "attempts": max_retries,
                        "duration_ms": step2_duration,
                    }
                )
                overall_success = False
            else:
                workflow_steps.append(
                    {
                        "step": "test_product",
                        "status": "success",
                        "details": test_result.get("details", {}),
                        "attempts": max_retries
                        if not test_result.get("status") == "success"
                        else 1,
                        "duration_ms": step2_duration,
                    }
                )

        # Step 2: Bulk add all products
        if overall_success:
            logger.info(f"[BulkFAISS] Step 2/2: Adding all products from database")
            step2_start = time.time()

            # Get all active products with eager loading for brand and images relationships
            products = (
                Product.query.filter_by(is_active=True)
                .options(
                    joinedload(Product.brand),
                    joinedload(Product.images),
                )
                .all()
            )

            if not products:
                logger.error(
                    f"[BulkFAISS] Step 3 failed: No products found in database"
                )
                workflow_steps.append(
                    {
                        "step": "bulk_add",
                        "status": "error",
                        "error": "No products found in database",
                    }
                )
                overall_success = False
            else:
                successful_count = 0
                failed_count = 0
                errors = []

                upload_folder = current_app.config.get(
                    "UPLOAD_FOLDER", "uploads/products"
                )

                # Wait logic for bulk add
                waited_after_first = False
                first_product_added = False

                for idx, product in enumerate(products):
                    try:
                        brand_name = product.brand.name if product.brand else ""
                        categories = list(product.categories)
                        category_name = categories[0].name if categories else ""

                        # Get image paths with detailed logging
                        image_paths = []
                        product_images = list(
                            product.images
                        )  # Force load from relationship
                        logger.info(
                            f"[BulkFAISS] Product {product.product_id} has {len(product_images)} image records in DB"
                        )

                        for img in product_images:
                            image_path = (
                                img.url
                                if os.path.isabs(img.url)
                                else os.path.join(
                                    upload_folder, os.path.basename(img.url)
                                )
                            )
                            if os.path.exists(image_path):
                                image_paths.append(image_path)
                                logger.info(
                                    f"[BulkFAISS]   ✓ Valid image: {image_path}"
                                )
                            else:
                                logger.warning(
                                    f"[BulkFAISS]   ✗ Image not found: {image_path} (DB url: {img.url})"
                                )

                        logger.info(
                            f"[BulkFAISS] Product {product.product_id}: {len(image_paths)}/{len(product_images)} images valid"
                        )

                        result = faiss_service.add_product(
                            product_id=str(product.product_id),
                            name=product.name,
                            description=product.description or "",
                            brand=brand_name,
                            category=category_name,
                            price=float(product.price) if product.price else 0.0,
                            images=image_paths,
                            textual_model_name=textual_model_name,
                            visual_model_name=visual_model_name,
                        )

                        if result.get("status") == "success":
                            successful_count += 1
                            details = result.get("details", {})
                            visual_count = len(details.get("visual_vector_ids", []))
                            text_id = details.get("textual_vector_id", "N/A")
                            logger.info(
                                f"[BulkFAISS] ✅ Product {product.product_id} added: "
                                f"text_id={text_id}, {visual_count} images embedded"
                            )

                            # Wait after first successful product
                            if (
                                data.get("wait_after_first", True)
                                and not waited_after_first
                            ):
                                first_product_added = True
                                waited_after_first = True
                                logger.info(
                                    f"[BulkFAISS] ⏳ Waiting {wait_duration_seconds}s for FAISS index initialization..."
                                )
                                time.sleep(wait_duration_seconds)
                                logger.info(
                                    f"[BulkFAISS] ✅ Wait completed, continuing with bulk import"
                                )
                        elif result.get("status") == "skipped":
                            successful_count += 1
                            logger.warning(
                                f"[BulkFAISS] ⚠️ Product {product.product_id} was skipped (already exists)"
                            )
                        else:
                            failed_count += 1
                            errors.append(
                                {
                                    "product_id": product.product_id,
                                    "error": result.get("error", "Unknown error"),
                                }
                            )
                            logger.error(
                                f"[BulkFAISS] ❌ Product {product.product_id} failed: {result.get('error', 'Unknown error')}"
                            )

                    except Exception as e:
                        failed_count += 1
                        errors.append(
                            {"product_id": product.product_id, "error": str(e)}
                        )

                    # Apply delay between products if configured
                    if delay_between_products_ms > 0 and idx < len(products) - 1:
                        time.sleep(delay_between_products_ms / 1000.0)

                step2_duration = (time.time() - step2_start) * 1000

                logger.info(
                    f"[BulkFAISS] Step 2 completed: {successful_count}/{len(products)} products added in {step2_duration:.2f}ms"
                )

                workflow_steps.append(
                    {
                        "step": "bulk_add",
                        "status": "success" if failed_count == 0 else "partial",
                        "details": {
                            "total_products": len(products),
                            "successful_count": successful_count,
                            "failed_count": failed_count,
                            "errors": errors[:10],
                        },
                        "duration_ms": step2_duration,
                    }
                )

        total_duration = (time.time() - start_time) * 1000

        logger.info(f"[BulkFAISS] Rebuild workflow completed in {total_duration:.2f}ms")

        return jsonify(
            {
                "status": "success" if overall_success else "partial",
                "workflow": "rebuild_with_test",
                "message": f"Rebuild completed in {total_duration:.2f}ms",
                "steps": workflow_steps,
                "summary": {
                    "total_duration_ms": total_duration,
                    "all_steps_successful": overall_success,
                },
            }
        ), 200 if overall_success else 207

    except Exception as e:
        logger.error(f"[BulkFAISS] Rebuild workflow failed: {e}")
        return jsonify(
            {
                "status": "error",
                "error": str(e),
                "workflow": "rebuild_with_test",
                "steps_completed": workflow_steps,
            }
        ), 500


@bulk_faiss_bp.route("/delete-all", methods=["POST"])
def delete_all_products():
    """
    Delete all products from FAISS index.

    This endpoint iterates through all products in the database and deletes
    each one from the FAISS index using the delete-product endpoint.

    Request body (optional):
        - delay_between_products_ms: Delay between each delete (default: 0)
    """
    import time

    start_time = time.time()

    successful_count = 0
    failed_count = 0
    not_found_count = 0
    errors = []

    # Get configuration from request body
    data = request.get_json() or {}
    delay_between_products_ms = data.get("delay_between_products_ms", 0)

    try:
        logger.info(
            "[BulkFAISS] Starting bulk delete of all products from FAISS index..."
        )

        # Get all active products (we need their IDs to delete)
        products = (
            Product.query.filter_by(is_active=True)
            .with_entities(Product.product_id)
            .all()
        )

        if not products:
            return jsonify(
                {
                    "status": "error",
                    "error": "No products found in database",
                }
            ), 404

        total_products = len(products)
        logger.info(f"[BulkFAISS] Found {total_products} products to delete from FAISS")

        for idx, (product_id,) in enumerate(products):
            try:
                # Call FAISS service to delete product
                result = faiss_service.delete_product(str(product_id))

                if result.get("status") == "success":
                    if "not in FAISS index" in result.get("message", ""):
                        not_found_count += 1
                        logger.info(
                            f"[BulkFAISS] Product {product_id} not in index (already deleted)"
                        )
                    else:
                        successful_count += 1
                        logger.info(
                            f"[BulkFAISS] ✅ Deleted product {product_id} from FAISS"
                        )
                else:
                    failed_count += 1
                    error_msg = result.get("error", "Unknown error")
                    errors.append({"product_id": product_id, "error": error_msg})
                    logger.error(
                        f"[BulkFAISS] ❌ Failed to delete product {product_id}: {error_msg}"
                    )

            except Exception as e:
                failed_count += 1
                errors.append({"product_id": product_id, "error": str(e)})
                logger.error(
                    f"[BulkFAISS] ❌ Exception deleting product {product_id}: {e}"
                )

            # Apply delay between products if configured
            if delay_between_products_ms > 0 and idx < len(products) - 1:
                time.sleep(delay_between_products_ms / 1000.0)

        total_time = (time.time() - start_time) * 1000

        logger.info(
            f"[BulkFAISS] Bulk delete completed: {successful_count} deleted, "
            f"{not_found_count} not found, {failed_count} failed in {total_time:.2f}ms"
        )

        return jsonify(
            {
                "status": "success",
                "message": f"Bulk delete completed: {successful_count} products deleted from FAISS",
                "details": {
                    "total_products": total_products,
                    "successful_count": successful_count,
                    "not_found_count": not_found_count,
                    "failed_count": failed_count,
                    "total_time_ms": total_time,
                    "delay_between_products_ms": delay_between_products_ms,
                    "errors": errors[:10],  # Limit errors to first 10
                },
            }
        ), 200

    except Exception as e:
        logger.error(f"[BulkFAISS] Bulk delete failed: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@bulk_faiss_bp.route("/clear-index", methods=["POST"])
def clear_faiss_index():
    """
    Clear entire FAISS index (faster than delete-all).

    This uses the FAISS service's clear-index endpoint to wipe all embeddings
    at once, which is much faster than deleting products one by one.
    """
    try:
        logger.info("[BulkFAISS] Clearing entire FAISS index...")

        result = faiss_service.clear_index()

        if result.get("status") == "success":
            return jsonify(
                {
                    "status": "success",
                    "message": "FAISS index cleared successfully",
                    "details": result.get("details", {}),
                }
            ), 200
        else:
            return jsonify(
                {
                    "status": "error",
                    "error": result.get("error", "Failed to clear index"),
                }
            ), 500

    except Exception as e:
        logger.error(f"[BulkFAISS] Clear index failed: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500
