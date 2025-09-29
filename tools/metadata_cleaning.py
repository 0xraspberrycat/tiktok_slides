import subprocess
from PIL import Image
import piexif
from pathlib import Path
import pypdf
import logging
from typing import Union, Optional

def setup_logging(level=logging.INFO):
    """Configure logging with the specified level"""
    logging.basicConfig(
        level=level,
        format='%(levelname)s: %(message)s'
    )

def clean_metadata(
    file_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None
) -> None:
    """
    Clean metadata from a file.
    
    Args:
        file_path: Path to file to clean
        output_path: Optional path where to save cleaned file. If None, adds '_clean' suffix
    """
    file_path = Path(file_path)
    if output_path is None:
        output_path = file_path.parent / f"{file_path.stem}_clean{file_path.suffix}"
    else:
        output_path = Path(output_path)
        
    setup_logging()
    original_size = file_path.stat().st_size

    try:
        # Handle different file types
        if file_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
            # Handle images
            with Image.open(file_path) as img:
                cleaned_img = Image.new(img.mode, img.size)
                cleaned_img.putdata(list(img.getdata()))

                if file_path.suffix.lower() in [".jpg", ".jpeg"]:
                    cleaned_img.save(
                        output_path,
                        format=img.format,
                        optimize=True,
                        exif=piexif.dump({}),
                    )
                else:
                    cleaned_img.save(output_path, format=img.format, optimize=True)

        elif file_path.suffix.lower() == ".pdf":
            # Handle PDFs
            reader = pypdf.PdfReader(file_path)
            writer = pypdf.PdfWriter()

            # Copy pages without metadata
            for page in reader.pages:
                writer.add_page(page)

            # Save without metadata
            with open(output_path, "wb") as f:
                writer.write(f)

        elif file_path.suffix.lower() in [".mp4", ".mov", ".avi"]:
            # Handle videos using ffmpeg command line
            cmd = [
                "ffmpeg",
                "-i",
                str(file_path),
                "-map_metadata",
                "-1",
                "-c",
                "copy",
                str(output_path),
            ]
            subprocess.run(cmd, check=True, capture_output=True)

        else:
            print(f"Unsupported file type: {file_path.suffix}")
            return

        # Calculate space saved
        new_size = output_path.stat().st_size
        saved = original_size - new_size

        logging.debug(f"Metadata cleaned successfully!")
        logging.debug(f"Original file: {file_path}")
        logging.debug(f"Cleaned file: {output_path}")
        logging.debug(f"Space saved: {saved/1024:.1f}KB")

    except Exception as e:
        logging.error(f"Error processing {file_path}: {str(e)}")


def bulk_clean_metadata(
    folder_path: Union[str, Path],
    output_folder: Optional[Union[str, Path]] = None,
    dry_run: bool = False,
    recursive: bool = True,
    supported_extensions: set[str] = {".png", ".jpg", ".jpeg", ".webp", ".pdf", ".mp4", ".mov", ".avi"},
    log_level: int = logging.INFO,
) -> None:
    """
    Clean metadata from all supported files in a folder.
    """
    setup_logging(log_level)
    folder_path = Path(folder_path)
    
    # Get all files
    if recursive:
        files = [f for f in folder_path.rglob("*") if f.is_file()]
    else:
        files = [f for f in folder_path.iterdir() if f.is_file()]
        
    # Filter for supported files
    supported_files = [f for f in files if f.suffix.lower() in supported_extensions]
    
    if dry_run:
        logging.info("\nDRY RUN - showing what would be processed:")
        for f in supported_files:
            logging.info(f"Would clean: {f.relative_to(folder_path)}")
        return
        
    # Setup output folder if provided
    if output_folder:
        output_folder = Path(output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)
    
    # Process files
    for file_path in supported_files:
        try:
            rel_path = file_path.relative_to(folder_path)
            logging.info(f"Processing: {rel_path}")
            
            if output_folder:
                output_path = output_folder / rel_path
                output_path.parent.mkdir(parents=True, exist_ok=True)
                clean_metadata(file_path, output_path=output_path)
            else:
                clean_metadata(file_path)
                
        except Exception as e:
            logging.error(f"Failed to process {rel_path}: {e}")
    
    print("done all files")

# Example usage:
"""
# Clean files and put them in a new output directory
bulk_clean_metadata(
    "path/to/input/folder",
    output_folder="path/to/output/folder"
)

# Original behavior (create _clean files in same directory)
bulk_clean_metadata("path/to/folder")

# Dry run with output folder
bulk_clean_metadata(
    "path/to/input/folder",
    output_folder="path/to/output/folder",
    dry_run=True
)
"""

