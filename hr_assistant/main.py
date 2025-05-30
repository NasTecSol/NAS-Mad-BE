import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import time
from config.settings import settings
from utils.logger import logger
from api.hr_service import HRService
from openai_client import create_openai_client  # Import our custom function
from openai import OpenAI  # Import the OpenAI class

# Import module interfaces
try:
    import modules.auth as auth_module
    import modules.employee as employee_module
    import modules.attendance as attendance_module
    MODULES_AVAILABLE = True
except ImportError as e:
    logger.error(f"Module import error: {str(e)}")
    MODULES_AVAILABLE = False
    
from utils.attendance_formatter import AttendanceFormatter

try:
    from services.mongodb_service import MongoDBService
    from services.vector_search_service import VectorSearchService
    from services.query_parser_service import QueryParserService
    from utils.access_control import AccessControlMatrix
    NEW_SERVICES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"New services not available: {str(e)}")
    NEW_SERVICES_AVAILABLE = False
    
# Initialize services
hr_service = HRService()
# Import assistant instructions
try:
    from modules.assistant_instructions import get_complete_instructions
    logger.info("Successfully imported assistant instructions module")
except ImportError:
    logger.error(
        "Assistant instructions module not found. Please create assistant_instructions.py in the root directory.")

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
    logger.warning(
        "Simulated API module not found. API simulation will not be available.")
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
attendance_module.initialize(hr_service)
# Backward compatibility check
if hasattr(employee_module, 'initialize'):
    employee_module.initialize(hr_service)
else:
    logger.info("Employee module uses new self-initialization pattern")

# Make sure the static directory exists
os.makedirs("static", exist_ok=True)

# Mount the static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Define request and response models


class ChatRequest(BaseModel):
    employee_id: str
    message: str
    language: str = "en"


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

# Initialize new services
mongodb_service = None
vector_search_service = None
query_parser_service = None

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
    # Use existing cache dictionary, no need to declare global
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
            logger.warning(
                f"Failed to retrieve assistant {assistant_id}: {str(e)}")
            # Continue to create a new assistant

    # Create a new assistant
    logger.info("Creating new HR assistant")
    # Note: This function is incomplete in the original code
    # You would need to implement the actual assistant creation logic here
    # For now, we'll assume the assistant ID is provided in settings

    # This is a placeholder - you should implement the actual creation logic
    raise ValueError(
        "Assistant ID not found and creation logic not implemented")


def initialize_new_services():
    """Initialize the new MongoDB and vector search services"""
    global mongodb_service, vector_search_service, query_parser_service

    if not NEW_SERVICES_AVAILABLE:
        logger.warning("New services not available")
        return False

    try:
        if not mongodb_service:
            mongodb_service = MongoDBService()
            vector_search_service = VectorSearchService(mongodb_service)
            query_parser_service = QueryParserService()
            logger.info("New services initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize new services: {str(e)}")
        return False

# Function to handle tool calls made by the assistant
def handle_tool_calls(required_action):
    """Process tool calls from the assistant and return results"""
    tool_outputs = []

    # Initialize new services if not already done
    if not initialize_new_services():
        logger.error("Failed to initialize services for tool handling")

    for tool_call in required_action.submit_tool_outputs.tool_calls:
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        logger.info(
            f"Processing tool call: {function_name} with args: {function_args}")

        # Get the current authenticated employee ID from the function attribute
        authenticated_employee_id = getattr(
            handle_tool_calls, 'current_employee_id', None)

        result = None
        try:
            if function_name == "get_employee_data":
                # Use the new intelligent employee data retrieval
                query = function_args.get("query", "")

                # If no query provided but employee_id exists, create a basic query
                if not query and function_args.get("employee_id"):
                    query = f"get information for employee {function_args['employee_id']}"
                elif not query:
                    query = "show my information"

                # Import the updated module function
                from modules.employee import get_employee_data_tool
                result = get_employee_data_tool(
                    query, authenticated_employee_id)

            elif function_name == "find_similar_employees":
                # Use the new similar employees functionality
                employee_id = function_args.get(
                    "employee_id", authenticated_employee_id)
                from modules.employee import search_similar_employees_tool
                result = search_similar_employees_tool(
                    employee_id, authenticated_employee_id)

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
                result = hr_service.get_team_data(
                    function_args.get("employee_id"))

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
                logger.warning(
                    f"Unknown function called by assistant: {function_name}")
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
        
        
# Add a new endpoint for access control information
@app.get("/access-info/{employee_id}")
def get_access_info(employee_id: str):
    """Get access control information for an employee"""
    try:
        # Initialize services
        if not initialize_new_services():
            return {"error": "Service initialization failed"}

        # Get employee data
        employee_data = mongodb_service.get_employee_by_id(employee_id)
        if not employee_data:
            return {"error": "Employee not found"}

        # Extract grade and role
        employee_info = employee_data.get("employeeInfo", [{}])[0]
        grade = employee_info.get("grade", "L4")
        role = employee_data.get("role", "")

        # Get access summary
        access_summary = AccessControlMatrix.get_access_summary(grade, role)

        return {
            "employee_id": employee_id,
            "grade": grade,
            "role": role,
            "access_summary": access_summary
        }

    except Exception as e:
        logger.error(f"Error getting access info for {employee_id}: {str(e)}")
        return {"error": str(e)}
    
# Add endpoint for testing vector search
@app.post("/test-search")
def test_search(request: dict):
    """Test endpoint for vector search functionality"""
    try:
        if not initialize_new_services():
            return {"error": "Service initialization failed"}

        query = request.get("query", "")
        # vector, criteria, or text
        search_type = request.get("type", "vector")

        if search_type == "vector":
            results = vector_search_service.semantic_search_employees(query)
        elif search_type == "criteria":
            criteria = request.get("criteria", {})
            results = mongodb_service.search_employees_by_criteria(criteria)
        else:
            results = mongodb_service.search_employees_by_text(query)

        # Return basic info only for testing
        simplified_results = []
        for emp in results:
            simplified_results.append({
                "name": f"{emp.get('firstName', '')} {emp.get('lastName', '')}".strip(),
                "employee_id": emp.get("userName", ""),
                "department": emp.get("employeeInfo", [{}])[0].get("depName", ""),
                "score": emp.get("score", 0) if search_type == "vector" else None
            })

        return {
            "query": query,
            "search_type": search_type,
            "results_count": len(simplified_results),
            "results": simplified_results
        }

    except Exception as e:
        logger.error(f"Error in test search: {str(e)}")
        return {"error": str(e)}
    
# Add endpoint for generating embeddings
@app.post("/generate-embeddings")
def generate_embeddings(request: dict):
    """Generate embeddings for employees"""
    try:
        if not initialize_new_services():
            return {"error": "Service initialization failed"}

        batch_size = request.get("batch_size", 10)
        count = vector_search_service.bulk_update_embeddings(batch_size)

        return {
            "success": True,
            "processed_count": count,
            "message": f"Generated embeddings for {count} employees"
        }

    except Exception as e:
        logger.error(f"Error generating embeddings: {str(e)}")
        return {"error": str(e)}


@app.get("/health")
def health_check():
    """Enhanced health check endpoint"""
    health_status = {
        "status": "ok",
        "message": "HR Assistant API is running",
        "stats": {
            "cached_employees": len(employee_data_cache),
            "active_threads": len(employee_threads),
            "greeted_today": len(employee_last_greeted)
        },
        "services": {
            "legacy_modules": MODULES_AVAILABLE,
            "new_services": NEW_SERVICES_AVAILABLE,
            "mongodb": False,
            "vector_search": False
        }
    }

    # Check new services
    if NEW_SERVICES_AVAILABLE:
        try:
            initialize_new_services()
            if mongodb_service and mongodb_service.is_connected():
                health_status["services"]["mongodb"] = True
            if vector_search_service:
                health_status["services"]["vector_search"] = True
        except Exception as e:
            health_status["services"]["error"] = str(e)

    return health_status

@app.delete("/cache/{employee_id}")
def clear_employee_cache(employee_id: str):
    """Clear cached data for a specific employee"""
    # No need to declare global as we're just reading and deleting, not reassigning
    if employee_id in employee_data_cache:
        del employee_data_cache[employee_id]
        return {"status": "success", "message": f"Cache cleared for employee {employee_id}"}

    return {"status": "not_found", "message": f"No cached data found for employee {employee_id}"}


def get_openai_client():
    """Initialize and return the OpenAI client with error handling"""
    global openai_client

    # Return existing client if already created
    if openai_client:
        logger.debug("Using existing OpenAI client")
        return openai_client

    # Create new client with multiple fallback methods
    api_key = settings.OPENAI_API_KEY
    logger.info("Initializing new OpenAI client")

    if not api_key:
        logger.error(
            "OpenAI API key not found. Please set OPENAI_API_KEY in your environment.")
        return None

    try:
        # Method 1: Minimal OpenAI client (most compatible)
        openai_client = OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized successfully")
        return openai_client
    except Exception as e1:
        logger.warning(f"Method 1 failed: {str(e1)}")
        try:
            # Method 2: Try with only required parameters
            openai_client = OpenAI(
                api_key=api_key,
                timeout=30.0
            )
            logger.info("OpenAI client initialized with method 2")
            return openai_client
        except Exception as e2:
            logger.warning(f"Method 2 failed: {str(e2)}")
            try:
                # Method 3: Legacy initialization
                import openai
                openai.api_key = api_key
                openai_client = openai
                logger.info("OpenAI client initialized with legacy method")
                return openai_client
            except Exception as e3:
                logger.error(
                    f"All OpenAI initialization methods failed: {str(e3)}")
                logger.info(
                    "Continuing without OpenAI - will use fallback responses")
                return None



def get_employee_thread(client, employee_id):
    """Get or create a thread for the employee"""
    # No need to declare global here as we're just reading or modifying, not reassigning

    # Check if employee already has a thread
    if employee_id in employee_threads:
        thread_id = employee_threads[employee_id]
        try:
            # Verify the thread exists
            client.beta.threads.retrieve(thread_id)
            logger.info(
                f"Using existing thread for employee {employee_id}: {thread_id}")
            return thread_id
        except Exception as e:
            logger.warning(
                f"Failed to retrieve thread {thread_id} for employee {employee_id}: {str(e)}")
            # Continue to create a new thread

    # Create a new thread
    logger.info(f"Creating new thread for employee {employee_id}")
    thread = client.beta.threads.create()
    employee_threads[employee_id] = thread.id
    return thread.id


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: Request):
    """Handle chat requests from the frontend with OpenAI error handling"""
    try:
        body_bytes = await request.body()
        body = json.loads(body_bytes)

        # Extract the data, handling both nested and flat structures
        # Try to get "request" field, if not present use the body itself
        data = body.get("request", body)

        # Extract the required fields
        employee_id = data.get("employee_id")
        if not employee_id:
            return JSONResponse(
                status_code=400,
                content={"error": "employee_id is required"}
            )

        req_message = data.get("message", "")
        user_language = data.get("language", "en")

        # Now process with these fields
        logger.info(f"Chat request received for employee: {employee_id}")

        employee_data = get_employee_data(employee_id)
        response = ""

        # Check if we got valid employee data
        if not employee_data:
            return ChatResponse(response="Error: Unable to retrieve your employee information. Please try again later.")

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
            employee_grade = "L4"

        # Create greeting based on time
        greeting = get_greeting()

        # Try OpenAI Assistant first, with fallback to new employee module
        try:
            # Initialize OpenAI client using our fixed function
            client = get_openai_client()

            if client is None:
                raise Exception("OpenAI client not available")

            # Get or create the assistant
            assistant = get_assistant(client)
            # Get or create a thread for this employee
            thread_id = get_employee_thread(client, employee_id)

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
                Employee ID: {employee_id}
                Language: {user_language}
                
                My question: {req_message}
                """
            )

            # Determine greeting instruction based on whether employee was already greeted today
            greeting_instruction = ""
            should_greet = should_greet_employee(employee_id)

            if should_greet:
                greeting_instruction = f"Greet employee i.e '{greeting}, {employee_name}! in language = {user_language}'"
                update_employee_greeting_time(employee_id)
            else:
                greeting_instruction = f"No need for formal greeting as we're already in a conversation, Keep conversation in language = {user_language} "

            assistant_instructions = get_complete_instructions(
                authenticated_employee_id=employee_id,
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
            handle_tool_calls.current_employee_id = employee_id

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
                    tool_outputs = handle_tool_calls(
                        run_status.required_action)
                    client.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread_id,
                        run_id=run.id,
                        tool_outputs=tool_outputs
                    )
                elif run_status.status in ["failed", "cancelled", "expired"]:
                    logger.error(
                        f"Run failed with status: {run_status.status}")
                    if hasattr(run_status, "last_error"):
                        logger.error(
                            f"Error details: {run_status.last_error}")
                    raise Exception(
                        f"Assistant run failed: {run_status.status}")

                # Wait before checking again (increase delay to avoid rate limits)
                time.sleep(2)

            if attempt >= max_attempts:
                logger.error(
                    "Reached maximum number of attempts waiting for assistant response")
                raise Exception("Assistant response timeout")

            # Get the latest message from the thread
            messages = client.beta.threads.messages.list(
                thread_id=thread_id
            )

            # Get the assistant's response (latest message from assistant)
            assistant_messages = [
                msg for msg in messages.data if msg.role == "assistant"]

            if assistant_messages:
                latest_message = assistant_messages[0]
                # Extract text content
                response_text = ""
                for content_item in latest_message.content:
                    if content_item.type == "text":
                        response_text += content_item.text.value

                response = response_text
            else:
                response = "I apologize, but I couldn't generate a response. Please try again."

        except Exception as openai_error:
            logger.warning(f"OpenAI Assistant failed: {str(openai_error)}")
            logger.info("Falling back to new employee module")

            # Fallback to new employee module
            try:
                # Try to use the new employee module
                from modules.employee import get_employee_data_tool

                # Use the new employee module as fallback
                query = req_message if req_message else "show my information"
                result = get_employee_data_tool(query, employee_id)

                if result.get("success"):
                    # Add greeting if needed
                    should_greet = should_greet_employee(employee_id)
                    greeting_text = ""
                    if should_greet:
                        greeting_text = f"{greeting}, {employee_name}!\n\n"
                        update_employee_greeting_time(employee_id)

                    response = greeting_text + \
                        result.get("formatted_response",
                                   "I found some information for you.")
                else:
                    response = result.get(
                        "message", "I apologize, but I couldn't find the information you requested.")

            except Exception as fallback_error:
                logger.error(
                    f"Fallback method also failed: {str(fallback_error)}")

                # Final fallback - basic response
                should_greet = should_greet_employee(employee_id)
                if should_greet:
                    response = f"{greeting}, {employee_name}! I'm having some technical difficulties right now, but I'm here to help. Could you please try your request again?"
                    update_employee_greeting_time(employee_id)
                else:
                    response = "I'm experiencing some technical issues right now. Please try your request again, or contact IT support if the problem persists."

        return ChatResponse(response=response)

    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}")
        return ChatResponse(response="I apologize, but I'm experiencing technical difficulties. Please try again later.")

# Run the application
if __name__ == "__main__":
    import uvicorn

    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=8000)
