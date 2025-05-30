# scripts/test_employee_module.py
"""
Comprehensive testing script for the new employee module with vector search capabilities.
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.employee import get_employee_data_tool, search_similar_employees_tool
from services.mongodb_service import MongoDBService
from services.vector_search_service import VectorSearchService
from services.query_parser_service import QueryParserService
from utils.access_control import AccessControlMatrix
from utils.logger import logger

class EmployeeModuleTester:
    """Comprehensive testing suite for the employee module"""
    
    def __init__(self):
        self.test_results = []
        self.mongodb_service = None
        self.vector_search_service = None
        self.query_parser_service = None
        
    def initialize_services(self):
        """Initialize testing services"""
        try:
            self.mongodb_service = MongoDBService()
            self.vector_search_service = VectorSearchService(self.mongodb_service)
            self.query_parser_service = QueryParserService()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize services: {str(e)}")
            return False
    
    def log_test_result(self, test_name: str, success: bool, details: Dict = None, error: str = None):
        """Log test result"""
        result = {
            "test_name": test_name,
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "details": details or {},
            "error": error
        }
        self.test_results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if error:
            print(f"   Error: {error}")
        if details:
            print(f"   Details: {json.dumps(details, indent=2)}")
    
    def test_direct_employee_lookup(self):
        """Test direct employee ID lookup"""
        test_queries = [
            ("EMP103", "Direct lookup with standard format"),
            ("ABC200", "Direct lookup with custom format"),
            ("QTG103", "Direct lookup with different custom format"),
            ("INVALID123", "Invalid employee ID test")
        ]
        
        for employee_id, description in test_queries:
            try:
                query = f"get information for employee {employee_id}"
                result = get_employee_data_tool(query, "EMP103")  # Test as EMP103
                
                if employee_id == "INVALID123":
                    # This should fail
                    success = not result["success"]
                    details = {"expected": "failure", "actual": "failure" if not result["success"] else "success"}
                else:
                    # These should succeed
                    success = result["success"] and len(result.get("data", [])) > 0
                    details = {
                        "query": query,
                        "found_employees": len(result.get("data", [])),
                        "has_formatted_response": bool(result.get("formatted_response"))
                    }
                
                self.log_test_result(f"Direct Lookup: {description}", success, details)
                
            except Exception as e:
                self.log_test_result(f"Direct Lookup: {description}", False, error=str(e))
    
    def test_name_based_search(self):
        """Test name-based employee search"""
        test_queries = [
            ("find John Smith", "Simple name search"),
            ("show me Jane Smith's information", "Name with possessive"),
            ("get Ahmed Al-Rashid details", "Arabic name search"),
            ("find employee named John", "Partial name search")
        ]
        
        for query, description in test_queries:
            try:
                result = get_employee_data_tool(query, "ABC200")  # Test as HR Manager
                
                success = result["success"] and len(result.get("data", [])) > 0
                details = {
                    "query": query,
                    "found_employees": len(result.get("data", [])),
                    "confidence": result.get("query_info", {}).get("confidence", 0),
                    "intent": result.get("query_info", {}).get("intent", "unknown")
                }
                
                self.log_test_result(f"Name Search: {description}", success, details)
                
            except Exception as e:
                self.log_test_result(f"Name Search: {description}", False, error=str(e))
    
    def test_department_based_search(self):
        """Test department-based search"""
        test_queries = [
            ("show me all software engineers", "Role-based search"),
            ("find employees in Engineering department", "Department-based search"),
            ("list all HR managers", "Role and department combined"),
            ("show me technical leads from engineering", "Specific role in department")
        ]
        
        for query, description in test_queries:
            try:
                result = get_employee_data_tool(query, "ABC200")  # Test as HR Manager
                
                success = result["success"]
                details = {
                    "query": query,
                    "found_employees": len(result.get("data", [])),
                    "search_strategy": result.get("query_info", {}).get("intent", "unknown")
                }
                
                self.log_test_result(f"Department Search: {description}", success, details)
                
            except Exception as e:
                self.log_test_result(f"Department Search: {description}", False, error=str(e))
    
    def test_salary_queries(self):
        """Test salary-specific queries"""
        test_queries = [
            ("what is EMP103's salary?", "EMP103", "Direct salary query"),
            ("show me John Smith's compensation", "ABC200", "Name-based salary query"),
            ("my salary information", "EMP103", "Self salary query"),
            ("what is my salary?", "QTG103", "Self salary query variant")
        ]
        
        for query, requester_id, description in test_queries:
            try:
                result = get_employee_data_tool(query, requester_id)
                
                # Check if salary information is included
                has_salary_info = False
                if result["success"] and result.get("data"):
                    for employee in result["data"]:
                        if "salaryInfo" in employee:
                            has_salary_info = True
                            break
                
                success = result["success"] and has_salary_info
                details = {
                    "query": query,
                    "requester_id": requester_id,
                    "has_salary_info": has_salary_info,
                    "intent": result.get("query_info", {}).get("intent", "unknown")
                }
                
                self.log_test_result(f"Salary Query: {description}", success, details)
                
            except Exception as e:
                self.log_test_result(f"Salary Query: {description}", False, error=str(e))
    
    def test_leave_balance_queries(self):
        """Test leave balance queries"""
        test_queries = [
            ("what is my leave balance?", "EMP103", "Self leave query"),
            ("show me EMP103 leave details", "ABC200", "Manager checking employee leave"),
            ("how many annual leaves does John have?", "ABC200", "Specific leave type query")
        ]
        
        for query, requester_id, description in test_queries:
            try:
                result = get_employee_data_tool(query, requester_id)
                
                # Check if leave information is included
                has_leave_info = False
                if result["success"] and result.get("data"):
                    for employee in result["data"]:
                        if "leaveBalance" in employee:
                            has_leave_info = True
                            break
                
                success = result["success"] and has_leave_info
                details = {
                    "query": query,
                    "requester_id": requester_id,
                    "has_leave_info": has_leave_info,
                    "formatted_response_length": len(result.get("formatted_response", ""))
                }
                
                self.log_test_result(f"Leave Query: {description}", success, details)
                
            except Exception as e:
                self.log_test_result(f"Leave Query: {description}", False, error=str(e))
    
    def test_access_control_enforcement(self):
        """Test access control enforcement"""
        test_scenarios = [
            {
                "query": "show me ABC200 salary details",
                "requester_id": "EMP103",  # L4 employee
                "target_accessible": False,
                "description": "L4 employee accessing other's salary"
            },
            {
                "query": "show me EMP103 salary details", 
                "requester_id": "ABC200",  # L2 HR Manager
                "target_accessible": True,
                "description": "HR Manager accessing employee salary"
            },
            {
                "query": "what is my salary?",
                "requester_id": "EMP103",  # Self query
                "target_accessible": True,
                "description": "Employee accessing own salary"
            },
            {
                "query": "show me QTG103 information",
                "requester_id": "EMP103",  # L4 accessing L3
                "target_accessible": False,
                "description": "L4 employee accessing L3 manager data"
            }
        ]
        
        for scenario in test_scenarios:
            try:
                result = get_employee_data_tool(scenario["query"], scenario["requester_id"])
                
                if scenario["target_accessible"]:
                    # Should succeed and return data
                    success = result["success"] and len(result.get("data", [])) > 0
                else:
                    # Should either fail or return empty/filtered data
                    success = not result["success"] or len(result.get("data", [])) == 0
                
                details = {
                    "query": scenario["query"],
                    "requester": scenario["requester_id"],
                    "expected_access": scenario["target_accessible"],
                    "actual_success": result["success"],
                    "data_returned": len(result.get("data", []))
                }
                
                self.log_test_result(f"Access Control: {scenario['description']}", success, details)
                
            except Exception as e:
                self.log_test_result(f"Access Control: {scenario['description']}", False, error=str(e))
    
    def test_vector_search_functionality(self):
        """Test vector search capabilities"""
        if not self.vector_search_service:
            self.log_test_result("Vector Search: Service Check", False, error="Vector search service not available")
            return
        
        test_queries = [
            ("find software developers with leadership experience", "Complex semantic search"),
            ("show me employees similar to technical leads", "Role-based semantic search"),
            ("find HR professionals", "Department semantic search"),
            ("get me senior level employees", "Grade-based semantic search")
        ]
        
        for query, description in test_queries:
            try:
                result = get_employee_data_tool(query, "ABC200")  # Test as HR Manager
                
                # Vector search should still return results even if not perfect matches
                success = result["success"]
                details = {
                    "query": query,
                    "found_employees": len(result.get("data", [])),
                    "search_strategy": "vector_search",
                    "confidence": result.get("query_info", {}).get("confidence", 0)
                }
                
                self.log_test_result(f"Vector Search: {description}", success, details)
                
            except Exception as e:
                self.log_test_result(f"Vector Search: {description}", False, error=str(e))
    
    def test_similar_employees_functionality(self):
        """Test finding similar employees"""
        test_cases = [
            ("EMP103", "ABC200", "Find employees similar to EMP103"),
            ("ABC200", "ABC200", "Find employees similar to ABC200 (self)")
        ]
        
        for target_id, requester_id, description in test_cases:
            try:
                result = search_similar_employees_tool(target_id, requester_id)
                
                success = result["success"] and len(result.get("data", [])) > 0
                details = {
                    "target_employee": target_id,
                    "requester": requester_id,
                    "similar_employees_found": len(result.get("data", []))
                }
                
                self.log_test_result(f"Similar Employees: {description}", success, details)
                
            except Exception as e:
                self.log_test_result(f"Similar Employees: {description}", False, error=str(e))
    
    def test_query_parsing_accuracy(self):
        """Test query parsing accuracy"""
        test_queries = [
            {
                "query": "show me EMP103 salary details",
                "expected_intent": "get_salary_info",
                "expected_params": ["employee_id"]
            },
            {
                "query": "find John Smith from Engineering",
                "expected_intent": "search_employees", 
                "expected_params": ["name", "department"]
            },
            {
                "query": "what is my leave balance?",
                "expected_intent": "get_leave_balance",
                "expected_params": ["is_self_query"]
            }
        ]
        
        for test in test_queries:
            try:
                parsed = self.query_parser_service.parse_query(test["query"], "EMP103")
                
                # Check intent accuracy
                intent_correct = parsed["intent"].value == test["expected_intent"]
                
                # Check parameter extraction
                params_found = 0
                for expected_param in test["expected_params"]:
                    if expected_param in parsed["parameters"] and parsed["parameters"][expected_param]:
                        params_found += 1
                    elif expected_param == "is_self_query" and parsed["parameters"].get("is_self_query"):
                        params_found += 1
                
                params_correct = params_found > 0
                success = intent_correct and params_correct and parsed["confidence"] > 0.3
                
                details = {
                    "query": test["query"],
                    "expected_intent": test["expected_intent"],
                    "actual_intent": parsed["intent"].value,
                    "intent_correct": intent_correct,
                    "params_correct": params_correct,
                    "confidence": parsed["confidence"],
                    "parameters": parsed["parameters"]
                }
                
                self.log_test_result(f"Query Parsing: {test['query'][:30]}...", success, details)
                
            except Exception as e:
                self.log_test_result(f"Query Parsing: {test['query'][:30]}...", False, error=str(e))
    
    def test_response_formatting(self):
        """Test response formatting quality"""
        test_queries = [
            ("show me EMP103 information", "EMP103", "Basic employee info formatting"),
            ("what is ABC200's salary?", "ABC200", "Salary info formatting"),
            ("my leave balance", "QTG103", "Leave balance formatting"),
            ("find all software engineers", "ABC200", "Multiple results formatting")
        ]
        
        for query, requester_id, description in test_queries:
            try:
                result = get_employee_data_tool(query, requester_id)
                
                if result["success"]:
                    formatted_response = result.get("formatted_response", "")
                    
                    # Check formatting quality
                    has_structure = "**" in formatted_response  # Headers
                    has_emojis = any(emoji in formatted_response for emoji in ["💰", "🏖️", "👤", "📧"])
                    has_bullets = "•" in formatted_response
                    reasonable_length = 50 < len(formatted_response) < 2000
                    
                    success = has_structure and reasonable_length
                    details = {
                        "query": query,
                        "response_length": len(formatted_response),
                        "has_structure": has_structure,
                        "has_emojis": has_emojis,
                        "has_bullets": has_bullets,
                        "preview": formatted_response[:100] + "..." if len(formatted_response) > 100 else formatted_response
                    }
                else:
                    success = False
                    details = {"error": "Query failed", "message": result.get("message", "")}
                
                self.log_test_result(f"Response Formatting: {description}", success, details)
                
            except Exception as e:
                self.log_test_result(f"Response Formatting: {description}", False, error=str(e))
    
    def run_all_tests(self):
        """Run all test suites"""
        print("🧪 Starting Employee Module Comprehensive Testing")
        print("=" * 60)
        
        if not self.initialize_services():
            print("❌ Failed to initialize services. Cannot run tests.")
            return False
        
        print("\n📋 Running Test Suites:")
        
        # Run all test suites
        test_suites = [
            ("Direct Employee Lookup", self.test_direct_employee_lookup),
            ("Name-based Search", self.test_name_based_search), 
            ("Department-based Search", self.test_department_based_search),
            ("Salary Queries", self.test_salary_queries),
            ("Leave Balance Queries", self.test_leave_balance_queries),
            ("Access Control Enforcement", self.test_access_control_enforcement),
            ("Vector Search Functionality", self.test_vector_search_functionality),
            ("Similar Employees", self.test_similar_employees_functionality),
            ("Query Parsing Accuracy", self.test_query_parsing_accuracy),
            ("Response Formatting", self.test_response_formatting)
        ]
        
        for suite_name, test_func in test_suites:
            print(f"\n🔍 {suite_name}")
            print("-" * 40)
            try:
                test_func()
            except Exception as e:
                print(f"❌ Test suite '{suite_name}' failed with error: {str(e)}")
        
        # Generate summary
        self.generate_test_summary()
        
        return True
    
    def generate_test_summary(self):
        """Generate and display test summary"""
        total_tests = len(self.test_results)
        passed_tests = len([t for t in self.test_results if t["success"]])
        failed_tests = total_tests - passed_tests
        
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"📈 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print(f"\n❌ Failed Tests:")
            for test in self.test_results:
                if not test["success"]:
                    print(f"   • {test['test_name']}")
                    if test.get("error"):
                        print(f"     Error: {test['error']}")
        
        # Save detailed report
        report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(report_file, 'w') as f:
                json.dump({
                    "summary": {
                        "total_tests": total_tests,
                        "passed_tests": passed_tests,
                        "failed_tests": failed_tests,
                        "success_rate": (passed_tests/total_tests)*100
                    },
                    "test_results": self.test_results
                }, f, indent=2)
            print(f"\n📄 Detailed report saved to: {report_file}")
        except Exception as e:
            print(f"⚠️ Failed to save detailed report: {str(e)}")

def main():
    """Main testing function"""
    tester = EmployeeModuleTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 Testing completed!")
        return 0
    else:
        print("\n💥 Testing failed to initialize.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
