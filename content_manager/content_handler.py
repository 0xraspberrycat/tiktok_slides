from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from config.logging import logger

from .captions import CaptionsValidator
from .metadata.metadata import Metadata
from .metadata.metadata_editor import MetadataEditor
from .path_handler import PathValidator
from .strict_validator import StrictValidator

"""
1. Path Validation (PathValidator)
├── Check if path exists
├── Check if it's a directory
├── Check if readable
└── Check for captions.csv

2. Captions Validation (CaptionsValidator)
├── Read CSV file
├── Validate headers (product_type, type pairs)
├── Extract content types
└── Return content_types and products

3. Folder Structure Validation (PathValidator again)
├── Check folders exist for each content type
├── Handle missing folders (create/warn or error based on strict)
└── Check for unexpected folders

4. Content Validation
└── (This seems to be handled by _validate_content method)

then we do image validation
"""


class ContentHandler(StrictValidator):
    """Handles content loading, validation, and management"""

    def __init__(self, strict: bool = False):
        super().__init__(strict)
        self.base_path: Path = None
        self.content_types: List[str] = []
        self.products: Dict[str, List[str]] = {}
        self.path_validator = PathValidator(strict=strict)
        self.captions_validator = CaptionsValidator(strict=strict)
        self.metadata = None
        self.metadata_editor = None

    def validate(
        self,
        path: Optional[Path] = None,
        separator: str = ",",
        strict: Optional[bool] = None,
    ) -> bool:
        """Validate content structure and load if path provided

        Args:
            path: Optional path to validate
            separator: CSV separator character
            strict: If provided, overrides the instance's strict mode for this validation

        Returns:
            bool: True if validation passes, False if errors/warnings exist
        """
        try:
            if path:
                self.base_path = path

            if not self.base_path:
                self.add_error("No path set - please provide a path")
                return False
            logger.trace(f"Using base_path: {self.base_path}")
            logger.trace(f"Strict mode: {self.strict if strict is None else strict}")

            # Update strict mode if provided
            if strict is not None:
                self.strict = strict
                self.path_validator.strict = strict
                self.captions_validator.strict = strict

            # First validate path structure
            if not self.path_validator.validate(self.base_path):
                self.errors.extend(self.path_validator.errors)
                self.warnings.extend(self.path_validator.warnings)
                return False

            # Then validate captions file
            captions_path = self.base_path / "captions.csv"
            logger.trace(f"\nValidating captions from: {captions_path}")
            try:
                self.content_types, self.products = self.captions_validator.validate(
                    captions_path, separator=separator
                )
                logger.trace("\nAfter captions validation:")
                logger.debug(f"{self.content_types=}")
                logger.debug(f"{self.products=}")
                # Pass content types to path validator before folder validation
                self.path_validator.content_types = self.content_types

                # Now validate the folder structure with known content types
                if not self.path_validator.folder_validation(self.base_path):
                    self.errors.extend(self.path_validator.errors)
                    self.warnings.extend(self.path_validator.warnings)
                    return False

                self.errors.extend(self.captions_validator.errors)
                self.warnings.extend(self.captions_validator.warnings)

            except ValueError as e:
                self.errors.extend(self.captions_validator.errors)
                return False

            # After successful validation of content structure
            if self.base_path:
                self.metadata = Metadata(
                    self.base_path, strict=self.strict if strict is None else strict
                )
                metadata_valid = self.metadata.load(
                    content_types=self.content_types,
                    products=self.products,
                    strict=self.strict if strict is None else strict,
                )

                # Silently collect metadata messages
                self.warnings.extend(self.metadata.warnings)
                self.errors.extend(self.metadata.errors)

                if not metadata_valid:
                    return False

                self.metadata_editor = MetadataEditor(self.metadata.data)

            self.raise_if_errors()
            return True

        except Exception as e:
            self.add_error(str(e))
            return False
