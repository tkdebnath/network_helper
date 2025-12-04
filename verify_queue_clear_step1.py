import requests
import sys
import time

BASE_URL = "http://127.0.0.1:8000"
API_KEY = "secure-api-key-123"

def verify_queue_clear():
    print("Verifying Queue Clearing...")
    
    # 1. Add item to queue
    print("Adding item to queue...")
    headers = {"access_token": API_KEY}
    payload = [{
        "device_name": "test-queue-clear",
        "ip_address": "1.1.1.1",
        "device_type": "ios"
    }]
    try:
        response = requests.post(f"{BASE_URL}/api/upgrade", json=payload, headers=headers)
        if response.status_code != 200:
            print(f"Failed to add item to queue: {response.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"Error connecting: {e}")
        sys.exit(1)

    # 2. Verify item is in queue
    print("Verifying item is in queue...")
    try:
        response = requests.get(f"{BASE_URL}/api/queue")
        queue = response.json()
        found = any(item["device_name"] == "test-queue-clear" for item in queue)
        if found:
            print("Item found in queue.")
        else:
            print("Item NOT found in queue (unexpected).")
            sys.exit(1)
    except Exception as e:
        print(f"Error connecting: {e}")
        sys.exit(1)

    print("Please restart the server now to trigger queue clearing...")
    # In a real test, we'd restart the server programmatically here, but since we are running this script
    # externally, we will just exit and let the agent handle the restart.
    
if __name__ == "__main__":
    verify_queue_clear()
