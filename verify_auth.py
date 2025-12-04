import requests
import sys

BASE_URL = "http://127.0.0.1:8000"
API_KEY = "secret"

def test_auth():
    print("Testing API Key Authentication...")
    
    # Test 1: POST without header (Should Fail)
    try:
        response = requests.post(f"{BASE_URL}/api/upgrade", json=[])
        if response.status_code == 403:
            print("PASS: POST without header failed as expected (403).")
        else:
            print(f"FAIL: POST without header returned {response.status_code}.")
    except Exception as e:
        print(f"Error connecting: {e}")

    # Test 2: POST with incorrect header (Should Fail)
    try:
        headers = {"access_token": "wrong_key"}
        response = requests.post(f"{BASE_URL}/api/upgrade", json=[], headers=headers)
        if response.status_code == 403:
            print("PASS: POST with incorrect header failed as expected (403).")
        else:
            print(f"FAIL: POST with incorrect header returned {response.status_code}.")
    except Exception as e:
        print(f"Error connecting: {e}")

    # Test 3: POST with correct header (Should Succeed - or at least pass auth)
    # Note: Sending empty list might return 200 with empty results, or 422 validation error if schema mismatch, 
    # but definitely NOT 403.
    try:
        headers = {"access_token": API_KEY}
        # Sending a valid dummy payload to avoid validation errors if possible
        payload = [{
            "device_name": "test-device",
            "ip_address": "1.1.1.1",
            "device_type": "ios"
        }]
        response = requests.post(f"{BASE_URL}/api/upgrade", json=payload, headers=headers)
        if response.status_code != 403:
            print(f"PASS: POST with correct header passed auth (Status: {response.status_code}).")
        else:
            print(f"FAIL: POST with correct header failed (403).")
    except Exception as e:
        print(f"Error connecting: {e}")

    # Test 4: GET request (Should NOT require auth)
    try:
        response = requests.get(f"{BASE_URL}/api/queue")
        if response.status_code == 200:
             print("PASS: GET request succeeded without auth (200).")
        else:
             print(f"FAIL: GET request returned {response.status_code}.")
    except Exception as e:
        print(f"Error connecting: {e}")

if __name__ == "__main__":
    test_auth()
