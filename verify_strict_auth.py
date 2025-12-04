import requests
import sys

BASE_URL = "http://127.0.0.1:8000"
API_KEY = "secure-api-key-123"

def test_auth():
    print("Testing Strict API Key Authentication...")
    
    # Test 1: POST with OLD default key (Should Fail)
    try:
        headers = {"access_token": "secret"}
        response = requests.post(f"{BASE_URL}/api/upgrade", json=[], headers=headers)
        if response.status_code == 403:
            print("PASS: POST with old default key 'secret' failed (403).")
        else:
            print(f"FAIL: POST with old default key returned {response.status_code}.")
    except Exception as e:
        print(f"Error connecting: {e}")

    # Test 2: POST with NEW env key (Should Succeed)
    try:
        headers = {"access_token": API_KEY}
        payload = [{
            "device_name": "test-device",
            "ip_address": "1.1.1.1",
            "device_type": "ios"
        }]
        response = requests.post(f"{BASE_URL}/api/upgrade", json=payload, headers=headers)
        if response.status_code != 403:
            print(f"PASS: POST with new env key passed auth (Status: {response.status_code}).")
        else:
            print(f"FAIL: POST with new env key failed (403).")
    except Exception as e:
        print(f"Error connecting: {e}")

if __name__ == "__main__":
    test_auth()
