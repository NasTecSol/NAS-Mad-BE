# quick_test.py
"""
Quick test script to verify everything is working
"""

import sys
import os

def test_imports():
    """Test if all required modules can be imported"""
    print("🔍 Testing imports...")
    
    try:
        from services.mongodb_service import MongoDBService
        print("✅ MongoDB service import: OK")
    except Exception as e:
        print(f"❌ MongoDB service import failed: {str(e)}")
        return False
    
    try:
        from services.vector_search_service import VectorSearchService
        print("✅ Vector search service import: OK")
    except Exception as e:
        print(f"❌ Vector search service import failed: {str(e)}")
        return False
    
    try:
        from services.query_parser_service import QueryParserService
        print("✅ Query parser service import: OK")
    except Exception as e:
        print(f"❌ Query parser service import failed: {str(e)}")
        return False
    
    try:
        from utils.access_control import AccessControlMatrix
        print("✅ Access control import: OK")
    except Exception as e:
        print(f"❌ Access control import failed: {str(e)}")
        return False
    
    try:
        from modules.employee import get_employee_data_tool
        print("✅ Employee module import: OK")
    except Exception as e:
        print(f"❌ Employee module import failed: {str(e)}")
        return False
    
    return True

def test_mongodb_connection():
    """Test MongoDB connection"""
    print("\n🔍 Testing MongoDB connection...")
    
    try:
        from services.mongodb_service import MongoDBService
        
        mongodb_service = MongoDBService()
        if mongodb_service.is_connected():
            print("✅ MongoDB connection: OK")
            
            # Test basic operation
            count = mongodb_service.employees_collection.count_documents({})
            print(f"✅ Found {count} documents in employees collection")
            return True
        else:
            print("❌ MongoDB connection: Failed")
            return False
            
    except Exception as e:
        print(f"❌ MongoDB connection test failed: {str(e)}")
        return False

def test_employee_module():
    """Test employee module basic functionality"""
    print("\n🔍 Testing employee module...")
    
    try:
        from modules.employee import get_employee_data_tool
        
        # Test basic query
        result = get_employee_data_tool("show me employee information", "test_user")
        
        if isinstance(result, dict) and "success" in result:
            print("✅ Employee module basic test: OK")
            print(f"   Result: {result.get('message', 'No message')}")
            return True
        else:
            print("❌ Employee module test failed: Invalid response format")
            return False
            
    except Exception as e:
        print(f"❌ Employee module test failed: {str(e)}")
        return False

def main():
    print("🧪 Quick System Test")
    print("=" * 30)
    
    # Test imports
    if not test_imports():
        print("\n❌ Import tests failed. Please check your file structure and dependencies.")
        return 1
    
    # Test MongoDB connection
    mongodb_ok = test_mongodb_connection()
    
    # Test employee module
    module_ok = test_employee_module()
    
    print("\n" + "=" * 30)
    print("📊 Test Summary:")
    print(f"  Imports: ✅")
    print(f"  MongoDB: {'✅' if mongodb_ok else '❌'}")
    print(f"  Employee Module: {'✅' if module_ok else '❌'}")
    
    if mongodb_ok and module_ok:
        print("\n🎉 All tests passed! Your system should work now.")
        print("Try running: python main.py")
        return 0
    else:
        print("\n⚠️ Some tests failed, but the application might still start with limited functionality.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
