import os 

def bulk_rename(
    folder_path: str, 
    prefix: str = "video", 
    dry_run: bool = True,
    file_types: list[str] = ["mp4"]
) -> None:
    """
    Bulk rename files in a folder using a prefix + number scheme
    Args:
        folder_path: Path to folder containing files to rename
        prefix: Prefix for new filenames (e.g., "haul" -> "haul_1.mp4", "haul_2.mp4")
        dry_run: If True, only print what would happen without actually renaming
        file_types: List of file extensions to process (without dots, e.g., ["mp4", "jpg"])
    """
    if not os.path.exists(folder_path):
        raise ValueError(f"Folder not found: {folder_path}")

    # Normalize extensions to lowercase with dots
    extensions = {f".{ext.lower().strip('.')}" for ext in file_types}

    # Get all matching files as a set
    matching_files = {
        f
        for f in os.listdir(folder_path)
        if os.path.splitext(f)[1].lower() in extensions
    }

    if not matching_files:
        print(f"No files found with extensions: {', '.join(file_types)}")
        return

    total_files = len(matching_files)
    print(f"Found {total_files} files")
    
    # Group files by extension for reporting
    by_extension = {}
    for f in matching_files:
        ext = os.path.splitext(f)[1].lower()
        by_extension.setdefault(ext, []).append(f)
    
    for ext, files in sorted(by_extension.items()):
        print(f"  {ext}: {len(files)} files")

    # Create rename map with new names for all files
    rename_map = {}
    for i, filename in enumerate(sorted(matching_files), 1):
        _, ext = os.path.splitext(filename)
        new_name = f"{prefix}_{i}{ext}"
        rename_map[filename] = new_name

    # Safety checks
    if len(rename_map) != total_files:
        raise ValueError("SAFETY CHECK FAILED: Not all files accounted for!")
    if len(set(rename_map.values())) != total_files:
        raise ValueError("SAFETY CHECK FAILED: Duplicate target names detected!")

    # Show the plan
    print("\nRename plan:")
    for old_name, new_name in sorted(rename_map.items()):
        if old_name != new_name:
            print(f"'{old_name}' -> '{new_name}'")
        else:
            print(f"'{old_name}' (no change)")

    # Only rename if not dry run and user confirms
    if not dry_run:
        confirm = input("\nProceed with rename? (yes/no): ")
        if confirm.lower() != "yes":
            print("Aborting.")
            return

        # Actually do the renaming
        for old_name, new_name in rename_map.items():
            if old_name != new_name:
                old_path = os.path.join(folder_path, old_name)
                new_path = os.path.join(folder_path, new_name)
                os.rename(old_path, new_path)
                print(f"Renamed: '{old_name}' -> '{new_name}'")

    print(
        f"\nComplete! {len([k for k,v in rename_map.items() if k != v])} files renamed"
    )
