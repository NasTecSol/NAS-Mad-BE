import os
import importlib
import sys
from config.settings import settings
from utils.logger import logger
from openai._client import OpenAI

def create_openai_client():
    """
    Create a minimal OpenAI client without any extra configurations
    """
    try:
        # Get API key from environment directly
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.error("OpenAI API key not set in environment variables")
            return None
        
        # Import dynamically to avoid any module-level configurations
        sys.path.insert(0, os.path.abspath("."))
        
        
        # Create the most minimal client possible
        client = OpenAI(api_key=api_key)
        
        logger.info("Successfully created minimal OpenAI client")
        return client
    except Exception as e:
        logger.error(f"Minimal client creation failed: {str(e)}")
        return None