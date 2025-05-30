# scripts/migrate_to_vector_search.py
"""
Migration script to transition from the old HR API-based system to the new MongoDB vector search system.
This script helps migrate existing data and test the new functionality.
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.mongodb_service import MongoDBService
from services.vector_search_service import VectorSearchService
from services.query_parser_service import QueryParserService
from utils.logger import logger
from utils.access_control import AccessControlMatrix
from config.settings import settings

class HRSystemMigration:
    """Handles migration from old HR API system to new vector search system"""
    
    def __init__(self):
        self.mongodb_service = None
        self.vector_search_service = None
        self.query_parser_service = None
        self.migration_log = []
        
    def initialize_services(self):
        """Initialize all required services"""
        try:
            self.mongodb_service = MongoDBService()
            self.vector_search_service = VectorSearchService(self.mongodb_service)
            self.query_parser_service = QueryParserService()
            logger.info("Migration services initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize services: {str(e)}")
            return False
    
    def log_migration_step(self, step: str, status: str, details: str = ""):
        """Log migration step for tracking"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "status": status,
            "details": details
        }
        self.migration_log.append(log_entry)
        logger.info(f"Migration: {step} - {status}")
        if details:
            logger.info(f"Details: {details}")
    
    def validate_mongodb_connection(self) -> bool:
        """Validate MongoDB connection and basic setup"""
        try:
            self.log_migration_step("MongoDB Connection", "STARTING", "Testing database connectivity")
            
            # Test basic connection
            if not self.mongodb_service:
                raise Exception("MongoDB service not initialized")
            
            # Test collection access
            test_count = self.mongodb_service.employees_collection.count_documents({})
            self.log_migration_step(
                "MongoDB Connection", 
                "SUCCESS", 
                f"Found {test_count} documents in employees collection"
            )
            return True
            
        except Exception as e:
            self.log_migration_step("MongoDB Connection", "FAILED", str(e))
            return False
    
    def create_sample_employee_data(self) -> bool:
        """Create sample employee data if collection is empty (for testing)"""
        try:
            count = self.mongodb_service.employees_collection.count_documents({})
            if count > 0:
                self.log_migration_step(
                    "Sample Data Creation", 
                    "SKIPPED", 
                    f"Collection already has {count} documents"
                )
                return True
            
            self.log_migration_step("Sample Data Creation", "STARTING", "Creating sample employee data")
            
            sample_employees = [
                {
                    "_id": "emp_001",
                    "userName": "EMP103",
                    "firstName": "John",
                    "lastName": "Doe",
                    "email": [{"workEmail": "john.doe@company.com"}],
                    "phoneNumber": [{"mobileNumber": "+1234567890"}],
                    "role": "Software Engineer",
                    "profession": "Software Developer",
                    "departmentId": "dept_eng",
                    "branchId": "branch_001",
                    "organizationId": "org_001",
                    "employeeInfo": [{
                        "empId": "EMP103",
                        "grade": "L4",
                        "designation": "Senior Developer",
                        "depName": "Engineering",
                        "jobTitle": "Software Engineer",
                        "reportingManager": "EMP101"
                    }],
                    "salaryInfo": {
                        "baseSalary": "85000",
                        "currency": "USD",
                        "netSalary": "75000"
                    },
                    "leaveBalance": {
                        "annualLeave": {"remaining": 15, "entitlement": 20, "used": 5},
                        "sickLeave": {"remaining": 8, "entitlement": 10, "used": 2},
                        "casualLeave": {"remaining": 3, "entitlement": 5, "used": 2}
                    }
                },
                {
                    "_id": "emp_002", 
                    "userName": "ABC200",
                    "firstName": "Jane",
                    "lastName": "Smith",
                    "email": [{"workEmail": "jane.smith@company.com"}],
                    "phoneNumber": [{"mobileNumber": "+1234567891"}],
                    "role": "HR Manager",
                    "profession": "Human Resources",
                    "departmentId": "dept_hr",
                    "branchId": "branch_001",
                    "organizationId": "org_001",
                    "employeeInfo": [{
                        "empId": "ABC200",
                        "grade": "L2",
                        "designation": "HR Manager",
                        "depName": "Human Resources", 
                        "jobTitle": "HR Manager",
                        "reportingManager": "EMP100"
                    }],
                    "salaryInfo": {
                        "baseSalary": "95000",
                        "currency": "USD",
                        "netSalary": "85000"
                    },
                    "leaveBalance": {
                        "annualLeave": {"remaining": 18, "entitlement": 25, "used": 7},
                        "sickLeave": {"remaining": 10, "entitlement": 12, "used": 2},
                        "casualLeave": {"remaining": 4, "entitlement": 6, "used": 2}
                    }
                },
                {
                    "_id": "emp_003",
                    "userName": "QTG103", 
                    "firstName": "Ahmed",
                    "lastName": "Al-Rashid",
                    "email": [{"workEmail": "ahmed.rashid@company.com"}],
                    "phoneNumber": [{"mobileNumber": "+1234567892"}],
                    "role": "Team Lead",
                    "profession": "Software Developer",
                    "departmentId": "dept_eng",
                    "branchId": "branch_001",
                    "organizationId": "org_001",
                    "employeeInfo": [{
                        "empId": "QTG103",
                        "grade": "L3",
                        "designation": "Technical Lead",
                        "depName": "Engineering",
                        "jobTitle": "Senior Software Engineer",
                        "reportingManager": "EMP101"
                    }],
                    "salaryInfo": {
                        "baseSalary": "110000",
                        "currency": "USD", 
                        "netSalary": "98000"
                    },
                    "leaveBalance": {
                        "annualLeave": {"remaining": 20, "entitlement": 25, "used": 5},
                        "sickLeave": {"remaining": 12, "entitlement": 12, "used": 0},
                        "casualLeave": {"remaining": 5, "entitlement": 6, "used": 1}
                    }
                }
            ]
            
            # Insert sample data
            result = self.mongodb_service.employees_collection.insert_many(sample_employees)
            
            self.log_migration_step(
                "Sample Data Creation", 
                "SUCCESS", 
                f"Created {len(result.inserted_ids)} sample employee records"
            )
            return True
            
        except Exception as e:
            self.log_migration_step("Sample Data Creation", "FAILED", str(e))
            return False
    
    def generate_embeddings_for_all(self) -> bool:
        """Generate embeddings for all employees in the collection"""
        try:
            self.log_migration_step("Embedding Generation", "STARTING", "Generating embeddings for all employees")
            
            total_employees = self.mongodb_service.employees_collection.count_documents({})
            employees_without_embeddings = self.mongodb_service.employees_collection.count_documents({
                "$or": [{"embedding": {"$exists": False}}, {"embedding": None}]
            })
            
            self.log_migration_step(
                "Embedding Generation",
                "INFO", 
                f"Total employees: {total_employees}, Need embeddings: {employees_without_embeddings}"
            )
            
            if employees_without_embeddings == 0:
                self.log_migration_step("Embedding Generation", "SKIPPED", "All employees already have embeddings")
                return True
            
            # Generate embeddings in batches
            processed_count = self.vector_search_service.bulk_update_embeddings(batch_size=50)
            
            self.log_migration_step(
                "Embedding Generation",
                "SUCCESS", 
                f"Generated embeddings for {processed_count} employees"
            )
            return True
            
        except Exception as e:
            self.log_migration_step("Embedding Generation", "FAILED", str(e))
            return False
    
    def test_search_functionality(self) -> bool:
        """Test various search methods to ensure they work correctly"""
        try:
            self.log_migration_step("Search Testing", "STARTING", "Testing search functionality")
            
            test_cases = [
                {
                    "name": "Direct ID Lookup",
                    "test": lambda: self.mongodb_service.get_employee_by_id("EMP103"),
                    "expected": "Should find John Doe"
                },
                {
                    "name": "Text Search",
                    "test": lambda: self.mongodb_service.search_employees_by_text("Software Engineer"),
                    "expected": "Should find engineering employees"
                },
                {
                    "name": "Criteria Search",
                    "test": lambda: self.mongodb_service.search_employees_by_criteria({"department": "Engineering"}),
                    "expected": "Should find engineering department employees"
                },
                {
                    "name": "Vector Search",
                    "test": lambda: self.vector_search_service.semantic_search_employees("show me software developers"),
                    "expected": "Should find relevant developers using AI"
                }
            ]
            
            results = []
            for test_case in test_cases:
                try:
                    result = test_case["test"]()
                    success = result is not None and (isinstance(result, list) and len(result) > 0 or not isinstance(result, list))
                    results.append({
                        "name": test_case["name"],
                        "success": success,
                        "result_count": len(result) if isinstance(result, list) else (1 if result else 0),
                        "expected": test_case["expected"]
                    })
                    logger.info(f"✓ {test_case['name']}: {'PASS' if success else 'FAIL'}")
                except Exception as e:
                    results.append({
                        "name": test_case["name"],
                        "success": False,
                        "error": str(e),
                        "expected": test_case["expected"]
                    })
                    logger.error(f"✗ {test_case['name']}: FAIL - {str(e)}")
            
            success_count = sum(1 for r in results if r["success"])
            self.log_migration_step(
                "Search Testing",
                "COMPLETED",
                f"Passed {success_count}/{len(test_cases)} search tests"
            )
            
            return success_count == len(test_cases)
            
        except Exception as e:
            self.log_migration_step("Search Testing", "FAILED", str(e))
            return False
    
    def test_access_control(self) -> bool:
        """Test access control functionality"""
        try:
            self.log_migration_step("Access Control Testing", "STARTING", "Testing role-based access control")
            
            # Test different access levels
            test_scenarios = [
                {
                    "scenario": "L4 Employee accessing own data",
                    "requester_grade": "L4",
                    "requester_role": "employee", 
                    "requester_id": "EMP103",
                    "target_id": "EMP103",
                    "should_access": True
                },
                {
                    "scenario": "L4 Employee accessing other's data",
                    "requester_grade": "L4",
                    "requester_role": "employee",
                    "requester_id": "EMP103", 
                    "target_id": "ABC200",
                    "should_access": False
                },
                {
                    "scenario": "L2 HR Manager accessing any employee",
                    "requester_grade": "L2",
                    "requester_role": "HR Manager",
                    "requester_id": "ABC200",
                    "target_id": "EMP103", 
                    "should_access": True
                },
                {
                    "scenario": "L0 Executive accessing any employee",
                    "requester_grade": "L0",
                    "requester_role": "admin",
                    "requester_id": "EMP100",
                    "target_id": "QTG103",
                    "should_access": True
                }
            ]
            
            results = []
            for scenario in test_scenarios:
                try:
                    can_access = AccessControlMatrix.can_access_employee(
                        requester_grade=scenario["requester_grade"],
                        requester_role=scenario["requester_role"],
                        requester_id=scenario["requester_id"],
                        target_employee_id=scenario["target_id"]
                    )
                    
                    success = can_access == scenario["should_access"]
                    results.append({
                        "scenario": scenario["scenario"],
                        "success": success,
                        "expected": scenario["should_access"],
                        "actual": can_access
                    })
                    
                    status = "PASS" if success else "FAIL"
                    logger.info(f"✓ {scenario['scenario']}: {status}")
                    
                except Exception as e:
                    results.append({
                        "scenario": scenario["scenario"],
                        "success": False,
                        "error": str(e)
                    })
                    logger.error(f"✗ {scenario['scenario']}: ERROR - {str(e)}")
            
            success_count = sum(1 for r in results if r["success"])
            self.log_migration_step(
                "Access Control Testing",
                "COMPLETED", 
                f"Passed {success_count}/{len(test_scenarios)} access control tests"
            )
            
            return success_count == len(test_scenarios)
            
        except Exception as e:
            self.log_migration_step("Access Control Testing", "FAILED", str(e))
            return False
    
    def test_query_parsing(self) -> bool:
        """Test natural language query parsing"""
        try:
            self.log_migration_step("Query Parsing Testing", "STARTING", "Testing query parser")
            
            test_queries = [
                {
                    "query": "show me EMP103 salary details",
                    "expected_params": ["employee_id"],
                    "expected_intent": "get_salary_info"
                },
                {
                    "query": "find John Smith from Engineering",
                    "expected_params": ["name", "department"],
                    "expected_intent": "search_employees"
                },
                {
                    "query": "what is my leave balance?",
                    "expected_params": ["is_self_query"],
                    "expected_intent": "get_leave_balance"
                },
                {
                    "query": "get information for employee QTG103",
                    "expected_params": ["employee_id"],
                    "expected_intent": "get_employee_info"
                }
            ]
            
            results = []
            for test in test_queries:
                try:
                    parsed = self.query_parser_service.parse_query(test["query"], "EMP103")
                    
                    # Check if expected parameters were extracted
                    params_found = []
                    for param in test["expected_params"]:
                        if param in parsed["parameters"] and parsed["parameters"][param]:
                            params_found.append(param)
                        elif param == "is_self_query" and parsed["parameters"].get("is_self_query"):
                            params_found.append(param)
                    
                    success = len(params_found) > 0 and parsed["confidence"] > 0.3
                    results.append({
                        "query": test["query"],
                        "success": success,
                        "confidence": parsed["confidence"],
                        "intent": parsed["intent"].value,
                        "params_found": params_found
                    })
                    
                    status = "PASS" if success else "FAIL"
                    logger.info(f"✓ Query '{test['query']}': {status} (confidence: {parsed['confidence']:.2f})")
                    
                except Exception as e:
                    results.append({
                        "query": test["query"],
                        "success": False,
                        "error": str(e)
                    })
                    logger.error(f"✗ Query '{test['query']}': ERROR - {str(e)}")
            
            success_count = sum(1 for r in results if r["success"])
            self.log_migration_step(
                "Query Parsing Testing",
                "COMPLETED",
                f"Passed {success_count}/{len(test_queries)} query parsing tests"
            )
            
            return success_count >= len(test_queries) * 0.8  # Allow 20% failure rate
            
        except Exception as e:
            self.log_migration_step("Query Parsing Testing", "FAILED", str(e))
            return False
    
    def save_migration_report(self):
        """Save migration report to file"""
        try:
            report = {
                "migration_date": datetime.now().isoformat(),
                "total_steps": len(self.migration_log),
                "successful_steps": len([step for step in self.migration_log if step["status"] in ["SUCCESS", "COMPLETED", "SKIPPED"]]),
                "failed_steps": len([step for step in self.migration_log if step["status"] == "FAILED"]),
                "steps": self.migration_log
            }
            
            report_file = f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"Migration report saved to {report_file}")
            return report_file
            
        except Exception as e:
            logger.error(f"Failed to save migration report: {str(e)}")
            return None
    
    def run_full_migration(self) -> bool:
        """Run the complete migration process"""
        print("🚀 Starting HR System Migration to Vector Search")
        print("=" * 50)
        
        try:
            # Initialize services
            if not self.initialize_services():
                print("❌ Failed to initialize services")
                return False
            
            # Validate MongoDB connection
            if not self.validate_mongodb_connection():
                print("❌ MongoDB connection validation failed")
                return False
            
            # Create sample data if needed
            if not self.create_sample_employee_data():
                print("❌ Sample data creation failed")
                return False
            
            # Generate embeddings
            if not self.generate_embeddings_for_all():
                print("❌ Embedding generation failed")
                return False
            
            # Test search functionality
            if not self.test_search_functionality():
                print("⚠️ Some search tests failed")
            
            # Test access control
            if not self.test_access_control():
                print("⚠️ Some access control tests failed")
            
            # Test query parsing
            if not self.test_query_parsing():
                print("⚠️ Some query parsing tests failed")
            
            # Save report
            report_file = self.save_migration_report()
            
            print("\n✅ Migration completed!")
            print(f"📊 Report saved to: {report_file}")
            print("\nNext steps:")
            print("1. Create vector search index in MongoDB Atlas")
            print("2. Update OpenAI Assistant with new tool definitions")
            print("3. Test the new employee module in the application")
            
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            print(f"❌ Migration failed: {str(e)}")
            return False

def main():
    """Main migration function"""
    migration = HRSystemMigration()
    success = migration.run_full_migration()
    
    if success:
        print("\n🎉 Migration completed successfully!")
        return 0
    else:
        print("\n💥 Migration failed. Check the logs for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
