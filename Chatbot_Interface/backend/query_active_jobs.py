import requests
import json
import sys

BASE_URL = "http://127.0.0.1:5001/api"
HEADERS = {"Content-Type": "application/json"}

# 1. Login
resp = requests.post(f"{BASE_URL}/auth/login", json={"username": "Abhinav", "password": "Abhinav123"}, headers=HEADERS)
if resp.status_code != 200:
    print(f"Login failed: {resp.text}")
    sys.exit(1)

token = resp.json().get("token")
auth_headers = {**HEADERS, "Authorization": f"Bearer {token}"}

# 2. Get active jobs
history_resp = requests.get(f"{BASE_URL}/history", headers=auth_headers)
if history_resp.status_code != 200:
    print(f"History failed: {history_resp.text}")
    sys.exit(1)

jobs = history_resp.json().get("jobs", [])
print(f"Found {len(jobs)} jobs in history.")

for job in jobs[:5]:
    status = job.get('status')
    job_id = job.get('job_id') or job.get('id')
    print(f"Job {job_id}: {status} - {job.get('prompt')}")
    
    if status == 'running':
        print(f"--> Querying logs for running job {job_id}")
        status_resp = requests.get(f"{BASE_URL}/pipeline/status/{job_id}", headers=auth_headers)
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            logs = status_data.get('logs', [])
            print(f"    Total log entries: {len(logs)}")
            if logs:
                print(f"    Last 3 logs:")
                for log in logs[-3:]:
                    print(f"      [{log.get('step')}] {log.get('message')}")
        else:
            print(f"    Failed to get status: {status_resp.text}")
