import json
from pathlib import Path
from typing import Dict, List, Literal, Optional
from ..captions import CaptionsHelper


class MetadataGenerator:
    def __init__(
        self, base_path: Path, content_types: List[str], products: Dict[str, List[str]]
    ):
        self.base_path = base_path
        self.content_types = content_types
        self.products = products
        self.metadata = {}

    def generate(self) -> Dict:
        """Main generation function, calls all sub-generators in order."""
        self._generate_content_types()
        self._generate_products()
        self._generate_structure()
        self._generate_images()
        self._generate_untagged()
        self._generate_settings()

        # Validate JSON serialization
        try:
            json.dumps(self.metadata)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Generated metadata is not JSON serializable: {e}")

        return self.metadata

    def _generate_content_types(self) -> None:
        """Generate content_types section."""
        self.metadata["content_types"] = self.content_types

    def _generate_products(self) -> None:
        """Generate products section with configuration.
        
        Product structure:
        {
            "name": str,              # Product name
            "prevent_duplicates": bool,# Whether to prevent duplicate usage
            "min_occurrences": int,   # Maximum times this product can be used
            "current_count": int      # Current number of times product has been used
        }
        """
        # Get max occurrences from captions
        captions_path = self.base_path / "captions.csv"
        min_occurrences = CaptionsHelper.get_product_min_occurrences(captions_path)

        self.metadata["products"] = {
            ct: [
                {
                    "name": prod,
                    "prevent_duplicates": False,  # Default all products to False
                    "current_count": 0,  # Initialize count at 0
                    # Find min_occurrences for this product, default to 0 if not found
                    "min_occurrences": next(
                        (
                            p["min_occurrences"]
                            for p in min_occurrences.get(ct, [])
                            if p["name"] == prod
                        ),
                        0,
                    ),
                }
                for prod in sorted(set(prods))
            ]
            for ct, prods in self.products.items()
        }

    def _generate_structure(self) -> None:
        """Generate structure section with paths and image lists."""
        valid_extensions = {".png", ".jpg", ".jpeg"}
        self.metadata["structure"] = {}

        for content_type in self.content_types:
            path = self.base_path / content_type
            # Get all valid images with case-insensitive extensions
            images = []
            for ext in valid_extensions:
                # Handle both lowercase and uppercase extensions
                images.extend([f.name for f in path.glob(f"*{ext}")])
                images.extend([f.name for f in path.glob(f"*{ext.upper()}")])

            self.metadata["structure"][content_type] = {
                "path": str(path),
                "images": sorted(images),  # Sort for consistency
            }

    def _generate_images(self) -> None:
        """Generate images section with metadata for each image."""
        self.metadata["images"] = {}
        all_images = []

        # First collect all images
        for content_type, struct in self.metadata["structure"].items():
            for image_name in struct["images"]:
                path = Path(struct["path"]) / image_name
                if path.exists():
                    all_images.append(
                        (
                            image_name,
                            {
                                "content_type": content_type,
                                "dimensions": self._get_image_dimensions(path),
                                "product": None,  # Initially untagged
                                "settings_source": "default",
                                "settings": None,  # No custom settings initially
                            },
                        )
                    )

        # Then add them in sorted order
        for image_name, image_data in sorted(all_images):
            self.metadata["images"][image_name] = image_data

    def _generate_untagged(self) -> None:
        """Generate untagged section - ONLY images in base folder that aren't in content folders."""
        # Get all valid image extensions
        valid_extensions = {".png", ".jpg", ".jpeg"}

        # Get all images from base folder
        base_images = [
            f.name
            for f in self.base_path.iterdir()
            if (
                f.is_file()
                and not f.name.startswith(".")
                and f.suffix.lower() in valid_extensions
            )
        ]

        # Get all images that are already in content folders
        content_images = set()
        for content_type in self.metadata["structure"].values():
            content_images.update(content_type["images"])

        # Only include images that are in base folder AND NOT in content folders
        untagged = [img for img in base_images if img not in content_images]

        self.metadata["untagged"] = sorted(untagged)  # Sort for consistency

    def _generate_settings(self) -> None:
        """Generate settings hierarchy with product groups."""
        self.metadata["settings"] = {}

        for content_type in self.content_types:
            # Get all products for this content type
            products = [p["name"] for p in self.metadata["products"][content_type]]

            # Create settings structure
            self.metadata["settings"][content_type] = {
                "content": None,  # Content-type level settings
                f"[{', '.join(sorted(products))}]": None,  # Product group settings
            }

    def _get_image_dimensions(self, path: Path) -> Dict[str, int]:
        """Helper to get image dimensions."""
        from PIL import Image

        with Image.open(path) as img:
            width, height = img.size
        return {"width": width, "height": height}

    def _generate_image_metadata(self, path: Path, content_type: str) -> Dict:
        """Generate metadata for a single image."""
        return {
            "content_type": content_type,
            "dimensions": self._get_image_dimensions(path),
            "product": None,  # Initially untagged
            "settings_source": "default",
            "settings": None,
        }
