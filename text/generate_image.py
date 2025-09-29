from PIL import Image
from typing import Dict, Any
from content_manager.settings.settings_constants import VALID_TEXT_TYPES
from text.highlight_text import draw_highlight_image
from text.plain_text import draw_plain_image  # We'll create this later
import random
from config.logging import logger

# use this function to calcualate things like max width,
# etc


# Map text types to their rendering functions
TEXT_RENDERERS = {
    "highlight": draw_highlight_image,
    "plain": draw_plain_image  # Will implement later
}

# Map color keys to parameter names for each text type
COLOR_PARAM_MAPPING = {
    "highlight": {
        "text": "text_color",
        "background": "background_color"
    },
    "plain": {
        "text": "text_color",
        "outline": "outline_color"
    }
}

def generate_image(settings: Dict[str, Any], text_type: str, colour_index: int, image_path: str, text: str) -> Image.Image:
    """Calculate settings and apply text to image"""
    logger.debug(f"GENERATE // Text type: {text_type}")
    logger.debug(f"GENERATE // Settings for text type: {settings['text_settings'][text_type]}")
    
    if text_type not in VALID_TEXT_TYPES:
        raise ValueError(f"Invalid text type: {text_type}")
    
    text_settings = settings["text_settings"][text_type]
    logger.debug(f"generate image // settings: {settings}")
    image = Image.open(image_path)
    width, height = image.size
    
    # Calculate margins and usable area
    margins = text_settings["margins"]
    logger.debug(f"Raw margins from settings: {margins}")
    
    margin_left = int(width * margins["left"])
    margin_right = int(width * margins["right"])
    margin_top = int(height * margins["top"])
    margin_bottom = int(height * margins["bottom"])
    
    logger.debug(f"Calculated pixel margins - Left: {margin_left}, Right: {margin_right}, Top: {margin_top}, Bottom: {margin_bottom}")
    logger.debug(f"Image dimensions - Width: {width}, Height: {height}")
    
    max_width = int(width - margin_left - margin_right)
    logger.debug(f"Max width after margins: {max_width}")
    
    # Calculate position with jitter
    position = text_settings["position"]
    v_pos = random.uniform(position["vertical"][0], position["vertical"][1])
    v_jitter = random.uniform(-position["vertical_jitter"], position["vertical_jitter"])
    height_center_position = v_pos + v_jitter
    
    h_pos = random.uniform(position["horizontal"][0], position["horizontal"][1])
    h_jitter = random.uniform(-position["horizontal_jitter"], position["horizontal_jitter"])
    width_center_position = h_pos + h_jitter
    
    # Keep within margins using pixel values
    original_height_pos = height_center_position
    original_width_pos = width_center_position
    
    height_center_position = max(margin_top/height, min(1 - margin_bottom/height, height_center_position))
    width_center_position = max(margin_left/width, min(1 - margin_right/width, width_center_position))
    
    logger.debug(f"Position adjustments:")
    logger.debug(f"Height - Original: {original_height_pos:.3f}, After margins: {height_center_position:.3f}")
    logger.debug(f"Width - Original: {original_width_pos:.3f}, After margins: {width_center_position:.3f}")
    
    # Pass calculated pixel margins instead of ratios
    calculated_margins = {
        "top": margin_top,
        "bottom": margin_bottom,
        "left": margin_left,
        "right": margin_right
    }
    
    # Basic settings that apply to both text types
    common_settings = {
        "image": image,
        "width": width, 
        "height": height,
        "text": text,
        "font_size": text_settings["font_size"],
        "font_path": text_settings["font"].replace("assets.fonts.", "assets/fonts/"),
        "max_width": max_width,
        "width_center_position": width_center_position,
        "height_center_position": height_center_position,
        "margins": calculated_margins
    }
    
    # Get colors for current index
    colors = text_settings["colors"][colour_index]
    param_mapping = COLOR_PARAM_MAPPING[text_type]
    style_settings = {}
    
    # Map colors using the param mapping
    for key in VALID_TEXT_TYPES[text_type]["required_color_keys"]:
        if key not in colors:
            raise KeyError(f"Missing required color key '{key}' for text type '{text_type}'")
        style_settings[param_mapping[key]] = colors[key]
    
    # Add style-specific settings
    if text_type == "plain":
        style_settings["outline_width"] = text_settings["style_value"]
        logger.trace("GENERATE // Drawing plain text")
        logger.trace(f"GENERATE // Font: {text_settings['font']}")
        logger.trace(f"GENERATE // Font size: {text_settings['font_size']}")
        logger.trace(f"GENERATE // Style type: {text_settings['style_type']}")
        logger.trace(f"GENERATE // Style value: {text_settings['style_value']}")
        logger.trace(f"GENERATE // Colors: {colors}")
    elif text_type == "highlight":
        style_settings["corner_radius"] = text_settings["style_value"]
        logger.trace("GENERATE // Drawing highlight text")
        
    logger.debug(f"Using image {image_path} with text type {text_type}")
    logger.debug(f"Style settings for {text_type}: {style_settings}")
    
    # Merge settings and render
    renderer = TEXT_RENDERERS[text_type]
    final_settings = {**common_settings, **style_settings}
    return renderer(**final_settings)