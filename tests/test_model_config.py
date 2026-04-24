from config.models import resolve_fused_model


def test_resolve_fused_model_uses_matching_textual_and_visual_over_existing_fused():
    assert (
        resolve_fused_model(
            "ViT-L/14",
            "ViT-L/14",
            fused_model="ViT-B/32",
            fallback="RN50",
        )
        == "ViT-L/14"
    )
