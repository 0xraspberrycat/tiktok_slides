import json
from pathlib import Path
from typing import Dict, List, Literal, Optional

from .metadata_editor import MetadataEditor
from .metadata_generator import MetadataGenerator
from .metadata_validator import MetadataValidator


class Metadata:
    def __init__(self, base_path: Path, strict: bool = False):
        """Initialize metadata handler
        Args:
            base_path: Base path for metadata file
            strict: If True, use strict validation (default: True)
        """

        self.base_path = base_path
        self.strict = strict
        self.data = {}
        self.warnings = []
        self.metadata_editor = None
        self.errors = []

    def print_warnings(self):
        """Print current warnings with a fancy separator."""
        if not self.warnings:
            return

        print("\n" + "=" * 50 + " WARNINGS " + "=" * 50)
        for warning in self.warnings:
            print(f"• {warning}")
        print("=" * 110 + "\n")

    def load(
        self,
        content_types: List[str],
        products: Dict[str, List[str]],
        strict: bool = True,
    ) -> bool:
        """Load metadata from file or generate new.

        Load metadata, generating new if needed or validating existing.

        Flow:
        1. Check if metadata.json exists
           - If not, generate new metadata
        2. If exists:
           - Load and validate
           - If validation fails, raise error with instructions

        Args:
            content_types: List of valid content types
            products: Product configurations by content type
            strict: Whether to use strict validation

        Returns:
            bool: True if metadata loaded successfully"""

        path = self.base_path / "metadata.json"

        if path.exists():
            try:
                with open(path) as f:
                    self.data = json.load(f)

                # print(f"Loaded metadata: {self.data}")  # Debug print

                # Validate loaded data
                validator = MetadataValidator(
                    base_path=self.base_path,
                    strict=self.strict if strict is None else strict,
                )
                validation_result = validator.validate(
                    self.data, content_types, products
                )

                print(f"Validation result: {validation_result}")  # Debug print

                # ALWAYS collect warnings and errors, regardless of validation result
                self.warnings.extend(validator.warnings)
                self.errors.extend(validator.errors)

                if not validation_result:
                    print("Validation failed")  # Debug print
                    return False

                self.metadata_editor = MetadataEditor(self.data)
                return True

            except Exception as e:
                import traceback

                traceback.print_exc()
                return False
        else:
            try:
                self.generate(content_types, products)
                return True
            except Exception as e:
                print(f"Error during generation: {str(e)}")
                return False

    def generate(
        self, content_types: List[str], products: Dict[str, List[str]]
    ) -> None:
        """Generate new metadata from scratch.

        Flow:
        1. Create new metadata using generator
        2. Validate JSON serialization
        3. Save to disk

        Args:
            content_types: List of valid content types
            products: Product configurations by content type

        Raises:
            ValueError: If generation fails or produces invalid JSON
        """
        # Convert sets to lists before generation
        print(f"{content_types=}")
        print(f"{products=}")
        content_types_list = sorted(list(content_types))
        products_dict = {ct: sorted(list(set(prods))) for ct, prods in products.items()}

        generator = MetadataGenerator(self.base_path, content_types_list, products_dict)
        self.data = generator.generate()
        # Initialize editor after generation
        self.metadata_editor = MetadataEditor(self.data)
        self.save()

    def save(self) -> None:
        """Save current metadata to disk.

        Flow:
        1. Validate JSON serialization
        2. Write to disk with pretty printing

        Raises:
            ValueError: If data is not JSON serializable
            OSError: If file cannot be written
        """
        path = self.base_path / "metadata.json"
        try:
            # Verify JSON serialization first
            json.dumps(self.data)

            with open(path, "w") as f:
                json.dump(self.data, f, indent=2)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Metadata is not JSON serializable: {e}")
        except OSError as e:
            raise OSError(f"Failed to save metadata file: {e}")
