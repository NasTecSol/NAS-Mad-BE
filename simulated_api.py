# from fastapi import APIRouter, Request, HTTPException
# from pydantic import BaseModel
# from typing import Dict, Any, Optional
# from datetime import datetime, timedelta
# import random
# import uuid

# # Create a router for simulated API
# mock_api_router = APIRouter(prefix="/api")

# # Simulated database
# EMPLOYEE_DATA = {
#     "EMP103": {
#         "id": "EMP103",
#         "firstName": "John",
#         "lastName": "Doe",
#         "email": "john.doe@company.com",
#         "department": "Engineering",
#         "position": "Software Developer",
#         "joiningDate": "2020-01-15",
#         "manager": "EMP101",
#         "salary": 85000,
#         "leaveBalance": {
#             "annual": 15,
#             "sick": 10,
#             "casual": 5
#         },
#         "contactInfo": {
#             "phone": "+1-555-123-4567",
#             "address": "123 Main St, Anytown, USA"
#         },
#         "skills": ["Python", "JavaScript", "React", "Docker"]
#     }
# }

# # Simulated attendance data
# def generate_attendance(employee_id, start_date_str, end_date_str=None):
#     if not end_date_str:
#         end_date_str = datetime.now().strftime("%Y-%m-%d")
    
#     start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
#     end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    
#     attendance = []
#     current_date = start_date
    
#     while current_date <= end_date:
#         # Skip weekends
#         if current_date.weekday() < 5:  # 0-4 are Monday to Friday
#             # 90% chance of being present
#             is_present = random.random() < 0.9
            
#             entry = {
#                 "date": current_date.strftime("%Y-%m-%d"),
#                 "status": "Present" if is_present else "Absent",
#                 "checkIn": "09:00" if is_present else None,
#                 "checkOut": "17:30" if is_present else None,
#                 "hours": 8.5 if is_present else 0
#             }
#             attendance.append(entry)
        
#         current_date += timedelta(days=1)
    
#     return attendance

# # Login model
# class LoginRequest(BaseModel):
#     userName: str
#     password: str
#     macAddress: str

# # Login endpoint
# @mock_api_router.post("/employee/login")
# async def login(request: LoginRequest):
#     if request.userName in EMPLOYEE_DATA:
#         # Simulate successful login
#         token = f"eyJ.{uuid.uuid4().hex}.{uuid.uuid4().hex}"
#         return {"data": {"token": token}}
#     else:
#         raise HTTPException(status_code=401, detail="Invalid credentials")

# # Get employee data
# @mock_api_router.get("/employee/getDataByEMPId/{employee_id}")
# async def get_employee_data(employee_id: str, request: Request):
#     # Check authorization
#     auth_header = request.headers.get("Authorization")
#     if not auth_header or not auth_header.startswith("Bearer "):
#         raise HTTPException(status_code=401, detail="Unauthorized")
    
#     if employee_id in EMPLOYEE_DATA:
#         return EMPLOYEE_DATA[employee_id]
#     else:
#         raise HTTPException(status_code=404, detail="Employee not found")

# # Get attendance data
# @mock_api_router.get("/employee/attendance/{employee_id}")
# async def get_attendance(
#     employee_id: str, 
#     request: Request,
#     startDate: Optional[str] = None,
#     endDate: Optional[str] = None
# ):
#     # Check authorization
#     auth_header = request.headers.get("Authorization")
#     if not auth_header or not auth_header.startswith("Bearer "):
#         raise HTTPException(status_code=401, detail="Unauthorized")
    
#     if employee_id not in EMPLOYEE_DATA:
#         raise HTTPException(status_code=404, detail="Employee not found")
    
#     # Use provided dates or defaults
#     start = startDate or (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
#     end = endDate or datetime.now().strftime("%Y-%m-%d")
    
#     attendance_data = generate_attendance(employee_id, start, end)
    
#     return {
#         "employeeId": employee_id,
#         "startDate": start,
#         "endDate": end,
#         "records": attendance_data
#     }

# # Function to add this router to the main app
# def add_mock_api(app):
#     app.include_router(mock_api_router)
#     return app