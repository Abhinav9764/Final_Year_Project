import requests
import time
import sys
import json

if __name__ == "__main__":

    BASE_URL = "http://localhost:5001"

    print("1. Registering/Logging in...")
    try:
        requests.post(f"{BASE_URL}/api/auth/register", json={"username": "testrunner", "password": "password", "email": "test@example.com"})
    except Exception as e:
        pass

    r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "testrunner", "password": "password"})
    if not r.ok:
        print("Login failed:", r.text)
        sys.exit(1)

    token = r.json().get("token")
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful.")

    print("\n2. Starting pipeline...")
    prompt = "Build a binary classification model to predict customer churn based on age, tenure, and monthly charges."
    r = requests.post(f"{BASE_URL}/api/pipeline/run", json={"prompt": prompt}, headers=headers)
    if not r.ok:
        print("Pipeline start failed:", r.text)
        sys.exit(1)

    job_id = r.json().get("job_id")
    print("Job ID:", job_id)

    print("\n3. Polling status...")
    while True:
        try:
            r = requests.get(f"{BASE_URL}/api/pipeline/status/{job_id}", headers=headers)
            data = r.json()
            status = data.get("status")

            # safely print the latest log
            logs = data.get("logs", [])
            if logs:
                latest = logs[-1]
                if isinstance(latest, dict):
                    print(f"[{status}] {latest.get('step')}: {latest.get('message')}")
                else:
                    print(f"[{status}] {latest}")
            else:
                print(f"[{status}] ...")

            if status in ["done", "error"]:
                print("\n================ FINAL RESULT ================")
                print(json.dumps(data.get("result", {}), indent=2))
                if status == "error":
                    print("ERROR:", data.get("error"))
                else:
                    deploy_url = data.get("result", {}).get("deploy_url")
                    if deploy_url:
                        print(f"\nVerifying Streamlit app at {deploy_url}...")
                        try:
                            app_res = requests.get(deploy_url)
                            print(f"App status code: {app_res.status_code}")
                        except Exception as e:
                            print(f"Could not reach app: {e}")
                break

            time.sleep(5)
        except Exception as e:
            print("Polling error:", e)
            time.sleep(5)
