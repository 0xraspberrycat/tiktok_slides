import json
from pathlib import Path

from content_manager.settings.settings_constants import DEFAULT_TEMPLATE

# Load default template once for all tests
with open(DEFAULT_TEMPLATE) as f:
    DEFAULT_SETTINGS = json.load(f)

# Load example metadata for tests
EXAMPLE_METADATA_PATH = Path("tests/metadata_example.json")
with open(EXAMPLE_METADATA_PATH) as f:
    EXAMPLE_METADATA = json.load(f)
from content_manager.settings.settings_constants import DEFAULT_TEMPLATE

# Load default template once for all tests
with open(DEFAULT_TEMPLATE) as f:
    DEFAULT_SETTINGS = json.load(f)