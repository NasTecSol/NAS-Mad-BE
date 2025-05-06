import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import time
from config.settings import settings
from utils.logger import logger
from api.hr_service import HRService
from openai_client import create_openai_client  # Import our custom function
from openai import OpenAI  # Import the OpenAI class

# Import module interfaces
import modules.auth as auth_module
import modules.employee as employee_module
import modules.attendance as attendance_module
from utils.attendance_formatter import AttendanceFormatter

from modules.assistant_instructions import get_complete_instructions
# Import assistant instructions
try:
    from modules.assistant_instructions import get_complete_instructions
    logger.info("Successfully imported assistant instructions module")
except ImportError:
    logger.error("Assistant instructions module not found. Please create assistant_instructions.py in the root directory.")
    
    # Fallback function if the module is missing
    def get_complete_instructions(authenticated_employee_id, employee_name, employee_grade, greeting_instruction=None):
        greeting_text = greeting_instruction + "\n\n" if greeting_instruction else ""
        return f"""
        {greeting_text}
        
        IMPORTANT CONTEXT:
        - The authenticated employee ID is: {authenticated_employee_id}
        - Employee name: {employee_name}
        - Employee grade: {employee_grade}
        """
    
# Import simulated API (if available)
try:
    from simulated_api import add_mock_api
except ImportError:
    logger.warning("Simulated API module not found. API simulation will not be available.")
    add_mock_api = None

# Initialize FastAPI app
app = FastAPI(title="HR Assistant API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add simulated API if available
if add_mock_api:
    add_mock_api(app)

# Initialize services
hr_service = HRService()

# Initialize modules by passing the HR service
auth_module.initialize(hr_service)
employee_module.initialize(hr_service)
attendance_module.initialize(hr_service)

# Make sure the static directory exists
os.makedirs("static", exist_ok=True)

# Mount the static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Request models
class ChatRequest(BaseModel):
    employee_id: str
    message: str = ""

class ChatResponse(BaseModel):
    response: str

# Store OpenAI client instance
openai_client = None

# Store employee threads
employee_threads = {}

# Store last greeting times
employee_last_greeted = {}

# Store employee data cache
# Structure: {employee_id: {"data": employee_data, "last_fetched": timestamp}}
employee_data_cache = {}

# Employee data cache expiration time (24 hours)
EMPLOYEE_DATA_CACHE_EXPIRY = timedelta(hours=24)

# Helper function to get time-based greeting
def get_greeting() -> str:
    """Generate appropriate greeting based on current time of day."""
    current_hour = datetime.now().hour
    
    if 5 <= current_hour < 12:
        return "Good morning"
    elif 12 <= current_hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"

# Check if employee should be greeted today
def should_greet_employee(employee_id: str) -> bool:
    """Check if employee should be greeted based on last greeting time."""
    today = datetime.now().date()
    
    # If employee hasn't been greeted before or was last greeted on a different day
    if employee_id not in employee_last_greeted:
        return True
        
    last_greeted_date = employee_last_greeted[employee_id].date()
    return last_greeted_date != today

# Update last greeting time for employee
def update_employee_greeting_time(employee_id: str):
    """Update the last time the employee was greeted."""
    employee_last_greeted[employee_id] = datetime.now()

# Get cached employee data or fetch it if needed/expired
def get_employee_data(employee_id: str) -> Dict[str, Any]:
    """
    Get employee data from cache or fetch from service if needed.
    Returns the employee data dictionary.
    """
    global employee_data_cache
    
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
        employee_data_result = hr_service.get_employee_data(employee_id)
        
        if not employee_data_result["success"]:
            logger.error(f"Failed to get employee data: {employee_data_result['message']}")
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

# Create or get assistant
def get_assistant(client):
    """Create or get the HR assistant"""
    # Check if assistant ID is in env
    assistant_id = settings.OPENAI_ASSISTANT_ID
    
    if assistant_id:
        try:
            # Verify the assistant exists
            assistant = client.beta.assistants.retrieve(assistant_id)
            logger.info(f"Using existing assistant with ID: {assistant_id}")
            return assistant
        except Exception as e:
            logger.warning(f"Failed to retrieve assistant {assistant_id}: {str(e)}")
            # Continue to create a new assistant
    
    # Create a new assistant
    logger.info("Creating new HR assistant")
    # Note: This function is incomplete in the original code
    # You would need to implement the actual assistant creation logic here
    # For now, we'll assume the assistant ID is provided in settings

    # This is a placeholder - you should implement the actual creation logic
    raise ValueError("Assistant ID not found and creation logic not implemented")

# Function to handle tool calls made by the assistant
def handle_tool_calls(required_action):
    """Process tool calls from the assistant and return results"""
    tool_outputs = []
    for tool_call in required_action.submit_tool_outputs.tool_calls:
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        logger.info(f"Processing tool call: {function_name} with args: {function_args}")
        
        # Get the current authenticated employee ID from the function attribute
        authenticated_employee_id = getattr(handle_tool_calls, 'current_employee_id', None)
        
        # IMPORTANT: Override any employee_id in the function arguments with the authenticated user's ID
        if authenticated_employee_id and "employee_id" in function_args:
            original_id = function_args["employee_id"]
            if original_id != authenticated_employee_id:
                logger.warning(f"Overriding employee_id in tool call from {original_id} to {authenticated_employee_id}")
            function_args["employee_id"] = authenticated_employee_id
        
        result = None
        try:
            if function_name == "get_employee_data":
                result = hr_service.get_employee_data(function_args.get("employee_id"))
            
            elif function_name == "get_attendance":
                result = hr_service.get_attendance(
                    function_args.get("employee_id"),
                    function_args.get("date_type", "recent"),
                    function_args.get("include_team")
                )
            
            elif function_name == "get_personal_attendance":
                result = hr_service.get_personal_attendance(
                    function_args.get("employee_id"),
                    function_args.get("date_type", "recent")
                )
            
            elif function_name == "get_team_attendance":
                result = hr_service.get_team_attendance(
                    function_args.get("employee_id"),
                    function_args.get("date_type", "recent")
                )
            
            elif function_name == "get_team_data":
                result = hr_service.get_team_data(function_args.get("employee_id"))
            
            elif function_name == "get_attendance_report":
                result = hr_service.get_attendance_report(
                    function_args.get("employee_id"),
                    function_args.get("date_type", "today"),
                    function_args.get("company_id"),
                    function_args.get("branch_id"),
                    function_args.get("department_id"),
                    function_args.get("report_type", "all")
                )
            
            else:
                logger.warning(f"Unknown function called by assistant: {function_name}")
                result = {
                    "success": False,
                    "message": f"Unknown function: {function_name}"
                }
        
        except Exception as e:
            logger.error(f"Error executing function {function_name}: {str(e)}")
            result = {
                "success": False,
                "message": f"Error executing function: {str(e)}"
            }
        
        # Add the result to tool outputs
        tool_outputs.append({
            "tool_call_id": tool_call.id,
            "output": json.dumps(result)
        })
    
    return tool_outputs

# Define routes
@app.get("/", response_class=HTMLResponse)
def read_root():
    """Serve the frontend HTML file"""
    try:
        with open("static/index.html") as f:
            return f.read()
    except FileNotFoundError:
        return """
        <html>
            <head><title>HR Assistant API</title></head>
            <body>
                <h1>HR Assistant API is running</h1>
                <p>Frontend file not found. Please create a static/index.html file.</p>
            </body>
        </html>
        """

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "ok", 
        "message": "HR Assistant API is running",
        "stats": {
            "cached_employees": len(employee_data_cache),
            "active_threads": len(employee_threads),
            "greeted_today": len(employee_last_greeted)
        }
    }

@app.delete("/cache/{employee_id}")
def clear_employee_cache(employee_id: str):
    """Clear cached data for a specific employee"""
    global employee_data_cache
    
    if employee_id in employee_data_cache:
        del employee_data_cache[employee_id]
        return {"status": "success", "message": f"Cache cleared for employee {employee_id}"}
    
    return {"status": "not_found", "message": f"No cached data found for employee {employee_id}"}

def get_openai_client():
    """Initialize and return the OpenAI client"""
    global openai_client
    
    # Return existing client if already created
    if openai_client:
        logger.debug("Using existing OpenAI client")
        return openai_client
    
    # Create new client
    api_key = settings.OPENAI_API_KEY
    logger.info("Initializing new OpenAI client")
    
    if not api_key:
        raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY in your environment.")
    
    openai_client = OpenAI(api_key=api_key)
    return openai_client

def get_employee_thread(client, employee_id):
    """Get or create a thread for the employee"""
    global employee_threads
    
    # Check if employee already has a thread
    if employee_id in employee_threads:
        thread_id = employee_threads[employee_id]
        try:
            # Verify the thread exists
            client.beta.threads.retrieve(thread_id)
            logger.info(f"Using existing thread for employee {employee_id}: {thread_id}")
            return thread_id
        except Exception as e:
            logger.warning(f"Failed to retrieve thread {thread_id} for employee {employee_id}: {str(e)}")
            # Continue to create a new thread
    
    # Create a new thread
    logger.info(f"Creating new thread for employee {employee_id}")
    thread = client.beta.threads.create()
    employee_threads[employee_id] = thread.id
    return thread.id

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Handle chat requests from the frontend"""
    try:
        logger.info(f"Chat request received for employee: {request.employee_id}")
        
        # Get employee data from cache or HR service
        employee_data = get_employee_data(request.employee_id)
        
        # Check if we got valid employee data
        if not employee_data:
            return ChatResponse(response=f"Error: Unable to retrieve your employee information. Please try again later.")
        
        # Extract employee name
        try:
            first_name = employee_data.get("firstName", "")
            last_name = employee_data.get("lastName", "")
            full_name = f"{first_name} {last_name}".strip()
            employee_name = full_name if full_name else "there"
            employee_einfo = employee_data.get("employeeInfo", [])[0]
            employee_grade = employee_einfo.get("grade", "") 
        except Exception as e:
            logger.warning(f"Error extracting employee name: {str(e)}")
            employee_name = "there"
        
        # Create greeting based on time
        greeting = get_greeting()
        
        # Generate AI response
        if not request.message:
            # Determine if employee should be greeted today
            should_greet = should_greet_employee(request.employee_id)
            
            if should_greet:
                # Initial greeting - only once per day
                response = f"{greeting}, {employee_name}! I'm your HR assistant. How may I help you today?"
                logger.info(f"Sending initial greeting to employee: {request.employee_id}")
                update_employee_greeting_time(request.employee_id)
            else:
                # Already greeted today
                response = f"Hello again {employee_name}, how can I assist you now?"
                logger.info(f"Employee {request.employee_id} already greeted today, sending minimal greeting")
        else:
            # Process actual query with OpenAI Assistant
            logger.info(f"Processing query for employee {request.employee_id}: {request.message}")
            
            try:
                # Initialize OpenAI client using our function that handles caching
                client = get_openai_client()
                
                # Get or create the assistant
                assistant = get_assistant(client)
                # Get or create a thread for this employee
                thread_id = get_employee_thread(client, request.employee_id)
                
                # Format employee data as a clean JSON string for the context
                employee_data_str = json.dumps(employee_data, indent=2)
                
                # Add the user's message to the thread
                client.beta.threads.messages.create(
                    thread_id=thread_id,
                    role="user",
                    content=f"""
                    Employee Information:
                    {employee_data_str}
                    
                    Time of day: {greeting.lower().replace('good ', '')}
                    Employee name: {employee_name}
                    Employee ID: {request.employee_id}
                    
                    My question: {request.message}
                    """
                )
                
                # Determine greeting instruction based on whether employee was already greeted today
                greeting_instruction = ""
                should_greet = should_greet_employee(request.employee_id)
                
                if should_greet:
                    greeting_instruction = f"Start your response with '{greeting}, {employee_name}!'"
                    update_employee_greeting_time(request.employee_id)
                else:
                    greeting_instruction = "No need for formal greeting as we're already in a conversation."
                

                    assistant_instructions = get_complete_instructions(
                        authenticated_employee_id=request.employee_id,
                        employee_name=employee_name,
                        employee_grade=employee_grade,
                        greeting_instruction=greeting_instruction
                            )
                    
                # Run the assistant
                run = client.beta.threads.runs.create(
                    thread_id=thread_id,
                    assistant_id=assistant.id,
                    instructions=assistant_instructions,
                )
                
                # Process the run including any tool calls
                max_attempts = 20  # Prevent infinite loops
                attempt = 0
                
                # Set the employee ID before processing any tool calls
                handle_tool_calls.current_employee_id = request.employee_id
                
                while attempt < max_attempts:
                    attempt += 1
                    run_status = client.beta.threads.runs.retrieve(
                        thread_id=thread_id,
                        run_id=run.id
                    )
                    
                    if run_status.status == "completed":
                        break
                    elif run_status.status == "requires_action":
                        # Call with just one parameter - the required_action
                        tool_outputs = handle_tool_calls(run_status.required_action)
                        client.beta.threads.runs.submit_tool_outputs(
                            thread_id=thread_id,
                            run_id=run.id,
                            tool_outputs=tool_outputs
                        )
                    elif run_status.status in ["failed", "cancelled", "expired"]:
                        logger.error(f"Run failed with status: {run_status.status}")
                        if hasattr(run_status, "last_error"):
                            logger.error(f"Error details: {run_status.last_error}")
                        return ChatResponse(response=f"I apologize, but I encountered an error processing your request. Please try again.")
                    
                    # Wait before checking again (increase delay to avoid rate limits)
                    time.sleep(2)
                
                if attempt >= max_attempts:
                    logger.error("Reached maximum number of attempts waiting for assistant response")
                    return ChatResponse(response=f"I apologize, but it's taking too long to process your request. Please try again later.")
                
                # Get the latest message from the thread
                messages = client.beta.threads.messages.list(
                    thread_id=thread_id
                )
                
                # Get the assistant's response (latest message from assistant)
                assistant_messages = [msg for msg in messages.data if msg.role == "assistant"]
                
                if assistant_messages:
                    latest_message = assistant_messages[0]
                    # Extract text content
                    response_text = ""
                    for content_item in latest_message.content:
                        if content_item.type == "text":
                            response_text += content_item.text.value
                    
                    response = response_text
                else:
                    response = f"I apologize, but I couldn't generate a response. Please try again."
            
            except Exception as e:
                logger.error(f"Error generating response: {str(e)}")
                response = f"I apologize, but I'm having trouble processing your request right now. Please try again later."
        
        return ChatResponse(response=response)
    
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

def get_attendance_report(self, employee_id: str, date_type: str = "today", 
                       company_id: str = None, branch_id: str = None, department_id: str = None) -> Dict[str, Any]:
    """
    Get comprehensive attendance report for all employees, categorized by company, branch, and department.
    This report is only available to high-level managers (L0-L1) with specific roles.
    
    Args:
        employee_id: Employee ID of the requester
        date_type: Date range specification ('today', 'yesterday', 'recent', 'this_month', 'previous_month', 
                  or specific date/range)
        company_id: Optional filter for specific company
        branch_id: Optional filter for specific branch
        department_id: Optional filter for specific department
        
    Returns:
        Dictionary containing attendance report data organized by company/branch/department
    """
    logger.info(f"Processing attendance report request for employee: {employee_id}")
    logger.info(f"Date type: {date_type}, Filters - Company: {company_id}, Branch: {branch_id}, Department: {department_id}")
    
    # 1. First, verify the employee has appropriate access level
    employee_data_result = self.get_employee_data(employee_id)
    if not employee_data_result["success"]:
        logger.error(f"Failed to get employee data for authorization check: {employee_data_result['message']}")
        return {
            "success": False,
            "message": "Authorization failed: Unable to verify employee details"
        }
    
    employee_data = employee_data_result["data"]
    
    # Check employee grade and role
    employee_grade = employee_data.get("grade", "")
    employee_role = employee_data.get("role", "")
    
    # Verify the employee is authorized (L0-L1 with appropriate role)
    is_authorized = (
        employee_grade in ["L0", "L1"] and 
        employee_role in ["HR Manager", "admin", "owner"]
    )
    
    if not is_authorized:
        logger.warning(f"Unauthorized access attempt by employee {employee_id} (Grade: {employee_grade}, Role: {employee_role})")
        return {
            "success": False,
            "message": "You are not authorized to access the attendance report"
        }
    
    # 2. Calculate date range for the report
    start_date, end_date = self.calculate_date_range(date_type)
    
    # For previous month special case
    if date_type == "previous_month":
        today = datetime.now().date()
        # First day of current month
        first_day_current_month = today.replace(day=1)
        # Last day of previous month
        last_day_previous_month = first_day_current_month - timedelta(days=1)
        # First day of previous month
        first_day_previous_month = last_day_previous_month.replace(day=1)
        
        start_date = first_day_previous_month.strftime("%Y-%m-%d")
        end_date = last_day_previous_month.strftime("%Y-%m-%d")
    
    # 3. Get token for API request
    token = self.get_token(employee_id)
    if not token:
        logger.error(f"Failed to get token for employee: {employee_id}")
        return {
            "success": False,
            "message": "Authentication failed"
        }
    
    # 4. Construct the attendance report URL
    # We'll use existing endpoint but request all data without filtering by employee ID
    report_url = f"{settings.HR_API_BASE_URL}/c-emp-attendance/getCompanyAttendance/{start_date}/{end_date}"
    
    # Add filters if provided
    filters = []
    if company_id:
        filters.append(f"companyId={company_id}")
    if branch_id:
        filters.append(f"branchId={branch_id}")
    if department_id:
        filters.append(f"departmentId={department_id}")
    
    if filters:
        report_url += f"?{'&'.join(filters)}"
    
    # Add pagination parameters
    if "?" in report_url:
        report_url += "&page=0&limit=1000"  # Large limit to get all data
    else:
        report_url += "?page=0&limit=1000"  # Large limit to get all data
    
    logger.info(f"Attendance report request to: {report_url}")
    
    # 5. Make the API request
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(report_url, headers=headers)
        response.raise_for_status()
        
        attendance_data = response.json()
        
        if attendance_data.get("statusCode") == 200 and "data" in attendance_data:
            # 6. Process and organize the data by company/branch/department
            raw_data = attendance_data["data"]
            
            # Organize by company, branch, department
            organized_data = self._organize_attendance_data(raw_data)
            
            # Generate summary statistics
            summary = self._generate_attendance_summary(organized_data, start_date, end_date)
            
            logger.info(f"Successfully retrieved and processed attendance report data")
            
            return {
                "success": True,
                "data": organized_data,
                "summary": summary,
                "date_range": {
                    "start_date": start_date,
                    "end_date": end_date
                },
                "message": "Attendance report generated successfully",
                "filters": {
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "department_id": department_id
                }
            }
        else:
            logger.warning(f"Attendance report response not in expected format: {json.dumps(attendance_data)}")
            return {
                "success": False,
                "message": "Failed to retrieve attendance report: Invalid response format"
            }
    except Exception as e:
        logger.error(f"Error retrieving attendance report: {str(e)}")
        return {
            "success": False,
            "message": f"Failed to retrieve attendance report: {str(e)}"
        }

def _organize_attendance_data(self, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Organize raw attendance data by company, branch, and department
    
    Args:
        raw_data: List of attendance records
        
    Returns:
        Nested dictionary organized by company > branch > department > employee
    """
    organized = {}
    
    for record in raw_data:
        # Extract organizational structure from record
        company_id = record.get("companyId", "unknown")
        company_name = record.get("companyName", "Unknown Company")
        branch_id = record.get("branchId", "unknown")
        branch_name = record.get("branchName", "Unknown Branch")
        department_id = record.get("departmentId", "unknown")
        department_name = record.get("departmentName", "Unknown Department")
        
        # Extract employee data
        employee_id = record.get("employeeId", "unknown")
        employee_name = f"{record.get('firstName', '')} {record.get('lastName', '')}".strip() or "Unknown Employee"
        
        # Create nested structure if it doesn't exist
        if company_id not in organized:
            organized[company_id] = {
                "name": company_name,
                "branches": {}
            }
            
        if branch_id not in organized[company_id]["branches"]:
            organized[company_id]["branches"][branch_id] = {
                "name": branch_name,
                "departments": {}
            }
            
        if department_id not in organized[company_id]["branches"][branch_id]["departments"]:
            organized[company_id]["branches"][branch_id]["departments"][department_id] = {
                "name": department_name,
                "employees": {}
            }
            
        if employee_id not in organized[company_id]["branches"][branch_id]["departments"][department_id]["employees"]:
            organized[company_id]["branches"][branch_id]["departments"][department_id]["employees"][employee_id] = {
                "name": employee_name,
                "attendance": []
            }
        
        # Add attendance record to employee
        attendance_info = {
            "date": record.get("date", ""),
            "punchIn": record.get("punchIn", ""),
            "punchOut": record.get("punchOut", ""),
            "status": record.get("status", ""),
            "workingHours": record.get("workingHours", 0),
            "late": record.get("late", False)
        }
        
        organized[company_id]["branches"][branch_id]["departments"][department_id]["employees"][employee_id]["attendance"].append(attendance_info)
    
    return organized

def _generate_attendance_summary(self, organized_data: Dict[str, Any], start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Generate summary statistics from organized attendance data
    
    Args:
        organized_data: Attendance data organized by company/branch/department/employee
        start_date: Start date of the report period
        end_date: End date of the report period
        
    Returns:
        Dictionary containing attendance summary statistics
    """
    summary = {
        "total_companies": 0,
        "total_branches": 0,
        "total_departments": 0,
        "total_employees": 0,
        "attendance_status": {
            "present": 0,
            "absent": 0,
            "half_day": 0,
            "leave": 0,
            "weekend": 0,
            "holiday": 0,
            "late": 0
        },
        "companies": [],
        "average_working_hours": 0,
        "total_working_hours": 0,
        "date_range": {
            "start_date": start_date,
            "end_date": end_date
        }
    }
    
    total_working_hours = 0
    total_records_with_hours = 0
    
    # Process each company
    for company_id, company_data in organized_data.items():
        company_summary = {
            "id": company_id,
            "name": company_data["name"],
            "total_branches": len(company_data["branches"]),
            "total_employees": 0,
            "attendance_rate": 0,
            "late_percentage": 0
        }
        
        company_present = 0
        company_late = 0
        company_total = 0
        
        # Process each branch
        for branch_id, branch_data in company_data["branches"].items():
            branch_employees = 0
            
            # Process each department
            for department_id, department_data in branch_data["departments"].items():
                department_employees = len(department_data["employees"])
                branch_employees += department_employees
                summary["total_departments"] += 1
                
                # Process each employee
                for employee_id, employee_data in department_data["employees"].items():
                    summary["total_employees"] += 1
                    company_total += len(employee_data["attendance"])
                    
                    # Process attendance records
                    for record in employee_data["attendance"]:
                        status = record.get("status", "").lower()
                        
                        if status == "present":
                            summary["attendance_status"]["present"] += 1
                            company_present += 1
                        elif status == "absent":
                            summary["attendance_status"]["absent"] += 1
                        elif status == "half day":
                            summary["attendance_status"]["half_day"] += 1
                        elif status == "leave":
                            summary["attendance_status"]["leave"] += 1
                        elif status == "weekend":
                            summary["attendance_status"]["weekend"] += 1
                        elif status == "holiday":
                            summary["attendance_status"]["holiday"] += 1
                        
                        if record.get("late", False):
                            summary["attendance_status"]["late"] += 1
                            company_late += 1
                        
                        # Add working hours to total
                        working_hours = record.get("workingHours", 0)
                        if working_hours:
                            total_working_hours += working_hours
                            total_records_with_hours += 1
            
            summary["total_branches"] += 1
            company_summary["total_employees"] += branch_employees
        
        # Calculate company attendance rate
        if company_total > 0:
            company_summary["attendance_rate"] = round((company_present / company_total) * 100, 2)
            company_summary["late_percentage"] = round((company_late / company_total) * 100, 2)
        
        summary["companies"].append(company_summary)
        summary["total_companies"] += 1
    
    # Calculate average working hours
    if total_records_with_hours > 0:
        summary["average_working_hours"] = round(total_working_hours / total_records_with_hours, 2)
    
    summary["total_working_hours"] = round(total_working_hours, 2)
    
    return summary
# Run the application
if __name__ == "__main__":
    import uvicorn
    
    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=8000)