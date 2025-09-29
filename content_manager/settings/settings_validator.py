import re
from pathlib import Path
from typing import Dict, List, Literal, Optional, Union

from content_manager.settings.settings_constants import VALID_TEXT_TYPES

# TODO product settings cannot have duplicate settings!!!


class SettingsValidator:
    """Validates all settings operations against defined rules and constants."""

    def __init__(self):
        self.fonts_dir = Path("assets/fonts")
        self.VALID_TEXT_TYPES = VALID_TEXT_TYPES

    def validate_settings(self, settings: Dict) -> bool:
        """Validate complete settings block.

        Args:
            settings: Complete settings dictionary

        Returns:
            bool: True if valid

        Raises:
            ValueError: With specific validation error
        """
        # Check exact required keys exist
        required_keys = {"base_settings", "text_settings"}
        settings_keys = set(settings.keys())

        # Check for missing required keys
        if missing := (required_keys - settings_keys):
            raise ValueError(f"Missing required settings sections: {missing}")

        # Check for extra unexpected keys
        if extra := (settings_keys - required_keys):
            raise ValueError(f"Unexpected settings sections found: {extra}")

        # First validate text_settings structure and required fields
        for text_type, type_settings in settings["text_settings"].items():
            required_fields = ["colors", "font", "margins", "position", "style_type", "style_value"]
            missing_fields = [field for field in required_fields if field not in type_settings]
            if missing_fields:
                raise ValueError(f"Missing required settings for text type '{text_type}': {', '.join(missing_fields)}")

        # Then validate base_settings and default_text_type
        self.validate_base_settings(settings["base_settings"])
        default_type = settings["base_settings"]["default_text_type"]
        if default_type not in settings["text_settings"]:
            raise ValueError(f"Default text type '{default_type}' not found in text_settings")

        # Finally do detailed validation of each section
        self.validate_text_settings(settings["text_settings"])

        return True

    def validate_base_settings(self, base_settings: Dict) -> bool:
        """Validate base settings section.

        Args:
            base_settings: Base settings dictionary

        Returns:
            bool: True if valid

        Raises:
            ValueError: With specific validation error
        """
        # Check only default_text_type exists
        allowed_keys = {"default_text_type"}
        if extra := (set(base_settings.keys()) - allowed_keys):
            raise ValueError(f"Unexpected keys in base_settings: {extra}")

        # Check default_text_type exists and is valid
        if "default_text_type" not in base_settings:
            raise ValueError("Missing default_text_type in base settings")

        if base_settings["default_text_type"] not in self.VALID_TEXT_TYPES:
            raise ValueError(
                f"Invalid default_text_type: {base_settings['default_text_type']}"
            )

        return True

    def validate_text_settings(self, text_settings: Dict) -> bool:
        """Validate text settings section.

        Args:
            text_settings: Text settings dictionary

        Returns:
            bool: True if valid

        Raises:
            ValueError: With specific validation error
        """
        # Check at least one text type exists
        if not text_settings:
            raise ValueError("No text types defined")

        # Validate each text type
        for text_type, settings in text_settings.items():
            if text_type not in self.VALID_TEXT_TYPES:
                raise ValueError(f"Invalid text type: {text_type}")

            # Check required fields first
            self._validate_required_fields(text_type, settings)

            # Then validate each field
            self._validate_font_size(text_type, settings)
            self._validate_font(text_type, settings)
            self._validate_style_type(text_type, settings)
            self._validate_style_value(text_type, settings)
            self._validate_colors(text_type, settings)

            # --- Margins Validation ---
            self._validate_margins(text_type, settings)
            # --- Position Validation ---
            self._validate_position(text_type, settings)
            self._validate_position_margins_compatibility(text_type, settings)

        return True

    def _validate_required_fields(self, text_type: str, settings: Dict) -> None:
        """Validate that all required fields exist for a text type.

        Args:
            text_type: The type of text being validated
            settings: Settings dictionary for this text type

        Raises:
            ValueError: If any required fields are missing
        """
        required_fields = {
            "font_size",
            "font",
            "style_type",
            "style_value",
            "colors",
            "position",
            "margins",
        }

        missing_fields = required_fields - set(settings.keys())
        if missing_fields:
            raise ValueError(
                f"Missing required settings for text type '{text_type}': {', '.join(sorted(missing_fields))}"
            )

    def _validate_font_size(self, text_type: str, settings: Dict) -> None:
        """Validate font size is positive integer."""
        if not isinstance(settings["font_size"], int) or settings["font_size"] <= 0:
            raise ValueError(
                f"Invalid font size for {text_type}: must be positive integer"
            )

    def _validate_font(self, text_type: str, settings: Dict) -> None:
        """Validate font path and existence."""
        font = settings["font"]
        if not isinstance(font, str):
            raise ValueError(f"Invalid font for {text_type}: must be string")

        # Validate basic format
        if not font.startswith("assets.fonts.") or not font.endswith(".ttf"):
            raise ValueError(f"Invalid font path format for {text_type}: {font}")

        # Split into meaningful parts: assets.fonts.fontname.ttf
        parts = font.split(".")
        if len(parts) != 4:  # We expect exactly 4 parts
            raise ValueError(f"Invalid font path structure for {text_type}: {font}")

        base, fonts_dir, font_name, extension = parts

        # Validate each part
        if base != "assets":
            raise ValueError(f"Font path must start with 'assets': {font}")
        if fonts_dir != "fonts":
            raise ValueError(f"Font path must be in 'fonts' directory: {font}")
        if not font_name:
            raise ValueError(f"Font name cannot be empty: {font}")
        if extension != "ttf":
            raise ValueError(f"Font must be TTF format: {font}")

        # Check if font file actually exists
        font_path = self.fonts_dir / f"{font_name}.{extension}"
        if not font_path.exists():
            raise ValueError(f"Font file does not exist: {font_name}.{extension}")

    def _validate_style_type(self, text_type: str, settings: Dict) -> None:
        """Validate style type matches text type."""
        expected_style = self.VALID_TEXT_TYPES[text_type]["style_type"]
        if settings["style_type"] != expected_style:
            raise ValueError(
                f"Invalid style_type for {text_type}: must be {expected_style}"
            )

    def _validate_style_value(self, text_type: str, settings: Dict) -> None:
        """Validate style value is positive integer."""
        if not isinstance(settings["style_value"], int) or settings["style_value"] <= 0:
            raise ValueError(
                f"Invalid style value for {text_type}: must be positive integer"
            )

    def _validate_colors(self, text_type: str, settings: Dict) -> bool:
        """Validate color list and hex color formats."""
        colors = settings["colors"]

        if not isinstance(colors, list):
            raise ValueError("Colors must be a list")

        if not colors:
            raise ValueError("Colors list cannot be empty")

        required_keys = self.VALID_TEXT_TYPES[text_type]["required_color_keys"]
        # Always put 'text' first, then the other key
        sorted_required_keys = ["text"] + [k for k in required_keys if k != "text"]
        required_keys_set = set(required_keys)
        seen_colors = {}

        for color in colors:
            if not isinstance(color, dict):
                raise ValueError("Each color must be a dictionary")

            if set(color.keys()) != required_keys_set:
                # Create error message with text first
                sorted_keys_str = "{'" + "', '".join(sorted_required_keys) + "'}"
                raise ValueError(
                    f"Each color must contain exactly: {sorted_keys_str} for type '{text_type}'"
                )

            for key, value in color.items():
                if not self._is_valid_hex_color(value):
                    raise ValueError(f"Invalid hex color for {key}: {value}")

            color_combo = tuple(f"{key}={color[key]}" for key in sorted_required_keys)
            if color_combo in seen_colors:
                first_occurrence = seen_colors[color_combo]
                error_msg = f"Duplicate color combination found: {', '.join(f'{key}={first_occurrence[key]}' for key in sorted_required_keys)}"
                raise ValueError(error_msg)
            seen_colors[color_combo] = color

        return True

    def _is_valid_hex_color(self, color: str) -> bool:
        """Validate hex color format."""
        if not isinstance(color, str):
            return False
        # Match exactly: # followed by exactly 6 hex digits (0-9 or A-F)
        return bool(re.match(r"^#[0-9A-F]{6}$", color))

    def _validate_position(self, text_type: str, settings: Dict) -> bool:
        """Validate position settings in both dictionary and tuple formats."""
        position = settings["position"]

        # Handle tuple format
        if isinstance(position, tuple):
            if len(position) != 4:
                raise ValueError(
                    "Position tuple must have 4 values (vertical, horizontal, v_jitter, h_jitter)"
                )

            vert, horiz, v_jitter, h_jitter = position

            # Validate vertical position if provided
            if vert is not None:
                if not isinstance(vert, tuple) or len(vert) != 2:
                    raise ValueError("Vertical position must be a tuple of 2 values")
                if not all(0 <= x <= 1 for x in vert):
                    raise ValueError("Vertical position values must be between 0 and 1")

                # Add min/max validation for tuple format
                if vert[0] >= vert[1]:
                    raise ValueError("Vertical position min must be less than max")

            # Validate horizontal position if provided
            if horiz is not None:
                if not isinstance(horiz, tuple) or len(horiz) != 2:
                    raise ValueError("Horizontal position must be a tuple of 2 values")
                if not all(0 <= x <= 1 for x in horiz):
                    raise ValueError(
                        "Horizontal position values must be between 0 and 1"
                    )

                # Add min/max validation for tuple format
                if horiz[0] >= horiz[1]:
                    raise ValueError("Horizontal position min must be less than max")

            # Validate jitters if provided
            for jitter in (v_jitter, h_jitter):
                if jitter is not None:
                    if not isinstance(jitter, (int, float)) or not 0 <= jitter <= 0.5:
                        raise ValueError("Jitter must be between 0 and 0.5")

            return True

        # Handle dictionary format
        if not isinstance(position, dict):
            raise ValueError("Position must be either a tuple or dictionary")

        required_keys = {
            "vertical",
            "horizontal",
            "vertical_jitter",
            "horizontal_jitter",
        }
        if set(position.keys()) != required_keys:
            raise ValueError(f"Position must contain exactly: {required_keys}")

        # Validate ranges and min/max order
        for key in ["vertical", "horizontal"]:
            if not isinstance(position[key], list) or len(position[key]) != 2:
                raise ValueError(f"{key} position must be a list of 2 values")
            if not all(0 <= x <= 1 for x in position[key]):
                raise ValueError(f"{key} position values must be between 0 and 1")
            # Add min/max validation
            if position[key][0] >= position[key][1]:
                raise ValueError(f"{key} position min must be less than max")

        # Validate jitters
        for key in ["vertical_jitter", "horizontal_jitter"]:
            if (
                not isinstance(position[key], (int, float))
                or not 0 <= position[key] <= 0.5
            ):
                raise ValueError(f"{key} must be between 0 and 0.5")

        return True

    def _validate_margins(self, text_type: str, settings: Dict) -> bool:
        """Validate margin settings in both dictionary and tuple formats."""
        margins = settings["margins"]

        # Handle tuple format
        if isinstance(margins, tuple):
            if len(margins) != 4:
                raise ValueError(
                    "Margins tuple must have 4 values (top, bottom, left, right)"
                )

            top, bottom, left, right = margins

            # Validate each provided margin
            for margin in margins:
                if margin is not None:
                    if not isinstance(margin, (int, float)) or not 0 <= margin < 1:
                        raise ValueError("Each margin must be between 0 and 1")

            # Check vertical margins sum if both provided
            if top is not None and bottom is not None:
                if top + bottom >= 1:
                    raise ValueError(
                        "Sum of top and bottom margins must be less than 1"
                    )

            # Check horizontal margins sum if both provided
            if left is not None and right is not None:
                if left + right >= 1:
                    raise ValueError(
                        "Sum of left and right margins must be less than 1"
                    )

            return True

        # Handle dictionary format
        if not isinstance(margins, dict):
            raise ValueError("Margins must be either a tuple or dictionary")

        required_keys = {"top", "bottom", "left", "right"}
        if set(margins.keys()) != required_keys:
            raise ValueError(f"Margins must contain exactly: {required_keys}")

        # Validate individual margins
        for key in required_keys:
            if not isinstance(margins[key], (int, float)) or not 0 <= margins[key] < 1:
                raise ValueError(f"{key} margin must be between 0 and 1")

        # Validate vertical and horizontal sums separately
        if margins["top"] + margins["bottom"] >= 1:
            raise ValueError("Sum of top and bottom margins must be less than 1")

        if margins["left"] + margins["right"] >= 1:
            raise ValueError("Sum of left and right margins must be less than 1")

        return True

    def _validate_position_margins_compatibility(
        self, text_type: str, settings: Dict
    ) -> None:
        """Validate that positions and jitter cannot generate values within margins."""
        margins = settings["margins"]
        position = settings["position"]

        # Get position ranges and jitters
        v_min, v_max = position["vertical"]
        h_min, h_max = position["horizontal"]
        v_jitter = position["vertical_jitter"]
        h_jitter = position["horizontal_jitter"]

        # Calculate absolute bounds after jitter
        v_absolute_min = v_min - v_jitter
        v_absolute_max = v_max + v_jitter
        h_absolute_min = h_min - h_jitter
        h_absolute_max = h_max + h_jitter

        # Check vertical bounds against margins
        if v_absolute_min <= margins["top"]:
            raise ValueError(
                f"Vertical position {v_min} with jitter {v_jitter} could overlap top margin {margins['top']}"
            )
        if v_absolute_max >= (1 - margins["bottom"]):
            raise ValueError(
                f"Vertical position {v_max} with jitter {v_jitter} could overlap bottom margin {margins['bottom']}"
            )

        # Check horizontal bounds against margins
        if h_absolute_min <= margins["left"]:
            raise ValueError(
                f"Horizontal position {h_min} with jitter {h_jitter} could overlap left margin {margins['left']}"
            )
        if h_absolute_max >= (1 - margins["right"]):
            raise ValueError(
                f"Horizontal position {h_max} with jitter {h_jitter} could overlap right margin {margins['right']}"
            )
