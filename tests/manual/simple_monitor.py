"""
Simple Job Monitor - Check pipeline execution status
"""
import requests
import json

BASE_URL = "http://localhost:5001/api"

def check_single_job(job_id):
    """Check status of a single job"""
    try:
        # Try without auth first (might work)
        response = requests.get(f"{BASE_URL}/pipeline/status/{job_id}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"Job {job_id}:")
            print(f"  Status: {data.get('status')}")
            if 'result' in data and data['result']:
                print(f"  Result: Available")
                print(f"    Algorithm: {data['result'].get('algorithm')}")
                print(f"    Accuracy: {data['result'].get('accuracy')}")
            return True
    except:
        pass
    return False

# Known job IDs from previous test
job_ids = [
    "b925212b-8d2",
    "35dd735b-26e", 
    "50aefdc2-383",
    "9874f46a-0cb"
]

print("=" * 50)
print("PIPELINE JOBS STATUS CHECK")
print("=" * 50)
print()

for jid in job_ids:
    check_single_job(jid)
    print()
