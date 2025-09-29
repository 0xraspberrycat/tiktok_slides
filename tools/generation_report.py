import os 
import time
import functools
from pathlib import Path
from typing import Callable, Any, Union
from content_manager.settings.settings_constants import VALID_IMAGE_EXTENSIONS

def report(func: Callable) -> Callable:
    """Decorator that generates processing report for functions that handle images"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Get start time
        start_time = time.time()
        
        # Run the actual function
        func(*args, **kwargs)
        
        # Get output path from kwargs or use default
        output_path = kwargs.get('output_path') or "output"
        
        # Calculate and print metrics
        metrics = calculate_metrics(Path(output_path), start_time)
        return metrics  # Return the metrics dictionary
        
    return wrapper

def calculate_metrics(output_path: Path, start_time: float) -> dict:
    """Calculate processing metrics"""
    total_time = time.time() - start_time
    
    # Count images and folders
    image_count = 0
    folder_count = 0

    
    # Get total folder size once
    total_size = sum(
        f.stat().st_size for f in Path(output_path).rglob('*') if f.is_file()
    ) / (1024 * 1024)  # Convert to MB
    
    # Count images and folders
    for root, dirs, files in os.walk(output_path):
        folder_count += len(dirs)
        for file in files:
            if Path(file).suffix.lower() in VALID_IMAGE_EXTENSIONS:
                image_count += 1
    
    metrics = {
        'total_time': total_time,
        'total_images': image_count,
        'total_folders': folder_count,
        'total_size_mb': total_size,
        'avg_size_per_image_mb': total_size / image_count if image_count else 0,
        'images_per_second': image_count/total_time if total_time > 0 else 0
    }
    
    print("\n=== Processing Summary ===")
    print(f"Total processing time: {metrics['total_time']:.2f} seconds")
    print(f"Images processed: {metrics['total_images']}")
    print(f"Number of folders: {metrics['total_folders']}")
    print(f"Total output size: {metrics['total_size_mb']:.1f} MB")
    print(f"Average image size: {metrics['avg_size_per_image_mb']:.2f} MB")
    print(f"Processing speed: {metrics['images_per_second']:.2f} images/second")
    
    return metrics
