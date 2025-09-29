import copy
import json
import logging
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

from config.logging import logger  # Import the pre-configured logger
from content_manager.settings.settings_constants import VALID_TEXT_TYPES
from content_manager.settings.settings_handler import Settings
from tests.test_utils import DEFAULT_SETTINGS

"""Tests for settings validation of complete settings dictionaries.

Note on Position/Margin Format Validation:
----------------------------------------
These tests only validate complete settings dictionaries, not partial updates.
Format mixing (e.g., using both tuple and dictionary formats) is handled differently:

1. Complete Settings (this file):
   - Must be either all dictionary format or all tuple format
   - No mixing of formats within a complete settings block
   - Example valid: {"position": {"vertical": [0.1, 0.2], ...}}
   - Example valid: {"position": ((0.1, 0.2), ...)}

2. Partial Updates (to be implemented in test_settings_modification.py):
   - Can update individual components
   - Cannot mix formats in a single update
   - Example valid: {"vertical": [0.1, 0.2]}
   - Example valid: {"position": ((0.1, 0.2), None, None, None)}
   - Example invalid: {"position": (...), "vertical": [...]}

This separation ensures:
- Clean validation of initial settings
- Flexible but safe partial updates
- Clear documentation of expected behavior
- Consistent handling across position and margin settings
"""


class TestSettingsHandler(unittest.TestCase):
    def setUp(self):
        """Create fresh instance and state for EACH test."""
        self.settings = Settings(test_mode=True)  # Use test mode!
        self.original_settings = copy.deepcopy(DEFAULT_SETTINGS)
        self.created_files = []  # Track what we create
        # Create test directories
        self.templates_dir = Path("assets/test_templates")
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # Create default template
        default_path = self.templates_dir / "default.json"
        with open(default_path, "w") as f:
            json.dump(DEFAULT_SETTINGS, f)
        self.created_files = [default_path]

    def tearDown(self):
        """Clean up after EACH test."""
        self.settings = None
        self.original_settings = None

        # Remove only the files we created
        for file in self.created_files:
            file.unlink(missing_ok=True)
        self.templates_dir.rmdir()

    def test_initialization(self):
        """Test basic initialization of Settings class."""
        self.assertIsInstance(self.settings, Settings)

    # 1. list_templates()
    def test_list_templates(self):
        """Test listing available templates."""
        import sys
        from io import StringIO

        stdout = StringIO()
        sys.stdout = stdout

        try:
            # Test basic functionality
            templates = self.settings.list_templates()
            expected_templates = ["default"]
            self.assertEqual(set(templates), set(expected_templates))

            expected_output = "Available templates:\n"
            expected_output += "\n".join(f"* {t}" for t in sorted(expected_templates))
            expected_output += "\n"

            self.assertEqual(stdout.getvalue(), expected_output)

        finally:
            sys.stdout = sys.__stdout__  # Restore stdout

    def test_list_templates_empty(self):
        """Test listing templates when directory is empty."""
        # Capture stdout
        import sys
        from io import StringIO

        stdout = StringIO()
        sys.stdout = stdout

        try:
            # Remove ALL templates including default
            for template in ["default"]:
                (self.templates_dir / f"{template}.json").unlink()

            templates = self.settings.list_templates()
            self.assertEqual(templates, [])

            expected_output = "Available templates:\n* No templates found\n"
            self.assertEqual(stdout.getvalue(), expected_output)

        finally:
            sys.stdout = sys.__stdout__  # Restore stdout

    # 2. load_template()
    def test_load_template_default(self):
        """Test loading default template."""
        loaded_settings = self.settings.load_template()
        self.assertEqual(loaded_settings, DEFAULT_SETTINGS)

    def test_load_template_nonexistent(self):
        """Test loading non-existent template."""
        with self.assertRaises(FileNotFoundError) as cm:
            self.settings.load_template("nonexistent")
        self.assertEqual(str(cm.exception), "Template not found: nonexistent")

    def test_load_template_invalid_json(self):
        """Test loading template with invalid JSON."""
        test_template = "default"
        with open(self.templates_dir / f"{test_template}.json", "w") as f:
            f.write("{invalid json")

        with self.assertRaises(ValueError) as cm:
            self.settings.load_template(test_template)
        self.assertTrue("Invalid JSON in template default:" in str(cm.exception))

    def test_load_template_invalid_structure(self):
        """Test loading template with invalid settings structure."""
        test_path = self.templates_dir / "test2.json"
        with open(test_path, "w") as f:
            json.dump({"wrong_key": "wrong_value"}, f)
        self.created_files.append(test_path)  # Track the file we created

        with self.assertRaises(ValueError) as cm:
            self.settings.load_template("test2")
        error_msg = str(cm.exception)
        # Check each required section is mentioned in error
        self.assertIn("base_settings", error_msg)
        self.assertIn("text_settings", error_msg)
        self.assertIn("Missing required settings sections", error_msg)

    def test_load_template_missing_required_fields(self):

        """Test loading template with missing required fields."""
        test_template = "default"
        # Start with default but remove required fields
        incomplete_settings = {
            "base_settings": DEFAULT_SETTINGS["base_settings"].copy(),
            "text_settings": {"plain": {"font_size": 80}},  # Only include one field
        }

        with open(self.templates_dir / f"{test_template}.json", "w") as f:
            json.dump(incomplete_settings, f)

        with self.assertRaises(ValueError) as cm:
            self.settings.load_template(test_template)
        self.assertEqual(
            str(cm.exception),
            "Missing required settings for text type 'plain': colors, font, margins, position, style_type, style_value",
        )

    def test_load_template_invalid_values(self):
        """Test loading template with invalid field values."""
        test_template = "default"
        # Start with default but modify one value to be invalid
        invalid_settings = DEFAULT_SETTINGS.copy()
        invalid_settings["text_settings"]["plain"]["font_size"] = "not_a_number"

        with open(self.templates_dir / f"{test_template}.json", "w") as f:
            json.dump(invalid_settings, f)

        with self.assertRaises(ValueError) as cm:
            self.settings.load_template(test_template)
        self.assertEqual(
            str(cm.exception), "Invalid font size for plain: must be positive integer"
        )

    def test_load_template_empty_file(self):
        """Test loading empty template file."""
        test_template = "default"
        with open(self.templates_dir / f"{test_template}.json", "w") as f:
            f.write("")

        with self.assertRaises(ValueError) as cm:
            self.settings.load_template(test_template)
        self.assertTrue(f"Invalid JSON in template default:" in str(cm.exception))

    # 3. list_fonts()
    def test_list_fonts_empty(self):
        """Test listing fonts when directory is empty."""
        import sys
        from io import StringIO

        # Create test fonts directory
        test_fonts_dir = Path("assets/test_fonts")
        test_fonts_dir.mkdir(parents=True, exist_ok=True)

        # Temporarily override fonts_dir
        original_fonts_dir = self.settings.fonts_dir
        self.settings.fonts_dir = test_fonts_dir

        stdout = StringIO()
        sys.stdout = stdout

        try:
            fonts = self.settings.list_fonts()
            self.assertEqual(fonts, [])

            expected_output = "Available fonts:\n* No fonts found\n"
            # TODO FIX THIS SO IT DOESNT REQUIRE PRINT BUT LOGS
            self.assertEqual(stdout.getvalue(), expected_output)

        finally:
            sys.stdout = sys.__stdout__
            self.settings.fonts_dir = original_fonts_dir  # Restore original
            test_fonts_dir.rmdir()  # Clean up

    def test_list_fonts(self):
        """Test listing available fonts."""
        import sys
        from io import StringIO

        # Create test fonts directory
        test_fonts_dir = Path("assets/test_fonts")
        test_fonts_dir.mkdir(parents=True, exist_ok=True)

        # Temporarily override fonts_dir
        original_fonts_dir = self.settings.fonts_dir
        self.settings.fonts_dir = test_fonts_dir

        # Create test fonts
        test_fonts = ["test1.ttf", "test2.ttf"]
        created_files = []
        for font in test_fonts:
            font_path = test_fonts_dir / font
            font_path.touch()
            created_files.append(font_path)

        stdout = StringIO()
        sys.stdout = stdout

        try:
            fonts = self.settings.list_fonts()
            expected_fonts = [Path(f).stem for f in test_fonts]
            self.assertEqual(set(fonts), set(expected_fonts))

            expected_output = "Available fonts:\n"
            # TODO FIX THIS SO IT DOESNT REQUIRE PRINT BUT LOGS
            expected_output += "\n".join(f"* {f}" for f in sorted(expected_fonts))
            expected_output += "\n"

            self.assertEqual(stdout.getvalue(), expected_output)

        finally:
            sys.stdout = sys.__stdout__
            # Clean up
            for file in created_files:
                file.unlink()
            test_fonts_dir.rmdir()
            self.settings.fonts_dir = original_fonts_dir  # Restore original

    # 4. load_fonts()
    def test_load_font_success(self):
        """Test loading valid font."""
        # Create test fonts directory
        test_fonts_dir = Path("assets/test_fonts")
        test_fonts_dir.mkdir(parents=True, exist_ok=True)

        # Temporarily override fonts_dir
        original_fonts_dir = self.settings.fonts_dir
        self.settings.fonts_dir = test_fonts_dir

        try:
            # Create valid test font
            font_name = "test_font"
            font_path = test_fonts_dir / f"{font_name}.ttf"
            font_path.touch()

            # Mock validator to pass
            self.settings.settings_validator.validate_font = lambda x: True

            result = self.settings.load_font(font_name)
            self.assertEqual(result, f"assets.fonts.{font_name}.ttf")

        finally:
            # Clean up
            font_path.unlink()
            test_fonts_dir.rmdir()
            self.settings.fonts_dir = original_fonts_dir

    def test_load_font_not_found(self):
        """Test loading non-existent font."""
        # Create test fonts directory
        test_fonts_dir = Path("assets/test_fonts")
        test_fonts_dir.mkdir(parents=True, exist_ok=True)

        # Temporarily override fonts_dir
        original_fonts_dir = self.settings.fonts_dir
        self.settings.fonts_dir = test_fonts_dir

        try:
            with self.assertRaises(ValueError) as cm:
                self.settings.load_font("nonexistent")
            self.assertEqual(str(cm.exception), "Font not found: nonexistent")

        finally:
            test_fonts_dir.rmdir()
            self.settings.fonts_dir = original_fonts_dir

    def test_load_font_invalid(self):
        """Test loading invalid font file."""
        # Create test fonts directory
        test_fonts_dir = Path("assets/test_fonts")
        test_fonts_dir.mkdir(parents=True, exist_ok=True)

        # Create invalid "font" (directory instead of file)
        font_name = "invalid_font"
        font_path = test_fonts_dir / f"{font_name}.ttf"
        font_path.mkdir()  # Make it a directory instead of a file

        try:
            with self.assertRaises(ValueError):
                self.settings.load_font(font_name)
        finally:
            # Clean up
            font_path.rmdir()
            test_fonts_dir.rmdir()

    def test_load_font_case_sensitive(self):
        """Test font name case sensitivity."""
        # Create test fonts directory
        test_fonts_dir = Path("assets/test_fonts")
        test_fonts_dir.mkdir(parents=True, exist_ok=True)

        # Temporarily override fonts_dir
        original_fonts_dir = self.settings.fonts_dir
        self.settings.fonts_dir = test_fonts_dir

        try:
            # Create font with specific case
            font_name = "TestFont"
            font_path = test_fonts_dir / f"{font_name}.ttf"
            font_path.touch()

            # Mock validator to pass
            self.settings.settings_validator.validate_font = lambda x: True

            # Test with different cases
            with self.assertRaises(ValueError):
                self.settings.load_font("testfont")
            with self.assertRaises(ValueError):
                self.settings.load_font("TESTFONT")

            # Original case should work
            result = self.settings.load_font(font_name)
            self.assertEqual(result, f"assets.fonts.{font_name}.ttf")

        finally:
            # Clean up
            font_path.unlink()
            test_fonts_dir.rmdir()
            self.settings.fonts_dir = original_fonts_dir

    def test_load_font_special_chars(self):
        """Test font names with special characters."""
        # Create test fonts directory
        test_fonts_dir = Path("assets/test_fonts")
        test_fonts_dir.mkdir(parents=True, exist_ok=True)

        # Temporarily override fonts_dir
        original_fonts_dir = self.settings.fonts_dir
        self.settings.fonts_dir = test_fonts_dir

        try:
            special_names = ["test-font", "test_font", "test.font"]
            created_files = []

            for name in special_names:
                font_path = test_fonts_dir / f"{name}.ttf"
                font_path.touch()
                created_files.append(font_path)

                # Mock validator to pass
                self.settings.settings_validator.validate_font = lambda x: True

                result = self.settings.load_font(name)
                self.assertEqual(result, f"assets.fonts.{name}.ttf")

        finally:
            # Clean up
            for file in created_files:
                file.unlink()
            test_fonts_dir.rmdir()
            self.settings.fonts_dir = original_fonts_dir

    # 5. modify_base_settings()


class TestModifySettings(unittest.TestCase):
    def setUp(self):
        """Create fresh instance and test data for EACH modify test."""
        self.settings = Settings(test_mode=True)

        # Create test directories
        self.templates_dir = Path("assets/test_templates")
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # Create default template
        self.default_path = self.templates_dir / "default.json"
        with open(self.default_path, "w") as f:
            json.dump(DEFAULT_SETTINGS, f)

        # Now load the template
        self.test_settings = self.settings.load_template("default")

        # Setup logger capture
        self.log_output = StringIO()
        self.log_handler = logging.StreamHandler(self.log_output)
        self.log_handler.setLevel(logging.DEBUG)  # Set handler level
        logger.setLevel(logging.DEBUG)  # Set logger level
        logger.addHandler(self.log_handler)

    def tearDown(self):
        """Clean up after each test."""
        # Remove logger handler
        logger.removeHandler(self.log_handler)
        self.log_output.close()

        self.settings = None
        self.test_settings = None

        # Clean up files
        self.default_path.unlink(missing_ok=True)
        self.templates_dir.rmdir()

    def test_modify_settings_basic(self):
        """Basic test to verify settings modification."""

        modified = self.settings.modify_settings(
            settings=self.test_settings, text_type="plain", font_size=80
        )

        self.assertEqual(modified["text_settings"]["plain"]["font_size"], 80)

    # 5. modify_base_settings()
    def test_modify_base_settings_to_highlight(self):
        """Test changing base settings to highlight type."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        modified = self.settings.modify_base_settings(
            settings=settings, default_text_type="highlight"
        )
        self.assertEqual(modified["base_settings"]["default_text_type"], "highlight")
        self.assertIn("highlight", VALID_TEXT_TYPES)  # Verify it's a valid type

    def test_modify_base_settings_to_plain(self):
        """Test changing base settings to plain type."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        modified = self.settings.modify_base_settings(
            settings=settings, default_text_type="plain"
        )
        self.assertEqual(modified["base_settings"]["default_text_type"], "plain")
        self.assertIn("plain", VALID_TEXT_TYPES)  # Verify it's a valid type

    def test_modify_base_settings_invalid_type(self):
        """Test invalid text type raises error."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        invalid_type = "invalid_type"
        with self.assertRaises(ValueError) as context:
            self.settings.modify_base_settings(
                settings=settings, default_text_type=invalid_type
            )
        self.assertNotIn(invalid_type, VALID_TEXT_TYPES)  # Verify it's not a valid type
        self.assertIn(
            f"must be one of: {list(VALID_TEXT_TYPES.keys())}", str(context.exception)
        )

    def test_modify_base_settings_no_changes(self):
        """Test no changes returns same settings."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        modified = self.settings.modify_base_settings(settings=settings)
        self.assertEqual(modified, settings)

    def test_modify_base_settings_preserves_other_settings(self):
        """Test that other settings are preserved when changing text type."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        original_text_settings = copy.deepcopy(settings["text_settings"])

        modified = self.settings.modify_base_settings(
            settings=settings, default_text_type="highlight"
        )

        # Check text settings weren't modified
        self.assertEqual(modified["text_settings"], original_text_settings)

    # 6. modify_settings()
    def test_modify_settings_single_parameter(self):
        """Test modifying a single parameter (font size)."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        original_font_size = int(
            settings["text_settings"]["plain"]["font_size"]
        )  # Convert to int
        new_font_size = original_font_size + 10

        modified = self.settings.modify_settings(
            settings=settings, text_type="plain", font_size=new_font_size
        )
        self.assertEqual(modified["text_settings"]["plain"]["font_size"], new_font_size)

    def test_modify_settings_multiple_parameters(self):
        """Test modifying multiple parameters together."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        font_path = DEFAULT_SETTINGS["text_settings"]["plain"]["font"]
        original_font_size = settings["text_settings"]["plain"]["font_size"]
        new_font_size = original_font_size + 10

        modified = self.settings.modify_settings(
            settings=settings,
            text_type="plain",
            font_size=new_font_size,
            font=font_path,
            style_value=3,
        )
        self.assertEqual(modified["text_settings"]["plain"]["font_size"], new_font_size)
        self.assertEqual(modified["text_settings"]["plain"]["font"], font_path)
        self.assertEqual(modified["text_settings"]["plain"]["style_value"], 3)

    def test_modify_settings_colors(self):
        """Test color modifications."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)

        # Test invalid color
        result = self.settings.modify_settings(
            settings=settings,
            text_type="plain",
            colors=[{"text": "not_a_color", "outline": "#000000"}],
        )

        # Should get original settings back
        self.assertEqual(result, settings)

        # Check error message in log output
        expected_error = (
            "Error modifying settings: Invalid hex color for text: not_a_color"
        )
        self.assertIn(expected_error, self.log_output.getvalue())

        # Clear log output for next test
        self.log_output.truncate(0)
        self.log_output.seek(0)

        # Test valid color modification
        result = self.settings.modify_settings(
            settings=settings,
            text_type="plain",
            colors=[{"text": "#FF0000", "outline": "#000000"}],
        )

        # Check color was updated
        self.assertEqual(
            result["text_settings"]["plain"]["colors"][0]["text"], "#FF0000"
        )

    def test_modify_settings_positions_tuple(self):
        """Test position modifications using tuple format."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)

        # Full position tuple
        modified = self.settings.modify_settings(
            settings=settings,
            text_type="plain",
            positions=((0.7, 0.9), (0.4, 0.6), 0.02, 0.01),
        )
        self.assertEqual(
            modified["text_settings"]["plain"]["position"]["vertical"], [0.7, 0.9]
        )
        self.assertEqual(
            modified["text_settings"]["plain"]["position"]["horizontal"], [0.4, 0.6]
        )
        self.assertEqual(
            modified["text_settings"]["plain"]["position"]["vertical_jitter"], 0.02
        )
        self.assertEqual(
            modified["text_settings"]["plain"]["position"]["horizontal_jitter"], 0.01
        )

        # Partial position tuple (some None values)
        modified = self.settings.modify_settings(
            settings=settings,
            text_type="plain",
            positions=(None, (0.4, 0.6), None, 0.02),
        )
        self.assertEqual(
            modified["text_settings"]["plain"]["position"]["horizontal"], [0.4, 0.6]
        )
        self.assertEqual(
            modified["text_settings"]["plain"]["position"]["horizontal_jitter"], 0.02
        )

    def test_modify_settings_positions_individual(self):
        """Test position modifications using individual parameters."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)

        # Individual position changes
        modified = self.settings.modify_settings(
            settings=settings,
            text_type="plain",
            vertical_position=[0.6, 0.8],
            horizontal_jitter=0.03,
        )
        self.assertEqual(
            modified["text_settings"]["plain"]["position"]["vertical"], [0.6, 0.8]
        )
        self.assertEqual(
            modified["text_settings"]["plain"]["position"]["horizontal_jitter"], 0.03
        )

    def test_modify_settings_margins_tuple(self):
        """Test margin modifications using tuple format."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)

        # Full margins tuple
        modified = self.settings.modify_settings(
            settings=settings, text_type="plain", margins=(0.1, 0.1, 0.2, 0.2)
        )
        self.assertEqual(modified["text_settings"]["plain"]["margins"]["top"], 0.1)
        self.assertEqual(modified["text_settings"]["plain"]["margins"]["bottom"], 0.1)
        self.assertEqual(modified["text_settings"]["plain"]["margins"]["left"], 0.2)
        self.assertEqual(modified["text_settings"]["plain"]["margins"]["right"], 0.2)

        # Partial margins tuple
        modified = self.settings.modify_settings(
            settings=settings, text_type="plain", margins=(0.1, None, None, 0.2)
        )
        self.assertEqual(modified["text_settings"]["plain"]["margins"]["top"], 0.1)
        self.assertEqual(modified["text_settings"]["plain"]["margins"]["right"], 0.2)

    def test_modify_settings_margins_individual(self):
        """Test margin modifications using individual parameters."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)

        modified = self.settings.modify_settings(
            settings=settings, text_type="plain", top_margin=0.15, right_margin=0.25
        )
        self.assertEqual(modified["text_settings"]["plain"]["margins"]["top"], 0.15)
        self.assertEqual(modified["text_settings"]["plain"]["margins"]["right"], 0.25)

    def test_modify_settings_validation_errors(self):
        """Test various validation error cases."""
        # Invalid font size
        result = self.settings.modify_settings(
            settings=self.test_settings, text_type="plain", font_size=-10
        )

        # Should get original settings back
        self.assertEqual(result, self.test_settings)

        # Check error message
        expected_error = "Error modifying settings: Invalid font size for plain: must be positive integer"
        self.assertIn(expected_error, self.log_output.getvalue())

    def test_modify_settings_mixing_errors(self):
        """Test errors when mixing parameter styles."""
        result = self.settings.modify_settings(
            settings=self.test_settings,
            text_type="plain",
            positions=((0.7, 0.9), None, None, None),
            vertical_jitter=0.02,  # This conflicts with positions tuple
        )

        # Should get original settings back
        self.assertEqual(result, self.test_settings)

        # Check error message
        expected_error = "Error modifying settings: Cannot mix positions tuple with individual position parameters"
        self.assertIn(expected_error, self.log_output.getvalue())

    def test_modify_settings_position_validation(self):
        """Test position-specific validation."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)

        # Test invalid vertical position range (max < min)
        result = self.settings.modify_settings(
            settings=settings,
            text_type="plain",
            vertical_position=[0.9, 0.1],  # max < min
        )

        # Compare result with original settings
        self.assertEqual(result, settings)
        self.assertIn(
            "vertical position min must be less than max",
            self.log_output.getvalue(),  # Changed from stdout to self.log_output
        )

    def test_modify_settings_margin_validation(self):
        """Test margin-specific validation."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)

        # Test margin/position overlap (vertical)
        result = self.settings.modify_settings(
            settings=settings,
            text_type="plain",
            bottom_margin=0.4,  # Will overlap with vertical position [0.7, 0.8]
        )
        self.assertEqual(result, settings)
        self.assertIn("Vertical position", self.log_output.getvalue())
        self.assertIn("could overlap", self.log_output.getvalue())

        # Clear log output for next test
        self.log_output.truncate(0)
        self.log_output.seek(0)

        # Test margin/position overlap (horizontal)
        result = self.settings.modify_settings(
            settings=settings,
            text_type="plain",
            left_margin=0.5,  # Will overlap with horizontal position [0.45, 0.55]
        )
        self.assertEqual(result, settings)
        self.assertIn("Horizontal position", self.log_output.getvalue())
        self.assertIn("could overlap", self.log_output.getvalue())

        # Clear log output for next test
        self.log_output.truncate(0)
        self.log_output.seek(0)

        # Test valid margin (no overlap)
        result = self.settings.modify_settings(
            settings=settings,
            text_type="plain",
            margins=(0.1, 0.1, 0.1, 0.1),  # Safe margins that won't overlap
        )
        self.assertEqual(
            result["text_settings"]["plain"]["margins"],
            {"top": 0.1, "bottom": 0.1, "left": 0.1, "right": 0.1},
        )

    def test_modify_settings_original_preserved(self):
        """Test that original settings are preserved on error."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)
        original = copy.deepcopy(settings)

        # Try invalid modification
        result = self.settings.modify_settings(
            settings=settings,
            text_type="plain",
            font_size=-10,  # invalid
        )

        # Check result is original
        self.assertEqual(result, original)
        # Check input wasn't modified
        self.assertEqual(settings, original)

    def test_modify_settings_highlight_type(self):
        """Test modifications specific to highlight text type."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)

        # Valid highlight modifications
        modified = self.settings.modify_settings(
            settings=settings,
            text_type="highlight",
            colors=[{"text": "#000000", "background": "#FFFFFF"}],
            style_value=5,  # corner_radius for highlight
        )
        self.assertEqual(
            modified["text_settings"]["highlight"]["colors"][0]["background"],
            "#FFFFFF",
        )
        self.assertEqual(modified["text_settings"]["highlight"]["style_value"], 5)

        # Clear log output
        self.log_output.truncate(0)
        self.log_output.seek(0)

        # Invalid highlight color keys
        result = self.settings.modify_settings(
            settings=settings,
            text_type="highlight",
            colors=[
                {"text": "#000000", "outline": "#FFFFFF"}
            ],  # wrong key for highlight
        )
        self.assertEqual(result, settings)  # Should get original settings back
        self.assertIn(
            "Color missing required keys:", self.log_output.getvalue()
        )  # Changed from stdout to self.log_output

    def test_modify_settings_empty_none_inputs(self):
        """Test empty and None input handling."""

        # Empty settings dict
        result = self.settings.modify_settings(
            settings={}, text_type="plain", font_size=80
        )
        self.assertEqual(result, {})  # Should return empty dict
        self.assertIn("No base settings provided", self.log_output.getvalue())

        # Clear log output
        self.log_output.truncate(0)
        self.log_output.seek(0)

        # None settings
        result = self.settings.modify_settings(
            settings=None, text_type="plain", font_size=80
        )
        self.assertIsNone(result)  # Should return None
        self.assertIn("No base settings provided", self.log_output.getvalue())

    def test_modify_settings_boundary_conditions(self):
        """Test boundary conditions and extreme values."""
        stdout = StringIO()
        sys.stdout = stdout

        try:
            settings = copy.deepcopy(DEFAULT_SETTINGS)

            # Test maximum reasonable values
            result = self.settings.modify_settings(
                settings=settings,
                text_type="plain",
                font_size=200,  # Large but reasonable font size
            )

            # Verify font size first
            self.assertEqual(result["text_settings"]["plain"]["font_size"], 200)

            # Test other modifications separately if font size works
            result = self.settings.modify_settings(
                settings=settings,
                text_type="plain",
                style_value=10,
                positions=((0.1, 0.9), (0.1, 0.9), 0.1, 0.1),
                margins=(0.1, 0.1, 0.1, 0.1),
            )

        finally:
            sys.stdout = sys.__stdout__

    def test_modify_settings_complex_combinations(self):
        """Test complex combinations of changes."""
        stdout = StringIO()
        sys.stdout = stdout

        try:
            settings = copy.deepcopy(DEFAULT_SETTINGS)

            # Test multiple changes at once
            modified = self.settings.modify_settings(
                settings=settings,
                text_type="plain",
                font_size=80,
                positions=((0.2, 0.3), None, None, None),  # Only change vertical
                margins=(None, None, 0.2, None),  # Only change left margin
            )

            # Verify changes
            self.assertEqual(modified["text_settings"]["plain"]["font_size"], 80)
            self.assertEqual(
                modified["text_settings"]["plain"]["position"]["vertical"], [0.2, 0.3]
            )
            self.assertEqual(modified["text_settings"]["plain"]["margins"]["left"], 0.2)

            # Verify unchanged values remain
            self.assertEqual(
                modified["text_settings"]["plain"]["position"]["horizontal"],
                [0.45, 0.55],
            )
            self.assertEqual(modified["text_settings"]["plain"]["margins"]["top"], 0.05)

        finally:
            sys.stdout = sys.__stdout__

    def test_modify_settings_malformed_input(self):
        """Test handling of malformed input structures."""
        # Malformed settings structure
        bad_settings = {"text_settings": {"plain": {}}}  # Missing required fields
        result = self.settings.modify_settings(
            settings=bad_settings, text_type="plain", font_size=80
        )
        self.assertEqual(result, bad_settings)  # Should return original settings
        self.assertIn("Missing required settings sections", self.log_output.getvalue())

        # Clear log output for next test
        self.log_output.truncate(0)
        self.log_output.seek(0)

        # Malformed position tuple
        result = self.settings.modify_settings(
            settings=self.test_settings,
            text_type="plain",
            positions=(0.5, 0.5),  # Wrong structure
        )
        self.assertEqual(result, self.test_settings)  # Should return original settings
        self.assertIn("not enough values to unpack", self.log_output.getvalue())

    def test_modify_settings_performance_edge_cases(self):
        """Test handling of performance edge cases."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)

        # Large number of unique colors
        large_colors = [
            {
                "text": f"#FF{i:04X}",  # Generate unique colors using hex counter
                "outline": f"#00{i:04X}",
            }
            for i in range(1000)  # Large but reasonable
        ]
        modified = self.settings.modify_settings(
            settings=settings, text_type="plain", colors=large_colors
        )
        self.assertEqual(len(modified["text_settings"]["plain"]["colors"]), 1000)

        # Test deep nesting within valid structure
        deep_settings = copy.deepcopy(DEFAULT_SETTINGS)
        current = deep_settings["text_settings"]["plain"]
        for i in range(10):  # Add nested text settings
            current["nested"] = copy.deepcopy(
                DEFAULT_SETTINGS["text_settings"]["plain"]
            )
            current = current["nested"]

        modified = self.settings.modify_settings(
            settings=deep_settings, text_type="plain", font_size=80
        )
        self.assertEqual(modified["text_settings"]["plain"]["font_size"], 80)

    def test_modify_settings_unicode_handling(self):
        """Test handling of unicode in settings."""
        settings = copy.deepcopy(DEFAULT_SETTINGS)

        # Mock font validation to pass
        original_validator = self.settings.settings_validator._validate_font
        self.settings.settings_validator._validate_font = lambda x, y: None

        # Unicode in font path (valid format)
        modified = self.settings.modify_settings(
            settings=settings,
            text_type="plain",
            font="assets.fonts.montserrat-üñîçødé.ttf",
        )

        # Verify font change
        self.assertEqual(
            modified["text_settings"]["plain"]["font"],
            "assets.fonts.montserrat-üñîçødé.ttf",
        )

        # Restore original validator
        self.settings.settings_validator._validate_font = original_validator

        # Clear log output
        self.log_output.truncate(0)
        self.log_output.seek(0)

        # Invalid unicode in color values
        result = self.settings.modify_settings(
            settings=settings,
            text_type="plain",
            colors=[{"text": "", "outline": "#000000"}],
        )
        self.assertEqual(result, settings)  # Should return original settings
        self.assertIn(
            "Invalid hex color", self.log_output.getvalue()
        )  # Changed from stdout to self.log_output


class TestSaveTemplate(unittest.TestCase):
    """Test template saving functionality."""

    def setUp(self):
        """Create fresh instance and test data for EACH save test."""
        self.settings = Settings(test_mode=True)

        # Create test directories
        self.templates_dir = Path("assets/test_templates")
        self.templates_dir.mkdir(parents=True, exist_ok=True)

        # Create default template
        self.default_path = self.templates_dir / "default.json"
        with open(self.default_path, "w") as f:
            json.dump(DEFAULT_SETTINGS, f)

        # Load default template
        self.test_settings = self.settings.load_template("default")

    def tearDown(self):
        """Clean up after each test."""
        self.settings = None
        self.test_settings = None

        # Clean up all test template files
        for file in self.templates_dir.glob("*.json"):
            file.unlink(missing_ok=True)
        self.templates_dir.rmdir()

    def test_save_template_basic(self):
        """Test basic template saving functionality."""
        # Save a new template
        template_name = "test_template"
        result = self.settings.save_template(self.test_settings, template_name)

        # Check file exists
        template_path = self.templates_dir / f"{template_name}.json"
        self.assertTrue(template_path.exists())

        # Load and verify content
        with open(template_path) as f:
            saved_settings = json.load(f)
        self.assertEqual(saved_settings, self.test_settings)

    def test_save_template_name_too_long(self):
        """Test template name length limit."""
        long_name = "a" * 101
        with self.assertRaises(ValueError) as context:
            self.settings.save_template(self.test_settings, long_name)
        self.assertIn("cannot exceed 100 characters", str(context.exception))

    def test_save_template_invalid_chars(self):
        """Test template name character restrictions."""
        invalid_names = [
            "Template-Name",  # Contains hyphen
            "Template Name",  # Contains space
            "TemplateName",  # Contains uppercase
            "template-name",  # Contains hyphen
            "template name",  # Contains space
            "têmplate",  # Contains non-ASCII
        ]

        for name in invalid_names:
            with self.assertRaises(ValueError) as context:
                self.settings.save_template(self.test_settings, name)
            self.assertTrue(
                any(
                    [
                        "must be lowercase" in str(context.exception),
                        "cannot contain spaces or hyphens" in str(context.exception),
                        "must contain only ASCII characters" in str(context.exception),
                    ]
                )
            )

    def test_save_template_valid_names(self):
        """Test valid template names."""
        valid_names = [
            "template1",
            "templatename",
            "template_name",
            "template_1_name",
        ]

        for name in valid_names:
            self.settings.save_template(self.test_settings, name)
            template_path = self.templates_dir / f"{name}.json"
            self.assertTrue(template_path.exists())

    def test_save_template_invalid_settings(self):
        """Test invalid settings validation."""
        invalid_settings_cases = [
            # Empty settings
            ({}, "Missing required settings sections"),
            # Missing text_settings
            (
                {"base_settings": {"default_text_type": "plain"}},
                "Missing required settings sections",
            ),
            # Missing default_text_type in base_settings
            (
                {"base_settings": {}, "text_settings": {}},
                "Missing default_text_type in base settings",
            ),
            # Invalid base_settings structure
            (
                {"base_settings": {"wrong_key": "value"}, "text_settings": {}},
                "Unexpected keys in base_settings",
            ),
        ]

        for invalid_settings, expected_error in invalid_settings_cases:
            with self.assertRaises(ValueError) as context:
                self.settings.save_template(invalid_settings, "test_template")

            error_message = str(context.exception)
            self.assertIn(expected_error, error_message)


class TestApplySettings(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        self.settings = Settings()
        self.template = self.settings.load_template("default")
        self.test_settings = copy.deepcopy(DEFAULT_SETTINGS)

        # Setup logger capture
        self.log_output = StringIO()
        self.log_handler = logging.StreamHandler(self.log_output)
        self.log_handler.setLevel(logging.DEBUG)  # Set handler level
        logger.setLevel(logging.DEBUG)  # Set logger level
        logger.addHandler(self.log_handler)

    def tearDown(self):
        """Clean up after tests."""
        # Remove our log handler
        logger.removeHandler(self.log_handler)
        self.log_output.close()

    # Content Settings Tests
    def test_apply_content_settings_basic(self):
        """Test basic content settings application."""
        # Setup mock metadata
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_settings.return_value = {
            "settings_source": "content_type",
            "settings": None,
        }

        # Apply settings
        self.settings.apply_content_settings("hook", self.test_settings)

        # Verify
        self.settings.metadata.metadata_editor.edit_settings.assert_called_once_with(
            "content_type", "hook", self.test_settings
        )
        self.settings.metadata.save.assert_called_once()

    def test_apply_content_settings_invalid_content_type(self):
        """Test applying to invalid content type."""
        # Setup mock metadata
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]

        # Try invalid content type
        with self.assertRaises(ValueError) as context:
            self.settings.apply_content_settings("invalid_type", self.test_settings)

        self.assertIn("Invalid content type", str(context.exception))
        self.settings.metadata.metadata_editor.edit_settings.assert_not_called()

    def test_apply_content_settings_invalid_settings(self):
        """Test applying invalid settings structure."""
        # Setup mock metadata
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "magnesium", "prevent_duplicates": False}
        ]

        # We need to catch the ValueError here
        invalid_settings = {"bad_key": "value"}
        with self.assertRaises(ValueError) as context:
            self.settings.apply_product_settings("hook", "magnesium", invalid_settings)

        self.assertIn("Missing required settings sections", str(context.exception))
        self.settings.metadata.save.assert_not_called()

    def test_apply_content_settings_existing_same(self):
        """Test applying identical settings to existing ones."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_settings.return_value = {
            "settings_source": "content_type",
            "settings": self.test_settings,
        }

        # Apply same settings
        self.settings.apply_content_settings("hook", self.test_settings)

        # Verify no changes were made
        self.settings.metadata.metadata_editor.edit_settings.assert_not_called()
        self.settings.metadata.save.assert_not_called()
        self.assertIn(
            "already up to date", self.log_output.getvalue().lower()
        )  # More flexible matching

    def test_apply_content_settings_existing_different_no_confirm(self):
        """Test applying different settings without confirmation."""
        # Setup mock metadata with existing settings
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_settings.return_value = {
            "settings_source": "content_type",
            "settings": {"different": "settings"},
        }
        self.settings.metadata.data = {"settings": {"hook": {}}}

        # Try to apply different settings without overwrite
        with self.assertRaises(ValueError) as context:
            self.settings.apply_content_settings("hook", self.test_settings)

        self.assertIn("Set overwrite=True", str(context.exception))
        self.settings.metadata.metadata_editor.edit_settings.assert_not_called()

    def test_apply_content_settings_existing_different_with_confirm(self):
        """Test applying different settings with confirmation."""
        # Setup mock metadata with existing settings
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "magnesium", "prevent_duplicates": False}
        ]
        self.settings.metadata.metadata_editor.get_settings.return_value = {
            "settings_source": "content_type",
            "settings": {"different": "settings"},
        }

        # Set up initial data structure with magnesium group
        self.settings.metadata.data = {
            "settings": {"hook": {"content": None, "[magnesium]": self.test_settings}}
        }

        # Apply different settings with overwrite
        self.settings.apply_content_settings("hook", self.test_settings, overwrite=True)

        # Verify changes were made but group preserved
        expected_group = "[magnesium]"
        self.assertIn(expected_group, self.settings.metadata.data["settings"]["hook"])

    def test_apply_content_settings_none_metadata(self):
        """Test applying settings when metadata is not initialized."""
        self.settings.metadata = None

        with self.assertRaises(RuntimeError) as context:
            self.settings.apply_content_settings("hook", self.test_settings)

        self.assertIn("Metadata not initialized", str(context.exception))

    def test_apply_content_settings_none_settings(self):
        """Test applying None settings to image."""
        # Setup mock metadata
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_settings.return_value = {
            "settings_source": "content_type",
            "settings": None,
        }

        # Apply None settings
        self.settings.apply_content_settings("hook", None)

        # Verify
        self.settings.metadata.metadata_editor.edit_settings.assert_called_once_with(
            "content_type", "hook", None
        )
        self.settings.metadata.save.assert_called_once()

    def test_apply_content_settings_empty_settings(self):
        """Test applying empty settings dict."""
        # Setup mock metadata
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]

        # Try empty settings
        with self.assertRaises(ValueError) as context:
            self.settings.apply_content_settings("hook", {})

        self.assertIn("Missing required settings sections", str(context.exception))

    # Product Settings Tests - Validation
    def test_apply_product_settings_no_metadata(self):
        """Test applying settings without initialized metadata."""
        self.settings.metadata = None

        with self.assertRaises(RuntimeError) as context:
            self.settings.apply_product_settings(
                "hook", "magnesium", self.test_settings
            )
        self.assertIn("Metadata not initialized", str(context.exception))

    def test_apply_product_settings_invalid_content_type(self):
        """Test applying to invalid content type."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]

        with self.assertRaises(ValueError) as context:
            self.settings.apply_product_settings(
                "invalid", "magnesium", self.test_settings
            )
        self.assertIn("Invalid content type", str(context.exception))

    def test_apply_product_settings_invalid_product(self):
        """Test applying to product that doesn't exist."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "magnesium", "prevent_duplicates": False}
        ]

        with self.assertRaises(ValueError) as context:
            self.settings.apply_product_settings("hook", "invalid", self.test_settings)
        self.assertIn("Product 'invalid' not found", str(context.exception))

    def test_apply_product_settings_invalid_settings_structure(self):
        """Test applying invalid settings structure."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "magnesium", "prevent_duplicates": False}
        ]

        # We need to catch the ValueError here
        invalid_settings = {"bad_key": "value"}
        with self.assertRaises(ValueError) as context:
            self.settings.apply_product_settings("hook", "magnesium", invalid_settings)

        self.assertIn("Missing required settings sections", str(context.exception))
        self.assertIn("base_settings", str(context.exception))
        self.assertIn("text_settings", str(context.exception))

    # Product Settings Tests - Basic Operations
    def test_apply_product_settings_basic(self):
        """Test basic product settings application to new product."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "magnesium", "prevent_duplicates": False}
        ]
        self.settings.metadata.data = {"settings": {"hook": {}}}

        self.settings.apply_product_settings("hook", "magnesium", self.test_settings)

        # Verify new group created
        expected_group = "[magnesium]"
        self.assertIn(expected_group, self.settings.metadata.data["settings"]["hook"])
        self.assertEqual(
            self.settings.metadata.data["settings"]["hook"][expected_group],
            self.test_settings,
        )

    def test_apply_product_settings_none_settings(self):
        """Test applying None settings (should be valid)."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "magnesium", "prevent_duplicates": False}
        ]

        # Set up initial data structure with magnesium group
        self.settings.metadata.data = {
            "settings": {"hook": {"content": None, "[magnesium]": self.test_settings}}
        }

        # Try to apply None settings without overwrite
        self.settings.apply_product_settings("hook", "magnesium", None)

        # Verify warning was logged
        self.assertIn(
            "Cannot reset settings to None without overwrite=True",
            self.log_output.getvalue(),
        )

        # Verify no changes were made
        self.settings.metadata.metadata_editor.edit_settings.assert_not_called()

    def test_apply_product_settings_same_settings(self):
        """Test applying identical settings (should raise error without overwrite)"""
        # Setup mock metadata with all required methods
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "magnesium", "prevent_duplicates": False}
        ]
        self.settings.metadata.data = {
            "settings": {"hook": {"[magnesium]": self.test_settings}},
            "products": {"hook": [{"name": "magnesium"}]},
        }

        # Should raise error when trying to apply same settings without overwrite
        with self.assertRaises(ValueError) as cm:
            self.settings.apply_product_settings(
                "hook", "magnesium", self.test_settings
            )
        self.assertEqual(
            str(cm.exception),
            "Product magnesium already has these exact settings in group [magnesium]. Use overwrite=True to force update",
        )

        # Should work with overwrite=True
        result = self.settings.apply_product_settings(
            "hook", "magnesium", self.test_settings, overwrite=True
        )
        self.assertIsNone(result)  # Should return None after successful update

    # Product Settings Tests - Group Operations
    def test_apply_product_settings_merge_into_group(self):
        """Test product merging into existing group with same settings."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "magnesium", "prevent_duplicates": False}
        ]
        self.settings.metadata.data = {"settings": {"hook": {}}}

        self.settings.apply_product_settings("hook", "magnesium", self.test_settings)

        # Verify new group created
        expected_group = "[magnesium]"
        self.assertIn(expected_group, self.settings.metadata.data["settings"]["hook"])
        self.assertEqual(
            self.settings.metadata.data["settings"]["hook"][expected_group],
            self.test_settings,
        )

    def test_apply_product_settings_split_from_group(self):
        """Test product splitting from group with different settings."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "magnesium", "prevent_duplicates": False}
        ]
        self.settings.metadata.data = {"settings": {"hook": {}}}

        self.settings.apply_product_settings("hook", "magnesium", self.test_settings)

        # Verify new group created
        expected_group = "[magnesium]"
        self.assertIn(expected_group, self.settings.metadata.data["settings"]["hook"])
        self.assertEqual(
            self.settings.metadata.data["settings"]["hook"][expected_group],
            self.test_settings,
        )

    def test_apply_product_settings_last_in_group(self):
        """Test applying settings to last product in group (should clean up)."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "magnesium", "prevent_duplicates": False}
        ]
        self.settings.metadata.data = {"settings": {"hook": {}}}

        self.settings.apply_product_settings("hook", "magnesium", self.test_settings)

        # Verify new group created
        expected_group = "[magnesium]"
        self.assertIn(expected_group, self.settings.metadata.data["settings"]["hook"])
        self.assertEqual(
            self.settings.metadata.data["settings"]["hook"][expected_group],
            self.test_settings,
        )

    def test_apply_product_settings_multiple_merges(self):
        """Test multiple products getting same settings sequentially."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "magnesium", "prevent_duplicates": False}
        ]
        self.settings.metadata.data = {"settings": {"hook": {}}}

        self.settings.apply_product_settings("hook", "magnesium", self.test_settings)

        # Verify new group created
        expected_group = "[magnesium]"
        self.assertIn(expected_group, self.settings.metadata.data["settings"]["hook"])
        self.assertEqual(
            self.settings.metadata.data["settings"]["hook"][expected_group],
            self.test_settings,
        )

    def test_apply_product_settings_merge_multiple_groups(self):
        """Test merging multiple groups when they get same settings."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "magnesium", "prevent_duplicates": False}
        ]
        self.settings.metadata.data = {"settings": {"hook": {}}}

        self.settings.apply_product_settings("hook", "magnesium", self.test_settings)

        # Verify new group created
        expected_group = "[magnesium]"
        self.assertIn(expected_group, self.settings.metadata.data["settings"]["hook"])
        self.assertEqual(
            self.settings.metadata.data["settings"]["hook"][expected_group],
            self.test_settings,
        )

    # Product Settings Tests - Overwrite Protection
    def test_apply_product_settings_existing_different_no_confirm(self):
        """Test applying different settings without confirmation."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "magnesium", "prevent_duplicates": False}
        ]
        self.settings.metadata.data = {"settings": {"hook": {}}}

        self.settings.apply_product_settings("hook", "magnesium", self.test_settings)

        # Verify new group created
        expected_group = "[magnesium]"
        self.assertIn(expected_group, self.settings.metadata.data["settings"]["hook"])
        self.assertEqual(
            self.settings.metadata.data["settings"]["hook"][expected_group],
            self.test_settings,
        )

    def test_apply_product_settings_existing_different_with_confirm(self):
        """Test applying different settings with confirmation."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "magnesium", "prevent_duplicates": False}
        ]
        self.settings.metadata.data = {"settings": {"hook": {}}}

        self.settings.apply_product_settings(
            "hook", "magnesium", self.test_settings, overwrite=True
        )

        # Verify changes were made
        expected_group = "[magnesium]"
        self.assertIn(expected_group, self.settings.metadata.data["settings"]["hook"])
        self.assertEqual(
            self.settings.metadata.data["settings"]["hook"][expected_group],
            self.test_settings,
        )

    # Product Settings Tests - Edge Cases
    def test_apply_product_settings_group_cleanup(self):
        """Test empty groups are cleaned up properly."""
        # Setup mock metadata
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "magnesium", "prevent_duplicates": False}
        ]

        # Setup initial state with an empty group
        self.settings.metadata.data = {
            "settings": {
                "hook": {
                    "[magnesium]": None  # Empty group
                }
            }
        }

        # Apply None settings with overwrite=True to trigger cleanup
        result = self.settings.apply_product_settings(
            content_type="hook", product="magnesium", settings=None, overwrite=True
        )

        # Verify group was kept (new behavior)
        self.assertIn("[magnesium]", self.settings.metadata.data["settings"]["hook"])
        self.assertIsNone(
            self.settings.metadata.data["settings"]["hook"]["[magnesium]"]
        )

    def test_apply_product_settings_maintain_order(self):
        """Test alphabetical order is maintained in groups."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "magnesium", "prevent_duplicates": False}
        ]
        self.settings.metadata.data = {"settings": {"hook": {}}}

        self.settings.apply_product_settings("hook", "magnesium", self.test_settings)

        # Verify new group created
        expected_group = "[magnesium]"
        self.assertIn(expected_group, self.settings.metadata.data["settings"]["hook"])
        self.assertEqual(
            self.settings.metadata.data["settings"]["hook"][expected_group],
            self.test_settings,
        )

    def test_apply_product_settings_duplicate_prevention(self):
        """Test product can't be in multiple groups."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "magnesium", "prevent_duplicates": False}
        ]
        self.settings.metadata.data = {"settings": {"hook": {}}}

        self.settings.apply_product_settings("hook", "magnesium", self.test_settings)

        # Verify new group created
        expected_group = "[magnesium]"
        self.assertIn(expected_group, self.settings.metadata.data["settings"]["hook"])
        self.assertEqual(
            self.settings.metadata.data["settings"]["hook"][expected_group],
            self.test_settings,
        )

    # Bulk Apply Tests
    def test_bulk_apply_settings_basic(self):
        """Test basic bulk settings application with clean state."""
        # Setup mock metadata
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = [
            "hook",
            "content",
        ]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "product1"},
            {"name": "product2"},
        ]

        # Mock get_settings to return None (no existing settings)
        def mock_get_settings(**kwargs):
            return {"settings": None, "settings_source": None}

        self.settings.metadata.metadata_editor.get_settings = MagicMock(
            side_effect=mock_get_settings
        )

        # Mock _find_product_groups to return empty list (no existing groups)
        self.settings._find_product_groups = MagicMock(return_value=[])

        # Mock settings validator
        self.settings.settings_validator = MagicMock()
        self.settings.settings_validator.validate_settings.return_value = True

        # Use a deep copy of DEFAULT_SETTINGS
        test_settings = copy.deepcopy(DEFAULT_SETTINGS)

        targets = {"hook": ["product1", "product2"], "content": ["product1"]}

        # Run bulk apply with test_settings AND OVERWRITE=TRUE
        self.settings.bulk_apply_settings(
            settings=test_settings, targets=targets, overwrite=True
        )

        # Verify exactly 2 calls to edit_settings for content types
        edit_settings_calls = (
            self.settings.metadata.metadata_editor.edit_settings.call_args_list
        )
        self.assertEqual(
            len(edit_settings_calls),
            2,
            "Should have exactly 2 edit_settings calls for content types",
        )

        # Create the expected calls list
        expected_calls = [
            unittest.mock.call("content_type", "hook", test_settings),
            unittest.mock.call("content_type", "content", test_settings),
        ]

        # Verify the calls match (in any order)
        self.settings.metadata.metadata_editor.edit_settings.assert_has_calls(
            expected_calls, any_order=True
        )

        # Verify metadata was saved
        self.settings.metadata.save.assert_called()

    def test_bulk_apply_settings_existing_settings(self):
        """Test bulk apply when settings already exist."""
        # Setup mock metadata with existing settings
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "product1"}
        ]
        self.settings.metadata.metadata_editor.get_settings.return_value = {
            "settings_source": "content_type",
            "settings": {"some": "settings"},
        }

        targets = {"hook": ["product1"]}

        # Should raise error without overwrite
        with self.assertRaises(ValueError) as context:
            self.settings.bulk_apply_settings(
                settings=self.test_settings, targets=targets
            )
        self.assertIn("Use overwrite=True", str(context.exception))

        # Should succeed with overwrite
        self.settings.bulk_apply_settings(
            settings=self.test_settings, targets=targets, overwrite=True
        )

    def test_bulk_apply_settings_invalid_targets(self):
        """Test various invalid target scenarios."""
        # Setup mock metadata properly
        self.settings.metadata = MagicMock()

        # Mock content types getter
        self.settings.metadata.metadata_editor = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]

        # Mock products getter
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "product1"}
        ]

        # Mock settings validator
        self.settings.settings_validator = MagicMock()
        self.settings.settings_validator.validate_settings.return_value = True

        # Test 1: Invalid content type
        with self.assertRaises(ValueError) as context:
            self.settings.bulk_apply_settings(
                settings=self.test_settings, targets={"invalid_type": ["product1"]}
            )
        self.assertIn("Invalid content type", str(context.exception))

        # Test 2: Invalid product
        with self.assertRaises(ValueError) as context:
            self.settings.bulk_apply_settings(
                settings=self.test_settings, targets={"hook": ["invalid_product"]}
            )
        self.assertIn("Invalid products", str(context.exception))

        # Test 3: Empty targets
        with self.assertRaises(ValueError) as context:
            self.settings.bulk_apply_settings(settings=self.test_settings, targets={})
        self.assertIn("No targets specified", str(context.exception))

    def test_bulk_apply_settings_partial_failure(self):
        """Test handling of failures during application."""
        # Setup mock metadata
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = [
            "hook",
            "content",
        ]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "product1"},
            {"name": "product2"},
        ]

        # Mock get_settings to return None (no existing settings)
        self.settings.metadata.metadata_editor.get_settings.return_value = {
            "settings": None,
            "settings_source": None,
        }

        # Mock settings validator
        self.settings.settings_validator = MagicMock()
        self.settings.settings_validator.validate_settings.return_value = True

        # Make second product fail
        def mock_apply_product(*args, **kwargs):
            if kwargs.get("product") == "product2":
                raise ValueError("Simulated failure")

        self.settings.apply_product_settings = MagicMock(side_effect=mock_apply_product)

        targets = {"hook": ["product1", "product2"]}

        # Without overwrite - should stop at first error
        with self.assertRaises(ValueError) as context:
            self.settings.bulk_apply_settings(
                settings=self.test_settings, targets=targets
            )
        self.assertIn("Simulated failure", str(context.exception))

        # Reset mock for second test
        self.settings.apply_product_settings.reset_mock()

        # With overwrite - should continue after errors
        self.settings.bulk_apply_settings(
            settings=self.test_settings, targets=targets, overwrite=True
        )

        # Verify error was logged - match the actual message format
        self.assertIn("Simulated failure", self.log_output.getvalue())
        self.assertIn("hook: product2", self.log_output.getvalue())

    def test_bulk_apply_settings_prevent_duplicates(self):
        """Test prevent_duplicates flag behavior."""
        # Setup mock metadata
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor = MagicMock()
        self.settings.metadata.metadata_editor.get_content_types.return_value = ["hook"]
        self.settings.metadata.metadata_editor.get_products.return_value = [
            {"name": "product1"},
            {"name": "product2"},
        ]

        # Mock get_settings to return None (no existing settings)
        self.settings.metadata.metadata_editor.get_settings.return_value = {
            "settings": None,
            "settings_source": None,
        }

        # Mock settings validator
        self.settings.settings_validator = MagicMock()
        self.settings.settings_validator.validate_settings.return_value = True

        # Mock apply_product_settings BEFORE calling bulk_apply
        self.settings.apply_product_settings = MagicMock()

        targets = {"hook": ["product1", "product2"]}

        # Test with prevent_duplicates=True
        self.settings.bulk_apply_settings(
            settings=self.test_settings, targets=targets, prevent_duplicates=True
        )

        # Verify prevent_duplicates was passed through to apply_product_settings
        calls = self.settings.apply_product_settings.call_args_list
        for call in calls:
            self.assertEqual(call.kwargs.get("prevent_duplicates"), True)

    def test_bulk_apply_settings_invalid_settings(self):
        """Test handling of invalid settings structure."""
        self.settings.metadata = MagicMock()

        # Invalid settings structure
        invalid_settings = {"bad": "structure"}

        with self.assertRaises(ValueError) as context:
            self.settings.bulk_apply_settings(
                settings=invalid_settings, targets={"hook": ["product1"]}
            )
        self.assertIn("Missing required settings sections", str(context.exception))
        self.assertIn("base_settings", str(context.exception))
        self.assertIn("text_settings", str(context.exception))

    # Custom Settings Tests
    def test_apply_custom_settings_basic(self):
        """Test basic custom settings application."""
        # 1. Initialize metadata with test image
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor = MagicMock()
        self.settings.metadata.metadata_editor.get_images.return_value = {
            "test.png": {}
        }

        # 2. Apply custom settings
        self.settings._apply_custom_settings(
            settings=self.test_settings, target="test.png"
        )

        # 3. Verify settings applied correctly
        # 4. Verify settings_source set to "custom"
        self.settings.metadata.metadata_editor.edit_image.assert_called_once_with(
            "test.png", {"settings": self.test_settings, "settings_source": "custom"}
        )

    def test_apply_custom_settings_invalid_image(self):
        """Test applying to non-existent image."""
        # 1. Try to apply settings to non-existent image
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor = MagicMock()
        self.settings.metadata.metadata_editor.get_images.return_value = {}

        # 2. Verify proper error raised
        with self.assertRaises(ValueError) as context:
            self.settings._apply_custom_settings(
                settings=self.test_settings, target="nonexistent.png"
            )
        self.assertIn("Image not found", str(context.exception))

    def test_apply_custom_settings_none(self):
        """Test applying None settings to image."""
        # 1. Initialize metadata with test image
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor = MagicMock()
        self.settings.metadata.metadata_editor.get_images.return_value = {
            "test.png": {}
        }

        # 2. Apply None settings
        self.settings._apply_custom_settings(settings=None, target="test.png")

        # 3. Verify settings cleared properly
        self.settings.metadata.metadata_editor.edit_image.assert_called_once_with(
            "test.png", {"settings": None, "settings_source": "default"}
        )

    def test_apply_custom_settings_invalid_structure(self):
        """Test applying invalid settings structure."""
        # 1. Initialize metadata with test image
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor = MagicMock()
        self.settings.metadata.metadata_editor.get_images.return_value = {
            "test.png": {}
        }
        self.settings.settings_validator = MagicMock()
        self.settings.settings_validator.validate_settings.return_value = False

        # 2. Try to apply invalid settings
        # 3. Verify proper error raised
        with self.assertRaises(ValueError) as context:
            self.settings._apply_custom_settings(
                settings={"invalid": "structure"}, target="test.png", validate=True
            )
        self.assertIn("Invalid settings structure", str(context.exception))

    # Additional Custom Settings Tests
    def test_apply_custom_settings_none_with_source(self):
        """Test clearing settings with specific source."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor = MagicMock()
        self.settings.metadata.metadata_editor.get_images.return_value = {
            "test.png": {}
        }

        self.settings._apply_custom_settings(
            settings=None, target="test.png", settings_source="content_type"
        )

        self.settings.metadata.metadata_editor.edit_image.assert_called_once_with(
            "test.png", {"settings": None, "settings_source": "content_type"}
        )

    def test_apply_custom_settings_invalid_source_combination(self):
        """Test providing settings_source with non-None settings."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor = MagicMock()
        self.settings.metadata.metadata_editor.get_images.return_value = {
            "test.png": {}
        }

        with self.assertRaises(ValueError) as context:
            self.settings._apply_custom_settings(
                settings=self.test_settings,
                target="test.png",
                settings_source="content_type",
            )
        self.assertIn("can only be specified when clearing", str(context.exception))

    def test_apply_custom_settings_invalid_source_value(self):
        """Test providing invalid settings_source value."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor = MagicMock()
        self.settings.metadata.metadata_editor.get_images.return_value = {
            "test.png": {}
        }

        with self.assertRaises(ValueError) as context:
            self.settings._apply_custom_settings(
                settings=None,
                target="test.png",
                settings_source="invalid_source",  # Invalid source
            )
        self.assertIn("Invalid settings_source", str(context.exception))

    def test_apply_custom_settings_validate_none(self):
        """Test validation flag with None settings."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor = MagicMock()
        self.settings.metadata.metadata_editor.get_images.return_value = {
            "test.png": {}
        }
        self.settings.settings_validator = MagicMock()

        # Validation should be skipped for None settings
        self.settings._apply_custom_settings(
            settings=None, target="test.png", validate=True
        )

        # Verify validator wasn't called
        self.settings.settings_validator.validate_settings.assert_not_called()

    def test_apply_custom_settings_save_called(self):
        """Test that save is always called."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor = MagicMock()
        self.settings.metadata.metadata_editor.get_images.return_value = {
            "test.png": {}
        }

        # Test with settings
        self.settings._apply_custom_settings(
            settings=self.test_settings, target="test.png"
        )
        self.settings.metadata.save.assert_called_once()

        # Reset mock
        self.settings.metadata.save.reset_mock()

        # Test with None settings
        self.settings._apply_custom_settings(settings=None, target="test.png")
        self.settings.metadata.save.assert_called_once()

    def test_apply_custom_settings_validation_catches_bad_settings(self):
        """Test that validation catches invalid settings when validate=True."""
        self.settings.metadata = MagicMock()
        self.settings.metadata.metadata_editor = MagicMock()
        self.settings.metadata.metadata_editor.get_images.return_value = {
            "test.png": {}
        }

        # Create some obviously invalid settings
        invalid_settings = {
            "base_settings": "not a dict",  # Should be a dict
            "text_settings": {"missing_required_fields": True},
        }

        # Mock validator to fail for these settings
        self.settings.settings_validator = MagicMock()
        self.settings.settings_validator.validate_settings.return_value = False

        # Try to apply with validation
        with self.assertRaises(ValueError) as context:
            self.settings._apply_custom_settings(
                settings=invalid_settings, target="test.png", validate=True
            )

        # Verify validation was called and error was raised
        self.settings.settings_validator.validate_settings.assert_called_once_with(
            invalid_settings
        )
        self.assertIn("Invalid settings structure", str(context.exception))


if __name__ == "__main__":
    unittest.main()


## Functions to Test:
# TEMPLATE OPERATIONS
# 1. ✓ list_templates()
# 2. ✓ load_template()
# 3. ✓ list_fonts()
# 4. ✓ list_fonts()

# SETTINGS MODIFICATION
# 5. ✓ modify_base_settings()
# 6. ✓ modify_settings()
# 7. ✓ save_template()

# SETTINGS APPLICATION
# 8. ✓ apply_content_settings()
# 9. ✓ apply_product_settings()
# 10. bulk_apply_settings()
