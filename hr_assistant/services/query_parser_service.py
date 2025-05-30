# services/query_parser_service.py
import re
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from utils.logger import logger


class QueryIntent(Enum):
    """Types of queries the system can handle"""
    GET_EMPLOYEE_INFO = "get_employee_info"
    GET_SALARY_INFO = "get_salary_info"
    GET_LEAVE_BALANCE = "get_leave_balance"
    GET_CONTACT_INFO = "get_contact_info"
    GET_DEPARTMENT_INFO = "get_department_info"
    SEARCH_EMPLOYEES = "search_employees"
    GET_PROFILE_SUMMARY = "get_profile_summary"
    UNKNOWN = "unknown"


class QueryParserService:
    """Service for parsing and understanding natural language queries"""

    def __init__(self):
        # Try to import OpenAI for advanced parsing
        self.openai_client = None
        self.use_ai_parsing = False

        try:
            import openai
            import os
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.openai_client = openai.OpenAI(api_key=api_key)
                self.use_ai_parsing = True
                logger.info("OpenAI available for enhanced query parsing")
        except Exception as e:
            logger.info(
                f"OpenAI not available for query parsing, using rule-based parsing: {str(e)}")

        # Define patterns for different query types
        self.intent_patterns = {
            QueryIntent.GET_SALARY_INFO: [
                r'\b(salary|pay|compensation|wage|income)\b',
                r'\b(allowance|bonus|deduction)\b',
                r'\b(basic\s+salary|net\s+salary)\b'
            ],
            QueryIntent.GET_LEAVE_BALANCE: [
                r'\b(leave|vacation|holiday)\s+(balance|remaining|left)\b',
                r'\b(annual\s+leave|sick\s+leave|casual\s+leave)\b',
                r'\b(how\s+many\s+leaves?)\b'
            ],
            QueryIntent.GET_CONTACT_INFO: [
                r'\b(contact|phone|email|address)\b',
                r'\b(mobile|telephone|landline)\b'
            ],
            QueryIntent.GET_DEPARTMENT_INFO: [
                r'\b(department|dept|division|team)\b',
                r'\b(manager|supervisor|reporting)\b'
            ],
            QueryIntent.SEARCH_EMPLOYEES: [
                r'\b(find|search|show\s+me|get\s+me)\b.*\b(employee|staff|person|people)\b',
                r'\b(who\s+is|who\s+are)\b',
                r'\b(list\s+of|all\s+employees)\b'
            ]
        }

        # Employee ID patterns for different formats
        self.employee_id_patterns = [
            r'\b[A-Z]{2,4}\d{2,4}\b',  # ABC123, XYZ1234, etc.
            r'\bEMP\d{2,4}\b',         # EMP123, EMP1234
            r'\b[A-Z]+\d+[A-Z]*\b'    # Generic alphanumeric IDs
        ]

    def parse_query(self, query: str, requester_id: str = None) -> Dict[str, Any]:
        """
        Parse a natural language query and extract intent and parameters
        """
        try:
            query_lower = query.lower().strip()

            # Extract basic parameters
            parameters = self._extract_parameters(query)

            # Determine intent
            intent = self._determine_intent(query_lower)

            # Handle self-referential queries
            if self._is_self_query(query_lower) and requester_id:
                parameters["employee_id"] = requester_id
                parameters["is_self_query"] = True

            # Extract specific data requests
            data_requested = self._extract_data_requests(query_lower)

            return {
                "original_query": query,
                "intent": intent,
                "parameters": parameters,
                "data_requested": data_requested,
                "confidence": self._calculate_confidence(query, intent, parameters)
            }

        except Exception as e:
            logger.error(f"Error parsing query '{query}': {str(e)}")
            return {
                "original_query": query,
                "intent": QueryIntent.UNKNOWN,
                "parameters": {},
                "data_requested": [],
                "confidence": 0.0
            }

    def _extract_parameters(self, query: str) -> Dict[str, Any]:
        """Extract various parameters from the query"""
        parameters = {}

        # Extract employee IDs
        employee_ids = self._extract_employee_ids(query)
        if employee_ids:
            parameters["employee_id"] = employee_ids[0]  # Take the first one
            if len(employee_ids) > 1:
                parameters["additional_employee_ids"] = employee_ids[1:]

        # Extract names
        names = self._extract_names(query)
        if names:
            parameters["name"] = names[0]
            if len(names) > 1:
                parameters["additional_names"] = names[1:]

        # Extract departments
        departments = self._extract_departments(query)
        if departments:
            parameters["department"] = departments[0]

        # Extract roles/positions
        roles = self._extract_roles(query)
        if roles:
            parameters["role"] = roles[0]

        # Extract grades
        grades = self._extract_grades(query)
        if grades:
            parameters["grade"] = grades[0]

        return parameters

    def _extract_employee_ids(self, query: str) -> List[str]:
        """Extract employee IDs from query"""
        employee_ids = []

        for pattern in self.employee_id_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            employee_ids.extend(matches)

        # Remove duplicates while preserving order
        return list(dict.fromkeys(employee_ids))

    def _extract_names(self, query: str) -> List[str]:
        """Extract person names from query"""
        names = []

        # Pattern for names (capitalized words, potentially with common name prefixes)
        name_patterns = [
            r'\b(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
            r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b',  # First Last
            # "employee John Smith"
            r'employee\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            # "for John Smith"
            r'(?:for|of|about)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        ]

        for pattern in name_patterns:
            matches = re.findall(pattern, query)
            names.extend(matches)

        # Filter out common false positives
        excluded_words = {'Software', 'Engineer', 'Manager',
                          'Director', 'Department', 'Team', 'Employee'}
        names = [name for name in names if not any(
            word in name for word in excluded_words)]

        return list(dict.fromkeys(names))

    def _extract_departments(self, query: str) -> List[str]:
        """Extract department names from query"""
        departments = []

        # Common department patterns
        dept_patterns = [
            r'\b(engineering|hr|human\s+resources|finance|marketing|sales|it|operations|legal)\b',
            r'from\s+(the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+department',
            r'in\s+(the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+department',
            r'department\s+of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
        ]

        for pattern in dept_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            if matches and isinstance(matches[0], tuple):
                departments.extend([match[-1]
                                   for match in matches if match[-1]])
            else:
                departments.extend(matches)

        return list(dict.fromkeys(departments))

    def _extract_roles(self, query: str) -> List[str]:
        """Extract roles/positions from query"""
        roles = []

        role_patterns = [
            r'\b(manager|director|supervisor|lead|senior|junior|analyst|developer|engineer|specialist|coordinator|executive|admin|administrator)\b',
            r'role\s+of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'position\s+of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'
        ]

        for pattern in role_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            roles.extend(matches)

        return list(dict.fromkeys(roles))

    def _extract_grades(self, query: str) -> List[str]:
        """Extract grades from query"""
        grade_pattern = r'\b(L[0-4]|level\s+[0-4])\b'
        matches = re.findall(grade_pattern, query, re.IGNORECASE)

        # Normalize to L0-L4 format
        normalized_grades = []
        for match in matches:
            if match.startswith('level'):
                normalized_grades.append(f"L{match.split()[-1]}")
            else:
                normalized_grades.append(match.upper())

        return normalized_grades

    def _determine_intent(self, query_lower: str) -> QueryIntent:
        """Determine the intent of the query"""
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return intent

        # Default to getting employee info if we have identifiable parameters
        if any(keyword in query_lower for keyword in ['employee', 'information', 'details', 'profile']):
            return QueryIntent.GET_EMPLOYEE_INFO

        return QueryIntent.UNKNOWN

    def _is_self_query(self, query_lower: str) -> bool:
        """Check if the query is asking about the requester's own information"""
        self_indicators = [
            r'\bmy\b', r'\bi\s+', r'\bme\b', r'\bmyself\b',
            r'\bdo\s+i\b', r'\bam\s+i\b', r'\bwhat\s+is\s+my\b'
        ]

        return any(re.search(indicator, query_lower) for indicator in self_indicators)

    def _extract_data_requests(self, query_lower: str) -> List[str]:
        """Extract specific types of data being requested"""
        data_requests = []

        data_patterns = {
            "salary": [r'\b(salary|pay|compensation|wage|income)\b'],
            "leave_balance": [r'\b(leave|vacation|holiday)\s+(balance|remaining|left)\b'],
            "contact_info": [r'\b(contact|phone|email|address)\b'],
            "basic_info": [r'\b(name|id|department|position|role|grade)\b'],
            "banking_info": [r'\b(bank|account|banking)\b'],
            "family_info": [r'\b(family|emergency|contact)\b'],
            "contract_info": [r'\b(contract|employment|hire|joining)\b']
        }

        for data_type, patterns in data_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    data_requests.append(data_type)
                    break

        return data_requests

    def _calculate_confidence(self, query: str, intent: QueryIntent, parameters: Dict[str, Any]) -> float:
        """Calculate confidence score for the parsed query"""
        confidence = 0.0

        # Base confidence based on intent recognition
        if intent != QueryIntent.UNKNOWN:
            confidence += 0.3

        # Increase confidence based on extracted parameters
        if parameters.get("employee_id"):
            confidence += 0.4
        elif parameters.get("name"):
            confidence += 0.3

        if parameters.get("department"):
            confidence += 0.1

        if parameters.get("role"):
            confidence += 0.1

        # Increase confidence for clear, structured queries
        if len(query.split()) >= 3:
            confidence += 0.1

        return min(confidence, 1.0)

    def get_search_strategy(self, parsed_query: Dict[str, Any]) -> str:
        """Determine the best search strategy based on parsed query"""
        parameters = parsed_query["parameters"]

        # If we have a specific employee ID, use direct lookup
        if parameters.get("employee_id"):
            return "direct_lookup"

        # If we have name and department, use criteria search
        if parameters.get("name") and parameters.get("department"):
            return "criteria_search"

        # If we have multiple specific criteria, use criteria search
        criteria_count = sum(
            1 for key in ["name", "department", "role", "grade"] if parameters.get(key))
        if criteria_count >= 2:
            return "criteria_search"

        # For general queries or single criteria, use vector search
        return "vector_search"
