#!/usr/bin/env python3
"""
Test script for production Hikvision attendance endpoint
Uses the actual data format that Hikvision devices send
"""

import requests
import json
from datetime import datetime

def test_production_hikvision_endpoint():
    """Test the production Hikvision attendance endpoint with realistic data"""
    
    # Production URL
    url = "https://hr.propertymetre.com/api/attendance/hikvision/receive/"
    
    # Test data matching the actual Hikvision format
    test_data = {
        'attendance_records': [
            {
                'timestamp': '2025-08-01T08:30:00+08:00',
                'employee_id': '001',
                'person_name': 'John Doe',
                'door_no': '1',
                'card_reader_no': '1',
                'serial_no': '123456789',
                'verify_mode': 'Face',
                'user_type': '1',
                'mask_status': '1',
                'major': 5,
                'minor': 75,
                'event_description': 'Access Granted (Valid Access)',
                'picture_url': '',
                'remote_host': '192.168.70.35'
            },
            {
                'timestamp': '2025-08-01T09:15:00+08:00',
                'employee_id': '002',
                'person_name': 'Jane Smith',
                'door_no': '1',
                'card_reader_no': '1',
                'serial_no': '123456790',
                'verify_mode': 'Card',
                'user_type': '1',
                'mask_status': '0',
                'major': 5,
                'minor': 75,
                'event_description': 'Access Granted (Valid Access)',
                'picture_url': '',
                'remote_host': '192.168.70.35'
            },
            {
                'timestamp': '2025-08-01T12:00:00+08:00',
                'employee_id': '003',
                'person_name': 'Mike Johnson',
                'door_no': '2',
                'card_reader_no': '2',
                'serial_no': '123456791',
                'verify_mode': 'Face',
                'user_type': '1',
                'mask_status': '1',
                'major': 5,
                'minor': 75,
                'event_description': 'Access Granted (Valid Access)',
                'picture_url': 'https://192.168.70.35/picture/123456791.jpg',
                'remote_host': '192.168.70.35'
            }
        ]
    }
    
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Hikvision-Test-Client/1.0'
    }
    
    print("Testing Production Hikvision Attendance Endpoint")
    print("=" * 50)
    print(f"URL: {url}")
    print(f"Sending {len(test_data['attendance_records'])} test records...")
    print()
    
    try:
        # Send the test data
        response = requests.post(
            url,
            json=test_data,
            headers=headers,
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print()
        
        if response.status_code == 200:
            try:
                result = response.json()
                print("✅ SUCCESS - Response JSON:")
                print(json.dumps(result, indent=2))
                
                if 'summary' in result:
                    summary = result['summary']
                    print(f"\n📊 Summary:")
                    print(f"  Total Records: {summary.get('total_records', 0)}")
                    print(f"  Created: {summary.get('created', 0)}")
                    print(f"  Updated: {summary.get('updated', 0)}")
                    print(f"  Skipped: {summary.get('skipped', 0)}")
                    
            except json.JSONDecodeError:
                print("✅ SUCCESS - Non-JSON Response:")
                print(response.text[:500])
                
        else:
            print(f"❌ FAILED - Status Code: {response.status_code}")
            print("Response:")
            try:
                error_data = response.json()
                print(json.dumps(error_data, indent=2))
            except json.JSONDecodeError:
                print(response.text[:500])
                
    except requests.exceptions.RequestException as e:
        print(f"❌ NETWORK ERROR: {e}")
        return False
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        return False
    
    return response.status_code == 200

def test_basic_connectivity():
    """Test basic connectivity to the production server"""
    print("\nTesting Basic Connectivity")
    print("-" * 30)
    
    try:
        # Test main site
        response = requests.get("https://hr.propertymetre.com", timeout=10)
        print(f"Main site status: {response.status_code}")
        
        # Test if we can reach the API endpoint with GET
        api_response = requests.get("https://hr.propertymetre.com/api/", timeout=10)
        print(f"API endpoint status: {api_response.status_code}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Connectivity test failed: {e}")
        return False

def main():
    print("Production Hikvision Endpoint Test")
    print("=" * 40)
    print(f"Test started at: {datetime.now()}")
    print()
    
    # Test basic connectivity first
    if not test_basic_connectivity():
        print("Basic connectivity test failed. Aborting.")
        return
    
    print()
    
    # Test the Hikvision endpoint
    success = test_production_hikvision_endpoint()
    
    print()
    print("=" * 40)
    if success:
        print("🎉 All tests passed!")
    else:
        print("❌ Some tests failed.")
    print(f"Test completed at: {datetime.now()}")

if __name__ == "__main__":
    main()
