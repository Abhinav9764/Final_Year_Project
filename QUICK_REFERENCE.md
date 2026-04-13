# RAD-ML Quick Reference & Common Operations

## 🚀 Starting the System

### Development Mode (all in one)

```bash
# Terminal 1: Backend
cd Chatbot_Interface/backend
python app.py
# Runs on http://localhost:5001

# Terminal 2: Frontend
cd Chatbot_Interface/frontend
npm run dev
# Runs on http://localhost:5173
```

### Access Points
- **Frontend UI**: http://localhost:5173
- **Backend API**: http://localhost:5001
- **Backend Health**: http://localhost:5001/api/health

---

## 🧪 Testing

### Basic Test Commands

```bash
# Run all tests
pytest tests/ -v

# Run unit tests only (no integration)
pytest tests/test_*.py -v

# Run specific test
pytest tests/test_prompt_parser.py::test_regression_intent -v

# Run with coverage report
pytest tests/ --cov=Data_Collection_Agent --cov=Code_Generator --cov-report=html

# Run integration tests (requires backend + frontend running)
pytest tests/SampleTests/ -v
```

### Test Files Quick Guide

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_prompt_parser.py` | Intent detection, keyword extraction | Data Collection Agent brain |
| `test_dataset_scorer.py` | Scoring formula, row/keyword/column weights | Dataset scoring logic |
| `test_dataset_merger.py` | Merging datasets, deduplication | Dataset merger logic |
| `test_kaggle_collector.py` | Search/download (mocked) | Kaggle API wrapper |
| `test_codegen_pipeline.py` | 5-layer pipeline, mocked LLM | Code generation layers |
| `test_explainability.py` | Narrative, diagrams, algorithm cards | Explanation engine |
| `test_complete_system_integration.py` | Full end-to-end flow | All components together |

---

## 📝 Common Code Snippets

### 1. Call Data Collection Agent Directly

```python
from Data_Collection_Agent.main import run_collection
import yaml

with open("config.yaml") as f:
    config = yaml.safe_load(f)

result = run_collection(
    prompt="Predict housing prices based on bedrooms and location",
    config=config,
    job_id="test_job_001",
    log_fn=lambda step, msg: print(f"[{step}] {msg}")
)

print(f"Dataset rows: {result['dataset']['row_count']}")
print(f"Columns: {result['dataset']['columns']}")
print(f"S3 URI: {result['dataset']['s3_uri']}")
```

### 2. Call Code Generator Directly

```python
from Code_Generator.RAD_ML.main import run_codegen

cg_result = run_codegen(
    db_results=result,  # from Data Collection Agent
    config=config,
    job_id="test_job_001",
    log_fn=lambda step, msg: print(f"[{step}] {msg}")
)

print(f"Generated files: {list(cg_result['generated_files'].keys())}")
print(f"Endpoint: {cg_result['endpoint_name']}")
```

### 3. Use Orchestrator (Production)

```python
from Chatbot_Interface.backend.orchestrator import Orchestrator
import time

orc = Orchestrator(config)

# Create and start job
job_id = orc.create_job("Build an ML model to predict customer churn")
orc.start_pipeline(job_id, user_id=123)

# Poll status
while True:
    job = orc.get_job(job_id)
    if job.status == "done":
        print("✓ Success!")
        print(f"Result: {job.result}")
        break
    elif job.status == "error":
        print(f"✗ Failed: {job.error}")
        break
    print(f"Status: {job.status}")
    time.sleep(2)
```

### 4. Test Prompt Parser

```python
from Data_Collection_Agent.brain.prompt_parser import PromptParser

parser = PromptParser()

# Test 1: Regression
spec = parser.parse("Predict house prices from bedrooms and location")
print(f"Task type: {spec['task_type']}")  # "regression"
print(f"Keywords: {spec['keywords']}")    # ["house", "price", "bedrooms"]
print(f"Target: {spec['target_param']}")  # "price"

# Test 2: Classification
spec = parser.parse("Classify emails as spam or not spam")
print(f"Task type: {spec['task_type']}")  # "classification"

# Test 3: Chatbot
spec = parser.parse("Build a chatbot for FAQ")
print(f"Intent: {spec['intent']}")        # "chatbot"
```

### 5. Dataset Scoring

```python
from Data_Collection_Agent.utils.dataset_scorer import DatasetScorer

config = {
    "scoring": {
        "keyword_match_weight": 0.40,
        "row_count_weight": 0.30,
        "column_match_weight": 0.20,
        "recency_weight": 0.10,
    }
}
scorer = DatasetScorer(config)

# Score metadata
meta = {
    "title": "California Housing Prices Dataset",
    "ref": "camnugent/california-housing-prices",
    "num_instances": 20640,
    "vote_count": 500,
}
spec = {
    "keywords": ["housing", "price", "california"],
    "input_params": ["longitude", "latitude"],
}
score = scorer.score_metadata(meta, spec)
print(f"Score: {score:.3f}")  # 0-1 range
```

### 6. Backend API Calls (curl)

```bash
# Register user
curl -X POST http://localhost:5001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "test_user", "password": "password123", "email": "test@example.com"}'

# Login
curl -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "test_user", "password": "password123"}'
# Returns: {"ok": true, "token": "eyJ...", "user": {...}}

# Create job
curl -X POST http://localhost:5001/api/pipeline/run \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Predict house prices"}'
# Returns: {"ok": true, "job_id": "abc123"}

# Check status
curl -X GET http://localhost:5001/api/pipeline/status/abc123 \
  -H "Authorization: Bearer <token>"

# Stream logs (SSE)
curl -X GET http://localhost:5001/api/pipeline/stream/abc123 \
  -H "Authorization: Bearer <token>"

# Get history
curl -X GET http://localhost:5001/api/history \
  -H "Authorization: Bearer <token>"

# Delete job from history
curl -X DELETE http://localhost:5001/api/history/abc123 \
  -H "Authorization: Bearer <token>"
```

### 7. Backend API Calls (Python requests)

```python
import requests
import json

BASE_URL = "http://localhost:5001"

# Register
resp = requests.post(f"{BASE_URL}/api/auth/register", json={
    "username": "test_user",
    "password": "pass123",
})
token = resp.json()["token"]

# Create job
headers = {"Authorization": f"Bearer {token}"}
resp = requests.post(f"{BASE_URL}/api/pipeline/run", 
    headers=headers,
    json={"prompt": "Predict house prices"}
)
job_id = resp.json()["job_id"]

# Poll status
while True:
    resp = requests.get(f"{BASE_URL}/api/pipeline/status/{job_id}", headers=headers)
    job = resp.json()
    print(f"Status: {job['status']}")
    
    if job['status'] == "done":
        print(f"Result: {job['result']}")
        break
    elif job['status'] == "error":
        print(f"Error: {job['error']}")
        break
    
    import time
    time.sleep(2)
```

---

## 🔧 Configuration (config.yaml)

### Minimal Config (dev mode, mock SageMaker)

```yaml
# config.yaml

# Data Collection
kaggle:
  username: ""        # Optional for dev
  key: ""             # Optional for dev

# AWS (optional for dev)
aws:
  region: "us-east-1"
  s3_bucket: ""       # Optional for dev
  sagemaker_role: ""  # Optional for dev

# LLM (Gemini API)
llm:
  gemini_api_key: ""  # Optional for dev (mock mode)

# Auth
auth:
  jwt_secret_key: "dev-secret-change-this"
  sqlite_path: "data/users.db"
  jwt_expires_hours: 24

# Code Generation
codegen:
  workspace_dir: "generated"
  flask_port: 7000
  max_fix_attempts: 5
  
# Logging
logging:
  console_level: "INFO"
  log_file: "logs/rad_ml.log"
```

### Production Config (with real credentials)

```yaml
kaggle:
  username: "your_kaggle_username"
  key: "your_kaggle_api_key"

aws:
  region: "us-east-1"
  s3_bucket: "your-ml-bucket"
  sagemaker_role: "arn:aws:iam::123456789:role/SageMakerExecutionRole"

llm:
  gemini_api_key: "your_gemini_api_key"

auth:
  jwt_secret_key: "very-long-random-secret-string-here"
  sqlite_path: "data/users.db"
  jwt_expires_hours: 24
  google_client_id: "your_google_client_id"  # Optional

codegen:
  workspace_dir: "/path/to/generated"
  flask_port: 7000
  max_fix_attempts: 5

collection:
  min_row_threshold: 500

scoring:
  keyword_match_weight: 0.40
  row_count_weight: 0.30
  column_match_weight: 0.20
  recency_weight: 0.10

logging:
  console_level: "WARNING"
  log_file: "logs/rad_ml.log"
```

---

## 📊 Data Flow Diagram

```
User Prompt
    │
    ├─ Auth Layer ────────────────────────────────┐
    │                                               │
    ▼                                               │
[Chat UI - Frontend]                               │
    │                                               │
    │ POST /api/pipeline/run                        │
    │ {prompt: string}                              │
    ▼                                               │
[Backend Flask API]────────────────────────────────┘
    │
    ├─ create_job(prompt) → job_id
    ├─ start_pipeline(job_id) [async, background thread]
    │
    ▼ [Thread]
[Orchestrator._run_pipeline]
    │
    ├─ if user_uploaded_dataset:
    │   └─ load CSV
    ├─ else:
    │   └─ run_collection(prompt)
    │       ├─ Parse prompt (PromptParser)
    │       ├─ Search Kaggle/UCI/OpenML
    │       ├─ Score & rank results
    │       ├─ Download top candidates
    │       ├─ Merge datasets
    │       └─ Upload to S3
    │
    ├─ run_codegen(db_results)
    │   ├─ Preprocess data
    │   ├─ Upload to S3
    │   ├─ Launch SageMaker training
    │   ├─ Layer 1: Prompt Understanding
    │   ├─ Layer 2: Architecture Planning
    │   ├─ Layer 3: Code Generation
    │   ├─ Layer 4: Validation (AST + pytest)
    │   ├─ Layer 5: Repair Loop (LLM auto-fix)
    │   └─ Layer 6: Explainability Engine
    │
    ├─ job.status = "done"
    └─ Sync to MongoDB
    
    │
    ├─ Frontend polls: GET /api/pipeline/status/job_id
    ├─ Returns: {status, logs, result}
    │
    └─ Frontend streams: GET /api/pipeline/stream/job_id
        └─ Server-Sent Events (live logs)
```

---

## 🐛 Debugging Tips

### Check Backend Logs
```bash
cd Chatbot_Interface/backend
tail -f logs/rad_ml.log
```

### Monitor Job Status
```python
from orchestrator import Orchestrator
import yaml

with open("config.yaml") as f:
    config = yaml.safe_load(f)

orc = Orchestrator(config)
job = orc.get_job("job_id_here")

print(f"Status: {job.status}")
print(f"Error: {job.error}")
print("\nLogs:")
for log in job.logs:
    print(f"  [{log['step']}] {log['message']}")
```

### Test Each Component Separately

```bash
# Test prompt parser only
python -m pytest tests/test_prompt_parser.py -v

# Test data collection only (mocked sources)
python -m pytest tests/test_dataset_scorer.py tests/test_dataset_merger.py -v

# Test code generation only (mocked LLM)
python -m pytest tests/test_codegen_pipeline.py -v

# Test full integration
python -m pytest tests/SampleTests/test_complete_system_integration.py -v
```

### Running Single Components in Python REPL

```python
# Start Python REPL
python

# Test prompt parser
from Data_Collection_Agent.brain.prompt_parser import PromptParser
parser = PromptParser()
spec = parser.parse("your prompt here")
print(spec)

# Test dataset scorer
from Data_Collection_Agent.utils.dataset_scorer import DatasetScorer
scorer = DatasetScorer({})
score = scorer.score_metadata({...}, {...})
print(f"Score: {score}")
```

### Check Generated Files
```bash
# After code generation completes
ls -la generated/

# View generated app.py
cat generated/app.py | head -50

# Run generated tests
python -m pytest generated/test_model.py -v
```

---

## 📋 Checklist: First Run

- [ ] Clone repo: `git clone ...`
- [ ] Create config.yaml with at least valid jwt_secret_key
- [ ] Install deps: `pip install -r requirements.txt`
- [ ] Install frontend deps: `cd Chatbot_Interface/frontend && npm install`
- [ ] Start backend: `cd Chatbot_Interface/backend && python app.py`
- [ ] Start frontend: `cd Chatbot_Interface/frontend && npm run dev`
- [ ] Open browser: `http://localhost:5173`
- [ ] Register user
- [ ] Submit test prompt: "Predict housing prices"
- [ ] Monitor logs: `tail -f logs/rad_ml.log`
- [ ] Check result when job completes

---

## 🎯 Next Steps

### For Development
- Read [PROJECT_STRUCTURE_GUIDE.md] for detailed architecture
- Run tests: `pytest tests/ -v`
- Add new test cases in [tests/]
- Extend collectors in [Data_Collection_Agent/collectors/]

### For Deployment
- Set real credentials in config.yaml
- Deploy backend to cloud (Heroku, AWS, GCP)
- Deploy frontend to CDN (Netlify, Vercel, CloudFront)
- Set up MongoDB for chat history persistence
- Configure AWS SageMaker for model training
- Set up Kaggle/UCI/OpenML API access

### For Customization
- Add custom collectors in [Data_Collection_Agent/collectors/]
- Modify scoring formula in [Data_Collection_Agent/utils/dataset_scorer.py]
- Extend code generation templates in [Code_Generator/RAD-ML/generator/]
- Add custom validation rules in [Code_Generator/RAD-ML/generator/validator.py]
- Create new explanation templates in [Code_Generator/RAD-ML/explainability/]

