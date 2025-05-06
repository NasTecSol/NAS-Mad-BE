import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from utils.logger import logger

class AttendanceFormatter:
    @staticmethod
    def format_personal_attendance(attendance_data: List[Dict[str, Any]], date_range: Dict[str, str]) -> str:
        """Format personal attendance structured data into a structured response"""
        try:
            # Basic formatting if no attendance data
            logger.info(f"inititiating formatting PERSONAL response data{attendance_data}")
            if not attendance_data or not isinstance(attendance_data, list):
                return "No attendance data available for the requested period."
            
            # Calculate statistics
            stats = AttendanceFormatter._calculate_personal_stats(attendance_data)
            
            # Format date range description
            period_desc = AttendanceFormatter._get_period_description(date_range)
            
            # Build response
            response = f"Here's your attendance record for {period_desc}:\n"
            
            # Present days
            response += f"* Total Present Days: {len(stats['present_days'])}\n"
            
            # Absent days
            response += f"* Total Absent Days: {len(stats['absent_days'])}\n"
            if stats['absent_days']:
                for day in stats['absent_days']:
                    date_obj = datetime.strptime(day['date'], "%Y-%m-%d")
                    day_name = date_obj.strftime("%A")
                    response += f"   * {day['date']} - {day_name}\n"
            
            # Missing check-ins/outs
            response += f"* Total Missing Check In/Out: {len(stats['missing_check_in_out'])}\n"
            if stats['missing_check_in_out']:
                for day in stats['missing_check_in_out']:
                    date_obj = datetime.strptime(day['date'], "%Y-%m-%d")
                    day_name = date_obj.strftime("%A")
                    response += f"   * {day['date']} - {day_name}\n"
            
            # Late comings
            response += f"* Late Comings: {len(stats['late_comings'])}\n"
            if stats['late_comings']:
                for day in stats['late_comings']:
                    date_obj = datetime.strptime(day['date'], "%Y-%m-%d")
                    day_name = date_obj.strftime("%A")
                    response += f"   * {day['date']} - {day_name} - {day['late_minutes']} min\n"
            logger.info(f"Finished formatting response data{response}")
            # Add brief analysis
            response += AttendanceFormatter._generate_personal_analysis(stats)
            logger.info(f"Finished formatting response data{response}")
            return response
            
        except Exception as e:
            logger.error(f"Error formatting personal attendance: {str(e)}")
            return "Error formatting attendance data. Please try again."
    
    @staticmethod
    def format_team_attendance(attendance_data: List[Dict[str, Any]], team_data: Dict[str, Any], date_range: Dict[str, str]) -> str:
        """Format team attendance data into a structured response"""
        try:
            # Basic formatting if no attendance data
            if not attendance_data or not isinstance(attendance_data, list):
                return "No team attendance data available for the requested period."
            
            # Format date range description
            period_desc = AttendanceFormatter._get_period_description(date_range)
            
            # Group attendance data by employee
            attendance_by_employee = AttendanceFormatter._group_attendance_by_employee(attendance_data, team_data)
            logger.info(f"initiating formatting response data")
            # Build response
            response = f"Here's your team attendance record for {period_desc}:\n"
            
            # For each employee
            for emp_id, employee in attendance_by_employee.items():
                response += f"** {employee['name']} - {employee['employee_id']}\n"
                
                # Calculate stats for this employee
                stats = AttendanceFormatter._calculate_personal_stats(employee['attendance'])
                
                # Present days
                response += f"* Total Present Days: {len(stats['present_days'])}\n"
                
                # Absent days
                response += f"* Total Absent Days: {len(stats['absent_days'])}\n"
                if stats['absent_days']:
                    # Show at most 5 dates to keep response concise
                    display_days = stats['absent_days'][:5]
                    for day in display_days:
                        date_obj = datetime.strptime(day['date'], "%Y-%m-%d")
                        day_name = date_obj.strftime("%A")
                        response += f"   * {day['date']} - {day_name}\n"
                    if len(stats['absent_days']) > 5:
                        response += f"   * ... and {len(stats['absent_days']) - 5} more days\n"
                
                # Missing check-ins/outs
                response += f"* Total Missing Check In/Out: {len(stats['missing_check_in_out'])}\n"
                if stats['missing_check_in_out']:
                    # Show at most 5 dates to keep response concise
                    display_days = stats['missing_check_in_out'][:5]
                    for day in display_days:
                        date_obj = datetime.strptime(day['date'], "%Y-%m-%d")
                        day_name = date_obj.strftime("%A")
                        response += f"   * {day['date']} - {day_name}\n"
                    if len(stats['missing_check_in_out']) > 5:
                        response += f"   * ... and {len(stats['missing_check_in_out']) - 5} more days\n"
                
                # Late comings
                response += f"* Late Comings: {len(stats['late_comings'])}\n"
                if stats['late_comings']:
                    # Show at most 5 dates to keep response concise
                    display_days = stats['late_comings'][:5]
                    for day in display_days:
                        date_obj = datetime.strptime(day['date'], "%Y-%m-%d")
                        day_name = date_obj.strftime("%A")
                        response += f"   * {day['date']} - {day_name} - {day['late_minutes']} min\n"
                    if len(stats['late_comings']) > 5:
                        response += f"   * ... and {len(stats['late_comings']) - 5} more days\n"
            
            # Add brief team analysis
            response += AttendanceFormatter._generate_team_analysis(attendance_by_employee)
            logger.info(f"Finished formatting response data{response}")
            return response
            
        except Exception as e:
            logger.error(f"Error formatting team attendance: {str(e)}")
            return "Error formatting team attendance data. Please try again."
    
    # Helper methods
    @staticmethod
    def _calculate_personal_stats(attendance_data: List[Dict[str, Any]]) -> Dict[str, List]:
        """Calculate attendance statistics from raw data"""
        stats = {
            'present_days': [],
            'absent_days': [],
            'missing_check_in_out': [],
            'late_comings': [],
            'total_work_hours': 0
        }
        
        # Process each attendance record
        for day in attendance_data:
            # Format date consistently
            date = day.get('date') or (day.get('checkin', '').split('T')[0] if day.get('checkin') else None)
            
            if not date:
                continue  # Skip if no date found
            
            # Check status (present, absent, etc.)
            status = day.get('status', 'Unknown')
            
            if status.lower() == 'absent':
                stats['absent_days'].append({'date': date})
                continue
            
            # Check if present
            if status.lower() == 'present':
                # Calculate work hours if check in and out times exist
                work_hours = 0
                late_minutes = 0
                
                if day.get('checkin') and day.get('checkout'):
                    checkin_time = datetime.fromisoformat(day['checkin'].replace('Z', '+00:00'))
                    checkout_time = datetime.fromisoformat(day['checkout'].replace('Z', '+00:00'))
                    
                    # Calculate work hours
                    work_hours = (checkout_time - checkin_time).total_seconds() / 3600
                    stats['total_work_hours'] += work_hours
                    
                    # Check for late coming (if shiftStartTime exists)
                    if day.get('shiftStartTime'):
                        shift_start = datetime.strptime(f"{date}T{day['shiftStartTime']}", "%Y-%m-%dT%H:%M:%S")
                        if checkin_time > shift_start:
                            late_minutes = round((checkin_time - shift_start).total_seconds() / 60)
                            if late_minutes > 0:
                                stats['late_comings'].append({'date': date, 'late_minutes': late_minutes})
                    
                    stats['present_days'].append({'date': date, 'work_hours': work_hours})
                else:
                    # Missing check in or check out
                    stats['missing_check_in_out'].append({'date': date})
        
        return stats
    
    @staticmethod
    def _group_attendance_by_employee(attendance_data: List[Dict[str, Any]], team_data: Dict[str, Any]) -> Dict[str, Dict]:
        """Group attendance data by employee"""
        employee_map = {}
        
        # Create mapping of employee IDs to names
        employee_names = {}
        if team_data and team_data.get('teamData') and isinstance(team_data.get('teamData'), list):
            for employee in team_data['teamData']:
                if employee.get('employeeId') and employee.get('firstName'):
                    employee_names[employee['employeeId']] = f"{employee['firstName']} {employee.get('lastName', '')}".strip()
        
        # Group attendance data by employee
        for record in attendance_data:
            employee_id = record.get('employeeId', 'unknown')
            
            if employee_id not in employee_map:
                employee_map[employee_id] = {
                    'employee_id': employee_id,
                    'name': employee_names.get(employee_id, f"Employee {employee_id}"),
                    'attendance': []
                }
            
            employee_map[employee_id]['attendance'].append(record)
        
        return employee_map
    
    @staticmethod
    def _get_period_description(date_range: Dict[str, str]) -> str:
        """Generate a description of the date range"""
        start_date = datetime.strptime(date_range['start_date'], "%Y-%m-%d")
        end_date = datetime.strptime(date_range['end_date'], "%Y-%m-%d")
        
        # Today
        if date_range['start_date'] == date_range['end_date']:
            return f"today ({date_range['start_date']})"
        
        # This month
        current_month = datetime.now().month
        current_year = datetime.now().year
        if start_date.month == current_month and start_date.year == current_year:
            return f"this month ({start_date.strftime('%B %Y')})"
        
        # Custom range
        return f"from {date_range['start_date']} to {date_range['end_date']}"
    
    @staticmethod
    def _generate_personal_analysis(stats: Dict[str, List]) -> str:
        """Generate brief analysis of personal attendance"""
        analysis = "\nAttendance Analysis:\n"
        
        # Analyze present vs absent ratio
        total_days = len(stats['present_days']) + len(stats['absent_days'])
        if total_days > 0:
            present_percentage = round((len(stats['present_days']) / total_days) * 100)
            
            if present_percentage >= 90:
                analysis += f"✅ Excellent attendance rate! You've been present for {present_percentage}% of working days.\n"
            elif present_percentage >= 80:
                analysis += f"👍 Good attendance rate at {present_percentage}% of working days.\n"
            elif present_percentage >= 70:
                analysis += f"⚠️ Your attendance rate is {present_percentage}%, which could be improved.\n"
            else:
                analysis += f"❗ Your attendance rate is low at {present_percentage}%. Please try to improve.\n"
        
        # Analyze late comings
        if stats['late_comings']:
            if len(stats['late_comings']) > 3:
                analysis += f"❗ You have {len(stats['late_comings'])} late arrivals. Please try to arrive on time.\n"
            else:
                analysis += f"⚠️ You have {len(stats['late_comings'])} late arrival(s).\n"
        elif stats['present_days']:
            analysis += "✅ Great job arriving on time every day!\n"
        
        # Analyze missing check-ins/outs
        if stats['missing_check_in_out']:
            analysis += f"⚠️ You have {len(stats['missing_check_in_out'])} day(s) with missing check-in or check-out records.\n"
        
        return analysis
    
    @staticmethod
    def _generate_team_analysis(attendance_by_employee: Dict[str, Dict]) -> str:
        """Generate brief analysis of team attendance"""
        if not attendance_by_employee:
            return ""
        
        analysis = "\nTeam Attendance Analysis:\n"
        
        # Calculate team-wide statistics
        total_present_days = 0
        total_absent_days = 0
        total_late_comings = 0
        total_missing_check_in_out = 0
        employee_count = 0
        
        for employee_id, employee in attendance_by_employee.items():
            stats = AttendanceFormatter._calculate_personal_stats(employee['attendance'])
            total_present_days += len(stats['present_days'])
            total_absent_days += len(stats['absent_days'])
            total_late_comings += len(stats['late_comings'])
            total_missing_check_in_out += len(stats['missing_check_in_out'])
            employee_count += 1
        
        # Overall attendance rate
        total_days = total_present_days + total_absent_days
        if total_days > 0 and employee_count > 0:
            attendance_rate = round((total_present_days / total_days) * 100)
            analysis += f"➡️ Overall team attendance rate: {attendance_rate}%\n"
            
            # Average absences per employee
            avg_absences = round(total_absent_days / employee_count, 1)
            analysis += f"➡️ Average absences per team member: {avg_absences} days\n"
            
            # Average late comings per employee
            avg_late_comings = round(total_late_comings / employee_count, 1)
            if avg_late_comings > 0:
                analysis += f"➡️ Average late arrivals per team member: {avg_late_comings}\n"
        
        # Identify best attendance
        if len(attendance_by_employee) > 1:
            best_employee = None
            best_attendance_rate = 0
            
            for employee_id, employee in attendance_by_employee.items():
                stats = AttendanceFormatter._calculate_personal_stats(employee['attendance'])
                total_days = len(stats['present_days']) + len(stats['absent_days'])
                if total_days > 0:
                    rate = len(stats['present_days']) / total_days
                    if rate > best_attendance_rate:
                        best_attendance_rate = rate
                        best_employee = employee
            
            if best_employee and best_attendance_rate > 0.9:
                analysis += f"🏆 {best_employee['name']} has the best attendance record on your team.\n"
        
        return analysis