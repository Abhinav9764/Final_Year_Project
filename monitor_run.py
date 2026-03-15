import requests
import time
import sys

def main():
    prompt = "build a housing price prediction model"
    print(f"Triggering pipeline with prompt: {prompt}")
    
    # 1. Trigger the job
    try:
        run_res = requests.post("http://localhost:5001/api/pipeline/run", json={"prompt": prompt})
        run_res.raise_for_status()
        data = run_res.json()
        job_id = data.get("job_id")
        if not job_id:
            print("Failed to get job_id")
            sys.exit(1)
        print(f"Started job ID: {job_id}")
    except Exception as e:
        print(f"Error starting pipeline: {e}")
        sys.exit(1)

    # 2. Monitor the job
    seen_logs = 0
    poll_interval = 2
    max_wait = 3600  # Up to 1 hour
    elapsed = 0
    
    while elapsed < max_wait:
        try:
            status_res = requests.get(f"http://localhost:5001/api/pipeline/status/{job_id}")
            status_res.raise_for_status()
            status_data = status_res.json()
            
            logs = status_data.get("logs", [])
            while seen_logs < len(logs):
                print(f"[Step {logs[seen_logs].get('step')}] {logs[seen_logs].get('message')}")
                seen_logs += 1
            
            status = status_data.get("status")
            if status in ["done", "error"]:
                print(f"Job completed with status: {status}")
                if status == "error":
                    print(f"Error details: {status_data.get('error')}")
                elif "result" in status_data:
                    print(f"Result details: {status_data.get('result')}")
                sys.exit(0 if status == "done" else 1)
                
            time.sleep(poll_interval)
            elapsed += poll_interval
        except Exception as e:
            print(f"Error polling status: {e}")
            time.sleep(poll_interval)
            elapsed += poll_interval
            
    print("Timeout waiting for job completion.")
    sys.exit(1)

if __name__ == "__main__":
    # Force stdout flush
    sys.stdout.reconfigure(line_buffering=True)
    main()
