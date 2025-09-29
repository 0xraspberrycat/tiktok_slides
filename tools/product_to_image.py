from pathlib import Path
from content_manager.metadata.metadata_validator import MetadataValidator
import json
from typing import Union, Dict, List, Tuple

def create_product_mapping(metadata_path: str, image_prefix_mapping: dict, print_output: bool = True) -> tuple[dict, list]:
    """
    Read metadata and create preview of product mappings based on image prefixes
    
    Args:
        metadata_path: Path to metadata JSON
        image_prefix_mapping: Dict of image_prefix -> product mappings
        print_output: Whether to print results summary
    
    Returns:
        tuple: (
            dict of image_name -> product mappings,
            list of unmatched image names
        )
        
    Example:
        image_prefix_mapping = {
            "hook_": "product1",
            "shill_": "product2",
            "follow_": "product3"
        }
        
        mappings, unmatched = create_product_mapping("metadata.json", image_prefix_mapping)
        # Sample output:
        # Found 50 images to map
        # hook_1.jpg: product1
        # shill_2.jpg: product2
    """
    metadata_path = Path(metadata_path)
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
        
    
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    image_product_map = {}
    unmatched_images = []
    
    # Loop through structure items
    for key in metadata['structure']:
        # Get list of images for this key
        images = metadata['structure'][key]['images']
        
        for image in images:
            # Check if image starts with any of our prefixes
            matched = False
            for prefix, product in image_prefix_mapping.items():
                if image.startswith(prefix):
                    image_product_map[image] = product
                    matched = True
                    break
                    
            if not matched:
                unmatched_images.append(image)
    
    if print_output:
        print(f"Found {len(image_product_map)} images to map")
        print(f"Found {len(unmatched_images)} unmatched images")
        if unmatched_images:
            print("Unmatched images:")
            for img in unmatched_images:
                print(f"- {img}")
            
    return image_product_map, unmatched_images

def apply_product_mapping(
    metadata_path: str, 
    image_product_map: Union[Tuple[Dict, List], Dict], 
    overwrite: bool = False, 
    print_output: bool = True
) -> Tuple[List, List]:
    """
    Apply product mapping to metadata file
    
    Args:
        metadata_path: Path to metadata JSON
        image_product_map: Either:
            - Tuple of (mapping_dict, unmatched_list) from create_product_mapping
            - Direct dictionary of image_name -> product mappings
        overwrite: Whether to overwrite existing product assignments
        print_output: Whether to print results
        
    Returns:
        tuple: (
            list of skipped images (didn't exist),
            list of conflict tuples (image, current_product, target_product)
        )
        
    Example:
        skipped, conflicts = apply_product_mapping(
            "metadata.json",
            {"hook_1.jpg": "product1"},
            overwrite=False
        )
    """
    metadata_path = Path(metadata_path)
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
        
    # Handle both tuple and direct dict input
    if isinstance(image_product_map, tuple):
        mapping_dict, _ = image_product_map
    else:
        mapping_dict = image_product_map
    
    # Initialize validator
    validator = MetadataValidator(metadata_path.parent)
    
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    # Get content types and products from metadata
    content_types = metadata.get('content_types', [])
    products_by_type = metadata.get('products', {})
    
    # Validate metadata structure
    valid_products = {
        ct: [p['name'] for p in products_by_type.get(ct, [])]
        for ct in content_types
    }
    
    # TODO Validate each mapping
    # for image_name, target_product in mapping_dict.items():
    #     if image_name in metadata.get('images', {}):
    #         content_type = metadata['images'][image_name]['content_type']
    #         if target_product not in valid_products[content_type]:
    #             raise ValueError(
    #                 f"Invalid product '{target_product}' for {content_type}. "
    #                 f"Valid products: {valid_products[content_type]}"
    #             )
    
    # Now proceed with the rest of the function as before
    skipped_images = []
    conflicts = []
    updated_count = 0
    
    # Process each image
    for image_name, target_product in mapping_dict.items():
        # Check if image exists in metadata
        if image_name not in metadata.get('images', {}):
            skipped_images.append(image_name)
            continue
            
        # Get current product assignment
        current_product = metadata['images'][image_name].get('product')
        
        # Determine if we should update
        should_update = False
        if current_product is None:
            should_update = True
        elif current_product == target_product:
            continue  # Skip if same product
        elif overwrite:
            should_update = True
        else:
            conflicts.append((image_name, current_product, target_product))
            continue
            
        if should_update:
            metadata['images'][image_name]['product'] = target_product
            updated_count += 1
    
    # Save changes
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
        
    if print_output:
        print(f"\nUpdated {updated_count} images")
        print(f"Skipped {len(skipped_images)} images (not found in metadata)")
        if conflicts:
            print(f"\nFound {len(conflicts)} conflicts:")
            for img, curr, target in conflicts:
                print(f"- {img}: current='{curr}' target='{target}'")
    
    return skipped_images, conflicts

# Usage example:
"""
metadata_path = "path/to/metadata.json"
mapping_result = create_product_mapping(metadata_path, prefix_mapping)
skipped, conflicts = apply_product_mapping(metadata_path, mapping_result)
"""
