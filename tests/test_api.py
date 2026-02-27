#!/usr/bin/env python3
"""
Simple script to test the MQTT monitor API
"""
import requests
import json

def test_api():
    url = "http://127.0.0.1:8000/mqtt/monitor/api/"
    
    print("Testing MQTT Monitor API...")
    print(f"URL: {url}")
    print("-" * 50)
    
    try:
        # Make the request
        response = requests.get(url)
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Content Type: {response.headers.get('content-type', 'Unknown')}")
        print("-" * 50)
        
        # Try to parse as JSON
        try:
            data = response.json()
            print("JSON Response:")
            print(json.dumps(data, indent=2))
        except json.JSONDecodeError:
            print("Response is not JSON:")
            print(response.text[:500])  # First 500 characters
            
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to the server")
        print("Make sure Django is running on http://127.0.0.1:8000/")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_api()
