import ast
import copy
import json
from pathlib import Path
from typing import Dict, List, Literal, Optional, Set, Union

from config.logging import logger
from content_manager.metadata.metadata import Metadata
from content_manager.settings.settings_constants import VALID_TEXT_TYPES
from content_manager.settings.settings_validator import SettingsValidator


class Settings:
    """Handles all settings operations and validation for content and product settings.

    This class manages:
    1. Template Operations:
        - Loading/saving templates (templates cannot be overwritten)
        - Listing available templates and fonts
        - Template validation before saving

    2. Settings Modification:
        - Base settings changes (default_text_type)
        - Text type specific settings (plain/highlight)
        - Adding new text types with validation

    3. Settings Application:
        - Content level settings (override all)
        - Product level settings (inherit from content)
        - Custom settings (highest priority)
        - Bulk application with overwrite protection
        - Automatic group merging for identical settings

    Settings Structure:
        {
            "base_settings": {
                "default_text_type": "plain"  # or "highlight"
            },
            "text_settings": {
                "plain": {  # Outline style
                    "font_size": int,
                    "font": "assets.fonts.X.ttf",
                    "style_type": "outline_width",
                    "style_value": int,
                    "colors": [{"text": "#hex", "outline": "#hex"}, ...],
                    "position": {
                        "vertical": [float, float],  # 0-1 range
                        "horizontal": [float, float],  # 0-1 range
                        "vertical_jitter": float,
                        "horizontal_jitter": float
                    },
                    "margins": {
                        "top": float,    # 0-1 range
                        "bottom": float,
                        "left": float,
                        "right": float
                    }
                },
                "highlight": {  # Background style
                    # Same structure but with background colors
                    "colors": [{"text": "#hex", "background": "#hex"}, ...]
                }
            }
        }

    Usage:
        settings = Settings()

        # Load and modify template
        my_settings = settings.load_template("default")

        # Modify base settings
        my_settings = settings.modify_base_settings(
            settings=my_settings,
            default_text_type="highlight"
        )

        # Modify text type settings - individual changes
        my_settings = settings.modify_settings(
            settings=my_settings,
            text_type="plain",
            font_size=80,
            vertical_jitter=0.05,
            left_margin=0.1
        )

        # Bulk apply with overwrite check
        targets = {
            "hook": ["product1", "product2"],
            "content": ["product3"]
        }
        settings.bulk_apply_settings(settings_dict, targets)

        # Modify colors (complete replacement)
        my_settings = settings.modify_settings(
            settings=my_settings,
            text_type="highlight",
            colors=[
                {"text": "#000000", "background": "#FFFFFF"},
                {"text": "#FFFFFF", "background": "#FF0000"}
            ]
        )

        # Save modified settings
        settings.save_template(my_settings, "my_template")

        # Apply to content
        settings.apply_content_settings("hook", my_settings)
    """

    def __init__(self, test_mode: bool = False):
        """Initialize settings handler.

        Args:
            test_mode: If True, use test directories instead of real ones
        """
        if test_mode:
            self.templates_dir = Path("assets/test_templates")
            self.fonts_dir = Path("assets/test_fonts")
        else:
            self.templates_dir = Path("assets/templates")
            self.fonts_dir = Path("assets/fonts")

        self.settings_validator = SettingsValidator()
        self.metadata = None
        self.base_path = None

    def set_data(self, metadata: Metadata):
        """Use existing metadata instance.

        Args:
            metadata: Initialized Metadata instance from content_handler
        """
        self.metadata = metadata

    # TEMPLATE OPERATIONS
    def list_templates(self) -> List[str]:
        """List available templates and print them to console.

        This function will:
        1. Print all available templates to console
        2. Return the list of templates for programmatic use

        Returns:
            List[str]: Template names without .json extension

        Example:
            >>> settings = Settings()
            >>> templates = settings.list_templates()
            Available templates:
            * default
            * template1
            * template2
            >>> print(templates)
            ['default', 'template1', 'template2']
        """
        templates = [p.stem for p in self.templates_dir.glob("*.json")]

        # Print available templates
        print("Available templates:")
        if templates:
            for template in sorted(templates):
                print(f"* {template}")
        else:
            print("* No templates found")

        return templates

    def load_template(self, name: str = "default") -> Dict:
        """Load settings template from templates directory.

        Args:
            name: Template name to load (use list_templates() to see available options)

        Returns:
            Dict: Complete settings block

        Raises:
            ValueError: If template doesn't exist or is invalid
            FileNotFoundError: If template file not found

        Example:
            >>> settings = Settings()
            >>> settings.list_templates()  # Check available templates
            Available templates:
            * default
            * template1
            >>> my_settings = settings.load_template("default")
        """
        template_path = self.templates_dir / f"{name}.json"
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {name}")

        try:
            with open(template_path) as f:
                settings = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in template {name}: {str(e)}")

        if not self.settings_validator.validate_settings(settings):
            raise ValueError(f"Invalid template: {name}")

        return settings

    def list_fonts(self) -> List[str]:
        """List available fonts and print them to console.

        This function will:
        1. Print all available fonts to console
        2. Return the list of fonts for programmatic use

        Returns:
            List[str]: Font names without extension

        Example:
            >>> settings = Settings()
            >>> fonts = settings.list_fonts()
            Available fonts:
            * montserratbold
            * tiktokfont
            >>> print(fonts)
            ['montserratbold', 'tiktokfont']
        """
        fonts = [p.stem for p in self.fonts_dir.glob("*.ttf")]

        # Print available fonts
        logger.trace("Available fonts:")
        if fonts:
            for font in sorted(fonts):
                logger.trace(f"* {font}")
        else:
            logger.trace("* No fonts found")

        return fonts

    def load_font(self, name: str) -> str:
        """Load and validate font.

        Args:
            name: Font name without extension (use list_fonts() to see available options)

        Returns:
            str: Full font path in assets.fonts.X.ttf format

        Raises:
            ValueError: If font doesn't exist or is invalid

        Example:
            >>> settings = Settings()
            >>> font_path = settings.load_font("tiktokfont")
            >>> print(font_path)
            'assets.fonts.tiktokfont.ttf'
        """
        # Check if font exists with exact name (case sensitive)
        font_file = f"{name}.ttf"
        if font_file not in [f.name for f in self.fonts_dir.iterdir()]:
            raise ValueError(f"Font not found: {name}")

        font_path = self.fonts_dir / font_file

        # Basic validation - check if it's a real file
        if not font_path.is_file():
            raise ValueError(f"Invalid font: {name}")

        return f"assets.fonts.{name}.ttf"

    # SETTINGS MODIFICATION
    def modify_settings(
        self,
        settings: Dict,
        text_type: str,
        font_size: Optional[int] = None,
        font: Optional[str] = None,
        style_value: Optional[int] = None,
        colors: Optional[List[Dict]] = None,
        positions: Optional[
            tuple[
                Optional[tuple[float, float]],
                Optional[tuple[float, float]],
                Optional[float],
                Optional[float],
            ]
        ] = None,
        vertical_position: Optional[List[float]] = None,
        horizontal_position: Optional[List[float]] = None,
        vertical_jitter: Optional[float] = None,
        horizontal_jitter: Optional[float] = None,
        margins: Optional[
            tuple[Optional[float], Optional[float], Optional[float], Optional[float]]
        ] = None,
        top_margin: Optional[float] = None,
        bottom_margin: Optional[float] = None,
        left_margin: Optional[float] = None,
        right_margin: Optional[float] = None,
    ) -> Dict:
        """Modify settings for a specific text type.

        Args:
            settings: Complete settings block
            text_type: Text type to modify ("plain" or "highlight")
            font_size: New font size
            font: New font path
            style_value: New style value (outline_width or corner_radius)
            colors: New colors list (completely replaces existing)

            positions: Tuple of (vertical_pos, horizontal_pos, vert_jitter, horiz_jitter)
                      where position tuples are (min, max) and jitters are single values
                      Any value can be None to skip that update
            vertical_position: New vertical position [min, max] (deprecated if positions used)
            horizontal_position: New horizontal position [min, max] (deprecated if positions used)
            vertical_jitter: New vertical jitter (deprecated if positions used)
            horizontal_jitter: New horizontal jitter (deprecated if positions used)

            margins: Tuple of (top, bottom, left, right) margins
                    Any value can be None to skip that update
            top_margin: New top margin
            bottom_margin: New bottom margin
            left_margin: New left margin
            right_margin: New right margin

        Notes:
            - Position and margin changes can be individual
            - Colors are completely replaced when changed
            - style_type is fixed per text_type (plain=outline_width, highlight=corner_radius)

        Returns:
            Dict: Modified settings

        Raises:
            ValueError: If any values invalid
        """

        # Make a deep copy of original settings to preserve in case of validation failure
        original_settings = copy.deepcopy(settings)
        working_copy = copy.deepcopy(settings)  # New! Work on this copy

        try:
            # REDO
            # Validate input settings. Must always input base settings to change.
            if not working_copy:
                raise ValueError("No base settings provided to change")
            if not self.settings_validator.validate_settings(working_copy):
                raise ValueError("Invalid input settings structure")

            # MODIFICATION :: text_type. Must always specifiy text type
            if text_type not in working_copy["text_settings"]:
                raise ValueError(f"Invalid text_type: {text_type}")

            text_settings = working_copy["text_settings"][text_type]

            # MODIFICATION :: font_size
            if font_size is not None:
                text_settings["font_size"] = font_size

            # MODIFICATION :: font
            if font is not None:
                text_settings["font"] = font

            # MODIFICATION :: style_value
            if style_value is not None:
                # Check text type has correct style_type
                text_type_info = VALID_TEXT_TYPES.get(text_type)
                if not text_type_info:
                    raise ValueError(f"Invalid text_type: {text_type}")

                # Simple non-negative check with dynamic style type in error
                if style_value < 0:
                    style_type = text_type_info["style_type"]
                    raise ValueError(f"{style_type} cannot be negative")

                text_settings["style_value"] = style_value

            # MODIFICATION :: colors
            if colors is not None:
                # Get valid color keys for this text type
                text_type_info = VALID_TEXT_TYPES.get(text_type)
                if not text_type_info:
                    raise ValueError(f"Invalid text_type: {text_type}")

                required_color_keys = text_type_info[
                    "required_color_keys"
                ]  # e.g., ["text", "outline"] or ["text", "background"]

                # Validate each color dict
                for color in colors:
                    if not isinstance(color, dict):
                        raise ValueError("Each color must be a dictionary")

                    # Check all required keys exist
                    if not all(key in color for key in required_color_keys):
                        raise ValueError(
                            f"Color missing required keys: {required_color_keys}"
                        )

                    # Validate hex values
                    for key in required_color_keys:
                        if not isinstance(color[key], str) or not color[key].startswith(
                            "#"
                        ):
                            raise ValueError(
                                f"Invalid hex color for {key}: {color[key]}"
                            )

                text_settings["colors"] = colors

            # MODIFICATION :: position tuple
            if positions is not None:
                # First check we're not mixing with individual params
                if any(
                    x is not None
                    for x in [
                        vertical_position,
                        horizontal_position,
                        vertical_jitter,
                        horizontal_jitter,
                    ]
                ):
                    raise ValueError(
                        "Cannot mix positions tuple with individual position parameters"
                    )

                vert_pos, horiz_pos, v_jitter, h_jitter = positions

                # Only update the values that aren't None
                if vert_pos is not None:
                    text_settings["position"]["vertical"] = list(vert_pos)
                if horiz_pos is not None:
                    text_settings["position"]["horizontal"] = list(horiz_pos)
                if v_jitter is not None:
                    text_settings["position"]["vertical_jitter"] = v_jitter
                if h_jitter is not None:
                    text_settings["position"]["horizontal_jitter"] = h_jitter
            # MODIFICATION :: individual positions
            elif any(
                x is not None
                for x in [
                    vertical_position,
                    horizontal_position,
                    vertical_jitter,
                    horizontal_jitter,
                ]
            ):
                # Only update the values that are provided
                if vertical_position is not None:
                    text_settings["position"]["vertical"] = vertical_position
                if horizontal_position is not None:
                    text_settings["position"]["horizontal"] = horizontal_position
                if vertical_jitter is not None:
                    text_settings["position"]["vertical_jitter"] = vertical_jitter
                if horizontal_jitter is not None:
                    text_settings["position"]["horizontal_jitter"] = horizontal_jitter

            # MODIFICATION :: margins tuple
            if margins is not None:
                # First check we're not mixing with individual params
                if any(
                    x is not None
                    for x in [top_margin, bottom_margin, left_margin, right_margin]
                ):
                    raise ValueError(
                        "Cannot mix margins tuple with individual margin parameters"
                    )

                top, bottom, left, right = margins

                # Only update the values that aren't None
                if top is not None:
                    text_settings["margins"]["top"] = top
                if bottom is not None:
                    text_settings["margins"]["bottom"] = bottom
                if left is not None:
                    text_settings["margins"]["left"] = left
                if right is not None:
                    text_settings["margins"]["right"] = right

            # MODIFICATION :: individual margins
            elif any(
                x is not None
                for x in [top_margin, bottom_margin, left_margin, right_margin]
            ):
                # Only update the values that are provided
                if top_margin is not None:
                    text_settings["margins"]["top"] = top_margin
                if bottom_margin is not None:
                    text_settings["margins"]["bottom"] = bottom_margin
                if left_margin is not None:
                    text_settings["margins"]["left"] = left_margin
                if right_margin is not None:
                    text_settings["margins"]["right"] = right_margin

            # FINAL validation - this will catch ALL issues including position overlaps
            if not self.settings_validator.validate_settings(working_copy):
                raise ValueError("Invalid settings structure")

            return working_copy

        except Exception as e:
            logger.error(f"Error modifying settings: {str(e)}")
            logger.error("Returning original unmodified settings")
            return original_settings

    def modify_base_settings(
        self, settings: Dict, default_text_type: Optional[str] = None
    ) -> Dict:
        """Modify base settings.

        Args:
            settings: Complete settings block
            default_text_type: New default text type ("plain" or "highlight")

        Returns:
            Dict: Modified settings

        Raises:
            ValueError: If text_type invalid
        """
        if default_text_type:
            if default_text_type not in VALID_TEXT_TYPES:
                raise ValueError(
                    f"default_text_type must be one of: {list(VALID_TEXT_TYPES.keys())}"
                )
            settings["base_settings"]["default_text_type"] = default_text_type
        return settings

    # SETTINGS APPLICATION
    def save_template(self, settings: Dict, name: str) -> None:
        """Save settings template to templates directory.

        Args:
            settings: Settings template
            name: Template name (must be lowercase, no spaces/hyphens, max 100 chars)

        Raises:
            ValueError: If name is "default" or template already exists
            ValueError: If settings invalid
            ValueError: If template name invalid
        """
        # Validate template name
        if name == "default":
            raise ValueError("Cannot overwrite default template")

        if not name or not isinstance(name, str):
            raise ValueError("Template name must be a non-empty string")

        if len(name) > 100:
            raise ValueError("Template name cannot exceed 100 characters")

        if not name.isascii():
            raise ValueError("Template name must contain only ASCII characters")

        if not name.islower():
            raise ValueError("Template name must be lowercase")

        if " " in name or "-" in name:
            raise ValueError("Template name cannot contain spaces or hyphens")

        # Check if template exists
        template_path = self.templates_dir / f"{name}.json"
        if template_path.exists():
            raise ValueError(f"Template already exists: {name}")

        # Validate settings
        if not self.settings_validator.validate_settings(settings):
            raise ValueError("Invalid settings")

        # Save template
        try:
            with open(template_path, "w") as f:
                json.dump(settings, f, indent=2)
        except IOError as e:
            raise IOError(f"Failed to save template: {str(e)}")

    def apply_content_settings(
        self, content_type: str, settings: Dict, overwrite: bool = False
    ) -> None:
        """Apply settings at content type level."""
        if self.metadata is None:
            raise RuntimeError("Metadata not initialized - please load content first")

        current = self.metadata.metadata_editor.get_settings(
            level="content_type", target=content_type
        )
        logger.trace(f"\nCurrent settings for {content_type}:")
        logger.trace(current)

        # Check if content type exists
        if content_type not in self.metadata.metadata_editor.get_content_types():
            raise ValueError(f"Invalid content type: {content_type}")

        # Validate settings (None is valid, otherwise must pass validation)
        if settings is not None:
            if not self.settings_validator.validate_settings(settings):
                raise ValueError("Invalid settings structure")

        # Settings application logic:
        # 1. If current settings are None -> apply new settings
        # 2. If current settings exist and are same -> skip
        # 3. If current settings exist and are different:
        #    - If overwrite=True -> apply new settings
        #    - If overwrite=False -> raise error
        if current["settings"] is not None:
            if current["settings"] == settings:
                logger.debug(
                    f"\nSettings for {content_type} are already up to date. No changes needed."
                )
                return
            elif not overwrite:
                raise ValueError(
                    f"Settings exist and are different for {content_type}. Set overwrite=True to force update."
                )

        self.metadata.metadata_editor.edit_settings(
            "content_type", content_type, settings
        )
        self.metadata.save()

    def apply_product_settings(
        self,
        content_type: str,
        product: str,
        settings: Optional[Dict],
        overwrite: bool = False,
        prevent_duplicates: bool = None,
    ) -> None:
        """Apply settings at product level."""

        # 1. ALL Validation First - SILENTLY
        if self.metadata is None:
            raise RuntimeError("Metadata not initialized - please load content first")

        # Check content type exists
        content_types = self.metadata.metadata_editor.get_content_types()
        if content_type not in content_types:
            raise ValueError(
                f"Invalid content type: {content_type}. Available types: {content_types}"
            )

        # Check product exists in content type
        products = self.metadata.metadata_editor.get_products(content_type)
        product_names = [p["name"] for p in products]
        if product not in product_names:
            raise ValueError(
                f"Product '{product}' not found in {content_type}.\n"
                f"Available products: {json.dumps(products, indent=2)}"
            )

        # Initialize content type settings if not exists (ONCE!)
        if content_type not in self.metadata.data["settings"]:
            self.metadata.data["settings"][content_type] = {}

        # Update prevent_duplicates if specified
        if prevent_duplicates is not None:
            logger.debug(
                f"\nUpdating duplicate prevention for {product} to: {prevent_duplicates}"
            )
            for prod in self.metadata.data["products"][content_type]:
                if prod["name"] == product:
                    prod["prevent_duplicates"] = prevent_duplicates
                    logger.debug("✓ Updated product metadata")
                    break

        # 2. Find Current State
        found_groups = self._find_product_groups(content_type, product)
        logger.debug(f"Found product in groups: {found_groups}")

        if len(found_groups) > 1:
            logger.error("\n!!! CRITICAL ERROR !!!")
            logger.error(f"Product {product} found in multiple groups: {found_groups}")
            raise ValueError(
                f"Product {product} exists in multiple groups: {found_groups}"
            )

        current_group = found_groups[0] if found_groups else None
        current_settings = self.metadata.data["settings"][content_type].get(
            current_group
        )
        logger.debug(f"Current group: {current_group}")
        logger.debug(f"Current settings: {current_settings}")

        # Handle None settings validation first
        if settings is None:
            if not overwrite:
                logger.warning("\nCannot reset settings to None without overwrite=True")
                return
        elif not self.settings_validator.validate_settings(settings):
            logger.critical("\n❌ Invalid settings structure - no changes will be made")
            raise ValueError("Missing required settings sections")

        # 3. Compare & Handle Settings
        if current_settings is not None:
            if current_settings == settings:
                msg = f"Product {product} already has these exact settings in group {current_group}"
                if overwrite:
                    # Force update if overwrite=True
                    logger.info(f"{msg} - Forcing update with overwrite=True")
                else:
                    # Otherwise just inform and stop
                    logger.info(msg)
                    raise ValueError(f"{msg}. Use overwrite=True to force update")

            elif not overwrite:
                msg = f"Product {product} has different settings in group {current_group}. Use overwrite=True to update"
                logger.error(msg)
                raise ValueError(msg)

        # IMPORTANT: Remove from ALL groups before any new group creation
        self._remove_product_from_groups(content_type, product)
        logger.debug("\nAfter removal - current groups:")
        logger.debug(self.metadata.data["settings"][content_type].keys())

        # Handle None settings after removal
        if settings is None:
            logger.debug("\nHandling None settings...")
            # Look for existing null settings group
            null_group = None
            for group, group_settings in self.metadata.data["settings"][
                content_type
            ].items():
                if group == "content":
                    continue
                if group_settings is None:
                    null_group = group
                    logger.debug(f"Found existing null group: {group}")
                    break

            if null_group:
                # Add to existing null group
                group_products = self._parse_group_products(null_group)
                if product not in group_products:  # Only add if not already there
                    group_products.append(product)
                    new_group = self._create_group_name(group_products)
                    logger.debug(
                        f"Adding to null group. Old: {null_group}, New: {new_group}"
                    )

                    # Update group
                    self.metadata.data["settings"][content_type][new_group] = None
                    if new_group != null_group:  # Only delete old if different
                        del self.metadata.data["settings"][content_type][null_group]
                    logger.debug(f"Added {product} to null settings group: {new_group}")
            else:
                # Create new null settings group
                self.metadata.data["settings"][content_type][f"[{product}]"] = None
                logger.debug(f"Created new null settings group for {product}")

            self.metadata.save()
            logger.debug("\nFinal state after None settings:")
            logger.debug(self.metadata.data["settings"][content_type])
            return

        # For non-None settings, check for matching groups
        logger.debug("\nChecking for matching settings groups...")
        matching_group = None

        for group, group_settings in self.metadata.data["settings"][
            content_type
        ].items():
            if group == "content" or group_settings is None:
                continue

            logger.trace(f"\nComparing with group: {group}")
            logger.trace("Group settings:")
            logger.trace(json.dumps(group_settings, indent=2))
            logger.trace("New settings:")
            logger.trace(json.dumps(settings, indent=2))

            if group_settings == settings:
                matching_group = group
                logger.debug(f"✓ Found matching settings in group: {group}")
                break
            else:
                logger.debug("✗ Settings don't match")

        # Final settings application
        if matching_group:
            # Merge into existing group
            group_products = self._parse_group_products(matching_group)
            if product not in group_products:
                group_products.append(product)
                new_group = self._create_group_name(group_products)

                self.metadata.data["settings"][content_type][new_group] = settings
                del self.metadata.data["settings"][content_type][matching_group]
                logger.debug(f"Merged {product} into group {new_group}")
        else:
            # Create new group
            self.metadata.data["settings"][content_type][f"[{product}]"] = settings
            logger.debug(f"Created new group for {product}")

        # 4. Save Changes
        self.metadata.save()
        logger.debug("\nFinal state:")
        logger.debug(self.metadata.data["settings"][content_type])

    def _find_product_groups(self, content_type: str, product: str) -> List[str]:
        """Find all groups containing the product."""
        found_groups = []
        for group in self.metadata.data["settings"][content_type]:
            if group == "content":
                continue
            group_products = self._parse_group_products(group)
            if product in group_products:
                found_groups.append(group)
        return found_groups

    def _parse_group_products(self, group: str) -> List[str]:
        """Parse products from group name."""
        if not (group.startswith("[") and group.endswith("]")):
            return []
        clean_group = group[1:-1]
        return [p.strip() for p in clean_group.split(",")]

    def _remove_product_from_groups(self, content_type: str, product: str) -> None:
        """Remove product from all groups it exists in."""
        logger.debug(f"\nRemoving {product} from all existing groups...")

        for group, settings in list(
            self.metadata.data["settings"][content_type].items()
        ):
            # Skip special keys that aren't product groups
            if not (group.startswith("[") and group.endswith("]")):
                continue

            group_products = self._parse_group_products(group)
            if product in group_products:
                logger.debug(f"Found in group: {group}")
                group_products.remove(product)

                if group_products:  # If group still has other products
                    new_group = f"[{', '.join(sorted(group_products))}]"
                    self.metadata.data["settings"][content_type][new_group] = settings
                del self.metadata.data["settings"][content_type][group]
                logger.debug(f"Removed from group: {group}")

    def _create_group_name(self, products: List[str]) -> str:
        """Create sorted group name from product list."""
        return f"[{', '.join(sorted(products))}]"

    def bulk_apply_settings(
        self,
        settings: Dict,
        targets: Dict[str, List[str]],
        overwrite: bool = False,
        prevent_duplicates: bool = None,
    ) -> None:
        """
        Bulk apply settings to multiple content types and their products.

        Args:
            settings: Settings dictionary to apply
            targets: Dict mapping content_types to list of products
                    Example: {"hook": ["product1", "product2"],
                             "content": ["product3"]}
            overwrite: Force overwrite existing settings

        Raises:
            RuntimeError: If metadata not initialized
            ValueError: If no targets specified or invalid settings/products
        """
        # Check metadata initialization first
        if self.metadata is None or self.metadata.metadata_editor is None:
            raise RuntimeError(
                "Metadata not initialized - please use set_data() to initialize metadata first"
            )

        # Basic validation first
        if not targets:
            raise ValueError("No targets specified")

        # 1. Validate settings structure
        if not self.settings_validator.validate_settings(settings):
            raise ValueError("Invalid settings structure")

        # 2. Validate all content types and products exist
        for content_type, products in targets.items():
            # Check content type exists
            if content_type not in self.metadata.metadata_editor.get_content_types():
                raise ValueError(f"Invalid content type: {content_type}")

            # Check all products exist in this content type
            valid_products = [
                p["name"]
                for p in self.metadata.metadata_editor.get_products(content_type)
            ]
            invalid_products = [p for p in products if p not in valid_products]
            if invalid_products:
                raise ValueError(
                    f"Invalid products for {content_type}: {invalid_products}\n"
                    f"Valid products are: {valid_products}"
                )

        # 3. If not overwriting, check nothing would be overwritten
        if not overwrite:
            for content_type, products in targets.items():
                # Check content type settings
                current = self.metadata.metadata_editor.get_settings(
                    level="content_type", target=content_type
                )
                if current["settings"] is not None:
                    logger.error("\nCannot apply settings without overwrite=True:")
                    logger.error(
                        f"\n - {content_type} already has settings and we don't check if they are the same for this pre-application check."
                    )
                    raise ValueError("Use overwrite=True to force update")

                # Check product settings
                for product in products:
                    groups = self._find_product_groups(content_type, product)
                    if groups:
                        current = self.metadata.metadata_editor.get_settings(
                            level="product", target=product, content_type=content_type
                        )
                        if current["settings"] is not None:
                            logger.error(
                                "\nCannot apply settings without overwrite=True:"
                            )
                            logger.error(f"- {product} already has settings")
                            raise ValueError("Use overwrite=True to force update")

        logger.debug(f"Bulk apply - Overwrite: {overwrite}")
        logger.debug(f"Bulk apply - Prevent duplicates: {prevent_duplicates}\n")

        # Process each content type and its products
        for content_type, products in targets.items():
            try:
                # Apply content type settings
                self.apply_content_settings(
                    content_type=content_type, settings=settings, overwrite=overwrite
                )
                logger.debug(f"{content_type}: content settings applied")
            except Exception as e:
                logger.error(f"{content_type}: content settings failed - {str(e)}")
                if not overwrite:
                    raise

            # Apply product settings
            for product in products:
                try:
                    self.apply_product_settings(
                        content_type=content_type,
                        product=product,
                        settings=settings,
                        overwrite=overwrite,
                        prevent_duplicates=prevent_duplicates,
                    )
                    logger.debug(f"{content_type}: {product}")
                except Exception as e:
                    logger.error(f"{content_type}: {product} - {str(e)}")
                    if not overwrite:
                        raise

    def _apply_custom_settings(
        self,
        settings: Optional[Dict],
        target: str,
        validate: bool = False,
        settings_source: Optional[Literal["default", "content_type", "product"]] = None,
    ) -> None:
        """Apply custom settings to individual image.

        Args:
            settings: Settings to apply (None is valid to clear settings)
            target: Image name (e.g. "2h.PNG")
            validate: Whether to validate settings structure
            settings_source: When clearing settings (settings=None), specify which source to set
                           Can be "default", "content_type", or "product"
                           Ignored if settings is not None

        Notes:
            - Can delete settings by setting settings=None
            - No overwrite protection needed
            - When applying settings, always sets settings_source to "custom"
            - When clearing settings, can specify alternate settings_source
            - Validation optional (controlled interface environment)

        Raises:
            ValueError: If settings_source provided with non-None settings
            ValueError: If invalid settings_source provided
        """
        # 1. Check if image exists first
        if target not in self.metadata.metadata_editor.get_images():
            raise ValueError(f"Image not found: {target}")

        # 2. Validate settings_source if provided
        valid_sources = ["default", "content_type", "product"]
        if settings_source is not None and settings_source not in valid_sources:
            raise ValueError(
                f"Invalid settings_source. Must be one of: {valid_sources}"
            )

        # 3. Validate settings_source usage
        if settings is not None and settings_source is not None:
            raise ValueError(
                "settings_source can only be specified when clearing settings (settings=None)"
            )

        # 4. Validate settings if requested (even if None)
        if validate:
            if settings is not None and not self.settings_validator.validate_settings(
                settings
            ):
                raise ValueError("Invalid settings structure")

        # 5. Handle clearing settings
        if settings is None:
            # Use provided source or default to "default"
            source = settings_source or "default"
            logger.debug(
                f"Clearing custom settings for {target} (new source: {source})"
            )
            self.metadata.metadata_editor.edit_image(
                target, {"settings": None, "settings_source": source}
            )
        else:
            # 6. Apply new settings (always custom source)
            logger.debug(f"Applying custom settings to {target}")
            self.metadata.metadata_editor.edit_image(
                target, {"settings": settings, "settings_source": "custom"}
            )

        # 7. Save changes
        self.metadata.save()
