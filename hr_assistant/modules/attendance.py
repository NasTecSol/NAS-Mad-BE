from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from langchain.tools import Tool
from utils.logger import logger

# Global service reference
hr_service = None

def initialize(service):
    global hr_service
    hr_service = service

def get_attendance_tool(employee_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Get employee attendance records.
    
    Args:
        employee_id: Employee ID (e.g., EMP103)
        start_date: Start date for attendance records (optional, format: YYYY-MM-DD)
        end_date: End date for attendance records (optional, format: YYYY-MM-DD)
    
    Returns:
        Dictionary containing attendance records
    """
    logger.info(f"Get attendance tool called for employee: {employee_id}")
    
    # Validate input
    if not employee_id:
        logger.error("Employee ID is missing or empty")
        return {
            "success": False,
            "message": "Employee ID is required"
        }
        
    # Call the HR service
    return hr_service.get_attendance(employee_id, start_date, end_date)

def get_recent_attendance_tool(employee_id: str, days: int = 7) -> Dict[str, Any]:
    """
    Get employee's recent attendance for the specified number of days.
    
    Args:
        employee_id: Employee ID (e.g., EMP103)
        days: Number of recent days to fetch (default: 7)
    
    Returns:
        Dictionary containing recent attendance records
    """
    logger.info(f"Get recent attendance tool called for employee: {employee_id}, days: {days}")
    
    # Validate input
    if not employee_id:
        logger.error("Employee ID is missing or empty")
        return {
            "success": False,
            "message": "Employee ID is required"
        }
    
    # Calculate dates
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Call the HR service
    return hr_service.get_attendance(employee_id, start_date, end_date)

# Create the LangChain tools
get_attendance = Tool(
    name="get_attendance",
    description="Get employee attendance records for a specific date range",
    func=get_attendance_tool
)

get_recent_attendance = Tool(
    name="get_recent_attendance",
    description="Get employee's recent attendance for the specified number of days",
    func=get_recent_attendance_tool
)