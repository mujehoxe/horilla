#!/usr/bin/env python3
"""
Debug test script for local Hikvision integration
"""

import requests
import json

def test_local_debug():
    """Test the local endpoint with debug info"""
    
    # Sample attendance data
    test_data = {
        'attendance_records': [
            {
                'timestamp': '2025-08-01T08:30:00+08:00',
                'employee_id': '001',
                'person_name': 'Test Employee',  # Using a generic name
                'door_no': '1',
                'event_description': 'Access Granted (Valid Access)',
                'verify_mode': 'Face',
            }
        ]
    }
    
    url = "http://localhost:8001/api/attendance/hikvision/receive/"
    
    try:
        print("Testing local endpoint with debug...")
        print(f"URL: {url}")
        print(f"Sending test data: {json.dumps(test_data, indent=2)}")
        
        response = requests.post(
            url,
            json=test_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Detailed result: {json.dumps(result, indent=2)}")
            
            # Check the summary
            summary = result.get('summary', {})
            if summary.get('skipped', 0) > 0:
                print("\n⚠️ WARNING: Records were skipped!")
                print("This usually means:")
                print("1. No employee found with matching biometric_employee_name")
                print("2. Invalid timestamp format")
                print("3. Missing required fields")
        else:
            print("✗ Request failed!")
            
    except Exception as e:
        print(f"✗ Error: {e}")

def check_employees():
    """Check what employees exist in the database"""
    
    url = "http://localhost:8001/api/employee/"  # Assuming there's an employee API
    
    try:
        print("\nChecking existing employees...")
        
        response = requests.get(url, timeout=30)
        
        print(f"Employee API Status: {response.status_code}")
        if response.status_code == 200:
            employees = response.json()
            print(f"Found {len(employees.get('results', []))} employees")
            
            # Show first few employees for reference
            for emp in employees.get('results', [])[:3]:
                print(f"- {emp.get('employee_first_name', '')} {emp.get('employee_last_name', '')}")
                print(f"  biometric_employee_name: {emp.get('biometric_employee_name', 'NOT SET')}")
        else:
            print(f"Employee API not accessible: {response.text}")
            
    except Exception as e:
        print(f"Error checking employees: {e}")

if __name__ == "__main__":
    test_local_debug()
    check_employees()
