import copy
import json
import unittest
from pathlib import Path

import pytest

from content_manager.settings.settings_validator import SettingsValidator

# Load default template for "known good" tests
DEFAULT_TEMPLATE = Path("assets/templates/default.json").read_text()


class TestSettingsValidator(unittest.TestCase):
    def setUp(self):
        self.validator = SettingsValidator()

    # Basic Structure Tests & Base Settings Tests
    def test_valid_complete_settings(self):
        """Test complete valid settings from default template."""
        settings = json.loads(DEFAULT_TEMPLATE)
        assert self.validator.validate_settings(settings) is True

    def test_missing_required_sections(self):
        """Test missing main sections."""
        with pytest.raises(ValueError, match="Missing required settings sections"):
            self.validator.validate_settings({"base_settings": {}})

    def test_all_test_settings_are_valid(self):
        """Ensure all test settings used in tests are valid."""
        # Load and validate the default template
        self.valid_test_settings = json.loads(DEFAULT_TEMPLATE)
        assert self.validator.validate_settings(self.valid_test_settings) is True

    def test_extra_sections(self):
        """Test extra unexpected sections."""
        settings = json.loads(DEFAULT_TEMPLATE)
        settings["extra_section"] = {}
        with pytest.raises(ValueError, match="Unexpected settings sections found"):
            self.validator.validate_settings(settings)

    def test_default_text_type_must_be_valid(self):
        """Test that default_text_type must be a valid type."""
        settings = json.loads(DEFAULT_TEMPLATE)
        settings["base_settings"]["default_text_type"] = "nonexistent"  # Invalid type
        with pytest.raises(ValueError, match="Invalid default_text_type: nonexistent"):
            self.validator.validate_settings(settings)

    def test_base_settings_only_default_text_type(self):
        """Test base_settings only allows default_text_type key."""
        settings = json.loads(DEFAULT_TEMPLATE)
        settings["base_settings"]["extra_key"] = "value"  # This should fail
        with pytest.raises(ValueError, match="Unexpected keys in base_settings"):
            self.validator.validate_settings(settings)

    def test_default_text_type_must_exist_in_text_settings(self):
        """Test that default_text_type must have corresponding settings."""
        settings = json.loads(DEFAULT_TEMPLATE)
        # Store the original settings for the other type
        other_type_settings = settings["text_settings"]["plain"].copy()

        # Change default type to something not in text_settings
        settings["base_settings"]["default_text_type"] = "plain"
        # Replace with only one type (not the default)
        settings["text_settings"] = {
            "heading": other_type_settings  # Use the complete settings structure
        }
        with pytest.raises(
            ValueError, match="Default text type 'plain' not found in text_settings"
        ):
            self.validator.validate_settings(settings)

    def test_default_text_type_must_have_complete_settings(self):
        """Test that default_text_type settings are complete."""
        settings = json.loads(DEFAULT_TEMPLATE)
        # Remove required fields to test validation
        settings["text_settings"]["plain"] = {
            "font_size": 70,
            "font": "assets.fonts.tiktokfont.ttf",
        }
        expected_error = "Missing required settings for text type 'plain': colors, margins, position, style_type, style_value"
        with pytest.raises(ValueError, match=expected_error):
            self.validator.validate_settings(settings)

    # TEXT SETTINGS TESTS
    # Font Tests
    def test_font_validation(self):
        """Test font path validation with various inputs."""
        test_cases = [
            ("assets.fonts.tiktokfont.ttf", True),
            ("assets.fonts.missing.ttf", False),
            ("invalid.path.ttf", False),
            ("assets.fonts.noextension", False),
        ]

        for font_path, expected_valid in test_cases:
            settings = {"text_type": "plain", "settings": {"font": font_path}}

            if expected_valid:
                self.validator._validate_font(**settings)
            else:
                with self.assertRaises(ValueError):
                    self.validator._validate_font(**settings)

    # Position Tests - Extended
    def test_position_validation(self):
        """Test both dictionary and tuple formats for position updates."""
        test_cases = [
            # Valid dictionary formats
            (
                {
                    "vertical": [0.1, 0.2],
                    "horizontal": [0.3, 0.4],
                    "vertical_jitter": 0.1,
                    "horizontal_jitter": 0.1,
                },
                True,
            ),
            (
                {
                    "vertical": [0, 1],
                    "horizontal": [0, 1],
                    "vertical_jitter": 0,
                    "horizontal_jitter": 0,
                },
                True,
            ),
            # Valid tuple formats - complete
            ((None, None, None, None), True),
            (((0.1, 0.2), (0.3, 0.4), 0.1, 0.1), True),
            # Valid tuple formats - partial updates
            (((0.1, 0.2), None, None, None), True),
            ((None, (0.3, 0.4), None, None), True),
            ((None, None, 0.1, None), True),
            ((None, None, None, 0.1), True),
            # Invalid - Out of range values
            (((1.1, 0.2), (0.3, 0.4), 0.1, 0.1), False),  # Vertical out of range
            (((0.1, 0.2), (1.1, 0.4), 0.1, 0.1), False),  # Horizontal out of range
            (((0.1, 0.2), (0.3, 0.4), 0.6, 0.1), False),  # V-jitter too large
            (((0.1, 0.2), (0.3, 0.4), 0.1, 0.6), False),  # H-jitter too large
            # Invalid - Wrong tuple sizes
            (((0.1,), (0.3, 0.4), 0.1, 0.1), False),  # Vertical tuple too small
            (
                ((0.1, 0.2, 0.3), (0.3, 0.4), 0.1, 0.1),
                False,
            ),  # Vertical tuple too large
            (((0.1, 0.2), (0.3,), 0.1, 0.1), False),  # Horizontal tuple too small
            (
                ((0.1, 0.2), (0.3, 0.4, 0.5), 0.1, 0.1),
                False,
            ),  # Horizontal tuple too large
            # Invalid - Mixed formats
            (
                {"position": (0.1, 0.2), "vertical": [0.3, 0.4]},
                False,
            ),  # Can't mix tuple and dict
            (
                {"vertical": (0.1, 0.2)},
                False,
            ),  # Wrong type in dict (tuple instead of list)
        ]

        for position, expected_valid in test_cases:
            settings = {"text_type": "plain", "settings": {"position": position}}

            if expected_valid:
                self.validator._validate_position(**settings)
            else:
                with self.assertRaises(ValueError):
                    self.validator._validate_position(**settings)

    # Margin Tests
    def test_margin_validation(self):
        """Test both dictionary and tuple formats for margin updates."""
        test_cases = [
            # Valid dictionary formats
            ({"top": 0.1, "bottom": 0.2, "left": 0.3, "right": 0.4}, True),
            ({"top": 0, "bottom": 0, "left": 0, "right": 0}, True),
            (
                {"top": 0.3, "bottom": 0.3, "left": 0.3, "right": 0.3},
                True,
            ),  # All 0.3 is valid
            (
                {"top": 0.8, "bottom": 0.1, "left": 0.8, "right": 0.1},
                True,
            ),  # Large individual margins OK
            # Valid tuple formats - complete
            ((0.1, 0.2, 0.3, 0.4), True),
            ((0.3, 0.3, 0.3, 0.3), True),  # All 0.3 in tuple format
            ((0.8, 0.1, 0.8, 0.1), True),  # Large margins in tuple format
            # Valid tuple formats - partial updates
            ((None, None, None, None), True),
            ((0.8, None, None, None), True),
            ((None, 0.8, None, None), True),
            ((None, None, 0.8, None), True),
            ((None, None, None, 0.8), True),
            # Invalid - Missing or extra keys
            ({"top": 0.5, "bottom": 0.5}, False),  # Missing keys
            ({"top": 0.1, "extra": 0.1}, False),  # Extra keys
            # Invalid - Out of range values
            ({"top": -0.1, "bottom": 0, "left": 0, "right": 0}, False),  # Negative
            ({"top": 1.1, "bottom": 0, "left": 0, "right": 0}, False),  # > 1
            ((1.1, 0, 0, 0), False),  # Same in tuple format
            # Invalid - Vertical sum >= 1
            ({"top": 0.6, "bottom": 0.5, "left": 0.1, "right": 0.1}, False),
            ((0.6, 0.5, 0.1, 0.1), False),
            # Invalid - Horizontal sum >= 1
            ({"top": 0.1, "bottom": 0.1, "left": 0.6, "right": 0.5}, False),
            ((0.1, 0.1, 0.6, 0.5), False),
            # Invalid - Individual margin = 1
            ({"top": 1.0, "bottom": 0.0, "left": 0.1, "right": 0.1}, False),
            ((1.0, 0.0, 0.1, 0.1), False),
            # Invalid - Wrong tuple length
            ((0.1, 0.2, 0.3), False),  # Too short
            ((0.1, 0.2, 0.3, 0.4, 0.5), False),  # Too long
        ]

        for margins, expected_valid in test_cases:
            settings = {"text_type": "plain", "settings": {"margins": margins}}

            if expected_valid:
                self.validator._validate_margins(**settings)
            else:
                with self.assertRaises(ValueError):
                    self.validator._validate_margins(**settings)

    def test_position_margin_compatibility(self):
        """Test position and margin compatibility validation."""
        test_cases = [
            # Valid cases - positions well within margins
            (
                {
                    "margins": {"top": 0.1, "bottom": 0.1, "left": 0.1, "right": 0.1},
                    "position": {
                        "vertical": [0.2, 0.3],
                        "horizontal": [0.2, 0.3],
                        "vertical_jitter": 0.01,
                        "horizontal_jitter": 0.01,
                    },
                },
                True,
            ),
            # Valid cases - positions close to but not overlapping margins
            (
                {
                    "margins": {"top": 0.1, "bottom": 0.1, "left": 0.1, "right": 0.1},
                    "position": {
                        "vertical": [0.11, 0.89],
                        "horizontal": [0.11, 0.89],
                        "vertical_jitter": 0.001,
                        "horizontal_jitter": 0.001,
                    },
                },
                True,
            ),
            # Invalid - position range overlaps top margin
            (
                {
                    "margins": {"top": 0.2, "bottom": 0.1, "left": 0.1, "right": 0.1},
                    "position": {
                        "vertical": [0.15, 0.3],  # Starts below margin
                        "horizontal": [0.2, 0.3],
                        "vertical_jitter": 0.01,
                        "horizontal_jitter": 0.01,
                    },
                },
                False,
            ),
            # Invalid - position range overlaps bottom margin
            (
                {
                    "margins": {"top": 0.1, "bottom": 0.2, "left": 0.1, "right": 0.1},
                    "position": {
                        "vertical": [0.7, 0.85],  # Ends above margin
                        "horizontal": [0.2, 0.3],
                        "vertical_jitter": 0.01,
                        "horizontal_jitter": 0.01,
                    },
                },
                False,
            ),
            # Invalid - jitter would push into top margin
            (
                {
                    "margins": {"top": 0.1, "bottom": 0.1, "left": 0.1, "right": 0.1},
                    "position": {
                        "vertical": [0.11, 0.3],  # Valid range
                        "horizontal": [0.2, 0.3],
                        "vertical_jitter": 0.02,  # But jitter too large
                        "horizontal_jitter": 0.01,
                    },
                },
                False,
            ),
            # Invalid - jitter would push into bottom margin
            (
                {
                    "margins": {"top": 0.1, "bottom": 0.1, "left": 0.1, "right": 0.1},
                    "position": {
                        "vertical": [0.7, 0.89],  # Valid range
                        "horizontal": [0.2, 0.3],
                        "vertical_jitter": 0.02,  # But jitter too large
                        "horizontal_jitter": 0.01,
                    },
                },
                False,
            ),
            # Invalid - horizontal position overlaps left margin
            (
                {
                    "margins": {"top": 0.1, "bottom": 0.1, "left": 0.2, "right": 0.1},
                    "position": {
                        "vertical": [0.2, 0.3],
                        "horizontal": [0.15, 0.3],  # Starts in margin
                        "vertical_jitter": 0.01,
                        "horizontal_jitter": 0.01,
                    },
                },
                False,
            ),
            # Invalid - horizontal position overlaps right margin
            (
                {
                    "margins": {"top": 0.1, "bottom": 0.1, "left": 0.1, "right": 0.2},
                    "position": {
                        "vertical": [0.2, 0.3],
                        "horizontal": [0.7, 0.85],  # Ends in margin
                        "vertical_jitter": 0.01,
                        "horizontal_jitter": 0.01,
                    },
                },
                False,
            ),
            # Invalid - horizontal jitter would push into left margin
            (
                {
                    "margins": {"top": 0.1, "bottom": 0.1, "left": 0.1, "right": 0.1},
                    "position": {
                        "vertical": [0.2, 0.3],
                        "horizontal": [0.11, 0.3],  # Valid range
                        "vertical_jitter": 0.01,
                        "horizontal_jitter": 0.02,  # But jitter too large
                    },
                },
                False,
            ),
            # Invalid - horizontal jitter would push into right margin
            (
                {
                    "margins": {"top": 0.1, "bottom": 0.1, "left": 0.1, "right": 0.1},
                    "position": {
                        "vertical": [0.2, 0.3],
                        "horizontal": [0.7, 0.89],  # Valid range
                        "vertical_jitter": 0.01,
                        "horizontal_jitter": 0.02,  # But jitter too large
                    },
                },
                False,
            ),
            # Edge cases - exactly at margin boundaries
            (
                {
                    "margins": {"top": 0.1, "bottom": 0.1, "left": 0.1, "right": 0.1},
                    "position": {
                        "vertical": [0.1, 0.9],  # Exactly at margins
                        "horizontal": [0.1, 0.9],  # Exactly at margins
                        "vertical_jitter": 0.0,  # No jitter
                        "horizontal_jitter": 0.0,
                    },
                },
                False,
            ),  # Should fail as we don't want positions exactly at margins
        ]

        for settings, expected_valid in test_cases:
            if expected_valid:
                self.validator._validate_position_margins_compatibility(
                    "test_type", settings
                )
            else:
                with self.assertRaises(ValueError):
                    self.validator._validate_position_margins_compatibility(
                        "test_type", settings
                    )

    def test_colors_validation(self):
        """Test color list validation."""
        test_cases = [
            # Valid cases - Different combinations
            ([{"text": "#FFFFFF", "outline": "#000000"}], "plain", True, None),
            ([{"text": "#FFFFFF", "background": "#000000"}], "highlight", True, None),
            (
                [
                    {"text": "#FFFFFF", "outline": "#000000"},
                    {"text": "#000000", "outline": "#FFFFFF"},  # Different combo
                ],
                "plain",
                True,
                None,
            ),
            # Invalid - Duplicate exact colors
            (
                [
                    {"text": "#FFFFFF", "outline": "#000000"},
                    {"text": "#FFFFFF", "outline": "#000000"},  # Exact duplicate
                ],
                "plain",
                False,
                "Duplicate color combination found: text=#FFFFFF, outline=#000000",
            ),
            # Invalid - Same colors different order
            (
                [
                    {"text": "#FFFFFF", "outline": "#000000"},
                    {
                        "outline": "#000000",
                        "text": "#FFFFFF",
                    },  # Same values, different order
                ],
                "plain",
                False,
                "Duplicate color combination found: text=#FFFFFF, outline=#000000",
            ),
            # Invalid - Multiple duplicates
            (
                [
                    {"text": "#FFFFFF", "outline": "#000000"},
                    {"text": "#000000", "outline": "#FFFFFF"},
                    {"text": "#FFFFFF", "outline": "#000000"},  # Duplicate of first
                ],
                "plain",
                False,
                "Duplicate color combination found: text=#FFFFFF, outline=#000000",
            ),
            # Structure tests
            ([], "plain", False, "Colors list cannot be empty"),
            ({}, "plain", False, "Colors must be a list"),
            (None, "plain", False, "Colors must be a list"),
            # Mixed keys in list
            (
                [
                    {"text": "#FFFFFF", "outline": "#000000"},
                    {"text": "#FFFFFF", "background": "#000000"},
                ],
                "plain",
                False,
                "Each color must contain exactly: {'text', 'outline'} for type 'plain'",
            ),
            # Edge cases
            (
                [{"text": "#FFFFFF", "outline": "#000000", "extra": "#FF0000"}],
                "plain",
                False,
                "Each color must contain exactly: {'text', 'outline'} for type 'plain'",
            ),
            (
                [{"text": "#FFFFFF", "outline": ""}],
                "plain",
                False,
                "Invalid hex color for outline: ",
            ),
            (
                [{"text": "#FFFFFF", "outline": None}],
                "plain",
                False,
                "Invalid hex color for outline: None",
            ),
            (
                [{"text": "#FFFFFF", "outline": 123}],
                "plain",
                False,
                "Invalid hex color for outline: 123",
            ),
            # Hex validation
            (
                [{"text": "000000", "outline": "#000000"}],
                "plain",
                False,
                "Invalid hex color for text: 000000",
            ),
            (
                [{"text": "#00000", "outline": "#000000"}],
                "plain",
                False,
                "Invalid hex color for text: #00000",
            ),
            (
                [{"text": "#0000000", "outline": "#000000"}],
                "plain",
                False,
                "Invalid hex color for text: #0000000",
            ),
            (
                [{"text": "#GGGGGG", "outline": "#000000"}],
                "plain",
                False,
                "Invalid hex color for text: #GGGGGG",
            ),
            (
                [{"text": "#FFfFFF", "outline": "#000000"}],
                "plain",
                False,
                "Invalid hex color for text: #FFfFFF",
            ),
            # 1. Weird Hex Colors
            (
                [{"text": "#ffffff", "outline": "#000000"}],
                "plain",
                False,
                "Invalid hex color for text: #ffffff",
            ),  # lowercase
            (
                [{"text": "#FFF", "outline": "#000"}],
                "plain",
                False,
                "Invalid hex color for text: #FFF",
            ),  # too short
            (
                [{"text": "FFFFFF", "outline": "#000000"}],
                "plain",
                False,
                "Invalid hex color for text: FFFFFF",
            ),  # no #
            (
                [{"text": "#FFFFFF ", "outline": "#000000"}],
                "plain",
                False,
                "Invalid hex color for text: #FFFFFF ",
            ),  # extra space
            # 2. Bad List Items
            ([None], "plain", False, "Each color must be a dictionary"),  # None in list
            (
                [123],
                "plain",
                False,
                "Each color must be a dictionary",
            ),  # number in list
            (
                [{}],
                "plain",
                False,
                "Each color must contain exactly: {'text', 'outline'} for type 'plain'",
            ),  # empty dict
            # 3. Missing/Extra Stuff
            (
                [{"text": "#FFFFFF"}],
                "plain",
                False,
                "Each color must contain exactly: {'text', 'outline'} for type 'plain'",
            ),  # missing key
            (
                [{"text": "#FFFFFF", "outline": "#000000", "extra": "#FF0000"}],
                "plain",
                False,
                "Each color must contain exactly: {'text', 'outline'} for type 'plain'",
            ),  # extra key
            (
                [{"text": "#FFFFFF", "background": "#000000"}],
                "plain",
                False,
                "Each color must contain exactly: {'text', 'outline'} for type 'plain'",
            ),  # wrong keys
        ]

        for colors, text_type, expected_valid, expected_error in test_cases:
            settings = {"text_type": text_type, "settings": {"colors": colors}}

            if expected_valid:
                self.validator._validate_colors(**settings)
            else:
                with self.assertRaises(ValueError) as cm:
                    self.validator._validate_colors(**settings)
                self.assertEqual(str(cm.exception), expected_error)
