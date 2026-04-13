import requests
import time
import json

if __name__ == "__main__":

    BASE_URL = "http://localhost:5001/api"
    HEADERS = {"Content-Type": "application/json"}

    # Register/Login
    username = "test_user_recommend"
    password = "password123"

    # Try register
    requests.post(f"{BASE_URL}/auth/register", json={"username": username, "password": password, "email": "r@r.com"}, headers=HEADERS)
    # Login
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password}, headers=HEADERS)
    token = resp.json().get("access_token")

    auth_headers = {**HEADERS, "Authorization": f"Bearer {token}"}

    prompt = "Suggest the movies. input: rating. output: list of recommended movies"
    print(f"Triggering pipeline with prompt: {prompt}")

    res = requests.post(f"{BASE_URL}/pipeline/run", json={"prompt": prompt}, headers=auth_headers)
    job_id = res.json().get("job_id")
    print(f"Job ID: {job_id}")

    while True:
        status_res = requests.get(f"{BASE_URL}/pipeline/status/{job_id}", headers=auth_headers)
        data = status_res.json()
        print(f"Status: {data.get('status')} - Progress: {data.get('progress')}")
        if data.get('status') in ['completed', 'failed']:
            print("Final result:", json.dumps(data, indent=2))
            break
        time.sleep(5)
