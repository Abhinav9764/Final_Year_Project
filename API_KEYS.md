# RAD-ML — API Keys & Setup Guide

## Quick Start Checklist

| Step | What | Where to get it | Required? |
|------|------|-----------------|-----------|
| 1 | Kaggle API key | https://www.kaggle.com/settings/account → "Create New Token" | ✅ Yes |
| 2 | Gemini API key | https://aistudio.google.com/apikey → "Create API key" | ✅ Yes |
| 3 | AWS credentials | AWS Console → IAM → Users → Security credentials | ⚠️ Optional (mock mode) |
| 4 | OpenML API key | https://www.openml.org/auth/sign-up | ❌ Optional (anonymous ok) |
| 5 | DynamoDB table | AWS Console → DynamoDB | ❌ Optional (in-memory fallback) |

---

## 1. Kaggle API Key (REQUIRED for data collection)

Kaggle provides free CSV datasets — the heart of RAD-ML's data collection.

**Steps:**
1. Go to https://www.kaggle.com/settings/account
2. Scroll to "API" section
3. Click **"Create New Token"** — downloads `kaggle.json`
4. Open `kaggle.json` — it looks like:
   ```json
   {"username": "yourname", "key": "abcdef1234567890..."}
   ```
5. Copy those values into `config.yaml`:
   ```yaml
   kaggle:
     username: "yourname"
     key:      "abcdef1234567890..."
   ```

**Test it works:**
```bash
cd RAD-ML
python -c "
import os, sys
sys.path.insert(0, 'Data_Collection_Agent')
from collectors.kaggle_collector import KaggleCollector
import yaml
config = yaml.safe_load(open('config.yaml'))
kc = KaggleCollector(config)
results = kc.search('iris')
print(f'Kaggle OK — found {len(results)} datasets')
"
```

---

## 2. Gemini API Key (REQUIRED for code generation)

Gemini Flash is free-tier — no credit card needed for reasonable usage.

**Steps:**
1. Go to https://aistudio.google.com/apikey
2. Click **"Create API key"**
3. Copy the key (starts with `AIza...`)
4. Set in `config.yaml`:
   ```yaml
   llm:
     gemini_api_key: "AIzaSy..."
     gemini_model:   "gemini-1.5-flash"
   ```

**Test it works:**
```bash
python -c "
import google.generativeai as genai
genai.configure(api_key='YOUR_KEY_HERE')
m = genai.GenerativeModel('gemini-1.5-flash')
print(m.generate_content('Say hello').text)
"
```

---

## 3. AWS Credentials (OPTIONAL — mock mode if absent)

If not set, SageMaker runs in **mock mode** — all pipeline steps complete
but no real ML training happens. The generated Flask app is still created.

**Steps for real AWS:**
1. Go to https://console.aws.amazon.com/iam
2. Users → Your user → "Security credentials" → "Create access key"
3. Set in `config.yaml`:
   ```yaml
   aws:
     region:            "us-east-1"
     s3_bucket:         "your-bucket-name"
     sagemaker_role:    "arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME"
     access_key_id:     "AKIA..."
     secret_access_key: "..."
   ```

**Required IAM permissions:** `s3:PutObject`, `s3:GetObject`,
`sagemaker:CreateTrainingJob`, `sagemaker:CreateEndpoint`

---

## 4. OpenML API Key (OPTIONAL)

Anonymous access works for most searches. An API key raises rate limits.

1. Sign up: https://www.openml.org/auth/sign-up
2. Go to: https://www.openml.org/settings/account → copy API key
3. Set in `config.yaml`:
   ```yaml
   openml:
     api_key: "your_key_here"
     enabled: true
   ```

---

## 5. DynamoDB History Table (OPTIONAL)

Without DynamoDB, chat history is stored in-memory and is lost on restart.

1. Open AWS Console → DynamoDB
2. Create table `radml-chat-history`
3. Use:
   - Partition key: `user_id` (String)
   - Sort key: `job_id` (String)
4. Set in `config.yaml`:
   ```yaml
   nosql:
     provider: "dynamodb"
     region: "us-east-1"
     table_name: "radml-chat-history"
   ```

---

## Installing Python Dependencies

```bash
pip install -r requirements.txt
```

**If spaCy was installed previously (causes Python 3.14 crash):**
```bash
pip uninstall spacy confection -y
```

---

## Running the System Debugger

After starting the backend, visit:
```
http://localhost:5001/api/debug
```

Or click the **🔬 Debug** button in the top-right of the UI.

This shows a full health check of every API, credential, and package.

---

## Common Errors & Fixes

| Error | Fix |
|-------|-----|
| `No datasets found for query '...'` | Check Kaggle credentials. Use simpler prompts. Or use "Upload CSV". |
| `pydantic.v1.errors.ConfigError: REGEX` | `pip uninstall spacy -y` — spaCy removed in v7 |
| `LLM not initialised` | Set `llm.gemini_api_key` in `config.yaml` |
| `Kaggle auth failed` | Regenerate token at kaggle.com/settings/account |
| `Pipeline failed: Dataset CSV not found` | Data collection stage failed — check Kaggle credentials |
| `NoSQL history unavailable` | Check AWS credentials and create the DynamoDB table configured in `nosql.table_name`. |
