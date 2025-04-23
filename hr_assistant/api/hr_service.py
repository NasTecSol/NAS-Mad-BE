import requests
import json
from typing import Dict, Any, Optional
from config.settings import settings
from utils.logger import logger
import jwt # Import the PyJWT library
from api.endpoints import EndpointManager, EndpointType

class HRService:
    def __init__(self):
        self.endpoint_manager = EndpointManager(settings.HR_API_BASE_URL)
        self.tokens = {}  # Cache for tokens
        self.DB_IDS = {}  # Cache for DB ID'S against employee id's
        
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
                algorithms=["HS256"] # Specify the expected algorithm
            )
            logger.info("JWT decoded and verified successfully.")
            # Optional: Add more validation if needed (e.g., check 'iss' or 'aud' claims)
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("JWT verification failed: Token has expired.")
            raise # Re-raise the specific exception
        except jwt.InvalidSignatureError:
            logger.error("JWT verification failed: Invalid signature.")
            # This likely means the wrong secret key is being used or the token was tampered with.
            raise # Re-raise the specific exception
        except jwt.DecodeError as e:
            logger.error(f"JWT verification failed: Decode error - {e}")
            raise # Re-raise the specific exception
        except Exception as e:
            logger.error(f"An unexpected error occurred during JWT processing: {e}")
            raise ValueError(f"JWT processing error: {e}") from e
        
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
            logger.info(f"Attempting login for user: {payload}")
        
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
                token_data = self.decode_and_verify_token(token)
                # Store by username string
                username_key = payload.get("userName", username)
                self.tokens[username_key] = token  # Cache the token
                
                logger.info(f"Login successful for user: {username_key}")
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
        """Get token from cache or login to get a new one"""
        if employee_id in self.DB_IDS:
            return self.DB_IDS[employee_id]
            
        # Fix: Ensure we're passing a proper username string, not a dict
        emp_Data_result = self.get_employee_data(employee_id)
        if emp_Data_result["statusCode"] == 200:
            return emp_Data_result["data"].first()
        return None

    def get_token(self, employee_id: str) -> Optional[str]:
        """Get token from cache or login to get a new one"""
        if employee_id in self.tokens:
            return self.tokens[employee_id]
            
        # Fix: Ensure we're passing a proper username string, not a dict
        login_result = self.login(employee_id)
        if login_result["success"]:
            return login_result["token"]
        return None
    
    def get_employee_data(self, employee_id: str) -> Dict[str, Any]:
        """Get employee data using employee ID"""
        logger.info(f"Fetching employee data for: {employee_id}")
        
        # Get token
        token = self.get_token(employee_id)
        if not token:
            logger.error(f"Failed to get token for employee: {employee_id}")
            return {
                "success": False,
                "message": "Authentication failed"
            }
            
        # Get employee data
        url = self.endpoint_manager.get_full_url(
            EndpointType.EMPLOYEE_DATA, 
            employee_id=employee_id
        )
        
        logger.debug(f"Employee data request to: {url}")
        
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            employee_data = response.json()
            logger.info(f"Successfully retrieved ID for employee: {employee_id}")
             # Store by username string
            self.DB_IDS[employee_id] = employee_data  # Cache the token
            return {
                "success": True,
                "data": employee_data,
                "message": "Employee data retrieved successfully"
            }
        except Exception as e:
            logger.error(f"Error retrieving employee data: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to retrieve employee data: {str(e)}"
            }
    
    def get_attendance(self, employee_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
        """Get employee attendance records"""
        logger.info(f"Fetching attendance for employee: {employee_id}")
        
        # Get token
        token = self.get_token(employee_id)
        if not token:
            logger.error(f"Failed to get token for employee: {employee_id}")
            return {
                "success": False,
                "message": "Authentication failed"
            }
            
        # Get attendance data
        url = self.endpoint_manager.get_full_url(
            EndpointType.ATTENDANCE, 
            employee_id=employee_id
        )
        
        # Add query parameters if provided
        params = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
            
        logger.debug(f"Attendance request to: {url}")
        logger.debug(f"Attendance params: {json.dumps(params)}")
        
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            attendance_data = response.json()
            logger.info(f"Successfully retrieved attendance for employee: {employee_id}")
            
            return {
                "success": True,
                "data": attendance_data,
                "message": "Attendance data retrieved successfully"
            }
        except Exception as e:
            logger.error(f"Error retrieving attendance: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to retrieve attendance data: {str(e)}"
            }