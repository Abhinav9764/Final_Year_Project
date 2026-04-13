"""
Detailed Status Check for Running Jobs
"""
import requests
import json
import time

BASE_URL = "http://localhost:5001/api"
HEADERS = {"Content-Type": "application/json"}

# Use token from previous test - registering new user
TEST_USERNAME = "status_check_user"
TEST_PASSWORD = "test_password_123"

def get_auth_token():
    """Get or create authentication token"""
    payload = {
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
        "email": f"{TEST_USERNAME}@radml.local"
    }
    
    # Try to register
    response = requests.post(f"{BASE_URL}/auth/register", json=payload, headers=HEADERS)
    if response.status_code in [200, 201]:
        return response.json().get("token")
    
    # If already exists, try login
    del payload["email"]
    response = requests.post(f"{BASE_URL}/auth/login", json=payload, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("access_token") or response.json().get("token")
    
    return None

def get_job_details(job_id, token):
    """Get detailed job information"""
    auth_headers = {**HEADERS, "Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/history/{job_id}", headers=auth_headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    print("=" * 70)
    print("DETAILED JOB STATUS CHECK".center(70))
    print("=" * 70)
    
    token = get_auth_token()
    if not token:
        print("Failed to get authentication token")
        return
    
    # Try to get history for jobs from first test user
    # Create a test user to get history
    test_payload = {
        "username": "test_user_54352",  # From previous test
        "password": "test_password_123"
    }
    
    # Try login with previous user
    response = requests.post(f"{BASE_URL}/auth/login", json=test_payload, headers=HEADERS)
    if response.status_code == 200:
        prev_token = response.json().get("token")
        print(f"\n✓ Logged in as test_user_54352")
        
        # Get job history
        auth_headers = {**HEADERS, "Authorization": f"Bearer {prev_token}"}
        response = requests.get(f"{BASE_URL}/history", headers=auth_headers)
        
        if response.status_code == 200:
            jobs = response.json().get("jobs", [])
            print(f"\n✓ Retrieved {len(jobs)} jobs\n")
            
            for i, job in enumerate(jobs, 1):
                job_id = job.get("id") or job.get("job_id")
                print(f"\n{i}. Job ID: {job_id}")
                print(f"   Status: {job.get('status')}")
                print(f"   Timestamp: {job.get('timestamp')}")
                print(f"   Prompt: {job.get('prompt', '')[:80]}...")
                
                # Get full details
                print(f"\n   Fetching detailed status...")
                time.sleep(0.5)
                
                detail_response = requests.get(f"{BASE_URL}/pipeline/status/{job_id}", 
                                             headers=auth_headers, timeout=10)
                if detail_response.status_code == 200:
                    details = detail_response.json()
                    print(f"   Detailed Status:")
                    print(f"     - Current Status: {details.get('status')}")
                    print(f"     - Progress: {details.get('progress', {})}")
                    
                    result = details.get('result', {})
                    if result:
                        print(f"   Results Available:")
                        print(f"     - Algorithm: {result.get('algorithm')}")
                        print(f"     - Accuracy: {result.get('accuracy')}")
                        if result.get('predictions'):
                            pred_count = len(result['predictions'])
                            print(f"     - Predictions: {pred_count} samples")
                            print(f"     - Sample: {result['predictions'][:3]}...")
                        print(f"     - Model: {result.get('model_file')}")

if __name__ == "__main__":
    main()
