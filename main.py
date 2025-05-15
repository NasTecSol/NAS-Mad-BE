import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from api.routes import router as api_router
from api.hr_service import HRService
from utils.logger import logger
from config.settings import settings

import modules.auth as auth_module
import modules.employee as employee_module
import modules.attendance as attendance_module

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
employee_module.initialize(hr_service)
attendance_module.initialize(hr_service)

# Make sure the static directory exists
os.makedirs("static", exist_ok=True)

# Mount the static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API routes
app.include_router(api_router, prefix="/api")


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
    from api.routes import get_cache_stats

    stats = get_cache_stats()

    return {
        "status": "ok",
        "message": "HR Assistant API is running",
        "stats": stats
    }

# Run the application
if __name__ == "__main__":
    import uvicorn

    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=8000)
