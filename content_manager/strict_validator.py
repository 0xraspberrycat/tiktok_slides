from typing import List, Tuple

from config.logging import logger


class StrictValidator:
    def __init__(self, strict: bool = False):
        self.strict = strict
        self.warnings: List[str] = []
        self.errors: List[str] = []

    def add_warning(self, message: str):
        """Add warning and log it"""
        self.warnings.append(message)
        logger.warning(f"Validation warning: {message}")
        if self.strict:
            # In strict mode, warnings are treated as errors
            self.errors.append(f"[STRICT MODE] {message}")
            logger.critical(f"Strict mode validation error: {message}")

    def add_error(self, message: str):
        """Add error and log it"""
        self.errors.append(message)
        logger.critical(f"Validation error: {message}")

    def has_errors(self) -> bool:
        """Check if there are any errors"""
        return len(self.errors) > 0

    def clear_messages(self):
        """Clear all warnings and errors"""
        self.warnings.clear()
        self.errors.clear()

    def raise_if_errors(self):
        """Raise ValueError if there are any errors"""
        if self.has_errors():
            error_msg = "\n".join(self.errors)
            logger.critical(f"Validation failed with errors:\n{error_msg}")
            raise ValueError(error_msg)
