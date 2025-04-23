import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    # API Settings
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
    
    # HR System API Settings
    HR_API_BASE_URL = os.getenv("HR_API_BASE_URL", "https://dev.nashrms.com/api")
    JWT_SECRET_KEY  = os.getenv("JWT_SECRET_KEY")
    
    # Default Credentials
    DEFAULT_PASSWORD = os.getenv("DEFAULT_PASSWORD", "123456")
    DEFAULT_MAC_ADDRESS = os.getenv("DEFAULT_MAC_ADDRESS", "206.84.153.69")
    
    # Logging Settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "hr_assistant.log")

settings = Settings()