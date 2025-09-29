from pathlib import Path
import streamlit as st
from typing import Set, Dict, Any
from config.logging import logger
from content_manager.settings.settings_constants import VALID_IMAGE_EXTENSIONS
from content_manager.metadata.metadata import Metadata
from content_manager.metadata.metadata_editor import MetadataEditor
from PIL import Image

class ImageManager:
    """Simple image display manager"""
    
    def __init__(self, base_path: Path, content_types: Set[str], products: Dict[str, Any], 
                 metadata: Metadata, metadata_data: Dict, metadata_editor: MetadataEditor):
        self.base_path = base_path
        self.content_types = content_types
        self.products = products
        self.metadata = metadata
        self.valid_extensions = VALID_IMAGE_EXTENSIONS
        self.metadata_data = metadata_data
        self.metadata_editor = metadata_editor
        self.initialize_state()
        
    def initialize_state(self):
        """Initialize image display state"""
        if "current_image" not in st.session_state:
            st.session_state.current_image = None
            
        if "image_settings" not in st.session_state:
            st.session_state.image_settings = None
    
    def display_image(self, image_path: Path):
        """Display a single image"""
        if not image_path.exists():
            st.error(f"Image not found: {image_path}")
            return
            
        if image_path.suffix not in self.valid_extensions:
            st.error(f"Invalid image type: {image_path.suffix}")
            return
            
        try:
            st.image(str(image_path))
        except Exception as e:
            st.error(f"Error displaying image: {e}")

    def render_image(self):
        """Render the current image with safety checks"""
        # Verify required session state exists
        if not all(key in st.session_state for key in ['content_type', 'selected_image']):
            st.error("Required session state not initialized")
            return
            
        if not st.session_state.content_type or not st.session_state.selected_image:
            st.warning("Please select an image to display")
            return
            
        try:
            # Check if a preview image exists
            if "preview_image_path" in st.session_state:
                image_path = Path(st.session_state.preview_image_path)
                if not image_path.exists():
                    # If preview doesn't exist, fall back to original
                    image_path = self.base_path / st.session_state.content_type / st.session_state.selected_image
                logger.debug(f"Using preview image path: {image_path}")
            else:
                # Use original image path
                image_path = self.base_path / st.session_state.content_type / st.session_state.selected_image
                logger.debug(f"Using original image path: {image_path}")
            
            # Display the image
            st.image(str(image_path), use_container_width=True)
            
        except Exception as e:
            logger.error(f"Error displaying image: {str(e)}")
            st.error("Failed to display image")