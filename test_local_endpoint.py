#!/usr/bin/env python3
"""
Test script for local Hikvision integration endpoint
"""

import requests
import json

def test_local_endpoint():
    """Test the local endpoint with sample data"""
    
    # Sample attendance data
    test_data = {
        'attendance_records': [
            {
                'timestamp': '2025-08-01T08:30:00+08:00',
                'employee_id': '001',
                'person_name': 'John Doe',
                'door_no': '1',
                'event_description': 'Access Granted (Valid Access)',
                'verify_mode': 'Face',
            }
        ]
    }
    
    url = "http://localhost:8001/api/attendance/hikvision/receive/"
    
    try:
        print("Testing local endpoint...")
        print(f"URL: {url}")
        print(f"Sending {len(test_data['attendance_records'])} test records...")
        
        # Allow redirects and track them
        response = requests.post(
            url,
            json=test_data,
            headers={'Content-Type': 'application/json'},
            timeout=30,
            allow_redirects=True
        )
        
        print(f"Final URL: {response.url}")
        print(f"History: {[r.url for r in response.history]}")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✓ Local endpoint test successful!")
            result = response.json()
            print(f"Result: {json.dumps(result, indent=2)}")
        else:
            print("✗ Local endpoint test failed!")
            
    except Exception as e:
        print(f"✗ Error testing local endpoint: {e}")

def test_remote_with_redirects():
    """Test remote endpoint tracking redirects"""
    
    test_data = {
        'attendance_records': [
            {
                'timestamp': '2025-08-01T08:30:00+08:00',
                'employee_id': '001',
                'person_name': 'Test User',
                'door_no': '1',
                'event_description': 'Access Granted (Valid Access)',
                'verify_mode': 'Face',
            }
        ]
    }
    
    url = "http://hr.propertymetre.com/api/attendance/hikvision/receive/"
    
    try:
        print("\nTesting remote endpoint with redirect tracking...")
        print(f"URL: {url}")
        
        # Disable redirects first to see what happens
        response = requests.post(
            url,
            json=test_data,
            headers={'Content-Type': 'application/json'},
            timeout=30,
            allow_redirects=False
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Response: {response.text}")
        
        if response.status_code in [301, 302, 303, 307, 308]:
            print(f"Redirect detected to: {response.headers.get('Location')}")
            
    except Exception as e:
        print(f"✗ Error testing remote endpoint: {e}")

if __name__ == "__main__":
    test_local_endpoint()
    test_remote_with_redirects()
