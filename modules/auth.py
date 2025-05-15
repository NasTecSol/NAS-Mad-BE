from typing import Dict, Any
from langchain.tools import Tool
from utils.logger import logger

# Global service reference
hr_service = None

def initialize(service):
    global hr_service
    hr_service = service

def login_employee_tool(username: str, password: str = None, mac_address: str = None) -> Dict[str, Any]:
    """
    Login employee using credentials and return access token.
    
    Args:
        username: Employee username (e.g., EMP103)
        password: Employee password (optional)
        mac_address: Employee device MAC address (optional)
    
    Returns:
        Dictionary containing login result and token if successful
    """
    logger.info(f"Login tool called for employee: {username}")
    
    # Ensure username is a string
    if not isinstance(username, str):
        logger.error(f"Invalid username type: {type(username)}")
        return {
            "success": False,
            "message": "Username must be a string"
        }
    
    # Call HR service
    return hr_service.login(username, password, mac_address)

# Create the LangChain tool
login_employee = Tool(
    name="login_employee",
    description="Login employee using credentials and return access token",
    func=login_employee_tool
)