import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from .logging import logger


class TemplateContainer:
    """Container for template methods to enable autocomplete"""

    def __init__(self, manager):
        self._manager = manager
        self._load_templates()

    def _load_templates(self):
        """Dynamically create methods for each template"""

        # Add default template
        def get_default():
            return self._manager.get_template("default")

        setattr(self, "default", get_default)

        # Add other templates
        for template_path in self._manager.templates_dir.glob("*.json"):
            name = template_path.stem

            def get_template(template_name=name):
                return self._manager.get_template(template_name)

            setattr(self, name, get_template)

    def list(self) -> List[str]:
        """List all available templates"""
        return [
            name
            for name in dir(self)
            if not name.startswith("_")
            and name != "list"
            and callable(getattr(self, name))
        ]


class FontContainer:
    """Container for font methods to enable autocomplete"""

    def __init__(self, manager):
        self._manager = manager
        self._load_fonts()

    def _load_fonts(self):
        """Dynamically create methods for each font"""
        fonts_dir = self._manager.fonts_dir
        fonts_dir.mkdir(exist_ok=True)

        # Add default font
        def get_default():
            return "assets.fonts.tiktokfont.ttf"

        setattr(self, "default", get_default)

        # Add other fonts
        for font_path in fonts_dir.glob("*.ttf"):
            name = font_path.stem

            def get_font(font_name=name):
                return f"assets.fonts.{font_name}.ttf"

            setattr(self, name, get_font)

    def list(self) -> List[str]:
        """List all available fonts"""
        return [
            name
            for name in dir(self)
            if not name.startswith("_")
            and name != "list"
            and name != "validate_font"
            and callable(getattr(self, name))
        ]

    def validate_font(self, font_path: str) -> bool:
        """Validate font path exists"""
        if not font_path.startswith("assets.fonts."):
            return False

        font_name = font_path.split(".")[-2]
        font_file = self._manager.fonts_dir / f"{font_name}.ttf"
        return font_file.exists()


class SettingsValidator:
    def __init__(self, manager):
        self._manager = manager
        self.STYLE_TYPES = {"plain": "outline_width", "highlight": "corner_radius"}
        self.REQUIRED_COLOR_KEYS = {
            "outline_width": ["text", "outline"],
            "corner_radius": ["text", "background"],
        }
        self.MARGIN_KEYS = ["top", "bottom", "left", "right"]

    @staticmethod
    def is_valid_hex(color: str) -> bool:
        """Validate hex color code"""
        if not color.startswith("#"):
            return False
        try:
            int(color[1:], 16)
            return len(color) in [4, 7]  # #RGB or #RRGGBB
        except ValueError:
            return False

    def validate_colors(self, colors: List[Dict], style_type: str) -> bool:
        """Validate color structure and values"""
        if not isinstance(colors, list):
            raise ValueError("Colors must be a list of dictionaries")

        required_keys = self.REQUIRED_COLOR_KEYS[style_type]
        for color in colors:
            if not isinstance(color, dict):
                raise ValueError("Each color must be a dictionary")

            for key in required_keys:
                if key not in color:
                    raise ValueError(f"Missing required color key: {key}")
                if not self.is_valid_hex(color[key]):
                    raise ValueError(f"Invalid hex color for {key}: {color[key]}")
        return True

    def validate_position(self, position: Dict) -> bool:
        """Validate position structure and values"""
        required_keys = [
            "vertical",
            "horizontal",
            "vertical_jitter",
            "horizontal_jitter",
        ]

        for key in required_keys:
            if key not in position:
                raise ValueError(f"Missing position key: {key}")

        # Validate ranges
        for range_key in ["vertical", "horizontal"]:
            range_val = position[range_key]
            if not isinstance(range_val, list) or len(range_val) != 2:
                raise ValueError(f"{range_key} must be a list of two floats")
            if not all(isinstance(x, (int, float)) and 0 <= x <= 1 for x in range_val):
                raise ValueError(f"{range_key} values must be between 0 and 1")

        # Validate jitter
        for jitter_key in ["vertical_jitter", "horizontal_jitter"]:
            jitter = position[jitter_key]
            if not isinstance(jitter, (int, float)) or not 0 <= jitter <= 1:
                raise ValueError(f"{jitter_key} must be a float between 0 and 1")

        return True

    def validate_margins(self, margins: Dict) -> bool:
        """Validate margins structure and values"""
        for key in self.MARGIN_KEYS:
            if key not in margins:
                raise ValueError(f"Missing margin key: {key}")
            if not isinstance(margins[key], (int, float)) or not 0 <= margins[key] <= 1:
                raise ValueError(f"Margin {key} must be a float between 0 and 1")
        return True

    def validate_text_settings(self, settings: Dict, text_type: str) -> bool:
        """Validate text settings structure and values"""
        required_keys = [
            "font_size",
            "font",
            "product_duplicate_prevention",
            "style_type",
            "style_value",
            "colors",
            "position",
            "margins",
        ]

        for key in required_keys:
            if key not in settings:
                raise ValueError(f"Missing required key in text settings: {key}")

        # Validate style type and value
        if settings["style_type"] != self.STYLE_TYPES[text_type]:
            raise ValueError(
                f"Invalid style_type for {text_type}: {settings['style_type']}"
            )

        if not isinstance(settings["style_value"], int):
            raise ValueError("style_value must be an integer")

        # Validate other components
        self.validate_colors(settings["colors"], settings["style_type"])
        self.validate_position(settings["position"])
        self.validate_margins(settings["margins"])

        # Add font validation
        if not self._manager.font.validate_font(settings["font"]):
            raise ValueError(f"Invalid font path: {settings['font']}")

        return True


class SettingsManager:
    def __init__(self):
        self.templates_dir = (
            Path(__file__).parent.parent / "assets" / "setting_templates"
        )
        self.fonts_dir = Path(__file__).parent.parent / "assets" / "fonts"
        self.templates_dir.mkdir(exist_ok=True)

        with open(Path(__file__).parent / "default_settings_template.json", "r") as f:
            self._default_template = json.load(f)

        self.load_template = TemplateContainer(self)
        self.font = FontContainer(self)
        self.validator = SettingsValidator(self)

    def get_template(self, name: str = "default") -> Dict:
        """Get template by name (internal use)"""
        if name == "default":
            return self._default_template.copy()

        template_path = self.templates_dir / f"{name}.json"
        if not template_path.exists():
            raise ValueError(f"Template '{name}' not found")

        with open(template_path, "r") as f:
            return json.load(f)

    def _get_base_settings(self, base: Optional[Union[str, Dict]] = None) -> Dict:
        """Get base settings from template name, dict, or default"""
        if base is None:
            return self.load_template.default()
        elif isinstance(base, str):
            return self.load_template.get_template(base)
        elif isinstance(base, dict):
            self.validate_settings(base)
            return base.copy()
        else:
            raise ValueError("base must be None, template name, or settings dict")

    def modify_base_settings(
        self,
        variations: Optional[int] = None,
        default_text_type: Optional[str] = None,
        log_level: Optional[str] = None,
        base: Optional[Union[str, Dict]] = None,
    ) -> Dict:
        """
        Modify base settings using template name, settings dict, or default

        Args:
            variations: Number of variations to generate
            default_text_type: Default text type to use ("plain" or "highlight")
            log_level: Optional logging level (uses template value if not provided)
            base: Template name, settings dict, or None for default
        """
        settings = self._get_base_settings(base)

        if variations is not None:
            settings["base_settings"]["variations"] = variations
        if default_text_type:
            if default_text_type not in settings["text_settings"]:
                raise ValueError(
                    f"default_text_type '{default_text_type}' not found in text_settings"
                )
            settings["base_settings"]["default_text_type"] = default_text_type
        if log_level is not None:
            settings["base_settings"]["log_level"] = log_level

        return settings

    def modify_text_settings(
        self,
        text_type: Union[str, List[str]],
        font_size: Optional[int] = None,
        font: Optional[str] = None,
        colors: Optional[List[Dict]] = None,
        position: Optional[
            Tuple[
                Optional[List[float]],
                Optional[List[float]],
                Optional[float],
                Optional[float],
            ]
        ] = None,
        margins: Optional[
            Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]
        ] = None,
        style_value: Optional[int] = None,
        base: Optional[Union[str, Dict]] = None,
    ) -> Dict:
        """
        Modify text settings using template name, settings dict, or default

        Args:
            text_type: "plain", "highlight", "both", or list of types
            font_size: Text size (default: 70)
            font: Font path (default: assets.fonts.tiktokfont.ttf)
            colors: List of color dicts
                   plain: [{"text": "#FFF", "outline": "#000"}, ...]
                   highlight: [{"text": "#000", "background": "#FFF"}, ...]
            position: (vertical_range, horizontal_range, vertical_jitter, horizontal_jitter)
                     vertical_range: [0.0-1.0, 0.0-1.0] - vertical position range
                     horizontal_range: [0.0-1.0, 0.0-1.0] - horizontal position range
                     vertical_jitter: 0.0-1.0 - vertical randomness
                     horizontal_jitter: 0.0-1.0 - horizontal randomness
                     Example: ([0.7, 0.8], None, 0.05, None) - only change vertical and v_jitter
            margins: (top, bottom, left, right) values 0.0-1.0
                    Example: (0.05, None, 0.1, None) - only change top and left margins
            style_value: Value for style_type (outline_width or corner_radius)
            base: Optional template to modify instead of default

        Returns:
            Dict: Modified settings
        """
        settings = self._get_base_settings(base)

        # Handle text_type input
        if text_type == "both":
            text_types = ["plain", "highlight"]
        elif isinstance(text_type, str):
            text_types = [text_type]
        else:
            text_types = text_type

        for t_type in text_types:
            if t_type not in settings["text_settings"]:
                raise ValueError(f"Invalid text_type: {t_type}")

            base_settings = settings["text_settings"][t_type]

            # Update basic settings
            if font_size:
                base_settings["font_size"] = font_size
            if font:
                base_settings["font"] = font
            if colors:
                base_settings["colors"] = colors
            if style_value is not None:
                base_settings["style_value"] = style_value

            # Update position - using tuple style
            if position:
                vertical, horizontal, v_jitter, h_jitter = position
                current_position = base_settings["position"]

                # Only update if value is not None
                if vertical is not None:
                    current_position["vertical"] = vertical
                if horizontal is not None:
                    current_position["horizontal"] = horizontal
                if v_jitter is not None:
                    current_position["vertical_jitter"] = v_jitter
                if h_jitter is not None:
                    current_position["horizontal_jitter"] = h_jitter

                # Validate the updated position
                self.validator.validate_position(current_position)

            # Update margins
            if margins:
                top, bottom, left, right = margins
                if top is not None:
                    base_settings["margins"]["top"] = top
                if bottom is not None:
                    base_settings["margins"]["bottom"] = bottom
                if left is not None:
                    base_settings["margins"]["left"] = left
                if right is not None:
                    base_settings["margins"]["right"] = right

        return settings

    def save_template(self, settings: Dict, name: str) -> None:
        """Save settings as a named template"""
        if name == "default":
            raise ValueError("Cannot overwrite default template")

        template_path = self.templates_dir / f"{name}.json"
        with open(template_path, "w") as f:
            json.dump(settings, f, indent=2)
        logger.info(f"Saved template: {name}")

    def validate_settings(self, settings: Dict) -> bool:
        """Validate settings structure and values"""
        if "base_settings" not in settings:
            raise ValueError("Missing base_settings")
        if "text_settings" not in settings:
            raise ValueError("Missing text_settings")

        # Validate all text settings exist and are valid
        for text_type, text_settings in settings["text_settings"].items():
            self.validator.validate_text_settings(text_settings, text_type)

        # Ensure default_text_type points to valid settings
        if "default_text_type" not in settings["base_settings"]:
            raise ValueError("Missing default_text_type in base_settings")
        if (
            settings["base_settings"]["default_text_type"]
            not in settings["text_settings"]
        ):
            raise ValueError(
                f"default_text_type '{settings['base_settings']['default_text_type']}' must exist in text_settings"
            )

        return True

    def add_text_type(
        self,
        text_type: str,
        font_size: int = 70,
        font: str = "assets.fonts.tiktokfont.ttf",
        style_type: str = "outline_width",
        style_value: int = 2,
        colors: List[Dict] = None,
        position: Dict = None,
        margins: Dict = None,
        base_template: Optional[Dict] = None,
    ) -> Dict:
        """
        Add a new text type with settings

        Args:
            text_type: Name of the new text type
            font_size: Text size (default: 70)
            font: Font path
            style_type: "outline_width" or "corner_radius"
            style_value: Value for style_type
            colors: List of color dicts matching style_type
            position: Position settings (will use defaults if None)
            margins: Margin settings (will use defaults if None)
            base_template: Optional template to modify instead of default
        """
        settings = base_template.copy() if base_template else self.get_template()

        # Use default position/margins if not provided
        default_position = {
            "vertical": [0.7, 0.8],
            "horizontal": [0.45, 0.55],
            "vertical_jitter": 0.01,
            "horizontal_jitter": 0.02,
        }

        default_margins = {"top": 0.05, "bottom": 0.05, "left": 0.05, "right": 0.05}

        # Create new text type settings
        new_settings = {
            "font_size": font_size,
            "font": font,
            "product_duplicate_prevention": False,
            "style_type": style_type,
            "style_value": style_value,
            "colors": colors or [{"text": "#FFFFFF", "outline": "#000000"}],
            "position": position or default_position,
            "margins": margins or default_margins,
        }

        # Add to text_settings
        settings["text_settings"][text_type] = new_settings

        return settings
