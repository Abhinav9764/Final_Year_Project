# 🔧 Code Generation Agent: Technical Implementation Guide

**Version:** v8 (Streamlit Edition)  
**Date:** March 21, 2026  
**Audience:** Backend Engineers, System Architects

---

## 📚 Architecture Overview

### Component Interaction Diagram

```
┌─────────────────┐
│  User Prompt    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  RefinementLoop.run(prompt)         │  ← Main Entry Point
│  [core/refinement_loop.py]          │
└────────┬────────────────────────────┘
         │
         ├─────────────────────────────────────────────┐
         │                                             │
    Phase 1: PLANNING                          Phase 2: INFRASTRUCTURE
         │                                             │
         ▼                                             ▼
    ┌─────────────┐                           ┌──────────────┐
    │  Router     │                           │ RAGBuilder   │
    │  (classify) │                           │ (or) SM Init │
    └─────────────┘                           └──────────────┘
         │                                             │
         └──────────────┬──────────────────────────────┘
                        │
                    Phase 3: CODE GENERATION
                        │
                        ▼
            ┌───────────────────────────────┐
            │  CodeGenFactory.generate()    │
            │  [generator/code_gen_factory] │
            └───────────┬───────────────────┘
                        │
        ┌───────────────┸───────────────┐
        │                               │
        ▼                               ▼
    app.py                         test_app.py
    (Streamlit)                    (pytest)
        │                               │
        └───────────────┬───────────────┘
                        │
                    Phase 4: TESTING
                        │
                        ▼
            ┌───────────────────────────────┐
            │  CodeVerifier.verify()        │
            │  + pytest.main()              │
            └───────────┬───────────────────┘
                        │
            ┌───────────┴────────────┐
            │                        │
        ✓ PASS              ✗ FAIL
            │                        │
            ▼                        ▼
    Phase 5a: LAUNCH       Phase 5b: REFINE
    streamlit run          Feed errors to LLM
    app.py                 Regenerate (retry)
            │                        │
            ▼                        ▼
        DEPLOYED                  Loop back to
        APP                        Phase 3
        READY                      (max 5 retries)
```

---

## 🔍 Module Deep Dives

### 1. `core/refinement_loop.py` — Orchestration

**Purpose:** 5-phase pipeline controller

**Key Methods:**

```python
class RefinementLoop:
    def __init__(self, cfg: dict)
        # Initialize with config settings
        # Load LLM, Router, CodeGenFactory
        
    def run(self, user_prompt: str) -> dict
        # Main entry point
        # Returns final result with app_path, status, metrics
        
    def _phase1_planning(prompt) -> RouteDecision
        # Classify prompt into task type
        # Extract requirements and constraints
        
    def _phase2_infrastructure(decision) -> bool
        # Build RAG index for chatbot mode
        # Init SageMaker endpoint for ML mode
        
    def _phase3_generate_code(spec, plan) -> CodeBundle
        # Call CodeGenFactory to generate app.py
        # Generate test_app.py
        
    def _phase4_test(code) -> (bool, str)
        # Run AST validation
        # Execute pytest
        # Measure execution time
        
    def _phase5_self_refine(code, error) -> (bool, str, float)
        # If PASS → launch app with streamlit run
        # If FAIL → feed error to LLM, regenerate
        # Score attempt with RewardSystem
```

**Configuration Usage:**
```python
cfg['refinement']['max_retries']           # Default: 5
cfg['refinement']['test_timeout_secs']     # Default: 60
cfg['refinement']['app_start_timeout_secs']# Default: 300
cfg['streamlit']['host']                   # Default: 127.0.0.1
cfg['streamlit']['port']                   # Default: 8501
```

**Return Value:**
```python
{
    "status": "success|failed",
    "app_path": "/path/to/app.py",
    "app_url": "http://127.0.0.1:8501",
    "test_results": {
        "passed": 5,
        "failed": 0,
        "errors": []
    },
    "metrics": {
        "avg_reward": 8.5,
        "total_attempts": 2,
        "generation_time_secs": 12.3
    },
    "error": None  # or error message
}
```

---

### 2. `generator/code_gen_factory.py` — Code Generation

**Purpose:** LLM-based code generation for Streamlit apps

**Key Methods:**

```python
class CodeGenFactory:
    def __init__(self, cfg: dict)
        # Initialize LLM backends in priority order:
        # 1. HuggingFace Hub
        # 2. Ollama local
        # 3. Offline stub
        
    def generate(
        self,
        spec: ProjectSpec,
        plan: ArchPlan,
        mode: str = "ml",  # "ml", "chatbot", "recommendation"
        error_context: str = None,  # For refinement loop
    ) -> CodeBundle:
        # Generate complete Streamlit app
        # Returns: {"python": app_code, "tests": test_code}
        
    def _call_llm(prompt: str) -> str
        # Try backends in priority order
        # Fall back to offline stub on failure
        
    def _build_prompt(spec, plan, mode, error) -> str
        # Construct structured LLM prompt
        # Include error context for refinement
```

**Output Format (CodeBundle):**
```python
CodeBundle = {
    "python": """
import streamlit as st
import pandas as pd
...
# Full app.py content here
""",
    "tests": """
import pytest
import streamlit as st
...
# Full test_app.py content here
""",
    "html": "",   # Always empty (Streamlit-only)
    "css": ""     # Always empty (Streamlit-only)
}
```

**LLM Backends:**

```python
# Backend 1: HuggingFace Hub (Free)
if hf_available():
    from huggingface_hub import InferenceClient
    client = InferenceClient(
        model="Qwen/Qwen2.5-Coder-3B-Instruct",
        token=cfg['qwen']['hf_token']  # Optional
    )
    response = client.text_generation(prompt)

# Backend 2: Ollama (Fully Offline)
if ollama_running():
    import requests
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "qwen2.5-coder:3b",
            "prompt": prompt,
            "stream": False
        }
    )

# Backend 3: Offline Stub (Last Resort)
from generator.templates.base_streamlit import STREAMLIT_APP_ML
# Use pre-built template
```

---

### 3. `generator/code_verifier.py` — Validation

**Purpose:** AST-based code validation and error detection

**Key Methods:**

```python
class CodeVerifier:
    def verify(self, code: str) -> (bool, list[str]):
        # Check code for errors
        # Returns: (is_valid, [error_messages])
        
    def _check_syntax(code: str) -> bool
        # Parse with ast.parse()
        # Catch SyntaxError
        
    def _has_required_imports(code: str) -> bool
        # Check for "import streamlit"
        # Check for domain libraries (pandas, sklearn, etc)
        
    def _detect_streamlit_patterns(code: str) -> dict
        # Count st.write(), st.button(), etc
        # Validate widget usage
        
    def _detect_flask_contamination(code: str) -> list[str]
        # Check for "from flask import"
        # Flag @app.route decorators
        # Return list of issues
        
    def _check_error_handling(code: str) -> bool
        # Verify try/except blocks present
        # Check for logging
```

**Validation Checklist:**
```python
checks = {
    "syntax": True,                    # ast.parse passes
    "streamlit_import": True,          # import streamlit present
    "domain_imports": True,            # pandas/sklearn/etc present
    "widgets_found": True,             # st.* patterns detected
    "error_handling": True,            # try/except blocks found
    "session_state": True,             # st.session_state usage
    "flask_free": True,                # No Flask imports
}
```

---

### 4. `core/reward_system.py` — RL Scoring

**Purpose:** Evaluate code quality and provide feedback

**Key Methods:**

```python
class RewardSystem:
    def score(
        self,
        code: str,
        app_started: bool,
        error: Optional[str],
        attempt: int,
        mode: str = "ml"
    ) -> float:
        # Calculate reward score (0-10)
        
    def _score_syntax(code: str) -> float
        # +2.0 if AST passes
        # 0.0 if syntax error
        
    def _score_imports(code: str) -> float
        # +1.0 for streamlit
        # +1.0 for domain lib
        
    def _score_patterns(code: str) -> float
        # +1.0 for widgets
        # +1.0 for error handling
        # +1.0 for session state
        
    def _score_runtime(app_started: bool) -> float
        # +4.0 if app started
        # -5.0 if crash
        
    def _detect_issues(code: str) -> list[dict]
        # Identify Flask imports
        # Find syntax errors
        # Detect incomplete patterns
```

**Scoring Rubric:**
```
Max: ~10.0 points per attempt

Basic Score:
├─ AST Syntax Check: +2.0
├─ Imports Check: +2.0 (streamlit + domain)
├─ Pattern Detection: +3.0 (widgets, error handling, session)
├─ App Start: +4.0
└─ Penalties:
   ├─ Flask contamination: -2.0
   ├─ App crash: -5.0
   └─ Per-attempt penalty: -0.5

Example: 8.5 = good code that runs
Example: 2.0 = syntax errors, requires refinement
Example: 0.0 = Flask code or major issues
```

---

### 5. `generator/base_streamlit.py` — Templates

**Purpose:** Offline fallback templates

**Template Types:**

```python
# 1. Chatbot Application
STREAMLIT_APP_CHATBOT = '''
# RAG + SLM pipeline
# - LlamaIndex + Chroma vector store
# - Session-based chat history
# - Real-time inference
'''

# 2. ML Model Application
STREAMLIT_APP_ML = '''
# SageMaker inference
# - Model artifact loading
# - Feature engineering UI
# - Prediction with confidence
# - Performance metrics
'''

# 3. Recommendation System
STREAMLIT_APP_RECOMMENDATION = '''
# Collaborative filtering
# - User-item interaction
# - Real-time recommendations
# - Interactive filters
'''

# 4. Data Analysis Dashboard
STREAMLIT_APP_ANALYTICS = '''
# EDA + visualization
# - Data profiling
# - Statistical summaries
# - Interactive charts
'''
```

**Usage:**
```python
from generator.base_streamlit import STREAMLIT_APP_ML

if condition_for_fallback:
    code = STREAMLIT_APP_ML.format(
        model_name="iris_classifier",
        features_list="sepal_length, sepal_width, petal_length, petal_width",
        target_classes="setosa, versicolor, virginica"
    )
```

---

## 🔄 Refinement Loop State Machine

```
┌──────────────────┐
│  START           │
│ [Run Prompt]     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  PLANNING        │
│ [Phase 1]        │ ← Router classifies task
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  INFRASTRUCTURE  │
│ [Phase 2]        │ ← Prepare RAG/SageMaker
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  GENERATION      │
│ [Phase 3]        │ ← LLM generates code
│  attempt = 1     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  TESTING         │
│ [Phase 4]        │ ← AST + pytest
└────────┬─────────┘
         │
    ┌────┴──────────────────┐
    │ Test Result?           │
    └────┬─────────────┬──────┘
         │ PASS        │ FAIL
         │             │
         ▼             ▼
    ┌────────────┐  ┌──────────────────┐
    │ LAUNCH     │  │ CHECK_RETRIES    │
    │ [Phase 5a] │  │ [Phase 5b]       │
    └────┬───────┘  │ attempt >= 5?    │
         │          └────┬──────────┬──┘
         │               │ NO       │ YES
         │               │          │
         │               ▼          ▼
         │          ┌──────────┐  ┌──────────┐
         │          │ REFINE   │  │ FALLBACK │
         │          │ REGENERATE│ │ TEMPLATE │
         │          │ (next)   │  │ [Offline]│
         │          └──┬───────┘  └────┬─────┘
         │             │               │
         │             └───────┬───────┘
         │                     │
         │              ┌──────▼──────┐
         │              │ GENERATION  │
         │              │ [Phase 3]   │
         │              │ attempt++   │
         │              └──────┬──────┘
         │                     │
         │                  (loop to TESTING)
         │
         ▼
    ┌──────────────────┐
    │ SUCCESS/COMPLETE │
    │ [Return Result]  │
    └──────────────────┘
```

---

## ⚙️ Configuration Reference

### `config.yaml` Sections Used:

```yaml
# Primary LLM Selection
primary_llm: "qwen"  # or "deepseek"

# Qwen Configuration (Free Backends)
qwen:
  hf_model: "Qwen/Qwen2.5-Coder-3B-Instruct"
  hf_token: ""  # Optional
  ollama_model: "qwen2.5-coder:3b"
  temperature: 0.3
  max_tokens: 4096

# Optional: DeepSeek (Paid)
deepseek:
  api_key: "sk-..."
  model: "deepseek-coder"
  temperature: 0.3
  max_tokens: 4096

# Optional: Gemini (Code Verification)
gemini:
  api_key: "sk-..."
  model: "gemini-1.5-pro-latest"

# Code Generation Settings
codegen:
  max_fix_attempts: 5
  workspace_dir: "Code_Generator/RAD-ML/workspace/current_app"
  test_timeout_seconds: 60

# Refinement Loop Parameters
refinement:
  max_retries: 5
  test_timeout_secs: 60
  app_start_timeout_secs: 300

# Streamlit Server
streamlit:
  host: "127.0.0.1"
  port: 8501

# Cost Control (Optional)
cost_control:
  auto_shutdown_mins: 30
  max_runtime_mins: 120
  enable_budget_alerts: true
```

---

## 🧪 Testing Examples

### Unit Test: Code Verifier

```python
from generator.code_verifier import CodeVerifier

def test_streamlit_verification():
    verifier = CodeVerifier()
    
    good_code = '''
import streamlit as st
import pandas as pd

def main():
    st.title("ML App")
    user_input = st.slider("Select", 0, 100)
    try:
        result = model.predict([user_input])
        st.write(f"Prediction: {result}")
    except Exception as e:
        st.error(f"Error: {e}")

if __name__ == "__main__":
    main()
'''
    
    is_valid, errors = verifier.verify(good_code)
    assert is_valid == True
    assert len(errors) == 0
```

### Unit Test: Reward System

```python
from core.reward_system import RewardSystem

def test_reward_scoring():
    reward = RewardSystem()
    
    # Perfect code that runs
    score1 = reward.score(
        code=good_streamlit_code,
        app_started=True,
        error=None,
        attempt=1
    )
    assert score1 > 8.0  # Should be high
    
    # Code with Flask contamination
    score2 = reward.score(
        code=flask_code,
        app_started=False,
        error="Flask import detected",
        attempt=1
    )
    assert score2 < 3.0  # Should be low
```

### Integration Test: Full Pipeline

```python
from core.refinement_loop import RefinementLoop

def test_full_pipeline(cfg):
    pipeline = RefinementLoop(cfg)
    
    result = pipeline.run(
        "Build a classifier for iris dataset"
    )
    
    assert result['status'] == 'success'
    assert result['app_path'].endswith('.py')
    assert result['metrics']['total_attempts'] <= 5
    assert result['metrics']['avg_reward'] > 7.0
```

---

## 🐛 Debugging Guide

### Common Issues:

**1. "LLM Backend Not Available"**
```
Check: ollama service running?
    ollama serve
    
Check: HuggingFace internet connection?
    ping huggingface.co
    
Check: API key configured?
    cat config.yaml | grep -A5 "qwen:"
```

**2. "Generated Code Has Syntax Errors"**
```
Verify with AST:
    python -c "import ast; ast.parse(open('app.py').read())"
    
Check LLM output:
    - Temperature too high? (increase max_tokens, lower temperature)
    - Missing imports? (regenerate with explicit requirements)
```

**3. "Streamlit App Fails to Start"**
```
Check port conflict:
    lsof -i :8501  # Unix
    netstat -ano | findstr :8501  # Windows
    
Check dependencies:
    pip install -r requirements.txt
    
Check logs:
    tail -f logs/rad_ml.log | grep streamlit
```

**4. "Refinement Loop Stuck (Max Retries Exceeded)"**
```
Increase max_retries in config.yaml:
    refinement:
      max_retries: 10  # Default is 5
      
Check error context being passed to LLM:
    - Is error message informative?
    - Is error from previous attempt included?
```

---

## 📊 Performance Metrics

### Expected Timings:

```
Phase 1 (Planning):        ~1-2 seconds
Phase 2 (Infrastructure):   ~5-15 seconds (depends on RAG/SM)
Phase 3 (Code Gen):        ~10-30 seconds (LLM inference)
Phase 4 (Testing):         ~5-10 seconds
Phase 5a (Launch):         ~5-10 seconds (streamlit startup)

Total Single Attempt:      ~25-70 seconds
Total Pipeline (2 attempts): ~50-140 seconds
```

### Optimization Tips:

1. **Speed up LLM calls:**
   - Use Ollama locally (faster than HF Hub)
   - Reduce max_tokens if quality acceptable
   - Cache LLM responses

2. **Speed up testing:**
   - Reduce test_timeout_secs
   - Run tests in parallel
   - Skip slow tests on refinement

3. **Speed up app startup:**
   - Pre-warm Streamlit process
   - Cache model artifacts
   - Lazy-load heavy dependencies

---

## 🎯 Future Enhancements

Potential improvements for v9+:

1. **Multi-Modal Generation**
   - Generate Dash apps in addition to Streamlit
   - FastAPI backends with React frontends

2. **Caching Layer**
   - Cache LLM responses
   - Cache generated code patterns
   - Reduce redundant computations

3. **Advanced RL**
   - Reinforcement learning agent
   - Learn from generation patterns
   - Self-improve over time

4. **Distributed Execution**
   - Parallel refinement attempts
   - Task queue for large batches
   - Model serving optimization

5. **Monitoring & Observability**
   - Detailed usage metrics
   - Cost tracking per generation
   - A/B testing framework

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-21  
**Maintained By:** Backend Team
