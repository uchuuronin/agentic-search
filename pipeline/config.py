# Loading application configurations from env file
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # LLM Related
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

    # Search Related
    MAX_SEARCH_RESULTS: int = int(os.getenv("MAX_SEARCH_RESULTS", "10"))
    MAX_PAGES_TO_SCRAPE: int = int(os.getenv("MAX_PAGES_TO_SCRAPE", "8"))
    SCRAPE_TIMEOUT_SECONDS: int = int(os.getenv("SCRAPE_TIMEOUT_SECONDS", "10"))
    MAX_CONTENT_CHARS: int = int(os.getenv("MAX_CONTENT_CHARS", "6000"))

    # Reflection Related
    MAX_REFLECTION_ROUNDS: int = int(os.getenv("MAX_REFLECTION_ROUNDS", "1"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()