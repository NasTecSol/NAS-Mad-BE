import os
import json
from datetime import datetime
from typing import Dict, Any, List
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import time
from openai import OpenAI

# Import our modules
from config.settings import settings
from utils.logger import logger
from api.hr_service import HRService

# Import module interfaces
import modules.auth as auth_module
import modules.employee as employee_module
import modules.attendance as attendance_module

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
    thread_id: str = None  # Optional thread ID for conversation history

class ChatResponse(BaseModel):
    response: str
    thread_id: str  # Return thread ID to maintain conversation state

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

# Initialize OpenAI client
def get_openai_client():
    """Initialize and return the OpenAI client"""
    api_key = settings.OPENAI_API_KEY
    logger.info(f"initialising open ai client with ID: {api_key}")
    if not api_key:
        raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY in your environment.")
    
    return OpenAI(api_key=api_key)

# Get or create assistant
def get_assistant(client):
    """Get existing or create new HR assistant"""
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
    try:
        assistant = client.beta.assistants.create(
            name="HR Assistant",
            instructions="""
            You are an HR Assistant that helps employees with HR-related queries.
            Always greet the employee by name according to the time of day.
            You have access to employee data and can help with queries about attendance,
            leave balance, employee profiles, and other HR-related information.
            """,
            tools=[
                {"type": "function", "function": {
                    "name": "get_employee_data",
                    "description": "Get detailed employee data using employee ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "employee_id": {
                                "type": "string",
                                "description": "The employee ID (e.g., EMP103)"
                            }
                        },
                        "required": ["employee_id"]
                    }
                }},
                {"type": "function", "function": {
                    "name": "get_attendance",
                    "description": "Get employee attendance records for a specific date range",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "employee_id": {
                                "type": "string",
                                "description": "The employee ID (e.g., EMP103)"
                            },
                            "start_date": {
                                "type": "string",
                                "description": "Start date in format YYYY-MM-DD"
                            },
                            "end_date": {
                                "type": "string", 
                                "description": "End date in format YYYY-MM-DD"
                            }
                        },
                        "required": ["employee_id"]
                    }
                }}
            ],
            model="gpt-4o"  # Using the latest model (as of April 2025)
        )
        
        # Output the assistant ID for the user to add to their .env
        assistant_id = assistant.id
        logger.info(f"Created new assistant with ID: {assistant_id}")
        logger.info(f"Add this to your .env file: OPENAI_ASSISTANT_ID={assistant_id}")
        
        return assistant
    except Exception as e:
        logger.error(f"Error creating assistant: {str(e)}")
        raise ValueError(f"Failed to create OpenAI assistant: {str(e)}")

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
    return {"status": "ok", "message": "HR Assistant API is running"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Handle chat requests from the frontend"""
    try:
        logger.info(f"Chat request received for employee: {request.employee_id}")
        
        # Get employee data directly from HR service
        try:
            employee_data_result = hr_service.get_employee_data(request.employee_id)
            
            if not employee_data_result["success"]:
                logger.error(f"Failed to get employee data: {employee_data_result['message']}")
                return ChatResponse(
                    response=f"Error: {employee_data_result['message']}",
                    thread_id=request.thread_id or "error"
                )
            
            employee_data = employee_data_result["data"]
        except Exception as e:
            logger.error(f"Error retrieving employee data: {str(e)}")
            return ChatResponse(
                response=f"Error retrieving employee data. Please try again.",
                thread_id=request.thread_id or "error"
            )
        
        # Extract employee name
        try:
            first_name = employee_data.get("firstName", "")
            last_name = employee_data.get("lastName", "")
            full_name = f"{first_name} {last_name}".strip()
            employee_name = full_name if full_name else "there"
        except Exception as e:
            logger.warning(f"Error extracting employee name: {str(e)}")
            employee_name = "there"
        
        # Create greeting based on time
        greeting = get_greeting()
        
        # Initialize OpenAI client
        client = get_openai_client()
        
        # Get or create the assistant
        assistant = get_assistant(client)
        
        # Handle the conversation using thread_id for state management
        thread_id = request.thread_id
        
        # If no thread_id provided, create a new thread
        if not thread_id:
            thread = client.beta.threads.create()
            thread_id = thread.id
            logger.info(f"Created new thread with ID: {thread_id}")
            
            # If this is a new thread, add employee context
            employee_data_str = json.dumps(employee_data, indent=2)
            client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=f"""
                SYSTEM CONTEXT (not visible to employee):
                Employee Information:
                {employee_data_str}
                
                Time of day: {greeting.lower().replace('good ', '')}
                Employee name: {employee_name}
                Employee ID: {request.employee_id}
                """
            )
        
        # Generate AI response
        if not request.message:
            # Initial greeting - no need to call the assistant
            response = f"{greeting}, {employee_name}! I'm your HR assistant. How may I help you today?"
            logger.info(f"Sending initial greeting to employee: {request.employee_id}")
        else:
            # Process actual query with OpenAI Assistant
            logger.info(f"Processing query for employee {request.employee_id}: {request.message}")
            
            try:
                # Add the user's message to the thread
                client.beta.threads.messages.create(
                    thread_id=thread_id,
                    role="user",
                    content=request.message
                )
                
                # Function to handle tool calls
                def handle_tool_calls(required_action):
                    tool_outputs = []
                    for tool_call in required_action.submit_tool_outputs.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        
                        result = None
                        if function_name == "get_employee_data":
                            result = hr_service.get_employee_data(function_args.get("employee_id"))
                        elif function_name == "get_attendance":
                            result = hr_service.get_attendance(
                                function_args.get("employee_id"),
                                function_args.get("start_date"),
                                function_args.get("end_date")
                            )
                        
                        tool_outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": json.dumps(result)
                        })
                    
                    return tool_outputs
                
                # Run the assistant
                run = client.beta.threads.runs.create(
                    thread_id=thread_id,
                    assistant_id=assistant.id,
                    instructions=f"Always start your response with '{greeting}, {employee_name}!' Provide helpful information based on the employee data."
                )
                
                # Process the run including any tool calls
                max_attempts = 20  # Prevent infinite loops
                attempt = 0
                
                while attempt < max_attempts:
                    attempt += 1
                    run_status = client.beta.threads.runs.retrieve(
                        thread_id=thread_id,
                        run_id=run.id
                    )
                    
                    if run_status.status == "completed":
                        break
                    elif run_status.status == "requires_action":
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
                        return ChatResponse(
                            response=f"{greeting}, {employee_name}! I apologize, but I encountered an error processing your request. Please try again.",
                            thread_id=thread_id
                        )
                    
                    # Wait before checking again (increase delay to avoid rate limits)
                    time.sleep(10)
                
                if attempt >= max_attempts:
                    logger.error("Reached maximum number of attempts waiting for assistant response")
                    return ChatResponse(
                        response=f"{greeting}, {employee_name}! I apologize, but it's taking too long to process your request. Please try again later.",
                        thread_id=thread_id
                    )
                
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
                    response = f"{greeting}, {employee_name}! I apologize, but I couldn't generate a response. Please try again."
            
            except Exception as e:
                logger.error(f"Error generating response: {str(e)}")
                response = f"{greeting}, {employee_name}! I apologize, but I'm having trouble processing your request right now. Please try again later."
        
        return ChatResponse(response=response, thread_id=thread_id)
    
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# Run the application
if __name__ == "__main__":
    import uvicorn
    
    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=8000)