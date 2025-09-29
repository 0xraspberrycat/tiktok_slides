from config.logging import logger
import random
from text.generate_image import generate_image
from PIL import Image  # type: ignore
from typing import List, Optional, Union
from pathlib import Path


class Generator:
    def __init__(self, base_path: Path, metadata: dict, captions: dict):
        self.base_path = base_path
        self.metadata = metadata
        self.captions = captions
        self.default_output_path = self.base_path / "output"

    def _validate_output_path(
        self, custom_output_path: Optional[Union[Path, str]] = None
    ) -> Path:
        """Validate and return the output path

        Args:
            custom_output_path: Optional custom output path

        Returns:
            Path: Valid output path (either custom or default)
        """
        if custom_output_path is None:
            output_path = self.default_output_path
        else:
            # Convert to Path if string
            output_path = (
                Path(custom_output_path)
                if isinstance(custom_output_path, str)
                else custom_output_path
            )

            # Validate the path exists
            if not output_path.exists():
                logger.warning(
                    f"Custom output path {output_path} does not exist. Using default: {self.default_output_path}"
                )
                output_path = self.default_output_path

        # Ensure output directory exists
        output_path.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Using output path: {output_path}")
        return output_path

    def generate(
        self,
        variations: int = 2,
        allow_all_duplicates: bool = False,
        output_path: Optional[Union[Path, str]] = None,
    ):
        """Generate slide variations from captions.
        If the only product is "all" and prevent duplicates is True then it wont find any.
        just name the product something other than all since all is a reserved name

        Args:
            variations: Number of variations to generate
            allow_all_duplicates: If True, allows 'all' product to be used even for products with prevent_duplicates=true
            output_path: Optional custom output path. If invalid or None, uses default path
        """
        logger.info(f"Starting generation of {variations} variations")

        # Validate and get output path
        output_path = self._validate_output_path(output_path)

        import gc

        gc_post_counter = (
            0  # count # of posts we have done. collect garbace every 5 rounds.
        )

        """
        Example header structure:
        headers = ['product_hook', 'hook', 'product_filler', 'filler', ...]
        For idx=1: headers[0] = 'product_hook' -> 'hook'
        For idx=2: headers[2] = 'product_filler' -> 'filler'
        And so on
        """
        headers_map = {
            i: self.captions["headers"][(i - 1) * 2].split("_")[1]  # Simpler indexing
            for i in range(1, len(self.captions["headers"]) // 2 + 1)
        }

        for variation_num in range(1, variations + 1):

            variation_path = output_path / f"variation{variation_num}"
            logger.info(f"Processing variation {variation_num}")

            # Process each row (post) in captions
            for post_num, row in enumerate(self.captions["captions"], 1):
                post_path = variation_path / f"post{post_num}"
                post_path.mkdir(
                    parents=True, exist_ok=True
                )  # Create directory once per post
                logger.info(f"Processing post {post_num}")

                # Track used images for duplicate prevention
                used_images = {
                    content_type: {
                        product_info["name"]: []  # Use product name as key
                        for product_info in self.metadata.data["products"][content_type]
                    }
                    for content_type in self.metadata.data["content_types"]
                }

                # Process each content piece in the row
                for idx, (product, content) in enumerate(zip(row[::2], row[1::2]), 1):
                    content_type = headers_map[idx]

                    logger.debug(
                        f"Processing {content_type} with product {product} and text: {content}"
                    )

                    if not content:  # Skip empty content
                        logger.debug(f"Skipping empty content for {content_type}")
                        continue

                    # Generate and save image
                    image = self._generate_single_image(
                        content_type=content_type,
                        product=product,
                        text=content,
                        used_images=used_images,
                        allow_all_duplicates=allow_all_duplicates,
                    )

                    # Save image
                    image_path = post_path / f"{idx}.png"
                    image.save(image_path)
                    image.close()
                    logger.debug(
                        f"Saved image {idx} for post {post_num} in variation {variation_num}"
                    )

                gc_post_counter += 1
                if gc_post_counter % 5 == 0:  # Every 5 images
                    gc.collect()  # Force garbage collection

    def _generate_single_image(
        self,
        content_type: str,
        product: str,
        text: str,
        used_images: dict,
        allow_all_duplicates: bool,
    ) -> Image.Image:
        """Generate a single image with text

        Args:
            content_type: Type of content (hook, content, cta)
            product: Product name
            text: Text to add to image
            used_images: Tracking dict for duplicate prevention
            allow_all_duplicates: If True, allows 'all' product to be used even for products
                                with prevent_duplicates=true
        """
        logger.debug(f"Generating image for {content_type} - {product}")

        # Get available images
        content_path = self.base_path / content_type
        available_images = self._get_available_images(
            content_type, product, used_images, allow_all_duplicates
        )

        if not available_images:
            raise ValueError(f"No available images for {content_type} - {product}")

        # Select and track image
        selected_image = random.choice(available_images)
        if self._should_prevent_duplicates(content_type, product):
            used_images[content_type][product].append(selected_image)

        # Get image settings
        image_settings = self._get_image_settings(content_type, product, selected_image)
        text_type = image_settings["base_settings"]["default_text_type"]

        # Generate image
        logger.debug(f"Using image {selected_image} with text type {text_type}")
        return generate_image(
            settings=image_settings,
            text_type=text_type,
            colour_index=random.randint(
                0, len(image_settings["text_settings"][text_type]["colors"]) - 1
            ),
            image_path=str(content_path / selected_image),
            text=text,
        )

    def _get_available_images(
        self,
        content_type: str,
        product: str,
        used_images: dict,
        allow_all_duplicates: bool,
    ) -> List[str]:
        """Get list of available images for content type and product with improved duplicate handling"""
        logger.debug(f"\n=== Getting Available Images ===")
        logger.debug(f"Content Type: {content_type}")

        # Strip whitespace from product name
        product = product.strip() if product else product
        logger.debug(f"Product (after stripping whitespace): {product}")

        # Rest of the method remains the same
        all_images = self.metadata.data["structure"][content_type]["images"]
        logger.debug(f"Found images in metadata: {all_images}")

        if product == "all":
            logger.debug("Processing 'all' product case")
            available = []

            content_products = self.metadata.data["products"][content_type]

            for prod_info in content_products:
                prod_name = prod_info["name"]
                prevent_duplicates = prod_info["prevent_duplicates"]

                logger.debug(
                    f"Checking product: {prod_name} (prevent_duplicates={prevent_duplicates})"
                )

                if prevent_duplicates and not allow_all_duplicates:
                    logger.debug(f"Skipping {prod_name} due to duplicate prevention")
                    continue

                matching_images = [
                    img
                    for img in all_images
                    if self.metadata.data["images"][img]["product"] == prod_name
                ]

                if prevent_duplicates:
                    matching_images = [
                        img
                        for img in matching_images
                        if img not in used_images[content_type][prod_name]
                    ]

                logger.debug(f"Adding {len(matching_images)} images from {prod_name}")
                available.extend(matching_images)

        else:
            logger.debug(f"Processing specific product: {product}")

            available = [
                img
                for img in all_images
                if self.metadata.data["images"][img]["product"] == product
            ]

            if self._should_prevent_duplicates(content_type, product):
                logger.debug(f"Applying duplicate prevention for {product}")
                logger.debug(f"Used images: {used_images[content_type][product]}")

                available = [
                    img
                    for img in available
                    if img not in used_images[content_type][product]
                ]

            logger.debug(f"Found {len(available)} available images")

        if not available:
            logger.warning(f"No available images found for {content_type} - {product}")

        return available

    def _should_prevent_duplicates(self, content_type: str, product: str) -> bool:
        """Check if duplicates should be prevented for this content type and product"""
        logger.debug(f"\n=== Checking Duplicate Prevention ===")
        logger.debug(f"Content Type: {content_type}")

        # Strip whitespace from product name
        product = product.strip() if product else product
        logger.debug(f"Product (after stripping whitespace): {product}")

        logger.debug(
            f"Products in metadata: {self.metadata.data['products'][content_type]}"
        )

        for prod_info in self.metadata.data["products"][content_type]:
            if prod_info["name"] == product:
                should_prevent = prod_info["prevent_duplicates"]
                logger.debug(f"Found product. Prevent duplicates: {should_prevent}")
                return should_prevent

        logger.debug("Product not found in metadata")
        return False

    def _get_image_settings(
        self, content_type: str, product: str, image_path: str
    ) -> dict:
        """Get settings for specific image, falling back through hierarchy as needed"""
        logger.debug(f"\n=== Getting Image Settings ===")
        logger.debug(f"Content Type: {content_type}")
        logger.debug(f"Product: {product}")
        logger.debug(f"Image path: {image_path}")

        # Extract filename from path
        image_name = Path(image_path).name
        logger.debug(f"Image name: {image_name}")

        try:
            # Get image metadata
            image_data = self.metadata.data["images"][image_name]
            settings_source = image_data["settings_source"]

            # Handle different settings sources
            if settings_source == "default":
                # Import default template for default settings
                from content_manager.settings.settings_constants import DEFAULT_TEMPLATE
                import json

                logger.debug(f"Loading default template from: {DEFAULT_TEMPLATE}")
                try:
                    with open(DEFAULT_TEMPLATE) as f:
                        return json.load(f)
                except (IOError, json.JSONDecodeError) as e:
                    logger.error(f"Failed to load default template: {str(e)}")
                    raise

            elif settings_source == "custom":
                if image_data["settings"] is None:
                    raise ValueError(
                        f"Image {image_name} has custom settings_source but no settings defined"
                    )
                return image_data["settings"]

            elif settings_source == "content":
                # Get content-level settings
                content_settings = self.metadata.data["settings"][content_type][
                    "content"
                ]
                if content_settings is None:
                    raise ValueError(
                        f"No content-level settings defined for {content_type}"
                    )
                return content_settings

            elif settings_source == "product":
                # Look for product settings
                for group, settings in self.metadata.data["settings"][
                    content_type
                ].items():
                    if group != "content":  # Skip content settings
                        products = {p.strip() for p in group[1:-1].split(",")}
                        if product in products and settings is not None:
                            return settings
                raise ValueError(
                    f"No product settings found for {product} in {content_type}"
                )

            else:
                raise ValueError(f"Invalid settings_source: {settings_source}")

        except Exception as e:
            logger.error(f"Error getting settings for {image_name}: {str(e)}")
            raise ValueError(f"Failed to get settings for {image_name}: {str(e)}")
