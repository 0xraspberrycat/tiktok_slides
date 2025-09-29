"""

1. MetadataTests
   - Basic structure validation
   - Product definitions
   - Image definitions
   - Settings structure
   - File loading/saving

2. MetadataValidatorTests
   - Product validation:
     - Missing products
     - Invalid product names
     - Product count validation
     - Max occurrences validation
   - Settings validation:
     - Default settings
     - Custom settings
     - Content settings
     - Product settings
   - Strict mode tests
   - Warning/Error handling

3. MetadataEditorTests
   - Product assignment
   - Product count tracking
   - Settings modifications
   - Validation state tracking

4. MetadataGeneratorTests
   - Template application
   - Product-based generation
   - Settings inheritance
   - Output validation

Want me to create the first test class structure?
"""

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from content_manager.metadata.metadata import Metadata
from content_manager.metadata.metadata_validator import MetadataValidator
from content_manager.metadata.metadata_editor import MetadataEditor
from content_manager.metadata.metadata_generator import MetadataGenerator
from tests.test_utils import EXAMPLE_METADATA, DEFAULT_SETTINGS


class TestMetadata(unittest.TestCase):
    def setUp(self):
        """Create fresh metadata instance with test data for each test"""
        self.base_path = Path("/fake/path")
        self.metadata = Metadata(base_path=self.base_path)
        self.metadata.data = copy.deepcopy(EXAMPLE_METADATA)
        self.test_settings = copy.deepcopy(DEFAULT_SETTINGS)

        # Initialize metadata editor with data
        self.metadata.metadata_editor = MetadataEditor(self.metadata.data)

    def test_get_content_types(self):
        """Test getting content types"""
        expected = ["content", "cta", "hook"]
        self.assertEqual(self.metadata.metadata_editor.get_content_types(), expected)

    def test_get_products(self):
        """Test getting products for content type"""
        hook_products = self.metadata.metadata_editor.get_products("hook")
        self.assertEqual(len(hook_products), 4)
        self.assertEqual(hook_products[0]["name"], "all")
        self.assertEqual(hook_products[1]["name"], "magnesium")

    def test_get_images(self):
        """Test getting images for content type"""
        hook_images = self.metadata.metadata_editor.get_images("hook")
        expected = ["1h.PNG", "2h.PNG", "3h.png", "4h.png"]
        self.assertEqual(sorted(hook_images), sorted(expected))

    def test_get_settings(self):
        """Test getting settings for content type"""
        # Get settings for hook content type
        hook_settings = self.metadata.metadata_editor.get_settings(
            "content_type", "hook"
        )

        # Check that settings exist and have expected structure
        self.assertIsNotNone(hook_settings)
        self.assertEqual(hook_settings["settings_source"], "content_type")
        self.assertIsNotNone(hook_settings["settings"])

        # Verify specific settings values
        settings = hook_settings["settings"]
        self.assertEqual(settings["base_settings"]["default_text_type"], "plain")
        self.assertEqual(settings["text_settings"]["plain"]["font_size"], 70)

    def test_get_settings_default(self):
        """Test getting default settings"""
        default_settings = self.metadata.metadata_editor.get_settings("default")
        self.assertIsNotNone(default_settings)
        self.assertEqual(default_settings["settings_source"], "default")
        self.assertIsNotNone(default_settings["settings"])

    def test_get_settings_product(self):
        """Test getting product-specific settings"""
        # Test magnesium product settings in hook content type
        settings = self.metadata.metadata_editor.get_settings(
            "product", "magnesium", "hook"
        )
        self.assertIsNotNone(settings)
        self.assertEqual(settings["settings_source"], "product")

        # First verify settings exist
        self.assertIsNotNone(settings["settings"])

        # The settings for magnesium are in hook -> [magnesium] in the example JSON
        # Let's verify the key parts of the settings that we know exist
        settings_data = settings["settings"]
        self.assertIn("base_settings", settings_data)
        self.assertIn("text_settings", settings_data)
        self.assertEqual(settings_data["base_settings"]["default_text_type"], "plain")

        # Verify the specific magnesium settings we can see in the example
        text_settings = settings_data["text_settings"]["plain"]
        self.assertEqual(text_settings["position"]["vertical"], [0.8, 0.9])
        self.assertEqual(text_settings["position"]["horizontal"], [0.45, 0.55])

    def test_get_settings_custom(self):
        """Test getting custom image settings"""
        # 2cta.PNG has custom settings in the example data
        settings = self.metadata.metadata_editor.get_settings("custom", "2cta.PNG")
        self.assertIsNotNone(settings)
        self.assertEqual(settings["settings_source"], "custom")
        self.assertIsNotNone(settings["settings"])

    def test_get_settings_invalid_content_type(self):
        """Test getting settings for invalid content type"""
        with self.assertRaises(ValueError):
            self.metadata.metadata_editor.get_settings("content_type", "invalid_type")

    def test_get_settings_invalid_product(self):
        """Test getting settings for invalid product"""
        settings = self.metadata.metadata_editor.get_settings(
            "product", "invalid_product", "hook"
        )
        self.assertIsNotNone(settings)
        self.assertIsNone(settings["settings"])

    def test_get_settings_missing_content_type(self):
        """Test error when content_type missing for product settings"""
        with self.assertRaises(ValueError):
            self.metadata.metadata_editor.get_settings("product", "magnesium")

    def test_metadata_structure(self):
        """Test basic metadata structure"""
        required_keys = ["content_types", "products", "images", "settings", "structure"]
        for key in required_keys:
            self.assertIn(key, self.metadata.data)

    def test_content_type_structure(self):
        """Test content type structure"""
        for content_type in self.metadata.data["content_types"]:
            # Check structure exists
            self.assertIn(content_type, self.metadata.data["structure"])
            # Check path exists
            self.assertIn("path", self.metadata.data["structure"][content_type])
            # Check images list exists
            self.assertIn("images", self.metadata.data["structure"][content_type])

    def test_product_structure(self):
        """Test product structure"""
        for content_type, products in self.metadata.data["products"].items():
            for product in products:
                required_fields = [
                    "name", 
                    "prevent_duplicates", 
                    "min_occurrences",
                    "current_count"  # Add new required field
                ]
                for field in required_fields:
                    self.assertIn(field, product)
                
                # Also validate the type and initial value
                self.assertIsInstance(product["current_count"], int)
                self.assertEqual(product["current_count"], 0)


class TestMetadataEditor(unittest.TestCase):
    def setUp(self):
        """Create fresh editor instance with test data"""
        self.test_data = copy.deepcopy(EXAMPLE_METADATA)
        self.editor = MetadataEditor(self.test_data)

    def mock_exists_fn(self, path):
        """Helper method for mocking Path.exists()"""
        return str(path).endswith("test.png")

    def test_edit_image_basic(self):
        """Test basic image metadata editing"""
        image_name = "1h.PNG"
        new_data = {
            "product": "magnesium",
            "settings_source": "custom",
            "settings": {"test": "value"},
        }

        self.editor.edit_image(image_name, new_data)

        # Verify changes
        image_data = self.test_data["images"][image_name]
        self.assertEqual(image_data["product"], "magnesium")
        self.assertEqual(image_data["settings_source"], "custom")
        self.assertEqual(image_data["settings"], {"test": "value"})

    def test_edit_image_invalid(self):
        """Test editing nonexistent image"""
        with self.assertRaises(ValueError):
            self.editor.edit_image("nonexistent.png", {"product": "test"})

    def test_edit_image_product_counts(self):
        """Test product count updates when editing image"""
        image_name = "1h.PNG"

        # First assignment
        self.editor.edit_image(image_name, {"product": "magnesium"})

        # Change to different product
        self.editor.edit_image(image_name, {"product": "supplement"})

        # Check counts updated correctly
        hook_products = self.test_data["products"]["hook"]
        for product in hook_products:
            if product["name"] == "magnesium":
                self.assertEqual(product.get("current_count", 0), 0)
            elif product["name"] == "supplement":
                self.assertEqual(product.get("current_count", 0), 1)

    def test_edit_image_untagged_status(self):
        """Test untagged list updates when editing image"""
        image_name = "1h.PNG"

        # Remove product (should add to untagged)
        self.editor.edit_image(image_name, {"product": None})
        self.assertIn(image_name, self.test_data["untagged"])

        # Assign product (should remove from untagged)
        self.editor.edit_image(image_name, {"product": "magnesium"})
        self.assertNotIn(image_name, self.test_data["untagged"])

    def test_edit_settings_content_type(self):
        """Test editing content type settings"""
        test_settings = {
            "base_settings": {"default_text_type": "plain"},
            "text_settings": {"plain": {"font_size": 80}},
        }

        self.editor.edit_settings("content_type", "hook", test_settings)

        # Verify settings updated
        self.assertEqual(self.test_data["settings"]["hook"]["content"], test_settings)

    def test_edit_settings_custom(self):
        """Test editing custom image settings"""
        image_name = "1h.PNG"
        test_settings = {
            "base_settings": {"default_text_type": "plain"},
            "text_settings": {"plain": {"font_size": 80}},
        }

        self.editor.edit_settings("custom", image_name, test_settings)

        # Verify settings updated
        self.assertEqual(
            self.test_data["images"][image_name]["settings"], test_settings
        )
        self.assertEqual(
            self.test_data["images"][image_name]["settings_source"], "custom"
        )

    @patch("content_manager.metadata.metadata_editor.Path")
    def test_move_untagged_image(self, MockPath):
        """Test moving image between content types"""
        image_name = "test.png"
        base_path = "/fake/base/path"
        hook_path = f"{base_path}/hook"

        # Setup metadata
        self.test_data["untagged"] = [image_name]
        self.test_data["structure"] = {"hook": {"path": hook_path, "images": []}}

        # Setup path mocks
        target_path_mock = MagicMock()
        target_path_mock.parent = MagicMock()  # This is base_path

        src_path_mock = MagicMock()
        src_path_mock.exists.return_value = True

        dest_path_mock = MagicMock()
        dest_path_mock.exists.return_value = False

        # Configure path creation
        MockPath.return_value = target_path_mock
        target_path_mock.parent.__truediv__.return_value = (
            src_path_mock  # base_path / image_name
        )
        target_path_mock.__truediv__.return_value = (
            dest_path_mock  # target_path / image_name
        )

        # Mock PIL.Image.open
        with patch("PIL.Image.open") as mock_open:
            mock_open.return_value.__enter__.return_value.size = (1080, 1920)

            # Move image
            self.editor.move_untagged_image(image_name, "hook")

        # Verify metadata updated
        self.assertNotIn(image_name, self.test_data["untagged"])
        self.assertIn(image_name, self.test_data["structure"]["hook"]["images"])
        self.assertIn(image_name, self.test_data["images"])

        # Verify file operations
        src_path_mock.rename.assert_called_once_with(dest_path_mock)

    def test_get_untagged(self):
        """Test getting untagged images list"""
        untagged = self.editor.get_untagged()
        self.assertEqual(untagged, self.test_data["untagged"])

    def test_edit_untagged(self):
        """Test editing untagged images list"""
        new_untagged = ["test1.png", "test2.png"]
        self.editor.edit_untagged(new_untagged)
        self.assertEqual(self.test_data["untagged"], new_untagged)

    def test_update_product_count(self):
        """Test product count updates"""
        self.editor._update_product_count("hook", "magnesium", increment=True)
        product = next(
            p for p in self.test_data["products"]["hook"] if p["name"] == "magnesium"
        )
        self.assertEqual(product.get("current_count", 0), 1)


class TestMetadataGenerator(unittest.TestCase):
    def setUp(self):
        """Setup test data and paths"""
        self.content_types = ["hook", "content", "cta"]
        self.products = {
            "hook": ["magnesium", "all", "supplement"],
            "content": ["magnesium", "vitamin_c", "all"],
            "cta": ["shop_now", "learn_more", "all"],
        }

        # Mock CaptionsHelper
        self.captions_patcher = patch(
            "content_manager.metadata.metadata_generator.CaptionsHelper"
        )
        self.mock_captions = self.captions_patcher.start()
        self.mock_captions.get_product_min_occurrences.return_value = {
            "hook": [{"name": "magnesium", "min_occurrences": 1}],
            "content": [{"name": "vitamin_c", "min_occurrences": 2}],
            "cta": [{"name": "shop_now", "min_occurrences": 1}],
        }

    def tearDown(self):
        self.captions_patcher.stop()

    def test_generate_basic_structure(self):
        """Test basic metadata structure generation"""
        with patch("pathlib.Path") as MockPath:
            # Setup mock path
            mock_base = MagicMock()
            mock_base.iterdir.return_value = []  # No untagged images
            mock_base.exists.return_value = True

            def mock_path_init(path):
                if str(path).endswith("base/path"):
                    return mock_base
                mock_content = MagicMock()
                mock_content.glob.return_value = [
                    MagicMock(name="test1.png", spec=Path),
                    MagicMock(name="test2.PNG", spec=Path),
                ]
                mock_content.exists.return_value = True
                return mock_content

            MockPath.side_effect = mock_path_init

            # Create generator AFTER mocking Path
            generator = MetadataGenerator(
                MockPath("/base/path"), self.content_types, self.products
            )
            metadata = generator.generate()

            # Verify structure
            self.assertIn("content_types", metadata)
            self.assertIn("products", metadata)
            self.assertIn("structure", metadata)
            self.assertIn("images", metadata)
            self.assertIn("untagged", metadata)
            self.assertIn("settings", metadata)

    def test_generate_settings_structure(self):
        """Test settings hierarchy generation"""
        with patch("pathlib.Path") as MockPath:
            # Setup mock paths
            mock_base = MagicMock()
            mock_base.iterdir.return_value = []
            mock_base.exists.return_value = True

            def mock_path_init(path):
                if str(path).endswith("base/path"):
                    return mock_base
                mock_content = MagicMock()
                mock_content.glob.return_value = []
                mock_content.exists.return_value = True
                return mock_content

            MockPath.side_effect = mock_path_init

            # Create generator AFTER mocking
            generator = MetadataGenerator(
                MockPath("/base/path"), self.content_types, self.products
            )
            metadata = generator.generate()

            # Verify settings
            self.assertIn("settings", metadata)
            self.assertIn("hook", metadata["settings"])
            hook_settings = metadata["settings"]["hook"]
            self.assertIn("content", hook_settings)

    def test_generate_content_types(self):
        """Test ONLY content types generation"""
        generator = MetadataGenerator(Path("/fake"), ["hook", "content"], {})
        generator._generate_content_types()

        self.assertEqual(generator.metadata["content_types"], ["hook", "content"])

    def test_generate_products(self):
        """Test ONLY products generation"""
        with patch(
            "content_manager.metadata.metadata_generator.CaptionsHelper"
        ) as mock_captions:
            mock_captions.get_product_min_occurrences.return_value = {}

            products = {"hook": ["product1", "product2"]}
            generator = MetadataGenerator(Path("/fake"), ["hook"], products)
            generator._generate_products()

            self.assertIn("hook", generator.metadata["products"])
            hook_products = generator.metadata["products"]["hook"]
            self.assertEqual(len(hook_products), 2)
            self.assertEqual(hook_products[0]["name"], "product1")

    def test_generate_structure(self):
        """Test ONLY structure generation"""
        with patch("pathlib.Path") as MockPath:
            # Mock a directory with one image
            mock_image = MagicMock(spec=Path)
            mock_image.name = "test.png"

            # Mock the hook directory
            mock_hook_dir = MagicMock(spec=Path)
            mock_hook_dir.glob.return_value = [mock_image]
            mock_hook_dir.exists.return_value = True

            # Mock base directory
            mock_base = MagicMock(spec=Path)
            mock_base.exists.return_value = True
            mock_base.__truediv__.return_value = mock_hook_dir

            # Handle Path creation
            def mock_path_init(*args):
                if isinstance(args[0], str) and args[0] == "/fake":
                    return mock_base
                return mock_hook_dir

            MockPath.side_effect = mock_path_init

            # Create generator with mocked Path
            generator = MetadataGenerator(MockPath("/fake"), ["hook"], {})
            generator._generate_structure()

            # Verify structure was created correctly
            self.assertIn("hook", generator.metadata["structure"])
            self.assertIn("test.png", generator.metadata["structure"]["hook"]["images"])

    def test_generate_images(self):
        """Test ONLY image metadata generation"""
        generator = MetadataGenerator("/fake/path", ["hook"], {})
        generator._get_image_dimensions = MagicMock(
            return_value={"width": 1920, "height": 1080}
        )

        # Test 1: Without exists() patch - should fail
        with self.assertRaises(Exception):
            generator._generate_images()

        # Test 2: With exists() patch but returning False
        with patch("pathlib.Path.exists", return_value=False):
            generator.metadata = {
                "images": {},
                "structure": {
                    "hook": {"path": "/fake/path/hook", "images": ["test.png"]}
                },
            }
            generator._generate_images()
            self.assertEqual(generator.metadata["images"], {})

        # Test 3: Normal case (should work)
        with patch("pathlib.Path.exists", return_value=True):
            generator.metadata = {
                "images": {},
                "structure": {
                    "hook": {"path": "/fake/path/hook", "images": ["test.png"]}
                },
            }
            generator._generate_images()
            self.assertIn("test.png", generator.metadata["images"])
            self.assertEqual(
                generator.metadata["images"]["test.png"]["dimensions"],
                {"width": 1920, "height": 1080},
            )

    def test_generate_untagged(self):
        """Test untagged images detection"""
        with patch("pathlib.Path") as MockPath:
            # Create mock base_path
            mock_base_path = MagicMock()
            mock_base_path.iterdir.return_value = []
            MockPath.return_value = mock_base_path

            generator = MetadataGenerator("/fake/path", ["hook"], {})
            generator.base_path = mock_base_path

            # Create mock files
            def create_mock_file(filename, suffix):
                mock = MagicMock()
                mock.name = filename
                mock.is_file.return_value = True
                mock.suffix = suffix
                return mock

            mock_files = [
                create_mock_file("test1.png", ".png"),
                create_mock_file("test2.jpg", ".jpg"),
                create_mock_file("test3.txt", ".txt"),
                create_mock_file(".hidden.png", ".png"),
            ]

            mock_base_path.iterdir.return_value = mock_files

            generator.metadata = {"structure": {"hook": {"images": ["test1.png"]}}}

            generator._generate_untagged()

            # Verify results
            self.assertIn("untagged", generator.metadata)
            self.assertIn("test2.jpg", generator.metadata["untagged"])
            self.assertNotIn("test1.png", generator.metadata["untagged"])
            self.assertNotIn("test3.txt", generator.metadata["untagged"])
            self.assertNotIn(".hidden.png", generator.metadata["untagged"])

    def test_generate_settings(self):
        """Test settings hierarchy generation"""
        # Create generator
        generator = MetadataGenerator("/fake/path", ["hook", "content"], {})

        # Setup initial metadata
        generator.metadata = {
            "products": {
                "hook": [{"name": "product1"}, {"name": "product2"}],
                "content": [{"name": "product3"}],
            }
        }

        # Generate settings
        generator._generate_settings()

        # Verify
        self.assertIn("settings", generator.metadata)

        # Check hook content type
        self.assertIn("hook", generator.metadata["settings"])
        hook_settings = generator.metadata["settings"]["hook"]
        self.assertIsNone(hook_settings["content"])
        self.assertIn("[product1, product2]", hook_settings)
        self.assertIsNone(hook_settings["[product1, product2]"])

        # Check content content type
        self.assertIn("content", generator.metadata["settings"])
        content_settings = generator.metadata["settings"]["content"]
        self.assertIsNone(content_settings["content"])
        self.assertIn("[product3]", content_settings)
        self.assertIsNone(content_settings["[product3]"])

    def test_get_image_dimensions(self):
        """Test getting image dimensions"""
        generator = MetadataGenerator("/fake/path", ["hook"], {})
        mock_image = MagicMock()
        mock_image.size = (1920, 1080)

        with patch("PIL.Image.open") as mock_open:
            mock_open.return_value.__enter__.return_value = mock_image
            mock_path = MagicMock()
            dimensions = generator._get_image_dimensions(mock_path)

            self.assertEqual(dimensions, {"width": 1920, "height": 1080})
            mock_open.assert_called_once_with(mock_path)

    def test_generate_image_metadata(self):
        """Test generating metadata for a single image"""
        generator = MetadataGenerator("/fake/path", ["hook"], {})
        generator._get_image_dimensions = MagicMock(
            return_value={"width": 1920, "height": 1080}
        )

        mock_path = MagicMock()
        metadata = generator._generate_image_metadata(mock_path, "hook")

        expected_metadata = {
            "content_type": "hook",
            "dimensions": {"width": 1920, "height": 1080},
            "product": None,
            "settings_source": "default",
            "settings": None,
        }

        self.assertEqual(metadata, expected_metadata)
        generator._get_image_dimensions.assert_called_once_with(mock_path)


class TestMetadataValidator(unittest.TestCase):
    def setUp(self):
        """Create fresh validator instance"""
        self.base_path = Path("/fake/path")
        self.validator = MetadataValidator(base_path=self.base_path)

        # Mock CaptionsHelper
        self.captions_patcher = patch(
            "content_manager.metadata.metadata_validator.CaptionsHelper"
        )
        self.mock_captions = self.captions_patcher.start()
        self.mock_captions.get_product_min_occurrences.return_value = {"product1": 1}

        # Mock Path.exists
        self.path_exists_patcher = patch("pathlib.Path.exists")
        self.mock_exists = self.path_exists_patcher.start()
        self.mock_exists.return_value = True

        # Mock PIL Image
        self.pil_patcher = patch("PIL.Image.open")
        self.mock_pil = self.pil_patcher.start()
        mock_image = MagicMock()
        mock_image.size = (1920, 1080)
        self.mock_pil.return_value.__enter__.return_value = mock_image

    def tearDown(self):
        self.captions_patcher.stop()
        self.path_exists_patcher.stop()
        self.pil_patcher.stop()

    def test_validate_key_order(self):
        """Test that metadata keys must be in correct order"""
        # Create data with wrong order
        data = {
            "products": {},
            "content_types": [],
            "structure": {},
            "images": {},
            "untagged": [],
            "settings": {},
        }

        result = self.validator.validate(data, [], {})
        self.assertFalse(result)
        self.assertIn(
            "Metadata keys are not in correct order", self.validator.errors[0]
        )

    def test_validate_content_types(self):
        """Test content_types validation"""
        data = copy.deepcopy(EXAMPLE_METADATA)

        # Test invalid type
        data["content_types"] = "not a list"
        result = self.validator._validate_content_types(data, ["hook"])
        self.assertFalse(result)
        self.assertIn("content_types must be a list", self.validator.errors)

        # Clear errors for next test
        self.validator.errors = []

        # Test mismatch
        data["content_types"] = ["hook", "extra"]
        result = self.validator._validate_content_types(data, ["hook"])
        self.assertFalse(result)
        self.assertIn("Content types mismatch", self.validator.errors[0])

        # Clear errors for next test
        self.validator.errors = []

        # Test correct
        data["content_types"] = ["hook"]
        result = self.validator._validate_content_types(data, ["hook"])
        self.assertTrue(result)

    def test_validate_strict_mode(self):
        """Test strict mode behavior with warnings"""
        data = {
            "content_types": ["hook"],
            "products": {
                "hook": [
                    {
                        "name": "product1",
                        "prevent_duplicates": True,
                        "min_occurrences": 0,
                    }
                ]
            },
            "structure": {"hook": {"path": "/fake/path/hook", "images": ["test1.png"]}},
            "images": {
                "test1.png": {
                    "content_type": "hook",
                    "dimensions": {"width": 1920, "height": 1080},
                    "product": None,
                    "settings_source": "default",
                    "settings": None,
                }
            },
            "untagged": [],
            "settings": {"hook": {"content": None, "[product1]": None}},
        }

        # Test strict mode (default)
        result = self.validator.validate(data, ["hook"], {"hook": ["product1"]})
        self.assertFalse(result)
        self.assertIn(
            "Image test1.png has no associated product", self.validator.errors
        )

        # Test non-strict mode
        self.validator.strict = False
        self.validator.errors = []  # Clear previous errors
        result = self.validator.validate(data, ["hook"], {"hook": ["product1"]})
        self.assertTrue(result)
        self.assertIn(
            "Image test1.png has no associated product", self.validator.warnings
        )

    def test_duplicate_warnings(self):
        """Test that duplicate warnings are not added"""
        data = {
            "content_types": ["hook"],
            "products": {
                "hook": [
                    {
                        "name": "product1",
                        "prevent_duplicates": True,
                        "min_occurrences": 0,
                    }
                ]
            },
            "structure": {
                "hook": {
                    "path": "/fake/path/hook",
                    "images": ["test1.png", "test2.png"],
                }
            },
            "images": {
                "test1.png": {
                    "content_type": "hook",
                    "dimensions": {"width": 1920, "height": 1080},
                    "product": None,
                    "settings_source": "default",
                    "settings": None,
                },
                "test2.png": {
                    "content_type": "hook",
                    "dimensions": {"width": 1920, "height": 1080},
                    "product": None,
                    "settings_source": "default",
                    "settings": None,
                },
            },
            "untagged": [],
            "settings": {"hook": {"content": None, "[product1]": None}},
        }

        self.validator.strict = False
        self.validator.seen_warnings = set()  # Clear any existing warnings
        result = self.validator.validate(data, ["hook"], {"hook": ["product1"]})
        self.assertTrue(result)

        # Verify we get one warning per image (this is the correct behavior)
        expected_warnings = {
            f"Image test1.png has no product assigned. Valid products: ['all', {['product1']}]",
            f"Image test2.png has no product assigned. Valid products: ['all', {['product1']}]"
        }
        actual_warnings = set(self.validator.warnings)

        self.assertEqual(actual_warnings, expected_warnings)
        self.assertEqual(len(self.validator.warnings), 2)  # Should have both warnings

        # Store first set of warnings
        first_warnings = set(self.validator.warnings)

        # Verify that running validation again doesn't add duplicate warnings
        result = self.validator.validate(data, ["hook"], {"hook": ["product1"]})
        self.assertTrue(result)

        # Verify warnings are identical after second validation
        self.assertEqual(set(self.validator.warnings), first_warnings)
        self.assertEqual(
            len(self.validator.warnings), 2
        )  # Should still have just the two warnings

    def test_warning_deduplication_per_image(self):
        """Test that warnings are tracked per image"""
        data = {
            "content_types": ["hook"],
            "products": {
                "hook": [
                    {
                        "name": "product1",
                        "prevent_duplicates": True,
                        "min_occurrences": 0,
                    }
                ]
            },
            "structure": {"hook": {"path": "/fake/path/hook", "images": ["test1.png"]}},
            "images": {
                "test1.png": {
                    "content_type": "hook",
                    "dimensions": {"width": 1920, "height": 1080},
                    "product": None,
                    "settings_source": "default",
                    "settings": None,
                }
            },
            "untagged": [],
            "settings": {"hook": {"content": None, "[product1]": None}},
        }

        self.validator.strict = False
        self.validator.seen_warnings = set()  # Clear any existing warnings

        # First validation
        result = self.validator.validate(data, ["hook"], {"hook": ["product1"]})
        self.assertTrue(result)
        first_warnings = self.validator.warnings.copy()

        # Second validation of same data
        result = self.validator.validate(data, ["hook"], {"hook": ["product1"]})
        self.assertTrue(result)

        # Warnings should be identical and contain one detailed warning
        self.assertEqual(first_warnings, self.validator.warnings)
        self.assertEqual(len(self.validator.warnings), 1)  # One warning for one image
        self.assertEqual(
            self.validator.warnings[0],
            f"Image test1.png has no product assigned. Valid products: ['all', {['product1']}]"
        )

    def test_validation_error_clearing(self):
        """Test that errors and warnings are cleared between validations"""
        # First validation with error
        data_with_error = {
            "content_types": ["wrong"],
            "products": {},
            "structure": {"wrong": {"path": "/fake/path/wrong", "images": []}},
            "images": {},
            "untagged": [],
            "settings": {},
        }

        result = self.validator.validate(
            data_with_error, ["hook"], {"hook": ["product1"]}
        )
        self.assertFalse(result)
        self.assertTrue(len(self.validator.errors) > 0)
        first_errors = self.validator.errors.copy()

        # Second validation with correct data
        correct_data = {
            "content_types": ["hook"],
            "products": {
                "hook": [
                    {
                        "name": "product1",
                        "prevent_duplicates": True,
                        "min_occurrences": 0,
                    }
                ]
            },
            "structure": {"hook": {"path": "/fake/path/hook", "images": []}},
            "images": {},
            "untagged": [],
            "settings": {"hook": {"content": None, "[product1]": None}},
        }

        result = self.validator.validate(correct_data, ["hook"], {"hook": ["product1"]})
        self.assertTrue(result)
        self.assertEqual(len(self.validator.errors), 0)

        # Verify first errors are different
        for error in first_errors:
            self.assertNotIn(error, self.validator.errors)

    def test_validate_products_structure(self):
        """Test product section structure validation"""
        data = {
            "content_types": ["hook"],
            "products": {
                "hook": [
                    {
                        "name": "product1",
                        "prevent_duplicates": True,
                        "min_occurrences": 1,
                        "current_count": 0  # Add new field
                    }
                ]
            },
            "structure": {"hook": {"path": "/fake/path/hook", "images": []}},
            "images": {},
            "untagged": [],
            "settings": {"hook": {"content": None}},
        }

        # Test invalid products type
        invalid_data = copy.deepcopy(data)
        invalid_data["products"] = []
        result = self.validator._validate_products(invalid_data, {"hook": ["product1"]})
        self.assertFalse(result)
        self.assertIn("products must be a dictionary", self.validator.errors)

        # Test missing required product fields
        invalid_data = copy.deepcopy(data)
        invalid_data["products"]["hook"][0] = {"name": "product1"}  # Missing fields
        result = self.validator._validate_products(invalid_data, {"hook": ["product1"]})
        self.assertFalse(result)
        self.assertIn("prevent_duplicates", str(self.validator.errors))

    def test_validate_structure_paths(self):
        """Test structure path validation"""
        data = {
            "content_types": ["hook"],
            "products": {"hook": []},
            "structure": {"hook": {"path": "/fake/path/hook", "images": ["test1.png"]}},
            "images": {},
            "untagged": [],
            "settings": {},
        }

        # Test missing path
        invalid_data = copy.deepcopy(data)
        del invalid_data["structure"]["hook"]["path"]
        result = self.validator._validate_structure(invalid_data)
        self.assertFalse(result)
        self.assertIn("missing required fields", str(self.validator.errors))

        # Test non-existent path (mock returns False)
        self.mock_exists.return_value = False
        result = self.validator._validate_structure(data)
        self.assertFalse(result)
        self.assertIn("does not exist", str(self.validator.errors))

    def test_validate_image_dimensions(self):
        """Test image dimension validation"""
        data = {
            "content_types": ["hook"],
            "products": {"hook": []},
            "structure": {"hook": {"path": "/fake/path/hook", "images": ["test1.png"]}},
            "images": {
                "test1.png": {
                    "content_type": "hook",
                    "dimensions": {"width": 1920, "height": 1080},
                    "product": None,
                    "settings_source": "default",
                    "settings": None,
                }
            },
            "untagged": [],
            "settings": {},
        }

        # Test missing dimensions field entirely
        invalid_data = copy.deepcopy(data)
        del invalid_data["images"]["test1.png"]["dimensions"]
        result = self.validator._validate_images(invalid_data)
        self.assertFalse(result)
        self.assertIn(
            "Image test1.png missing required field: dimensions", self.validator.errors
        )

        # Clear errors before next test
        self.validator.errors.clear()

        # Test dimensions as empty dict
        invalid_data = copy.deepcopy(data)
        invalid_data["images"]["test1.png"]["dimensions"] = {}
        result = self.validator._validate_images(invalid_data)
        self.assertFalse(result)
        self.assertIn("Image test1.png has no dimensions", self.validator.errors)

        # Clear errors before next test
        self.validator.errors.clear()

        # Test dimension mismatch with actual image
        mock_image = MagicMock()
        mock_image.size = (1000, 500)  # Different from metadata
        self.mock_pil.return_value.__enter__.return_value = mock_image

        result = self.validator._validate_images(data)
        self.assertFalse(result)
        self.assertIn("dimensions mismatch", str(self.validator.errors))

    def test_validate_image_content_type(self):
        """Test image content type validation"""
        data = {
            "content_types": ["hook"],
            "products": {"hook": []},
            "structure": {"hook": {"path": "/fake/path/hook", "images": ["test1.png"]}},
            "images": {
                "test1.png": {
                    "content_type": "hook",
                    "dimensions": {"width": 1920, "height": 1080},
                    "product": None,
                    "settings_source": "default",
                    "settings": None,
                }
            },
            "untagged": [],
            "settings": {},
        }

        # Test invalid content type
        invalid_data = copy.deepcopy(data)
        invalid_data["images"]["test1.png"]["content_type"] = "invalid"
        result = self.validator._validate_images(invalid_data)
        self.assertFalse(result)
        self.assertIn("has invalid content_type: invalid", str(self.validator.errors))

        # Test image not in content type folder
        invalid_data = copy.deepcopy(data)
        invalid_data["structure"]["hook"]["images"] = []  # Remove image from structure
        result = self.validator._validate_images(invalid_data)
        self.assertFalse(result)
        self.assertIn(
            "claims to be in hook folder but isn't found there",
            str(self.validator.errors),
        )

    def test_validate_image_sorting(self):
        """Test image alphabetical sorting requirement"""
        data = {
            "content_types": ["hook"],
            "products": {"hook": []},
            "structure": {
                "hook": {
                    "path": "/fake/path/hook",
                    "images": ["b.png", "a.png"],  # Out of order
                }
            },
            "images": {
                "b.png": {  # Out of order
                    "content_type": "hook",
                    "dimensions": {"width": 1920, "height": 1080},
                    "product": None,
                    "settings_source": "default",
                    "settings": None,
                },
                "a.png": {
                    "content_type": "hook",
                    "dimensions": {"width": 1920, "height": 1080},
                    "product": None,
                    "settings_source": "default",
                    "settings": None,
                },
            },
            "untagged": [],
            "settings": {},
        }

        result = self.validator._validate_images(data)
        self.assertFalse(result)
        self.assertIn("Images must be sorted alphabetically", self.validator.errors)

    def test_validate_image_required_fields(self):
        """Test image required fields validation"""
        data = {
            "content_types": ["hook"],
            "products": {"hook": []},
            "structure": {"hook": {"path": "/fake/path/hook", "images": ["test1.png"]}},
            "images": {
                "test1.png": {
                    "content_type": "hook",
                    "dimensions": {"width": 1920, "height": 1080},
                    "product": None,
                    "settings_source": "default",
                    "settings": None,
                }
            },
            "untagged": [],
            "settings": {},
        }

        required_fields = [
            "content_type",
            "dimensions",
            "product",
            "settings_source",
            "settings",
        ]

        # Test each required field
        for field in required_fields:
            invalid_data = copy.deepcopy(data)
            del invalid_data["images"]["test1.png"][field]
            result = self.validator._validate_images(invalid_data)
            self.assertFalse(result)
            self.assertIn(
                f"Image test1.png missing required field: {field}",
                self.validator.errors,
            )

    def test_validate_settings_sources(self):
        """Test settings source validation"""
        data = {
            "content_types": ["hook"],
            "products": {"hook": []},
            "structure": {"hook": {"path": "/fake/path/hook", "images": ["test1.png"]}},
            "images": {
                "test1.png": {
                    "content_type": "hook",
                    "dimensions": {"width": 1920, "height": 1080},
                    "product": None,
                    "settings_source": "invalid",  # Invalid source
                    "settings": None,
                }
            },
            "untagged": [],
            "settings": {"hook": {"content": None}},
        }

        # Test invalid settings_source
        result = self.validator._validate_images(data)
        self.assertFalse(result)
        self.assertIn("invalid settings_source", str(self.validator.errors))

        # Test custom settings source with no settings
        data["images"]["test1.png"]["settings_source"] = "custom"
        result = self.validator._validate_images(data)
        self.assertFalse(result)
        self.assertIn(
            "has custom settings_source but settings are null",
            str(self.validator.errors),
        )

    def test_validate_settings_structure(self):
        """Test settings structure validation"""
        data = {
            "content_types": ["hook"],
            "products": {
                "hook": [
                    {
                        "name": "product1",
                        "prevent_duplicates": True,
                        "min_occurrences": 1,
                    }
                ]
            },
            "structure": {"hook": {"path": "/fake/path/hook", "images": []}},
            "images": {},
            "untagged": [],
            "settings": {"hook": {"content": None, "[product1]": None}},
        }

        # Test invalid settings type
        invalid_data = copy.deepcopy(data)
        invalid_data["settings"] = []
        result = self.validator._validate_settings(invalid_data)
        self.assertFalse(result)
        self.assertIn("settings must be a dictionary", self.validator.errors)

        # Test invalid product group format
        invalid_data = copy.deepcopy(data)
        invalid_data["settings"]["hook"]["product1"] = None  # Missing brackets
        result = self.validator._validate_settings(invalid_data)
        self.assertFalse(result)
        self.assertIn("Invalid product group format", str(self.validator.errors))

    def test_validate_untagged_images(self):
        """Test untagged images validation"""
        data = {
            "content_types": ["hook"],
            "products": {"hook": []},
            "structure": {"hook": {"path": "/fake/path/hook", "images": []}},
            "images": {},
            "untagged": ["test1.png", "test1.png"],  # Duplicate entry
            "settings": {},
        }

        # Test duplicate entries
        result = self.validator._validate_untagged(data)
        self.assertFalse(result)
        self.assertIn("Duplicate entries found in untagged list", self.validator.errors)

        # Test non-existent images
        self.mock_exists.return_value = False
        data["untagged"] = ["nonexistent.png"]
        result = self.validator._validate_untagged(data)
        self.assertFalse(result)
        self.assertIn("not found in base folder", str(self.validator.errors))

        # Test strict mode with untagged images
        self.validator.strict = True
        data["untagged"] = ["test1.png"]
        self.mock_exists.return_value = True
        result = self.validator._validate_untagged(data)
        self.assertFalse(result)
        self.assertIn(
            "Strict mode: Untagged images not allowed", str(self.validator.errors)
        )

    def test_validate_product_min_occurrences(self):
        """Test product max occurrences validation"""
        data = {
            "content_types": ["hook"],
            "products": {
                "hook": [
                    {
                        "name": "product1",
                        "prevent_duplicates": True,
                        "min_occurrences": 2,
                    }
                ]
            },
            "structure": {"hook": {"path": "/fake/path/hook", "images": ["test1.png"]}},
            "images": {
                "test1.png": {
                    "content_type": "hook",
                    "dimensions": {"width": 1920, "height": 1080},
                    "product": "product1",
                    "settings_source": "default",
                    "settings": None,
                }
            },
            "untagged": [],
            "settings": {"hook": {"content": None}},
        }

        # Test insufficient occurrences
        result = self.validator._validate_products(data, {"hook": ["product1"]})
        self.assertFalse(result)
        self.assertIn("requires at least 2 images", str(self.validator.errors))

        # Test exact occurrences
        data["images"]["test2.png"] = data["images"]["test1.png"].copy()
        data["structure"]["hook"]["images"].append("test2.png")
        result = self.validator._validate_products(data, {"hook": ["product1"]})
        self.assertTrue(result)

    def test_validate_settings_inheritance(self):
        """Test settings inheritance and validation"""
        data = {
            "content_types": ["hook"],
            "products": {
                "hook": [
                    {
                        "name": "product1",
                        "prevent_duplicates": True,
                        "min_occurrences": 0,
                    }
                ]
            },
            "structure": {"hook": {"path": "/fake/path/hook", "images": ["test1.png"]}},
            "images": {
                "test1.png": {
                    "content_type": "hook",
                    "dimensions": {"width": 1920, "height": 1080},
                    "product": "product1",
                    "settings_source": "content_type",
                    "settings": None,
                }
            },
            "untagged": [],
            "settings": {
                "hook": {"content": None, "[product1]": {"some_setting": "value"}}
            },
        }

        # Test content-level settings missing
        result = self.validator._validate_images(data)
        if self.validator.strict:
            self.assertFalse(result)
            self.assertIn(
                "uses content-level settings but none defined",
                str(self.validator.errors),
            )
        else:
            self.assertTrue(result)
            self.assertIn("will use default settings", str(self.validator.warnings))

    def test_validate_product_groups(self):
        """Test product group validation in settings"""
        data = {
            "content_types": ["hook"],
            "products": {
                "hook": [
                    {
                        "name": "product1",
                        "prevent_duplicates": True,
                        "min_occurrences": 0,
                    },
                    {
                        "name": "product2",
                        "prevent_duplicates": True,
                        "min_occurrences": 0,
                    },
                ]
            },
            "structure": {"hook": {"path": "/fake/path/hook", "images": []}},
            "images": {},
            "untagged": [],
            "settings": {
                "hook": {"content": None, "[product1]": None, "[product2]": None}
            },
        }

        # Test overlapping product groups
        invalid_data = copy.deepcopy(data)
        invalid_data["settings"]["hook"]["[product1,product2]"] = None
        invalid_data["settings"]["hook"]["[product2]"] = None
        result = self.validator._validate_settings(invalid_data)
        self.assertFalse(result)
        self.assertIn("Duplicate products in hook settings", str(self.validator.errors))

        # Test invalid product in group
        invalid_data = copy.deepcopy(data)
        invalid_data["settings"]["hook"]["[invalid_product]"] = None
        result = self.validator._validate_settings(invalid_data)
        self.assertFalse(result)
        self.assertIn("Invalid products in hook settings", str(self.validator.errors))

    def test_validate_product_references(self):
        """Test product reference validation in images"""
        data = {
            "content_types": ["hook"],
            "products": {
                "hook": [
                    {
                        "name": "product1",
                        "prevent_duplicates": True,
                        "min_occurrences": 0,
                        "current_count": 0  # Add new field
                    }
                ]
            },
            "structure": {"hook": {"path": "/fake/path/hook", "images": ["test1.png"]}},
            "images": {
                "test1.png": {
                    "content_type": "hook",
                    "dimensions": {"width": 1920, "height": 1080},
                    "product": "invalid_product",  # Invalid product reference
                    "settings_source": "default",
                    "settings": None,
                }
            },
            "untagged": [],
            "settings": {"hook": {"content": None}},
        }

        result = self.validator._validate_images(data)
        self.assertFalse(result)
        self.assertIn(
            "has invalid product: invalid_product", str(self.validator.errors)
        )

    def test_validate_content_type_consistency(self):
        """Test content type consistency across metadata"""
        data = {
            "content_types": ["hook"],
            "products": {
                "invalid": []  # Inconsistent content type
            },
            "structure": {"hook": {"path": "/fake/path/hook", "images": []}},
            "images": {},
            "untagged": [],
            "settings": {"hook": {"content": None}},
        }

        result = self.validator._validate_products(data, {"hook": []})
        self.assertFalse(result)
        self.assertIn("Product content types mismatch", str(self.validator.errors))

        # Test settings content type consistency
        invalid_data = copy.deepcopy(data)
        invalid_data["products"] = {"hook": []}
        invalid_data["settings"] = {"invalid": {"content": None}}
        result = self.validator._validate_settings(invalid_data)
        self.assertFalse(result)
        self.assertIn(
            "Settings defined for invalid content type", str(self.validator.errors)
        )
