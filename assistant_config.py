ASSISTANT_FUNCTIONS = [
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
        "description": "Get attendance records based on employee grade and date range",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {
                    "type": "string",
                    "description": "The employee ID (e.g., EMP103)"
                },
                "date_type": {
                    "type": "string", 
                    "description": "Type of date range - 'today', 'recent', 'this_month', a specific date 'YYYY-MM-DD', or month_MM_YYYY for a specific month",
                    "enum": ["today", "recent", "this_month", "month_01_2025", "month_02_2025", "month_03_2025", "month_04_2025"],
                    "default": "recent"
                },
                "include_team": {
                    "type": "boolean",
                    "description": "Override to include team data (if not provided, auto-detect based on grade)",
                    "default": null
                }
            },
            "required": ["employee_id"]
        }
    }},
    {"type": "function", "function": {
        "name": "get_personal_attendance",
        "description": "Get attendance records for a specific employee",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {
                    "type": "string",
                    "description": "The employee ID (e.g., EMP103)"
                },
                "date_type": {
                    "type": "string", 
                    "description": "Type of date range - 'today', 'recent', 'this_month', a specific date 'YYYY-MM-DD', or month_MM_YYYY for a specific month",
                    "enum": ["today", "recent", "this_month", "month_01_2025", "month_02_2025", "month_03_2025", "month_04_2025"],
                    "default": "recent"
                }
            },
            "required": ["employee_id"]
        }
    }},
    {"type": "function", "function": {
        "name": "get_team_attendance",
        "description": "Get attendance records for a manager's team",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {
                    "type": "string",
                    "description": "The employee ID of the manager (e.g., EMP103)"
                },
                "date_type": {
                    "type": "string", 
                    "description": "Type of date range - 'today', 'recent', 'this_month', a specific date 'YYYY-MM-DD', or month_MM_YYYY for a specific month",
                    "enum": ["today", "recent", "this_month", "month_01_2025", "month_02_2025", "month_03_2025", "month_04_2025"],
                    "default": "recent"
                }
            },
            "required": ["employee_id"]
        }
    }},
    {"type": "function", "function": {
        "name": "get_team_data",
        "description": "Get team members data for a manager",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {
                    "type": "string",
                    "description": "The employee ID of the manager (e.g., EMP103)"
                }
            },
            "required": ["employee_id"]
        }
    }}
]
ASSISTANT_INSTRUCTIONS = """
You are an HR Assistant that helps employees with HR-related queries.

## Greeting and Personalization
- Always start with a time-appropriate greeting (Good morning/afternoon/evening) followed by the employee's name
- Be professional yet friendly in your communication

## Attendance Functionality
When responding to attendance queries, follow these guidelines:

1. Determine the appropriate function to call based on employee grade and query:
   - For employees with grade L4, use get_personal_attendance to fetch their own attendance
   - For employees with grades L0, L1, L2, or L3 (managers/supervisors), use get_team_attendance to fetch team attendance
   - When in doubt about which function to use, use get_attendance which automatically determines the appropriate data to fetch

2. Determine the correct date_type parameter based on the query:
   - For "recent attendance" or "last week": use "recent" (covers last 7 days)
   - For "today's attendance": use "today"
   - For "this month's attendance": use "this_month"
   - For specific date: use date in format "YYYY-MM-DD"
   - For specific month: use "month_MM_YYYY" format (e.g., "month_04_2025" for April 2025)

3. Format attendance data clearly in your response:
   - For personal attendance: Summarize data by date, status, and hours worked
   - For team attendance: Group by team member, then summarize their attendance patterns

## Response Guidelines
- Keep responses concise and focused on the employee's query
- Format attendance data in an easily readable format
- For queries you can't answer, politely offer to redirect to HR department

Remember to be responsive, accurate, and helpful in all your interactions.
"""