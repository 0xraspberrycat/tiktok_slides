import imghdr
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# import imagehash
# from PIL import Image

from config.logging import logger

from .strict_validator import StrictValidator


class PathValidator(StrictValidator):
    def __init__(self, strict: bool = True):
        super().__init__(strict)
        self.base_path = None
        self.content_types: Set[str] = set()

    def validate(self, base_path: Path) -> bool:
        """Main validation method"""
        self.clear_messages()

        if base_path is None:
            self.add_error("Base path cannot be None")
            return False

        # Check if it's an empty path by checking the original string representation
        if str(base_path) == "." or str(base_path) == "":
            self.add_error("Base path cannot be empty")
            logger.critical(
                f"Validation failed: Base path cannot be empty (got: {base_path})"
            )
            return False

        self.base_path = base_path

        if not self._validate_base_path(self.base_path):
            logger.critical(f"Validation failed: {self.errors[-1]}")
            return False

        # Add check for base folder files
        if not self._check_base_folder_files(self.base_path):
            logger.critical(f"Validation failed: {self.errors[-1]}")
            return False

        return True

    def folder_validation(self, base_path: Path) -> bool:
        """Run folder validations"""
        try:
            # Check for unexpected folders first
            if not self._check_unexpected_folders(base_path):
                raise ValueError(self.errors[-1])

            # Check for exact name matches
            if not self._check_folder_names_exact_match(base_path):
                raise ValueError(self.errors[-1])

            # Check no nested folders
            if not self._check_no_nested_folders(base_path):
                raise ValueError(self.errors[-1])

            # Check if folders exist and are not empty
            if not self._check_folder_exists(base_path):
                if self.strict:
                    raise ValueError(self.errors[-1])
                return True

            # Check if folders are not empty
            if not self._check_folders_not_empty(base_path):
                if self.strict:
                    raise ValueError(self.errors[-1])
                return True  # In non-strict mode, empty folders are just warnings

            # Check that only images are allowed (this will catch non-image files first)
            if not self._check_only_images_allowed(base_path):
                raise ValueError(self.errors[-1])

            # Then check image formats for valid images
            if not self._check_image_formats(base_path):
                raise ValueError(self.errors[-1])

            # Check for duplicate image names
            if not self._check_duplicate_image_names(base_path):
                raise ValueError(self.errors[-1])

            # Check for duplicate image content
            if not self._check_duplicate_image_content(base_path):
                raise ValueError(self.errors[-1])

            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Error in folder validation: {str(e)}")
            return False

    def _check_folder_exists(self, base_path: Path) -> bool:
        """Check ONLY if required folders exist"""
        try:
            missing_folders = []
            for content_type in self.content_types:
                folder_path = base_path / content_type
                if not folder_path.exists():
                    msg = f"Folder '{content_type}' does not exist"
                    if self.strict:
                        self.add_error(msg)
                    else:
                        self.add_warning(msg)
                    missing_folders.append(content_type)

            if missing_folders and self.strict:
                raise ValueError(self.errors[0])

            return True
        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Error checking folder existence: {str(e)}")
            return False

    def _check_unexpected_folders(self, base_path: Path) -> bool:
        """Check ONLY for unexpected folders in base path"""
        try:
            allowed = {name.lower() for name in self.content_types} | {"metadata"}

            for item in base_path.iterdir():
                if item.name.startswith("."):
                    continue

                if item.is_dir() and item.name.lower() not in allowed:
                    # Special handling for preview folder
                    if item.name.lower() == "preview":
                        import shutil
                        logger.warning(f"Found a preview folder, deleting it: {item}")
                        shutil.rmtree(item)
                        continue
                        
                    msg = f"Unexpected folder(s) found: {item.name}"
                    self.add_error(msg)
                    raise ValueError(msg)

            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Error checking unexpected folders: {str(e)}")
            return False

    def _check_folder_permissions(self, base_path: Path) -> bool:
        """Check ONLY permissions for all folders"""
        try:
            for content_type in self.content_types:
                folder_path = base_path / content_type
                # Skip permission check if folder doesn't exist
                if not folder_path.exists():
                    continue

                if not os.access(folder_path, os.R_OK | os.W_OK):
                    msg = f"Insufficient permissions for folder: {content_type}"
                    self.add_error(msg)
                    raise ValueError(msg)
            return True
        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Error checking folder permissions: {str(e)}")
            return False

    def _check_folder_contents(self, base_path: Path) -> bool:
        """Check ONLY files in content folders"""
        try:
            for content_type in self.content_types:
                folder_path = base_path / content_type
                if not folder_path.exists():
                    continue  # Skip non-existent folders - handled by exists check

                for item in folder_path.iterdir():
                    if item.name.startswith("."):
                        continue
                    if not item.is_file() or not self._is_valid_image(item):
                        msg = f"Invalid file in {content_type} folder: {item.name}"
                        self.add_error(msg)
                        raise ValueError(msg)
            return True
        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Error checking folder contents: {str(e)}")
            return False

    def _is_valid_image(self, file_path: Path) -> bool:
        """Helper to check if file is a valid image"""
        try:
            # Get file extension and check if it's an image extension
            ext = file_path.suffix.lower()
            if ext not in [".png", ".jpg", ".jpeg"]:
                return False

            # Additional check using imghdr for content validation
            return imghdr.what(file_path) is not None
        except Exception:
            return False

    def _validate_base_path(self, base_path: Path) -> bool:
        """Validate base path and captions.csv existence"""
        # Check empty path BEFORE any resolution
        path_str = str(base_path).strip()
        if not path_str:
            self.add_error("Base path cannot be empty")
            logger.critical(f"Validation failed: Base path cannot be empty")
            return False

        # Check if base_path exists
        if not base_path.exists():
            self.add_error(f"Base path '{base_path}' does not exist")
            logger.critical(
                f"Validation failed: Base path '{base_path}' does not exist"
            )
            return False

        # Check if base_path is a directory
        if not base_path.is_dir():
            self.add_error(f"Base path '{base_path}' is not a directory")
            logger.critical(
                f"Validation failed: Base path '{base_path}' is not a directory"
            )
            return False

        # Check for captions.csv
        captions_file = base_path / "captions.csv"
        if not captions_file.exists():
            msg = f"Required file 'captions.csv' not found in {base_path}"
            self.add_error(msg)
            logger.critical(f"Validation failed: {msg}")
            return False

        if not captions_file.is_file():
            msg = f"'captions.csv' exists but is not a file in {base_path}"
            self.add_error(msg)
            logger.critical(f"Validation failed: {msg}")
            return False

        return True

    def _check_folder_names_exact_match(self, base_path: Path) -> bool:
        """Check ONLY if folder names match content types exactly"""
        try:
            for item in base_path.iterdir():
                if item.name.startswith("."):
                    continue

                if item.is_dir() and item.name.lower() in {
                    name.lower() for name in self.content_types
                }:
                    if item.name not in self.content_types:  # Case-sensitive check
                        msg = f"Invalid folder name: '{item.name}' must exactly match content type '{item.name.lower()}'"
                        self.add_error(msg)
                        raise ValueError(msg)
            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Error checking folder names: {str(e)}")
            return False

    def _check_folders_not_empty(self, base_path: Path) -> bool:
        """Check ONLY if content folders contain any files"""
        try:
            for content_type in self.content_types:
                folder_path = base_path / content_type
                if not folder_path.exists():
                    continue

                # Check if folder has any non-hidden files
                has_files = False
                for item in folder_path.iterdir():
                    if not item.name.startswith(".") and item.is_file():
                        has_files = True
                        break

                if not has_files:
                    msg = f"Folder is empty: {content_type}"
                    if self.strict:
                        self.add_error(msg)
                        raise ValueError(msg)
                    else:
                        self.add_warning(msg)

            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Error checking empty folders: {str(e)}")
            return False

    def _check_only_images_allowed(self, base_path: Path) -> bool:
        """Check ONLY that all files in content folders are valid images"""
        try:
            for content_type in self.content_types:
                folder_path = base_path / content_type
                if not folder_path.exists():
                    continue

                for item in folder_path.rglob("*"):
                    # Skip hidden files and directories
                    if item.name.startswith("."):
                        continue

                    if item.is_file():
                        if not self._is_valid_image(item):
                            msg = f"Invalid file in {content_type} folder: {item.name}"
                            self.add_error(msg)
                            raise ValueError(msg)
            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Error checking file types: {str(e)}")
            return False

    def _check_base_folder_files(self, base_path: Path) -> bool:
        """Check ONLY that base folder contains only allowed files, warn about images"""
        try:
            allowed_files = {"captions.csv", "metadata.json"}

            for item in base_path.iterdir():
                if item.name.startswith("."):
                    continue

                if item.is_file():
                    if item.name not in allowed_files:
                        # Check if it's an image
                        if self._is_valid_image(item):
                            msg = f"Image found in base folder: {item.name}. Consider moving to appropriate content folder."
                            self.add_warning(msg)
                            if self.strict:
                                raise ValueError(msg)
                        else:
                            # Non-image files not allowed
                            msg = f"Invalid file in base folder: {item.name}"
                            self.add_error(msg)
                            raise ValueError(msg)

            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Error checking base folder files: {str(e)}")
            return False

    def _check_no_nested_folders(self, base_path: Path) -> bool:
        """Check ONLY that content folders don't contain nested folders"""
        try:
            for content_type in self.content_types:
                folder_path = base_path / content_type
                if not folder_path.exists():
                    continue

                for item in folder_path.iterdir():
                    if item.name.startswith("."):
                        continue

                    if item.is_dir():
                        msg = f"Nested folder found in {content_type}: {item.name}"
                        self.add_error(msg)
                        raise ValueError(msg)

            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Error checking nested folders: {str(e)}")
            return False

    def _check_image_formats(self, base_path: Path) -> bool:
        """Check ONLY that image files have valid extensions"""
        try:
            for content_type in self.content_types:
                folder_path = base_path / content_type
                if not folder_path.exists():
                    continue

                for item in folder_path.iterdir():
                    if item.name.startswith("."):
                        continue

                    if item.is_file():
                        ext = item.suffix.lower()
                        if ext not in [".png", ".jpg", ".jpeg"]:
                            msg = f"Invalid image format in {content_type}: {item.name}"
                            self.add_error(msg)
                            raise ValueError(msg)
            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Error checking image formats: {str(e)}")
            return False

    def _check_duplicate_image_names(self, base_path: Path) -> bool:
        """Check ONLY for duplicate image names (case-insensitive, extension-independent)"""
        try:
            name_map = defaultdict(list)

            # Helper function to add file to name_map
            def add_file(file_path: Path):
                base_name = file_path.stem.lower()
                # Store path - if in base folder, just filename, otherwise relative path
                if file_path.parent == base_path:
                    name_map[base_name].append(file_path.name)
                else:
                    rel_path = file_path.relative_to(base_path)
                    name_map[base_name].append(str(rel_path))

            # Check base folder first
            for item in base_path.iterdir():
                if item.is_file() and not item.name.startswith("."):
                    if self._is_valid_image(item):
                        add_file(item)

            # Check each content folder
            for folder in sorted(self.content_types):  # Sort folders for consistency
                folder_path = base_path / folder
                if not folder_path.exists():
                    continue

                for item in folder_path.iterdir():
                    if item.is_file() and not item.name.startswith("."):
                        if self._is_valid_image(item):
                            add_file(item)

            # Check for duplicates - ensure consistent sorting
            duplicates = {
                name: sorted(paths)
                for name, paths in name_map.items()
                if len(paths) > 1
            }
            if duplicates:
                msg = "Duplicate image names found:\n" + "\n".join(
                    f"[{', '.join(paths)}]" for paths in sorted(duplicates.values())
                )
                self.add_error(msg)
                raise ValueError(msg)

            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Error checking image names: {str(e)}")
            return False

    def _check_duplicate_image_content(self, base_path: Path) -> bool:
        """Check ONLY for duplicate image content using image hashing"""
        try:
            hash_map = defaultdict(list)

            # Helper function to add file to hash_map
            def add_file(file_path: Path):
                if self._is_valid_image(file_path):
                    with open(file_path, "rb") as f:
                        content = f.read()
                    # Store path - if in base folder, just filename, otherwise relative path
                    if file_path.parent == base_path:
                        hash_map[content].append(file_path.name)
                    else:
                        rel_path = file_path.relative_to(base_path)
                        hash_map[content].append(str(rel_path))

            # Process base folder
            for item in base_path.iterdir():
                if item.is_file() and not item.name.startswith("."):
                    add_file(item)

            # Process content folders
            for folder in sorted(self.content_types):  # Sort folders for consistency
                folder_path = base_path / folder
                if not folder_path.exists():
                    continue

                for item in folder_path.iterdir():
                    if item.is_file() and not item.name.startswith("."):
                        add_file(item)

            # Check for duplicates - ensure consistent sorting
            duplicates = [
                sorted(paths) for paths in hash_map.values() if len(paths) > 1
            ]
            if duplicates:
                msg = "Duplicate images found:\n" + "\n".join(
                    f"[{', '.join(paths)}]" for paths in sorted(duplicates)
                )
                self.add_error(msg)
                raise ValueError(msg)

            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Error checking image content: {str(e)}")
            return False
