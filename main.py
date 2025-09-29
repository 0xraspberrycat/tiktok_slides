import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Literal, Optional, Union

from config.logging import TESTING_LEVEL, TRACE_LEVEL, logger, setup_slide_logger
from content_manager.content_handler import ContentHandler
from content_manager.settings.settings_handler import Settings
from content_manager.captions import CaptionsHelper
from generation.generate import Generator
from tools.generation_report import report



class SlideManager:
    """Main manager for slide content and generation"""

    def __init__(self, log_level: str = "INFO"):
        """Initialize manager

        Args:
            log_level: Initial log level (TRACE, DEBUG, INFO, TESTING, WARNING, ERROR, CRITICAL)
                      Defaults to INFO for production use
        """
        self.base_path = None
        self.content_handler = ContentHandler(strict=True)
        self.settings = Settings()  # TODO add this so we can add & change settings
        self.logger = setup_slide_logger(log_level)
        self.metadata = None  # Initialize as None
        self.separator = ","  # Default separator

    def help(self):
        """prints some useful info and helper function."""

        prints = """
useful functions: 
bulk changing settings / want to see the products & content types :: print_content_structure
print issues with metadat and warnings :: metadata.print_warnings 

"""
        print(prints)

    def _reset_state(self):
            """Reset all state to ensure fresh validation"""
            self.content_handler = ContentHandler(strict=True)
            self.content_handler.separator = self.separator
            self.metadata = None

    def load(self, path: Union[Path, str], strict: bool = True, separator: str = ",") -> bool:
        """Load and validate content from the specified path

        Args:
            path: Path to content directory
            separator: CSV separator character
            strict: If True, treats warnings as errors (default: True)

        Returns:
            bool: True if validation passes, False if errors/warnings exist
        """
        logger.debug(f"Loading with separator: {separator}")
        self.separator = separator
        self.base_path = Path(path)
        
        # Reset state before loading
        self._reset_state()

        # Run validation
        is_valid = self.content_handler.validate(
            path=self.base_path, separator=separator, strict=strict
        )

        if is_valid:
            self.settings.set_data(metadata=self.content_handler.metadata)
            self.metadata = self.content_handler.metadata

        # Always show validation results
        if self.content_handler.metadata and self.content_handler.metadata.warnings:
            print("\nWarnings:")
            for warning in self.content_handler.metadata.warnings:
                print(f"  - {warning}")
        else:
            print("\nNo warnings")

        if self.content_handler.errors:
            print("\nErrors:")
            for error in self.content_handler.errors:
                print(f"  - {error}")
        else:
            print("No errors")

        if is_valid:
            captions_path = self.base_path / "captions.csv"
            self.captions = CaptionsHelper.get_captions(
                captions_path,
                content_types=self.content_handler.content_types,
                products=self.content_handler.products,
                separator=self.separator
            )

        return is_valid
    
    def validate(self, strict: bool = True) -> bool:
        """Validate all content and settings

        Args:
            strict: If True, treats warnings as errors (default: True)

        Returns:
            bool: True if validation passes, False if errors/warnings exist
        """
        if not self.base_path:
            raise ValueError("No path set - please call load() first")

        # Reset state before validating
        self._reset_state()
            
        logger.debug(f"Validating with separator: {self.separator}")
        is_valid = self.content_handler.validate(
            path=self.base_path, 
            strict=strict,
            separator=self.separator
        )

        # If validation passed, restore metadata (similar to load())
        if is_valid:
            self.settings.set_data(metadata=self.content_handler.metadata)
            self.metadata = self.content_handler.metadata

        # Show ALL validation messages as errors in strict mode
        if strict:
            # Combine messages but remove duplicates using a set
            all_messages = list(
                set(self.content_handler.errors + self.content_handler.warnings)
            )
            if all_messages:
                print("\nValidation failed with errors:")
                for msg in sorted(all_messages):  # Sort for consistent output
                    print(f"  - {msg}")
        else:
            if self.content_handler.warnings:
                print("\nValidation warnings:")
                for warning in sorted(self.content_handler.warnings):
                    print(f"  - {warning}")
            if self.content_handler.errors:
                print("\nValidation failed with errors:")
                for error in sorted(self.content_handler.errors):
                    print(f"  - {error}")

        return is_valid

    def open_interface(self):
        """Open the text slide interface"""
        if not self.base_path:
            raise ValueError("No path set - please call load() first")
            
        logger.debug(f"Opening interface - validating with separator: {self.separator}")
        if not self.validate(strict=False):  # Uses stored separator
            raise ValueError("cant load interface bc validation is False")

        try:
            # Initialize Streamlit through subprocess to avoid context warnings
            interface_path = Path(__file__).parent / "interface" / "main.py"
            logger.debug(f"Launching Streamlit with interface at: {interface_path}")

            # Build and print command before executing
            cmd = [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(interface_path),
                "--",
                str(self.base_path),  # Pass base path
                str(self.content_handler.content_types),  # Pass content types
                str(self.content_handler.products),  # Pass products
                str(self.separator),  # Pass separator
            ]

            print(cmd)

            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Error launching interface: {e}")
            raise

    @report
    def generate(self, variations: int = 2, allow_all_duplicates: bool = False, 
                    output_path: Optional[Union[Path, str]] = None) -> str:
            """Generate slides with validation
            
            Args:
                variations: Number of variations to generate
                allow_all_duplicates: If True, allows 'all' product to be used even for products with prevent_duplicates=true
                output_path: Optional custom output path. If invalid or None, uses default path
                
            Returns:
                str: Path where images were generated
            """
            if not self.validate(strict=True):
                logger.error("Validation failed, stopping generation")
                return None
                
            logger.info("Starting generation after successful validation")
            
            generator = Generator(self.base_path, self.metadata, self.captions)
            generator.generate(variations, allow_all_duplicates, output_path)
            
            # Return the actual output path used
            return str(output_path or "output")


    def print_content_structure(
        self, format: Literal["raw", "standard"] = "raw"
    ) -> None:
        """Print current content structure showing content types and products."""

        if not self.base_path:
            raise ValueError("No content loaded - please call load() first")

        # Get the products structure
        products = self.content_handler.captions_validator.products

        if format == "raw":
            print(json.dumps(products, indent=2))
        else:
            print("\n=== Content Structure ===")
            for content_type, product_list in products.items():
                print(f"\n{content_type}:")
                for product in sorted(product_list):
                    print(f"  - {product}")
            print("\n=====================")

        return products
