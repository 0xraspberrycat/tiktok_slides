import csv
from pathlib import Path
from typing import Dict, List, Set, Tuple

from config.logging import logger

from .strict_validator import StrictValidator

INVALID_PRODUCT_NAMES = {"none", "null"}


class CaptionsValidator(StrictValidator):
    def __init__(self, strict: bool = False):
        super().__init__(strict)
        self.separator = ","
        self.content_types: Set[str] = set()
        self.products: Dict[str, Set[str]] = {}
        self.validation_messages: List[Tuple[str, str]] = []

    def validate(
        self, file_path: Path, separator: str = ","
    ) -> Tuple[Set[str], Dict[str, Set[str]]]:
        """Main validation method"""
        self.separator = separator
        self.clear_messages()

        # Basic file checks first
        if not self._validate_file_basics(file_path):
            self.raise_if_errors()
            return set(), {}

        # Header checks
        if not self._validate_headers(file_path):
            self.raise_if_errors()
            return set(), {}

        # Run all validation checks
        checks = [
            self._check_unquoted_empty_rows,
            self._check_empty_rows,
            self._check_column_count,
            self._check_string_cells,
            self._check_whitespace_cells,
            self._check_empty_content_format,
            self._check_product_cells,
            self._populate_products,
            self._check_product_name_not_content_type,
            self._check_reserved_product_names,
            self._check_unique_product_names,
        ]

        validation_passed = True
        for check in checks:
            result = check(file_path)

            if not result:
                # Special case: allow empty product cell warnings
                if check == self._check_product_cells and all(
                    "Empty product cell" in w for w in self.warnings
                ):
                    continue

                validation_passed = False
                if self.errors:  # If there are errors, raise them
                    self.raise_if_errors()
                    return set(), {}

        if not validation_passed:
            return set(), {}

        return self.content_types, self.products

    def _validate_file_basics(self, file_path: Path) -> bool:
        """Validate basic file requirements

        Args:
            file_path: Path to CSV file

        Returns:
            bool: True if valid, False if validation fails
        """
        # Check if file exists
        if not file_path.exists():
            self.add_error(f"File does not exist: {file_path}")
            logger.critical(f"Validation failed: File does not exist at {file_path}")
            return False

        # Check if it's a file (not a directory)
        if not file_path.is_file():
            self.add_error(f"Path is not a file: {file_path}")
            logger.critical(f"Validation failed: Path is not a file at {file_path}")
            return False

        # Check if file is empty
        if file_path.stat().st_size == 0:
            self.add_error(f"File is empty: {file_path}")
            logger.critical(f"Validation failed: File is empty at {file_path}")
            return False

        # Check UTF-8 encoding
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                f.read()
        except UnicodeDecodeError:
            self.add_error(f"File is not UTF-8 encoded: {file_path}")
            logger.debug(f"Validation failed: File is not UTF-8 encoded at {file_path}")
            return False

        return True

    def _validate_headers(self, file_path: Path) -> bool:
        """Validate headers one check at a time"""
        logger.debug(f"Validating headers called from: {file_path}")
        logger.debug(f"Current separator is: {self.separator}")

        # 1. Read header line
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=self.separator)
                headers = next(reader)  # Get first line as list

            logger.debug(
                f"Headers after reading with separator '{self.separator}': {headers}"
            )

        except Exception as e:
            self.add_error(f"Failed to read headers: {str(e)}")
            return False

        # 2. Check if headers exist
        if not headers:
            self.add_error("Headers must exist")
            return False

        # 3. Check for empty/whitespace headers
        if any(not h for h in headers):
            self.add_error("Headers cannot be empty or whitespace")
            return False

        # 4. Check product header format - with detailed logging
        logger.debug(f"Raw headers received: {headers}")

        for header in headers:
            # Skip non-product headers
            if not header.lower().startswith("product"):
                logger.debug(f"Skipping non-product header: {header}")
                continue

            logger.debug(f"Validating product header: {header}")

            # Clean and split header
            header = header.strip()
            parts = header.split("_")
            logger.debug(f"Header parts after split: {parts}")

            if len(parts) != 2 or parts[0] != "product":
                error_msg = (
                    f"Invalid product header format: {header}. Must be 'product_type'"
                )
                logger.debug(f"Validation failed: {error_msg}")
                logger.debug(f"Split parts were: {parts}")
                self.add_error(error_msg)
                return False

            logger.debug(f"Valid product header: {header} -> type: {parts[1]}")

        # 5. Check content/product pairs
        product_headers = [h for h in headers if h.startswith("product_")]
        content_headers = [h for h in headers if not h.startswith("product_")]

        for content_header in content_headers:
            if f"product_{content_header}" not in product_headers:
                self.add_error(
                    f"Content header '{content_header}' has no matching product header"
                )
                return False

        # 6. Store valid content types
        self.content_types = set(h for h in headers if not h.startswith("product_"))

        return True

    def _validate_data_consistency(self) -> bool:
        """Validate data consistency across the file"""
        try:
            # Check that all content types exist in products dictionary
            if set(self.products.keys()) != self.content_types:
                self.add_error("Content types mismatch between headers and data")
                return False

            return True

        except Exception as e:
            self.add_error(f"Failed to validate data consistency: {str(e)}")
            logger.critical(
                f"Validation failed: Error validating data consistency: {str(e)}"
            )
            return False

    def _check_empty_rows(self, file_path: Path) -> bool:
        """Check ONLY for completely empty unquoted rows"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                next(f)  # Skip header
                for row_num, line in enumerate(f, start=2):
                    stripped = line.strip()

                    # Case 1: Just commas (,,,)
                    if all(c in [",", " "] for c in stripped):
                        self.add_error(
                            f"Row {row_num} cannot be empty (use quotes for empty cells)"
                        )
                        raise ValueError(
                            f"Row {row_num} cannot be empty (use quotes for empty cells)"
                        )

                    # Case 2: Has proper empty quotes (,"",,"")
                    if '""' in stripped:
                        continue

            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Unexpected error checking empty rows: {str(e)}")
            return False

    def _check_column_count(self, file_path: Path) -> bool:
        """Check ONLY column counts"""
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=self.separator)
            headers = next(reader)
            expected_columns = len(headers)

            for row_num, row in enumerate(reader, start=2):
                if len(row) != expected_columns:
                    self.add_error(f"Row {row_num} has incorrect number of columns")
                    return False
        return True

    def _check_string_cells(self, file_path: Path) -> bool:
        """Check ONLY that all cells are strings and look like strings"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=self.separator)
                next(reader)  # Skip headers

                for row_num, row in enumerate(reader, start=2):
                    for col_num, cell in enumerate(row):
                        # Check if cell looks like a number
                        if cell.isdigit():
                            self.add_error(
                                f"Cell at row {row_num}, column {col_num} is not a string"
                            )
                            raise ValueError(
                                f"Cell at row {row_num}, column {col_num} is not a string"
                            )

                return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Unexpected error checking string cells: {str(e)}")
            return False

    def _check_whitespace_cells(self, file_path: Path) -> bool:
        """Check ONLY that cells are not unquoted whitespace-only"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=self.separator)
                next(reader)  # Skip headers

                for row_num, row in enumerate(reader, start=2):
                    for col_num, cell in enumerate(row):
                        # Skip empty cells
                        if not cell:
                            continue

                        # Skip any cells that contain quotes
                        if '"' in cell:
                            continue

                        # Now check if unquoted cell is only whitespace
                        if cell.strip() == "":
                            self.add_error(
                                f"Cell at row {row_num}, column {col_num + 1} is whitespace only"
                            )
                            raise ValueError(
                                f"Cell at row {row_num}, column {col_num + 1} is whitespace only"
                            )

            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Unexpected error checking whitespace cells: {str(e)}")
            return False

    def _check_empty_cell_quotes(self, file_path: Path) -> bool:
        """Check ONLY that empty cells use explicit quotes ("")"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                lines = content.splitlines()
                headers = lines[0].split(self.separator)

                # Get indices for content columns (non-product)
                content_indices = [
                    i for i, h in enumerate(headers) if not h.startswith("product_")
                ]

                for row_num, line in enumerate(lines[1:], start=2):
                    cells = line.split(self.separator)
                    for idx in content_indices:  # Only check content cells
                        # Check if content cell is empty without quotes
                        if not cells[idx].strip() and not cells[idx].strip('"'):
                            self.add_error(
                                f'Empty content cell at row {row_num}, column {idx+1} must use explicit quotes ("")'
                            )
                            raise ValueError(
                                f'Empty content cell at row {row_num}, column {idx+1} must use explicit quotes ("")'
                            )

            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Unexpected error checking empty cells: {str(e)}")
            return False

    def _populate_products(self, file_path: Path) -> bool:
        """Populate content types and products dictionary"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=self.separator)
                headers = next(reader)

                # Initialize products dict with all content types
                product_cols = [
                    (i, h[8:])  # Get index and content type
                    for i, h in enumerate(headers)
                    if h.startswith("product_")
                ]

                # Initialize all content types with empty lists
                self.content_types = {content_type for _, content_type in product_cols}
                self.products = {
                    content_type: set() for _, content_type in product_cols
                }

                # Now populate with non-empty products
                for row in reader:
                    for col_idx, content_type in product_cols:
                        product = row[col_idx].strip()
                        if product and product != '""':  # Only add non-empty products
                            self.products[content_type].add(
                                product
                            )  # add() instead of append()

                # Convert sets to sorted lists at the end
                self.products = {
                    ct: sorted(prods) for ct, prods in self.products.items()
                }

                return True

        except Exception as e:
            self.add_error(f"Unexpected error populating products: {str(e)}")
            return False

    def _check_product_cells(self, file_path: Path) -> bool:
        """Check ONLY product cells for validity"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=self.separator)
                headers = next(reader)

                # Get product column indices
                product_cols = [
                    i for i, h in enumerate(headers) if h.startswith("product_")
                ]

                for row_num, row in enumerate(reader, start=2):
                    for col in product_cols:
                        cell = row[col]
                        content_type = headers[col][8:]  # Skip 'product_' prefix

                        # Empty cell checks
                        if not cell or cell.strip() == '""':
                            self.add_warning(
                                f"Empty product cell at row {row_num}, column {col + 1}"
                            )
                            continue

                        # Check for unquoted whitespace
                        if cell.strip() == "" and not (
                            cell.startswith('"') and cell.endswith('"')
                        ):
                            self.add_error(
                                f"Product cell at row {row_num}, column {col + 1} contains unquoted whitespace"
                            )
                            raise ValueError(
                                f"Product cell at row {row_num}, column {col + 1} contains unquoted whitespace"
                            )

            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Unexpected error checking product cells: {str(e)}")
            return False

    def _check_empty_content_format(self, file_path: Path) -> bool:
        """Check ONLY that empty content cells use explicit quotes (\"\")"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                headers = lines[0].strip().split(self.separator)

                # Get indices for content columns
                content_indices = [
                    i for i, h in enumerate(headers) if not h.startswith("product_")
                ]

                for row_num, line in enumerate(lines[1:], start=2):
                    cells = line.strip().split(self.separator)

                    for idx in content_indices:
                        raw_cell = cells[idx].strip()

                        # Empty cell must be exactly '""'
                        if not raw_cell or raw_cell.strip('"') == "":
                            if raw_cell != '""':
                                self.add_error(
                                    f'Empty content cell at row {row_num}, column {idx+1} must use explicit quotes ("")'
                                )
                                raise ValueError(
                                    f'Empty content cell at row {row_num}, column {idx+1} must use explicit quotes ("")'
                                )

            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Unexpected error checking empty content format: {str(e)}")
            return False

    def _check_product_name_not_content_type(self, file_path: Path) -> bool:
        """Check ONLY that product names don't match content types"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=self.separator)
                headers = next(reader)

                # Get content types and their product column indices
                content_types = {
                    h.lower() for h in headers if not h.startswith("product_")
                }
                product_indices = [
                    (i, headers[i][8:])
                    for i, h in enumerate(headers)
                    if h.startswith("product_")
                ]

                for row_num, row in enumerate(reader, start=2):
                    for idx, content_type in product_indices:
                        product = row[idx].strip().lower()
                        if product and product in content_types:
                            self.add_error(
                                f"Product name '{product}' at row {row_num}, column {idx+1} cannot match content type"
                            )
                            raise ValueError(
                                f"Product name '{product}' at row {row_num}, column {idx+1} cannot match content type"
                            )

            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Unexpected error checking product names: {str(e)}")
            return False

    def _check_reserved_product_names(self, file_path: Path) -> bool:
        """Check ONLY that product names are not 'none' (case insensitive)"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=self.separator)
                headers = next(reader)

                # Get product column indices
                product_indices = [
                    i for i, h in enumerate(headers) if h.startswith("product_")
                ]

                for row_num, row in enumerate(reader, start=2):
                    for idx in product_indices:
                        product = row[idx].strip().lower()
                        if product in INVALID_PRODUCT_NAMES:  # only checks for "none"
                            self.add_error(
                                f"Product name '{product}' at row {row_num}, column {idx+1} is a reserved word"
                            )
                            raise ValueError(
                                f"Product name '{product}' at row {row_num}, column {idx+1} is a reserved word"
                            )

            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(
                f"Unexpected error checking reserved product names: {str(e)}"
            )
            return False

    def _check_unique_product_names(self, file_path: Path) -> bool:
        """Check ONLY that product names don't have case variations within their type"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=self.separator)
                headers = next(reader)

                # Get product column indices
                product_indices = [
                    (i, h[8:])
                    for i, h in enumerate(headers)
                    if h.startswith("product_")
                ]

                has_warnings = False  # Track if we found any issues

                # Track seen products per type with their original case
                seen_products = {
                    content_type: {} for _, content_type in product_indices
                }

                for row_num, row in enumerate(reader, start=2):
                    for idx, content_type in product_indices:
                        product = row[idx].strip()
                        if not product:  # Skip empty
                            continue

                        product_lower = product.lower()

                        # Special handling for 'all'
                        if product_lower == "all" and product != "all":
                            msg = f"Product 'all' must be lowercase at row {row_num}"
                            self.add_warning(msg)
                            has_warnings = True
                            continue

                        # If we've seen this lowercase version before
                        if product_lower in seen_products[content_type]:
                            # Only warn if it's a different case version
                            if product != seen_products[content_type][product_lower]:
                                msg = f"Duplicate product name '{product}' at row {row_num} (previously seen as '{seen_products[content_type][product_lower]}')"
                                self.add_warning(msg)
                                has_warnings = True
                        else:
                            # First time seeing this product
                            seen_products[content_type][product_lower] = product

                return not has_warnings  # Return False if we found any issues

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Unexpected error checking product name cases: {str(e)}")
            return False

    def _check_unquoted_empty_rows(self, file_path: Path) -> bool:
        """Check ONLY for rows that are just commas with no quotes (,,,)"""
        try:
            with open(file_path, "r") as f:
                next(f)  # Skip header
                for row_num, line in enumerate(f, start=2):
                    stripped_line = line.strip()

                    if stripped_line and all(c in [",", " "] for c in stripped_line):
                        self.add_error(
                            f"Row {row_num} is empty or contains only whitespace"
                        )
                        raise ValueError(
                            f"Row {row_num} is empty or contains only whitespace"
                        )

            return True

        except ValueError:
            raise
        except Exception as e:
            self.add_error(f"Unexpected error checking empty rows: {str(e)}")
            return False


# TODO TESTS FOR CAPTIONSHELPER
class CaptionsHelper:
    @staticmethod
    def get_product_min_occurrences(
        file_path: Path, separator: str = ","
    ) -> Dict[str, List[Dict]]:
        """Get maximum occurrences of each product per content type.

        Args:
            file_path: Path to validated captions.csv
            separator: CSV separator character

        Returns:
            Dict[content_type, List[product_dict]]
            Example: {
                "content": [
                    {"name": "magnesium", "prevent_duplicates": False, "min_occurrences": 3},
                    {"name": "zinc", "prevent_duplicates": False, "min_occurrences": 2}
                ],
                "hook": [
                    {"name": "magnesium", "prevent_duplicates": False, "min_occurrences": 1}
                ]
            }
        """
        product_info = {}

        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=separator)
            headers = next(reader)

            # Get product columns and their content types
            product_cols = [
                (i, h[8:]) for i, h in enumerate(headers) if h.startswith("product_")
            ]

            # Initialize tracking
            product_info = {ct: {} for _, ct in product_cols}

            # Process each row
            for row in reader:
                # Count products in this row
                for col_idx, content_type in product_cols:
                    product = row[col_idx].strip()
                    if product and product != '""':
                        # Update max count if this row has more
                        current_max = (
                            product_info[content_type]
                            .get(product, {})
                            .get("min_occurrences", 0)
                        )
                        row_count = sum(
                            1
                            for i, ct in product_cols
                            if ct == content_type and row[i].strip() == product
                        )

                        product_info[content_type][product] = {
                            "min_occurrences": max(current_max, row_count)
                        }

        # Convert to final format matching metadata structure
        return {
            ct: [
                {
                    "name": prod_name,
                    "prevent_duplicates": False,  # This will be set later in metadata
                    "min_occurrences": info["min_occurrences"],
                }
                for prod_name, info in sorted(prods.items())  # Sort by product name
            ]
            for ct, prods in product_info.items()
        }

    """    
    @staticmethod
    def get_captions(
        captions_path: Path,
        content_types: Set[str],
        products: Dict[str, List[str]],
        separator: str
    ) -> Dict:
        "" "Get captions from CSV file and organize by type and product" ""

        # Read CSV with proper separator
        with open(captions_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=separator)
            headers = next(reader)  # Get headers
            rows = list(reader)  # Get all rows

        # Clean headers
        headers = [h.strip() for h in headers]
        print("headers", headers)

        # Initialize structure
        by_type = {
            content_type: {product: [] for product in products[content_type]}
            for content_type in content_types
        }

        # Process each row
        for row in rows:
            # Clean row data
            row = [cell.strip() for cell in row]

            # For each content type
            for content_type in content_types:
                product_idx = headers.index(f"product_{content_type}")
                content_idx = headers.index(content_type)

                # Get product and content
                product = row[product_idx]
                content = row[content_idx]

                if product and content:  # Only add if both exist
                    if product not in by_type[content_type]:
                        by_type[content_type][product] = []
                    by_type[content_type][product].append(content)

        return {"headers": headers, "captions": rows, "by_type": by_type}
    """
    @staticmethod
    def get_captions(
        captions_path: Path,
        content_types: Set[str],
        products: Dict[str, List[str]],
        separator: str
    ) -> Dict:
        """Get captions from CSV file and organize by type and product"""
        
        # Read file content first
        with open(captions_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Split into lines and process
        lines = content.strip().split('\n')
        headers = [h.strip() for h in lines[0].split(separator)]
        rows = [line.split(separator) for line in lines[1:]]

        # Initialize structure
        by_type = {
            content_type: {product: [] for product in products[content_type]}
            for content_type in content_types
        }

        # Process each row
        for row in rows:
            # For each content type
            for content_type in content_types:
                try:
                    # Find all occurrences of product/content pairs for this type
                    product_indices = [i for i, h in enumerate(headers) if h == f"product_{content_type}"]
                    content_indices = [i for i, h in enumerate(headers) if h == content_type]
                    
                    # Process each pair of indices
                    for product_idx, content_idx in zip(product_indices, content_indices):
                        if product_idx < len(row) and content_idx < len(row):
                            product = row[product_idx].strip()
                            content = row[content_idx].strip()
                            
                            if product and content:  # Only add if both exist
                                if product in products[content_type]:
                                    if product not in by_type[content_type]:
                                        by_type[content_type][product] = []
                                    by_type[content_type][product].append(content)
                except (ValueError, IndexError):
                    continue

        return {"headers": headers, "captions": rows, "by_type": by_type}