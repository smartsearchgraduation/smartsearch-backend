"""
Model configuration for FAISS embeddings.
Edit this file to add or modify available models.
"""

# Available CLIP models for text and image embeddings
# Format: "model_id": {"name": "Model ID", "dimension": 512}
AVAILABLE_MODELS = {
    # ViT (Vision Transformer) models - recommended
    "ViT-B/32": {"name": "ViT-B/32", "dimension": 512},
    "ViT-B/16": {"name": "ViT-B/16", "dimension": 512},
    "ViT-L/14": {"name": "ViT-L/14", "dimension": 768},
    "ViT-L/14@336px": {"name": "ViT-L/14@336px", "dimension": 768},
    "BAAI/bge-large-en-v1.5": {"name": "BAAI/bge-large-en-v1.5", "dimension": 1024},

    # Qwen embedding model
    "Qwen/Qwen3-Embedding-8B": {"name": "Qwen/Qwen3-Embedding-8B", "dimension": 4096},

    # ResNet models - alternative
    "RN50": {"name": "RN50", "dimension": 1024},
    "RN101": {"name": "RN101", "dimension": 1024},
    "RN50x4": {"name": "RN50x4", "dimension": 640},
    "RN50x16": {"name": "RN50x16", "dimension": 768},
    "RN50x64": {"name": "RN50x64", "dimension": 1024},
}

# Default model settings
DEFAULT_TEXTUAL_MODEL = "BAAI/bge-large-en-v1.5"
DEFAULT_VISUAL_MODEL = "ViT-B/32"

# Model groups for UI organization
MODEL_GROUPS = {
    "ViT (Önerilen)": ["ViT-B/32", "ViT-B/16", "ViT-L/14", "ViT-L/14@336px", "BAAI/bge-large-en-v1.5"],
    "Qwen": ["Qwen/Qwen3-Embedding-8B"],
    "ResNet": ["RN50", "RN101", "RN50x4", "RN50x16", "RN50x64"],
}


def get_model_options_html():
    """Generate HTML option tags for model selection dropdowns."""
    html = ""
    for model_id, model_info in AVAILABLE_MODELS.items():
        display_name = model_info.get("name", model_id) if isinstance(model_info, dict) else model_info
        # Add description based on model type
        description = ""
        if model_id == DEFAULT_TEXTUAL_MODEL:
            description = " (Varsayılan - Hızlı)"
        elif "bge-large" in model_id.lower():
            description = " (Büyük Model)"
        elif "16x" in model_id.lower() or "64x" in model_id.lower():
            description = " (Genişletilmiş)"
        
        selected = " selected" if model_id == DEFAULT_TEXTUAL_MODEL else ""
        html += f'<option value="{model_id}"{selected}>{display_name}{description}</option>\n'
    return html


def get_models_list():
    """Return list of available model IDs."""
    return list(AVAILABLE_MODELS.keys())


def is_valid_model(model_name: str) -> bool:
    """Check if a model name is valid."""
    return model_name in AVAILABLE_MODELS


def get_model_info(model_id: str):
    """
    Get detailed information about a model.
    
    Args:
        model_id: The model identifier
        
    Returns:
        Dict with model info (name, dimension) or None if not found
    """
    model_info = AVAILABLE_MODELS.get(model_id)
    if isinstance(model_info, dict):
        return {
            "name": model_info.get("name", model_id),
            "dimension": model_info.get("dimension", 512)
        }
    return {
        "name": str(model_info),
        "dimension": 512
    }


def get_selected_models():
    """
    Get currently selected models from config file.

    Returns:
        dict: Selected textual and visual models

    Usage:
        models = get_selected_models()
        textual_model = models['textual_model']
        visual_model = models['visual_model']
    """
    import json
    import os

    config_path = os.path.join(os.path.dirname(__file__), 'selected_models.json')

    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Return defaults if config doesn't exist
        return {
            "textual_model": DEFAULT_TEXTUAL_MODEL,
            "visual_model": DEFAULT_VISUAL_MODEL,
            "last_updated": None
        }


def save_selected_models(textual: str, visual: str):
    """
    Save selected models to config file.

    Args:
        textual: Textual model name
        visual: Visual model name

    Usage:
        save_selected_models('ViT-L/14', 'ViT-L/14')
    """
    import json
    import os
    from datetime import datetime

    config_path = os.path.join(os.path.dirname(__file__), 'selected_models.json')

    config = {
        "textual_model": textual,
        "visual_model": visual,
        "last_updated": datetime.utcnow().isoformat() + "Z"
    }

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
