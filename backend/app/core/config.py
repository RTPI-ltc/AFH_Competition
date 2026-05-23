"""Application configuration."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

# Load .env file
load_dotenv(BASE_DIR / ".env")

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# LLM Configuration
LLM_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
