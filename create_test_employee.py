#!/usr/bin/env python3
"""
Create a test employee and sync attendance
"""

import os
import sys
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'horilla.settings')
django.setup()

from employee.models import Employee
from attendance.models import Attendance
import requests
import json
from datetime import date

def create_test_employee():
    """Create a test employee with biometric name"""
    
    # Check if test employee already exists
    existing = Employee.objects.filter(biometric_employee_name="Test Employee").first()
    if existing:
        print(f"Test employee already exists: {existing.get_full_name()}")
        return existing
    
    # Create new test employee
    employee = Employee.objects.create(
        employee_first_name="Test",
        employee_last_name="Employee", 
        email="test.employee@company.com",
        phone="1234567890",
        biometric_employee_name="Test Employee"
    )
    
    print(f"Created test employee: {employee.get_full_name()}")
    print(f"Biometric name: {employee.biometric_employee_name}")
    return employee

def test_attendance_sync():
    """Test the attendance sync with real employee"""
    
    test_data = {
        'attendance_records': [
            {
                'timestamp': '2025-08-01T08:30:00+08:00',
                'employee_id': '001',
                'person_name': 'Test Employee',  # This should now match
                'door_no': '1',
                'event_description': 'Access Granted (Valid Access)',
                'verify_mode': 'Face',
            }
        ]
    }
    
    url = "http://localhost:8001/api/attendance/hikvision/receive/"
    
    try:
        print("\nTesting attendance sync with real employee...")
        
        response = requests.post(
            url,
            json=test_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if result.get('summary', {}).get('created', 0) > 0:
            print("✅ SUCCESS: Attendance record created!")
            
            # Check if record exists in database
            today = date.today()
            attendance = Attendance.objects.filter(
                employee_id__biometric_employee_name="Test Employee",
                attendance_date=today
            ).first()
            
            if attendance:
                print(f"✅ Verified: Attendance record found in database")
                print(f"   Employee: {attendance.employee_id.get_full_name()}")
                print(f"   Date: {attendance.attendance_date}")
                print(f"   Check-in: {attendance.attendance_clock_in}")
            else:
                print("❌ Error: No attendance record found in database")
        else:
            print("❌ FAILED: No attendance record created")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def show_all_employees():
    """Show all employees and their biometric names"""
    print("\nAll employees in database:")
    employees = Employee.objects.all()[:10]  # Show first 10
    
    for emp in employees:
        print(f"- {emp.get_full_name()}")
        print(f"  biometric_employee_name: '{emp.biometric_employee_name or 'NOT SET'}'")
        print()

if __name__ == "__main__":
    print("Setting up test employee and testing attendance sync...")
    
    # Show existing employees
    show_all_employees()
    
    # Create test employee
    create_test_employee()
    
    # Test attendance sync
    test_attendance_sync()
