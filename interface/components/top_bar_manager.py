import streamlit as st  # type: ignore
from pathlib import Path
from typing import Set, Dict, Any, List
import json
from content_manager.settings.settings_constants import VALID_IMAGE_EXTENSIONS
from content_manager.metadata.metadata import Metadata
from content_manager.metadata.metadata_editor import MetadataEditor

class TopBarManager:
    def __init__(self, base_path: Path, content_types: Set[str], products: Dict[str, Any], 
                 metadata: Metadata, metadata_data: Dict, metadata_editor: MetadataEditor,
                 settings_manager=None):  # Add settings_manager parameter
        self.base_path = base_path
        self.content_types = content_types
        self.products = products
        self.metadata = metadata
        self.metadata_data = metadata_data
        self.metadata_editor = metadata_editor
        self.settings_manager = settings_manager  # Store reference to settings manager
        self.initialize_state()

    def initialize_state(self):
        """Initialize or reset the session state"""
        if "content_type" not in st.session_state:
            st.session_state.content_type = self.content_types[0]
        if "selected_image" not in st.session_state:
            st.session_state.selected_image = self.metadata["structure"][st.session_state.content_type]["images"][0]
        if "nav_index" not in st.session_state:
            st.session_state.nav_index = 0
        if "top_bar_message" not in st.session_state:
            st.session_state.top_bar_message = "Notifications show up here"
        if "top_bar_message_type" not in st.session_state:
            st.session_state.top_bar_message_type = "warning"

    def render(self):
        """Render the top bar"""
        col1, col2, col3, col4, col5 = st.columns([2.35, 1, 1, 1.175, 1.175])
        
        with col1:
            # Message display with type
            message = st.session_state.get('top_bar_message', '')
            message_type = st.session_state.get('top_bar_message_type', 'warning')
            
            if message:
                if message_type == 'success':
                    st.success(message, icon=None)
                elif message_type == 'error':
                    st.error(message, icon=None)
                else:  # default to warning
                    st.warning(message, icon=None)
            
        with col2:
            # Content type selection
            st.selectbox(
                "Content Type Selection",
                options=self.content_types,
                key="content_type",
                on_change=self.on_content_type_change,
                label_visibility="collapsed",
            )
            
        with col3:
            content_images = self.metadata_data["structure"][st.session_state.content_type]["images"]
            
            # Get current index
            if not hasattr(st.session_state, 'nav_index'):
                st.session_state.nav_index = 0
                
            # Image selection dropdown
            st.selectbox(
                "Image Selection",
                options=content_images,
                index=st.session_state.nav_index,
                key="selected_image",
                on_change=self._update_nav_index,
                label_visibility="collapsed"
            )
            
        with col4:
            # Previous button with callback
            if st.button("Previous", 
                        use_container_width=True, 
                        type="secondary",
                        on_click=self._handle_prev_click):
                pass
                
        with col5:
            # Next button with callback
            if st.button("Next", 
                        use_container_width=True, 
                        type="secondary",
                        on_click=self._handle_next_click):
                pass

    def _handle_prev_click(self):
        """Handle previous button click"""
        content_images = self.metadata_data["structure"][st.session_state.content_type]["images"]
        if content_images:
            st.session_state.nav_index = (st.session_state.nav_index - 1) % len(content_images)

    def _handle_next_click(self):
        """Handle next button click"""
        content_images = self.metadata_data["structure"][st.session_state.content_type]["images"]
        if content_images:
            st.session_state.nav_index = (st.session_state.nav_index + 1) % len(content_images)

    def _update_nav_index(self):
        """Update nav_index when image selection changes"""
        content_images = self.metadata_data["structure"][st.session_state.content_type]["images"]
        try:
            st.session_state.nav_index = content_images.index(st.session_state.selected_image)
        except ValueError:
            st.session_state.nav_index = 0

    def on_content_type_change(self):
        """Handle content type change"""
        content_images = self.metadata_data["structure"][st.session_state.content_type]["images"]
        if content_images:
            st.session_state.nav_index = 0
        # Sync settings_content_type
        st.session_state.settings_content_type = st.session_state.content_type

    def get_warnings(self) -> str:
        """Get any warnings for current state"""
        warnings = []
        if not st.session_state.selected_image:
            warnings.append("No image selected")
        return " | ".join(warnings) if warnings else ""

    def get_images_for_type(self, content_type: str) -> List[str]:
        """Get list of images for given content type from metadata structure"""
        content_path = self.base_path / content_type
        if not content_path.exists():
            return []
        return [
            f.name for f in content_path.iterdir() 
            if f.is_file() and f.suffix in VALID_IMAGE_EXTENSIONS
        ]

    def prev_image(self):
        """Move to previous image in current content type"""
        images = self.metadata["structure"][st.session_state.content_type]["images"]
        if not images:
            return
        
        st.session_state.nav_index = (st.session_state.nav_index - 1) % len(images)
        st.rerun()

    def next_image(self):
        """Move to next image in current content type"""
        images = self.metadata["structure"][st.session_state.content_type]["images"]
        if not images:
            return
        
        st.session_state.nav_index = (st.session_state.nav_index + 1) % len(images)
        st.rerun()

    def get_settings_level(self) -> str:
        """Get settings level for current image"""
        if not st.session_state.selected_image:
            return "N/A"
        
        # Get image metadata directly from images
        image_name = st.session_state.selected_image
        image_data = self.metadata["images"].get(image_name, {})
        
        # Return settings source or default if not found
        return image_data.get("settings_source", "default")

    def update_data_manager(self):
        """Update DataManager with current image info"""
        if hasattr(self, 'data_manager'):
            current_type = st.session_state.content_type
            current_image = st.session_state.selected_image
            self.data_manager.update_current_image_info(
                path=f"{current_type}/{current_image}",
                settings_level="default"  # You might want to get this from somewhere else
            )