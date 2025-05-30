from typing import Dict, Any, List, Optional
from langchain.tools import Tool
from utils.logger import logger

# Global service references
mongodb_service = None
vector_search_service = None
query_parser_service = None

# Try to import services with fallbacks
try:
    from utils.access_control import AccessControlMatrix, DataCategory
    ACCESS_CONTROL_AVAILABLE = True
except ImportError as e:
    logger.error(f"Access control not available: {str(e)}")
    ACCESS_CONTROL_AVAILABLE = False

try:
    from services.mongodb_service import MongoDBService
    MONGODB_AVAILABLE = True
except ImportError as e:
    logger.error(f"MongoDB service not available: {str(e)}")
    MONGODB_AVAILABLE = False

try:
    from services.vector_search_service import VectorSearchService
    VECTOR_SEARCH_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Vector search service not available: {str(e)}")
    VECTOR_SEARCH_AVAILABLE = False

try:
    from services.query_parser_service import QueryParserService, QueryIntent
    QUERY_PARSER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Query parser service not available: {str(e)}")
    QUERY_PARSER_AVAILABLE = False


def initialize_services():
    """Initialize all available services"""
    global mongodb_service, vector_search_service, query_parser_service

    if not MONGODB_AVAILABLE:
        logger.error(
            "MongoDB service not available - employee module will not work")
        return False

    try:
        if not mongodb_service:
            mongodb_service = MongoDBService()
            logger.info("MongoDB service initialized")

        if VECTOR_SEARCH_AVAILABLE and not vector_search_service:
            vector_search_service = VectorSearchService(mongodb_service)
            logger.info("Vector search service initialized")

        if QUERY_PARSER_AVAILABLE and not query_parser_service:
            query_parser_service = QueryParserService()
            logger.info("Query parser service initialized")

        logger.info("Employee module services initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Error initializing services: {str(e)}")
        return False


def get_employee_data_tool(query: str, requester_id: str = None) -> Dict[str, Any]:
    """
    Employee data retrieval with fallback functionality
    
    Args:
        query: Natural language query or employee ID
        requester_id: ID of the person making the request
    
    Returns:
        Dictionary containing filtered employee data based on access permissions
    """
    logger.info(
        f"Employee data query: '{query}' from requester: {requester_id}")

    try:
        # Initialize services if not already done
        if not initialize_services():
            return {
                "success": False,
                "message": "Service initialization failed. Please check your configuration."
            }

        # Parse the query if parser is available, otherwise use simple parsing
        if QUERY_PARSER_AVAILABLE and query_parser_service:
            parsed_query = query_parser_service.parse_query(
                query, requester_id)
            logger.info(f"Parsed query: {parsed_query}")
        else:
            # Simple fallback parsing
            parsed_query = _simple_query_parse(query, requester_id)
            logger.info(f"Simple parsed query: {parsed_query}")

        # Get requester's information for access control
        requester_info = _get_requester_info(requester_id)
        if not requester_info:
            return {
                "success": False,
                "message": "Could not verify requester information for access control"
            }

        # Execute search with available methods
        search_results = _execute_search_with_fallbacks(parsed_query)

        if not search_results:
            return {
                "success": False,
                "message": "No employees found matching your query",
                "query_parsed": parsed_query
            }

        # Apply access control if available
        filtered_results = []
        for employee_data in search_results:
            if _can_access_employee(requester_info, employee_data):
                filtered_data = _filter_employee_data(
                    requester_info,
                    employee_data,
                    parsed_query.get("data_requested", [])
                )
                if filtered_data:
                    filtered_results.append(filtered_data)

        if not filtered_results:
            return {
                "success": False,
                "message": "You don't have permission to access the requested employee information"
            }

        # Format response
        formatted_response = _format_response_simple(
            parsed_query, filtered_results)

        return {
            "success": True,
            "data": filtered_results,
            "formatted_response": formatted_response,
            "query_info": {
                "intent": parsed_query.get("intent", "unknown"),
                "confidence": parsed_query.get("confidence", 0.5),
                "parameters": parsed_query.get("parameters", {})
            },
            "message": f"Found {len(filtered_results)} employee(s)"
        }

    except Exception as e:
        logger.error(f"Error in employee data retrieval: {str(e)}")
        return {
            "success": False,
            "message": f"Error processing your request: {str(e)}"
        }


def _simple_query_parse(query: str, requester_id: str = None) -> Dict[str, Any]:
    """Simple fallback query parsing when query parser service isn't available"""
    import re

    parsed = {
        "original_query": query,
        "intent": "get_employee_info",
        "parameters": {},
        "data_requested": [],
        "confidence": 0.5
    }

    # Look for employee IDs (various formats)
    employee_id_patterns = [
        r'\b[A-Z]{2,4}\d{2,4}\b',  # ABC123, XYZ1234, etc.
        r'\bEMP\d{2,4}\b',         # EMP123, EMP1234
        r'\b[A-Z]+\d+[A-Z]*\b'    # Generic alphanumeric IDs
    ]

    for pattern in employee_id_patterns:
        matches = re.findall(pattern, query, re.IGNORECASE)
        if matches:
            parsed["parameters"]["employee_id"] = matches[0]
            break

    # Look for names
    name_pattern = r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b'
    name_matches = re.findall(name_pattern, query)
    if name_matches:
        parsed["parameters"]["name"] = name_matches[0]

    # Check for self-referential queries
    self_indicators = [r'\bmy\b', r'\bi\s+', r'\bme\b']
    if any(re.search(indicator, query.lower()) for indicator in self_indicators):
        if requester_id:
            parsed["parameters"]["employee_id"] = requester_id
            parsed["parameters"]["is_self_query"] = True

    # Determine intent based on keywords
    if any(word in query.lower() for word in ['salary', 'pay', 'compensation']):
        parsed["intent"] = "get_salary_info"
        parsed["data_requested"].append("salary")
    elif any(word in query.lower() for word in ['leave', 'balance', 'vacation']):
        parsed["intent"] = "get_leave_balance"
        parsed["data_requested"].append("leave_balance")
    elif any(word in query.lower() for word in ['find', 'search', 'list']):
        parsed["intent"] = "search_employees"

    return parsed


def _get_requester_info(requester_id: str) -> Optional[Dict[str, Any]]:
    """Get requester information for access control"""
    if not requester_id or not mongodb_service:
        return None

    try:
        requester_data = mongodb_service.get_employee_by_id(requester_id)
        if not requester_data:
            logger.warning(f"Requester {requester_id} not found")
            return None

        # Extract relevant info for access control
        employee_info = requester_data.get("employeeInfo", [{}])[0]

        return {
            "employee_id": requester_id,
            "grade": employee_info.get("grade", "L4"),
            "role": requester_data.get("role", ""),
            "department": employee_info.get("depName", ""),
            "team_members": mongodb_service.get_employee_team_members(requester_id) if hasattr(mongodb_service, 'get_employee_team_members') else []
        }

    except Exception as e:
        logger.error(f"Error getting requester info: {str(e)}")
        return None


def _execute_search_with_fallbacks(parsed_query: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Execute search using available methods with fallbacks"""
    parameters = parsed_query["parameters"]

    try:
        # Try direct employee ID lookup first
        if parameters.get("employee_id"):
            employee = mongodb_service.get_employee_by_id(
                parameters["employee_id"])
            if employee:
                return [employee]

        # Try vector search if available
        if VECTOR_SEARCH_AVAILABLE and vector_search_service:
            try:
                results = vector_search_service.semantic_search_employees(
                    parsed_query["original_query"]
                )
                if results:
                    return results
            except Exception as e:
                logger.warning(f"Vector search failed, falling back: {str(e)}")

        # Try criteria search
        if hasattr(mongodb_service, 'search_employees_by_criteria'):
            criteria = {}
            if parameters.get("name"):
                criteria["name"] = parameters["name"]
            if parameters.get("department"):
                criteria["department"] = parameters["department"]
            if parameters.get("role"):
                criteria["role"] = parameters["role"]

            if criteria:
                results = mongodb_service.search_employees_by_criteria(
                    criteria)
                if results:
                    return results

        # Fallback to text search
        if hasattr(mongodb_service, 'search_employees_by_text'):
            return mongodb_service.search_employees_by_text(
                parsed_query["original_query"]
            )

        return []

    except Exception as e:
        logger.error(f"Error executing search: {str(e)}")
        return []


def _can_access_employee(requester_info: Dict[str, Any], target_employee: Dict[str, Any]) -> bool:
    """Check if requester can access target employee's data"""
    if not ACCESS_CONTROL_AVAILABLE:
        # Basic fallback - only allow self-access
        requester_id = requester_info["employee_id"]
        target_id = target_employee.get("userName") or target_employee.get(
            "employeeInfo", [{}])[0].get("empId")
        return requester_id == target_id

    target_id = target_employee.get("userName") or target_employee.get(
        "employeeInfo", [{}])[0].get("empId")

    return AccessControlMatrix.can_access_employee(
        requester_grade=requester_info["grade"],
        requester_role=requester_info["role"],
        requester_id=requester_info["employee_id"],
        target_employee_id=target_id,
        requester_team_members=requester_info.get("team_members", [])
    )


def _filter_employee_data(requester_info: Dict[str, Any], employee_data: Dict[str, Any],
                          data_requested: List[str]) -> Dict[str, Any]:
    """Filter employee data based on access permissions"""

    if ACCESS_CONTROL_AVAILABLE:
        # Use full access control filtering
        filtered_data = AccessControlMatrix.filter_employee_data(
            requester_grade=requester_info["grade"],
            requester_role=requester_info["role"],
            employee_data=employee_data
        )
    else:
        # Basic filtering - only show safe fields
        filtered_data = {
            "_id": employee_data.get("_id"),
            "firstName": employee_data.get("firstName"),
            "lastName": employee_data.get("lastName"),
            "userName": employee_data.get("userName"),
            "employeeInfo": employee_data.get("employeeInfo"),
            "role": employee_data.get("role")
        }

        # Only show sensitive data for self-access
        requester_id = requester_info["employee_id"]
        target_id = employee_data.get("userName") or employee_data.get(
            "employeeInfo", [{}])[0].get("empId")

        if requester_id == target_id:
            # Self-access - show more data
            for field in ["salaryInfo", "leaveBalance", "email", "phoneNumber"]:
                if field in employee_data:
                    filtered_data[field] = employee_data[field]

    return filtered_data


def _format_response_simple(parsed_query: Dict[str, Any], results: List[Dict[str, Any]]) -> str:
    """Simple response formatting"""
    if not results:
        return "No employees found matching your criteria."

    if len(results) == 1:
        employee = results[0]
        name = f"{employee.get('firstName', '')} {employee.get('lastName', '')}".strip(
        )
        emp_id = employee.get("userName") or employee.get(
            "employeeInfo", [{}])[0].get("empId", "")

        response = f"**Employee Information for {name} ({emp_id})**\n\n"

        # Add employee info
        if "employeeInfo" in employee and employee["employeeInfo"]:
            emp_info = employee["employeeInfo"][0]
            response += f"👤 **Basic Information:**\n"
            response += f"• Employee ID: {emp_info.get('empId', 'N/A')}\n"
            response += f"• Department: {emp_info.get('depName', 'N/A')}\n"
            response += f"• Designation: {emp_info.get('designation', 'N/A')}\n"
            response += f"• Grade: {emp_info.get('grade', 'N/A')}\n"

        # Add salary info if available
        if "salaryInfo" in employee:
            salary_info = employee["salaryInfo"]
            response += f"\n💰 **Salary Information:**\n"
            response += f"• Base Salary: {salary_info.get('baseSalary', 'N/A')} {salary_info.get('currency', '')}\n"

        # Add leave info if available
        if "leaveBalance" in employee:
            leave_balance = employee["leaveBalance"]
            response += f"\n🏖️ **Leave Balance:**\n"
            if "annualLeave" in leave_balance:
                al = leave_balance["annualLeave"]
                response += f"• Annual Leave: {al.get('remaining', 0)} days remaining\n"

        return response
    else:
        response = f"**Found {len(results)} employees:**\n\n"
        for i, employee in enumerate(results[:5], 1):
            name = f"{employee.get('firstName', '')} {employee.get('lastName', '')}".strip(
            )
            emp_id = employee.get("userName") or employee.get(
                "employeeInfo", [{}])[0].get("empId", "")

            if "employeeInfo" in employee and employee["employeeInfo"]:
                emp_info = employee["employeeInfo"][0]
                dept = emp_info.get("depName", "N/A")
                designation = emp_info.get("designation", "N/A")
                response += f"{i}. **{name}** ({emp_id}) - {designation}, {dept}\n"
            else:
                response += f"{i}. **{name}** ({emp_id})\n"

        if len(results) > 5:
            response += f"\n... and {len(results) - 5} more employees.\n"

        return response


# Create the LangChain tool
get_employee_data = Tool(
    name="get_employee_data",
    description="""Employee data retrieval using natural language queries with automatic access control.
    Examples: 
    - "show me EMP103 salary details"
    - "get John Smith's information" 
    - "what is my leave balance?"
    - "find software engineers"
    - "show me QTG103 employee information"
    
    The tool automatically handles different employee ID formats and applies security controls.""",
    func=get_employee_data_tool
)

# Additional utility function (simplified version)


def search_similar_employees_tool(employee_id: str, requester_id: str) -> Dict[str, Any]:
    """Find employees similar to a given employee (simplified version)"""
    try:
        if not initialize_services():
            return {"success": False, "message": "Service initialization failed"}

        # Get requester info for access control
        requester_info = _get_requester_info(requester_id)
        if not requester_info:
            return {"success": False, "message": "Access verification failed"}

        # Get the reference employee
        reference_employee = mongodb_service.get_employee_by_id(employee_id)
        if not reference_employee:
            return {"success": False, "message": f"Employee {employee_id} not found"}

        # Use vector search if available, otherwise use criteria-based similarity
        similar_employees = []

        if VECTOR_SEARCH_AVAILABLE and vector_search_service:
            try:
                similar_employees = vector_search_service.search_similar_employees(
                    employee_id)
            except Exception as e:
                logger.warning(f"Vector similarity search failed: {str(e)}")

        # Fallback to criteria-based similarity
        if not similar_employees and hasattr(mongodb_service, 'search_employees_by_criteria'):
            criteria = {}
            if "employeeInfo" in reference_employee and reference_employee["employeeInfo"]:
                emp_info = reference_employee["employeeInfo"][0]
                if "depName" in emp_info:
                    criteria["department"] = emp_info["depName"]
                if "grade" in emp_info:
                    criteria["grade"] = emp_info["grade"]

            if criteria:
                similar_employees = mongodb_service.search_employees_by_criteria(
                    criteria, limit=5)
                # Filter out the reference employee
                similar_employees = [
                    emp for emp in similar_employees if emp.get("userName") != employee_id]

        # Apply access control
        filtered_results = []
        for employee in similar_employees:
            if _can_access_employee(requester_info, employee):
                filtered_data = _filter_employee_data(
                    requester_info, employee, []
                )
                filtered_results.append(filtered_data)

        return {
            "success": True,
            "data": filtered_results,
            "message": f"Found {len(filtered_results)} similar employees"
        }

    except Exception as e:
        logger.error(f"Error finding similar employees: {str(e)}")
        return {"success": False, "message": str(e)}


# Create similar employees tool
find_similar_employees = Tool(
    name="find_similar_employees",
    description="Find employees with similar profiles to a given employee ID",
    func=lambda employee_id: search_similar_employees_tool(employee_id, None)
)
