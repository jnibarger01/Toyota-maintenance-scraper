"""
Scraper configuration settings.
"""
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PDF_DIR = DATA_DIR / "pdfs"
OUTPUT_DIR = PROJECT_ROOT / "output"

# Create directories
PDF_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Rate limiting (requests per second)
TOYOTA_PDF_RATE_LIMIT = 1.0  # Conservative for PDF downloads
FUELECONOMY_RATE_LIMIT = 2.0  # Public API, more permissive

# Retry settings
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  # Exponential backoff multiplier

# HTTP settings
REQUEST_TIMEOUT = 30.0
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# FuelEconomy.gov API
FUELECONOMY_BASE_URL = "https://www.fueleconomy.gov/ws/rest"

# Output files
OUTPUT_JSONL = OUTPUT_DIR / "maintenance.jsonl"
OUTPUT_CSV = OUTPUT_DIR / "maintenance.csv"
VEHICLE_SPECS_JSONL = OUTPUT_DIR / "vehicle_specs.jsonl"
VEHICLE_SPECS_CSV = OUTPUT_DIR / "vehicle_specs.csv"

# Logging
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"
