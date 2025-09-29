import os
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import warnings
import re
import shutil

# Video settings
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30
BACKGROUND_COLOR = (255, 255, 255)  # White in BGR format. For black use (0, 0, 0)


def is_image_file(filename):
    """Check if a file is an image based on its extension."""
    valid_extensions = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}
    return Path(filename).suffix.lower() in {ext.lower() for ext in valid_extensions}


def natural_sort_key(s):
    """Key function for natural sorting of strings with numbers."""
    return [
        int(text) if text.isdigit() else text.lower()
        for text in re.split("([0-9]+)", str(s))
    ]


def resize_and_pad(image):
    """Resize image maintaining aspect ratio and add padding to center it."""
    # Convert PIL image to numpy array if needed
    if isinstance(image, Image.Image):
        image = np.array(image)
    
    # Handle RGBA images by removing alpha channel
    if len(image.shape) == 3 and image.shape[2] == 4:
        image = image[:, :, :3]
        
    h, w = image.shape[:2]
    aspect = w / h

    # Calculate new dimensions maintaining aspect ratio
    if aspect > VIDEO_WIDTH / VIDEO_HEIGHT:  # wider than 16:9
        new_w = VIDEO_WIDTH
        new_h = int(VIDEO_WIDTH / aspect)
    else:  # taller than 16:9
        new_h = VIDEO_HEIGHT
        new_w = int(VIDEO_HEIGHT * aspect)
        
    # Resize image
    resized = cv2.resize(image, (new_w, new_h))
    
    # Create canvas with specified background color
    canvas = np.full((VIDEO_HEIGHT, VIDEO_WIDTH, 3), BACKGROUND_COLOR, dtype=np.uint8)
    
    # Calculate padding
    pad_x = (VIDEO_WIDTH - new_w) // 2
    pad_y = (VIDEO_HEIGHT - new_h) // 2
    
    # Place image in center
    canvas[pad_y:pad_y+new_h, pad_x:pad_x+new_w] = resized
    
    return canvas


def create_video_from_slides(root_folder: str, slide_duration: float = 1.5, output_path: str = None):
    """
    Create videos from slides in the specified folder structure.

    Args:
        root_folder: Path to the root folder containing variation and post folders
        slide_duration: Duration (in seconds) to show each slide
    """
    root_path = Path(root_folder)
    output_path = Path(output_path) if output_path else root_path

    # Create output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)

    # Iterate through variation folders
    for variation_folder in root_path.iterdir():
        if not variation_folder.is_dir():
            continue

        # Iterate through post folders
        for post_folder in variation_folder.iterdir():
            if not post_folder.is_dir():
                continue

            # Get all image files in the post folder
            image_files = [f for f in post_folder.iterdir() if is_image_file(f)]

            if not image_files:
                warnings.warn(f"No image files found in: {post_folder}")
                continue

            # Sort images naturally (1.jpg, 2.jpg, 3.jpg, etc.)
            image_files.sort(key=natural_sort_key)

            # Create video filename
            video_name = f"{variation_folder.name}_{post_folder.name}.mp4"
            video_path = output_path / video_name  

            # Initialize video writer with H.264 codec
            fourcc = cv2.VideoWriter_fourcc(*'avc1')  # H.264 codec
            video = cv2.VideoWriter(str(video_path), 
                                  fourcc, 
                                  FPS,
                                  (VIDEO_WIDTH, VIDEO_HEIGHT))

            if not video.isOpened():
                warnings.warn(f"Failed to initialize video writer for {video_path}")
                continue

            try:
                for img_path in image_files:
                    # Read image
                    img = Image.open(img_path)
                    img = np.array(img)
                    
                    # Convert RGB to BGR for OpenCV
                    if len(img.shape) == 3:  # Color image
                        if img.shape[2] == 4:  # RGBA
                            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
                        elif img.shape[2] == 3:  # RGB
                            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                    
                    # Resize and pad image
                    img = resize_and_pad(img)
                    
                    # Write frame for duration
                    for _ in range(int(slide_duration * FPS)):
                        video.write(img)

                video.release()
                print(f"Created video: {video_path}")

            except Exception as e:
                warnings.warn(f"Error processing folder {post_folder}: {str(e)}")
                if video is not None:
                    video.release()
                continue

    # After all videos are created, organize them
    print("\nOrganizing videos into variation folders...")
    
    # Get all MP4 files (ignoring other files and folders)
    mp4_files = [f for f in output_path.iterdir() if f.is_file() and f.suffix.lower() == '.mp4']
    
    # Group files by variation
    for video_file in mp4_files:
        # Extract variation number from filename (e.g., "variation1_post1.mp4" -> "1")
        variation_num = video_file.name.split('_')[0].replace('variation', '')
        
        # Create folder name and path
        folder_name = f"variation{variation_num}_videos"
        folder_path = output_path / folder_name
        
        # Create folder if it doesn't exist
        folder_path.mkdir(exist_ok=True)
        
        # Move file to appropriate folder
        shutil.move(str(video_file), str(folder_path / video_file.name))
        print(f"Moved {video_file.name} to {folder_name}/")