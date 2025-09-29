from PIL import Image, ImageDraw, ImageFont
import logging
import random

logger = logging.getLogger(__name__)


def draw_plain_image(
    image: Image.Image,
    width: int,
    height: int,
    text: str,
    font_size: int,
    font_path: str,
    max_width: int,
    width_center_position: float,
    height_center_position: float,
    outline_width: int,
    text_color: str,
    outline_color: str,
    margins: dict,
) -> Image.Image:
    """Draw plain text with outline on an image

    Args:
        image: The base image to draw on
        width: Width of the image
        height: Height of the image
        text: Text to render
        font_size: Font size to use
        font_path: Path to font file
        max_width: Maximum width for text wrapping
        width_center_position: X position for text center (0-1)
        height_center_position: Y position for text center (0-1)
        outline_width: Width of the text outline
        text_color: Color of the main text
        outline_color: Color of the text outline
        highlight_padding: Ignored for plain text

    Returns:
        PIL.Image: The image with text drawn on it
    """
    logger.critical(f"PLAIN // Drawing plain text")
    logger.critical(f"PLAIN // Text: {text}")
    logger.critical(f"PLAIN // Font: {font_path}, Size: {font_size}")
    logger.critical(f"PLAIN // Position: w={width_center_position}, h={height_center_position}")
    logger.critical(f"PLAIN // Colors - Text: {text_color}, Outline: {outline_color}")
    logger.critical(f"PLAIN // Margins: {margins}")

    # First upscale the base image with LANCZOS
    scale = 2
    base = image.copy()
    base = base.resize((width * scale, height * scale), Image.Resampling.LANCZOS)
    
    # Print original image metadata
    logger.critical("Original Image Metadata:")
    if hasattr(image, 'info'):
        for k, v in image.info.items():
            logger.critical(f"{k}: {v}")

    # Create high-res text layer
    scaled_width = width * scale
    scaled_height = height * scale
    scaled_font_size = font_size * scale

    text_layer = Image.new("RGBA", (scaled_width, scaled_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)

    # Load font at higher resolution
    font = ImageFont.truetype(font_path, scaled_font_size)

    # Scale other parameters
    scaled_max_width = max_width * scale
    scaled_margins = {k: v * scale for k, v in margins.items()}
    scaled_outline_width = outline_width * scale

    # Rest of the position calculations, but scaled
    lines = wrap_text(draw, text, font, scaled_max_width)
    line_spacing = scaled_font_size * 1.2
    total_height = len(lines) * line_spacing

    # Calculate y position with scaling
    y = int(scaled_height * (1 - height_center_position) - total_height/2)
    y = max(
        scaled_margins["top"],
        min(
            scaled_height - scaled_margins["bottom"] - total_height,
            y
        )
    )

    # Draw text at higher resolution
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = int(scaled_width * width_center_position)
        line_x = x - (text_width // 2)
        line_y = y + (i * line_spacing)

        # Draw outline
        for adj_x in range(-scaled_outline_width, scaled_outline_width + 1):
            for adj_y in range(-scaled_outline_width, scaled_outline_width + 1):
                draw.text(
                    (line_x + adj_x, line_y + adj_y),
                    line,
                    font=font,
                    fill=outline_color
                )

        # Draw main text
        draw.text(
            (line_x, line_y), 
            line, 
            font=font, 
            fill=text_color
        )

    # Scale back down with high-quality resampling
    text_layer = text_layer.resize((width, height), Image.Resampling.LANCZOS)
    result = Image.alpha_composite(base.resize((width, height), Image.Resampling.LANCZOS), text_layer)

    # Print final image metadata
    logger.critical("Final Image Metadata:")
    if hasattr(result, 'info'):
        for k, v in result.info.items():
            logger.critical(f"{k}: {v}")

    return result


def wrap_text(draw, text, font, max_width):
    """Helper function to wrap text, treating each \n as a line break"""
    lines = []

    # Split by \n first to honor all line breaks
    paragraphs = text.split("\\n")

    for paragraph in paragraphs:
        if not paragraph.strip():
            lines.append("")
            continue

        # Now wrap the words within each paragraph
        words = paragraph.strip().split()
        current_line = ""

        for word in words:
            test_line = current_line + " " + word if current_line else word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            line_width = bbox[2] - bbox[0]

            if line_width <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word

        lines.append(current_line)  # Add last line of paragraph

    return lines
