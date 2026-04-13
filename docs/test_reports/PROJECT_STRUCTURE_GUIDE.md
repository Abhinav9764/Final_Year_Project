# RAD-ML Project Structure & Component Guide

## 📊 System Architecture Overview

RAD-ML is a comprehensive, agentic ML pipeline with 4 main components:

```
User Prompt (via Chat UI)
    ↓
┌─────────────────────────────────────────┐
│ 1. DATA COLLECTION AGENT                 │
│    • Prompt parsing                      │
│    • Search: Kaggle, UCI, OpenML         │
│    • Download & score datasets           │
│    • Merge multiple sources              │
│    • Upload to S3                        │
└─────────────────────────────────────────┘
    ↓ db_results.json (dataset + spec)
┌─────────────────────────────────────────┐
│ 2. CODE GENERATOR (5 Layers)             │
│    Layer 1: Prompt Understanding         │
│    Layer 2: Architecture Planner         │
│    Layer 3: File-by-File Code Gen       │
│    Layer 4: Validation (AST + pytest)   │
│    Layer 5: Repair Loop (LLM auto-fix)  │
│    Layer 6: Explainability Engine       │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ 3. ML TRAINING & DEPLOYMENT              │
│    • Data preprocessing                  │
│    • AWS SageMaker XGBoost training      │
│    • Model endpoint deployment           │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ 4. ORCHESTRATOR & CHAT UI                │
│    • Job lifecycle management            │
│    • User authentication                 │
│    • MongoDB chat history                │
│    • React frontend with live logs       │
└─────────────────────────────────────────┘
```

---

## 1. DATA COLLECTION AGENT

### Location
- **Main entry point**: [Data_Collection_Agent/main.py](Data_Collection_Agent/main.py)
- **Collectors**: [Data_Collection_Agent/collectors/](Data_Collection_Agent/collectors/)
  - `kaggle_collector.py` - Kaggle API integration
  - `openml_collector.py` - OpenML API integration
  - `uci_collector.py` - UCI Repository integration
- **Utilities**: [Data_Collection_Agent/utils/](Data_Collection_Agent/utils/)
  - `dataset_scorer.py` - Scoring formula (keyword + rows + columns + recency)
  - `dataset_merger.py` - Merge multiple datasets
  - `s3_uploader.py` - Upload to AWS S3
- **Brain**: [Data_Collection_Agent/brain/](Data_Collection_Agent/brain/)
  - `prompt_parser.py` - Intent classification, keyword extraction, fallback datasets

### Entry Point Function

```python
def run_collection(prompt: str, config: dict, job_id: str, log_fn=None) -> dict:
    """
    Full data collection pipeline.
    
    Args:
        prompt (str): User's plain-English prompt
        config (dict): YAML config with Kaggle/UCI/OpenML credentials
        job_id (str): Unique job identifier
        log_fn (callable): Optional logging callback(step, message)
    
    Returns:
        dict: {
            "job_id": str,
            "prompt": str,
            "spec": {...},           # parsed intent, keywords, target, etc
            "dataset": {
                "local_path": str,    # path to final CSV
                "s3_uri": str,        # S3 location
                "columns": [str],     # column names
                "row_count": int,
                "source_count": int,  # 1 or more if merged
                "preview_rows": [...], # first 5-10 rows as dicts
                "merged": bool,
            },
            "top_sources": [...]     # metadata of best datasets
        }
    """
```

### How to Call It

#### Option 1: Direct Python Call
```python
from Data_Collection_Agent.main import run_collection
import yaml

# Load config
with open("config.yaml") as f:
    config = yaml.safe_load(f)

# Call the agent
prompt = "Predict housing prices based on bedrooms and location"
job_id = "job_12345"

result = run_collection(
    prompt=prompt,
    config=config,
    job_id=job_id,
    log_fn=lambda step, msg: print(f"[{step}] {msg}")
)

# Access results
print(f"Dataset: {result['dataset']['local_path']}")
print(f"Rows: {result['dataset']['row_count']}")
print(f"Columns: {result['dataset']['columns']}")
```

#### Option 2: Via Orchestrator (Production)
```python
from Chatbot_Interface.backend.orchestrator import Orchestrator

orc = Orchestrator(config)
job_id = orc.create_job("Predict housing prices based on bedrooms and location")
orc.start_pipeline(job_id, user_id=1)

# Poll for status
job = orc.get_job(job_id)
print(f"Status: {job.status}")
print(f"Logs: {job.logs}")
```

### Data Collection Pipeline Stages

1. **Parse Prompt** (PromptParser)
   - Intent classification: `ml_model` or `chatbot`
   - Task type: `regression`, `classification`, `clustering`
   - Keywords extraction (1-word terms that work with APIs)
   - Input/target parameters
   - Domain detection with fallback dataset refs

2. **Tier 1: Live Search** (3 parallel sources)
   - Kaggle API search
   - UCI Repository search
   - OpenML API search
   - Results: up to 15+ candidate datasets

3. **Tier 2: Fallback Search** (if Tier 1 returns 0)
   - Use hardcoded Kaggle dataset slugs for known domains
   - E.g., housing → `harlfoxem/house-prices-dataset`

4. **Tier 3: Task/Domain Search** (if still 0)
   - OpenML task-based search
   - OpenML domain-based search

5. **Score & Rank** (DatasetScorer)
   ```
   score = 0.40 × keyword_match
         + 0.30 × row_count_score
         + 0.20 × column_match
         + 0.10 × recency_score
   ```

6. **Download & Score CSVs** (per-file scoring)
   - Download top 8 candidates
   - Verify tabular structure
   - Score each CSV
   - Stop early if ≥500 rows and ≥2 files

7. **Merge** (DatasetMerger)
   - Combine 1+ CSVs into final dataset
   - Keep `source_count` metric
   - Preview first 5-10 rows

8. **Upload to S3** (S3Uploader)
   - Upload final CSV
   - Tag with job_id
   - Return S3 URI

### Configuration Section (config.yaml)

```yaml
kaggle:
  username: "your_username"
  key: "your_api_key"

aws:
  region: "us-east-1"
  s3_bucket: "your-ml-datasets"
  sagemaker_role: "arn:aws:iam::ACCOUNT:role/SageMakerRole"

collection:
  min_row_threshold: 500  # minimum rows to consider

scoring:
  keyword_match_weight: 0.40
  row_count_weight: 0.30
  column_match_weight: 0.20
  recency_weight: 0.10

logging:
  console_level: "INFO"
  log_file: "logs/rad_ml.log"
```

---

## 2. CODE GENERATOR (5-Layer Pipeline)

### Location
- **Main entry point**: [Code_Generator/RAD-ML/main.py](Code_Generator/RAD-ML/main.py)
- **Layers**:
  - Layer 1: [generator/prompt_understanding.py](Code_Generator/RAD-ML/generator/prompt_understanding.py)
  - Layer 2: [generator/planner.py](Code_Generator/RAD-ML/generator/planner.py)
  - Layer 3: [generator/code_gen_factory.py](Code_Generator/RAD-ML/generator/code_gen_factory.py)
  - Layer 4: [generator/validator.py](Code_Generator/RAD-ML/generator/validator.py)
  - Layer 5: [generator/repair_loop.py](Code_Generator/RAD-ML/generator/repair_loop.py)
- **Explainability**: [explainability/engine.py](Code_Generator/RAD-ML/explainability/engine.py)
- **ML Engine**: 
  - [engines/ml_engine/data_preprocessor.py](Code_Generator/RAD-ML/engines/ml_engine/data_preprocessor.py)
  - [engines/ml_engine/sagemaker_handler.py](Code_Generator/RAD-ML/engines/ml_engine/sagemaker_handler.py)

### Entry Point Function

```python
def run_codegen(db_results: dict, config: dict, job_id: str, 
                log_fn=None) -> dict:
    """
    Full 5-layer code generation + explainability.
    
    Args:
        db_results (dict): Output from run_collection()
        config (dict): YAML config
        job_id (str): Unique job identifier
        log_fn (callable): Optional logging callback(step, message)
    
    Returns:
        dict: {
            "endpoint_name": str,         # SageMaker endpoint
            "deploy_url": str,            # http://localhost:7000
            "app_path": str,              # path to app.py
            "sm_meta": {...},             # SageMaker training metadata
            "preprocess": {
                "feature_cols": [str],
                "target_col": str,
                "task_type": str,
                "stats": {...}
            },
            "generated_files": {
                "app.py": Path,
                "predictor.py": Path,
                "train.py": Path,
                "requirements.txt": Path,
                "README.md": Path,
                "test_model.py": Path,
            },
            "validation_summary": str,
            "explanation": {
                "narrative": str,          # plain-English explanation
                "algorithm_card": {...},   # why XGBoost, etc
                "data_story": str,
                "usage_guide": str,
                "diagram_path": str,       # architecture PNG
                "code_preview": {...}      # first 60 lines per file
            }
        }
    """
```

### How to Call It

#### Option 1: Direct Python Call (with mocked SageMaker)
```python
from Code_Generator.RAD-ML.main import run_codegen
import yaml

with open("config.yaml") as f:
    config = yaml.safe_load(f)

# First, run data collection
from Data_Collection_Agent.main import run_collection
db_results = run_collection(
    prompt="Predict housing prices",
    config=config,
    job_id="job_xyz"
)

# Then run code generation
cg_result = run_codegen(
    db_results=db_results,
    config=config,
    job_id="job_xyz",
    log_fn=lambda step, msg: print(f"[{step}] {msg}")
)

# Access results
print(f"Endpoint: {cg_result['endpoint_name']}")
print(f"App: {cg_result['app_path']}")
for filename, filepath in cg_result['generated_files'].items():
    print(f"  - {filename}: {filepath}")
```

#### Option 2: Via Orchestrator (Production)
```python
# Orchestrator handles both data collection and code generation
orc = Orchestrator(config)
job_id = orc.create_job("Predict housing prices")
orc.start_pipeline(job_id, user_id=1)

job = orc.get_job(job_id)
if job.status == "done":
    result = job.result
    print(f"Generated files: {result.get('generated_files')}")
```

### Code Generation Pipeline - 5 Layers

#### Layer 1: Prompt Understanding
```python
from Code_Generator.RAD-ML.generator.prompt_understanding import PromptUnderstandingLayer
from Code_Generator.RAD-ML.core.llm_client import LLMClient

llm = LLMClient(config)
layer1 = PromptUnderstandingLayer(llm)

# Input: raw user prompt + parsed spec + dataset info
project_spec = layer1.build_spec(
    prompt="Predict house prices",
    parsed_spec={"task_type": "regression", "keywords": ["housing", "price"]},
    dataset_info={"columns": ["bedrooms", "bathrooms", "price"], "row_count": 1000},
    sm_meta={"endpoint_name": "xgb-endpoint-123"},
    preprocess_result={
        "feature_cols": ["bedrooms", "bathrooms"],
        "target_col": "price",
        "task_type": "regression",
        "stats": {...}
    },
    config=config,
)

# Output: structured ProjectSpec with task, framework, deliverables, etc
print(f"Task: {project_spec['task']}")
print(f"Task Type: {project_spec['task_type']}")
print(f"Framework: {project_spec['framework']}")  # e.g., Flask
print(f"Deliverables: {project_spec['deliverables']}")  # e.g., app.py, predictor.py
```

#### Layer 2: Architecture Planner
```python
from Code_Generator.RAD-ML.generator.planner import Planner

planner = Planner(llm)
plan = planner.plan(project_spec)

# Output includes file structure, function signatures, dependencies
print(f"File structure: {plan['file_structure'].keys()}")
print(f"Dependencies: {plan['dependencies']}")
print(f"Key functions in app.py: {plan['key_functions']['app.py']}")
# Example output:
#   - ["index() -> str", "predict(features) -> str"]
```

#### Layer 3: File-by-File Code Generation
```python
from Code_Generator.RAD-ML.generator.code_gen_factory import CodeGenFactory

factory = CodeGenFactory(llm, config)
written_files = factory.generate_all(project_spec, plan)

# Output: dict of {filename: filepath}
for filename, filepath in written_files.items():
    print(f"Generated {filename}: {filepath}")
```

#### Layer 4: Validation
```python
from Code_Generator.RAD-ML.generator.validator import Validator

validator = Validator(project_spec, config)
val_report = validator.validate(written_files)

# Validates: AST syntax, security, relevance, pytest success
print(f"All passed: {val_report.all_passed}")
if not val_report.all_passed:
    for failed_file in val_report.failed_files():
        print(f"  {failed_file.filename}: {failed_file.errors}")
```

#### Layer 5: Repair Loop
```python
from Code_Generator.RAD-ML.generator.repair_loop import RepairLoop

if not val_report.all_passed:
    repair = RepairLoop(llm, project_spec, plan, config)
    written_files, val_report = repair.repair(
        written_files, 
        val_report, 
        validator,
        max_attempts=5  # up to 5 fix attempts per file
    )
    print(f"After repair: {val_report.summary()}")
```

#### Layer 6: Explainability Engine
```python
from Code_Generator.RAD-ML.explainability.engine import ExplainabilityEngine

explain_engine = ExplainabilityEngine(llm, config)
explanation = explain_engine.explain(
    job_result={
        "deploy_url": "http://localhost:7000",
        "endpoint_name": "xgb-endpoint",
        "dataset": {
            "row_count": 1000,
            "columns": ["bedrooms", "bathrooms", "price"],
        }
    },
    db_results=db_results,
    written_files={k: str(v) for k, v in written_files.items()},
)

# Output: Plain-English explanations + PNG diagram
print(f"Narrative: {explanation['narrative']}")
print(f"Algorithm card: {explanation['algorithm_card']}")
print(f"Data story: {explanation['data_story']}")
print(f"Diagram: {explanation['diagram_path']}")
```

---

## 3. TEST FILES & TESTING PATTERNS

### Test Structure

```
tests/
├── test_prompt_parser.py              # Intent classification tests
├── test_dataset_scorer.py             # Scoring formula tests
├── test_dataset_merger.py             # Merge logic tests
├── test_kaggle_collector.py           # Kaggle API tests (mocked)
├── test_openml_collector.py           # OpenML API tests (mocked)
├── test_codegen_pipeline.py           # 5-layer code gen tests
├── test_data_preprocessor.py          # Data preprocessing tests
├── test_sagemaker_handler.py          # SageMaker handler tests
├── test_explainability.py             # Explanation engine tests
│
├── SampleTests/                       # Integration tests
│   ├── test_complete_system_integration.py
│   ├── test_end_to_end_integration.py
│   ├── test_pipeline.py
│   ├── test_gold_price.py
│   └── test_authentication_and_api.py
│
└── TestResults/                       # Test output & logs
```

### Test 1: Prompt Parser

**Location**: [tests/test_prompt_parser.py](tests/test_prompt_parser.py)

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "Data_Collection_Agent"))

from brain.prompt_parser import PromptParser

PARSER = PromptParser()

# Test 1: Intent detection
def test_regression_intent():
    spec = PARSER.parse("Predict housing prices based on bedrooms and location")
    assert spec["intent"]    == "ml_model"
    assert spec["task_type"] == "regression"

# Test 2: Classification
def test_classification_intent():
    spec = PARSER.parse("Classify emails as spam or not spam")
    assert spec["task_type"] == "classification"

# Test 3: Keywords extraction
def test_keywords_extracted():
    spec = PARSER.parse("Predict car price based on engine size, fuel type and mileage")
    assert len(spec["keywords"]) > 0
    assert any("price" in p for p in spec["keywords"])

# Test 4: Parameter extraction
def test_input_params_extracted():
    spec = PARSER.parse("Predict salary based on age experience education")
    params = spec["input_params"]
    assert any("age" in p or "experience" in p for p in params)

# Test 5: Target parameter
def test_target_param_extracted():
    spec = PARSER.parse("Predict salary of an employee")
    assert "salary" in spec["target_param"].lower()

# Run tests
pytest.main([__file__, "-v"])
```

### Test 2: Code Generation Pipeline

**Location**: [tests/test_codegen_pipeline.py](tests/test_codegen_pipeline.py)

```python
import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Layer 1 test: Prompt Understanding
def test_understanding_uses_llm_output():
    llm = MagicMock()
    spec = {
        "task": "housing prediction",
        "task_type": "regression",
        "framework": "Flask",
        "feature_cols": ["bedrooms", "bathrooms"],
        "target_col": "price",
    }
    llm.generate.return_value = json.dumps(spec)
    
    from generator.prompt_understanding import PromptUnderstandingLayer
    layer = PromptUnderstandingLayer(llm)
    result = layer.build_spec(
        prompt="predict house price",
        parsed_spec={"task_type": "regression", "input_params": ["bedrooms"]},
        dataset_info={"columns": ["bedrooms", "price"], "row_count": 600},
        sm_meta={"endpoint_name": "test-endpoint"},
        preprocess_result={"feature_cols": ["bedrooms"], "target_col": "price"},
        config={"codegen": {"workspace_dir": "/tmp"}},
    )
    assert result["task_type"] == "regression"

# Layer 4 test: Validation
def test_validator_catches_syntax_errors():
    from generator.validator import Validator
    
    project_spec = {
        "task": "test",
        "task_type": "regression",
        "feature_cols": ["x"],
        "target_col": "y",
    }
    validator = Validator(project_spec, {"codegen": {"max_fix_attempts": 2}})
    
    bad_code = {"app.py": Path("/tmp/bad.py") }
    # Write intentionally bad Python
    bad_code["app.py"].write_text("def broken(:\n  pass")
    
    report = validator.validate(bad_code)
    assert not report.all_passed
    assert len(report.failed_files()) > 0
```

### Test 3: Dataset Scoring

**Location**: [tests/test_dataset_scorer.py](tests/test_dataset_scorer.py)

```python
from utils.dataset_scorer import DatasetScorer
import tempfile
import pandas as pd

CFG = {
    "scoring": {
        "keyword_match_weight": 0.40,
        "row_count_weight": 0.30,
        "column_match_weight": 0.20,
        "recency_weight": 0.10,
    },
}
SCORER = DatasetScorer(CFG)

# Test scoring formula
def test_keyword_score_full_match():
    meta = {"title": "housing price bedrooms dataset", "ref": ""}
    score = SCORER.score_metadata(meta, 
        {"keywords": ["housing", "price", "bedrooms"]})
    assert score > 0.3

def test_row_score_above_threshold():
    meta = {"title": "housing", "num_instances": 1000, "ref": ""}
    score = SCORER.score_metadata(meta, {"keywords": ["housing"]})
    assert score > 0.5
```

### Test 4: Complete System Integration

**Location**: [tests/SampleTests/test_complete_system_integration.py](tests/SampleTests/test_complete_system_integration.py)

```python
import requests
import time

BACKEND_URL = "http://localhost:5001"
FRONTEND_URL = "http://localhost:5173"

# Test 1: Backend health
def test_backend_health():
    response = requests.get(f"{BACKEND_URL}/api/health")
    assert response.status_code == 200

# Test 2: Frontend accessible
def test_frontend_accessible():
    response = requests.get(FRONTEND_URL)
    assert response.status_code == 200

# Test 3: Full pipeline
def test_full_pipeline_via_api():
    # 1. Register user
    user_data = {
        "username": f"test_user_{int(time.time())}",
        "password": "Test@1234!",
    }
    resp = requests.post(f"{BACKEND_URL}/api/auth/register", json=user_data)
    token = resp.json()["token"]
    
    # 2. Create job
    headers = {"Authorization": f"Bearer {token}"}
    job_data = {"prompt": "Predict housing prices"}
    resp = requests.post(f"{BACKEND_URL}/api/pipeline/run", 
                        json=job_data, headers=headers)
    job_id = resp.json()["job_id"]
    
    # 3. Poll status
    for _ in range(300):  # 5 minute timeout
        resp = requests.get(f"{BACKEND_URL}/api/pipeline/status/{job_id}",
                           headers=headers)
        status = resp.json()["status"]
        if status == "done":
            break
        elif status == "error":
            raise Exception(resp.json()["error"])
        time.sleep(1)
    
    assert status == "done"
```

### How to Run Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_prompt_parser.py -v

# Run with coverage
pytest tests/ --cov=Data_Collection_Agent --cov=Code_Generator

# Run integration tests (requires running backend/frontend)
pytest tests/SampleTests/ -v

# Run specific test function
pytest tests/test_prompt_parser.py::test_regression_intent -v
```

---

## 4. PIPELINE ORCHESTRATION

### Orchestrator Class

**Location**: [Chatbot_Interface/backend/orchestrator.py](Chatbot_Interface/backend/orchestrator.py)

The `Orchestrator` class manages the full lifecycle of jobs:

```python
from orchestrator import Orchestrator, Job

orc = Orchestrator(config)

# Create a job
job_id = orc.create_job("Predict housing prices from bedrooms and location")
# Returns: "abc12def"

# Get job details
job = orc.get_job(job_id)
print(f"Prompt: {job.prompt}")
print(f"Status: {job.status}")  # queued, running, done, error
print(f"Logs: {job.logs}")      # list of {step, message, ts}

# List all jobs
jobs = orc.list_jobs()
for j in jobs:
    print(f"{j['id']}: {j['prompt'][:40]} → {j['status']}")

# Start pipeline execution (async, in background thread)
orc.start_pipeline(job_id, user_id=1, history_db=db)

# Cancel a running job
orc.cancel_job(job_id)

# Delete a job
orc.delete_job(job_id)
```

### Job Execution Flow

When `start_pipeline()` is called, this happens:

```python
def _run_pipeline(self, job: Job, history_db=None) -> None:
    job.status = "running"
    
    try:
        # Stage 1: Data Collection
        # ─────────────────────────────────────────────
        if job.dataset_path:
            # User uploaded CSV → skip collection
            db_results = self._load_csv(job.dataset_path)
        else:
            # Run full collection pipeline
            run_collection = _import_run_collection()
            db_results = run_collection(
                prompt=job.prompt,
                config=self._config,
                job_id=job.id,
                log_fn=lambda step, msg: self._log_step(job, step, msg)
            )
        
        # Stage 2: Code Generation
        # ─────────────────────────────────────────────
        run_codegen = _import_run_codegen()
        cg_result = run_codegen(
            db_results=db_results,
            config=self._config,
            job_id=job.id,
            log_fn=lambda step, msg: self._log_step(job, step, msg)
        )
        
        # You can cancel at checkpoint
        if job.cancelled:
            raise RuntimeError("Job cancelled by user.")
        
        # Build final result
        job.result = {
            "deploy_url": cg_result["deploy_url"],
            "endpoint_name": cg_result["endpoint_name"],
            "generated_files": cg_result["generated_files"],
            "explanation": cg_result["explanation"],
            # ... more fields
        }
        
        job.status = "done"
    
    except Exception as exc:
        job.error = str(exc)
        job.status = "error"
    
    finally:
        # Sync to MongoDB
        if history_db:
            history_db.upsert_job(
                user_id=job.user_id,
                job_id=job.id,
                prompt=job.prompt,
                status=job.status,
                logs=job.logs,
                result=job.result,
                error=job.error
            )
```

### Backend API Endpoints

**Location**: [Chatbot_Interface/backend/app.py](Chatbot_Interface/backend/app.py)

```python
# ═══════════════════════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

POST /api/auth/register
  Body: {"username": str, "password": str, "email": str}
  Returns: {"ok": bool, "token": str, "user": {...}}

POST /api/auth/login
  Body: {"username": str, "password": str}
  Returns: {"ok": bool, "token": str, "user": {...}}

GET /api/auth/me
  Headers: Authorization: Bearer <token>
  Returns: {"id": int, "username": str, "email": str}

# ═══════════════════════════════════════════════════════════════════════════
# PIPELINE ENDPOINTS (JWT required)
# ═══════════════════════════════════════════════════════════════════════════

POST /api/pipeline/run
  Body: {"prompt": str}
  Returns: {"ok": bool, "job_id": str}

GET /api/pipeline/status/<job_id>
  Returns: {
    "id": str,
    "prompt": str,
    "status": "queued|running|done|error",
    "logs": [...],
    "result": {...}
  }

GET /api/pipeline/stream/<job_id>
  Returns: Server-Sent Events (SSE) stream for live logs
  Event format: data: {"step": str, "message": str, "ts": float}

# ═══════════════════════════════════════════════════════════════════════════
# HISTORY ENDPOINTS (JWT required)
# ═══════════════════════════════════════════════════════════════════════════

GET /api/history
  Returns: [{"id": str, "prompt": str, "status": str, "created": float}, ...]

GET /api/history/<job_id>
  Returns: {"id": str, "prompt": str, "status": str, "result": {...}, "logs": [...]}

DELETE /api/history/<job_id>
  Returns: {"ok": bool}

DELETE /api/history
  Returns: {"ok": bool, "deleted_count": int}

# ═══════════════════════════════════════════════════════════════════════════
# MISC
# ═══════════════════════════════════════════════════════════════════════════

GET /api/health
  Returns: {"status": "ok"}
```

### End-to-End Example: Full Workflow

```python
#!/usr/bin/env python3
"""
Complete workflow example: from prompt to deployed model.
"""
import time
import yaml
from pathlib import Path

# Load config
with open("config.yaml") as f:
    config = yaml.safe_load(f)

# ──────────────────────────────────────────────────────────────────────────────
# Option A: Manual stage-by-stage
# ──────────────────────────────────────────────────────────────────────────────

from Data_Collection_Agent.main import run_collection
from Code_Generator.RAD_ML.main import run_codegen

prompt = "Build an ML model to predict gold prices based on market indicators"
job_id = "gold_price_v1"

print("=" * 80)
print("STAGE 1: DATA COLLECTION")
print("=" * 80)

db_results = run_collection(
    prompt=prompt,
    config=config,
    job_id=job_id,
    log_fn=lambda step, msg: print(f"[{step:12}] {msg}")
)

print(f"\n✓ Dataset: {db_results['dataset']['local_path']}")
print(f"  Rows: {db_results['dataset']['row_count']:,}")
print(f"  Columns: {db_results['dataset']['columns']}")

print("\n" + "=" * 80)
print("STAGE 2: CODE GENERATION")
print("=" * 80)

cg_result = run_codegen(
    db_results=db_results,
    config=config,
    job_id=job_id,
    log_fn=lambda step, msg: print(f"[{step:12}] {msg}")
)

print(f"\n✓ Generated Files:")
for filename, filepath in cg_result['generated_files'].items():
    print(f"  - {filename}: {filepath}")

print(f"\n✓ Endpoint: {cg_result['endpoint_name']}")
print(f"✓ Deploy URL: {cg_result['deploy_url']}")

print(f"\n✓ Explanation:")
print(f"  - Narrative: {cg_result['explanation']['narrative'][:100]}...")
print(f"  - Diagram: {cg_result['explanation']['diagram_path']}")

# ──────────────────────────────────────────────────────────────────────────────
# Option B: Via Orchestrator (production-ready)
# ──────────────────────────────────────────────────────────────────────────────

from Chatbot_Interface.backend.orchestrator import Orchestrator

orc = Orchestrator(config)

# Create a job
job_id = orc.create_job("Predict gold prices from market indicators")
print(f"\nCreated job: {job_id}")

# Start it (runs in background thread)
orc.start_pipeline(job_id, user_id=1)

# Poll until done
print("\nPolling status...")
while True:
    job = orc.get_job(job_id)
    print(f"  Status: {job.status}")
    
    if job.status == "done":
        print("\n✓ Pipeline complete!")
        print(f"  Result: {job.result}")
        break
    elif job.status == "error":
        print(f"\n✗ Pipeline failed: {job.error}")
        break
    
    time.sleep(2)
```

---

## 5. QUICK TESTING GUIDE

### Run Entire Test Suite

```bash
# Install dependencies
pip install pytest pytest-cov scikit-learn xgboost pandas numpy

# Run all tests
cd /path/to/RAD-ML-v8
pytest tests/ -v

# Expected output should show:
# - test_prompt_parser.py: 8 passed
# - test_dataset_scorer.py: 6 passed
# - test_codegen_pipeline.py: 10+ passed
# - SampleTests/: integration tests
```

### Run Specific Component Tests

```bash
# Test prompt parsing
pytest tests/test_prompt_parser.py -v

# Test scoring
pytest tests/test_dataset_scorer.py -v

# Test code generation
pytest tests/test_codegen_pipeline.py -v

# Test integration
pytest tests/SampleTests/test_complete_system_integration.py -v
```

### Mock Mode (no API keys needed)

Most tests run in mock mode:
- Kaggle/UCI/OpenML API calls are mocked
- LLM calls (Gemini) are mocked
- SageMaker is mocked
- Only logic is tested

```python
# Example: mock LLM for testing
from unittest.mock import MagicMock
import json

llm = MagicMock()
spec = {"task_type": "regression", "framework": "Flask"}
llm.generate.return_value = json.dumps(spec)
```

### Integration Tests (require running services)

```bash
# Terminal 1: Start backend
cd Chatbot_Interface/backend
python app.py

# Terminal 2: Start frontend  
cd Chatbot_Interface/frontend
npm run dev

# Terminal 3: Run integration tests
pytest tests/SampleTests/ -v
```

---

## 6. DEPLOYMENT CHECKLIST

- [ ] Configure `config.yaml` with real credentials
- [ ] Set up Python environment: `pip install -r requirements.txt`
- [ ] Set up AWS credentials (SageMaker + S3)
- [ ] Set up Kaggle API credentials
- [ ] Install Graphviz for diagrams (optional but recommended)
- [ ] Start backend: `cd Chatbot_Interface/backend && python app.py`
- [ ] Start frontend: `cd Chatbot_Interface/frontend && npm run dev`
- [ ] Test system: visit `http://localhost:5173`

