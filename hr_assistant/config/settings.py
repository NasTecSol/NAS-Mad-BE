# config/settings.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    # API Settings
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")

    # HR System API Settings (Legacy - kept for backward compatibility)
    HR_API_BASE_URL = os.getenv(
        "HR_API_BASE_URL", "https://dev.nashrms.com/api")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

    # MongoDB Settings
    MONGODB_URI = os.getenv("MONGODB_URI")
    MONGODB_HOST = os.getenv("MONGODB_HOST", "localhost")
    MONGODB_PORT = int(os.getenv("MONGODB_PORT", "27017"))
    MONGODB_USER = os.getenv("MONGODB_USER")
    MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD")
    MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "nas_hr")
    MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "employees")

    # Vector Search Settings
    VECTOR_INDEX_NAME = os.getenv("VECTOR_INDEX_NAME", "employee_vector_index")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    VECTOR_SEARCH_LIMIT = int(os.getenv("VECTOR_SEARCH_LIMIT", "10"))

    # Default Credentials (Legacy)
    DEFAULT_PASSWORD = os.getenv("DEFAULT_PASSWORD", "123456")
    DEFAULT_MAC_ADDRESS = os.getenv("DEFAULT_MAC_ADDRESS", "206.84.153.69")

    # Logging Settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "hr_assistant.log")

    # Access Control Settings
    DEFAULT_ACCESS_LEVEL = os.getenv("DEFAULT_ACCESS_LEVEL", "L4")
    ENABLE_ENHANCED_LOGGING = os.getenv(
        "ENABLE_ENHANCED_LOGGING", "false").lower() == "true"

    # Performance Settings
    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))  # 1 hour
    MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "50"))
    QUERY_TIMEOUT_SECONDS = int(os.getenv("QUERY_TIMEOUT_SECONDS", "30"))


settings = Settings()
