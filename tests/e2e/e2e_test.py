"""
End-to-End ML Pipeline Testing
Tests: Auth, Pipeline Execution, Predictions, Model Output
"""
import requests
import json
import time
import sys
import random
from datetime import datetime

BASE_URL = "http://localhost:5001/api"
HEADERS = {"Content-Type": "application/json"}

# Test user credentials
import random
TEST_USERNAME = f"test_user_{random.randint(10000, 99999)}"
TEST_PASSWORD = "test_password_123"
TEST_EMAIL = f"test_{random.randint(10000, 99999)}@radml.local"

# Test data - Various ML scenarios
TEST_PROMPTS = [
    {
        "name": "Classification Task",
        "prompt": "Build a machine learning model to classify iris flowers using the iris dataset. The model should predict flower species (setosa, versicolor, virginica) based on sepal length, sepal width, petal length, and petal width."
    },
    {
        "name": "Regression Task",
        "prompt": "Create a regression model to predict house prices using features like square footage, number of bedrooms, bathrooms, and location. Use a dataset with at least 500 samples."
    },
    {
        "name": "Binary Classification",
        "prompt": "Build a binary classifier to detect spam emails. Use email text features and train on a balanced dataset with spam and non-spam messages."
    },
    {
        "name": "Multi-class Prediction",
        "prompt": "Create a model to classify handwritten digits (0-9) using image data. Implement a neural network with at least 2 hidden layers."
    },
]

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{msg:^60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

def print_success(msg):
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")

def print_error(msg):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")

def print_info(msg):
    print(f"{Colors.OKCYAN}ℹ {msg}{Colors.ENDC}")

def print_warning(msg):
    print(f"{Colors.WARNING}⚠ {msg}{Colors.ENDC}")

def test_health():
    """Test backend health check"""
    print_header("TESTING BACKEND HEALTH")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success(f"Backend is running: {data}")
            return True
        else:
            print_error(f"Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Cannot connect to backend: {e}")
        return False

def test_register():
    """Test user registration"""
    print_header("TESTING USER REGISTRATION")
    url = f"{BASE_URL}/auth/register"
    payload = {
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
        "email": TEST_EMAIL
    }
    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        if response.status_code in [200, 201]:
            data = response.json()
            token = data.get("token")
            print_success(f"User registered successfully")
            print_info(f"Response: {data}")
            return token  # Return the token from registration
        elif response.status_code == 409:
            print_warning(f"User already exists (which is fine for this test)")
            return None  # Need to login separately
        else:
            print_error(f"Registration failed: {response.status_code}")
            print_info(f"Response: {response.text}")
            return None
    except Exception as e:
        print_error(f"Registration error: {e}")
        return None

def test_login():
    """Test user login"""
    print_header("TESTING USER LOGIN")
    url = f"{BASE_URL}/auth/login"
    payload = {
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD
    }
    try:
        response = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            if token:
                print_success(f"User logged in successfully")
                print_info(f"Token: {token[:50]}...")
                return token
            else:
                print_error("No token in response")
                return None
        else:
            print_error(f"Login failed: {response.status_code}")
            print_info(f"Response: {response.text}")
            return None
    except Exception as e:
        print_error(f"Login error: {e}")
        return None

def run_pipeline_test(token, test_prompt):
    """Run a pipeline test with a specific prompt"""
    print_header(f"RUNNING PIPELINE TEST: {test_prompt['name']}")
    print_info(f"Prompt: {test_prompt['prompt'][:100]}...")
    
    # Prepare headers with auth token
    auth_headers = {**HEADERS, "Authorization": f"Bearer {token}"}
    
    # Step 1: Submit pipeline run
    print_info("Step 1: Submitting pipeline request...")
    run_url = f"{BASE_URL}/pipeline/run"
    payload = {"prompt": test_prompt["prompt"]}
    
    try:
        response = requests.post(run_url, json=payload, headers=auth_headers, timeout=30)
        if response.status_code != 200:
            print_error(f"Pipeline submission failed: {response.status_code}")
            print_info(f"Response: {response.text}")
            return None
        
        job_data = response.json()
        job_id = job_data.get("job_id")
        if not job_id:
            print_error("No job_id in response")
            return None
        
        print_success(f"Pipeline submitted with job_id: {job_id}")
        print_info(f"Response: {json.dumps(job_data, indent=2)}")
        
    except Exception as e:
        print_error(f"Pipeline submission error: {e}")
        return None
    
    # Step 2: Poll for status
    print_info("Step 2: Monitoring pipeline execution...")
    status_url = f"{BASE_URL}/pipeline/status/{job_id}"
    max_wait = 120  # seconds
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(status_url, headers=auth_headers, timeout=10)
            if response.status_code == 200:
                status_data = response.json()
                status = status_data.get("status", "unknown")
                progress = status_data.get("progress", {})
                
                print_info(f"Status: {status} | Progress: {progress}")
                
                if status == "completed":
                    print_success("Pipeline execution completed!")
                    
                    # Extract results
                    result = status_data.get("result", {})
                    if result:
                        print_info(f"Results Summary:")
                        print_info(f"  - Algorithm: {result.get('algorithm', 'N/A')}")
                        print_info(f"  - Accuracy: {result.get('accuracy', 'N/A')}")
                        print_info(f"  - Model: {result.get('model_file', 'N/A')}")
                        
                        # Check for predictions
                        if result.get('predictions'):
                            print_success(f"  - Predictions: {len(result['predictions'])} samples predicted")
                            print_info(f"  - Sample predictions: {result['predictions'][:5]}")
                    
                    return job_id
                
                elif status == "failed":
                    error_msg = status_data.get("error", "Unknown error")
                    print_error(f"Pipeline failed: {error_msg}")
                    return None
                
                elif status in ["running", "queued", "processing"]:
                    elapsed = int(time.time() - start_time)
                    print_info(f"Waiting... ({elapsed}s)")
                    time.sleep(5)  # Check every 5 seconds
                else:
                    print_warning(f"Unknown status: {status}")
                    time.sleep(5)
            else:
                print_warning(f"Status check returned: {response.status_code}")
                time.sleep(5)
        
        except requests.exceptions.Timeout:
            print_warning("Status check timed out, retrying...")
            time.sleep(5)
        except Exception as e:
            print_error(f"Status check error: {e}")
            time.sleep(5)
    
    print_warning(f"Pipeline did not complete within {max_wait} seconds")
    return None

def get_job_history(token):
    """Retrieve job history"""
    print_header("RETRIEVING JOB HISTORY")
    auth_headers = {**HEADERS, "Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/history", headers=auth_headers, timeout=10)
        if response.status_code == 200:
            jobs = response.json().get("jobs", [])
            print_success(f"Retrieved {len(jobs)} jobs from history")
            
            if jobs:
                print_info("Job History:")
                for job in jobs[:5]:  # Show last 5
                    job_id = job.get("id") or job.get("job_id")
                    status = job.get("status")
                    timestamp = job.get("timestamp")
                    print_info(f"  - {job_id}: {status} ({timestamp})")
            
            return jobs
        else:
            print_error(f"Failed to retrieve history: {response.status_code}")
            return None
    except Exception as e:
        print_error(f"History retrieval error: {e}")
        return None

def main():
    """Run all tests"""
    print(f"\n{Colors.BOLD}RAD-ML END-TO-END TEST SUITE{Colors.ENDC}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test backend health
    if not test_health():
        print_error("Backend is not running. Please start the backend first.")
        sys.exit(1)
    
    time.sleep(2)
    
    # Test registration
    token = test_register()
    
    # If registration didn't return token, try login
    if not token:
        print_info("Attempting login...")
        token = test_login()
    
    if not token:
        print_error("Could not obtain authentication token. Cannot continue tests.")
        sys.exit(1)
    
    time.sleep(1)
    
    # Run pipeline tests with different prompts
    completed_jobs = []
    for i, test_prompt in enumerate(TEST_PROMPTS, 1):
        print_info(f"\nRunning test {i}/{len(TEST_PROMPTS)}...")
        job_id = run_pipeline_test(token, test_prompt)
        
        if job_id:
            completed_jobs.append({
                "name": test_prompt["name"],
                "job_id": job_id
            })
        
        if i < len(TEST_PROMPTS):
            print_info("Waiting 10 seconds before next test...")
            time.sleep(10)
    
    time.sleep(2)
    
    # Get final history
    get_job_history(token)
    
    # Summary
    print_header("TEST SUMMARY")
    print_info(f"Total tests run: {len(TEST_PROMPTS)}")
    print_info(f"Successful completions: {len(completed_jobs)}")
    
    if completed_jobs:
        print_success("Completed Jobs:")
        for job in completed_jobs:
            print_success(f"  ✓ {job['name']} (ID: {job['job_id']})")
    
    print_info(f"\nTest completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_success("End-to-end testing completed!")

if __name__ == "__main__":
    main()
