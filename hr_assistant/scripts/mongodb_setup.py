# scripts/setup_mongodb.py
"""
MongoDB setup script for HR Assistant
This script helps set up the MongoDB database, collections, and vector search index
"""

import os
import sys
from pymongo import MongoClient
from services.mongodb_service import MongoDBService
from services.vector_search_service import VectorSearchService
from utils.logger import logger
from config.settings import settings

def create_vector_search_index():
    """Create vector search index for employee collection"""
    try:
        client = MongoClient(settings.MONGODB_URI or f"mongodb://{settings.MONGODB_HOST}:{settings.MONGODB_PORT}")
        db = client[settings.MONGODB_DATABASE]
        collection = db[settings.MONGODB_COLLECTION]
        
        # Define the vector search index
        index_definition = {
            "name": settings.VECTOR_INDEX_NAME,
            "definition": {
                "fields": [
                    {
                        "type": "vector",
                        "path": "embedding",
                        "numDimensions": 1536,  # For text-embedding-3-small
                        "similarity": "cosine"
                    },
                    {
                        "type": "filter",
                        "path": "departmentId"
                    },
                    {
                        "type": "filter", 
                        "path": "branchId"
                    },
                    {
                        "type": "filter",
                        "path": "employeeInfo.grade"
                    }
                ]
            }
        }
        
        # Note: Vector search indexes must be created through MongoDB Atlas UI or mongosh
        # This is for documentation purposes
        print("Vector Search Index Definition:")
        print("=====================================")
        print(f"Database: {settings.MONGODB_DATABASE}")
        print(f"Collection: {settings.MONGODB_COLLECTION}")
        print(f"Index Name: {settings.VECTOR_INDEX_NAME}")
        print("\nIndex Definition (use this in MongoDB Atlas):")
        print(index_definition)
        
        print("\nTo create this index:")
        print("1. Go to MongoDB Atlas Dashboard")
        print("2. Navigate to Search -> Create Search Index")
        print("3. Choose Vector Search")
        print("4. Use the definition above")
        
        return True
        
    except Exception as e:
        logger.error(f"Error setting up vector search index: {str(e)}")
        return False

def create_text_search_index():
    """Create text search index for fallback searches"""
    try:
        client = MongoClient(settings.MONGODB_URI or f"mongodb://{settings.MONGODB_HOST}:{settings.MONGODB_PORT}")
        db = client[settings.MONGODB_DATABASE]
        collection = db[settings.MONGODB_COLLECTION]
        
        # Create text index on searchable fields
        text_index = [
            ("firstName", "text"),
            ("lastName", "text"),
            ("userName", "text"),
            ("employeeInfo.empId", "text"),
            ("employeeInfo.depName", "text"),
            ("employeeInfo.designation", "text"),
            ("employeeInfo.jobTitle", "text"),
            ("role", "text"),
            ("profession", "text")
        ]
        
        result = collection.create_index(text_index, name="employee_text_search")
        print(f"Created text search index: {result}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating text search index: {str(e)}")
        return False

def create_performance_indexes():
    """Create indexes for better query performance"""
    try:
        client = MongoClient(settings.MONGODB_URI or f"mongodb://{settings.MONGODB_HOST}:{settings.MONGODB_PORT}")
        db = client[settings.MONGODB_DATABASE]
        collection = db[settings.MONGODB_COLLECTION]
        
        # Individual field indexes
        indexes = [
            ("userName", 1),
            ("employeeInfo.empId", 1),
            ("departmentId", 1),
            ("branchId", 1),
            ("employeeInfo.grade", 1),
            ("employeeInfo.reportingManager", 1),
            ("role", 1)
        ]
        
        for index_spec in indexes:
            try:
                result = collection.create_index([index_spec])
                print(f"Created index on {index_spec[0]}: {result}")
            except Exception as e:
                print(f"Index on {index_spec[0]} might already exist: {str(e)}")
        
        # Compound indexes
        compound_indexes = [
            [("departmentId", 1), ("employeeInfo.grade", 1)],
            [("branchId", 1), ("departmentId", 1)],
            [("firstName", 1), ("lastName", 1)]
        ]
        
        for compound_index in compound_indexes:
            try:
                result = collection.create_index(compound_index)
                print(f"Created compound index: {result}")
            except Exception as e:
                print(f"Compound index might already exist: {str(e)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error creating performance indexes: {str(e)}")
        return False

def generate_sample_embeddings(limit=10):
    """Generate embeddings for a sample of employees (for testing)"""
    try:
        mongodb_service = MongoDBService()
        vector_service = VectorSearchService(mongodb_service)
        
        client = MongoClient(settings.MONGODB_URI or f"mongodb://{settings.MONGODB_HOST}:{settings.MONGODB_PORT}")
        db = client[settings.MONGODB_DATABASE]
        collection = db[settings.MONGODB_COLLECTION]
        
        # Find employees without embeddings
        employees_without_embeddings = list(collection.find(
            {"embedding": {"$exists": False}}, 
            limit=limit
        ))
        
        print(f"Generating embeddings for {len(employees_without_embeddings)} employees...")
        
        for i, employee in enumerate(employees_without_embeddings):
            try:
                embedding = vector_service.create_employee_embedding(employee)
                if embedding:
                    collection.update_one(
                        {"_id": employee["_id"]},
                        {"$set": {"embedding": embedding}}
                    )
                    print(f"Generated embedding for employee {i+1}/{len(employees_without_embeddings)}")
                else:
                    print(f"Failed to generate embedding for employee {employee.get('userName', 'unknown')}")
                    
            except Exception as e:
                print(f"Error processing employee {employee.get('userName', 'unknown')}: {str(e)}")
        
        print("Sample embedding generation completed!")
        return True
        
    except Exception as e:
        logger.error(f"Error generating sample embeddings: {str(e)}")
        return False

def test_connection():
    """Test MongoDB connection"""
    try:
        client = MongoClient(settings.MONGODB_URI or f"mongodb://{settings.MONGODB_HOST}:{settings.MONGODB_PORT}")
        
        # Test connection
        client.admin.command('ping')
        print("✓ MongoDB connection successful")
        
        # Test database access
        db = client[settings.MONGODB_DATABASE]
        collections = db.list_collection_names()
        print(f"✓ Database '{settings.MONGODB_DATABASE}' accessible")
        print(f"  Collections: {collections}")
        
        # Test collection access
        if settings.MONGODB_COLLECTION in collections:
            collection = db[settings.MONGODB_COLLECTION]
            count = collection.count_documents({})
            print(f"✓ Collection '{settings.MONGODB_COLLECTION}' has {count} documents")
        else:
            print(f"⚠ Collection '{settings.MONGODB_COLLECTION}' not found")
        
        return True
        
    except Exception as e:
        print(f"✗ MongoDB connection failed: {str(e)}")
        return False

def main():
    """Main setup function"""
    print("HR Assistant MongoDB Setup")
    print("==========================")
    
    # Test connection first
    if not test_connection():
        print("Please check your MongoDB configuration and try again.")
        return False
    
    print("\n1. Creating performance indexes...")
    create_performance_indexes()
    
    print("\n2. Creating text search index...")
    create_text_search_index()
    
    print("\n3. Vector search index setup...")
    create_vector_search_index()
    
    print("\n4. Generating sample embeddings...")
    generate_sample_embeddings(limit=5)
    
    print("\nSetup completed!")
    print("\nNext steps:")
    print("1. Create the vector search index in MongoDB Atlas using the definition above")
    print("2. Run the full embedding generation for all employees")
    print("3. Test the employee search functionality")
    
    return True

if __name__ == "__main__":
    main()
