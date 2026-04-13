# RAD-ML Component Architecture & Responsibilities

## Component Interaction Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          REACT FRONTEND (Vite)                              │
│  - Authentication UI (login/register)                                       │
│  - Job submission form                                                      │
│  - Live logs viewer (SSE stream)                                            │
│  - Result tabs: Dataset, Model, Files, Explanation, Diagram                │
└──────────────────┬──────────────────────────────────────────────────────────┘
                   │ REST API (HTTP + JWT)
                   │
┌──────────────────▼──────────────────────────────────────────────────────────┐
│                        FLASK BACKEND (app.py)                               │
│  Routes:                                                                    │
│  - /api/auth/* (register, login, google)                                    │
│  - /api/pipeline/* (run, status, stream)                                    │
│  - /api/history/* (list, detail, delete)                                    │
│  - /api/health                                                              │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │ ORCHESTRATOR (orchestrator.py)                                     │     │
│  │ - Job lifecycle management                                         │     │
│  │ - Thread pool for async pipeline execution                         │     │
│  │ - Logging callbacks                                                │     │
│  │ - Cancellation checkpoints                                         │     │
│  │                                                                    │     │
│  │ ┌──────────────────────────────────────────────────────────────┐  │     │
│  │ │ _run_pipeline(job) [THREAD]                                 │  │     │
│  │ │ 1. Call DATA_COLLECTION_AGENT.run_collection()             │  │     │
│  │ │ 2. Call CODE_GENERATOR.run_codegen()                        │  │     │
│  │ │ 3. Store result in job.result                               │  │     │
│  │ │ 4. Sync to MongoDB via history_db                           │  │     │
│  │ └──────────────────────────────────────────────────────────────┘  │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │ AUTH_DB (auth_db.py) - SQLite                                      │     │
│  │ - User registration/login                                          │     │
│  │ - Password hashing (bcrypt)                                        │     │
│  │ - Google OAuth support                                             │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │ CHAT_HISTORY_DB (chat_history_db.py) - MongoDB                    │     │
│  │ - Store job logs & results                                         │     │
│  │ - User job history                                                 │     │
│  │ - Upsert operations for live updates                               │     │
│  └────────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
┌───────────────▼──────────────────┐   ┌──▼──────────────────────────────────┐
│   DATA COLLECTION AGENT           │   │   CODE GENERATOR (5 Layers)         │
│   (main.py)                       │   │   (main.py)                         │
│                                   │   │                                     │
│ Input: prompt, config, job_id     │   │ Input: db_results from DCA          │
│ Output: db_results (dataset+spec) │   │ Output: cg_result (code+explain)    │
│                                   │   │                                     │
│ ┌─────────────────────────────┐   │   │ ┌─────────────────────────────┐    │
│ │ 1. PromptParser             │   │   │ │ 1. PromptUnderstandingLayer │    │
│ │ Intent, keywords, fallback  │   │   │ │ Build ProjectSpec from      │    │
│ │ datasets                    │   │   │ │ prompt + data               │    │
│ │                             │   │   │ │                             │    │
│ │ 2. KaggleCollector          │   │   │ ┌─────────────────────────────┐    │
│ │ 3. UCICollector             │   │   │ │ 2. Planner                  │    │
│ │ 4. OpenMLCollector          │   │   │ │ File structure + function   │    │
│ │ (Parallel search)           │   │   │ │ signatures (no code yet)    │    │
│ │                             │   │   │ │                             │    │
│ │ 5. DatasetScorer            │   │   │ ┌─────────────────────────────┐    │
│ │ Rank by: keyword + rows +   │   │   │ │ 3. CodeGenFactory           │    │
│ │ columns + recency           │   │   │ │ Generate each file via LLM  │    │
│ │                             │   │   │ │ (app.py, predictor.py, etc) │    │
│ │ 6. DatasetMerger            │   │   │ │                             │    │
│ │ Combine 1+ CSVs             │   │   │ ┌─────────────────────────────┐    │
│ │                             │   │   │ │ 4. Validator                │    │
│ │ 7. S3Uploader               │   │   │ │ AST parsing + pytest        │    │
│ │ Upload final CSV            │   │   │ │                             │    │
│ │                             │   │   │ ┌─────────────────────────────┐    │
│ │ Fallback Tiers:             │   │   │ │ 5. RepairLoop               │    │
│ │ 1. Kaggle + UCI + OpenML    │   │   │ │ Auto-fix via LLM up to 5x   │    │
│ │ 2. Fallback refs (domain)   │   │   │ │                             │    │
│ │ 3. OpenML task search       │   │   │ ┌─────────────────────────────┐    │
│ └─────────────────────────────┘   │   │ │ 6. ExplainabilityEngine     │    │
│                                   │   │ │ Narrative + algorithm card  │    │
│ Data stores:                      │   │ │ + data story + diagram      │    │
│ - local CSV files                 │   │ │                             │    │
│ - S3 (final dataset)              │   │ ┌─────────────────────────────┘    │
│                                   │   │                                     │
└───────────────────────────────────┘   └─────────────────────────────────────┘
                                                         │
                                        ┌────────────────┴────────────────┐
                                        │ ML Engine                       │
                                        │                                 │
                                        │ • DataPreprocessor              │
                                        │   Train/test split              │
                                        │   Scaling, encoding             │
                                        │                                 │
                                        │ • SageMakerHandler              │
                                        │   S3 upload                     │
                                        │   XGBoost training              │
                                        │   Endpoint deployment           │
                                        │                                 │
                                        └─────────────────────────────────┘
```

---

## 1. Data Collection Agent - Detailed Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Input: "Predict housing prices from bedrooms, bathrooms, location"          │
└─────────────────────────────────────────┬──────────────────────────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────┐
                    │ PromptParser.parse(prompt)          │
                    │                                     │
                    │ Process:                            │
                    │ 1. Tokenize & lemmatize             │
                    │ 2. Detect intent keyword signals    │
                    │ 3. Extract task signals             │
                    │ 4. Extract domain                   │
                    │ 5. Extract keywords (1-word)        │
                    │ 6. Extract input/target params      │
                    │ 7. Lookup fallback dataset refs     │
                    └─────────────────────────────────────┘
                                          │
                    ┌─────────────────────┴──────────────────────┐
                    │ Emits: spec = {                            │
                    │   intent: "ml_model",                      │
                    │   task_type: "regression",                 │
                    │   domain: "housing",                       │
                    │   keywords: ["house", "price", ...],       │
                    │   input_params: ["bedrooms", ...],         │
                    │   target_param: "price",                   │
                    │   fallback_refs: ["house-prices-...]       │
                    │ }                                          │
                    └────────────────────────────────────────────┘
                                          │
                                          ▼
        ┌─────────────────────────────────────────────────────────┐
        │ TIER 1: Parallel Search (3 sources)                     │
        │ for each keyword in keywords[:4]:                       │
        │                                                         │
        │ ┌──────────────┐  ┌───────────┐  ┌────────────────┐    │
        │ │ Kaggle       │  │ UCI       │  │ OpenML         │    │
        │ │ .search(kw)  │  │ .search() │  │ .search()      │    │
        │ │              │  │           │  │                │    │
        │ │ Returns:     │  │ Returns:  │  │ Returns:       │    │
        │ │ [{meta...}]  │  │ [{meta}]  │  │ [{meta...}]    │    │
        │ └──────────────┘  └───────────┘  └────────────────┘    │
        │                                                         │
        │ Result: all_metas = [~15 candidates]                   │
        │ Stop condition: ≥5 candidates or exhausted keywords    │
        └─────────────────────────────────────────────────────────┘
                                          │
                          ┌───────────────┴────────────────┐
                          │                                │
                  ┌─ NO ─►┌─────────────────────────────┐  │
                  │       │ TIER 2: Fallback search     │  │
                  │       │ Use domain-specific refs    │  │
                  │       │ E.g., housing →             │  │
                  │       │ harlfoxem/house-prices-...  │  │
                  │       └─────────────────────────────┘  │
                  │                                        │
        If 0 results                              └─ NO ──► TIER 3:
        from Tier 1                                       OpenML
                                                         task/domain
                                          │
                                          ▼
                    ┌─────────────────────────────────────┐
                    │ For each candidate metadata:         │
                    │ score_metadata(meta, spec)          │
                    │                                     │
                    │ score = 0.40 × keyword_match        │
                    │       + 0.30 × row_count            │
                    │       + 0.20 × column_match         │
                    │       + 0.10 × recency              │
                    │                                     │
                    │ Sort by score (descending)          │
                    │ Take top 8                          │
                    └─────────────────────────────────────┘
                                          │
                                          ▼
        ┌─────────────────────────────────────────────────────────┐
        │ For each of top 8:                                      │
        │ 1. Download from source (Kaggle/UCI/OpenML)             │
        │ 2. Extract CSV files                                    │
        │ 3. Choose largest CSV                                   │
        │ 4. score_csv(path, meta, spec) - per-file scoring       │
        │ 5. Store: (csv_path, score, meta)                       │
        │                                                         │
        │ Stop condition: ≥500 rows AND ≥2 candidates            │
        │                                                         │
        │ Result: scored_csvs = [(path, score, meta), ...]        │
        └─────────────────────────────────────────────────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────┐
                    │ Sort by score (descending)          │
                    │ Take best 1-3 CSVs for merging      │
                    │                                     │
                    │ DatasetMerger.build_final_dataset()│
                    │ - Deduplicate rows                  │
                    │ - Align columns                     │
                    │ - Preserve source tracking          │
                    │                                     │
                    │ Result: df (merged dataframe)       │
                    └─────────────────────────────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────┐
                    │ S3Uploader.upload_dataset()         │
                    │ → S3 URI                            │
                    └─────────────────────────────────────┘
                                          │
                                          ▼
        ┌─────────────────────────────────────────────────────────┐
        │ Output: db_results = {                                  │
        │   job_id, prompt, spec,                                 │
        │   dataset: {                                            │
        │     local_path (CSV),                                   │
        │     s3_uri,                                             │
        │     columns, row_count,                                 │
        │     source_count (1, 2, or 3),                          │
        │     preview_rows (first 5-10),                          │
        │     merged (bool)                                       │
        │   },                                                    │
        │   top_sources (metadata of best datasets)               │
        │ }                                                       │
        └─────────────────────────────────────────────────────────┘
```

---

## 2. Code Generator - 5-Layer Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Input: db_results (from Data Collection Agent)                              │
│ Output: cg_result (generated code + explanations)                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
                    ┌────────────────────────────────────┐
                    │ DataPreprocessor.preprocess()      │
                    │                                    │
                    │ - Load CSV into pandas             │
                    │ - Auto-detect target column        │
                    │ - Auto-detect task type (class/reg)│
                    │ - Handle missing values            │
                    │ - Encode categorical features      │
                    │ - Scale numerical features         │
                    │ - Train/test split (80/20)         │
                    │ - Write to temp train/val CSVs     │
                    │                                    │
                    │ Output: pre_result = {             │
                    │   feature_cols, target_col,        │
                    │   task_type,                       │
                    │   train_path, val_path,            │
                    │   stats (n_samples, etc)           │
                    │ }                                  │
                    └────────────────────────────────────┘
                                          │
                                          ▼
                    ┌────────────────────────────────────┐
                    │ SageMakerHandler.upload_data()     │
                    │                                    │
                    │ - Upload train/val CSVs to S3      │
                    │ - Return S3 URIs                   │
                    └────────────────────────────────────┘
                                          │
                                          ▼
                    ┌────────────────────────────────────┐
                    │ SageMakerHandler.run_training()    │
                    │                                    │
                    │ - Launch XGBoost training job      │
                    │ - Wait for completion              │
                    │ - Create model endpoint            │
                    │ - Return: sm_meta = {              │
                    │     job_name, status,              │
                    │     endpoint_name, etc             │
                    │   }                                │
                    └────────────────────────────────────┘
                                          │
                                          ▼
        ┌─────────────────────────────────────────────────────────┐
        │ LAYER 1: PromptUnderstandingLayer.build_spec()         │
        │                                                         │
        │ Input: prompt, spec, data_info, sm_meta, preprocess   │
        │                                                         │
        │ Uses LLM to:                                            │
        │ 1. Understand user intent                              │
        │ 2. Map to task type (regression/classification)        │
        │ 3. Select framework (Flask for API)                    │
        │ 4. Select model type (XGBoost)                         │
        │ 5. List deliverables (app.py, predictor.py, etc)      │
        │                                                         │
        │ Output: project_spec = {                               │
        │   task, task_type, framework,                          │
        │   model_type, feature_cols, target_col,                │
        │   deliverables, constraints, endpoint_name, etc        │
        │ }                                                       │
        └─────────────────────────────────────────────────────────┘
                                          │
                                          ▼
        ┌─────────────────────────────────────────────────────────┐
        │ LAYER 2: Planner.plan()                                │
        │                                                         │
        │ Input: project_spec                                    │
        │                                                         │
        │ Uses LLM to create:                                    │
        │ 1. Architecture overview                               │
        │ 2. File structure (which files needed)                 │
        │ 3. Key functions per file (signatures only)            │
        │ 4. Dependencies list                                   │
        │ 5. Validation strategy                                 │
        │ 6. Edge cases to handle                                │
        │                                                         │
        │ Output: plan = {                                       │
        │   file_structure: {filename: description},             │
        │   key_functions: {filename: [func_sigs]},              │
        │   dependencies: [packages],                            │
        │   ...                                                  │
        │ }                                                       │
        └─────────────────────────────────────────────────────────┘
                                          │
                                          ▼
        ┌─────────────────────────────────────────────────────────┐
        │ LAYER 3: CodeGenFactory.generate_all()                 │
        │                                                         │
        │ For each file in plan:                                 │
        │ 1. Generate context (project_spec + plan)              │
        │ 2. Call LLM to generate full file                      │
        │ 3. Write to disk                                       │
        │ 4. Store in written_files dict                         │
        │                                                         │
        │ Files generated:                                       │
        │ - app.py (Flask endpoints)                             │
        │ - predictor.py (SageMaker caller)                      │
        │ - train.py (local training/testing)                    │
        │ - requirements.txt (dependencies)                      │
        │ - README.md (usage guide)                              │
        │ - test_model.py (unit tests)                           │
        │                                                         │
        │ Output: written_files = {                              │
        │   "app.py": Path("/generated/app.py"),                 │
        │   "predictor.py": Path(...),                           │
        │   ...                                                  │
        │ }                                                       │
        └─────────────────────────────────────────────────────────┘
                                          │
                                          ▼
        ┌─────────────────────────────────────────────────────────┐
        │ LAYER 4: Validator.validate()                          │
        │                                                         │
        │ For each written file:                                 │
        │ 1. AST parsing (Python syntax check)                   │
        │ 2. Security check (no dangerous imports)               │
        │ 3. Relevance check (uses declared functions)           │
        │ 4. Run pytest (if test file)                           │
        │                                                         │
        │ Output: val_report = {                                 │
        │   all_passed: bool,                                    │
        │   failed_files: [...],                                 │
        │   summary(): str                                       │
        │ }                                                       │
        └─────────────────────────────────────────────────────────┘
                                          │
                ┌─────────────────────────┴─────────────────────┐
                │                                               │
         ┌── YES▼──┐                              ┌────────NO──┘
         │ All OK? │                              │
         └─────────┘                              ▼
                │                    ┌──────────────────────────┐
                │                    │ LAYER 5: RepairLoop      │
                │                    │                          │
                │                    │ For each failed file:    │
                │                    │ max 5 attempts per file  │
                │                    │                          │
                │                    │ 1. Analyze error         │
                │                    │ 2. Call LLM to fix       │
                │                    │ 3. Re-validate           │
                │                    │ 4. If still broken:      │
                │                    │    retry or skip         │
                │                    │                          │
                │                    │ Output: repaired files   │
                │                    └──────────────────────────┘
                │                              │
                └──────────────────┬───────────┘
                                   │
                                   ▼
        ┌─────────────────────────────────────────────────────────┐
        │ LAYER 6: ExplainabilityEngine.explain()                │
        │                                                         │
        │ Generate 6 explanation tabs:                           │
        │ 1. Narrative (plain-English explanation)               │
        │ 2. Algorithm Card (why XGBoost, pros/cons)             │
        │ 3. Data Story (sources, scoring, merge decisions)      │
        │ 4. Usage Guide (step-by-step how to use)               │
        │ 5. Code Preview (first 60 lines of each file)          │
        │ 6. Architecture Diagram (PNG via graphviz)             │
        │                                                         │
        │ Output: explanation = {                                │
        │   narrative: str,                                      │
        │   algorithm_card: {...},                               │
        │   data_story: str,                                     │
        │   usage_guide: str,                                    │
        │   code_preview: {filename: first_lines},               │
        │   diagram_path: str (to PNG)                           │
        │ }                                                       │
        └─────────────────────────────────────────────────────────┘
                                          │
                                          ▼
        ┌─────────────────────────────────────────────────────────┐
        │ Final cg_result = {                                     │
        │   endpoint_name,                                        │
        │   deploy_url,                                           │
        │   app_path,                                             │
        │   sm_meta (SageMaker metadata),                         │
        │   preprocess (features, target, etc),                   │
        │   generated_files (dict of all files),                  │
        │   validation_summary,                                  │
        │   explanation (all 6 tabs)                             │
        │ }                                                       │
        └─────────────────────────────────────────────────────────┘
```

---

## 3. Test Pyramid

```
                          ╱╲
                         ╱  ╲
                        ╱ E2E ╲          (1% of tests)
                       ╱Tests ╲
                      ╱─────────╲
                     ╱           ╲
                    ╱ Integration  ╲  (5% of tests)
                   ╱  Tests         ╲
                  ╱─────────────────╲
                 ╱                   ╲
                ╱      Unit Tests    ╲ (94% of tests)
               ╱ (Mocked dependencies)╲
              ╱_________________________╲

Unit Tests (Fast, isolated):
├── test_prompt_parser.py (8 tests)
│   └─ Intent detection, keyword extraction
├── test_dataset_scorer.py (6 tests)
│   └─ Scoring formula validation
├── test_dataset_merger.py (4 tests)
│   └─ Dataset merging logic
├── test_kaggle_collector.py (5 tests, mocked)
│   └─ Search/download logic
├── test_codegen_pipeline.py (12 tests, mocked LLM)
│   └─ 5-layer pipeline validation
└── test_explainability.py (4 tests)
    └─ Explanation generation

Integration Tests (Medium speed):
└── SampleTests/
    ├── test_complete_system_integration.py
    │   └─ Full flow: auth → collection → codegen
    ├── test_end_to_end_integration.py
    │   └─ API → database → result
    └── test_pipeline.py
        └─ Orchestrator + job management

E2E Tests (Slow, full system):
└── SampleTests/
    └── test_complete_system_integration.py
        └─ Requires: backend + frontend running
```

---

## 4. Key Responsibilities by Component

### PromptParser (Brain)
**Responsibility**: Convert user intent into machine-readable spec

**Input**: "Predict house prices from bedrooms, bathrooms, location"  
**Output**:
```python
{
    "intent": "ml_model",              # ml_model | chatbot
    "task_type": "regression",         # regression | classification | clustering
    "domain": "housing",               # detected domain
    "keywords": ["house", "price"],    # 1-word search terms
    "input_params": ["bedrooms", "bathrooms", "location"],
    "target_param": "price",
    "fallback_refs": [                 # Known Kaggle datasets for fallback
        "camnugent/california-housing-prices",
        "harlfoxem/house-prices-dataset"
    ]
}
```

**Key Methods**:
- `parse(prompt: str) -> dict` - Main entry point
- `_extract_keywords(text) -> list` - Get search keywords
- `_detect_intent(text) -> str` - Classify intent
- `_get_fallback_datasets(domain) -> list` - Lookup fallback refs

---

### Collectors (Kaggle, UCI, OpenML)
**Responsibility**: Search and download datasets from public repositories

**Common interface**:
```python
class Collector:
    def search(keyword: str, spec: dict) -> list[dict]  # Returns metadata
    def download(ref: str) -> list[Path]                # Downloads and returns CSVs
```

**KaggleCollector**:
- Uses Kaggle API (requires credentials)
- Returns: `[{title, ref, num_instances, num_features, vote_count}, ...]`

**UCICollector**:
- Scrapes UCI ML Repository
- Returns: `[{title, ref, num_instances, num_features}, ...]`

**OpenMLCollector**:
- Uses OpenML API (no credentials required)
- Returns: `[{title, ref, num_instances, num_features}, ...]`

---

### DatasetScorer
**Responsibility**: Rank candidates using weighted scoring formula

**Scoring factors**:
```
score = 0.40 × keyword_match     (how many keywords in title/description)
      + 0.30 × row_count         (0 if <500, 1 if >50k)
      + 0.20 × column_match      (how many spec columns/target in CSV)
      + 0.10 × recency           (0 if >3yrs old, 1 if fresh)
```

**Key Methods**:
- `score_metadata(meta: dict, spec: dict) -> float` - Score metadata only
- `score_csv(path: Path, meta: dict, spec: dict) -> float` - Score actual CSV

---

### DatasetMerger
**Responsibility**: Combine multiple CSVs into one clean dataset

**Process**:
1. Load all CSVs
2. Identify common columns
3. Stack/merge based on matching columns
4. Deduplicate rows
5. Preserve source tracking
6. Preview first 5-10 rows

---

### S3Uploader
**Responsibility**: Upload final dataset to AWS S3 for SageMaker training

**Key Methods**:
- `upload_dataset(path: Path, job_id: str) -> str` - Returns S3 URI

---

### DataPreprocessor
**Responsibility**: Clean data for ML training

**Process**:
1. Load CSV → pandas DataFrame
2. Auto-detect target column (if not specified)
3. Auto-detect task (regression vs classification)
4. Handle missing values (drop/impute)
5. Encode categorical features (label encoder)
6. Scale numerical features (StandardScaler)
7. Split into train/test (80/20)
8. Compute statistics (n_samples, feature_importance)

**Output**:
```python
{
    "feature_cols": ["bedrooms", "bathrooms"],
    "target_col": "price",
    "task_type": "regression",
    "train_path": Path(".../train.csv"),
    "val_path": Path(".../val.csv"),
    "stats": {"train_rows": 1000, "val_rows": 250, ...}
}
```

---

### SageMakerHandler
**Responsibility**: Train model on AWS SageMaker, create endpoint

**Key Methods**:
- `upload_data(train_path, val_path, job_id) -> tuple(s3_train_uri, s3_val_uri)`
- `run_training(...) -> dict` - Launch XGBoost job, wait, create endpoint

**Output**:
```python
{
    "job_name": "xgb-job-xyz",
    "status": "InService",
    "endpoint_name": "xgb-endpoint-xyz",
    "model_name": "xgb-model-xyz"
}
```

---

### PromptUnderstandingLayer (Layer 1)
**Responsibility**: Build structured ProjectSpec from raw prompt

**Uses LLM to**:
1. Parse user intent and goals
2. Select framework (Flask recommended)
3. Select model type (XGBoost for tabular)
4. Specify deliverables (app.py, test.py, etc)
5. List constraints (use endpoint, production code, etc)

**Output**: ProjectSpec dict with all metadata

---

### Planner (Layer 2)
**Responsibility**: Design architecture without writing code

**Outputs**:
- File structure (which files needed + purpose)
- Function signatures per file (no implementation)
- Dependencies required
- Validation strategy

---

### CodeGenFactory (Layer 3)
**Responsibility**: Generate file-by-file code

**For each file in plan**:
1. Build rich context (project_spec + plan + requirements)
2. Call Gemini Flash LLM
3. Parse response into valid Python
4. Write to disk

**Files generated**:
- `app.py` - Flask web server
- `predictor.py` - Calls SageMaker endpoint
- `train.py` - Local training/testing
- `requirements.txt` - Python dependencies
- `README.md` - Usage documentation
- `test_model.py` - Unit tests

---

### Validator (Layer 4)
**Responsibility**: Test generated code for correctness

**Checks**:
1. **AST** - Python syntax valid
2. **Security** - No dangerous imports (subprocess, eval, etc)
3. **Relevance** - Functions used, no dead code
4. **Tests** - Run pytest if test file

---

### RepairLoop (Layer 5)
**Responsibility**: Auto-fix broken files using LLM

**Process per failed file**:
1. Parse error message
2. Call LLM with error + original code
3. LLM generates fix
4. Re-validate
5. If still broken: retry up to 5× or mark as "skipped"

---

### ExplainabilityEngine (Layer 6)
**Responsibility**: Generate plain-English explanations + diagrams

**Generates 6 tabs**:
1. **Narrative** - Why we chose this model, how it works
2. **Algorithm Card** - XGBoost explained: pros, cons, when to use
3. **Data Story** - Where data came from, how we scored/merged it
4. **Usage Guide** - Step-by-step: how to run/deploy your model
5. **Code Preview** - First 60 lines of each generated file
6. **Diagram** - Architecture PNG (Flask → SageMaker endpoint)

---

## 5. Error Handling & Fallbacks

### Data Collection Fallback Tiers

```
Query: "house prices"

        │
        ▼
    ┌────────────────┐
    │ TIER 1 Search  │
    │ +Kaggle +UCI   │
    │ +OpenML        │
    └────────────────┘
        │
    ┌───┴──────────────┐
    │ Found results?   │
    └──┬─── NO ───┬────┘
       │          YES → Continue
       │
       ▼
    ┌────────────────┐
    │ TIER 2 Search  │
    │ Fallback refs  │
    │ e.g. "house"   │
    │ → Kaggle dsid  │
    └────────────────┘
       │
    ┌──┴──────────────┐
    │ Found results?  │
    └──┬─── NO ───┬───┘
       │          YES → Continue
       │
       ▼
    ┌────────────────┐
    │ TIER 3 Search  │
    │ Task-based:    │
    │ OpenML         │
    │ "regression"   │
    └────────────────┘
       │
    ┌──┴──────────────┐
    │ Found results?  │
    └──┬─── NO ───┬───┘
       │          YES → Continue
       │
       ▼
    ┌────────────────┐
    │ Domain-based:  │
    │ OpenML         │
    │ "housing"      │
    └────────────────┘
       │
    ┌──┴──────────────┐
    │ Found results?  │
    └──┬─── YES ──┬───┘
       │           │
       │           └─► Continue
       │
       ▼
    Error: No datasets found
    Suggestion: Use "Upload CSV" button
```

---

## 6. Data Flow Example: "Predict Gold Prices"

```
User Input:
"Build an ML model to predict gold prices from historical market data"

┌─ DCA Stage 1: Parse ──────────────────────────────────────────┐
│ spec = {                                                      │
│   intent: "ml_model",                                         │
│   task_type: "regression",                                    │
│   domain: "finance",                                          │
│   keywords: ["gold", "price", "market", "time series"],       │
│   target_param: "price"                                       │
│ }                                                             │
└──────────────────────────────────────────────────────────────┘
        ↓
┌─ DCA Stage 2: Search ──────────────────────────────────────────┐
│ → Search Kaggle: "gold price" → 20 results                   │
│   Top: "Gold Futures Price Data" (12000 rows)                │
│ → Search UCI: "time series" → 3 results                      │
│ → Search OpenML: "financial" → 8 results                     │
│                                                              │
│ all_metas = 31 candidates                                    │
└──────────────────────────────────────────────────────────────┘
        ↓
┌─ DCA Stage 3: Score & Rank ────────────────────────────────────┐
│ Top 3:                                                         │
│ 1. Gold Futures (score: 0.92)  [Kaggle, 12k rows]            │
│ 2. LBMA Gold Fixing (0.85)     [UCI, 8k rows]                │
│ 3. Precious Metals (0.78)      [OpenML, 5k rows]             │
└──────────────────────────────────────────────────────────────┘
        ↓
┌─ DCA Stage 4: Download & Merge ────────────────────────────────┐
│ Download top 1: Gold Futures (12000 rows)                     │
│ Columns: [date, open, high, low, close, volume]               │
│ ✓ All required columns present                                │
│                                                              │
│ Merge: dataset = Gold Futures only (12k rows)                 │
│ merged = false (single source)                                │
└──────────────────────────────────────────────────────────────┘
        ↓
┌─ DCA Stage 5: Upload to S3 ────────────────────────────────────┐
│ s3://ml-datasets/job_abc123/gold_prices.csv                   │
└──────────────────────────────────────────────────────────────┘
        ↓ db_results = {...}
┌─ CG Stage 0: Preprocess ───────────────────────────────────────┐
│ - Load 12k rows × 6 columns                                   │
│ - Target: close                                               │
│ - Features: [open, high, low, volume] (date → index)          │
│ - Train/val split: 9600 / 2400                                │
│ - Scale features: StandardScaler                              │
└──────────────────────────────────────────────────────────────┘
        ↓ pre_result = {...}
┌─ CG Stage 1-5: Generate Code ──────────────────────────────────┐
│ app.py           (Flask server)                               │
│ predictor.py     (SageMaker endpoint caller)                   │
│ train.py         (Local training/test)                        │
│ requirements.txt (Dependencies)                               │
│ README.md        (Usage guide)                                │
│ test_model.py    (Unit tests)                                 │
│                                                              │
│ Validation: ✓ All AST checks pass                            │
│             ✓ All tests pass                                 │
│             ✓ No repairs needed                              │
└──────────────────────────────────────────────────────────────┘
        ↓ written_files = {...}
┌─ CG Stage 6: Explain ──────────────────────────────────────────┐
│ Tabs:                                                          │
│ 1. Narrative: "XGBoost is ideal for time-series price..."    │
│ 2. Algorithm: "Why XGBoost: fast, handles trends..."         │
│ 3. Data Story: "Sourced from Kaggle Gold Futures..."         │
│ 4. Usage: "1) Load model 2) Call endpoint 3) Get price..."   │
│ 5. Code: (first 60 lines of app.py, predictor.py, etc)       │
│ 6. Diagram: (PNG showing Flask → SageMaker flow)             │
└──────────────────────────────────────────────────────────────┘
        ↓ cg_result = {...}
┌─ Final Result ─────────────────────────────────────────────────┐
│ ✓ Model deployed to: xgb-endpoint-job-abc123                 │
│ ✓ API running at: http://localhost:7000                      │
│ ✓ Endpoint accepts JSON: {open, high, low, volume}           │
│ ✓ Returns JSON: {predicted_price: 2150.42}                   │
│ ✓ All files generated in: generated/                          │
│ ✓ Full explanation with 6 tabs + diagram                     │
└──────────────────────────────────────────────────────────────┘
```

---

That's the complete architectural breakdown! Each component has clear responsibilities and well-defined interfaces.

