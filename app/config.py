
import os
from pathlib import Path

from dotenv import load_dotenv

# Resolve paths relative to the project directory.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load local development configuration.
load_dotenv(BASE_DIR / ".env")

# Use an absolute database path so startup location
# does not accidentally create a second database.
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{(BASE_DIR / 'shaha_lms.db').as_posix()}",
)

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is missing. Configure it in your .env file."
    )