import unittest

from content_manager.strict_validator import StrictValidator


class TestStrictValidator(unittest.TestCase):
    def setUp(self):
        self.validator = StrictValidator()

    def test_errors_always_fail(self):
        """Errors should fail validation regardless of strict mode"""
        # Test in non-strict mode
        self.validator.strict = False
        self.validator.add_error("Test error")
        with self.assertRaises(ValueError) as context:
            self.validator.raise_if_errors()
        self.assertIn("Test error", str(context.exception))

        # Test in strict mode
        self.validator.clear_messages()
        self.validator.strict = True
        self.validator.add_error("Test error")
        with self.assertRaises(ValueError) as context:
            self.validator.raise_if_errors()
        self.assertIn("Test error", str(context.exception))

    def test_warnings_only_fail_in_strict(self):
        """Warnings should only fail validation in strict mode"""
        # Test in non-strict mode
        self.validator.strict = False
        self.validator.add_warning("Test warning")
        try:
            self.validator.raise_if_errors()
        except ValueError:
            self.fail("Warning raised error in non-strict mode")

        # Test in strict mode
        self.validator.clear_messages()
        self.validator.strict = True
        self.validator.add_warning("Test warning")
        with self.assertRaises(ValueError) as context:
            self.validator.raise_if_errors()
        self.assertIn("[STRICT MODE] Test warning", str(context.exception))

    def test_mixed_warnings_and_errors(self):
        """Test behavior with both warnings and errors"""
        self.validator.add_error("Test error")
        self.validator.add_warning("Test warning")

        # Non-strict mode should only show error
        self.validator.strict = False
        with self.assertRaises(ValueError) as context:
            self.validator.raise_if_errors()
        self.assertIn("Test error", str(context.exception))
        self.assertNotIn("Test warning", str(context.exception))

        # Strict mode should show both
        self.validator.clear_messages()
        self.validator.strict = True
        self.validator.add_error("Test error")
        self.validator.add_warning("Test warning")
        with self.assertRaises(ValueError) as context:
            self.validator.raise_if_errors()
        self.assertIn("Test error", str(context.exception))
        self.assertIn("[STRICT MODE] Test warning", str(context.exception))

    def test_clear_messages(self):
        """Test that clear_messages removes all warnings and errors"""
        self.validator.add_error("Test error")
        self.validator.add_warning("Test warning")
        self.validator.clear_messages()
        self.assertEqual(len(self.validator.errors), 0)
        self.assertEqual(len(self.validator.warnings), 0)
