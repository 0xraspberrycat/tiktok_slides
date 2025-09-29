import ast
import json
from pathlib import Path
from typing import Dict, List, Literal, Optional

from config.logging import logger
from content_manager.settings.settings_constants import DEFAULT_TEMPLATE


class MetadataEditor:
    """Handles safe reading and writing of metadata fields"""

    def __init__(self, metadata: Dict):
        self.metadata = metadata

    # Content Types
    def get_content_types(self, filter: Optional[str] = None) -> List[str]:
        """Get all content types or filtered by name"""
        types = self.metadata["content_types"]
        if filter:
            return [ct for ct in types if filter in ct]
        return types

    # Products
    def get_products(self, content_type: Optional[str] = None) -> Dict:
        """Get all products or for specific content type"""
        if content_type:
            return self.metadata["products"].get(content_type, [])
        return self.metadata["products"]

    # Images
    def get_images(
        self, content_type: Optional[str] = None, product: Optional[str] = None
    ) -> Dict[str, Dict]:
        """Get images with optional filtering"""
        images = self.metadata["images"]
        if content_type:
            images = {
                k: v for k, v in images.items() if v["content_type"] == content_type
            }
        if product:
            images = {k: v for k, v in images.items() if v["product"] == product}
        return images

    def edit_image(self, image_name: str, data: Dict) -> None:
        """Update image metadata

        Args:
            image_name: Name of image to update
            data: Dict of fields to update. Can include:
                - product: New product assignment
                - settings_source: Source of settings
                - settings: Settings data
                (dimensions cannot be changed)
        """

        if image_name not in self.metadata["images"]:
            raise ValueError(f"Image {image_name} not found")

        image = self.metadata["images"][image_name]

        # Handle product changes
        if "product" in data:
            content_type = image["content_type"]
            new_product = data["product"]
            old_product = image["product"]

            # Update product counts
            if old_product:
                self._update_product_count(content_type, old_product, increment=False)
            if new_product:
                self._update_product_count(content_type, new_product, increment=True)

            # Handle untagged status
            if new_product is None:
                if image_name not in self.metadata["untagged"]:
                    self.metadata["untagged"].append(image_name)
            else:
                self.metadata["untagged"] = [
                    img for img in self.metadata["untagged"] if img != image_name
                ]

        # Update image data
        image.update(data)

    # Untagged
    def get_untagged(self) -> List[str]:
        """Get list of untagged images"""
        return self.metadata["untagged"]

    def edit_untagged(self, untagged: List[str]) -> None:
        """Update untagged list"""
        self.metadata["untagged"] = untagged

    # Settings
    def get_settings(
        self,
        level: Literal["default", "content_type", "product", "custom"],
        target: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> Dict:
        """Get settings at specified level.

        Args:
            level: Settings level to retrieve
                - default: Get default settings template
                - content_type: Get settings for content type
                - product: Get settings for product (from product groups)
                - custom: Get settings for specific image
            target: Required for content_type, product, and custom levels
                For content_type: content type name
                For product: product name
                For custom: image filename
            content_type: Required when level="product" to specify which content
                type's product settings to check

        Returns:
            Dict containing:
                - settings_source: Level where settings came from
                - settings: The settings dict or None

        Example:
            >>> get_settings("default")
            {
                "settings_source": "default",
                "settings": DEFAULT_SETTINGS  # From settings_constants
            }

            >>> get_settings("content_type", "hook")
            {
                "settings_source": "content_type",
                "settings": {...}  # Content settings from hook.content
            }

            >>> get_settings("product", "magnesium", "hook")
            {
                "settings_source": "product",
                "settings": {...}  # Settings from hook's product group containing magnesium
            }

            >>> get_settings("custom", "image1.png")
            {
                "settings_source": "custom",
                "settings": {...}  # From image metadata
            }
        """
        logger.debug(f"\n=== Metadata editor get_settings Debug ===")
        logger.debug(f"Inputs - level: {level}, target: {target}, content_type: {content_type}")
        if level == "default":
            logger.debug(f"1. Getting default settings from: {DEFAULT_TEMPLATE}")
            try:
                with open(DEFAULT_TEMPLATE) as f:
                    default_settings = json.load(f)
                logger.debug(f"2. Loaded default settings: {default_settings}")
                return {"settings_source": "default", "settings": default_settings}
            except (IOError, json.JSONDecodeError) as e:
                raise ValueError(f"Failed to load default template: {str(e)}")

            return {"settings_source": "default", "settings": default_settings}

        if level == "content_type":
            logger.debug(f"1. Settings dict: {self.metadata['settings']}")
            if not target:
                raise ValueError("specific content_type target required for content_type level")
            if target not in self.metadata["content_types"]:
                raise ValueError(f"Invalid content type: {target}")
            content_settings = self.metadata["settings"].get(target, {})
            logger.debug(f"2. Content type settings: {content_settings}")
            return {
                "settings_source": "content_type",
                "settings": content_settings.get("content"),
            }

        if level == "product":
            logger.debug(f"1. Settings dict: {self.metadata['settings']}")
            if not target:
                raise ValueError("Product name required for product level")
            if not content_type:
                raise ValueError("Content type required for product level settings")

            # Get product settings for the specific content type
            content_settings = self.metadata["settings"].get(content_type, {})
            logger.debug(f"2. Content type settings: {content_settings}")

            # Look for the product in the settings
            # The key will be "[magnesium]" for single product
            single_product_key = f"[{target}]"
            logger.debug(f"3a. Product key: {single_product_key}")
            if single_product_key in content_settings:
                logger.debug(f"3b. Product settings: {content_settings[single_product_key]}")
                return {
                    "settings_source": "product",
                    "settings": content_settings[single_product_key],
                }

            # Look through product groups
            for group_key, settings in content_settings.items():
                if group_key.startswith("[") and group_key.endswith("]"):
                    try:
                        # Parse the group string into a list
                        group_products = group_key.strip("[]").split(", ")
                        if target in group_products:
                            return {"settings_source": "product", "settings": settings}
                    except:
                        continue

            # If no settings found, return None for settings
            return {"settings_source": "product", "settings": None}

        if level == "custom":
            if not target:
                raise ValueError("Image name required for custom level")
            image_data = self.metadata["images"].get(target)
            if not image_data:
                raise ValueError(f"Image {target} not found")
            return {
                "settings_source": image_data.get("settings_source", "custom"),
                "settings": image_data.get("settings"),
            }

    def edit_settings(
        self,
        level: Literal["content_type", "product", "custom"],
        target: str,
        data: Dict,
        content_type: Optional[str] = None,
    ) -> None:
        """Update settings at specified level.

        Args:
            level: Settings level to update
            target: Target to update (content type name, product name, or image name)
            data: Settings data to apply
            content_type: Required when level="product" to specify which content
                type's product settings to update

        Raises:
            ValueError: If content_type missing for product level
            ValueError: If content_type provided for non-product level
            ValueError: If image not found for custom level
        """
        # Validate content_type parameter
        if level == "product" and not content_type:
            raise ValueError("content_type required for product level settings")
        if level != "product" and content_type:
            raise ValueError("content_type should only be provided for product level")

        if level == "content_type":
            # Initialize if not exists
            if target not in self.metadata["settings"]:
                self.metadata["settings"][target] = {}

            # Update only content settings, preserve other keys
            self.metadata["settings"][target]["content"] = data

        elif level == "product":
            # ThiS IS DONE IN SETTINGS HANDLER APPly PRODUCT SETTINGS WHICH
            # IS REALLY BAD DEV WORK BUT IDGAF

            # Product Settings Merging Logic:
            # 1. Check if product exists in any group
            #    - Search all groups in content_type
            #    - Parse "[product1, product2]" strings
            #    - Track current group and settings

            # 2. If found in existing group:
            #    - If settings same as another group -> merge groups
            #    - If settings different -> split from group
            #    - If last product in group -> delete group

            # 3. If not in any group:
            #    - Check if settings match existing group -> join
            #    - If no match -> create new group

            # 4. Always maintain:
            #    - Alphabetical order in groups
            #    - No duplicate settings
            #    - No empty groups
            #    - Valid group string format

            raise NotImplementedError("Product level settings not implemented yet")

        elif level == "custom":
            # Custom Settings Validation:
            # 1. Check image exists
            if target not in self.metadata["images"]:
                raise ValueError(f"Image {target} not found")

            # 2. Validate settings structure (if not None)
            if data is not None:
                # TODO: Add settings structure validation
                # - Check required fields
                # - Validate field types
                # - Verify constraints
                pass

            # 3. Update image metadata
            self.metadata["images"][target].update(
                {"settings_source": "custom", "settings": data}
            )

            # 4. Maintain consistency:
            # - Update any related metadata
            # - Clear cached values if any
            # - Log changes if needed

    def move_untagged_image(self, image_name: str, target_content_type: str) -> None:
        """Move image from untagged to a content type folder."""
        logger.debug(
            f"\nStarting move operation for {image_name} to {target_content_type}"
        )

        try:
            # Validate inputs
            if image_name not in self.metadata["untagged"]:
                raise ValueError(f"Image {image_name} not in untagged list")
            logger.debug("✓ Image found in untagged list")

            if target_content_type not in self.metadata["content_types"]:
                raise ValueError(f"Invalid content type: {target_content_type}")
            logger.debug("✓ Valid content type")

            # Get correct paths from structure
            target_path = Path(self.metadata["structure"][target_content_type]["path"])
            base_path = target_path.parent
            logger.debug(
                f"✓ Paths resolved: \n  From: {base_path}\n  To: {target_path}"
            )

            # Move the file
            src_path = base_path / image_name
            dest_path = target_path / image_name

            if not src_path.exists():
                raise ValueError(f"Source file not found: {src_path}")
            logger.debug("✓ Source file exists")

            if dest_path.exists():
                raise ValueError(f"Destination file already exists: {dest_path}")
            logger.debug("✓ Destination path clear")

            src_path.rename(dest_path)
            logger.debug(f"✓ File moved successfully")

            # Update structure (maintaining sort)
            structure = self.metadata["structure"][target_content_type]
            structure["images"].append(image_name)
            structure["images"].sort()  # Sort images in structure
            logger.debug(f"✓ Structure updated and sorted")

            # Generate and add image metadata (maintaining sort)
            from PIL import Image  # type: ignore 

            with Image.open(dest_path) as img:
                width, height = img.size
            logger.debug(f"✓ Image dimensions read: {width}x{height}")

            # Add to images and resort entire images dict
            self.metadata["images"][image_name] = {
                "content_type": target_content_type,
                "dimensions": {"width": width, "height": height},
                "product": None,
                "settings_source": "default",
                "settings": None,
            }
            # Resort images dictionary
            self.metadata["images"] = dict(sorted(self.metadata["images"].items()))
            logger.debug(f"✓ Image metadata generated and sorted")

            # Remove from untagged and sort
            self.metadata["untagged"].remove(image_name)
            self.metadata["untagged"].sort()
            logger.debug(f"✓ Removed from untagged list and sorted")

            # Save changes to disk
            path = (
                Path(self.metadata["structure"][target_content_type]["path"]).parent
                / "metadata.json"
            )
            with open(path, "w") as f:
                json.dump(self.metadata, f, indent=2)
            logger.debug("✓ Changes saved to metadata.json")
            logger.debug("\nMove operation completed successfully!")

        except Exception as e:
            logger.debug("\n❌ Error during move operation!")
            raise ValueError(f"Failed to move image: {str(e)}")

    def update_image_product(
        self, image_name: str, content_type: str, new_product: str
    ):
        """Update product assignment for an image.

        Args:
            image_name: Name of image to update
            content_type: Content type of image
            new_product: Product to assign

        Raises:
            ValueError: If image doesn't exist or product invalid for content type
        """
        # 1. Basic validation
        if image_name not in self.metadata["images"]:
            raise ValueError(f"Image {image_name} not found")

        # Get the ACTUAL content type from the image data
        actual_content_type = self.metadata["images"][image_name]["content_type"]
        
        # Validate against the ACTUAL content type, not the passed one
        valid_products = {p["name"] for p in self.metadata["products"][actual_content_type]}
        if new_product not in valid_products:
            raise ValueError(f"Invalid product '{new_product}' for content type '{actual_content_type}'. Valid products are: {valid_products}")

        # 2. Handle product counts
        old_product = self.metadata["images"][image_name]["product"]
        if old_product:  # If there was a previous product, decrease its count
            self._update_product_count(content_type, old_product, increment=False)
        self._update_product_count(content_type, new_product, increment=True)

        # 3. Update product
        self.metadata["images"][image_name]["product"] = new_product

    def _update_product_count(self, content_type: str, product: str, increment: bool):
        """Update the current count for a product.

        Args:
            content_type: Content type of the product
            product: Product name to update
            increment: True to increase count, False to decrease
        """
        for prod in self.metadata["products"][content_type]:
            if prod["name"] == product:
                if "current_count" not in prod:
                    prod["current_count"] = 0
                prod["current_count"] += 1 if increment else -1
                break


