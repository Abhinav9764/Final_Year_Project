import requests
import json
import time
import sys

def main():
    res = requests.post('http://127.0.0.1:5001/api/pipeline/run', json={'prompt':'build a housing price prediction model'})
    try:
        data = res.json()
        job_id = data['job_id']
    except Exception as e:
        print("Failed to start job:", res.text)
        sys.exit(1)
        
    print(f"Job started: {job_id}")
    prev = 0
    while True:
        try:
            r = requests.get(f"http://127.0.0.1:5001/api/pipeline/status/{job_id}")
            if r.status_code != 200:
                print("Bad status code:", r.status_code)
                break
            
            data = r.json()
            logs = data.get("logs", [])
            for l in logs[prev:]:
                print(l)
            prev = len(logs)
            
            status = data.get("status")
            if status in ["done", "error"]:
                with open("job_logs.json", "w") as f:
                    json.dump(data, f, indent=2)
                print("Job finished with status:", status)
                break
                
        except Exception as e:
            print("Error polling:", e)
            
        time.sleep(1)

if __name__ == '__main__':
    main()
