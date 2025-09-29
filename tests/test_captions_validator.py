import unittest
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile

from content_manager.captions import CaptionsValidator


class TestCaptionsValidator(unittest.TestCase):
    def setUp(self):
        self.validator = CaptionsValidator()

    def _create_test_file(self, content: str) -> StringIO:
        """Helper to create test file content"""
        return StringIO(content)

    """
    def test_valid_basic_file(self):
        "" "Test a minimal valid file"" "
        content = (
            "product_hook,hook,product_content,content,product_content,content,product_cta,cta\n"
            "tiktok shop,HOOK YAY,magnesium,check this out content,vitamin d,this makes me sleep so well,swipe,go to the bio\n"
        )
        test_file = self._create_test_file(content)
        content_types, products = self.validator.validate(test_file, separator=",")
        
        # Expected content types are hook, content, cta (from the header pairs)
        self.assertEqual(content_types, {'hook', 'content', 'cta'})
        
        # Products should be grouped by content type
        expected_products = {
            'hook': ['tiktok shop'],
            'content': ['magnesium', 'vitamin d'],
            'cta': ['swipe']
        }
        self.assertEqual(products, expected_products)
    """

    # File Level Tests
    def test_file_must_exist(self):
        """File must exist"""
        non_existent = Path("does_not_exist.csv")
        with self.assertRaises(ValueError) as context:
            self.validator.validate(non_existent)
        self.assertIn("does not exist", str(context.exception))

    def test_file_must_be_a_file(self):
        """Must be a file, not a directory"""
        # Create a directory with the same name
        dir_path = Path("test_dir.csv")
        dir_path.mkdir(exist_ok=True)
        try:
            with self.assertRaises(ValueError) as context:
                self.validator.validate(dir_path)
            self.assertIn("not a file", str(context.exception))
        finally:
            dir_path.rmdir()  # cleanup

    def test_file_must_not_be_empty(self):
        """File must not be empty"""
        empty_file = Path("empty.csv")
        empty_file.touch()  # creates empty file
        try:
            with self.assertRaises(ValueError) as context:
                self.validator.validate(empty_file)
            self.assertIn("empty", str(context.exception))
        finally:
            empty_file.unlink()  # cleanup

    def test_file_must_be_utf8_encoded(self):
        """File must be UTF-8 encoded"""
        non_utf8 = Path("non_utf8.csv")
        # Write some non-UTF8 content
        with open(non_utf8, "wb") as f:
            f.write(b"\xff\xfe\x00\x00")  # UTF-32 BOM
        try:
            with self.assertRaises(ValueError) as context:
                self.validator.validate(non_utf8)
            self.assertIn("UTF-8", str(context.exception))
        finally:
            non_utf8.unlink()  # cleanup

    # Header Level Tests
    def test_headers_must_exist(self):
        """Headers must exist"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("\nsome,data,here")  # File starts with newline

        try:
            with self.assertRaises(ValueError) as context:
                self.validator.validate(Path(f.name))
            self.assertIn("Headers must exist", str(context.exception))
        finally:
            Path(f.name).unlink()  # cleanup

    def test_headers_cannot_be_empty_or_whitespace(self):
        """Headers cannot be empty or whitespace"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("product_hook,,product_content,content\ndata,empty,data2,content")

        try:
            with self.assertRaises(ValueError) as context:
                self.validator.validate(Path(f.name))
            self.assertIn("cannot be empty or whitespace", str(context.exception))
        finally:
            Path(f.name).unlink()

    def test_content_headers_must_have_matching_product_headers(self):
        """Content headers must have matching product headers"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("hook,content\nsome,data")  # Missing product_ prefixes

        try:
            with self.assertRaises(ValueError) as context:
                self.validator.validate(Path(f.name))
            self.assertIn("has no matching product header", str(context.exception))
        finally:
            Path(f.name).unlink()

    def test_headers_format_must_be_product_content_type(self):
        """Headers must follow format 'product_[content_type]'"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "productcontent,content\n"  # Malformed header
                "data1,data2"
            )

        try:
            with self.assertRaises(ValueError) as context:
                self.validator.validate(Path(f.name))
            self.assertIn("Invalid product header format", str(context.exception))
        finally:
            Path(f.name).unlink()

    def test_headers_content_type_dont_have_to_be_unique(self):
        """Duplicate content types are allowed"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_content,content,product_content,content\n"
                "prod1,cont1,prod2,cont2\n"
            )  # Added newline

        try:
            content_types, products = self.validator.validate(Path(f.name))
            self.assertEqual(
                len(content_types), 1
            )  # Should only have one unique content type
            self.assertIn("content", content_types)
        finally:
            Path(f.name).unlink()

    def test_different_separators(self):
        """Test different CSV separators"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_hook;hook;product_content;content\ndata1;data2;data3;data4"
            )

        try:
            content_types, products = self.validator.validate(
                Path(f.name), separator=";"
            )
            self.assertIn("hook", content_types)
            self.assertIn("content", content_types)
        finally:
            Path(f.name).unlink()

    def test_malformed_headers(self):
        """Test malformed header formats"""
        bad_headers = [
            "Product_hook,hook",  # Wrong capitalization
            "_product_hook,hook",  # Extra underscore
            "product__hook,hook",  # Double underscore
            "productHook,hook",  # CamelCase without underscore
        ]

        for headers in bad_headers:
            with NamedTemporaryFile(mode="w", delete=False) as f:
                f.write(f"{headers}\ndata1,data2\n")

            try:
                with self.assertRaises(ValueError) as context:
                    self.validator.validate(Path(f.name))
                self.assertTrue(
                    "Invalid product header format" in str(context.exception)
                    or "has no matching product header" in str(context.exception)
                )
            finally:
                Path(f.name).unlink()

    def test_valid_header_pairs(self):
        """Test valid header pairs combinations"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_hook,hook,product_content,content,product_cta,cta\ndata1,data2,data3,data4,data5,data6"
            )

        try:
            content_types, products = self.validator.validate(Path(f.name))
            expected_types = {"hook", "content", "cta"}
            self.assertEqual(content_types, expected_types)
        finally:
            Path(f.name).unlink()

    # Row Level Tests
    def test_row_must_not_be_completely_empty(self):
        """Row must not be completely empty"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_hook,hook,product_content,content\n"
                "data1,data2,data3,data4\n"
                ",,,,\n"
            )  # Empty row

        try:
            with self.assertRaises(ValueError) as context:
                self.validator.validate(Path(f.name))
            self.assertIn("empty or contains only whitespace", str(context.exception))
        finally:
            Path(f.name).unlink()

    def test_row_must_have_correct_number_of_columns(self):
        """Row must have correct number of columns"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_hook,hook,product_content,content\n" "data1,data2,data3\n"
            )  # Missing column

        try:
            with self.assertRaises(ValueError) as context:
                self.validator.validate(Path(f.name))
            self.assertIn("incorrect number of columns", str(context.exception))
        finally:
            Path(f.name).unlink()

    def test_all_cells_must_be_strings(self):
        """All cells must be strings"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_hook,hook,product_content,content\n" "data1,123,data3,data4\n"
            )  # Numeric value

        try:
            with self.assertRaises(ValueError) as context:
                self.validator.validate(Path(f.name))
            self.assertIn("not a string", str(context.exception))
        finally:
            Path(f.name).unlink()

    def test_cells_cannot_be_whitespace_only(self):
        """Cells cannot be whitespace-only"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_hook,hook,product_content,content\n"
                'data1,"",   ,""'  # Properly quoted empty cells AND a whitespace cell
            )

        try:
            with self.assertRaises(ValueError) as context:
                self.validator.validate(Path(f.name))
            self.assertIn("whitespace only", str(context.exception))
        finally:
            Path(f.name).unlink()

    def test_at_least_one_valid_row_must_exist(self):
        """At least one valid row must exist"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_hook,hook,product_content,content\n"
                ",,,,\n"  # Invalid row
                "   ,   ,   ,   \n"
            )  # Another invalid row

        try:
            with self.assertRaises(ValueError) as context:
                self.validator.validate(Path(f.name))
            self.assertIn("empty or contains only whitespace", str(context.exception))
        finally:
            Path(f.name).unlink()

    def test_valid_rows_with_some_empty_cells(self):
        """Valid rows can have empty cells but not all empty"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_hook,hook,product_content,content\n"
                'data1,"",data3,""\n'  # Use explicit quotes for empty content cells
            )
        try:
            content_types, products = self.validator.validate(Path(f.name))
            # Verify the validation succeeded
            self.assertIn("hook", content_types)
            self.assertIn("content", content_types)
            self.assertEqual(products["hook"], ["data1"])
            self.assertEqual(products["content"], ["data3"])
        finally:
            Path(f.name).unlink()

    # Content Level Tests
    def test_empty_content_must_use_explicit_quotes(self):
        """Empty content must use explicit '""'"""

    def test_content_without_product(self):
        """Content without product triggers warning or error based on strict mode"""

    def test_product_without_content(self):
        """Product without content triggers warning or error based on strict mode"""

    # Product Level Tests

    def test_product_names_can_contain_header_names(self):
        """Product names can contain header names as substrings"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_hook,hook,product_content,content\n"
                "hooky,hook1,contently,content1\n"
            )  # Valid: contains but doesn't match
        try:
            content_types, products = self.validator.validate(Path(f.name))
            self.assertTrue("hook" in products)  # Should validate successfully
        finally:
            Path(f.name).unlink()

    def test_product_names_can_be_header_values(self):
        """Product names can be header values (like 'product' or 'content')"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_hook,hook,product_content,content\n"
                "product,hook1,content2,content1\n"
            )  # Valid: 'product' for hook, 'content2' for content
        try:
            content_types, products = self.validator.validate(Path(f.name))
            self.assertTrue("hook" in products)  # Should validate successfully
        finally:
            Path(f.name).unlink()

    def test_product_names_cannot_match_content_types(self):
        """Product names cannot match their content type (case insensitive)"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_hook,hook,product_content,content\n"
                "HOOK,hook1,content1,content2\n"
            )  # Invalid: 'HOOK' matches content type 'hook'
        try:
            with self.assertRaises(ValueError) as context:
                self.validator.validate(Path(f.name))
            self.assertIn("cannot match content type", str(context.exception))
        finally:
            Path(f.name).unlink()

    def test_product_names_cannot_be_reserved_words(self):
        """Product names cannot be reserved words ('none', 'all') case insensitive"""
        reserved_tests = ["none", "NONE"]
        for word in reserved_tests:
            with NamedTemporaryFile(mode="w", delete=False) as f:
                f.write(f"product_hook,hook\n{word},hook1\n")
            try:
                with self.assertRaises(ValueError) as context:
                    self.validator.validate(Path(f.name))
                self.assertIn("reserved word", str(context.exception))
            finally:
                Path(f.name).unlink()

    def test_product_names_can_contain_special_chars(self):
        """Product names can contain spaces, hyphens, and underscores"""
        valid_names = [
            "tiktok shop",
            "tiktok  shop",  # double space
            "tiktok-shop",  # hyphen
            "tiktok_shop",  # underscore
        ]
        for name in valid_names:
            with NamedTemporaryFile(mode="w", delete=False) as f:
                f.write(f"product_hook,hook\n{name},hook1\n")
            try:
                content_types, products = self.validator.validate(Path(f.name))
                self.assertTrue("hook" in products)  # Should validate successfully
            finally:
                Path(f.name).unlink()

    def test_product_names_must_be_unique_per_product_type_strict(self):
        """Product names must be unique within same content type (case insensitive) in strict mode"""
        validator = CaptionsValidator(strict=True)
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_hook,hook,product_content,content\n"
                "vitamin d,hook1,vitamin2,content1\n"
                "Vitamin D,hook2,vitamin3,content2\n"
            )  # 'Vitamin D' duplicates 'vitamin d' in hook type
        try:
            with self.assertRaises(ValueError):
                validator.validate(Path(f.name))
        finally:
            Path(f.name).unlink()

    def test_product_names_duplicates_warning_non_strict(self):
        """Product name duplicates should raise warning in non-strict mode"""
        validator = CaptionsValidator(strict=False)  # Ensure non-strict mode
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_hook,hook,product_content,content\n"
                "vitamin d,hook1,vitamin2,content1\n"
                "Vitamin D,hook2,vitamin3,content2\n"
            )  # Testing duplicate in hook type
        try:
            validator.validate(Path(f.name))
            print(
                "\nWarnings after validation:", validator.warnings
            )  # Use warnings from StrictValidator
            self.assertTrue(
                any(
                    "duplicate product name" in warning.lower()
                    for warning in validator.warnings
                ),
                f"No duplicate warning found in warnings: {validator.warnings}",
            )
        finally:
            Path(f.name).unlink()

    # Data Consistency Tests
    def test_all_content_types_must_exist_in_products_dictionary(self):
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_hook,hook,product_content,content,product_cta,cta\n"
                'prod1,hook1,"","","",""\n'  # All empty cells should use explicit quotes
            )

        try:
            content_types, products = self.validator.validate(Path(f.name))
            # All three content types should exist in products dict
            expected_types = {"hook", "content", "cta"}
            self.assertEqual(set(products.keys()), expected_types)
            # Verify empty lists are present
            self.assertEqual(products["content"], [])
            self.assertEqual(products["cta"], [])
        finally:
            Path(f.name).unlink()

    def test_no_extra_content_types_in_products_dictionary(self):
        """No extra content types in products dictionary"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_hook,hook\n"  # Only one content type
                "prod1,hook1\n"
            )

        try:
            content_types, products = self.validator.validate(Path(f.name))
            # Should only have 'hook' in both sets
            self.assertEqual(set(products.keys()), {"hook"})
            self.assertEqual(content_types, {"hook"})
        finally:
            Path(f.name).unlink()

    def test_content_cells_must_use_explicit_empty_quotes(self):
        """Content cells must use explicit quotes ("") when empty, but product cells can be empty"""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_hook,hook,product_content,content\n"
                "tiktok shop,some hook,,\n"  # Empty content cell without quotes - should fail
                'tiktok shop,some hook,,""\n'  # Empty content cell with quotes - should pass
            )

        try:
            with self.assertRaises(ValueError) as context:
                self.validator.validate(Path(f.name))
            self.assertIn('must use explicit quotes ("")', str(context.exception))
        finally:
            Path(f.name).unlink()

    def test_product_cells_can_be_empty(self):
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write(
                "product_hook,hook,product_content,content\n"
                ',"",,""\n'  # Empty all cells with explicit quotes
            )

        try:
            content_types, products = self.validator.validate(Path(f.name))
            # Should have warning but not error
            self.assertTrue(
                any("Empty product cell" in w for w in self.validator.warnings)
            )
            self.assertEqual(len(self.validator.errors), 0)
        finally:
            Path(f.name).unlink()


if __name__ == "__main__":
    unittest.main()
