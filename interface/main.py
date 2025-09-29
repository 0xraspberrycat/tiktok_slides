import streamlit as st  # type: ignore

# First thing in the script - before ANY other st.commands!
st.set_page_config(
    page_title="Slide Manager",
    layout="wide",
    initial_sidebar_state="expanded",
)

import subprocess
import sys
from pathlib import Path
import ast
from content_manager.metadata.metadata import Metadata
from content_manager.settings.settings_handler import Settings
from interface.components.data_manager import DataManager
from interface.components.image_manager import ImageManager
from interface.components.interface_settings_manager import InterfaceSettingsManager
from interface.components.top_bar_manager import TopBarManager
import json
from typing import Set, Dict


class Interface:
    def __init__(
        self, base_path: Path, content_types: Set[str], products: Dict, separator: str
    ):
        self.base_path = base_path
        self.content_types = sorted(content_types)
        self.products = products
        self.separator = separator

        # Initialize metadata properly
        self.metadata = Metadata(base_path)
        self.metadata.load(content_types, products, strict=False)
        self.metadata_data = self.metadata.data  # Get the data directly from metadata
        self.metadata_editor = (
            self.metadata.metadata_editor
        )  # This will now be properly set

        self.settings_handler = Settings()

        # Now initialize components with the data we have
        self.initialize_components()

    def load_metadata(self) -> Dict:
        """Load metadata from json file"""
        metadata_path = self.base_path / "metadata.json"
        with open(metadata_path) as f:
            return json.load(f)

    def refresh_metadata(self):
        """Refresh metadata from disk"""
        self.metadata = self.load_metadata()

    def display(self):
        """Display the interface with proper layout"""
        # Top bar section
        self.top_bar_manager.render()

        # Main content area
        cols = st.columns([1, 0.85, 1])  # Settings : Image : Metadata

        with cols[0]:
            # Metadata column
            self.data_manager.render_content()

        with cols[1]:
            # Image column
            self.image_manager.render_image()

        with cols[2]:
            # Settings column
            self.settings_manager.render()

    def _initialize_streamlit(self):
        """Initialize Streamlit through subprocess to avoid context warnings"""
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "streamlit",
                    "run",
                    str(Path(__file__).parent / "interface.py"),
                ],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"Error initializing Streamlit: {e}")
            raise

    def initialize_session_state(self):
        """Initialize all required session state variables"""
        if "current_content_type" not in st.session_state:
            st.session_state.current_content_type = (
                "no content type found, check main.py"
            )
        if "images" not in st.session_state:
            st.session_state.images = None
        if "current_index" not in st.session_state:
            st.session_state.current_index = 0
        if "metadata" not in st.session_state:
            st.session_state.metadata = {}

    def initialize_components(self):
        """Initialize interface components"""

        # Initialize settings manager with the data we already have
        self.settings_manager = InterfaceSettingsManager(
            base_path=self.base_path,
            content_types=self.content_types,
            products=self.products,
            metadata=self.metadata,
            metadata_data=self.metadata_data,
            metadata_editor=self.metadata_editor,
            settings_handler=self.settings_handler,
            separator=self.separator
        )

        # Initialize data manager
        self.data_manager = DataManager(
            base_path=self.base_path,
            content_types=self.content_types,
            products=self.products,
            metadata=self.metadata,
            metadata_data=self.metadata_data,
            metadata_editor=self.metadata_editor,
        )

        # Initialize image manager
        self.image_manager = ImageManager(
            base_path=self.base_path,
            content_types=self.content_types,
            products=self.products,
            metadata=self.metadata,
            metadata_data=self.metadata_data,
            metadata_editor=self.metadata_editor,
        )

        # Initialize top bar manager
        self.top_bar_manager = TopBarManager(
            base_path=self.base_path,
            content_types=self.content_types,
            products=self.products,
            metadata=self.metadata,
            metadata_data=self.metadata_data,
            metadata_editor=self.metadata_editor,
            settings_manager=self.settings_manager,
        )


if __name__ == "__main__":
    if len(sys.argv) != 5:  # Change to 5 to account for all arguments
        print(
            "Usage: streamlit run main.py -- <base_path> <content_types> <products> <separator>"
        )
        sys.exit(1)

    # print("Command line arguments:", sys.argv)
    base_path = Path(sys.argv[1])
    try:
        content_types = ast.literal_eval(sys.argv[2])
        products = ast.literal_eval(sys.argv[3])
        separator = sys.argv[4]  # Get the separator argument
        
    except Exception as e:
        print(f"Error parsing arguments: {e}")
        raise
    interface = Interface(
        base_path, content_types, products, separator
    )  # Pass separator to Interface
    interface.display()
