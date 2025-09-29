import csv
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Literal, Set, Tuple

from PIL import Image

from config.logging import logger


class ContentLoader:
    def __init__(self):
        self.metadata = Metadata()
        self.base_path = None
        self.content_types = []
        self.products = {}

    def load(self, base_path: Path, separator: str = ",") -> bool:
        """Load and validate content structure"""
        self.base_path = base_path
        metadata_path = base_path / "metadata.json"
        captions_csv_path = base_path / "captions.csv"

        # First validate captions and structure
        self._load_captions(captions_csv_path, separator=separator)
        self._validate_folder_structure()

        # Scan images first to have info ready
        image_info = self.scan_images()

        # Generate or load metadata
        if not metadata_path.exists() or metadata_path.stat().st_size == 0:
            logger.info("Generating new metadata file")
            self.metadata.generate_new_metadata(
                base_path, self.content_types, self.products, image_info
            )
        else:
            try:
                if not self.metadata.load(metadata_path):
                    logger.info("Failed to load metadata, regenerating")
                    self.metadata.generate_new_metadata(
                        base_path, self.content_types, self.products, image_info
                    )
            except ValueError as e:
                logger.error(f"Invalid metadata, regenerating: {str(e)}")
                self.metadata.generate_new_metadata(
                    base_path, self.content_types, self.products, image_info
                )

        return True

    def _load_captions(
        self, captions_path: Path, separator: str = ",", strict: bool = False
    ) -> None:
        """Load and validate captions.csv format"""
        validator = CaptionValidator()

        try:
            self.content_types, self.products = validator.validate(
                captions_path, separator=separator, strict=strict
            )
            logger.info(f"Loaded content types: {self.content_types}")
            logger.info(f"Loaded products: {self.products}")
        except Exception as e:
            logger.error(f"Error loading captions.csv: {str(e)}")
            raise

    def validate_captions(self, strict: bool = False) -> List[str]:
        """Validate captions structure and content

        Args:
            strict: If True, missing products are treated as errors

        Returns:
            List[str]: List of validation warnings
        """
        warnings = []

        try:
            with open(self.base_path / "captions.csv", "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                for row_num, row in enumerate(reader, start=2):
                    for content_type in self.content_types:
                        content = row.get(content_type, "").strip()
                        product = row.get(f"product_{content_type}", "").strip()

                        if content and not product:
                            warnings.append(
                                f"Row {row_num}: Content without product for {content_type}"
                            )

            return warnings

        except Exception as e:
            logger.error(f"Caption validation failed: {str(e)}")
            raise

    def validate_metadata(self, strict: bool = False) -> List[str]:
        """Validate metadata structure and content

        Args:
            strict: If True, treats incomplete metadata as error

        Returns:
            List[str]: List of validation warnings
        """
        return self.metadata.validate_against_captions(
            content_types=self.content_types, products=self.products, strict=strict
        )

    def get_validation_summary(self) -> str:
        summary = []

        if self.warnings["missing_products"]:
            products_needed = {}
            for row, content in self.warnings["missing_products"]:
                if content not in products_needed:
                    products_needed[content] = []
                products_needed[content].append(row)

            summary.append("\nAction needed: Add products for these content types:")
            for content, rows in products_needed.items():
                summary.append(f"- {content}: rows {', '.join(map(str, rows))}")

        return "\n".join(summary)

    def get_content_structure(
        self, format: Literal["simple", "detailed", "raw"] = "simple"
    ) -> Dict[str, List[str]]:
        """
        Always returns the content map dict and prints formatted output

        Args:
            format: Output format
                - simple: Basic bullet point structure
                - detailed: With counts and settings status
                - raw: Raw dictionary format. Use this to help you when you want to bulk_apply settings.
        """
        content_map = self.metadata.get_content_map()

        if format == "raw":
            # Format for easy copy-paste into settings application
            formatted_map = {}
            for content_type, products in content_map.items():
                formatted_map[content_type] = products
            print(json.dumps(formatted_map, indent=4))

        elif format == "detailed":
            output = []
            for content_type, products in content_map.items():
                output.append(f"\n{content_type.upper()}")

                # Show image stats
                images = [
                    img
                    for img in self.metadata["images"].values()
                    if img["content_type"] == content_type
                ]
                custom = [img for img in images if img["settings_source"] == "custom"]

                output.append(f"\n  Images: {len(images)}")
                output.append(f"  - With custom settings: {len(custom)}")

            print("\n".join(output))

        else:  # simple
            for content_type, products in content_map.items():
                print(f"\n{content_type}")
                for product in sorted(products):
                    print(f"  • {product}")

        return content_map

    def validate_metadata_structure(self) -> List[str]:
        """Validate metadata structure and content"""
        warnings = []

        # Track images by folder for better error messages
        images_by_folder = {}
        duplicate_locations = {}

        for content_type in self.content_types:
            folder = self.base_path / content_type
            if not folder.exists():
                warnings.append(f"Content folder missing: {content_type}")
                continue

            images = [
                f
                for f in folder.glob("*")
                if f.suffix.lower() in {".jpg", ".jpeg", ".png"}
            ]
            image_names = [
                f.name.lower() for f in images
            ]  # Case-insensitive comparison
            images_by_folder[content_type] = image_names

            # Track duplicates with their locations
            for img_name in image_names:
                if img_name not in duplicate_locations:
                    duplicate_locations[img_name] = []
                duplicate_locations[img_name].append(content_type)

        # Check for duplicates with locations
        duplicates = {
            img: locations
            for img, locations in duplicate_locations.items()
            if len(locations) > 1
        }

        if duplicates:
            error_msg = "Duplicate image names found (case-insensitive):\n"
            for img, locations in duplicates.items():
                error_msg += f"- {img} found in: {', '.join(locations)}\n"
            raise ValueError(error_msg)

        # Check for orphaned metadata entries
        for img_name in self.metadata["images"].keys():
            if img_name.lower() not in [
                name.lower() for names in images_by_folder.values() for name in names
            ]:
                warnings.append(f"Metadata exists for missing image: {img_name}")

        # Check for images without metadata
        all_images = [name for names in images_by_folder.values() for name in names]
        for img_name in all_images:
            if img_name not in self.metadata["images"]:
                warnings.append(f"Image exists without metadata: {img_name}")

        return warnings

    def _validate_folder_structure(self) -> List[str]:
        """Validate folder structure matches content types"""
        warnings = []

        # Check all required folders exist
        for content_type in set(self.content_types):
            folder = self.base_path / content_type
            if not folder.exists():
                warnings.append(f"Missing folder for content type: {content_type}")
                continue

            # Check folder is readable
            if not folder.is_dir() or not os.access(folder, os.R_OK):
                warnings.append(f"Cannot access folder: {content_type}")

        return warnings

    def _check_image_similarity(self, image_paths: List[Path]) -> None:
        """Check for similar images using perceptual hashing"""
        import imagehash
        from PIL import Image

        hash_dict = {}
        for path in image_paths:
            try:
                with Image.open(path) as img:
                    # Use average_hash for quick comparison
                    img_hash = str(imagehash.average_hash(img))
                    if img_hash in hash_dict:
                        raise ValueError(
                            f"Similar images detected:\n"
                            f"- {path.name}\n"
                            f"- {hash_dict[img_hash].name}"
                        )
                    hash_dict[img_hash] = path
            except Exception as e:
                logger.warning(f"Could not check similarity for {path}: {str(e)}")

    def validate_structure(self) -> List[str]:
        """Validate content structure matches captions"""
        warnings = []

        # Get content types from captions
        caption_content_types = set(self.content_types)

        # Check folders exist for all content types
        for content_type in caption_content_types:
            folder = self.base_path / content_type
            if not folder.exists():
                warnings.append(f"Missing folder for content type: {content_type}")

        # Check for extra folders not in captions
        existing_folders = {f.name for f in self.base_path.glob("*") if f.is_dir()}
        extra_folders = existing_folders - caption_content_types
        if extra_folders:
            warnings.append(
                f"Found folders without caption content: {', '.join(extra_folders)}"
            )

        return warnings

    def scan_images(self) -> Dict[str, List[Tuple[str, Path, Dict]]]:
        """Scan all content folders for images and return their info with dimensions"""
        from PIL import Image

        image_info = {}

        for content_type in self.content_types:
            folder = self.base_path / content_type
            if not folder.exists():
                logger.warning(f"Content folder missing: {content_type}")
                continue

            image_info[content_type] = []
            images = [
                f
                for f in folder.glob("*")
                if f.suffix.lower() in {".jpg", ".jpeg", ".png"}
            ]

            for img_path in images:
                try:
                    with Image.open(img_path) as img:
                        width, height = img.size
                        image_info[content_type].append(
                            (
                                img_path.name,
                                img_path,
                                {
                                    "content_type": content_type,
                                    "dimensions": {
                                        "width": width,
                                        "height": height,
                                        "aspect_ratio": round(width / height, 3),
                                    },
                                },
                            )
                        )
                except Exception as e:
                    logger.warning(
                        f"Could not read dimensions for {img_path}: {str(e)}"
                    )

        return image_info

    def check_duplicates(self) -> None:
        """Check for duplicate and similar images across all content folders"""
        image_info = self.scan_images()

        # Check filename duplicates
        name_locations = {}
        for content_type, images in image_info.items():
            for img_name, path, _ in images:
                if img_name.lower() not in name_locations:
                    name_locations[img_name.lower()] = []
                name_locations[img_name.lower()].append((path, content_type))

        duplicates = {
            name: locations
            for name, locations in name_locations.items()
            if len(locations) > 1
        }

        if duplicates:
            error_msg = "Duplicate image names found (case-insensitive):\n"
            for name, locations in duplicates.items():
                location_str = ", ".join(f"{loc[1]}" for loc in locations)
                error_msg += f"- {name} found in: {location_str}\n"
            raise ValueError(error_msg)

        # Check content similarity
        all_paths = [img[1] for images in image_info.values() for img in images]
        self._check_image_similarity(all_paths)
