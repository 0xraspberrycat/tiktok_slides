import json
from pathlib import Path
from typing import Dict, List, Literal, Optional, Union

from content_manager.settings.settings_validator import SettingsValidator

# Text type constants


class Settings:
    """Handles all settings operations and validation for content and product settings.

    This class manages:
    1. Template Operations:
        - Loading/saving templates (templates cannot be overwritten)
        - Listing available templates and fonts
        - Template validation before saving

    2. Settings Modification:
        - Base settings changes (default_text_type)
        - Text type specific settings (plain/highlight)
        - Adding new text types with validation

    3. Settings Application:
        - Content level settings (override all)
        - Product level settings (inherit from content)
        - Custom settings (highest priority)
        - Bulk application with overwrite protection
        - Automatic group merging for identical settings

    Settings Structure:
        {
            "base_settings": {
                "default_text_type": "plain"  # or "highlight"
            },
            "text_settings": {
                "plain": {  # Outline style
                    "font_size": int,
                    "font": "assets.fonts.X.ttf",
                    "style_type": "outline_width",
                    "style_value": int,
                    "colors": [{"text": "#hex", "outline": "#hex"}, ...],
                    "position": {
                        "vertical": [float, float],  # 0-1 range
                        "horizontal": [float, float],  # 0-1 range
                        "vertical_jitter": float,
                        "horizontal_jitter": float
                    },
                    "margins": {
                        "top": float,    # 0-1 range
                        "bottom": float,
                        "left": float,
                        "right": float
                    }
                },
                "highlight": {  # Background style
                    # Same structure but with background colors
                    "colors": [{"text": "#hex", "background": "#hex"}, ...]
                }
            }
        }

    Usage:
        settings = Settings()

        # Load and modify template
        my_settings = settings.load_template("default")

        # Modify base settings
        my_settings = settings.modify_base_settings(
            settings=my_settings,
            default_text_type="highlight"
        )

        # Modify text type settings - individual changes
        my_settings = settings.modify_settings(
            settings=my_settings,
            text_type="plain",
            font_size=80,
            vertical_jitter=0.05,
            left_margin=0.1
        )

        # Bulk apply with overwrite check
        targets = {
            "hook": ["product1", "product2"],
            "content": ["product3"]
        }
        settings.bulk_apply_settings(settings_dict, targets)

        # Modify colors (complete replacement)
        my_settings = settings.modify_settings(
            settings=my_settings,
            text_type="highlight",
            colors=[
                {"text": "#000000", "background": "#FFFFFF"},
                {"text": "#FFFFFF", "background": "#FF0000"}
            ]
        )

        # Save modified settings
        settings.save_template(my_settings, "my_template")

        # Apply to content
        settings.apply_content_settings("hook", my_settings)
    """

    def __init__(self):
        self.templates_dir = Path("assets/setting_templates")
        self.fonts_dir = Path("assets/fonts")
        self.settings_validator = SettingsValidator()

    # TEMPLATE OPERATIONS
    def list_templates(self) -> List[str]:
        """List available templates.

        Available templates:
        {{ templates }}

        Returns:
            List[str]: Template names without .json extension
        """
        templates = [p.stem for p in self.templates_dir.glob("*.json")]

        # Generate template list for docstring
        template_list = "\n".join(f"* {t}" for t in templates)
        self.list_templates.__doc__ = self.list_templates.__doc__.replace(
            "{{ templates }}", template_list or "* No templates found"
        )

        return templates

    def list_fonts(self) -> List[str]:
        """List available fonts.

        Available fonts:
        {{ fonts }}

        Returns:
            List[str]: Font paths in assets.fonts.X.ttf format
        """
        fonts = [f"assets.fonts.{p.stem}.ttf" for p in self.fonts_dir.glob("*.ttf")]

        # Generate font list for docstring
        font_list = "\n".join(f"* {f}" for f in fonts)
        self.list_fonts.__doc__ = self.list_fonts.__doc__.replace(
            "{{ fonts }}", font_list or "* No fonts found"
        )

        return fonts

    def load_template(self, name: str = "default") -> Dict:
        """Load settings template from templates directory.

        Args:
            name: Template name to load

        Available templates:
        {{ templates }}

        Returns:
            Dict: Complete settings block

        Raises:
            ValueError: If template doesn't exist or is invalid
            FileNotFoundError: If template file not found
        """
        # Generate template list for docstring
        templates = self.list_templates()
        template_list = "\n".join(f"* {t}" for t in templates)
        self.load_template.__doc__ = self.load_template.__doc__.replace(
            "{{ templates }}", template_list or "* No templates found"
        )

        template_path = self.templates_dir / f"{name}.json"
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {name}")

        with open(template_path) as f:
            settings = json.load(f)

        if not self.settings_validator.validate_settings(settings):
            raise ValueError(f"Invalid template: {name}")

        return settings

    def save_template(self, settings: Dict, name: str) -> None:
        """Save settings template to templates directory.

        Args:
            settings: Settings template
            name: Template name

        Raises:
            ValueError: If name is "default" or template already exists
            ValueError: If settings invalid
        """
        if name == "default":
            raise ValueError("Cannot overwrite default template")

        template_path = self.templates_dir / f"{name}.json"
        if template_path.exists():
            raise ValueError(f"Template already exists: {name}")

        if not self.settings_validator.validate_settings(settings):
            raise ValueError("Invalid settings")

        with open(template_path, "w") as f:
            json.dump(settings, f, indent=2)

    # SETTINGS MODIFICATION
    def modify_base_settings(
        self, settings: Dict, default_text_type: Optional[str] = None
    ) -> Dict:
        """Modify base settings.

        Args:
            settings: Complete settings block
            default_text_type: New default text type ("plain" or "highlight")

        Returns:
            Dict: Modified settings

        Raises:
            ValueError: If text_type invalid
        """
        if default_text_type:
            if default_text_type not in ["plain", "highlight"]:
                raise ValueError("default_text_type must be 'plain' or 'highlight'")
            settings["base_settings"]["default_text_type"] = default_text_type
        return settings

    def modify_settings(
        self,
        settings: Dict,
        text_type: str,
        font_size: Optional[int] = None,
        font: Optional[str] = None,
        style_value: Optional[int] = None,
        colors: Optional[List[Dict]] = None,
        vertical_position: Optional[List[float]] = None,
        horizontal_position: Optional[List[float]] = None,
        vertical_jitter: Optional[float] = None,
        horizontal_jitter: Optional[float] = None,
        top_margin: Optional[float] = None,
        bottom_margin: Optional[float] = None,
        left_margin: Optional[float] = None,
        right_margin: Optional[float] = None,
    ) -> Dict:
        """Modify settings for a specific text type.

        Args:
            settings: Complete settings block
            text_type: Text type to modify ("plain" or "highlight")
            font_size: New font size
            font: New font path
            style_value: New style value (outline_width or corner_radius)
            colors: New colors list (completely replaces existing)
            vertical_position: New vertical position [min, max]
            horizontal_position: New horizontal position [min, max]
            vertical_jitter: New vertical jitter
            horizontal_jitter: New horizontal jitter
            top_margin: New top margin
            bottom_margin: New bottom margin
            left_margin: New left margin
            right_margin: New right margin

        Notes:
            - Position and margin changes can be individual
            - Colors are completely replaced when changed
            - style_type is fixed per text_type (plain=outline_width, highlight=corner_radius)

        Returns:
            Dict: Modified settings

        Raises:
            ValueError: If any values invalid
        """
        if text_type not in settings["text_settings"]:
            raise ValueError(f"Invalid text_type: {text_type}")

        text_settings = settings["text_settings"][text_type]

        # Basic settings updates
        if font_size is not None:
            text_settings["font_size"] = font_size
        if font is not None:
            text_settings["font"] = font
        if style_value is not None:
            text_settings["style_value"] = style_value
        if colors is not None:
            text_settings["colors"] = colors

        # Position updates - validate no conflicts
        position_count = sum(
            1 for x in [vertical_position, horizontal_position] if x is not None
        )
        jitter_count = sum(
            1 for x in [vertical_jitter, horizontal_jitter] if x is not None
        )

        if position_count > 0 and jitter_count > 0:
            raise ValueError("Cannot update both position and jitter at once")

        # Apply position changes
        if vertical_position is not None:
            text_settings["position"]["vertical"] = vertical_position
        if horizontal_position is not None:
            text_settings["position"]["horizontal"] = horizontal_position
        if vertical_jitter is not None:
            text_settings["position"]["vertical_jitter"] = vertical_jitter
        if horizontal_jitter is not None:
            text_settings["position"]["horizontal_jitter"] = horizontal_jitter

        # Margin updates (can be individual)
        if top_margin is not None:
            text_settings["margins"]["top"] = top_margin
        if bottom_margin is not None:
            text_settings["margins"]["bottom"] = bottom_margin
        if left_margin is not None:
            text_settings["margins"]["left"] = left_margin
        if right_margin is not None:
            text_settings["margins"]["right"] = right_margin

        # Validate modified settings
        if not self.settings_validator.validate_settings(settings):
            raise ValueError("Invalid settings after modification")

        return settings

    def add_text_type(
        self,
        settings: Dict,
        text_type: str,
        style_type: Literal["outline_width", "corner_radius"],
        font_size: int,
        font: str,
        style_value: int,
        colors: List[Dict],
        position: Dict[str, Union[List[float], float]],
        margins: Dict[str, float],
    ) -> Dict:
        """Add new text type with complete settings block.

        Args:
            settings: Complete settings block
            text_type: New text type name
            style_type: Either "outline_width" or "corner_radius"
            font_size: Font size
            font: Font path
            style_value: Style value (width or radius)
            colors: List of color dicts matching style_type
            position: Complete position dict
            margins: Complete margins dict

        Returns:
            Dict: Modified settings

        Raises:
            ValueError: If text_type exists or settings invalid
        """
        if text_type in settings["text_settings"]:
            raise ValueError(f"Text type already exists: {text_type}")

        # Create new text type settings
        new_settings = {
            "font_size": font_size,
            "font": font,
            "style_type": style_type,
            "style_value": style_value,
            "colors": colors,
            "position": position,
            "margins": margins,
        }

        # Add to text_settings
        settings["text_settings"][text_type] = new_settings

        # Validate complete settings
        if not self.settings_validator.validate_settings(settings):
            raise ValueError("Invalid settings for new text type")

        return settings

    # SETTINGS APPLICATION
    def apply_content_settings(self, content_type: str, settings: Dict) -> None:
        """Apply settings at content type level.

        Args:
            content_type: Content type to apply settings to
            settings: Complete settings block

        Raises:
            ValueError: If content type invalid or settings invalid
        """
        # TODO: Check existing settings
        # TODO: Validate before applying
        pass

    def apply_product_settings(
        self,
        content_type: str,
        product: str,
        settings: Dict,
        confirm_overwrite: bool = False,
    ) -> None:
        """Apply settings at product level.

        Args:
            content_type: Content type product belongs to
            product: Product to apply settings to
            settings: Complete settings block
            confirm_overwrite: Force overwrite existing settings

        Raises:
            ValueError: If product invalid or settings invalid
        """
        # TODO: Check content settings exist
        # TODO: Handle product group merging
        pass

    def bulk_apply_settings(
        self,
        settings: Dict,
        targets: Dict[str, List[str]],
        confirm_overwrite: bool = False,
    ) -> None:
        """
            Bulk apply settings to multiple content types and their products.

            Args:
                settings: Settings dictionary to apply
                targets: Dict mapping content_types to list of products
                        Example: {"hook": ["product1", "product2"],
                                 "content": ["product3"]}
                confirm_overwrite: Force overwrite existing settings

            Notes:
                - Use slides.print_products() to get current structure
                - Modify that output for bulk_apply targets
                - Validates all products exist before applying
                - Checks for existing settings before overwriting
                - Merges product groups with identical settings
                - Groups only merged within same content_type

        TODO:
                - Add print_products helper to Slides/Metadata
                - Validate all products exist
                - Check for existing settings
                - Implement group merging logic
                - Add progress/status prints
        """
        # TODO: Implement bulk apply logic
        # TODO: Add overwrite protection
        # TODO: Handle group merging
        pass
