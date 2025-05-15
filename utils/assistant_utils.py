import json
from utils.logger import logger
from config.settings import settings
from openai import OpenAI

# Store OpenAI client instance
openai_client = None

# Store employee threads
employee_threads = {}


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
        raise ValueError(
            "OpenAI API key not found. Please set OPENAI_API_KEY in your environment.")

    openai_client = OpenAI(api_key=api_key)
    return openai_client


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


def get_employee_thread(client, employee_id):
    """Get or create a thread for the employee"""
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


def handle_tool_calls(required_action):
    """Process tool calls from the assistant and return results"""
    # Import here to avoid circular imports
    from api.hr_service import HRService

    hr_service = HRService()

    tool_outputs = []
    for tool_call in required_action.submit_tool_outputs.tool_calls:
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)
        logger.info(
            f"Processing tool call: {function_name} with args: {function_args}")

        # Get the current authenticated employee ID from the function attribute
        authenticated_employee_id = getattr(
            handle_tool_calls, 'current_employee_id', None)

        # IMPORTANT: Override any employee_id in the function arguments with the authenticated user's ID
        if authenticated_employee_id and "employee_id" in function_args:
            original_id = function_args["employee_id"]
            if original_id != authenticated_employee_id:
                logger.warning(
                    f"Overriding employee_id in tool call from {original_id} to {authenticated_employee_id}")
            function_args["employee_id"] = authenticated_employee_id

        result = None
        try:
            if function_name == "get_employee_data":
                result = hr_service.get_employee_data(
                    function_args.get("employee_id"))

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
