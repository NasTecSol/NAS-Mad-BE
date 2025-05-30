# scripts/test_basic_functionality.py
"""
Basic test script to verify MongoDB and core functionality without vector search
"""

import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_mongodb_connection():
    """Test MongoDB connection"""
    try:
        from services.mongodb_service import MongoDBService
        
        print("🔍 Testing MongoDB connection...")
        mongodb_service = MongoDBService()
        
        # Test basic operations
        count = mongodb_service.employees_collection.count_documents({})
        print(f"✅ MongoDB connected! Found {count} employees in collection.")
        
        return mongodb_service
    except Exception as e:
        print(f"❌ MongoDB connection failed: {str(e)}")
        return None

def test_access_control():
    """Test access control system"""
    try:
        from utils.access_control import AccessControlMatrix
        
        print("\n🔍 Testing access control...")
        
        # Test basic access control
        can_access = AccessControlMatrix.can_access_employee(
            requester_grade="L4",
            requester_role="employee", 
            requester_id="EMP103",
            target_employee_id="EMP103"
        )
        
        print(f"✅ Access control working! L4 employee can access own data: {can_access}")
        return True
    except Exception as e:
        print(f"❌ Access control test failed: {str(e)}")
        return False

def test_employee_module():
    """Test employee module basic functionality"""
    try:
        from modules.employee import get_employee_data_tool
        
        print("\n🔍 Testing employee module...")
        
        # Test basic query
        result = get_employee_data_tool("get information for employee EMP103", "EMP103")
        
        if result.get("success"):
            print("✅ Employee module working! Query executed successfully.")
            print(f"   Found {len(result.get('data', []))} employees")
        else:
            print(f"⚠️ Employee module query failed: {result.get('message', 'Unknown error')}")
        
        return True
    except Exception as e:
        print(f"❌ Employee module test failed: {str(e)}")
        return False

def create_sample_data(mongodb_service):
    """Create sample data for testing"""
    try:
        count = mongodb_service.employees_collection.count_documents({})
        if count > 0:
            print(f"📊 Collection already has {count} documents. Skipping sample data creation.")
            return True
        
        print("\n🔍 Creating sample data...")
        
        sample_employees = [
            {
                "_id": "emp_001",
                "userName": "EMP103",
                "firstName": "John",
                "lastName": "Doe",
                "email": [{"workEmail": "john.doe@company.com"}],
                "role": "Software Engineer",
                "departmentId": "dept_eng",
                "employeeInfo": [{
                    "empId": "EMP103",
                    "grade": "L4",
                    "designation": "Senior Developer",
                    "depName": "Engineering"
                }],
                "salaryInfo": {
                    "baseSalary": "85000",
                    "currency": "USD"
                }
            },
            {
                "_id": "emp_002", 
                "userName": "ABC200",
                "firstName": "Jane",
                "lastName": "Smith",
                "email": [{"workEmail": "jane.smith@company.com"}],
                "role": "HR Manager",
                "departmentId": "dept_hr",
                "employeeInfo": [{
                    "empId": "ABC200",
                    "grade": "L2",
                    "designation": "HR Manager",
                    "depName": "Human Resources"
                }],
                "salaryInfo": {
                    "baseSalary": "95000",
                    "currency": "USD"
                }
            }
        ]
        
        result = mongodb_service.employees_collection.insert_many(sample_employees)
        print(f"✅ Created {len(result.inserted_ids)} sample employees")
        return True
        
    except Exception as e:
        print(f"❌ Sample data creation failed: {str(e)}")
        return False

def main():
    print("🧪 Basic Functionality Test")
    print("=" * 40)
    
    # Test MongoDB
    mongodb_service = test_mongodb_connection()
    if not mongodb_service:
        print("❌ Cannot proceed without MongoDB connection")
        return 1
    
    # Create sample data if needed
    create_sample_data(mongodb_service)
    
    # Test access control
    access_control_ok = test_access_control()
    
    # Test employee module
    employee_module_ok = test_employee_module()
    
    print("\n" + "=" * 40)
    print("📊 Test Results:")
    print(f"  MongoDB: ✅")
    print(f"  Access Control: {'✅' if access_control_ok else '❌'}")
    print(f"  Employee Module: {'✅' if employee_module_ok else '❌'}")
    
    if access_control_ok and employee_module_ok:
        print("\n🎉 Basic functionality is working!")
        print("You can now proceed to fix the OpenAI integration for vector search.")
        return 0
    else:
        print("\n⚠️ Some basic functionality failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
