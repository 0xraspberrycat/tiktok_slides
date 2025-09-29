import json
from pathlib import Path
from typing import Dict, List, Optional

from config.content_loader import Metadata

from .logging import logger


class SettingsHandler:
    def __init__(self):
        self.metadata = None
        self.metadata_path = None

    def apply_settings(
        self,
        settings: Dict,
        bulk_apply: Optional[Dict[str, List[str]]] = None,
        content_type: Optional[str] = None,
        product: Optional[str] = None,
        confirm_use: bool = False,
        fill_empties: bool = False,
    ) -> None:
        """Apply settings to content types and products

        Args:
            settings: Settings dictionary to apply
            bulk_apply: Dictionary of content_type -> list of products for bulk application
            content_type: Single content type to apply settings to
            product: Single product to apply settings to
            confirm_use: Must be True when applying to all products/content types
            fill_empties: Only apply settings to images without existing settings
        """
        if not self.metadata:
            raise ValueError("No metadata loaded. Call load() first.")

        # Validate settings structure
        if not isinstance(settings, dict):
            raise ValueError("Settings must be a dictionary")

        if "base_settings" not in settings or "text_settings" not in settings:
            raise ValueError("Settings missing required keys")

        if "default_text_type" not in settings["base_settings"]:
            raise ValueError("Settings missing default_text_type")

        default_type = settings["base_settings"]["default_text_type"]
        if default_type not in settings["text_settings"]:
            raise ValueError(f"Missing text settings for type: {default_type}")

        base_settings = settings["text_settings"][default_type]

        # Handle bulk apply case
        if bulk_apply:
            logger.critical(f"Bulk applying settings: {bulk_apply}")
            for content_type, products in bulk_apply.items():
                self.apply_content_type_settings(
                    content_type=content_type,
                    settings=base_settings,
                    products=products,
                    fill_empties=fill_empties,
                )
                # Validate settings were applied
                if not self.validate_settings_applied(content_type, products):
                    raise ValueError(f"Failed to apply settings for {content_type}")
            return

        # Handle single content type/product case
        if content_type:
            self.apply_content_type_settings(
                content_type=content_type,
                settings=base_settings,
                products=[product] if product else None,
                fill_empties=fill_empties,
            )

    def get_content_map(self) -> Dict[str, List[str]]:
        """Get current content type and product mapping"""
        content_map = {}
        for img_name, img_data in self.metadata["images"].items():
            content_type = img_data.get("content_type")
            product = img_data.get("product")

            if content_type:
                if content_type not in content_map:
                    content_map[content_type] = set()
                if product:
                    content_map[content_type].add(product)

        # Convert sets to sorted lists
        return {k: sorted(v) for k, v in content_map.items()}

    def validate_bulk_apply(self, bulk_settings: Dict[str, List[str]]) -> List[str]:
        """Validate that bulk settings were applied correctly"""
        errors = []

        for content_type, products in bulk_settings.items():
            content_settings = self.metadata["settings"]["content_type"].get(
                content_type
            )
            if not content_settings:
                errors.append(f"Settings not applied for content type: {content_type}")
                continue

            # Check product settings
            for product in products:
                if product not in content_settings["products"]:
                    errors.append(
                        f"Settings not applied for product: {content_type}.{product}"
                    )

        return errors

    def _get_target_images(
        self, content_type: Optional[str], product: Optional[str]
    ) -> List[str]:
        """Get target images based on content_type and product filters"""
        target_images = []
        for img_name, img_data in self.metadata["images"].items():
            if "content_type" not in img_data:
                continue

            img_content = img_data["content_type"]
            img_product = img_data.get("product", "")

            # Check if image matches filters
            if (
                content_type
                and content_type.lower() != "all"
                and img_content != content_type
            ):
                continue
            if product and product.lower() != "all" and img_product != product:
                continue

            target_images.append(img_name)

        return target_images

    def apply_content_type_settings(
        self,
        content_type: str,
        settings: Dict,
        products: Optional[List[str]] = None,
        fill_empties: bool = False,
    ) -> None:
        """Apply settings to content type, optionally for specific products

        Args:
            content_type: Content type to apply settings to
            settings: Settings dictionary to apply
            products: Optional list of products to apply settings to
            fill_empties: Only apply settings where none exist
        """
        logger.critical(
            f"Applying settings to content_type: {content_type}, products: {products}"
        )

        if not isinstance(settings, dict):
            raise ValueError("Settings must be a dictionary")

        content_settings = self.metadata["settings"]["content_type"].setdefault(
            content_type, {"products": {}, "all": None}
        )

        if products:
            # Create product key from sorted list
            product_key = "|".join(sorted(products))
            logger.critical(f"Creating product group: {product_key}")
            logger.critical(f"Applying settings: {json.dumps(settings, indent=2)}")

            # Remove these products from any existing groups
            new_product_groups = {}
            for group_key, group_settings in content_settings["products"].items():
                group_products = set(group_key.split("|"))
                remaining_products = group_products - set(products)
                if remaining_products:
                    new_product_groups["|".join(sorted(remaining_products))] = (
                        group_settings
                    )

            # Add new group
            new_product_groups[product_key] = settings
            content_settings["products"] = new_product_groups
        else:
            logger.critical(f"Applying settings to all products in {content_type}")
            logger.critical(f"Settings: {json.dumps(settings, indent=2)}")
            content_settings["all"] = settings

    def validate_settings_applied(
        self, content_type: str, products: Optional[List[str]] = None
    ) -> bool:
        """Validate that settings were properly applied"""
        if content_type not in self.metadata["settings"]["content_type"]:
            logger.error(f"No settings found for content type: {content_type}")
            return False

        content_settings = self.metadata["settings"]["content_type"][content_type]

        if products:
            # Find which product group contains our products
            found_products = set()
            for group_key, group_settings in content_settings["products"].items():
                group_products = set(group_key.split("|"))
                matching_products = set(products) & group_products
                if matching_products:
                    found_products.update(matching_products)
                    if group_settings is None:
                        logger.error(
                            f"Settings are null for product group: {group_key}"
                        )
                        return False

            # Check if all products were found
            missing = set(products) - found_products
            if missing:
                logger.error(f"No settings found for products: {missing}")
                return False
        else:
            if content_settings["all"] is None:
                logger.error(f"All settings are null for content type: {content_type}")
                return False

        return True
