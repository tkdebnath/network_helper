import requests
import time
import sys
import asyncio

BASE_URL = "http://127.0.0.1:8000"

def verify_parallelism():
    print("Generating 10 devices...")
    payload = []
    for i in range(10):
        payload.append({
            "device_name": f"switch-parallel-{i}",
            "operation_type": "upgrade",
            "ip_address": f"192.168.1.{100+i}",
            "device_type": "cisco_ios",
            "target_version": "17.9.4"
        })

    print("Triggering bulk upgrade...")
    start_time = time.time()
    headers = {"access_token": "secure-api-key-123"}
    response = requests.post(f"{BASE_URL}/api/upgrade", json=payload, headers=headers)
    if response.status_code != 200:
        print(f"Failed to trigger upgrade: {response.text}")
        sys.exit(1)
    
    data = response.json()
    results = data["results"]
    task_ids = [r["task_id"] for r in results]
    print(f"Triggered {len(task_ids)} tasks.")
    
    # Poll until all are done
    completed_count = 0
    while completed_count < len(task_ids):
        completed_count = 0
        for task_id in task_ids:
            resp = requests.get(f"{BASE_URL}/api/status/{task_id}")
            status = resp.json()["status"]
            if status in ["completed", "failed", "error"]:
                completed_count += 1
                if status != "completed":
                    print(f"Task {task_id} failed with status {status}. Logs: {resp.json().get('log_output')}")
        
        elapsed = time.time() - start_time
        print(f"Elapsed: {elapsed:.2f}s, Completed: {completed_count}/{len(task_ids)}")
        
        if elapsed > 30: # Should take ~8-10s if parallel, ~80s if serial
            print("Time limit exceeded. Likely running serially.")
            break
            
        if completed_count == len(task_ids):
            print("All tasks completed!")
            break
            
        time.sleep(1)
        
    total_time = time.time() - start_time
    print(f"Total time taken: {total_time:.2f}s")
    
    if total_time < 20:
        print("SUCCESS: Tasks ran in parallel.")
    else:
        print("FAILURE: Tasks ran serially.")

if __name__ == "__main__":
    verify_parallelism()
