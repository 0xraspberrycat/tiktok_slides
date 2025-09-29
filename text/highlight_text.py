from PIL import Image, ImageDraw, ImageFont


def draw_rounded_rectangle(draw, xy, radius, fill):
    "" "Draw a rounded rectangle" ""
    x1, y1, x2, y2 = xy
    r = radius
    draw.rectangle([x1 + r, y1, x2 - r, y2], fill=fill)  # Center
    draw.rectangle([x1, y1 + r, x2, y2 - r], fill=fill)  # Sides
    # Corners
    draw.pieslice([x1, y1, x1 + 2 * r, y1 + 2 * r], 180, 270, fill=fill)  # Top left
    draw.pieslice([x2 - 2 * r, y1, x2, y1 + 2 * r], 270, 360, fill=fill)  # Top right
    draw.pieslice([x1, y2 - 2 * r, x1 + 2 * r, y2], 90, 180, fill=fill)  # Bottom left
    draw.pieslice([x2 - 2 * r, y2 - 2 * r, x2, y2], 0, 90, fill=fill)  # Bottom right


def draw_wrapped_text(
    draw: ImageDraw.Draw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    position: tuple[int, int],
    width: int,
    text_color: str,
    background_color: str,
    highlight_padding: int = 2,
    corner_radius: int = 15,
) -> None:
    """Draw wrapped text with highlights, treating each \n as a line break"""
    
    # Split by \n first
    paragraphs = text.split('\\n')
    lines = []
    
    # Process each paragraph
    for paragraph in paragraphs:
        if not paragraph.strip():
            lines.append("")
            continue
            
        words = paragraph.strip().split()
        current_line = ""
        
        # Wrap words within paragraph
        for word in words:
            test_line = f"{current_line} {word}".strip()
            text_width = draw.textlength(test_line, font=font)
            if text_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
                
        lines.append(current_line)

    # Store the line info for drawing
    line_info = []
    x, y = position
    
    # Calculate positions
    for line in lines:
        if not line:  # Empty line
            y += font.size // 2  # Add small space for empty line
            continue
            
        bbox = font.getbbox(line)
        line_width = bbox[2] - bbox[0]
        line_height = bbox[3] - bbox[1]

        # Center horizontally
        x = (width - line_width) // 2

        # Store drawing info
        highlight_offset = 5
        highlight_x1 = x - highlight_padding
        highlight_y1 = y - highlight_padding + highlight_offset
        highlight_x2 = x + line_width + highlight_padding
        highlight_y2 = y + line_height + highlight_padding + highlight_offset

        line_info.append({
            "text": line,
            "x": x,
            "y": y,
            "highlight_coords": [highlight_x1, highlight_y1, highlight_x2, highlight_y2],
        })

        y += line_height + 20

    # Draw highlights bottom to top
    for line_data in reversed(line_info):
        draw_rounded_rectangle(draw, line_data["highlight_coords"], corner_radius, fill=background_color)

    # Draw text top to bottom
    for line_data in line_info:
        draw.text((line_data["x"], line_data["y"]), line_data["text"], font=font, fill=text_color)


def draw_highlight_image(
    image: Image.Image,
    width: int,
    height: int,
    text: str,
    font_size: int,
    font_path: str,
    max_width: int,
    width_center_position: float,  # This is % from left
    height_center_position: float,  # This is % from top
    corner_radius: int,
    text_color: str,
    background_color: str,
    margins: dict,
    highlight_padding: int = 20,
) -> Image.Image:
    """Draw highlighted text on an existing image
    
    Args:
        width: Base image width
        height: Base image height
        image: The base image to draw on
        width: Width to use for text positioning
        height: Height to use for text positioning
        text: Text to render
        font_size: Font size to use
        font_path: Path to font file
        max_width: Maximum width for text wrapping
        width_center_position: X position for text center (0-1)
        height_center_position: Y position for text center (0-1)
        corner_radius: Radius for rounded corners
        highlight_padding: Padding around text
        
    Returns:
        PIL.Image: The image with text drawn on it
    """
    # Create a temporary transparent layer for the text
    text_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)
    
    font = ImageFont.truetype(font_path, font_size)
    
    # Calculate actual pixel positions
    x = int(width * width_center_position)
    y = int(height * (1 - height_center_position))  # Invert the vertical position
    
    position = (x, y)
    
    draw_wrapped_text(
        draw=draw,
        text=text,
        font=font,
        max_width=max_width,
        position=position,
        width=width,
        text_color=text_color,
        background_color=background_color,
        highlight_padding=highlight_padding,
        corner_radius=corner_radius
    )
    
    result = Image.alpha_composite(image.convert("RGBA"), text_layer)
    return result


"""
NEVER REMOVE THIS 
# Example Usage
# Example Usage with higher resolution
width, height = 1080 * 2, 1920 * 2  # Doubled resolution
image = Image.new("RGB", (width, height), (0, 0, 0))  # Black background
draw = ImageDraw.Draw(image)
font = ImageFont.truetype(
# TODO    "tiktokfont.ttf FONT pATH",
    100,
)  # Double font size too

text = "This is a demonstration of text wrapping in TikTok style highlights with black background."
max_width = 1600  # Double the max width
position = (width // 2, height // 2)  # Center position
draw_wrapped_text(
    draw,
    text,
    font,
    max_width,
    position,
    highlight_padding=30,  # Double padding
    corner_radius=40,
)  # Double corner radius

# Optionally resize down for display while keeping the higher quality
# image = image.resize((1080, 1920), Image.Resampling.LANCZOS)
image.show()
"""