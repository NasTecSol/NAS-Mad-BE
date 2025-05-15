from datetime import datetime, timedelta
from typing import Dict, Any
from utils.logger import logger
from api.hr_service import HRService

# Store last greeting times
employee_last_greeted = {}

# Store employee data cache
# Structure: {employee_id: {"data": employee_data, "last_fetched": timestamp}}
employee_data_cache = {}

# Employee data cache expiration time (24 hours)
EMPLOYEE_DATA_CACHE_EXPIRY = timedelta(hours=24)

# Initialize HR service
hr_service = None


def initialize():
    """Initialize the HR service if not already done"""
    global hr_service
    if hr_service is None:
        hr_service = HRService()
    return hr_service


def get_greeting() -> str:
    """Generate appropriate greeting based on current time of day."""
    current_hour = datetime.now().hour

    if 5 <= current_hour < 12:
        return "Good morning"
    elif 12 <= current_hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"


def should_greet_employee(employee_id: str) -> bool:
    """Check if employee should be greeted based on last greeting time."""
    today = datetime.now().date()

    # If employee hasn't been greeted before or was last greeted on a different day
    if employee_id not in employee_last_greeted:
        return True

    last_greeted_date = employee_last_greeted[employee_id].date()
    return last_greeted_date != today


def update_employee_greeting_time(employee_id: str):
    """Update the last time the employee was greeted."""
    employee_last_greeted[employee_id] = datetime.now()


def get_employee_data(employee_id: str) -> Dict[str, Any]:
    """
    Get employee data from cache or fetch from service if needed.
    Returns the employee data dictionary.
    """
    # Make sure HR service is initialized
    service = initialize()

    current_time = datetime.now()

    # Check if we have cached data that's still valid
    if (
        employee_id in employee_data_cache
        and employee_data_cache[employee_id]["data"]
        and current_time - employee_data_cache[employee_id]["last_fetched"] < EMPLOYEE_DATA_CACHE_EXPIRY
    ):
        logger.info(f"Using cached employee data for employee {employee_id}")
        return employee_data_cache[employee_id]["data"]

    # If not in cache or expired, fetch from HR service
    try:
        logger.info(f"Fetching fresh employee data for employee {employee_id}")
        employee_data_result = service.get_employee_data(employee_id)

        if not employee_data_result["success"]:
            logger.error(
                f"Failed to get employee data: {employee_data_result['message']}")
            # Return empty dict or cached data if available
            return employee_data_cache.get(employee_id, {}).get("data", {}) or {}

        # Cache the fresh data
        employee_data = employee_data_result["data"]
        employee_data_cache[employee_id] = {
            "data": employee_data,
            "last_fetched": current_time
        }

        return employee_data
    except Exception as e:
        logger.error(f"Error retrieving employee data: {str(e)}")
        # Return cached data if available, otherwise empty dict
        return employee_data_cache.get(employee_id, {}).get("data", {}) or {}


def clear_employee_cache(employee_id: str):
    """Clear cached data for a specific employee"""
    if employee_id in employee_data_cache:
        del employee_data_cache[employee_id]
        return {"status": "success", "message": f"Cache cleared for employee {employee_id}"}

    return {"status": "not_found", "message": f"No cached data found for employee {employee_id}"}


def get_cache_stats():
    """Get statistics about the cache"""
    return {
        "cached_employees": len(employee_data_cache),
        "active_threads": 0,  # This would need to be updated from assistant_utils
        "greeted_today": len(employee_last_greeted)
    }
