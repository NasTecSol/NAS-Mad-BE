import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from config.settings import settings
from utils.logger import logger
import jwt  # Import the PyJWT library
from api.endpoints import EndpointManager, EndpointType

# Global cache for HR service data
class GlobalHRCache:
    """Global cache for HR service data shared across instances"""
    
    # Singleton pattern
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GlobalHRCache, cls).__new__(cls)
            # Initialize cache stores
            cls._instance.tokens = {}  # Cache for tokens {employee_id: {"token": token_string, "expires_at": timestamp}}
            cls._instance.employee_data = {}  # Cache for employee data {employee_id: {"data": data_dict, "last_fetched": timestamp}}
            cls._instance.db_ids = {}  # Cache for DB IDs {employee_id: db_id}
            cls._instance.team_data = {}  # Cache for team data {manager_id: {"data": team_data, "employee_ids": [ids], "last_fetched": timestamp}}
            cls._instance.attendance_data = {}  # Cache for attendance data {employee_id+date_range: {"data": data, "last_fetched": timestamp}}
            
            # Cache expiration settings
            cls._instance.TOKEN_EXPIRY = timedelta(hours=8)  # Tokens typically expire after 8-12 hours
            cls._instance.EMPLOYEE_DATA_EXPIRY = timedelta(hours=24)  # Employee data refreshed daily
            cls._instance.TEAM_DATA_EXPIRY = timedelta(hours=12)  # Team data refreshed twice daily
            cls._instance.ATTENDANCE_DATA_EXPIRY = timedelta(minutes=30)  # Attendance data refreshed more frequently
        
        return cls._instance
    
    def get_token(self, employee_id: str) -> Optional[str]:
        """Get token from cache if valid"""
        now = datetime.now()
        
        if (employee_id in self.tokens and 
            self.tokens[employee_id].get("token") and
            self.tokens[employee_id].get("expires_at", now) > now):
            logger.debug(f"Using cached token for employee {employee_id}")
            return self.tokens[employee_id]["token"]
        return None
    
    def set_token(self, employee_id: str, token: str) -> None:
        """Set token in cache with expiration time"""
        now = datetime.now()
        self.tokens[employee_id] = {
            "token": token,
            "expires_at": now + self.TOKEN_EXPIRY
        }
        logger.debug(f"Token cached for employee {employee_id}, expires at {now + self.TOKEN_EXPIRY}")
    
    def get_employee_data(self, employee_id: str) -> Optional[Dict]:
        """Get employee data from cache if valid"""
        now = datetime.now()
        
        if (employee_id in self.employee_data and 
            self.employee_data[employee_id].get("data") and
            self.employee_data[employee_id].get("last_fetched", now - timedelta(days=2)) + self.EMPLOYEE_DATA_EXPIRY > now):
            logger.debug(f"Using cached employee data for {employee_id}")
            return self.employee_data[employee_id]["data"]
        return None
    
    def set_employee_data(self, employee_id: str, data: Dict) -> None:
        """Set employee data in cache"""
        self.employee_data[employee_id] = {
            "data": data,
            "last_fetched": datetime.now()
        }
        logger.debug(f"Employee data cached for {employee_id}")
    
    def get_db_id(self, employee_id: str) -> Optional[str]:
        """Get database ID from cache"""
        if employee_id in self.db_ids:
            return self.db_ids[employee_id]
        return None
    
    def set_db_id(self, employee_id: str, db_id: str) -> None:
        """Set database ID in cache"""
        self.db_ids[employee_id] = db_id
        logger.debug(f"DB ID cached for employee {employee_id}: {db_id}")
    
    def get_team_data(self, manager_id: str) -> Optional[Dict]:
        """Get team data from cache if valid"""
        now = datetime.now()
        
        if (manager_id in self.team_data and 
            self.team_data[manager_id].get("data") and
            self.team_data[manager_id].get("last_fetched", now - timedelta(days=2)) + self.TEAM_DATA_EXPIRY > now):
            logger.debug(f"Using cached team data for manager {manager_id}")
            return {
                "data": self.team_data[manager_id]["data"],
                "employee_ids": self.team_data[manager_id]["employee_ids"]
            }
        return None
    
    def set_team_data(self, manager_id: str, team_data: Dict) -> None:
        """Set team data in cache"""
        self.team_data[manager_id] = {
            "data": team_data,
            "last_fetched": datetime.now()
        }
        logger.debug(f"Team data cached for manager {manager_id} with {len(team_data)} team members")
    
    def get_attendance_key(self, employee_id: str, start_date: str, end_date: str) -> str:
        """Generate a unique key for attendance data cache"""
        return f"{employee_id}_{start_date}_{end_date}"
    
    def get_attendance_data(self, employee_id: str, start_date: str, end_date: str) -> Optional[Dict]:
        """Get attendance data from cache if valid"""
        key = self.get_attendance_key(employee_id, start_date, end_date)
        now = datetime.now()
        
        if (key in self.attendance_data and 
            self.attendance_data[key].get("data") and
            self.attendance_data[key].get("last_fetched", now - timedelta(days=2)) + self.ATTENDANCE_DATA_EXPIRY > now):
            logger.debug(f"Using cached attendance data for {key}")
            return self.attendance_data[key]["data"]
        return None
    
    def set_attendance_data(self, employee_id: str, start_date: str, end_date: str, data: Dict) -> None:
        """Set attendance data in cache"""
        key = self.get_attendance_key(employee_id, start_date, end_date)
        self.attendance_data[key] = {
            "data": data,
            "last_fetched": datetime.now()
        }
        logger.debug(f"Attendance data cached for {key}")
    
    def clear_employee_cache(self, employee_id: str) -> None:
        """Clear all cached data for an employee"""
        if employee_id in self.tokens:
            del self.tokens[employee_id]
        
        if employee_id in self.employee_data:
            del self.employee_data[employee_id]
        
        if employee_id in self.db_ids:
            del self.db_ids[employee_id]
        
        if employee_id in self.team_data:
            del self.team_data[employee_id]
        
        # Clear attendance data with this employee ID
        keys_to_delete = []
        for key in self.attendance_data:
            if key.startswith(f"{employee_id}_"):
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            del self.attendance_data[key]
        
        logger.info(f"Cleared all cached data for employee {employee_id}")
    
    def get_cache_stats(self) -> Dict:
        """Get statistics about the cache"""
        return {
            "tokens": len(self.tokens),
            "employee_data": len(self.employee_data),
            "db_ids": len(self.db_ids),
            "team_data": len(self.team_data),
            "attendance_data": len(self.attendance_data)
        }

class HRService:
    def __init__(self):
        self.endpoint_manager = EndpointManager(settings.HR_API_BASE_URL)
        # Initialize the global cache
        self.cache = GlobalHRCache()
        
    def decode_and_verify_token(self, token_string: str) -> Dict[str, Any]:
        """
        Decodes and verifies the JWT token using the shared secret key.
        Also checks standard claims like expiration ('exp').

        Args:
            token_string: The JWT received from the API.

        Returns:
            The decoded token payload as a dictionary if verification succeeds.

        Raises:
            jwt.ExpiredSignatureError: If the token is expired.
            jwt.InvalidSignatureError: If the signature doesn't match.
            jwt.DecodeError: For other JWT decoding/format issues.
            ValueError: If the secret key is not configured.
        """
        secret_key = getattr(settings, 'JWT_SECRET_KEY', None)
        if not secret_key:
            logger.error("JWT Secret Key is not configured in settings!")
            raise ValueError("JWT Secret Key is not configured.")
            
        if not secret_key:
            logger.warning("Using a placeholder or missing JWT Secret Key. Verification will fail or is insecure.")
            # Depending on security needs, you might want to raise ValueError here too.

        try:
            # Decode the token. This automatically verifies:
            # 1. Signature (using the secret_key)
            # 2. Expiration ('exp' claim)
            # 3. Algorithm ('alg' claim matches)
            payload = jwt.decode(
                token_string,
                secret_key,
                algorithms=["HS256"]  # Specify the expected algorithm
            )
            logger.info("JWT decoded and verified successfully.")
            # Optional: Add more validation if needed (e.g., check 'iss' or 'aud' claims)
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("JWT verification failed: Token has expired.")
            raise  # Re-raise the specific exception
        except jwt.InvalidSignatureError:
            logger.error("JWT verification failed: Invalid signature.")
            # This likely means the wrong secret key is being used or the token was tampered with.
            raise  # Re-raise the specific exception
        except jwt.DecodeError as e:
            logger.error(f"JWT verification failed: Decode error - {e}")
            raise  # Re-raise the specific exception
        except Exception as e:
            logger.error(f"An unexpected error occurred during JWT processing: {e}")
            raise ValueError(f"JWT processing error: {e}") from e
        
    def calculate_date_range(self, date_type: str) -> tuple:
        """
        Calculate start and end dates based on date_type
        
        Args:
            date_type: One of 'today', 'recent', 'this_month', or a specific date 'YYYY-MM-DD'
            
        Returns:
            Tuple of (end_date, start_date) formatted as 'YYYY-MM-DD'
        """
        today = datetime.now().date()
        end_date = today.strftime("%Y-%m-%d")
        
        if date_type == "today":
            start_date = end_date
        elif date_type == "yesterday":
            # Last 7 days
            start_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
            end_date = start_date
        elif date_type == "recent":
            # Last 7 days
            start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        elif date_type == "this_month":
            # First day of current month
            start_date = today.replace(day=1).strftime("%Y-%m-%d")
        elif date_type.count("-") == 2:  # Looks like a date 'YYYY-MM-DD'
            # Specific date
            start_date = date_type
            end_date = date_type
        else:
            # Default to recent
            start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
            
        return start_date,end_date
        
    def login(self, username: str, password: Optional[str] = None, mac_address: Optional[str] = None) -> Dict[str, Any]:
        """Login to HR system and get access token"""
        login_url = self.endpoint_manager.get_full_url(EndpointType.LOGIN)
        
        # Use defaults if not provided
        password = password or settings.DEFAULT_PASSWORD
        mac_address = mac_address or settings.DEFAULT_MAC_ADDRESS
        
        # Fix: Make sure username is a string, not a dict
        if isinstance(username, dict):
            # If it's already a complete payload, use it directly
            payload = username
            username_str = payload.get("userName", "unknown")
            logger.info(f"Attempting login for user: {payload}")
        else:
            # Otherwise create the payload
            payload = {
                "empId": username,
                "password": password,
                "macAddress": mac_address
            }
            username_str = username
            logger.info(f"Attempting login for user: {username_str}")
        
        logger.debug(f"Login request to: {login_url}")
        logger.debug(f"Login payload: {json.dumps(payload)}")
        
        try:
            response = requests.post(login_url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            logger.debug(f"Login response received")
            
            if "data" in result and "token" in result["data"]:
                # Extract token from response
                token = result["data"]["token"]
                
                # Cache the token
                self.cache.set_token(username_str, token)
                
                logger.info(f"Login successful for user: {username_str}")
                return {
                    "success": True,
                    "token": token,
                    "message": "Login successful!"
                }
            else:
                logger.warning(f"Login failed: Invalid response format")
                logger.debug(f"Response content: {json.dumps(result)}")
                return {
                    "success": False,
                    "message": "Login failed: Invalid response format"
                }
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return {
                "success": False,
                "message": f"Login failed: {str(e)}"
            }
            
    def get_DB_ID(self, employee_id: str) -> Optional[str]:
        """Get database ID from cache or extract from employee data"""
        # Check if it's in cache
        db_id = self.cache.get_db_id(employee_id)
        if db_id:
            return db_id
            
        # If not in cache, try to get it from employee data
        emp_data_result = self.get_employee_data(employee_id)
        if emp_data_result["success"] and "data" in emp_data_result:
            employee_data = emp_data_result["data"]
            if "_id" in employee_data:
                db_id = employee_data["_id"]
                # Cache it for future use
                self.cache.set_db_id(employee_id, db_id)
                return db_id
                
        logger.warning(f"Could not find database ID for employee {employee_id}")
        return None

    def get_token(self, employee_id: str) -> Optional[str]:
        """Get token from cache or login to get a new one"""
        # Try to get from cache first
        token = self.cache.get_token(employee_id)
        if token:
            return token
            
        # Otherwise, login to get a new token
        login_result = self.login(employee_id)
        if login_result["success"]:
            return login_result["token"]
            
        logger.error(f"Failed to get token for employee {employee_id}")
        return None
    
    def get_employee_data(self, employee_id: str) -> Dict[str, Any]:
        """Get employee data using employee ID"""
        logger.info(f"Requesting employee data for: {employee_id}")
        
        # Try to get from cache first
        cached_data = self.cache.get_employee_data(employee_id)
        if cached_data:
            logger.info(f"Using cached employee data for: {employee_id}")
            return {
                "success": True,
                "data": cached_data,
                "message": "Employee data retrieved from cache",
                "cached": True
            }
            
        # Not in cache, get token
        token = self.get_token(employee_id)
        if not token:
            logger.error(f"Failed to get token for employee: {employee_id}")
            return {
                "success": False,
                "message": "Authentication failed"
            }
            
        # Get employee data from API
        url = self.endpoint_manager.get_full_url(
            EndpointType.EMPLOYEE_DATA, 
            employee_id=employee_id
        )
        
        logger.debug(f"Employee data request to: {url}")
        
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("statusCode") == 200 and "data" in result:
                employee_data = result["data"][0]
                logger.info(f"Retrieved employee data: {employee_data}")
                logger.info(f"Successfully retrieved data for employee: {employee_id}")
                
                # Cache the employee data
                self.cache.set_employee_data(employee_id, employee_data)
                # If data contains database ID, cache it separately for quick access
                if "_id" in employee_data:
                    self.cache.set_db_id(employee_id, employee_data["_id"])
                
                return {
                    "success": True,
                    "data": employee_data,
                    "message": "Employee data retrieved successfully",
                    "cached": False
                }
            else:
                logger.warning(f"Invalid employee data response: {json.dumps(result)}")
                return {
                    "success": False,
                    "message": "Failed to retrieve employee data: Invalid response format"
                }
        except Exception as e:
            logger.error(f"Error retrieving employee data: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to retrieve employee data: {str(e)}"
            }
    
    def get_personal_attendance(self, employee_id: str, date_type: str = "recent") -> Dict[str, Any]:
        """
        Get attendance records for a single employee
        
        Args:
            employee_id: Employee ID
            date_type: One of 'today', 'recent', 'this_month', or a specific date 'YYYY-MM-DD'
            
        Returns:
            summarised attendance data by employees and sorted by dates
        """
        logger.info(f"Fetching personal attendance for employee: {employee_id} (date_type: {date_type})")
        
        # Calculate date range
        end_date, start_date = self.calculate_date_range(date_type)
        
        # Check cache first
        # # cached_attendance = self.cache.get_attendance_data(employee_id, start_date, end_date)
        # if cached_attendance:
        #     logger.info(f"Using cached attendance data for employee {employee_id}")
        #     return {
        #         "success": True,
        #         "data": cached_attendance,
        #         "date_range": {
        #             "start_date": start_date,
        #             "end_date": end_date
        #         },
        #         "message": "Attendance data retrieved from cache",
        #         "cached": True
        #     }
        
        # Get token
        token = self.get_token(employee_id)
        if not token:
            logger.error(f"Failed to get token for employee: {employee_id}")
            return {
                "success": False,
                "message": "Authentication failed"
            }
        
        # Get employee DB ID
        employee_db_id = self.get_DB_ID(employee_id)
        if not employee_db_id:
            logger.error(f"Missing employee database ID for {employee_id}")
            return {
                "success": False,
                "message": "Missing employee database ID"
            }
        
        # Construct the attendance URL
        attendance_url = f"{settings.HR_API_BASE_URL}/c-emp-attendance/getDataByEmployeeId/{employee_db_id}/{start_date}/{end_date}?page=0&limit=50"
        
        logger.debug(f"Personal attendance request to: {attendance_url}")
        logger.info(f"Personal attendance request to: {attendance_url}")
        
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(attendance_url, headers=headers)
            response.raise_for_status()
            
            attendance_data = response.json()
            logger.info(f"Successfully retrieved attendance data for employee: {attendance_data}")
            
            if attendance_data.get("statusCode") == 200 and "data" in attendance_data:
                # Cache the attendance data
                self.cache.set_attendance_data(employee_id, start_date, end_date, attendance_data["data"])
                
                return {
                    "success": True,
                    "data": attendance_data["data"],
                    "date_range": {
                        "start_date": start_date,
                        "end_date": end_date
                    },
                    "message": "Attendance data retrieved successfully",
                    "cached": False
                }
            else:
                logger.warning(f"Attendance data response not in expected format: {json.dumps(attendance_data)}")
                return {
                    "success": False,
                    "message": "Failed to retrieve attendance data: Invalid response format"
                }
        except Exception as e:
            logger.error(f"Error retrieving attendance data: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to retrieve attendance data: {str(e)}"
            }
    
    def get_team_data(self, employee_id: str) -> Dict[str, Any]:
        """
        Get team data for a manager
        
        Args:
            employee_id: Employee ID of the manager
            
        Returns:
            Dictionary containing team data and list of employee IDs
        """
        logger.info(f"Fetching team data for manager: {employee_id}")
        
        # Check cache first
        # cached_team_data = self.cache.get_team_data(employee_id)
        # if cached_team_data:
        #     logger.info(f"Using cached team data for manager {employee_id}")
        #     return {
        #         "success": True,
        #         "data": cached_team_data["data"],
        #         "employee_ids": cached_team_data["employee_ids"],
        #         "message": "Team data retrieved from cache",
        #         "cached": True
        #     }
        
        # Get token
        token = self.get_token(employee_id)
        if not token:
            logger.error(f"Failed to get token for employee: {employee_id}")
            return {
                "success": False,
                "message": "Authentication failed"
            }
        
        # Get employee's DB ID first
        cached_data = self.cache.get_employee_data(employee_id)
        employee_db_id = self.get_DB_ID(employee_id)
        employee_branch_id = cached_data.get("branchId")
        employee_department = cached_data.get("departmentId")
        logger.info(f"cache data for manager {cached_data}")
        if not employee_db_id:
            logger.error(f"Missing database ID for manager {employee_id}")
            return {
                "success": False,
                "message": "Missing manager database ID"
            }
        
        # Construct the team data URL
        # Placeholder - adjust this URL according to your API
        team_url = f"{settings.HR_API_BASE_URL}/branches/getTeamData/{employee_branch_id}/{employee_department}/{employee_db_id}"
        logger.info(f"Team data request to: {team_url}")
        logger.debug(f"Team data request to: {team_url}")
        
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(team_url, headers=headers)
            response.raise_for_status()
            
            team_data = response.json()
            
            if team_data.get("statusCode") == 200 and "data" in team_data:
                # Extract employee IDs from team data
                employee_ids = []
                
                team_members = team_data["data"]
                for employee in team_members["teamData"]:
                    if "employeeId" in employee:
                        employee_ids.append(employee["employeeId"])
                
                # Cache team data
                self.cache.set_team_data(employee_id, team_members)
                
                logger.info(f"Successfully retrieved team data for manager {employee_id} with {len(employee_ids)} team members")
                return {
                    "success": True,
                    "data": team_members,
                    "employee_ids": employee_ids,
                    "message": "Team data retrieved successfully",
                    "cached": False
                }
            else:
                logger.warning(f"Team data response not in expected format: {json.dumps(team_data)}")
                return {
                    "success": False,
                    "message": "Failed to retrieve team data: Invalid response format"
                }
        except Exception as e:
            logger.error(f"Error retrieving team data: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to retrieve team data: {str(e)}"
            }
    
    def get_team_attendance(self, employee_id: str, date_type: str = "recent") -> Dict[str, Any]:
        """
        Get attendance records for a manager's team
        
        Args:
            employee_id: Employee ID of the manager
            date_type: One of 'today', 'recent', 'this_month', or a specific date 'YYYY-MM-DD'
            
        Returns:
            summarised attendance data by employees and sorted by dates
        """
        logger.info(f"Fetching team attendance for manager: {employee_id} (date_type: {date_type})")
        
        # Calculate date range
        end_date, start_date = self.calculate_date_range(date_type)
        
        # Generate a composite key for team attendance
        team_cache_key = f"team_{employee_id}"
        
        # Check cache first
        cached_attendance = self.cache.get_attendance_data(team_cache_key, start_date, end_date)
        if cached_attendance:
            logger.info(f"Using cached team attendance data for manager {employee_id}")
            
            # Get team data to include in response
            team_data_result = self.get_team_data(employee_id)
            team_data = team_data_result.get("data", []) if team_data_result["success"] else []
            
            return {
                "success": True,
                "data": cached_attendance,
                "team_data": team_data,
                "date_range": {
                    "start_date": start_date,
                    "end_date": end_date
                },
                "message": "Team attendance data retrieved from cache",
                "cached": True
            }
        
        # Get token
        token = self.get_token(employee_id)
        if not token:
            logger.error(f"Failed to get token for employee: {employee_id}")
            return {
                "success": False,
                "message": "Authentication failed"
            }
        
        # Get team data first
        team_data_result = self.get_team_data(employee_id)
        if not team_data_result["success"]:
            return team_data_result
        
        team_data = team_data_result["data"]
        employee_ids = team_data_result["employee_ids"]
        
        if not employee_ids:
            logger.warning(f"No team members found for employee: {employee_id}")
            return {
                "success": False,
                "message": "No team members found"
            }
        
        # Join employee IDs with commas
        employee_id_list = ",".join(employee_ids)
        
        # Construct the team attendance URL
        attendance_url = f"{settings.HR_API_BASE_URL}/c-emp-attendance/getDataByEmployeeId/{employee_id_list}/{start_date}/{end_date}?page=0&limit=50"
        logger.info(f"Team attendance request to: {attendance_url}")
        logger.debug(f"Team attendance request to: {attendance_url}")
        
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(attendance_url, headers=headers)
            response.raise_for_status()
            
            attendance_data = response.json()
            logger.info(f"Successfully retrieved team attendance data for manager: {employee_id}")
            
            if attendance_data.get("statusCode") == 200 and "data" in attendance_data:
                # Cache the team attendance data
                self.cache.set_attendance_data(team_cache_key, start_date, end_date, attendance_data["data"])
                
                return {
                    "success": True,
                    "data": attendance_data["data"],
                    "team_data": team_data,
                    "date_range": {
                        "start_date": start_date,
                        "end_date": end_date
                    },
                    "message": "Team attendance data retrieved successfully",
                    "cached": False
                }
            else:
                logger.warning(f"Team attendance data response not in expected format: {json.dumps(attendance_data)}")
                return {
                    "success": False,
                    "message": "Failed to retrieve team attendance data: Invalid response format"
                }
        except Exception as e:
            logger.error(f"Error retrieving team attendance data: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to retrieve team attendance data: {str(e)}"
            }
    
    def get_attendance(self, employee_id: str, date_type: str = "recent", include_team: bool = None) -> Dict[str, Any]:
        """
        Get attendance data based on employee grade and request
        
        Args:
            employee_id: Employee ID
            date_type: One of 'today', 'recent', 'this_month', or a specific date 'YYYY-MM-DD'
            include_team: Override to include team data (None = auto-detect based on grade)
            
        Returns:
           summarised attendance data by employees and sorted by dates
        """
        logger.info(f"Processing attendance request for employee: {employee_id} (date_type: {date_type}, include_team: {include_team})")
        
        # Get employee data to determine grade
        employee_data_result = self.get_employee_data(employee_id)
        if not employee_data_result["success"]:
            return employee_data_result
        
        employee_data = employee_data_result["data"]
        
        # Determine if employee is a manager based on grade
        try:
            grade = employee_data.get("grade", "L4")  # Default to L4 if not found
            is_manager = grade in ["L0", "L1", "L2", "L3", "L4"]
            
            # Override with include_team parameter if provided
            if include_team is not None:
                is_manager = include_team
                
            logger.info(f"Employee {employee_id} has grade {grade}, is_manager: {is_manager}")
        except Exception as e:
            logger.error(f"Error determining employee grade: {str(e)}")
            return {
                "success": False,
                "message": "Failed to determine employee role"
            }
        
        # Get appropriate attendance data
        if is_manager:
            return self.get_team_attendance(employee_id, date_type)
        else:
            return self.get_personal_attendance(employee_id, date_type)
            
    def clear_employee_cache(self, employee_id: str) -> Dict[str, Any]:
        """
        Clear all cached data for an employee
        
        Args:
            employee_id: Employee ID to clear from cache
            
        Returns:
            Dictionary with operation status
        """
        try:
            self.cache.clear_employee_cache(employee_id)
            return {
                "success": True,
                "message": f"Cache cleared for employee {employee_id}"
            }
        except Exception as e:
            logger.error(f"Error clearing cache for employee {employee_id}: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to clear cache: {str(e)}"
            }
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the cache
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            stats = self.cache.get_cache_stats()
            return {
                "success": True,
                "stats": stats,
                "message": "Cache statistics retrieved successfully"
            }
        except Exception as e:
            logger.error(f"Error retrieving cache statistics: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to retrieve cache statistics: {str(e)}"
            }