from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from langchain.tools import Tool
from utils.logger import logger

# Global service reference
hr_service = None

def initialize(service):
    global hr_service
    hr_service = service

def get_personal_attendance_tool(employee_id: str, date_type: str = "recent") -> Dict[str, Any]:
    """
    Get attendance records for a specific employee.
    
    Args:
        employee_id: Employee ID (e.g., EMP103)
        date_type: Type of date range - 'today', 'recent', 'this_month', 
                   a specific date 'YYYY-MM-DD', or month_MM_YYYY for a specific month
    
    Returns:
        Dictionary containing attendance records
    """
    logger.info(f"Get personal attendance tool called for employee: {employee_id}, date_type: {date_type}")
    
    # Validate input
    if not employee_id:
        logger.error("Employee ID is missing or empty")
        return {
            "success": False,
            "message": "Employee ID is required"
        }
    
    # Call the HR service
    return hr_service.get_personal_attendance(employee_id, date_type)

def get_team_attendance_tool(employee_id: str, date_type: str = "recent") -> Dict[str, Any]:
    """
    Get attendance records for a manager's team.
    
    Args:
        employee_id: Employee ID of the manager (e.g., EMP103)
        date_type: Type of date range - 'today', 'recent', 'this_month', 
                   a specific date 'YYYY-MM-DD', or month_MM_YYYY for a specific month
    
    Returns:
        Dictionary containing team attendance records
    """
    logger.info(f"Get team attendance tool called for manager: {employee_id}, date_type: {date_type}")
    
    # Validate input
    if not employee_id:
        logger.error("Employee ID is missing or empty")
        return {
            "success": False,
            "message": "Employee ID is required"
        }
    
    # Call the HR service
    return hr_service.get_team_attendance(employee_id, date_type)

def get_attendance_tool(employee_id: str, date_type: str = "recent", include_team: bool = None) -> Dict[str, Any]:
    """
    Get attendance records based on employee grade and date range.
    The function automatically determines if the employee is a manager (L0-L3) 
    and returns team attendance if appropriate.
    
    Args:
        employee_id: Employee ID (e.g., EMP103)
        date_type: Type of date range - 'today', 'recent', 'this_month', 
                   a specific date 'YYYY-MM-DD', or month_MM_YYYY for a specific month
        include_team: Override to include team data (None = auto-detect based on grade)
    
    Returns:
        Dictionary containing attendance records
    """
    logger.info(f"Get attendance tool called for employee: {employee_id}, date_type: {date_type}, include_team: {include_team}")
    
    # Validate input
    if not employee_id:
        logger.error("Employee ID is missing or empty")
        return {
            "success": False,
            "message": "Employee ID is required"
        }
    
    # Call the HR service
    return hr_service.get_attendance(employee_id, date_type, include_team)

def get_attendance_report_tool(employee_id: str, date_type: str = "today", 
                              company_id: str = None, branch_id: str = None, 
                              department_id: str = None, report_type: str = "all") -> Dict[str, Any]:
    """
    Get comprehensive attendance report for all employees, categorized by company, branch, and department.
    This tool is only available to high-level managers (L0-L1) with specific roles (HR Manager, admin, owner).
    
    Args:
        employee_id: Employee ID of the requester (e.g., EMP103)
        date_type: Type of date range - 'today', 'yesterday', 'recent' (1 week), 'this_month', 
                   'previous_month', or a specific date 'YYYY-MM-DD' or date range 'YYYY-MM-DD:YYYY-MM-DD'
        company_id: Optional filter for specific company (can be ID or name)
        branch_id: Optional filter for specific branch (can be ID or name)
        department_id: Optional filter for specific department
        report_type: Type of report - 'all', 'present', 'absent', 'late'
    
    Returns:
        Dictionary containing attendance report data organized by company/branch/department
    """
    logger.info(f"Get attendance report tool called by employee: {employee_id}, date_type: {date_type}, report_type: {report_type}")
    logger.info(f"Filters - Company: {company_id}, Branch: {branch_id}, Department: {department_id}")
    
    # Validate input
    if not employee_id:
        logger.error("Employee ID is missing or empty")
        return {
            "success": False,
            "message": "Employee ID is required"
        }
    
    # Call the HR service
    return hr_service.get_attendance_report(
        employee_id, 
        date_type, 
        company_id, 
        branch_id, 
        department_id,
        report_type
    )

# Create the LangChain tools
get_personal_attendance = Tool(
    name="get_personal_attendance",
    description="Get attendance records for a specific employee",
    func=get_personal_attendance_tool
)

get_team_attendance = Tool(
    name="get_team_attendance",
    description="Get attendance records for a manager's team",
    func=get_team_attendance_tool
)

get_attendance = Tool(
    name="get_attendance",
    description="Get attendance records based on employee grade and date range",
    func=get_attendance_tool
)

get_attendance_report = Tool(
    name="get_attendance_report",
    description="""Get comprehensive attendance report for all companies/branches/departments.
    Can filter by specific company name or ID, branch name or ID, or department.
    Can generate specific report types like 'present', 'absent', or 'late' employees.
    Only available to L0-L1 managers with HR Manager/admin/owner roles.""",
    func=get_attendance_report_tool
)