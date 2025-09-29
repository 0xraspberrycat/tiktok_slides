from pathlib import Path

VALID_TEXT_TYPES = {
    "plain": {
        "style_type": "outline_width",
        "required_color_keys": ["text", "outline"],
    },
    "highlight": {
        "style_type": "corner_radius",
        "required_color_keys": ["text", "background"],
    },
}

# Define paths
TEMPLATE_PATH = Path("assets/templates")
DEFAULT_TEMPLATE = TEMPLATE_PATH / "default.json"

VALID_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".PNG", ".JPG", ".JPEG"}


MULTI_COLOUR_SETTINGS_BACKUP = {
    "base_settings": {"default_text_type": "plain"},
    "text_settings": {
        "plain": {
            "font_size": 70,
            "font": "assets.fonts.tiktokfont.ttf",
            "style_type": "outline_width",
            "style_value": 2,
            "colors": [
                {"text": "#FFFFFF", "outline": "#000000"},
                {"text": "#000000", "outline": "#FFFFFF"},
            ],
            "position": {
                "vertical": [0.7, 0.8],
                "horizontal": [0.45, 0.55],
                "vertical_jitter": 0.01,
                "horizontal_jitter": 0.02,
            },
            "margins": {"top": 0.05, "bottom": 0.05, "left": 0.05, "right": 0.05},
        },
        "highlight": {
            "font_size": 70,
            "font": "assets.fonts.tiktokfont.ttf",
            "style_type": "corner_radius",
            "style_value": 20,
            "colors": [
                {"text": "#000000", "background": "#FFFFFF"},
                {"text": "#FFFFFF", "background": "#FF0000"},
            ],
            "position": {
                "vertical": [0.6, 0.8],
                "horizontal": [0.45, 0.55],
                "vertical_jitter": 0.01,
                "horizontal_jitter": 0.02,
            },
            "margins": {"top": 0.05, "bottom": 0.05, "left": 0.05, "right": 0.05},
        },
    },
}
