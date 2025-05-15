from typing import Dict, Any
from langchain.tools import Tool
from utils.logger import logger

# Global service reference
hr_service = None

def initialize(service):
    global hr_service
    hr_service = service

def get_employee_data_tool(employee_id: str) -> Dict[str, Any]:
    """
    Get detailed employee data using employee ID.
    
    Args:
        employee_id: Employee ID (e.g., EMP103)
    
    Returns:
        Dictionary containing employee data
    """
    logger.info(f"Get employee data tool called for: {employee_id}")
    
    # Validate input
    if not employee_id:
        logger.error("Employee ID is missing or empty")
        return {
            "success": False,
            "message": "Employee ID is required"
        }
    
    # Call the HR service
    return hr_service.get_employee_data(employee_id)

# Create the LangChain tool
get_employee_data = Tool(
    name="get_employee_data",
    description="Get detailed employee information using their employee ID",
    func=get_employee_data_tool
)