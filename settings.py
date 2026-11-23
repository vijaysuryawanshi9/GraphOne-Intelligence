
import os
from pathlib import Path
from dotenv import load_dotenv

# Project root directory
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env
load_dotenv(BASE_DIR / ".env")

# Project information
PROJECT_NAME = "GraphOne Intelligence"

# Data directories
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"

# Logs
LOG_DIR = BASE_DIR / "logs"
LOG_LEVEL = "INFO"

# Crawler configuration
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2

# Data processing
BATCH_SIZE = 500

# Google Sheets configuration
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_SERVICE_ACCOUNT_FILE = (
    BASE_DIR / os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_FILE",
        "credentials/google_service_account.json"
    )
)

# LLM provider configuration
LLM_PROVIDER_ORDER = [
    "gemini",
    "groq",
    "deepseek",
]

# Create required directories if missing
for directory in [
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    LOG_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)
