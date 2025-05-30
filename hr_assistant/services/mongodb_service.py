import os
from typing import Dict, Any, List, Optional
from utils.logger import logger

# Try to import MongoDB dependencies
try:
    from pymongo import MongoClient
    from pymongo.collection import Collection
    from pymongo.database import Database
    MONGODB_AVAILABLE = True
except ImportError:
    logger.error("pymongo not installed. Install with: pip install pymongo")
    MONGODB_AVAILABLE = False


class MongoDBService:
    """Service for MongoDB operations with fallback functionality"""

    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.database: Optional[Database] = None
        self.employees_collection: Optional[Collection] = None

        if MONGODB_AVAILABLE:
            self._connect()
        else:
            logger.error("MongoDB dependencies not available")

    def _connect(self):
        """Establish connection to MongoDB"""
        try:
            # Get MongoDB connection details from environment
            mongo_uri = os.getenv('MONGODB_URI')
            if not mongo_uri:
                # Fallback to individual components
                mongo_host = os.getenv('MONGODB_HOST', 'localhost')
                mongo_port = os.getenv('MONGODB_PORT', '27017')
                mongo_user = os.getenv('MONGODB_USER')
                mongo_password = os.getenv('MONGODB_PASSWORD')

                if mongo_user and mongo_password:
                    mongo_uri = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}"
                else:
                    mongo_uri = f"mongodb://{mongo_host}:{mongo_port}"

            self.client = MongoClient(mongo_uri)
            self.database = self.client[os.getenv(
                'MONGODB_DATABASE', 'nas_hr')]
            self.employees_collection = self.database[os.getenv(
                'MONGODB_COLLECTION', 'employees')]

            # Test connection
            self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")

        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            # Don't raise exception - let the app start with limited functionality
            self.client = None
            self.database = None
            self.employees_collection = None

    def is_connected(self) -> bool:
        """Check if MongoDB is connected"""
        return self.employees_collection is not None

    def get_employee_by_id(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """Get employee by exact ID match"""
        if not self.is_connected():
            logger.error("MongoDB not connected")
            return None

        try:
            # Search in multiple possible ID fields
            query = {
                "$or": [
                    {"userName": employee_id},
                    {"employeeInfo.empId": employee_id},
                    {"_id": employee_id}
                ]
            }

            result = self.employees_collection.find_one(query)
            if result:
                logger.info(f"Found employee by ID: {employee_id}")
                return result
            else:
                logger.warning(f"No employee found with ID: {employee_id}")
                return None

        except Exception as e:
            logger.error(
                f"Error searching for employee by ID {employee_id}: {str(e)}")
            return None

    def search_employees_by_text(self, search_text: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search employees using text search"""
        if not self.is_connected():
            logger.error("MongoDB not connected")
            return []

        try:
            # Try text search first
            try:
                query = {"$text": {"$search": search_text}}
                results = list(
                    self.employees_collection.find(query).limit(limit))
                if results:
                    logger.info(
                        f"Text search for '{search_text}' returned {len(results)} results")
                    return results
            except Exception:
                # Text index might not exist, fall back to regex search
                pass

            # Fallback to regex search on common fields
            regex_query = {
                "$or": [
                    {"firstName": {"$regex": search_text, "$options": "i"}},
                    {"lastName": {"$regex": search_text, "$options": "i"}},
                    {"userName": {"$regex": search_text, "$options": "i"}},
                    {"role": {"$regex": search_text, "$options": "i"}},
                    {"employeeInfo.depName": {"$regex": search_text, "$options": "i"}},
                    {"employeeInfo.designation": {
                        "$regex": search_text, "$options": "i"}}
                ]
            }

            results = list(self.employees_collection.find(
                regex_query).limit(limit))
            logger.info(
                f"Regex search for '{search_text}' returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Error in text search for '{search_text}': {str(e)}")
            return []

    def search_employees_by_criteria(self, criteria: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
        """Search employees by specific criteria"""
        if not self.is_connected():
            logger.error("MongoDB not connected")
            return []

        try:
            # Build query based on criteria
            query = {}

            if "name" in criteria:
                name_parts = criteria["name"].split()
                if len(name_parts) == 1:
                    # Single name - could be first or last name
                    query["$or"] = [
                        {"firstName": {
                            "$regex": criteria["name"], "$options": "i"}},
                        {"lastName": {
                            "$regex": criteria["name"], "$options": "i"}}
                    ]
                elif len(name_parts) >= 2:
                    # Multiple parts - treat as first and last name
                    query["$and"] = [
                        {"firstName": {
                            "$regex": name_parts[0], "$options": "i"}},
                        {"lastName": {
                            "$regex": name_parts[-1], "$options": "i"}}
                    ]

            if "department" in criteria:
                query["employeeInfo.depName"] = {
                    "$regex": criteria["department"], "$options": "i"}

            if "role" in criteria:
                query["role"] = {"$regex": criteria["role"], "$options": "i"}

            if "grade" in criteria:
                query["employeeInfo.grade"] = criteria["grade"]

            if "employee_id" in criteria:
                query["$or"] = [
                    {"userName": criteria["employee_id"]},
                    {"employeeInfo.empId": criteria["employee_id"]}
                ]

            results = list(self.employees_collection.find(query).limit(limit))
            logger.info(f"Criteria search returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Error in criteria search: {str(e)}")
            return []

    def get_employee_team_members(self, manager_id: str) -> List[str]:
        """Get list of team member IDs for a manager"""
        if not self.is_connected():
            return []

        try:
            # Find employees who report to this manager
            query = {"employeeInfo.reportingManager": manager_id}
            results = self.employees_collection.find(
                query, {"userName": 1, "employeeInfo.empId": 1})

            team_member_ids = []
            for emp in results:
                # Get the employee ID from userName or empId
                emp_id = emp.get("userName") or emp.get(
                    "employeeInfo", [{}])[0].get("empId")
                if emp_id:
                    team_member_ids.append(emp_id)

            logger.info(
                f"Found {len(team_member_ids)} team members for manager {manager_id}")
            return team_member_ids

        except Exception as e:
            logger.error(
                f"Error getting team members for manager {manager_id}: {str(e)}")
            return []

    def close_connection(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
