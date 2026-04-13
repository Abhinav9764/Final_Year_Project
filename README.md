# RAD-ML v4 — Rapid Adaptive Data · Machine Learning

> Type one sentence. Get a trained, deployed ML model — with a full explainability report.

RAD-ML is an end-to-end agentic pipeline that converts a plain-English prompt into a
fully trained, cloud-hosted ML application, complete with dataset preview, generated
code, architecture diagrams, and a plain-English explanation of every decision made.

---

## Architecture

```
User Prompt (via chat UI)
         │
         ▼
┌─────────────────────────┐
│  Auth Layer             │  SQLite (users) + JWT
│  Login / Register       │  Google OAuth (optional)
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Data Collection Agent  │  Kaggle + UCI ML Repository + OpenML
│  Scoring-based (no RL)  │  4-factor score: keyword · rows · columns · recency
│  Merger (≥500 rows)     │  S3 upload of final CSV
└────────────┬────────────┘
             │  db_results.json
             ▼
┌─────────────────────────┐
│  Code Generator (5 layers)│
│  1. Prompt Understanding │  ProjectSpec JSON via Gemini Flash
│  2. Architect Planner    │  File structure + function signatures (no code yet)
│  3. File-by-File Codegen │  app.py, predictor.py, train.py, tests, README
│  4. Validator            │  AST + security + relevance + pytest
│  5. Repair Loop          │  LLM auto-fix up to 5× per file
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  AWS SageMaker          │  XGBoost train + endpoint deploy
│  (mock mode for dev)    │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Explainability Engine  │
│  • LLM narrative        │  Plain-English explanation (Gemini Flash)
│  • Algorithm card       │  Why XGBoost, how it works, pros/cons
│  • Usage guide          │  Step-by-step "how to use your model"
│  • Data story           │  Sources searched, scoring, merge decisions
│  • Architecture diagram │  PNG via Python diagrams + Graphviz
│  • Code preview         │  First 60 lines of each generated file
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Chat UI                │  React + Vite · Syne + JetBrains Mono
│  Auth: login/register   │  Greeting: "Hello, username!"
│  Sidebar: job history   │  DynamoDB chat history + in-memory fallback
│  Live log: SSE stream   │  Pipeline stepper + filter chips
│  Result card: 5 tabs    │  Summary · Dataset · Model · Files · Explain
│  Explain panel: 6 tabs  │  Narrative · Algorithm · Data · Usage · Code · Diagram
└─────────────────────────┘
```

---

## Quick Start

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
# For architecture diagrams (optional but recommended):
# Ubuntu/Debian:
apt-get install graphviz
# macOS:
brew install graphviz
```

### 2. Configure credentials

Copy `.env.example` to `.env` or export the same environment variables. `config.yaml`
is intentionally sanitized in git and acts as a safe default template:

```yaml
kaggle:
  username: "YOUR_KAGGLE_USERNAME"
  key:      "YOUR_KAGGLE_API_KEY"

aws:
  s3_bucket:       "your-bucket-name"
  sagemaker_role:  "arn:aws:iam::ACCOUNT:role/SageMakerExecutionRole"

gemini:
  api_key: "YOUR_GEMINI_API_KEY"

auth:
  jwt_secret_key: "change-this-to-a-long-random-string"
```

### 3. Configure NoSQL history (optional but recommended)

```bash
# Default provider: DynamoDB
# Table name: radml-chat-history
```

### 4. Start the backend

```bash
cd Chatbot_Interface/backend
python app.py
# Listening on http://localhost:5001
```

### 5. Start the frontend

```bash
cd Chatbot_Interface/frontend
npm install
npm run dev
# Open http://localhost:5173
```

---

## Project Structure

```
RAD-ML/
├── config.yaml                          ← all credentials & settings
├── requirements.txt
├── conftest.py / pytest.ini
│
├── Data_Collection_Agent/
│   ├── main.py                          ← collection pipeline entry
│   ├── brain/prompt_parser.py           ← NLP intent + param extraction
│   ├── collectors/
│   │   ├── kaggle_collector.py
│   │   ├── uci_collector.py             ← free, no auth
│   │   └── openml_collector.py          ← free, no auth
│   └── utils/
│       ├── dataset_scorer.py            ← 4-factor scoring
│       ├── dataset_merger.py            ← merge when < 500 rows
│       └── s3_uploader.py
│
├── Code_Generator/RAD-ML/
│   ├── main.py                          ← 5-layer + explain pipeline
│   ├── core/llm_client.py              ← Gemini Flash wrapper
│   ├── engines/ml_engine/
│   │   ├── data_preprocessor.py
│   │   └── sagemaker_handler.py
│   ├── generator/
│   │   ├── prompt_understanding.py     ← Layer 1
│   │   ├── planner.py                  ← Layer 2
│   │   ├── code_gen_factory.py         ← Layer 3
│   │   ├── validator.py                ← Layer 4
│   │   └── repair_loop.py              ← Layer 5
│   └── explainability/
│       └── engine.py                   ← Layer 6: Explain
│
├── Chatbot_Interface/
│   ├── backend/
│   │   ├── app.py                      ← Flask REST API + JWT auth
│   │   ├── auth_db.py                  ← SQLite users (bcrypt)
│   │   ├── chat_history_db.py          ← DynamoDB + in-memory fallback
│   │   └── orchestrator.py             ← job lifecycle
│   └── frontend/src/
│       ├── App.jsx                     ← auth router + chat layout
│       ├── components/
│       │   ├── AuthPage.jsx            ← login/register + particle bg
│       │   ├── Sidebar.jsx             ← history + user profile
│       │   ├── PromptComposer.jsx      ← auto-resize + starter prompts
│       │   ├── LiveLog.jsx             ← pipeline stepper + SSE
│       │   ├── ResultCard.jsx          ← 5-tab result view
│       │   └── ExplainPanel.jsx        ← 6-tab explainability panel
│       └── hooks/
│           ├── useAuth.js
│           └── usePipeline.js
│
└── tests/                              ← 63 tests, all passing
    ├── test_explainability.py          ← 14 tests
    ├── test_codegen_pipeline.py        ← 11 tests
    ├── test_dataset_merger.py          ← 9 tests
    ├── test_openml_collector.py        ← 6 tests
    ├── test_data_preprocessor.py       ← 7 tests
    ├── test_dataset_scorer.py          ← 6 tests
    ├── test_prompt_parser.py           ← 8 tests
    └── test_sagemaker_handler.py       ← 2 tests
```

---

## Running Tests

```bash
pytest tests/ -v
# 63 tests, all passing (no AWS/Gemini credentials needed)
```

---

## API Reference

### Auth

| Method | Endpoint | Body | Returns |
|--------|----------|------|---------|
| POST | `/api/auth/register` | `{username, password, email?}` | `{token, user}` |
| POST | `/api/auth/login` | `{username, password}` | `{token, user}` |
| POST | `/api/auth/google` | `{id_token}` | `{token, user}` |
| GET  | `/api/auth/me` | — (JWT) | `{user}` |
| POST | `/api/auth/logout` | — | `{ok}` |

### Pipeline (JWT required)

| Method | Endpoint | Returns |
|--------|----------|---------|
| POST | `/api/pipeline/run` | `{job_id}` |
| GET  | `/api/pipeline/status/<id>` | Full job state |
| GET  | `/api/pipeline/stream/<id>` | SSE live logs |

### History & Explain (JWT required)

| Method | Endpoint | Returns |
|--------|----------|---------|
| GET    | `/api/history` | List of user's jobs |
| GET    | `/api/history/<id>` | Full job detail |
| DELETE | `/api/history/<id>` | `{deleted}` |
| DELETE | `/api/history` | `{deleted_count}` |
| GET    | `/api/explain/<id>` | Full explanation payload |

---

## Cloud Costs

Only AWS costs money:

| Service | Per job |
|---------|---------|
| S3 storage | < $0.01 |
| SageMaker `ml.m5.large` training (≤1h) | ~$0.115 |
| SageMaker endpoint (per hour) | ~$0.115/h |

**Delete endpoints when not needed.**  
Everything else (Kaggle, UCI, OpenML, Gemini Flash) is completely free.
