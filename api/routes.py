from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import json
from datetime import datetime, timedelta
import time
from typing import Dict, Any

from utils.logger import logger
from utils.assistant_utils import (
    get_openai_client,
    get_assistant,
    get_employee_thread,
    handle_tool_calls,
)
from utils.employee_utils import (
    get_employee_data,
    should_greet_employee,
    update_employee_greeting_time,
    get_greeting,
    clear_employee_cache,
    get_cache_stats,
)

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

# Create router
router = APIRouter()

# Define request and response models


class ChatRequest(BaseModel):
    employee_id: str
    message: str
    language: str = "en"


class ChatResponse(BaseModel):
    response: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request):
    """Handle chat requests from the frontend"""
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

        # Create greeting based on time
        greeting = get_greeting()

        # Generate AI response
        if not req_message:
            # Determine if employee should be greeted today
            should_greet = should_greet_employee(employee_id)

            if should_greet:
                # Initial greeting - only once per day
                response = f"{greeting}, {employee_name}! I'm your HR assistant. How may I help you today?"
                logger.info(
                    f"Sending initial greeting to employee: {employee_id}")
                update_employee_greeting_time(employee_id)
            else:
                # Already greeted today
                response = f"Hello again {employee_name}, how can I assist you now?"
                logger.info(
                    f"Employee {employee_id} already greeted today, sending minimal greeting")
        else:
            # Process actual query with OpenAI Assistant
            logger.info(
                f"Processing query for employee {employee_id}: {req_message}")

            try:
                # Initialize OpenAI client using our function that handles caching
                client = get_openai_client()

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
                    greeting_instruction = f"Start your response with '{greeting}, {employee_name}!'"
                    update_employee_greeting_time(employee_id)
                else:
                    greeting_instruction = "No need for formal greeting as we're already in a conversation."

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
                        return ChatResponse(response="I apologize, but I encountered an error processing your request. Please try again.")

                    # Wait before checking again (increase delay to avoid rate limits)
                    time.sleep(2)

                if attempt >= max_attempts:
                    logger.error(
                        "Reached maximum number of attempts waiting for assistant response")
                    return ChatResponse(response="I apologize, but it's taking too long to process your request. Please try again later.")

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

            except Exception as e:
                logger.error(f"Error generating response: {str(e)}")
                response = "I apologize, but I'm having trouble processing your request right now. Please try again later."

        return ChatResponse(response=response)

    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"An error occurred: {str(e)}")


@router.delete("/cache/{employee_id}")
def clear_cache(employee_id: str):
    """Clear cached data for a specific employee"""
    return clear_employee_cache(employee_id)
