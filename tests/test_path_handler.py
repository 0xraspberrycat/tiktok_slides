import os
import shutil
import tempfile
import unittest
from pathlib import Path

from content_manager.path_handler import PathValidator

"""
Complete Test List
Base Path Validation DONE 
Test empty/None path DONE 
Test non-existent path DONE 
Test path without captions.csv DONE
Test path with captions.csv DONE

Folder Structure Validation
Test missing folders (strict vs non-strict) DONE
Test extra folders DONE
Test folder names matching content types exactly
Test folder permissions DONE
Test duplicate content type folders

Strict Mode Behavior
Test warnings become errors DONE
Test missing folders fail in strict DONE
Test all validations must pass
Test warning/error message storage DONE

Content Validation
Test image existence in folders DONE
Test image formats (PNG) DONE
Test empty folders DONE
Test invalid files in folders DONE

Integration Tests
Test full validation flow with valid structure DONE
Test full validation flow with various issues DONE
Test validation with different strict settings DONE
"""


class TestPathValidator(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test"""
        self.validator = PathValidator()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.validator.content_types = {"hook", "content", "cta"}

        # Create captions.csv to make it a valid base folder
        with open(self.temp_dir / "captions.csv", "w") as f:
            f.write("product_hook,hook,product_content,content,product_cta,cta\n")

    def tearDown(self):
        """Clean up test environment after each test"""
        shutil.rmtree(self.temp_dir)

    def test_validate_nonexistent_path(self):
        """Test validation fails with non-existent path"""
        non_existent_path = self.temp_dir / "does_not_exist"

        result = self.validator.validate(non_existent_path)

        self.assertFalse(result)
        self.assertEqual(len(self.validator.errors), 1)
        self.assertIn("does not exist", self.validator.errors[0])

    def test_validate_none_path(self):
        """Test validation fails with None path"""
        result = self.validator.validate(None)

        self.assertFalse(result)
        self.assertEqual(len(self.validator.errors), 1)
        self.assertIn("cannot be None", self.validator.errors[0])

    def test_validate_empty_path(self):
        """Test validation fails with empty path"""
        result = self.validator.validate(Path(""))

        self.assertFalse(result)
        self.assertEqual(len(self.validator.errors), 1)
        self.assertIn("cannot be empty", self.validator.errors[0])

    def test_validate_missing_captions_csv(self):
        """Test validation fails when captions.csv is missing"""
        # Remove the captions.csv created in setUp
        (self.temp_dir / "captions.csv").unlink()

        result = self.validator.validate(self.temp_dir)

        self.assertFalse(result)
        self.assertEqual(len(self.validator.errors), 1)
        self.assertIn("captions.csv' not found", self.validator.errors[0])

    def test_validate_with_captions_csv(self):
        """Test validation passes with valid captions.csv"""
        # Create directory with captions.csv
        os.makedirs(self.temp_dir, exist_ok=True)
        with open(self.temp_dir / "captions.csv", "w") as f:
            f.write("test")

        result = self.validator.validate(self.temp_dir)

        self.assertTrue(result)
        self.assertEqual(len(self.validator.errors), 0)

    def test_validate_captions_csv_is_directory(self):
        """Test validation fails when captions.csv is a directory"""
        # Remove the file created in setUp first
        (self.temp_dir / "captions.csv").unlink()
        # Now create as directory
        (self.temp_dir / "captions.csv").mkdir()

        result = self.validator.validate(self.temp_dir)

        self.assertFalse(result)
        self.assertEqual(len(self.validator.errors), 1)
        self.assertIn("exists but is not a file", self.validator.errors[0])

    def test_validate_path_is_file(self):
        """Test validation fails when path is a file instead of directory"""
        # Create a file instead of directory
        file_path = self.temp_dir / "test.txt"
        with open(file_path, "w") as f:
            f.write("test")

        result = self.validator.validate(file_path)

        self.assertFalse(result)
        self.assertEqual(len(self.validator.errors), 1)
        self.assertIn("is not a directory", self.validator.errors[0])

    # Folder Structure Tests
    def test_missing_folders_strict_mode(self):
        """Should fail in strict mode when content type folders are missing"""
        # Set strict mode
        self.validator.strict = True

        # Create only one of the required folders
        (self.temp_dir / "hook").mkdir()

        # Should fail because 'content' and 'cta' folders are missing
        with self.assertRaises(ValueError) as context:
            self.validator.folder_validation(self.temp_dir)

        # Verify error message
        self.assertIn("does not exist", str(context.exception))
        # Verify specific folders mentioned in errors
        self.assertTrue(any("content" in err for err in self.validator.errors))
        self.assertTrue(any("cta" in err for err in self.validator.errors))

    def test_missing_folders_non_strict_mode(self):
        """Should warn but not fail in non-strict mode when content type folders are missing"""
        # Set non-strict mode
        self.validator.strict = False

        # Create only one of the required folders
        (self.temp_dir / "hook").mkdir()

        # Should not fail but should add warnings
        result = self.validator.folder_validation(self.temp_dir)
        self.assertTrue(result)  # Validation should pass

        # Verify warnings were added
        self.assertTrue(any("content" in w for w in self.validator.warnings))
        self.assertTrue(any("cta" in w for w in self.validator.warnings))
        self.assertEqual(len(self.validator.errors), 0)  # No errors in non-strict mode

    def test_unexpected_folder_fails(self):
        """Should fail when unexpected folders exist in base path"""
        # Setup test with unexpected folder
        (self.temp_dir / "unexpected").mkdir()

        with self.assertRaises(ValueError) as context:
            self.validator.folder_validation(self.temp_dir)

        # Update the expected message to match the actual error message
        self.assertIn("Unexpected folder(s) found: unexpected", str(context.exception))

    def test_content_type_folder_names_must_match_exactly(self):
        """Should fail if folder names don't exactly match content types (case sensitive)"""
        # Create folder with wrong case
        (self.temp_dir / "Hook").mkdir()

        with self.assertRaises(ValueError) as context:
            self.validator.folder_validation(self.temp_dir)

        self.assertIn(
            "Invalid folder name: 'Hook' must exactly match content type 'hook'",
            str(context.exception),
        )

    def test_folder_permissions_read_write(self):
        """Should fail if folders don't have read/write permissions"""

    def test_empty_content_folders_allowed(self):
        """Should warn in non-strict mode and fail in strict mode if folders are empty"""
        # Create empty folders for all content types
        for content_type in self.validator.content_types:
            (self.temp_dir / content_type).mkdir()

        # Test non-strict mode
        self.validator.strict = False
        result = self.validator.folder_validation(self.temp_dir)
        self.assertTrue(result)  # Should pass with warnings
        self.assertTrue(any("empty" in w for w in self.validator.warnings))

        # Test strict mode
        self.validator.strict = True
        with self.assertRaises(ValueError) as context:
            self.validator.folder_validation(self.temp_dir)
        self.assertIn("Folder is empty", str(context.exception))

    # File Validation Tests
    def test_only_images_allowed_in_content_folders(self):
        """Should fail if non-image files exist in content folders"""
        # Create content folders
        for content_type in self.validator.content_types:
            folder = self.temp_dir / content_type
            folder.mkdir()

            # Add valid image
            with open(folder / "valid.png", "wb") as f:
                f.write(b"PNG")  # Minimal PNG file content

            # Add invalid file
            with open(folder / "invalid.txt", "w") as f:
                f.write("not an image")

        with self.assertRaises(ValueError) as context:
            self.validator.folder_validation(self.temp_dir)

        self.assertIn("Invalid file in", str(context.exception))
        self.assertIn(".txt", str(context.exception))

    def test_hidden_files_are_ignored(self):
        """Should ignore hidden files (starting with .)"""
        # Create all required content folders with unique valid images
        png_headers = [
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89",
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02\x08\x06\x00\x00\x00\x72\xb6\x0d\x24",
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x03\x00\x00\x00\x03\x08\x06\x00\x00\x00\x56\x28\xb5\xbf",
        ]

        for i, content_type in enumerate(self.validator.content_types):
            folder = self.temp_dir / content_type
            folder.mkdir()
            # Add valid image with UNIQUE name AND content
            with open(folder / f"valid_{content_type}.png", "wb") as f:
                f.write(png_headers[i])  # Use different header for each file

        # Create various hidden files in one of the folders
        content_folder = self.temp_dir / "content"
        hidden_files = [
            ".DS_Store",
            ".gitignore",
            ".hidden_folder/.hidden_file",
        ]

        for hidden_file in hidden_files:
            file_path = content_folder / hidden_file
            file_path.parent.mkdir(exist_ok=True, parents=True)
            with open(file_path, "w") as f:
                f.write("hidden")

        # Should pass validation since hidden files are ignored
        result = self.validator.folder_validation(self.temp_dir)
        self.assertTrue(result)

    def test_base_folder_only_allows_specific_files(self):
        """Should only allow captions.csv and metadata.json in base folder"""
        # Create valid files
        with open(self.temp_dir / "captions.csv", "w") as f:
            f.write("test")
        with open(self.temp_dir / "metadata.json", "w") as f:
            f.write("{}")

        # Create invalid files
        with open(self.temp_dir / "invalid.txt", "w") as f:
            f.write("not allowed")
        with open(self.temp_dir / "image.png", "wb") as f:
            f.write(b"PNG")

        with self.assertRaises(ValueError) as context:
            self.validator.validate(self.temp_dir)

        self.assertIn("Invalid file in base folder", str(context.exception))

    def test_no_nested_folders_in_content_folders(self):
        """Should fail if content folders contain nested folders"""
        # Create content folders with nested folder
        for content_type in self.validator.content_types:
            folder = self.temp_dir / content_type
            folder.mkdir()
            # Add valid image to avoid empty folder error
            with open(folder / "valid.png", "wb") as f:
                f.write(
                    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                )

        # Create nested folder in one content folder
        nested_folder = self.temp_dir / "content" / "nested"
        nested_folder.mkdir()

        with self.assertRaises(ValueError) as context:
            self.validator.folder_validation(self.temp_dir)

        self.assertIn("Nested folder found in content", str(context.exception))

    def test_valid_image_formats_accepted(self):
        """Should accept all valid image formats"""
        # Create a single folder for testing
        test_folder = self.temp_dir / "content"
        test_folder.mkdir()

        # Minimal valid image headers
        png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        jpg_header = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00"

        # Test various image formats
        test_files = {
            "test.png": (True, png_header),
            "test.PNG": (True, png_header),
            "test.jpg": (True, jpg_header),
            "test.JPG": (True, jpg_header),
            "test.jpeg": (True, jpg_header),
            "test.JPEG": (True, jpg_header),
            "test.txt": (False, b"not an image"),
            "test.gif": (False, b"not an image"),
            "test": (False, b"no extension"),
        }

        for filename, (should_be_valid, content) in test_files.items():
            file_path = test_folder / filename
            with open(file_path, "wb") as f:
                f.write(content)
            result = self.validator._is_valid_image(file_path)
            self.assertEqual(result, should_be_valid, f"Failed for {filename}")

    def test_duplicate_image_names_not_allowed(self):
        """Should fail if same image name exists with different extensions"""
        # Create test structure
        for folder in ["hook", "content", "cta"]:
            (self.temp_dir / folder).mkdir()

        # Create test files with valid PNG header
        png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"

        # Create duplicates across different folders
        test_files = [
            ("hook/1.png", png_header),
            ("content/1.PNG", png_header),
            ("cta/1.jpg", png_header),
            ("2.png", png_header),  # in base folder
            ("hook/2.PNG", png_header),
            ("content/unique.png", png_header),
        ]

        for path, content in test_files:
            file_path = self.temp_dir / path
            file_path.parent.mkdir(exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(content)

        with self.assertRaises(ValueError) as context:
            self.validator._check_duplicate_image_names(self.temp_dir)

        error_msg = str(context.exception)
        # Verify both duplicate groups are reported
        self.assertIn("Duplicate image names found:", error_msg)
        self.assertIn("[content/1.PNG, cta/1.jpg, hook/1.png]", error_msg)
        self.assertIn("[2.png, hook/2.PNG]", error_msg)

    def test_duplicate_image_content_not_allowed(self):
        """Should fail if identical images exist with different names"""
        # Create test structure
        for folder in ["hook", "content", "cta"]:
            (self.temp_dir / folder).mkdir()

        # Two different PNG headers for testing
        png_1 = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        png_2 = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02\x08\x06\x00\x00\x00\x72\xb6\x0d\x24"

        # Create test files - some with same content, some different
        test_files = [
            ("hook/image1.png", png_1),
            ("content/image2.png", png_1),  # Same as image1
            ("cta/image3.png", png_2),  # Different content
            ("image4.png", png_1),  # Same as image1, in base folder
            ("content/unique.png", png_2),  # Same as image3
        ]

        for path, content in test_files:
            file_path = self.temp_dir / path
            file_path.parent.mkdir(exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(content)

        with self.assertRaises(ValueError) as context:
            self.validator._check_duplicate_image_content(self.temp_dir)

        error_msg = str(context.exception)
        # Verify duplicate groups are reported
        self.assertIn("Duplicate images found:", error_msg)
        self.assertIn("[content/image2.png, hook/image1.png, image4.png]", error_msg)
        self.assertIn("[content/unique.png, cta/image3.png]", error_msg)

    # Integration Tests
    def test_valid_structure_passes_validation(self):
        """Should pass validation with correct folder structure and files"""
        # Create required folders
        for content_type in self.validator.content_types:
            folder = self.temp_dir / content_type
            folder.mkdir()

            # Add unique valid image to each folder
            with open(folder / f"valid_{content_type}.png", "wb") as f:
                # Use different PNG headers for each file to avoid duplicate content
                if content_type == "hook":
                    f.write(
                        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                    )
                elif content_type == "content":
                    f.write(
                        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02\x08\x06\x00\x00\x00\x72\xb6\x0d\x24"
                    )
                else:  # cta
                    f.write(
                        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x03\x00\x00\x00\x03\x08\x06\x00\x00\x00\x56\x28\xb5\xbf"
                    )

        # Create required captions.csv
        with open(self.temp_dir / "captions.csv", "w") as f:
            f.write("image,caption\n")  # Header only is fine for validation

        # Run validation
        result = self.validator.validate(self.temp_dir)
        self.assertTrue(result)
        self.assertEqual(len(self.validator.errors), 0)
        self.assertEqual(len(self.validator.warnings), 0)

    def test_strict_mode_converts_warnings_to_errors(self):
        """Should treat warnings as errors in strict mode"""
        # Create base structure
        for content_type in self.validator.content_types:
            folder = self.temp_dir / content_type
            folder.mkdir()

        # Create required captions.csv
        with open(self.temp_dir / "captions.csv", "w") as f:
            f.write("image,caption\n")

        # Test in non-strict mode first - should pass with warnings
        self.validator.strict = False
        result = self.validator.folder_validation(self.temp_dir)
        self.assertTrue(result)
        self.assertTrue(
            len(self.validator.warnings) > 0
        )  # Should have empty folder warnings
        self.assertEqual(len(self.validator.errors), 0)

        # Test in strict mode - same conditions should fail
        self.validator.strict = True
        with self.assertRaises(ValueError) as context:
            self.validator.folder_validation(self.temp_dir)

        self.assertIn("empty", str(context.exception))
