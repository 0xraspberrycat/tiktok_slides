from pathlib import Path
import json
import streamlit as st  # type: ignore
from content_manager.settings.settings_constants import (
    DEFAULT_TEMPLATE,
    VALID_TEXT_TYPES,
)
from typing import List, Dict, Any, Set
from content_manager.metadata.metadata_editor import MetadataEditor
from content_manager.metadata.metadata import Metadata
from content_manager.settings.settings_handler import Settings
from content_manager.captions import CaptionsHelper
from config.logging import logger


class InterfaceSettingsManager:
    """Manages interface settings and state

    Settings Levels (in order of priority):
    1. default
    2. content
    3. product
    4. custom
    """

    def __init__(
        self,
        base_path: Path,
        content_types: Set[str],
        products: Dict[str, Any],
        metadata: Metadata,
        metadata_data: Dict,
        metadata_editor: MetadataEditor,
        settings_handler: Settings,
        separator: str
    ):
        self.base_path = base_path
        self.content_types = content_types
        self.products = products
        self.separator = separator
        self.metadata = metadata
        self.metadata_data = metadata_data
        self.metadata_editor = metadata_editor
        self.settings_handler = settings_handler
        # Create font mapping on init
        self.fonts = {
            font_name: self.settings_handler.load_font(font_name)
            for font_name in self.settings_handler.list_fonts()
        }
        self.initialize_session_state()

    def initialize_session_state(self):
        """Initialize or reset the session state with required defaults"""
        # Find first non-empty content type and its first image
        first_image = None
        first_content_type = None
        
        # Look through all content types to find the first one with images
        for content_type in self.content_types:
            available_images = self.metadata_data["structure"][content_type]["images"]
            if available_images:
                first_content_type = content_type
                first_image = available_images[0]
                break
        
        # Initialize content type states
        if "settings_content_type" not in st.session_state:
            st.session_state.settings_content_type = first_content_type or next(iter(self.content_types))
            
        if "content_type" not in st.session_state:
            st.session_state.content_type = first_content_type or next(iter(self.content_types))
        
        # Initialize selected image
        if "selected_image" not in st.session_state or not st.session_state.selected_image:
            st.session_state.selected_image = first_image
        
        # Initialize nav index based on selected image
        if "nav_index" not in st.session_state:
            if first_image:
                content_type = st.session_state.content_type
                images = self.metadata_data["structure"][content_type]["images"]
                if st.session_state.selected_image in images:
                    st.session_state.nav_index = images.index(st.session_state.selected_image)
                else:
                    st.session_state.nav_index = 0
            else:
                st.session_state.nav_index = 0

        # Initialize product related states
        # This eliminates the duplicate initialization warning
        if "product" not in st.session_state:
            if st.session_state.selected_image:
                st.session_state.product = self.metadata_data["images"][st.session_state.selected_image].get("product")
            else:
                st.session_state.product = None
                
        # Initialize other required states
        if "selected_caption_idx" not in st.session_state:
            st.session_state.selected_caption_idx = 0
                
        if "top_bar_message" not in st.session_state:
            st.session_state.top_bar_message = ""
                
        if "top_bar_message_type" not in st.session_state:
            st.session_state.top_bar_message_type = "info"
            
        # Debug logging
        logger.debug(f"Initialized session state:")
        logger.debug(f"Content type: {st.session_state.content_type}")
        logger.debug(f"Selected image: {st.session_state.selected_image}")
        logger.debug(f"Nav index: {st.session_state.nav_index}")

    def render_type_selection(self):
        """Render content type and product selection with proper product filtering"""
        col1, col2 = st.columns(2)

        with col1:
            # Content type selection remains the same
            st.selectbox(
                label="Content Type Selection",
                options=self.content_types,
                key="settings_content_type",
                on_change=self.handle_content_type_change,
                label_visibility="visible",
            )

        with col2:
            # Get current image and its product
            current_image = st.session_state.get("selected_image")
            current_product = None
            if current_image:
                current_product = self.metadata_data["images"][current_image].get("product")

            # Get content type for product list
            content_type = st.session_state.settings_content_type
            
            # Get valid products for this content type from metadata
            valid_products = [
                p["name"] 
                for p in self.metadata_data["products"][content_type]
            ] if content_type in self.metadata_data["products"] else []
            
            # Create product list with "None" option
            product_list = ["None"] + valid_products
            
            # Find proper index for current product
            default_index = (
                product_list.index(current_product)
                if current_product in product_list
                else 0  # Default to "None" if current product not valid
            )
            
            def on_product_change():
                """Handle product selection change"""
                if not current_image:
                    return

                old_product = current_product
                new_product = st.session_state.settings_product
                
                # Handle "None" selection
                if new_product == "None":
                    new_product = None

                # Don't process if no change
                if old_product == new_product:
                    return

                # Validate the change
                is_valid, error_msg = self._validate_product_assignment(
                    content_type, new_product
                )
                if not is_valid:
                    st.error(error_msg)
                    # Reset to old value
                    st.session_state.settings_product = "None" if old_product is None else old_product
                    return

                # Handle the product assignment
                self._handle_product_assignment(old_product, new_product, content_type)

            # Product selection dropdown
            st.selectbox(
                label="Product Selection",
                options=product_list,
                index=default_index,
                key="settings_product",
                on_change=on_product_change,
                label_visibility="visible"
            )

    def render_base_settings(self, settings_data):
        """Render base settings controls"""
        current_settings = self.get_current_settings()
        if not current_settings:
            st.error("Could not retrieve current settings")
            return
            
        # Get base settings from the proper location
        base_settings = current_settings.get("base_settings", {})
        current_text_type = base_settings.get("default_text_type")
        logger.debug(f"{current_text_type=}")
        logger.debug(f"{base_settings=}")
        
        if not current_text_type:
            st.error("No text type found in current settings")
            return

        # Create expander label with current text type
        expander_label = f"Base Settings (Default: {current_text_type.title()})"

        with st.expander(expander_label, expanded=False):
            # Existing text type selection
            valid_types = list(VALID_TEXT_TYPES)
            index = (
                valid_types.index(current_text_type)
                if current_text_type in valid_types
                else 0
            )

            selected_type = st.selectbox(
                "Default Text Type",
                options=valid_types,
                index=index,
                label_visibility="visible",
            )

            if selected_type != current_text_type and st.button(
                "Update Text Type", use_container_width=True
            ):
                self.handle_text_type_change(selected_type)
                st.rerun()

            st.divider()
            # product level dupe changer. 
            self._product_level_duplicate_prevention_changer_base_settings()
            
            # Settings level selector
            st.divider()
            self._render_settings_level_selector()

    def render_text_settings(self, settings_data):
        """Render text type settings controls"""
        logger.trace("\n=== Text Settings Debug ===")
        logger.trace(f"Input settings_data: {settings_data}")

        with st.expander("Text Type Settings", expanded=True):
            if not settings_data:
                logger.trace("DEBUG: No settings data provided")
                st.error("No settings data available")
                return

            # Get current image and metadata
            current_image = st.session_state.get("selected_image")
            if not current_image:
                st.error("No image selected")
                return

            image_data = self.metadata_data["images"].get(current_image)
            if not image_data:
                st.error(f"No metadata found for image: {current_image}")
                return

            # Get settings source from image data
            settings_source = image_data.get("settings_source", "default")
            content_type = image_data.get("content_type")
            product = image_data.get("product")

            logger.debug(f"Settings resolution - Source: {settings_source}, Content: {content_type}, Product: {product}")

            # Get settings based on source priority (custom > product > content > default)

            
            if settings_source == "custom" and "settings" in image_data:
                # Custom settings are stored directly in image_data
                current_settings = {"settings": image_data["settings"]}
                logger.debug("Using custom settings from image data")
            elif settings_source == "product" and product:
                current_settings = self.metadata_editor.get_settings("product", product, content_type)
                logger.debug(f"Using product settings for {product}")
            elif settings_source == "content":  # Just check settings_source is "content"
                current_settings = self.metadata_editor.get_settings("content_type", content_type)
                logger.debug(f"Using content settings for {content_type}")
            else:
                # Default is the fallback
                current_settings = self.metadata_editor.get_settings("default")
                logger.debug("Using default settings")

            if not current_settings:
                logger.debug(f"No valid settings found for source: {settings_source}")
                st.error("No valid settings found")
                return

            settings = current_settings.get("settings", {})
            current_type = settings.get("base_settings", {}).get("default_text_type")
            
            if not current_type:
                logger.trace("DEBUG: No default text type found")
                st.error("No default text type set")
                return

            logger.debug(f"{settings_source=}")
            logger.debug(f"{current_settings=}")

            text_settings = settings.get("text_settings", {}).get(current_type, {})
            if not text_settings:
                logger.trace(f"DEBUG: No settings found for type {current_type}")
                st.error(f"No settings found for text type: {current_type}")
                return

            # Font Settings & Style Value Settings
            self._font_input(current_type, text_settings)

            # Position Settings
            position = text_settings["position"]
            self._render_position_settings(position, current_type)

            # Margins
            margins = text_settings["margins"]
            self._render_margin_settings(margins, current_type)

    def _render_color_pair(
        self, text_type: str, idx: int, color_keys: List[str], color_pair: Dict
    ) -> bool:
        """Render a single color pair with delete button in a horizontal layout"""
        # Create columns with better proportions for tighter layout
        cols = st.columns([1.5, 1.5, 0.8])  # Text color, Background color, Delete

        deleted = False

        # Render color pickers
        for i, key in enumerate(color_keys):
            with cols[i]:
                st.write(f"{key.title()} {idx + 1}")  # Add number to label
                # Ensure hex color is uppercase
                color_pair[key] = st.color_picker(
                    label=f"{key} {idx + 1}",
                    value=color_pair[key],
                    label_visibility="collapsed",
                    key=f"color_{text_type}_{idx}_{key}",
                ).upper()  # Convert hex to uppercase

        # Delete button with label
        with cols[2]:
            st.write(f"Delete {idx + 1}")  # Add number to delete label
            if st.button("🗑️", key=f"delete_color_{text_type}_{idx}"):
                logger.trace(f"\n=== Deleting Color Pair {idx + 1} ===")
                logger.trace(f"Removing: {color_pair}")
                deleted = True

        return deleted

    def render_color_settings(self, text_type: str):
        """Render and manage complete color settings UI for a text type"""
        # Create notification container at top

        logger.trace("\n=== Color Settings Debug ===")
        logger.trace(f"Text type: {text_type}")

        # Get current image and its settings level
        current_image = st.session_state.get("selected_image")
        image_data = self.metadata_data["images"][current_image]
        settings_source = image_data["settings_source"]
        content_type = image_data["content_type"]
        product = image_data.get("product")

        logger.trace(f"Current image: {current_image}")
        logger.trace(f"Settings source: {settings_source}")
        logger.trace(f"Content type: {content_type}")
        logger.trace(f"Product: {product}")

        # Get settings based on source level
        if settings_source == "custom":
            settings_data = self.metadata_editor.get_settings("custom", current_image)
        elif settings_source == "product" and product:
            settings_data = self.metadata_editor.get_settings(
                "product", product, content_type
            )
        elif settings_source == "content_type":
            settings_data = self.metadata_editor.get_settings(
                "content_type", content_type
            )
        else:
            settings_data = self.metadata_editor.get_settings("default")

        logger.trace(f"Settings data retrieved: {settings_data}")

        settings = settings_data.get("settings", {})
        if not settings:
            st.warning("No settings available")
            return

        text_settings = settings.get("text_settings", {})
        logger.trace(f"Text settings found: {text_settings}")

        # Rest of the function stays the same
        current_type_settings = text_settings.get(text_type, {})
        logger.trace(f"Current type settings: {current_type_settings}")

        colors = current_type_settings.get("colors", [])
        logger.trace(f"Colors found: {colors}")

        with st.expander("Color Settings", expanded=False):
            # Display existing color pairs
            to_delete = None
            for idx, color_pair in enumerate(colors):
                if self._render_color_pair(
                    text_type, idx, color_pair.keys(), color_pair
                ):
                    to_delete = idx

            if to_delete is not None:
                colors.pop(to_delete)
                self._save_color_settings(settings)
                st.rerun()

            # Action buttons in horizontal layout
            cols = st.columns([1, 1])  # Split bottom buttons into two columns
            with cols[0]:
                if st.button("Add Color Pair", key=f"add_color_{text_type}"):
                    if colors:
                        new_pair = {k: "#FFFFFF" for k in colors[0].keys()}
                        colors.append(new_pair)
                        logger.trace(f"\n=== Adding New Color Pair ===")
                        logger.trace(f"New pair: {new_pair}")
                        self._save_color_settings(settings)
                        st.rerun()

            with cols[1]:
                if st.button("Save Colors", key=f"save_colors_{text_type}"):
                    if self._save_color_settings(settings):
                        st.session_state.show_success = True
                        st.rerun()

        # Show success message if flag is set, then clear it
        if st.session_state.pop("show_success", False):
            st.success("Settings saved successfully")

    def _get_color_keys_for_type(self, text_type: str) -> list:
        """Get the required color keys based on text type from current settings"""
        settings_data = self.get_current_settings()
        if not settings_data:
            return []

        # Navigate to the correct settings level
        settings = settings_data.get("settings", {}).get("settings", {})
        text_settings = settings.get("text_settings", {}).get(text_type, {})

        # Get colors from current settings
        colors = text_settings.get("colors", [])
        if colors:
            # Get keys from first color entry
            return list(colors[0].keys())

        logger.trace(f"Warning: No existing color keys found for {text_type}")
        return []

    def _save_color_settings(self, settings_data: dict):
        """Save updated color settings to metadata"""
        try:
            current_image = st.session_state.selected_image
            if not current_image:
                st.error("No image selected")
                return False

            # Update metadata directly
            self.metadata_data["images"][current_image]["settings_source"] = "custom"
            self.metadata_data["images"][current_image]["settings"] = settings_data

            # Save metadata to disk
            self.metadata.save()
            st.success("Color settings saved successfully")
            return True

        except Exception as e:
            st.error(f"Failed to save color settings: {str(e)}")
            return False

    def render(self):
        """Render the settings interface with proper error handling"""

        with st.container():
            # Get current image with safety check
            current_image = st.session_state.get("selected_image")
            if not current_image:
                st.warning("Please select an image to edit settings")
                return

            try:
                # Get current settings and image data with safety checks
                current_settings = self.get_current_settings()
                
                # Safely get image data
                image_data = self.metadata_data["images"].get(current_image)
                if not image_data:
                    st.error(f"No metadata found for image: {current_image}")
                    return

                settings_source = image_data.get("settings_source", "default")
                logger.debug(f"RENDER DEBUG - Current image: {current_image}")
                logger.debug(f"RENDER DEBUG - Settings source: {settings_source}")
                logger.debug(f"RENDER DEBUG - Image data: {image_data}")
                logger.debug(f"RENDER DEBUG - Current settings: {current_settings}")

                if current_settings:
                    settings_data = current_settings  # The settings are already at the right level

                    self.render_type_selection()
                    self.render_base_settings(settings_data)
                    self.render_text_settings(settings_data)

                    # Get text type safely with proper fallback
                    text_type = settings_data.get("base_settings", {}).get(
                        "default_text_type", "plain"
                    )
                    if not text_type:
                        st.warning("No default text type set")
                        return

                    self.render_color_settings(text_type)
                    self.render_preview_expander(settings_data)

                    # Debug view of settings
                    with st.expander("Debug Settings View"):
                        st.json(settings_data)
                else:
                    st.warning("No settings available for the selected image")

            except Exception as e:
                logger.error(f"Error in render method: {str(e)}")
                st.error("An error occurred while rendering settings")

    def get_current_settings(self):
        """Get settings and product info for current image based on settings level hierarchy"""
        if not self.metadata_editor:
            logger.error("ERROR: metadata_editor is None!")
            return None

        current_image = st.session_state.get("selected_image")
        if not current_image:
            logger.debug("No image selected")
            return None

        try:
            # Safely get image data with detailed logging
            image_data = self.metadata_data["images"].get(current_image)
            if not image_data:
                logger.error(f"No metadata found for image: {current_image}")
                return None

            settings_source = image_data.get("settings_source", "default")
            logger.debug(f"SETTINGS DEBUG - Image: {current_image}")
            logger.debug(f"SETTINGS DEBUG - Raw image data: {image_data}")
            logger.debug(f"SETTINGS DEBUG - Settings source: {settings_source}")

            # If settings_source is content, get content type settings
            if settings_source == "content":
                content_type = image_data.get("content_type")
                logger.debug(f"SETTINGS DEBUG - Getting content type settings for: {content_type}")
                content_settings = self.metadata_editor.get_settings("content_type", content_type)
                logger.debug(f"SETTINGS DEBUG - Content settings retrieved: {content_settings}")
                if content_settings:
                    return content_settings.get("settings")
                logger.error(f"No content type settings found for {content_type}")

            # If settings_source is default OR settings are None, get from default template
            if settings_source == "default" or image_data.get("settings") is None:
                logger.debug("SETTINGS DEBUG - Getting default settings")
                default_result = self.metadata_editor.get_settings("default")
                logger.debug(f"SETTINGS DEBUG - Default settings result: {default_result}")
                
                if not default_result:
                    logger.error("Failed to get default settings")
                    return None
                    
                settings = default_result.get("settings")
                logger.debug(f"SETTINGS DEBUG - Extracted settings from default: {settings}")
                return settings

            # For all other cases, return the stored settings
            logger.debug(f"SETTINGS DEBUG - Returning stored settings: {image_data.get('settings')}")
            
            return image_data.get("settings")

        except Exception as e:
            logger.error(f"Error getting settings: {str(e)}")
            logger.error(f"Full exception: {str(e.__class__.__name__)}: {str(e)}")
            return None

    def handle_text_type_change(self, new_text_type: str):
        """Handle changing text type in settings"""
        logger.debug("\n=== Text Type Change Debug ===")
        logger.debug(f"1. Starting text type change to: {new_text_type}")

        current_image = st.session_state.selected_image
        if not current_image:
            logger.error("No image selected")
            return

        # Get current settings
        image_data = self.metadata_data["images"][current_image]
        settings_source = image_data["settings_source"]
        logger.debug(f"2. Current settings source: {settings_source}")

        # Get the settings we're currently using
        if settings_source == "content":
            content_type = image_data["content_type"]
            current_settings = self.metadata_data["settings"][content_type]["content"]
            logger.debug(f"3a. Using content settings for {content_type}")
        elif settings_source == "product":
            product = image_data["product"]
            content_type = image_data["content_type"]
            for group, settings in self.metadata_data["settings"][content_type].items():
                if group != "content":
                    products = {p.strip() for p in group[1:-1].split(",")}
                    if product in products:
                        current_settings = settings
                        break
            logger.debug(f"3b. Using product settings for {product}")
        else:
            current_settings = image_data.get("settings")
            logger.info("3c. Using custom/default settings")

        logger.debug(f"4. Current settings: {current_settings}")

        # Create a copy of current settings
        settings_data = current_settings.copy() if current_settings else {}
        logger.debug("5. Created settings copy")
        
        # Update settings with new text type
        if new_text_type not in settings_data.get("text_settings", {}):
            logger.debug(f"6. Adding new text type {new_text_type} settings")
            # Get default settings for new type
            default_settings = self.metadata_editor.get_settings(level="default")["settings"]
            default_type_settings = default_settings["text_settings"][new_text_type]
            settings_data.setdefault("text_settings", {})[new_text_type] = default_type_settings.copy()

        # Update default text type
        settings_data.setdefault("base_settings", {})["default_text_type"] = new_text_type
        logger.debug(f"7. Updated default text type to {new_text_type}")

        # Always switch to custom settings when making changes
        try:
            logger.debug("8. Applying changes...")
            self.metadata_editor.edit_image(
                image_name=current_image,
                data={"settings_source": "custom", "settings": settings_data},
            )
            logger.debug("9. Saved changes via metadata_editor")
            
            # Update local metadata_data
            self.metadata_data["images"][current_image]["settings_source"] = "custom"
            self.metadata_data["images"][current_image]["settings"] = settings_data
            logger.debug("10. Updated local metadata copy")

            self.metadata.save()
            logger.debug("11. Saved metadata to disk")

        except Exception as e:
            logger.error(f"ERROR during save: {str(e)}")
            st.error("Failed to save settings changes")
            return

        logger.debug("=== Text Type Change Complete ===\n")

    def add_color_picker(self, text_type: str, color_index: int):
        """Add color picker UI elements for a text type"""
        settings_data = self.get_current_settings()
        if not settings_data:
            return

        colors = settings_data["text_settings"][text_type]["colors"]
        if color_index >= len(colors):
            colors.append({})  # Add new color slot

        required_keys = VALID_TEXT_TYPES[text_type]["required_color_keys"]
        col1, col2 = st.columns(2)

        for key in required_keys:
            with col1:
                st.write(f"Color {color_index + 1} - {key}")
            with col2:
                colors[color_index][key] = st.color_picker(
                    f"Pick {key} color ###{color_index}",
                    value=colors[color_index].get(key, "#FFFFFF"),
                    key=f"color_{text_type}_{key}_{color_index}",
                )

    def _font_input(self, text_type: str, text_settings: Dict) -> None:
        """Render font selection dropdown and font size input in one row"""
        # Create columns with 3:2:2 ratio for font, size, and style
        cols = st.columns([4, 2, 2])

        # Get current font name from path
        current_font_name = text_settings["font"].split(".")[-2]
        settings_data = self.get_current_settings()

        # Font dropdown
        with cols[0]:
            selected_font = st.selectbox(
                "Font",
                options=list(self.fonts.keys()),
                index=list(self.fonts.keys()).index(current_font_name),
                key=f"font_select_{text_type}",
            )

            # Apply font change if needed
            if selected_font != current_font_name:
                logger.trace(f"\n=== Font Change ===")
                logger.trace(f"Old font: {text_settings['font']}")
                new_font = self.fonts[selected_font]
                logger.trace(f"New font: {new_font}")

                # Update settings with new font
                settings_data["text_settings"][text_type]["font"] = new_font

                # Apply changes via metadata editor
                image_name = st.session_state.get("selected_image")
                self.metadata_editor.edit_image(
                    image_name, {"settings": settings_data, "settings_source": "custom"}
                )
                self.metadata.save()
                st.rerun()

        # Font size input (keeping the same structure for consistency)
        with cols[1]:
            font_size = st.number_input(
                "Font Size",
                min_value=10,
                max_value=200,
                value=text_settings["font_size"],
                key=f"font_size_{text_type}",
            )

            if font_size != text_settings["font_size"]:
                logger.trace(f"\n=== Font Size Change ===")
                logger.trace(f"Old size: {text_settings['font_size']}")
                logger.trace(f"New size: {font_size}")

                # Update settings with new font size
                settings_data["text_settings"][text_type]["font_size"] = font_size
                image_name = st.session_state.get("selected_image")
                self.metadata_editor.edit_image(
                    image_name, {"settings": settings_data, "settings_source": "custom"}
                )
                self.metadata.save()
                st.rerun()

        # Style value input
        with cols[2]:
            style_type = text_settings["style_type"]
            style_value = text_settings["style_value"]
            style_label = style_type.replace("_", " ").title()

            new_style_value = st.number_input(
                style_label,
                min_value=0,
                max_value=100,
                value=style_value,
                key=f"style_value_{text_type}",
            )

            if new_style_value != style_value:
                logger.trace(f"\n=== Style Value Change ===")
                logger.trace(f"Old value: {style_value}")
                logger.trace(f"New value: {new_style_value}")

                settings_data["text_settings"][text_type][
                    "style_value"
                ] = new_style_value
                image_name = st.session_state.get("selected_image")
                self.metadata_editor.edit_image(
                    image_name, {"settings": settings_data, "settings_source": "custom"}
                )
                self.metadata.save()
                st.rerun()

    def _render_position_settings(self, position: dict, current_type: str):
        """Render position settings UI and handle updates"""

        def update_position_setting(setting_name: str, new_value, old_value):
            """Helper function to update position settings"""
            
            if new_value != old_value:
                try:
                    logger.debug(f"\n=== Position Change Debug ===")
                    logger.debug(f"Old {setting_name}: {old_value}")
                    logger.debug(
                        f"New {setting_name}: {list(new_value) if isinstance(new_value, tuple) else new_value}"
                    )

                    settings_data = self.get_current_settings()
                    # logger.critical(f"update position setting {settings_data=}")  # TODO 
                    new_settings = settings_data.copy()
                    new_settings["text_settings"][current_type]["position"][
                        setting_name
                    ] = (list(new_value) if isinstance(new_value, tuple) else new_value)

                    self.settings_handler.settings_validator.validate_settings(new_settings)

                    settings_data = new_settings

                    image_name = st.session_state.get("selected_image")
                    logger.testing(f"Updating image: {image_name}")
                    logger.testing(f"New settings data: {settings_data}")

                    self.metadata_editor.edit_image(
                        image_name, {"settings": settings_data, "settings_source": "custom"}
                    )
                    st.session_state.top_bar_message = "changed settings !"
                    st.session_state.top_bar_message_type = "success"
                    self.metadata.save()
                    st.rerun()
                    
                except ValueError as e:
                    # Show error in top bar and don't update settings
                    st.session_state.top_bar_message = str(e)
                    st.session_state.top_bar_message_type = "error"
                    st.rerun()

        # Position and jitter controls in rows
        # Vertical controls
        vcol1, vcol2 = st.columns([0.7, 0.3])
        with vcol1:
            vertical_pos = st.slider(
                "Vertical Position",
                min_value=0.0,
                max_value=1.0,
                value=tuple(position["vertical"]),
                label_visibility="visible",
                key=f"vertical_pos_{current_type}",
            )
            update_position_setting("vertical", vertical_pos, tuple(position["vertical"]))
            
        with vcol2:
            vertical_jitter = st.number_input(
                "V Jitter",
                min_value=0.0,
                max_value=0.1,
                value=position["vertical_jitter"],
                label_visibility="visible",
                key=f"vertical_jitter_{current_type}",
            )
            update_position_setting(
                "vertical_jitter", vertical_jitter, position["vertical_jitter"]
            )

        # Horizontal controls
        hcol1, hcol2 = st.columns([0.7, 0.3])
        with hcol1:
            horizontal_pos = st.slider(
                "Horizontal Position",
                min_value=0.0,
                max_value=1.0,
                value=tuple(position["horizontal"]),
                label_visibility="visible",
                key=f"horizontal_pos_{current_type}",
            )
            update_position_setting(
                "horizontal", horizontal_pos, tuple(position["horizontal"])
            )
            
        with hcol2:
            horizontal_jitter = st.number_input(
                "H Jitter",
                min_value=0.0,
                max_value=0.1,
                value=position["horizontal_jitter"],
                label_visibility="visible",
                key=f"horizontal_jitter_{current_type}",
            )
            update_position_setting(
                "horizontal_jitter", horizontal_jitter, position["horizontal_jitter"]
            )

    def _render_margin_settings(self, margins: dict, current_type: str):
        """Render margin settings UI"""

        def update_margin_setting(setting_name: str, new_value_int, old_value):
            """Helper function to update margin settings"""
            # Convert integer input to float (divide by 100)
            new_value = new_value_int / 100.0
            old_value_int = int(old_value * 100)

            if new_value_int != old_value_int:
                logger.trace(f"\n=== Margin Change Debug ===")
                logger.trace(f"Old {setting_name}: {old_value} (from {old_value_int})")
                logger.trace(f"New {setting_name}: {new_value} (from {new_value_int})")

                settings_data = self.get_current_settings()
                settings_data["text_settings"][current_type]["margins"][
                    setting_name
                ] = new_value

                image_name = st.session_state.get("selected_image")
                logger.trace(f"Updating image: {image_name}")
                logger.trace(f"New settings data: {settings_data}")

                self.metadata_editor.edit_image(
                    image_name, {"settings": settings_data, "settings_source": "custom"}
                )
                self.metadata.save()
                st.rerun()

        # Create 4 equal columns
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            top_margin = st.number_input(
                "Top %",
                min_value=0,
                max_value=50,
                value=int(margins["top"] * 100),
                label_visibility="visible",
                key=f"margin_top_{current_type}",
            )
            update_margin_setting("top", top_margin, margins["top"])

        with col2:
            bottom_margin = st.number_input(
                "Bottom %",
                min_value=0,
                max_value=50,
                value=int(margins["bottom"] * 100),
                label_visibility="visible",
                key=f"margin_bottom_{current_type}",
            )
            update_margin_setting("bottom", bottom_margin, margins["bottom"])

        with col3:
            left_margin = st.number_input(
                "Left %",
                min_value=0,
                max_value=50,
                value=int(margins["left"] * 100),
                label_visibility="visible",
                key=f"margin_left_{current_type}",
            )
            update_margin_setting("left", left_margin, margins["left"])

        with col4:
            right_margin = st.number_input(
                "Right %",
                min_value=0,
                max_value=50,
                value=int(margins["right"] * 100),
                label_visibility="visible",
                key=f"margin_right_{current_type}",
            )
            update_margin_setting("right", right_margin, margins["right"])

    def _render_settings_level_selector(self):
        """Render UI for changing settings level"""
        # Get current settings info
        current_image = st.session_state.get("selected_image")
        if not current_image:
            return

        # Get current image metadata using our existing method
        settings_data = self.get_current_settings()
        if not settings_data:
            return

        # Get image info from settings data
        current_level = settings_data.get("settings_source", "default")
        content_type = settings_data.get("content_type")
        product = settings_data.get("product")

        # Get settings following the metadata structure:
        # settings -> content_type -> "content" -> actual settings
        content_type_settings = (
            self.metadata_editor.metadata.get("settings", {})  # settings dict
            .get(content_type, {})  # content type level
            .get("content")
        )  # actual settings

        levels_status = {
            "default": {"available": True, "reason": None},
            "content": {
                "available": bool(content_type and content_type_settings),
                "reason": (
                    "No content type settings exist"
                    if content_type
                    else "Image has no content type defined"
                ),
            },
            "product": {
                "available": bool(
                    product
                    and content_type
                    and self.metadata_editor.get_settings(
                        "product", product, content_type
                    )
                ),
                "reason": (
                    "No product settings exist"
                    if product
                    else "Image has no product defined"
                ),
            },
        }

        # Get current image metadata
        current_image = st.session_state.get("selected_image")
        image_data = self.metadata_editor.metadata["images"][current_image]
        image_content_type = image_data.get("content_type")
        image_product = image_data.get("product")

        # Debug both content type and product settings
        settings = self.metadata_editor.metadata.get("settings", {})
        logger.trace("\n=== Settings Structure Debug === {settings level selector}")
        logger.trace(f"{image_data=}")
        logger.trace(f"Image content type: {image_content_type}")
        logger.trace(f"Image product: {image_product}")

        # Get content type settings
        content_type_settings = settings.get(image_content_type, {})
        content_settings = content_type_settings.get("content", {})

        # Get product settings if product exists
        product_settings = None
        if image_product:
            product_key = f"[{image_product}]"
            product_settings = content_type_settings.get(product_key, {})

        logger.trace(f"Content type settings: {content_type_settings}")
        logger.trace(f"Content settings: {content_settings}")
        logger.trace(f"Product settings: {product_settings}")

        # Update levels status with proper checks
        levels_status = {
            "default": {"available": True, "reason": None},
            "content": {
                "available": bool(image_content_type and content_settings),
                "reason": (
                    "No content settings exist"
                    if image_content_type
                    else "Image has no content type defined"
                ),
            },
            "product": {
                "available": bool(image_product and product_settings),
                "reason": (
                    "No product settings exist"
                    if image_product
                    else "Image has no product defined"
                ),
            },
        }

        st.write("Change Settings Level")

        # Simplify the options creation
        options = ["default"]  # Always include default first
        if current_level != "content":
            options.append(
                f"content ({levels_status['content']['reason']})"
                if not levels_status["content"]["available"]
                else "content"
            )
        if current_level != "product":
            options.append(
                f"product ({levels_status['product']['reason']})"
                if not levels_status["product"]["available"]
                else "product"
            )

        target_level = st.selectbox(
            "Switch to:",
            options=options,
            index=None,  # No default selection
            label_visibility="collapsed",
        )

        # Only show button if a level is selected
        if target_level:
            # Extract the actual level from the label if it has a reason
            selected_level = target_level.split(" (")[0]

            if st.button(
                f"Confirm switch to {selected_level} settings",
                disabled=not levels_status[selected_level]["available"],
            ):
                current_image = st.session_state.get("selected_image")
                image_data = self.metadata_data["images"][current_image]
                content_type = image_data.get("content_type")
                product = image_data.get("product")
                
                # Get the settings for the new level BEFORE switching
                new_settings = None
                if selected_level == "default":
                    new_settings = self.metadata_editor.get_settings("default")
                elif selected_level == "content":
                    new_settings = self.metadata_editor.get_settings("content_type", content_type)
                elif selected_level == "product":
                    new_settings = self.metadata_editor.get_settings("product", product, content_type)
                
                # Only proceed if we got valid settings
                if new_settings and "settings" in new_settings:
                    self.metadata_editor.edit_image(
                        current_image, 
                        {
                            "settings": new_settings["settings"],
                            "settings_source": selected_level
                        }
                    )
                    self.metadata.save()
                    st.rerun()
                else:
                    st.error(f"Could not load settings for {selected_level} level")

    def _move_image_between_content_types(
        self, image_name: str, new_content_type: str
    ) -> None:
        """Move image file between content type folders and update metadata.

        Args:
            image_name: Name of image to move
            new_content_type: Destination content type folder
        """
        logger.trace("\n=== Moving Image Between Content Types ===")

        # Get current image data
        image_data = self.metadata_data["images"][image_name]
        old_content_type = image_data["content_type"]

        # Get paths
        old_path = self.base_path / old_content_type / image_name
        new_path = self.base_path / new_content_type / image_name

        logger.trace(
            f"Moving {image_name} from {old_content_type} to {new_content_type}"
        )
        logger.trace(f"Old path: {old_path}")
        logger.trace(f"New path: {new_path}")

        try:
            # Physically move the file
            old_path.rename(new_path)

            # Update metadata structure
            # Remove from old content type
            old_images = self.metadata_data["structure"][old_content_type]["images"]
            self.metadata_data["structure"][old_content_type]["images"] = [
                img for img in old_images if img != image_name
            ]

            # Add to new content type
            self.metadata_data["structure"][new_content_type]["images"].append(
                image_name
            )
            self.metadata_data["structure"][new_content_type]["images"].sort()

            # Update image metadata
            self.metadata_editor.edit_image(
                image_name=image_name,
                data={
                    "content_type": new_content_type,
                    "product": None,  # Reset product when changing content type
                    "settings_source": "default",  # Reset to default settings
                },
            )

            # Save metadata
            self.metadata.save()

            logger.trace("File moved and metadata updated successfully")

        except Exception as e:
            logger.error(f"Failed to move image: {str(e)}")
            st.error(f"Failed to move image: {str(e)}")
            raise

    def handle_content_type_change(self):
        """Enhanced content type change handler with improved state management"""
        current_image = st.session_state.selected_image
        new_content_type = st.session_state.settings_content_type
        
        if not current_image:
            return
        
        try:
            # Get current image data with validation
            image_data = self.metadata_data["images"][current_image]
            if not image_data:
                raise ValueError(f"No metadata found for image: {current_image}")
                
            old_content_type = image_data["content_type"]
            old_product = image_data.get("product")
            
            if old_content_type == new_content_type:
                return
            
            # Handle product count updates
            if old_product:
                logger.debug(f"Updating product count for {old_product}")
                # Decrement old product count
                self.metadata_editor._update_product_count(
                    old_content_type, old_product, increment=False
                )
            
            # Physical file move
            old_path = self.base_path / old_content_type / current_image
            new_path = self.base_path / new_content_type / current_image
            
            if not old_path.exists():
                raise FileNotFoundError(f"Source file not found: {old_path}")
                
            old_path.rename(new_path)
            
            # Update metadata structure
            old_images = self.metadata_data["structure"][old_content_type]["images"]
            new_images = self.metadata_data["structure"][new_content_type]["images"]
            
            if current_image in old_images:
                old_images.remove(current_image)
            if current_image not in new_images:
                new_images.append(current_image)
                new_images.sort()
                
            # Update image metadata
            self.metadata_data["images"][current_image].update({
                "content_type": new_content_type,
                "product": None,  # Reset product
                "settings_source": "default",
                "settings": None
            })
            
            # Update session state
            st.session_state.content_type = new_content_type
            st.session_state.settings_product = None
            st.session_state.product = None
            
            # Update navigation index
            try:
                new_index = new_images.index(current_image)
                st.session_state.nav_index = new_index
            except ValueError:
                st.session_state.nav_index = 0
                
            # Save changes
            self.metadata.save()
            
            # Set success message
            st.session_state.top_bar_message = f"Image moved to {new_content_type}"
            st.session_state.top_bar_message_type = "success"
            
        except Exception as e:
            error_msg = f"Failed to change content type: {str(e)}"
            logger.error(error_msg)
            st.session_state.top_bar_message = error_msg
            st.session_state.top_bar_message_type = "error"
            raise

    def _validate_product_assignment(
        self, content_type: str, product: str
    ) -> tuple[bool, str]:
        """Validate if a product can be assigned.
        Only checks if product exists in content type.
        """
        if not product:
            return True, ""

        # Only check if product exists
        if any(p["name"] == product for p in self.metadata_data["products"][content_type]):
            return True, ""
            
        return False, f"Product '{product}' not found in content type '{content_type}'"

    def _render_product_assignment(self):
        """Render product assignment UI controls"""
        current_image = st.session_state.get("selected_image")
        if not current_image:
            return

        image_data = self.metadata_data["images"][current_image]
        content_type = image_data["content_type"]
        current_product = image_data.get("product")
        error_msg = ""  # Initialize error_msg at the start!

        # Create columns for product selection and info
        col1, col2 = st.columns([3, 2])

        with col1:
            # Get available products for content type
            available_products = ["None"]  # Add None as first option
            products_info = {}  # Store product info for display

            for prod in self.metadata_data["products"][content_type]:
                name = prod["name"]
                if "current_count" not in prod:
                    prod["current_count"] = 0
                products_info[name] = {
                    "current": prod["current_count"],
                    "min": prod["min_occurrences"],
                }
                available_products.append(name)

            # Show product dropdown
            selected_product = st.selectbox(
                "Assign Product",
                options=available_products,
                index=(
                    available_products.index(current_product)
                    if current_product in available_products
                    else 0
                ),
                key=f"product_select_{current_image}",
            )

        # Show product info in second column
        with col2:
            if selected_product != "None":
                info = products_info.get(selected_product)
                if info:
                    st.write(f"Usage: {info['current']}/{info['min']}")

        # Only show assign button if selection changed
        if selected_product != (current_product or "None"):
            is_valid, error_msg = self._validate_product_assignment(
                content_type, selected_product if selected_product != "None" else None
            )

            if st.button(
                "Assign Product",
                disabled=not is_valid,
                use_container_width=True,
                key=f"assign_product_{current_image}",
            ):
                self._handle_product_assignment(
                    current_product, selected_product, content_type
                )
                st.rerun()

        if error_msg:
            st.error(error_msg)

    def _handle_product_assignment(
        self, old_product: str, new_product: str, content_type: str
    ):
        """Handle product assignment including count updates"""
        try:
            current_image = st.session_state.get("selected_image")
            if not current_image:
                return

            # Prevent setting product to None
            if new_product == "None":
                st.error("Cannot set product to None. Please select a valid product.")
                return

            # Just validate product exists
            is_valid, error_msg = self._validate_product_assignment(content_type, new_product)
            if not is_valid:
                st.error(error_msg)
                return

            # Handle count updates
            if old_product:
                self.metadata_editor._update_product_count(
                    content_type, old_product, increment=False
                )

            if new_product:
                self.metadata_editor._update_product_count(
                    content_type, new_product, increment=True
                )

            # Update image metadata
            self.metadata_editor.edit_image(current_image, {"product": new_product})
            
            # Save metadata
            self.metadata.save()
            
            # Set success message in top bar
            st.session_state.top_bar_message = f"Product updated to: {new_product or 'None'}"
            st.session_state.top_bar_message_type = "success"

        except Exception as e:
            st.session_state.top_bar_message = f"Failed to update product: {str(e)}"
            st.session_state.top_bar_message_type = "error"
            logger.error(f"Product assignment error: {str(e)}")
            # Attempt to rollback counts
            if old_product:
                self.metadata_editor._update_product_count(
                    content_type, old_product, increment=True
                )
            if new_product:
                self.metadata_editor._update_product_count(
                    content_type, new_product, increment=False
                )

    """
    def handle_content_type_change(self):
        "" "Updated content type change handler with product management" ""
        print("\n=== Content Type Change Handler ===")

        current_image = st.session_state.selected_image
        new_content_type = st.session_state.settings_content_type

        print(f"Current image: {current_image}")
        print(f"New content type: {new_content_type}")

        if not current_image:
            return

        try:
            # Get current image data
            image_data = self.metadata_data["images"][current_image]
            old_content_type = image_data["content_type"]
            old_product = image_data.get("product")

            if old_content_type == new_content_type:
                return

            # Handle product count if needed
            if old_product:
                print(f"Decrementing count for product {old_product}")
                self.metadata_editor._update_product_count(
                    old_content_type, old_product, increment=False
                )

            # Physical move and metadata updates remain the same
            old_path = self.base_path / old_content_type / current_image
            new_path = self.base_path / new_content_type / current_image
            old_path.rename(new_path)

            # Update metadata structure
            self.metadata_data["structure"][old_content_type]["images"].remove(
                current_image
            )
            self.metadata_data["structure"][new_content_type]["images"].append(
                current_image
            )
            self.metadata_data["structure"][new_content_type]["images"].sort()

            # Update image metadata - note product is reset to None
            self.metadata_data["images"][current_image].update(
                {
                    "content_type": new_content_type,
                    "product": None,  # Reset product when changing content type
                    "settings_source": "default",
                    "settings": None,
                }
            )

            # Update session states
            st.session_state.content_type = new_content_type
            st.session_state.settings_product = None
            st.session_state.product = None

            # Update nav index
            images = self.metadata_data["structure"][new_content_type]["images"]
            if current_image in images:
                st.session_state.nav_index = images.index(current_image)

            # Save metadata
            self.metadata.save()

            # st.success(f"Image moved to {new_content_type}")
            st.session_state.top_bar_message = f"Image moved to {new_content_type}"
            st.session_state.top_bar_message_type = "success"

        except Exception as e:
            print(f"ERROR: {str(e)}")
            logger.error(f"Failed to change content type: {str(e)}")
            st.error(f"Failed to change content type: {str(e)}")
        """

    def _product_level_duplicate_prevention_changer_base_settings(self):
        current_image = st.session_state.selected_image
        if current_image:
            image_data = self.metadata_data["images"][current_image]
            content_type = image_data["content_type"]
            product = image_data["product"]

            if product:
                # Create two columns for the state and button
                col1, col2 = st.columns([1, 2])

                # Get current state
                product_info = next(
                    (
                        p
                        for p in self.metadata_data["products"][content_type]
                        if p["name"] == product
                    ),
                    None,
                )
                current_state = (
                    product_info["prevent_duplicates"] if product_info else False
                )

                # Display current state in first column
                with col1:
                    st.write(f"Current: {current_state}")

                # Display toggle button in second column
                with col2:
                    if st.button("Toggle Duplicate Prevention"):
                        # Toggle logic here
                        if product_info:
                            product_info['prevent_duplicates'] = not current_state
                            self.metadata.save()  # Save changes
                            st.rerun()  # Force UI refresh
            else:
                st.button(
                    "Toggle Duplicate Prevention",
                    disabled=True,
                    help="Select a product first",
                )

    def get_available_captions(self, content_type: str, product: str, captions_data: dict) -> List[str]:
        """Get available captions based on product duplication rules
        
        Args:
            content_type: Type of content (hook, content, cta)
            product: Product name for the image
            captions_data: Loaded captions data from CaptionsHelper
            
        Returns:
            List of available captions based on product rules
        """
        # Get product settings from metadata
        product_settings = next(
            (p for p in self.metadata_data['products'][content_type] 
            if p['name'] == product),
            None
        )
        
        if not product_settings:
            st.session_state.top_bar_message = f"Product is '{product}'. If None, no captions :("
            st.session_state.top_bar_message_type = "warning"
            return []
        
        prevent_duplicates = product_settings['prevent_duplicates']
        captions = []
        
        if prevent_duplicates:
            # Only show captions for this specific product
            captions.extend(captions_data['by_type'][content_type].get(product, []))
        elif product != 'all':
            # Show this product's captions
            captions.extend(captions_data['by_type'][content_type].get(product, []))
        else:
            # Product is 'all' and duplicates allowed - show all captions except from prevent_duplicate products
            for prod, prod_captions in captions_data['by_type'][content_type].items():
                # Check if this product allows duplicates
                prod_settings = next(
                    (p for p in self.metadata_data['products'][content_type] 
                    if p['name'] == prod),
                    None
                )
                if prod_settings and not prod_settings['prevent_duplicates']:
                    captions.extend(prod_captions)
        
        return captions
    

    def render_preview_expander(self, settings_data):
        """Render preview expander with corrected content types and products access"""
        with st.expander("Preview Settings", expanded=True):
            # Check if an image is selected
            current_image = st.session_state.get('selected_image')
            if not current_image:
                st.warning("Please select an image to preview")
                return
                
            try:
                # Get image metadata with safety checks
                image_data = self.metadata_data["images"].get(current_image)
                if not image_data:
                    st.error(f"No metadata found for image: {current_image}")
                    return
                    
                content_type = image_data.get("content_type")
                if not content_type:
                    st.error("No content type found for image")
                    return
                    
                product = image_data.get("product")
                
                # Verify captions.csv exists
                captions_csv_path = self.base_path / "captions.csv"
                if not captions_csv_path.exists():
                    st.error("Captions file not found")
                    return
                
                # Get captions using the class's content_types and products
                try:
                    captions_data = CaptionsHelper.get_captions(
                        captions_csv_path,
                        content_types=self.content_types,  # Use class's content_types
                        products=self.products,  # Use class's products dictionary
                        separator=self.separator  # Pass separator to get_captions
                    )
                except Exception as e:
                    st.error(f"Error loading captions: {str(e)}")
                    logger.error(f"Caption loading error: {str(e)}")
                    return
                
                # Get available captions with safety checks
                captions = self.get_available_captions(content_type, product, captions_data)
                
                # Initialize caption selection if needed
                if "selected_caption_idx" not in st.session_state:
                    st.session_state.selected_caption_idx = 0
                    
                # Reset index if it's out of bounds
                if captions and st.session_state.selected_caption_idx >= len(captions):
                    st.session_state.selected_caption_idx = 0
                
                # Two columns for buttons
                col1, col2 = st.columns(2)
                
                # Generate button
                with col1:
                    generate_enabled = bool(captions)  # Only enable if we have captions
                    if st.button("Generate Preview", 
                                use_container_width=True,
                                disabled=not generate_enabled):
                        if captions:  # Double-check we have captions
                            try:
                                # Get selected caption
                                selected_caption = captions[st.session_state.selected_caption_idx]
                                
                                # Get current image path
                                image_path = self.base_path / st.session_state.content_type / current_image
                                
                                # Get text type from settings
                                text_type = settings_data.get('base_settings', {}).get('default_text_type', 'plain')
                                
                                # Generate preview
                                preview_image = self.generate_preview(
                                    settings_data=settings_data,
                                    text_type=text_type,
                                    colour_index=0,
                                    image_path=str(image_path),
                                    text=selected_caption
                                )
                                
                                # Save preview image
                                preview_dir = self.base_path / "preview"
                                preview_dir.mkdir(exist_ok=True)
                                preview_path = preview_dir / f"{current_image}"
                                preview_image.save(str(preview_path))
                                
                                # Update session state with preview path
                                st.session_state.preview_image_path = str(preview_path)
                                
                                # Force rerun to update display
                                st.rerun()
                                
                            except Exception as e:
                                logger.error(f"Preview generation failed: {str(e)}")
                                st.error(f"Failed to generate preview: {str(e)}")

                # Reset button
                with col2:
                    if st.button("Reset Preview", use_container_width=True):
                        # Clear preview path from session state
                        if "preview_image_path" in st.session_state:
                            # Delete preview file if it exists
                            preview_path = Path(st.session_state.preview_image_path)
                            if preview_path.exists():
                                preview_path.unlink()
                            del st.session_state.preview_image_path
                            st.rerun()

                # Show captions if available
                if captions:
                    st.selectbox(
                        "Select Caption",
                        range(len(captions)),
                        index=st.session_state.selected_caption_idx,
                        format_func=lambda x: f"[{x}] {captions[x][:90]}",
                        key="selected_caption_idx"
                    )
                    
                    st.divider()
                    st.write("Available Captions:")
                    for idx, caption in enumerate(captions):
                        st.text(f"[{idx}] {caption}")
                else:
                    if product:
                        st.info(f"No captions available for {content_type} with product {product}")
                    else:
                        st.info(f"No captions available for {content_type}")
                
            except Exception as e:
                logger.error(f"Error in preview expander: {str(e)}")
                st.error(f"An error occurred while loading the preview: {str(e)}")

    def generate_preview(self, settings_data: dict, text_type: str, colour_index: int, 
                        image_path: str, text: str):
        """
        Wrapper function to generate preview images that can be reused across components
        
        Args:
            settings_data (dict): Complete settings dictionary
            text_type (str): Type of text (plain/highlight)
            colour_index (int): Index of color pair to use
            image_path (str): Path to source image
            text (str): Caption text to render
            
        Returns:
            PIL.Image: Generated preview image
        """
        try:
            from text.generate_image import generate_image
            
            logger.trace(f"PREVIEW // About to call generate_image with settings: {settings_data}")
            
            result = generate_image(
                settings=settings_data,
                text_type=text_type,
                colour_index=colour_index,
                image_path=image_path,
                text=text
            )
            
            logger.trace("PREVIEW // generate_image call completed")
            return result
            
        except Exception as e:
            logger.error(f"Preview generation failed: {str(e)}")
            raise