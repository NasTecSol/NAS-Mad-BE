# services/vector_search_service.py
from typing import Dict, Any, List, Optional
from utils.logger import logger

# Try to import OpenAI
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    logger.warning(
        "OpenAI not available. Vector search will use fallback methods.")
    OPENAI_AVAILABLE = False


class VectorSearchService:
    """Service for vector-based semantic search with fallback to text search"""

    def __init__(self, mongodb_service):
        self.mongodb_service = mongodb_service
        self.openai_client = None
        self.vector_index_name = "employee_vector_index"
        self.openai_working = False

        if OPENAI_AVAILABLE:
            self._initialize_openai_client()
        else:
            logger.info(
                "OpenAI not available, will use fallback search methods")

    def _initialize_openai_client(self):
        """Initialize OpenAI client with error handling"""
        try:
            import os
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.warning("OPENAI_API_KEY not found in environment")
                return

            # Try different initialization methods
            try:
                self.openai_client = openai.OpenAI(api_key=api_key)
                # Test the connection
                test_response = self.openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input="test"
                )
                if test_response and test_response.data:
                    self.openai_working = True
                    logger.info(
                        "OpenAI client initialized and tested successfully")

            except Exception as e:
                logger.warning(
                    f"OpenAI client initialization failed: {str(e)}")
                # Try legacy method
                try:
                    openai.api_key = api_key
                    self.openai_client = openai
                    logger.info("OpenAI initialized with legacy method")
                except Exception as e2:
                    logger.warning(
                        f"Legacy OpenAI initialization also failed: {str(e2)}")

        except Exception as e:
            logger.error(f"Failed to initialize OpenAI: {str(e)}")
            self.openai_client = None

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI with fallback"""
        if not self.openai_client or not self.openai_working:
            return []

        try:
            if hasattr(self.openai_client, 'embeddings'):
                response = self.openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text
                )
                return response.data[0].embedding
            elif hasattr(self.openai_client, 'Embedding'):
                response = self.openai_client.Embedding.create(
                    model="text-embedding-3-small",
                    input=text
                )
                return response['data'][0]['embedding']
            else:
                return []

        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            self.openai_working = False
            return []

    def semantic_search_employees(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Perform semantic search with fallback to text search
        """
        try:
            # Try vector search if OpenAI is working
            if self.openai_working and self.openai_client:
                query_embedding = self._generate_embedding(query)
                if query_embedding:
                    # Try MongoDB Atlas Vector Search
                    try:
                        pipeline = [
                            {
                                "$vectorSearch": {
                                    "index": self.vector_index_name,
                                    "path": "embedding",
                                    "queryVector": query_embedding,
                                    "numCandidates": limit * 2,
                                    "limit": limit
                                }
                            },
                            {
                                "$addFields": {
                                    "score": {"$meta": "vectorSearchScore"}
                                }
                            }
                        ]

                        results = list(
                            self.mongodb_service.employees_collection.aggregate(pipeline))

                        if results:
                            logger.info(
                                f"Vector search for '{query}' returned {len(results)} results")
                            return results

                    except Exception as e:
                        logger.warning(f"Vector search failed: {str(e)}")

            # Fallback to text search
            logger.info(f"Using fallback text search for: {query}")
            return self.mongodb_service.search_employees_by_text(query, limit)

        except Exception as e:
            logger.error(f"Error in semantic search for '{query}': {str(e)}")
            # Final fallback
            return self.mongodb_service.search_employees_by_text(query, limit)

    def search_similar_employees(self, employee_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Find employees similar to a given employee"""
        try:
            # Get the reference employee
            reference_employee = self.mongodb_service.get_employee_by_id(
                employee_id)
            if not reference_employee:
                logger.warning(f"Reference employee {employee_id} not found")
                return []

            # Try vector search if embedding exists
            reference_embedding = reference_employee.get("embedding")
            if reference_embedding and self.openai_working:
                try:
                    pipeline = [
                        {
                            "$vectorSearch": {
                                "index": self.vector_index_name,
                                "path": "embedding",
                                "queryVector": reference_embedding,
                                "numCandidates": limit * 2,
                                "limit": limit + 1
                            }
                        },
                        {
                            "$addFields": {
                                "score": {"$meta": "vectorSearchScore"}
                            }
                        },
                        {
                            "$match": {
                                "userName": {"$ne": employee_id}
                            }
                        },
                        {
                            "$limit": limit
                        }
                    ]

                    results = list(
                        self.mongodb_service.employees_collection.aggregate(pipeline))
                    if results:
                        logger.info(
                            f"Found {len(results)} similar employees to {employee_id}")
                        return results

                except Exception as e:
                    logger.warning(
                        f"Vector similarity search failed: {str(e)}")

            # Fallback to criteria-based similarity
            return self._criteria_similar_search(reference_employee, limit)

        except Exception as e:
            logger.error(
                f"Error finding similar employees to {employee_id}: {str(e)}")
            return []

    def _criteria_similar_search(self, reference_employee: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        """Fallback similar search using criteria matching"""
        try:
            criteria = {}

            # Extract similar criteria
            if "employeeInfo" in reference_employee and reference_employee["employeeInfo"]:
                emp_info = reference_employee["employeeInfo"][0]
                if "depName" in emp_info:
                    criteria["department"] = emp_info["depName"]
                if "grade" in emp_info:
                    criteria["grade"] = emp_info["grade"]

            if "role" in reference_employee:
                criteria["role"] = reference_employee["role"]

            # Search using criteria
            results = self.mongodb_service.search_employees_by_criteria(
                criteria, limit + 1)

            # Filter out the reference employee
            ref_id = reference_employee.get("userName")
            if ref_id:
                results = [emp for emp in results if emp.get(
                    "userName") != ref_id]

            return results[:limit]

        except Exception as e:
            logger.error(f"Error in criteria similar search: {str(e)}")
            return []

    def create_employee_embedding(self, employee_data: Dict[str, Any]) -> List[float]:
        """Create embedding for an employee (only if OpenAI is available)"""
        if not self.openai_working:
            return []

        try:
            # Create searchable text from employee data
            text_parts = []

            # Basic info
            if "firstName" in employee_data:
                text_parts.append(f"Name: {employee_data['firstName']}")
            if "lastName" in employee_data:
                text_parts.append(employee_data["lastName"])

            # Employee info
            if "employeeInfo" in employee_data and employee_data["employeeInfo"]:
                emp_info = employee_data["employeeInfo"][0]
                if "empId" in emp_info:
                    text_parts.append(f"Employee ID: {emp_info['empId']}")
                if "designation" in emp_info:
                    text_parts.append(
                        f"Designation: {emp_info['designation']}")
                if "depName" in emp_info:
                    text_parts.append(f"Department: {emp_info['depName']}")
                if "grade" in emp_info:
                    text_parts.append(f"Grade: {emp_info['grade']}")
                if "jobTitle" in emp_info:
                    text_parts.append(f"Job Title: {emp_info['jobTitle']}")

            # Role
            if "role" in employee_data:
                text_parts.append(f"Role: {employee_data['role']}")

            # Profession
            if "profession" in employee_data:
                text_parts.append(f"Profession: {employee_data['profession']}")

            # Join all parts
            searchable_text = " ".join(text_parts)

            # Generate embedding
            return self._generate_embedding(searchable_text)

        except Exception as e:
            logger.error(f"Error creating employee embedding: {str(e)}")
            return []

    def bulk_update_embeddings(self, batch_size: int = 100) -> int:
        """Update embeddings for employees (only if OpenAI is available)"""
        if not self.openai_working:
            logger.info("OpenAI not available, skipping embedding generation")
            return 0

        try:
            processed_count = 0

            # Get employees without embeddings
            cursor = self.mongodb_service.employees_collection.find(
                {"$or": [{"embedding": {"$exists": False}}, {"embedding": None}]}
            ).batch_size(batch_size)

            for employee in cursor:
                try:
                    embedding = self.create_employee_embedding(employee)
                    if embedding:
                        self.mongodb_service.employees_collection.update_one(
                            {"_id": employee["_id"]},
                            {"$set": {"embedding": embedding}}
                        )
                        processed_count += 1

                        if processed_count % 10 == 0:
                            logger.info(
                                f"Processed {processed_count} employee embeddings")

                        # Limit to prevent rate limiting
                        if processed_count >= batch_size:
                            break

                except Exception as e:
                    logger.error(
                        f"Error processing employee {employee.get('userName', 'unknown')}: {str(e)}")
                    continue

            logger.info(
                f"Bulk embedding update completed. Processed {processed_count} employees")
            return processed_count

        except Exception as e:
            logger.error(f"Error in bulk embedding update: {str(e)}")
            return 0

    def test_openai_connection(self) -> bool:
        """Test OpenAI connection"""
        if not OPENAI_AVAILABLE:
            return False

        try:
            test_embedding = self._generate_embedding("test")
            if test_embedding:
                logger.info("OpenAI connection test successful")
                self.openai_working = True
                return True
            else:
                logger.warning(
                    "OpenAI connection test failed - no embedding generated")
                self.openai_working = False
                return False
        except Exception as e:
            logger.error(f"OpenAI connection test failed: {str(e)}")
            self.openai_working = False
            return False
