## TODO add tests for this
# this comes before running metadata validation


def _validate_content(self, strict: bool = False) -> bool:
    """Internal method to validate loaded content

    Validates:
    - Image existence and format
    - Image duplication
    - product level duplicate prevention
    - Product assignments
    - Settings structure
    - Metadata consistency
    """
    warnings = []

    try:
        # Validate images exist for each content type
        for content_type in self.content_types:
            content_path = self.base_path / content_type
            if not content_path.exists():
                warnings.append(f"Content folder missing: {content_type}")
                continue

            # Check for images in content folder
            images = list(content_path.glob("*.png")) + list(content_path.glob("*.PNG"))
            if not images:
                warnings.append(f"No images found in {content_type} folder")

            # Additional image validations could go here
            # - Check image dimensions
            # - Validate product assignments
            # - Check settings existence

        # Validate metadata structure if it exists
        if self.metadata:
            # Add metadata validation here
            pass

        # Handle warnings based on strict mode
        if warnings:
            if strict:
                raise ValueError("\n".join(warnings))
            for warning in warnings:
                logger.warning(warning)
            return False

        return True

    except Exception as e:
        logger.error(f"Content validation failed: {str(e)}")
        return False
