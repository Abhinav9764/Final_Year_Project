import requests

BASE_URL = "http://localhost:5001/api"
HEADERS = {"Content-Type": "application/json"}

# Test login
resp = requests.post(f"{BASE_URL}/auth/login", json={"username": "test_user_recommend", "password": "password123"}, headers=HEADERS)
print(f"Status Code: {resp.status_code}")
print(f"Response: {resp.text}")
