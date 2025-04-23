import logging
import sys
from config.settings import settings

# Configure logging
def setup_logger():
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format=log_format,
        handlers=[
            logging.FileHandler(settings.LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger("hr_assistant")

logger = setup_logger()