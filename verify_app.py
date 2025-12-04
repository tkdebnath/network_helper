import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_api():
    print("Waiting for server to start...")
    for _ in range(10):
        try:
            requests.get(f"{BASE_URL}/api/queue")
            break
        except requests.exceptions.ConnectionError:
            time.sleep(1)
    else:
        print("Server failed to start.")
        sys.exit(1)

    print("Server is up.")

    # 1. Trigger Upgrade
    print("Triggering upgrades for Warning and Error scenarios...")
    payload = [
        {
            "device_name": "switch-warning-01",
            "operation_type": "upgrade",
            "ip_address": "192.168.1.201",
            "device_type": "cisco_ios",
            "target_version": "17.9.4"
        },
        {
            "device_name": "switch-error-01",
            "operation_type": "upgrade",
            "ip_address": "192.168.1.202",
            "device_type": "cisco_ios",
            "target_version": "17.9.4"
        },
        {
            "device_name": "switch-precheck-01",
            "operation_type": "precheck",
            "ip_address": "192.168.1.203",
            "device_type": "cisco_ios"
        }
    ]
    resp = requests.post(f"{BASE_URL}/api/upgrade", json=payload)
    if resp.status_code != 200:
        print(f"Failed to trigger upgrade: {resp.text}")
        sys.exit(1)
    
    data = resp.json()
    print(f"Response: {data}")
    results = data["results"]
    if not results:
        print("No results returned")
        sys.exit(1)
        
    task_id = results[0]["task_id"]
    print(f"Upgrade triggered. Task ID: {task_id}")

    # 2. Check Queue
    print("Checking queue...")
    resp = requests.get(f"{BASE_URL}/api/queue")
    queue = resp.json()
    print(f"Queue: {queue}")
    
    # 3. Check Status loop
    print("Polling status...")
    for _ in range(20):
        resp = requests.get(f"{BASE_URL}/api/status/{task_id}")
        status = resp.json()
        print(f"Status: {status['status']}")
        if status['status'] in ["completed", "failed", "error", "warning"]:
            print(f"Task {task_id} finished with status: {status['status']}")
            logs = status.get('log_output', '')
            print(f"Logs: {logs[:50]}...")
            if "Free space available" in logs:
                print("Verified: 'Free space available' found in logs.")
            if "Target file exists in flash" in logs:
                print("Verified: 'Target file exists in flash' found in logs.")
            if "Precheck completed successfully" in logs:
                print("Verified: 'Precheck completed successfully' found in logs.")
            break
        
        # Check logs while running
        current_logs = status.get('log_output', '')
        if current_logs and "Connected to" in current_logs:
             print(f"Verified: Real-time log update detected ({len(current_logs)} chars).")
             
        time.sleep(1)
    else:
        print("Task timed out.")

    # 4. Check History
    print("Checking history...")
    resp = requests.get(f"{BASE_URL}/api/history")
    history = resp.json()
    print(f"History count: {len(history)}")

    print("Verification complete.")

    print("\n--- Verifying Precheck Files and Diff ---")
    device_name = "switch-precheck-01"

    # 1. List files (should have at least 1 from the run above)
    resp = requests.get(f"{BASE_URL}/api/prechecks/{device_name}")
    files = resp.json()
    print(f"Precheck files for {device_name}: {files}")
    if not files:
        print("Error: No precheck files found.")
        sys.exit(1)

    file1 = files[0]

    # 2. Trigger a second precheck to get a second file
    print("Triggering second precheck...")
    payload = [{
        "device_name": device_name,
        "operation_type": "precheck",
        "ip_address": "1.2.3.4",
        "device_type": "cisco_ios"
    }]
    resp = requests.post(f"{BASE_URL}/api/upgrade", json=payload)
    task_id = resp.json()['results'][0]['task_id']
    print(f"Second precheck task ID: {task_id}")

    # Poll for completion
    while True:
        resp = requests.get(f"{BASE_URL}/api/status/{task_id}")
        status = resp.json()['status']
        if status in ["completed", "failed", "error", "warning"]:
            print(f"Second precheck finished with status: {status}")
            break
        time.sleep(1)

    # 3. List files again (should have 2)
    resp = requests.get(f"{BASE_URL}/api/prechecks/{device_name}")
    files = resp.json()
    print(f"Precheck files for {device_name}: {files}")
    if len(files) < 2:
        print("Error: Expected at least 2 files.")
        sys.exit(1)

    file2 = files[0] # Newest
    file1 = files[1] # Older

    # 4. Download file1
    print(f"Downloading {file1}...")
    resp = requests.get(f"{BASE_URL}/api/prechecks/download/{file1}")
    if resp.status_code == 200:
        print(f"Download successful. Size: {len(resp.content)} bytes")
    else:
        print(f"Download failed: {resp.status_code}")

    # 5. Diff files
    print(f"Diffing {file1} and {file2}...")
    resp = requests.post(f"{BASE_URL}/api/prechecks/diff", json={"file1": file1, "file2": file2})
    if resp.status_code == 200:
        print("Diff successful. Response is HTML.")
        if "<html>" in resp.text:
            print("Verified: Response contains HTML.")
    else:
        print(f"Diff failed: {resp.status_code}")

    # 6. Verify Autocomplete Endpoint
    print("\n--- Verifying Autocomplete Endpoint ---")
    resp = requests.get(f"{BASE_URL}/api/prechecks/devices")
    devices = resp.json()
    print(f"Devices with prechecks: {devices}")
    if device_name in devices:
        print(f"Verified: '{device_name}' found in autocomplete list.")
    else:
        print(f"Error: '{device_name}' not found in autocomplete list.")
        sys.exit(1)

    # 7. Verify Case-Insensitive Precheck Fetch
    print("\n--- Verifying Case-Insensitive Precheck Fetch ---")
    mixed_case_name = "Switch-Precheck-01"
    print(f"Fetching prechecks for '{mixed_case_name}'...")
    resp = requests.get(f"{BASE_URL}/api/prechecks/{mixed_case_name}")
    files = resp.json()
    print(f"Files found: {files}")
    if files:
        print(f"Verified: Found {len(files)} files for mixed-case input.")
    else:
        print("Error: No files found for mixed-case input.")
        sys.exit(1)

if __name__ == "__main__":
    test_api()
