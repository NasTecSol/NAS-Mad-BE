# utils/access_control.py
from enum import Enum
from typing import Dict, List, Set, Optional
from utils.logger import logger


class AccessLevel(Enum):
    """Employee access levels based on grade"""
    L0 = "L0"  # Executive/Owner
    L1 = "L1"  # Executive/Admin
    L2 = "L2"  # HR Manager
    L3 = "L3"  # Supervisor
    L4 = "L4"  # Employee


class DataCategory(Enum):
    """Categories of data that can be accessed"""
    BASIC_INFO = "basic_info"           # Name, ID, department, position
    CONTACT_INFO = "contact_info"       # Phone, email, address
    SALARY_INFO = "salary_info"         # Salary, allowances, deductions
    LEAVE_DATA = "leave_data"           # Leave balance, leave history
    ATTENDANCE_DATA = "attendance_data"  # Attendance records
    BANKING_INFO = "banking_info"       # Bank details
    FAMILY_INFO = "family_info"         # Family and emergency contacts
    DOCUMENTS = "documents"             # Personal documents
    CONTRACT_INFO = "contract_info"     # Contract details
    ASSETS_INFO = "assets_info"         # Company assets
    LOAN_INFO = "loan_info"            # Loan information


class AccessControlMatrix:
    """Manages access control based on employee grade and role"""

    # Define what data categories each grade can access
    GRADE_PERMISSIONS = {
        AccessLevel.L0: {  # Executive/Owner
            "can_access_all_employees": True,
            "allowed_data_categories": [
                DataCategory.BASIC_INFO,
                DataCategory.CONTACT_INFO,
                DataCategory.SALARY_INFO,
                DataCategory.LEAVE_DATA,
                DataCategory.ATTENDANCE_DATA,
                DataCategory.BANKING_INFO,
                DataCategory.FAMILY_INFO,
                DataCategory.DOCUMENTS,
                DataCategory.CONTRACT_INFO,
                DataCategory.ASSETS_INFO,
                DataCategory.LOAN_INFO
            ]
        },
        AccessLevel.L1: {  # Executive/Admin
            "can_access_all_employees": True,
            "allowed_data_categories": [
                DataCategory.BASIC_INFO,
                DataCategory.CONTACT_INFO,
                DataCategory.SALARY_INFO,
                DataCategory.LEAVE_DATA,
                DataCategory.ATTENDANCE_DATA,
                DataCategory.BANKING_INFO,
                DataCategory.FAMILY_INFO,
                DataCategory.DOCUMENTS,
                DataCategory.CONTRACT_INFO,
                DataCategory.ASSETS_INFO,
                DataCategory.LOAN_INFO
            ]
        },
        AccessLevel.L2: {  # HR Manager
            "can_access_all_employees": True,
            "allowed_data_categories": [
                DataCategory.BASIC_INFO,
                DataCategory.CONTACT_INFO,
                DataCategory.SALARY_INFO,
                DataCategory.LEAVE_DATA,
                DataCategory.ATTENDANCE_DATA,
                DataCategory.BANKING_INFO,
                DataCategory.FAMILY_INFO,
                DataCategory.CONTRACT_INFO,
                DataCategory.ASSETS_INFO
            ]
        },
        AccessLevel.L3: {  # Supervisor
            "can_access_all_employees": False,  # Only team members
            "allowed_data_categories": [
                DataCategory.BASIC_INFO,
                DataCategory.CONTACT_INFO,
                DataCategory.LEAVE_DATA,
                DataCategory.ATTENDANCE_DATA,
                DataCategory.SALARY_INFO
            ]
        },
        AccessLevel.L4: {  # Employee
            "can_access_all_employees": False,  # Only own data
            "allowed_data_categories": [
                DataCategory.BASIC_INFO,
                DataCategory.CONTACT_INFO,
                DataCategory.LEAVE_DATA,
                DataCategory.ATTENDANCE_DATA
            ]
        }
    }

    # Special roles with enhanced permissions
    ENHANCED_ROLES = {
        "admin": AccessLevel.L0,
        "owner": AccessLevel.L0,
        "hr manager": AccessLevel.L2,
        "hr_manager": AccessLevel.L2
    }

    @classmethod
    def get_access_level(cls, grade: str, role: str = None) -> AccessLevel:
        """Determine access level based on grade and role"""
        try:
            # Check for enhanced roles first
            if role and role.lower() in cls.ENHANCED_ROLES:
                return cls.ENHANCED_ROLES[role.lower()]

            # Default to grade-based access
            return AccessLevel(grade.upper())
        except ValueError:
            logger.warning(f"Unknown grade '{grade}', defaulting to L4")
            return AccessLevel.L4

    @classmethod
    def can_access_employee(cls, requester_grade: str, requester_role: str,
                            requester_id: str, target_employee_id: str,
                            requester_team_members: List[str] = None) -> bool:
        """Check if requester can access target employee's data"""
        access_level = cls.get_access_level(requester_grade, requester_role)
        permissions = cls.GRADE_PERMISSIONS[access_level]

        # Own data is always accessible
        if requester_id == target_employee_id:
            return True

        # L0, L1, L2 can access all employees
        if permissions["can_access_all_employees"]:
            return True

        # L3 (Supervisors) can only access team members
        if access_level == AccessLevel.L3:
            if requester_team_members and target_employee_id in requester_team_members:
                return True

        # L4 (Employees) can only access own data
        return False

    @classmethod
    def filter_employee_data(cls, requester_grade: str, requester_role: str,
                             employee_data: Dict) -> Dict:
        """Filter employee data based on access permissions"""
        access_level = cls.get_access_level(requester_grade, requester_role)
        permissions = cls.GRADE_PERMISSIONS[access_level]
        allowed_categories = permissions["allowed_data_categories"]

        filtered_data = {}

        # Always include basic identifiers
        basic_fields = ["_id", "firstName", "lastName", "userName"]
        for field in basic_fields:
            if field in employee_data:
                filtered_data[field] = employee_data[field]

        # Filter based on allowed categories
        if DataCategory.BASIC_INFO in allowed_categories:
            basic_info_fields = [
                "employeeInfo", "profession", "departmentId",
                "branchId", "organizationId", "role"
            ]
            for field in basic_info_fields:
                if field in employee_data:
                    filtered_data[field] = employee_data[field]

        if DataCategory.CONTACT_INFO in allowed_categories:
            contact_fields = ["email", "phoneNumber", "address"]
            for field in contact_fields:
                if field in employee_data:
                    filtered_data[field] = employee_data[field]

        if DataCategory.SALARY_INFO in allowed_categories:
            if "salaryInfo" in employee_data:
                filtered_data["salaryInfo"] = employee_data["salaryInfo"]

        if DataCategory.LEAVE_DATA in allowed_categories:
            if "leaveBalance" in employee_data:
                filtered_data["leaveBalance"] = employee_data["leaveBalance"]

        if DataCategory.BANKING_INFO in allowed_categories:
            if "bankingInfo" in employee_data:
                filtered_data["bankingInfo"] = employee_data["bankingInfo"]

        if DataCategory.FAMILY_INFO in allowed_categories:
            if "familyInfo" in employee_data:
                filtered_data["familyInfo"] = employee_data["familyInfo"]

        if DataCategory.DOCUMENTS in allowed_categories:
            if "documentsInfo" in employee_data:
                filtered_data["documentsInfo"] = employee_data["documentsInfo"]

        if DataCategory.CONTRACT_INFO in allowed_categories:
            if "contractInfo" in employee_data:
                filtered_data["contractInfo"] = employee_data["contractInfo"]

        if DataCategory.ASSETS_INFO in allowed_categories:
            if "assetsInfo" in employee_data:
                filtered_data["assetsInfo"] = employee_data["assetsInfo"]

        if DataCategory.LOAN_INFO in allowed_categories:
            if "loanInfo" in employee_data:
                filtered_data["loanInfo"] = employee_data["loanInfo"]

        return filtered_data

    @classmethod
    def get_access_summary(cls, grade: str, role: str = None) -> Dict:
        """Get a summary of what the user can access"""
        access_level = cls.get_access_level(grade, role)
        permissions = cls.GRADE_PERMISSIONS[access_level]

        return {
            "access_level": access_level.value,
            "can_access_all_employees": permissions["can_access_all_employees"],
            "allowed_data_categories": [cat.value for cat in permissions["allowed_data_categories"]]
        }
