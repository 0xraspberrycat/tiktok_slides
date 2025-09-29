import streamlit as st
from pathlib import Path
from typing import Set, Dict, Any, Optional, Tuple, List
from content_manager.metadata.metadata import Metadata
from content_manager.metadata.metadata_editor import MetadataEditor
import pandas as pd 
from config.logging import logger

class DataManager:
    """Manages data and metadata display"""
    
    def __init__(self, base_path: Path, content_types: Set[str], products: Dict[str, Any], 
                 metadata: Metadata, metadata_data: Dict, metadata_editor: MetadataEditor):
        self.base_path = base_path
        self.content_types = content_types
        self.products = products
        self.metadata = metadata
        self.metadata_data = metadata_data
        self.metadata_editor = metadata_editor
        self.initialize_state()
        self.current_path = ""
        self.settings_level = "default"
        
    def initialize_state(self):
        """Initialize state for data tracking"""
        if "content_type" not in st.session_state:
            st.session_state.content_type = list(self.content_types)[0]
            
        if "product" not in st.session_state:
            st.session_state.product = "all"
            
        if "selected_image" not in st.session_state:
            first_type_images = self.metadata_data["structure"][st.session_state.content_type]["images"]
            st.session_state.selected_image = list(first_type_images)[0] if first_type_images else None
            
        if "selected_data" not in st.session_state:
            st.session_state.selected_data = None
            
    def render_content(self):
        """Render content data with improved error handling and organization"""
        current_image = st.session_state.get("selected_image")
        
        if not current_image:
            st.warning("No image selected")
            return
            
        try:
            # Get image data with validation
            image_data = self.metadata_data["images"].get(current_image)
            if not image_data:
                st.warning(f"No metadata found for image: {current_image}")
                return
                
            # Basic image info at top level
            st.write(f"Image: {current_image}")

            # Current Image Details
            with st.expander("Additional Info", expanded=True):
                content_type = image_data.get("content_type")
                product = image_data.get("product")
                settings_level = image_data.get("settings_source", "default")
                
                # Display basic info
                st.write(f"Path: {self.get_relative_path(content_type, current_image)}")
                st.write(f"Content Type: {content_type}")
                dims = image_data.get("dimensions", {})
                if dims:
                    st.write(f"Size: {dims.get('width', 'unknown')}x{dims.get('height', 'unknown')}")
                st.write(f"Settings Level: {settings_level}")

                # Get and display product info with safety checks
                if product:
                    product_info = next(
                        (p for p in self.metadata_data["products"][content_type] 
                        if p["name"] == product),
                        None
                    )
                    if product_info:
                        st.write(f"Prevent Duplicates: {product_info.get('prevent_duplicates', False)}")
                        st.write(f"Min Required: {product_info.get('min_occurrences', 'NA')}")
                        st.write(f"Current Count: {product_info.get('current_count', 0)}")
                        st.write(f"Current Product: {product}")
                    else:
                        st.write("No product info available")
                else:
                    st.write("Current Product: None")

            # Products with Duplicate Prevention
            with st.expander("Product Requirements", expanded=True):
                requirements_data = []
                try:
                    for content_type_iter, products in self.metadata_data["products"].items():
                        for prod in products:
                            if prod.get("prevent_duplicates", False):
                                requirements_data.append({
                                    "Content Type": content_type_iter,
                                    "Product": prod["name"],
                                    "Min Required": prod.get("min_occurrences", 0),
                                    "Current Count": prod.get("current_count", 0)
                                })
                    
                    if requirements_data:
                        # Sort by content type then product
                        requirements_data.sort(key=lambda x: (x["Content Type"], x["Product"]))
                        df = pd.DataFrame(requirements_data)
                        st.dataframe(df, hide_index=True)
                    else:
                        st.info("No products with duplicate prevention configured")
                except Exception as e:
                    logger.error(f"Error displaying requirements: {str(e)}")
                    st.error("Error displaying product requirements")

            # Tagging Status
            with st.expander("Tagging Status", expanded=False):
                try:
                    untagged_stats = self.get_untagged_stats()
                    if untagged_stats:
                        st.write("Untagged Images:")
                        for stat in untagged_stats:
                            st.write(f"**{stat['Content Type']}** ({stat['Untagged Count']} images):")
                            st.write(f"_{stat['Images']}_")
                    else:
                        st.success("✅ All images have been tagged!")
                except Exception as e:
                    logger.error(f"Error displaying tagging status: {str(e)}")
                    st.error("Error displaying tagging status")

            # Warnings
            with st.expander("Warnings", expanded=True):
                try:
                    warnings = self.get_metadata_warnings()
                    if any(warnings.values()):
                        for category, category_warnings in warnings.items():
                            if category_warnings:  # Only show categories that have warnings
                                st.write(f"**{category}:**")
                                for warning in category_warnings:
                                    st.markdown(f"* {warning}")
                                st.write("")  # Add spacing between categories
                    else:
                        st.success("✅ No warnings found!")
                except Exception as e:
                    logger.error(f"Error displaying warnings: {str(e)}")
                    st.error("Error displaying warnings")

        except Exception as e:
            logger.error(f"Error rendering content: {str(e)}")
            st.error(f"Error displaying content information: {str(e)}")

    def update_current_path(self):
        """Updates the current path information based on top bar state"""
        content_type = st.session_state.get('top_bar_content_type', '')
        image = st.session_state.get('top_bar_selected_image', '')
        self.current_path = f"path: {content_type}/{image} settings_level: {self.settings_level}"
        return self.current_path

    def render_product_controls(self):
        """Render product selection and requirements info"""
        with st.expander("Additional Info", expanded=True):
            if st.session_state.selected_image:
                image_data = self.metadata_data["images"][st.session_state.selected_image]
                content_type = image_data.get('content_type', '')
                
                # Existing product selection dropdown
                products = self.products.get(content_type, [])
                current_product = image_data.get('product')
                

        with st.expander("Product Requirements", expanded=True):
            # Create list of requirements
            requirements = []
            for content_type, products in self.metadata_data["products"].items():
                for prod in products:
                    if prod.get("min_occurrences", 0) > 0 or prod.get("prevent_duplicates", False):
                        requirements.append({
                            "Content Type": content_type,
                            "Product": prod["name"],
                            "Min Req": prod.get("min_occurrences", 0),
                            "No Dupes": "Yes" if prod.get("prevent_duplicates", False) else "No"
                        })
            
            # Sort by content type then product
            requirements.sort(key=lambda x: (x["Content Type"], x["Product"]))
            
            # Display as table
            if requirements:
                st.table(requirements)
            else:
                st.text("No minimum requirements configured")

    def update_image_product(self, image_name: str, new_product: str):
        """Update product for an image using metadata editor"""
        try:
            if new_product == 'None':
                new_product = None
            
            content_type = self.metadata_data["images"][image_name]["content_type"]
            self.metadata_editor.update_image_product(
                image_name=image_name,
                content_type=content_type,
                new_product=new_product
            )
            return True
        except ValueError as e:
            st.error(str(e))
            return False

    def get_relative_path(self, content_type: str, image_name: str) -> str:
        """Get the relative path from the full path"""
        full_path = self.metadata_data['structure'][content_type]['path']
        # Get just the last folder name + image
        return f"{full_path.split('/')[-1]}/{image_name}"

    def get_product_info(self, content_type: str, current_product: Optional[str]) -> Dict:
        """Get complete product info including counts and requirements"""
        if not current_product:
            return {
                "prevent_duplicates": False,
                "min_occurrences": "NA",
                "current_count": 0,
                "product": "None"
            }
        
        for p in self.metadata_data["products"][content_type]:
            if p["name"] == current_product:
                return {
                    "prevent_duplicates": p.get("prevent_duplicates", False),
                    "min_occurrences": p.get("min_occurrences", "NA") if p.get("prevent_duplicates", False) else "NA",
                    "current_count": p.get("current_count", 0),
                    "product": current_product
                }
        return None

    def get_untagged_stats(self) -> list:
        """Get stats about untagged images per content type"""
        stats = []
        for content_type in self.metadata_data["content_types"]:
            untagged = []
            for img_name, img_data in self.metadata_data["images"].items():
                if img_data["content_type"] == content_type and not img_data.get("product"):
                    untagged.append(img_name)
            
            if untagged:  # Only add to stats if there are untagged images
                stats.append({
                    "Content Type": content_type,
                    "Untagged Count": len(untagged),
                    "Images": ", ".join(untagged)
                })
        
        return sorted(stats, key=lambda x: x["Content Type"])

    def get_metadata_warnings(self) -> Dict[str, List[str]]:
        """Get current metadata warnings as categorized dict"""
        try:
            is_valid, categorized_warnings = self.validate_metadata()
            return {
                "Duplicate Prevention": categorized_warnings["duplicate_prevention"],
                "Missing Data": categorized_warnings["missing_data"]
            }
        except Exception as e:
            return {"Error": [f"Error getting warnings: {str(e)}"]}

    def validate_metadata(self) -> Tuple[bool, List[Dict[str, List[str]]]]:
        warnings = {
            "product_requirements": [],
            "duplicate_prevention": [],
            "missing_data": []
        }
        errors = []
        
        # Check images without products and custom settings
        for img_name, img_data in self.metadata_data['images'].items():
            if not img_data.get('product'):
                warnings["missing_data"].append(f"{img_name} has no product assigned")
            # if img_data.get('settings_source') == 'custom':
                # warnings["missing_data"].append(f"{img_name} has custom settings")

        # Only show warnings for products with prevent_duplicates=True
        for content_type, products in self.metadata_data['products'].items():
            for product in products:
                if product['prevent_duplicates']:  # First check if duplicate prevention is enabled
                    if product['current_count'] < product['min_occurrences']:
                        warnings["duplicate_prevention"].append(
                            f"{content_type}/{product['name']}: needs {product['min_occurrences']} images (has {product['current_count']})"
                        )

        return len(errors) == 0, warnings