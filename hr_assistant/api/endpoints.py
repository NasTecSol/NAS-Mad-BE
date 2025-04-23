from enum import Enum
from dataclasses import dataclass

class EndpointType(Enum):
    LOGIN = "login"
    EMPLOYEE_DATA = "employee_data"
    ATTENDANCE = "attendance"
    LEAVE = "leave"
    PAYROLL = "payroll"

@dataclass
class Endpoint:
    type: EndpointType
    path: str
    method: str
    requires_auth: bool = False
    description: str = ""

class EndpointManager:
    def __init__(self, base_url):
        self.base_url = base_url
        self.endpoints = self._register_endpoints()
    
    def _register_endpoints(self):
        return {
            EndpointType.LOGIN: Endpoint(
                type=EndpointType.LOGIN,
                path="/employee/login",
                method="POST",
                requires_auth=False,
                description="Authenticate employee and get access token"
            ),
            EndpointType.EMPLOYEE_DATA: Endpoint(
                type=EndpointType.EMPLOYEE_DATA,
                path="/employee/getDataByEMPId/{employee_id}",
                method="GET",
                requires_auth=True,
                description="Get employee data using employee ID"
            ),
            EndpointType.ATTENDANCE: Endpoint(
                type=EndpointType.ATTENDANCE,
                path="/c-emp-attendance/getDataByEmployeeId/{employee_id}/{start_date}/{end_date}?page=0&limit=13",
                method="GET",
                requires_auth=True,
                description="Get employee attendance records"
            )
            # Add more endpoints as needed
        }
    
    def get_full_url(self, endpoint_type, **kwargs):
        """Get the full URL for an endpoint with path parameters replaced"""
        endpoint = self.endpoints.get(endpoint_type)
        if not endpoint:
            raise ValueError(f"Unknown endpoint type: {endpoint_type}")
            
        # Replace path parameters with provided values
        path = endpoint.path
        for key, value in kwargs.items():
            path = path.replace(f"{{{key}}}", str(value))
            
        return f"{self.base_url}{path}"