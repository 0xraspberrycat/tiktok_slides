import streamlit as st  # type: ignore
import os
from PIL import Image  # type: ignore
import pandas as pd  # type: ignore
from pathlib import Path
import json
from typing import Dict

"""
HOW TO OPERATE THIS: 
change directory, img starts with 
add products you want for the images and what they should be tagged as, so like child_overwhelm_1.png etc 
automatically creates a json file so you dont overwrite images, only selects images to display that have the 
img_starts_with prefix setup, so use bulk-rename to make it nice 

very hacky. 

then run 
streamlit run tools/image_renaming.py 
in the terminal /venv 
"""

DIRECTORY = "path"
IMG_STARTS_WITH = "prefix_"

# Move categories to global constant with proper ordering
CATEGORIES = {
    "child_parent_nice": 0,
    "grandchild_parent_nice": 0,
    "child_worried": 0,
    "child_overwhelm": 0,
    "parent_lonely": 0,
    "parent_overwhelm": 0,
    "medical_overwhelm": 0,
    "old_people_time_nice": 0,
    "old_people_time_bad": 0,
    "getting_help": 0,
    "technology": 0,
    "child_happy_cta": 0,
}

COUNTS_FILE = os.path.join(DIRECTORY, "category_counts.json")

def load_category_counts() -> Dict[str, int]:
    """Load category counts from JSON file or initialize if not exists"""
    try:
        if os.path.exists(COUNTS_FILE):
            with open(COUNTS_FILE, 'r') as f:
                counts = json.load(f)
                # Ensure all categories exist in loaded counts
                for cat in CATEGORIES:
                    if cat not in counts:
                        counts[cat] = 0
                return counts
    except Exception as e:
        st.warning(f"Error reading counts file: {e}, initializing with default values")
    
    # Create new counts file if it doesn't exist
    counts = CATEGORIES.copy()
    save_category_counts(counts)
    return counts

def save_category_counts(counts: Dict[str, int]) -> None:
    """Save category counts to JSON file"""
    try:
        with open(COUNTS_FILE, 'w') as f:
            json.dump(counts, f, indent=2)
    except Exception as e:
        st.error(f"Error saving category counts: {e}")

def load_image(image_path):
    """Load and resize image for preview"""
    try:
        img = Image.open(image_path)
        aspect_ratio = img.size[0] / img.size[1]
        target_height = 600
        target_width = int(target_height * aspect_ratio)
        img = img.resize((target_width, target_height))
        return img
    except Exception as e:
        st.error(f"Error loading image: {e}")
        return None

def get_prefix_images(directory):
    """Get all prefix_ images in directory, sorted"""
    valid_extensions = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}
    return sorted(
        [
            f
            for f in os.listdir(directory)
            if Path(f).suffix.lower() in valid_extensions and f.startswith(IMG_STARTS_WITH)
        ]
    )

def update_category_count(category: str, count: int):
    """Update a specific category count and save"""
    counts = load_category_counts()
    counts[category] = count
    save_category_counts(counts)
    return counts

def main():
    
    # Initialize session state
    if "remaining_images" not in st.session_state:
        st.session_state.remaining_images = get_prefix_images(DIRECTORY)
    if "renamed_files" not in st.session_state:
        st.session_state.renamed_files = []
    
    # Always load fresh category counts
    category_counts = load_category_counts()
    

    if not st.session_state.remaining_images:
        st.success("All prefix_ images have been processed!")
        if st.session_state.renamed_files:
            st.write("### All Renamed Files")
            df = pd.DataFrame(
                st.session_state.renamed_files, columns=["Original Name", "New Name"]
            )
            st.dataframe(df)
        return

    # Display progress
    total_images = len(st.session_state.renamed_files) + len(st.session_state.remaining_images)
    current_progress = len(st.session_state.renamed_files) / total_images
    st.progress(current_progress)
    st.write(f"Remaining images: {len(st.session_state.remaining_images)}")

    # Create two columns for layout
    col1, col2 = st.columns([1, 1])

    current_image = st.session_state.remaining_images[0]
    image_path = os.path.join(DIRECTORY, current_image)

    # Display current image
    with col1:
        st.write(current_image)
        img = load_image(image_path)
        if img:
            st.image(img)

    # Renaming options
    with col2:
        selected_category = st.radio(
            "Category", list(CATEGORIES.keys())
        )

        # Preview new filename
        new_count = category_counts[selected_category] + 1
        base, ext = os.path.splitext(current_image)
        new_filename = f"{selected_category}_{new_count}{ext}"
        st.write("New filename will be:", new_filename)

        # Action buttons
        col_btn1, col_btn2 = st.columns(2)

        with col_btn1:
            if st.button("Rename", key="rename"):
                try:
                    new_path = os.path.join(DIRECTORY, new_filename)
                    os.rename(image_path, new_path)
                    st.session_state.renamed_files.append((current_image, new_filename))
                    
                    # Update and save category count
                    category_counts = update_category_count(selected_category, new_count)
                    
                    # Remove the processed image from the list
                    st.session_state.remaining_images.pop(0)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error renaming file: {e}")

        with col_btn2:
            if st.button("Skip", key="skip"):
                # Move skipped image to end of list
                skipped = st.session_state.remaining_images.pop(0)
                st.session_state.remaining_images.append(skipped)
                st.rerun()

            # Display current counts
        with st.expander("Current Category Counts", expanded=True):
            for cat, count in category_counts.items():
                st.text(f"{cat}: {count}")

    # Display rename history
    if st.session_state.renamed_files:
        st.write("### Recently Renamed Files")
        recent_renames = st.session_state.renamed_files[-5:]
        df = pd.DataFrame(recent_renames, columns=["Original Name", "New Name"])
        st.dataframe(df)

        if st.button("Export Rename History"):
            full_df = pd.DataFrame(
                st.session_state.renamed_files, columns=["Original Name", "New Name"]
            )
            full_df.to_csv(os.path.join(DIRECTORY, "rename_history.csv"), index=False)
            st.success("Rename history exported!")

if __name__ == "__main__":
    main()