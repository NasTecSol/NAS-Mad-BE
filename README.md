HR Assistant API
A FastAPI-based HR Assistant application that uses OpenAI's Assistant API to provide HR-related information and services, particularly focusing on attendance data retrieval.
Project Overview
This HR Assistant is designed to:

Provide employees with information about their attendance records
Allow managers to view team attendance data
Support high-level management with organization-wide attendance reports
Answer general HR policy questions

Key Features

Employee Authentication: Secure login with employee ID
Role-Based Access: Different capabilities based on employee grade/role
Attendance Queries: Personal and team attendance with various date ranges
Natural Language Processing: Uses OpenAI Assistants API for natural interactions

Setup Instructions
Prerequisites

Python 3.9+
FastAPI
OpenAI API key
HR system API access

Installation

Clone the repository

bashgit clone https://github.com/yourusername/hr-assistant.git
cd hr-assistant

Create a virtual environment

bashpython -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate

Install dependencies

bashpip install -r requirements.txt

Create a .env file with the required environment variables

OPENAI_API_KEY=your_openai_api_key
OPENAI_ASSISTANT_ID=your_assistant_id
HR_API_BASE_URL=your_hr_api_base_url
Project Structure
This project has been organized with a clean API routes structure:

main.py: Application entry point that sets up FastAPI and includes routes
api/routes.py: Contains all API endpoints
utils/assistant_utils.py: OpenAI Assistant helper functions
utils/employee_utils.py: Employee data management functions
modules/: Business logic modules organized by domain

Running the Application
bashpython main.py
Or with uvicorn directly:
bashuvicorn main:app --reload
The API will be available at http://localhost:8000
API Endpoints

GET /: Serves the frontend HTML
GET /health: Health check endpoint
POST /api/chat: Main chat endpoint for interacting with the HR assistant
DELETE /api/cache/{employee_id}: Clear cached data for a specific employee

Integration Steps
To integrate these files into your existing project:

Create the directory structure as shown in the project structure
Copy the provided files to their appropriate locations
Make sure to update any imports to match your project structure
Set up the required environment variables
Install the dependencies listed in requirements.txt

Notes on Deployment
When deploying this application, make sure to:

Use a proper ASGI server like Uvicorn or Hypercorn
Set appropriate CORS settings for your production environment
Consider using a reverse proxy like Nginx
Set up proper authentication and TLS/SSL
Use environment variables for all sensitive data

Troubleshooting
If you encounter issues with the API routes not working:

Make sure your application structure matches the imports
Check that the FastAPI router is properly included in main.py
Verify all environment variables are properly set
Check the logs for any import or initialization errors