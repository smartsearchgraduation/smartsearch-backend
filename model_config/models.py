"""
Model configuration for FAISS embeddings.
Edit this file to add or modify available models.
"""

# Available CLIP models for text and image embeddings
# Format: "model_id": "Display Name (Description)"
AVAILABLE_MODELS = {
    # ViT (Vision Transformer) models - recommended
    "ViT-B/32": "ViT-B/32 (Varsayılan - Hızlı)",
    "ViT-B/16": "ViT-B/16 (Daha Doğru)",
    "ViT-L/14": "ViT-L/14 (Büyük Model)",
    "ViT-L/14@336px": "ViT-L/14@336px (En Yüksek Çözünürlük)",
    "BAAI/bge-large-en-v1.5": "BAAI/bge-large-en-v1.5 (Büyük Model)",
    
    # ResNet models - alternative
    "RN50": "RN50 (ResNet-50)",
    "RN101": "RN101 (ResNet-101)",
    "RN50x4": "RN50x4 (4x Genişletilmiş)",
    "RN50x16": "RN50x16 (16x Genişletilmiş)",
    "RN50x64": "RN50x64 (64x Genişletilmiş - En Büyük)",
}

# Default model settings
DEFAULT_TEXTUAL_MODEL = "BAAI/bge-large-en-v1.5"
DEFAULT_VISUAL_MODEL = "ViT-B/32"

# Model groups for UI organization
MODEL_GROUPS = {
    "ViT (Önerilen)": ["ViT-B/32", "ViT-B/16", "ViT-L/14", "ViT-L/14@336px", "BAAI/bge-large-en-v1.5"],
    "ResNet": ["RN50", "RN101", "RN50x4", "RN50x16", "RN50x64"],
}


def get_model_options_html():
    """Generate HTML option tags for model selection dropdowns."""
    html = ""
    for model_id, display_name in AVAILABLE_MODELS.items():
        selected = " selected" if model_id == DEFAULT_TEXTUAL_MODEL else ""
        html += f'<option value="{model_id}"{selected}>{display_name}</option>\n'
    return html


def get_models_list():
    """Return list of available model IDs."""
    return list(AVAILABLE_MODELS.keys())


def is_valid_model(model_name: str) -> bool:
    """Check if a model name is valid."""
    return model_name in AVAILABLE_MODELS
