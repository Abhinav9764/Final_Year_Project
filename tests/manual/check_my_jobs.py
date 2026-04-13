import requests
import json
import sys

BASE_URL = "http://localhost:5001"
r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "testrunner", "password": "password"})
if not r.ok:
    print("Login failed:", r.text)
    sys.exit(1)

token = r.json().get("token")
headers = {"Authorization": f"Bearer {token}"}

r = requests.get(f"{BASE_URL}/api/history", headers=headers)
if not r.ok:
    print("History failed:", r.text)
else:
    print(json.dumps(r.json(), indent=2))
