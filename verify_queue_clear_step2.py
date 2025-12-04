import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def verify_queue_empty():
    print("Verifying Queue is Empty...")
    try:
        response = requests.get(f"{BASE_URL}/api/queue")
        queue = response.json()
        if len(queue) == 0:
            print("SUCCESS: Queue is empty.")
        else:
            print(f"FAILURE: Queue is not empty. Found {len(queue)} items.")
            print(queue)
    except Exception as e:
        print(f"Error connecting: {e}")

if __name__ == "__main__":
    verify_queue_empty()
