from pathlib import Path
from typing import Dict, List, Optional, Set
from collections import defaultdict

from content_manager.settings.settings_validator import SettingsValidator
from content_manager.captions import CaptionsHelper
from config.logging import logger


class MetadataValidator:
    # Define expected structure and order
    REQUIRED_KEYS_ORDER = [
        "content_types",
        "products",
        "structure",
        "images",
        "untagged",
        "settings",
    ]

    def __init__(self, base_path: Path, strict: bool = True):
        self.strict = strict
        self.errors = []
        self.warnings = []
        self.settings_validator = SettingsValidator()
        self.base_path = base_path

    def validate(
        self, data: Dict, content_types: List[str], products: Dict[str, List[Dict]]
    ) -> bool:
        """Validate metadata structure and content."""
        self.errors.clear()
        self.warnings.clear()
        self.seen_warnings = set()

        # Check keys order - this is a hard requirement
        if list(data.keys()) != self.REQUIRED_KEYS_ORDER:
            self.errors.append(
                f"Metadata keys are not in correct order. Expected: {self.REQUIRED_KEYS_ORDER}"
            )
            return False

        # Run all validations to collect all warnings/errors
        validators = [
            (self._validate_content_types, data, content_types),
            (self._validate_products, data, products),
            (self._validate_structure, data),
            (self._validate_images, data),
            (self._validate_untagged, data),
            (self._validate_settings, data),
            (self._validate_product_counts, data)
        ]

        valid = True
        for validator, *args in validators:
            if not validator(*args):
                valid = False
                if self.strict:  # Exit early in strict mode if any validator fails
                    return False

        # If there are only warnings and we're in strict mode, fail
        if self.strict and self.warnings:
            self.errors.extend(self.warnings)
            return False

        # If there are errors, fail regardless of strict mode
        if not valid:
            return False

        return True

    def _validate_content_types(self, data: Dict, expected_types: List[str]) -> bool:
        """Validate content_types section."""
        types = data.get("content_types", [])

        if not isinstance(types, list):
            self.errors.append("content_types must be a list")
            return False

        if set(types) != set(expected_types):
            self.errors.append(
                f"Content types mismatch. Found: {types}, Expected: {expected_types}"
            )
            return False

        return True

    def _validate_products(
        self, data: Dict, expected_products: Dict[str, List[str]]
    ) -> bool:
        """Validate products section.

        Args:
            data: Current metadata
            expected_products: Products from captions.csv as {content_type: [product_names]}
        """
        # Get current min_occurrences from captions
        captions_path = self.base_path / "captions.csv"
        min_occurrences = CaptionsHelper.get_product_min_occurrences(captions_path)
        products = data.get("products", {})

        if not isinstance(products, dict):
            self.errors.append("products must be a dictionary")
            return False

        # First check content types match
        if set(products.keys()) != set(expected_products.keys()):
            self.errors.append(
                f"Product content types mismatch. Found: {list(products.keys())}, "
                f"Expected: {list(expected_products.keys())}"
            )
            return False

        # Then validate each content type's products
        for ct, prods in products.items():
            if not isinstance(prods, list):
                self.errors.append(f"Products for {ct} must be a list")
                return False

            # Get expected product names for this content type
            expected_names = set(
                expected_products[ct]
            )  # Now just use the list directly
            found_names = set()

            # Validate each product
            for prod in prods:
                if not isinstance(prod, dict):
                    self.errors.append(f"Product {prod} in {ct} must be a dictionary")
                    return False

                if "name" not in prod:
                    self.errors.append(f"Product in {ct} missing 'name' field")
                    return False

                if "prevent_duplicates" not in prod:
                    self.errors.append(
                        f"Product {prod['name']} in {ct} missing 'prevent_duplicates' field"
                    )
                    return False

                # Validate product name exists in expected products
                if prod["name"] not in expected_names:
                    self.errors.append(
                        f"Invalid product '{prod['name']}' in {ct}. "
                        f"Valid products are: {sorted(expected_names)}"
                    )
                    return False

                found_names.add(prod["name"])

            # Check for missing products
            missing = expected_names - found_names
            if missing:
                self.errors.append(f"Missing products in {ct}: {sorted(missing)}")
                return False

            # Check for extra products
            extra = found_names - expected_names
            if extra:
                self.errors.append(f"Unexpected products in {ct}: {sorted(extra)}")
                return False

        # After validating basic structure, check image counts for products
        images = data.get("images", {})

        # Count product usage in images AND collect missing product warnings
        product_counts = {ct: {} for ct in products.keys()}

        for img_name, img_data in images.items():
            ct = img_data["content_type"]
            prod = img_data["product"]
            if prod:  # Only count if product is assigned
                product_counts[ct][prod] = product_counts[ct].get(prod, 0) + 1
            else:
                # Get valid products for this content type
                valid_products = [p["name"] for p in data["products"][ct]]
                # Create warning with valid products list
                # all is always a valid product, but it doesn't have to exist in the captions. 
                
                # Reorder products: 'all' first, then rest alphabetically
                if "all" in valid_products:
                    valid_products.remove("all")
                    valid_products.sort()  # Sort remaining products
                    valid_products.insert(0, "all")  # Put 'all' back at start
                else:
                    valid_products.sort()  # Just sort if no 'all'
                
                # Create warning with properly ordered products list
                warning_key = f"missing_product_{img_name}"
                msg = f"Image {img_name} has no product assigned. Valid products: {valid_products}"
                
                if self.strict:
                    self.errors.append(msg)
                else:
                    self.add_warning(msg, warning_key)

        # Check counts against min_occurrences for products with prevent_duplicates
        for ct, prods in products.items():
            for prod in prods:
                if prod["prevent_duplicates"] and prod["min_occurrences"] > 0:
                    count = product_counts[ct].get(prod["name"], 0)
                    if count < prod["min_occurrences"]:
                        msg = (
                            f"Product '{prod['name']}' in {ct} requires at least "
                            f"{prod['min_occurrences']} images (has {count})"
                        )
                        if self.strict:
                            self.errors.append(msg)
                            return False
                        else:
                            self.add_warning(msg)

        return True

    def _validate_structure(self, data: Dict) -> bool:
        """Validate structure section."""
        structure = data.get("structure", {})

        if not isinstance(structure, dict):
            self.errors.append("structure must be a dictionary")
            return False

        for ct, info in structure.items():
            if not isinstance(info, dict):
                self.errors.append(f"Structure for {ct} must be a dictionary")
                return False

            if "path" not in info or "images" not in info:
                self.errors.append(f"Structure for {ct} missing required fields")
                return False

            # Verify path exists
            if not Path(info["path"]).exists():
                self.errors.append(f"Path {info['path']} for {ct} does not exist")
                return False

            # Verify images exist in path
            for img in info["images"]:
                if not (Path(info["path"]) / img).exists():
                    self.errors.append(f"Image {img} not found in {info['path']}")
                    return False

        return True

    def _validate_images(self, data: Dict) -> bool:
        """Validate images section with comprehensive checks."""
        images = data.get("images", {})

        # Validate images are sorted alphabetically
        image_names = list(images.keys())
        if image_names != sorted(image_names):
            self.errors.append("Images must be sorted alphabetically")
            return False

        for img_name, img_data in sorted(images.items()):
            # 1. Basic field validation
            required_fields = [
                "content_type",
                "dimensions",
                "product",
                "settings_source",
                "settings",
            ]
            for field in required_fields:
                if field not in img_data:
                    self.errors.append(
                        f"Image {img_name} missing required field: {field}"
                    )
                    return False

            # 2. Content type folder validation
            content_type = img_data["content_type"]
            if content_type not in data["structure"]:
                self.errors.append(
                    f"Image {img_name} has invalid content_type: {content_type}"
                )
                return False

            # Check if image is actually in the specified content folder
            if img_name not in data["structure"][content_type]["images"]:
                self.errors.append(
                    f"Image {img_name} claims to be in {content_type} folder but isn't found there"
                )
                return False

            # 3. Dimensions validation
            dimensions = img_data.get("dimensions", {})
            if not dimensions:
                self.errors.append(f"Image {img_name} has no dimensions")
                return False

            if "width" not in dimensions or "height" not in dimensions:
                self.errors.append(f"Image {img_name} has invalid dimensions structure")
                return False

            # Verify dimensions match actual image
            img_path = Path(data["structure"][content_type]["path"]) / img_name
            if img_path.exists():
                try:
                    from PIL import Image # type: ignore

                    with Image.open(img_path) as img:
                        actual_width, actual_height = img.size
                        if (
                            actual_width != dimensions["width"]
                            or actual_height != dimensions["height"]
                        ):
                            self.errors.append(
                                f"Image {img_name} dimensions mismatch: "
                                f"stored: {dimensions['width']}x{dimensions['height']}, "
                                f"actual: {actual_width}x{actual_height}"
                            )
                            return False
                except Exception as e:
                    self.errors.append(
                        f"Failed to verify dimensions for {img_name}: {str(e)}"
                    )
                    return False

            # 4. Settings validation
            settings_source = img_data["settings_source"]
            settings = img_data["settings"]

            # Define valid settings sources
            valid_sources = ["default", "custom", "product", "content"]
            if settings_source not in valid_sources:
                msg = f"Image {img_name} has invalid settings_source: {settings_source}"
                if self.strict:
                    self.errors.append(msg)
                    return False
                else:
                    self.add_warning(msg)

            # Handle settings validation based on source
            if settings_source == "custom":
                if settings is None:
                    msg = f"Image {img_name} has custom settings_source but settings are null"
                    if self.strict:
                        self.errors.append(msg)
                        return False
                    else:
                        self.add_warning(msg)
                # If settings exist, they're valid
                continue

            elif settings_source == "content":
                # Get content settings for this content type
                if content_type not in data["settings"]:
                    self.errors.append(f"No settings found for content type: {content_type}")
                    return False
                    
                content_settings = data["settings"][content_type].get("content")
                if content_settings is None:
                    if self.strict:
                        self.errors.append(
                            f"Image {img_name} uses content-level settings but none defined for {content_type}"
                        )
                        return False
                    else:
                        self.add_warning(
                            f"Image {img_name} will use default settings as no content-level settings defined"
                        )
                else:
                    # Validate content settings
                    if not self.settings_validator.validate_settings(content_settings):
                        self.errors.extend(
                            [
                                f"Image {img_name} content settings: {e}"
                                for e in self.settings_validator.errors
                            ]
                        )
                        return False

            elif settings_source == "product":
                # Get product settings
                product = img_data["product"]
                product_settings = None
                # Look through product groups to find matching settings
                for group, group_settings in data["settings"][content_type].items():
                    if group != "content":  # Skip content settings
                        products = {p.strip() for p in group[1:-1].split(",")}
                        if product in products:
                            product_settings = group_settings
                            break

                if product_settings is None:
                    if self.strict:
                        self.errors.append(
                            f"Image {img_name} uses product-level settings but none found for {product}"
                        )
                        return False
                    else:
                        self.add_warning(
                            f"Image {img_name} will use default settings as no product settings found"
                        )
                else:
                    # Validate product settings
                    if not self.settings_validator.validate_settings(product_settings):
                        self.errors.extend(
                            [
                                f"Image {img_name} product settings: {e}"
                                for e in self.settings_validator.errors
                            ]
                        )
                        return False
            elif settings_source == "default":
                if settings is not None:
                    self.errors.append(
                        f"Image {img_name} has default settings_source but has non-null settings"
                    )
                    return False

            # 5. Product validation
            if img_data["product"] is None:
                valid_products = [p["name"] for p in data["products"][content_type]]
                # Create a unique warning key for this specific image
                warning_key = f"missing_product_{img_name}"
                msg = f"Image {img_name} has no product assigned. Valid products: ['all', {valid_products}]"
                if self.strict:
                    self.errors.append(msg)
                    return False
                else:
                    self.add_warning(msg, warning_key)
            elif content_type in data["products"]:
                # Special case: 'all' is always valid
                if img_data["product"] == "all":
                    continue
                    
                valid_products = [p["name"] for p in data["products"][content_type]]
                if img_data["product"] not in valid_products:
                    self.errors.append(
                        f"Image {img_name} has invalid product: {img_data['product']}. "
                        f"Valid products: {sorted(['all'] + valid_products)}"
                    )
                    return False

        return True

    def _validate_untagged(self, data: Dict) -> bool:
        """Validate untagged section."""
        untagged = data.get("untagged", [])

        if not isinstance(untagged, list):
            self.errors.append("untagged must be a list")
            return False

        # Check for duplicates
        if len(untagged) != len(set(untagged)):
            self.errors.append("Duplicate entries found in untagged list")
            return False

        # Verify all untagged images exist in base folder
        base_path = Path(data["structure"][data["content_types"][0]]["path"]).parent
        for img in untagged:
            if not (base_path / img).exists():
                self.errors.append(f"Untagged image {img} not found in base folder")
                return False

        # In strict mode, having any untagged images is an error
        if self.strict and untagged:
            self.errors.append(
                "Strict mode: Untagged images not allowed. Please tag all images: "
                f"{', '.join(sorted(untagged))}"
            )
            return False
        # In non-strict mode, untagged images generate a warning
        elif untagged:
            self.add_warning(
                f"Found {len(untagged)} untagged images: {', '.join(sorted(untagged))}"
            )

        return True

    def _validate_settings(self, data: Dict) -> bool:
        """Validate settings section."""
        settings = data.get("settings", {})

        if not isinstance(settings, dict):
            self.errors.append("settings must be a dictionary")
            return False

        # Get valid content types directly
        valid_content_types = set(data.get("content_types", []))

        # Get valid products per content type directly from products
        valid_products = {}
        for ct, products in data.get("products", {}).items():
            valid_products[ct] = {p["name"] for p in products}

        # Validate each content type's settings
        for content_type, ct_settings in settings.items():
            # 1. Validate content type exists
            if content_type not in valid_content_types:
                self.errors.append(
                    f"Settings defined for invalid content type: {content_type}"
                )
                return False

            if not isinstance(ct_settings, dict):
                self.errors.append(f"Settings for {content_type} must be a dictionary")
                return False

            # 2. Check content-level settings
            if "content" not in ct_settings:
                self.errors.append(
                    f"Settings for {content_type} missing 'content' field"
                )
                return False

            # 3. Validate content settings if they exist
            if ct_settings["content"] is not None:
                if not self.settings_validator.validate_settings(
                    ct_settings["content"]
                ):
                    self.errors.extend(
                        [
                            f"{content_type} content settings: {e}"
                            for e in self.settings_validator.errors
                        ]
                    )
                    return False

            # 4. Validate product group settings
            seen_products = set()
            for key, value in ct_settings.items():
                if key == "content":
                    continue

                # Parse product group
                if not (key.startswith("[") and key.endswith("]")):
                    self.errors.append(
                        f"Invalid product group format in {content_type}: {key}"
                    )
                    return False

                products = {p.strip() for p in key[1:-1].split(",")}

                # Check for duplicate products across groups
                if seen_products & products:
                    self.errors.append(
                        f"Duplicate products in {content_type} settings: {seen_products & products}"
                    )
                    return False
                seen_products.update(products)

                # Validate products exist
                if content_type in valid_products:
                    invalid_products = products - valid_products[content_type] - {"all"}
                    if invalid_products:
                        self.errors.append(
                            f"Invalid products in {content_type} settings: {invalid_products}. "
                            f"Valid products: {sorted(valid_products[content_type])}"
                        )
                        return False

                # Validate settings if they exist
                if value is not None:
                    if not self.settings_validator.validate_settings(value):
                        self.errors.extend(
                            [
                                f"{content_type} {key} settings: {e}"
                                for e in self.settings_validator.errors
                            ]
                        )
                        return False

        return True
    
    def _validate_product_counts(self, data: Dict) -> bool:
        """Validate product counts and coverage"""
        logger.debug("Validating product counts and image coverage...")
        
        product_counts = {}
        
        # Initialize count structure
        for ct in data["products"]:
            product_counts[ct] = defaultdict(int)

        # First pass: Count non-'all' images
        for img_name, img_data in data["images"].items():
            ct = img_data.get("content_type")
            prod = img_data.get("product")
            
            if prod and prod != "all":
                product_counts[ct][prod] += 1
        
        # Second pass: Add 'all' images to total count
        all_images_count = {}
        for ct in data["products"]:
            all_images_count[ct] = sum(1 for img in data["images"].values() 
                                    if img.get("content_type") == ct and img.get("product") == "all")

        # Validate counts against metadata
        for content_type, products in data["products"].items():
            for product_info in products:
                product_name = product_info["name"]
                stored_count = product_info.get("current_count", 0)
                
                # Get product-specific count
                actual_count = product_counts[content_type][product_name]
                # Add 'all' images count only once
                actual_count += all_images_count[content_type]
                
                # Update the stored count
                product_info["current_count"] = actual_count
                
                if stored_count != actual_count:
                    msg = f"Incorrect count for {content_type}/{product_name}: metadata shows {stored_count} but found {actual_count} images"
                    self.add_warning(msg)
                
                logger.debug(f"Product count validation for {content_type}/{product_name}: metadata={stored_count}, actual={actual_count}")
        
        return True
    def add_warning(self, msg: str, key: Optional[str] = None):
        """Add warning only if not seen before.
        
        Args:
            msg: The warning message
            key: Optional unique key for the warning. If not provided, uses the message as the key
        """
        warning_key = key if key is not None else msg
        if warning_key not in self.seen_warnings:
            self.warnings.append(msg)
            self.seen_warnings.add(warning_key)

