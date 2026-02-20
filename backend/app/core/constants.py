"""
constants.py

Constants used throughout the CI/CD pipeline healing system.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# GitHub API configuration
GITHUB_API_BASE = "https://api.github.com"

# Database configuration
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ci_healer")

# Supported bug types for classification
BUG_TYPES = [
    "LINTING",
    "SYNTAX", 
    "LOGIC",
    "TYPE_ERROR",
    "IMPORT",
    "INDENTATION",
]

# Default configuration values
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT = 120
DEFAULT_COMMIT_PREFIX = "[AI-AGENT]"
