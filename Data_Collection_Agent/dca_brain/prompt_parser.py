"""
Data_Collection_Agent/brain/prompt_parser.py  (v9 — Enhanced Global Parser)
============================================================================
Enhanced, globally-shared prompt understanding module for all RAD-ML agents.

8 Enhancement Pillars:
  1. Prompt Normalization    — clean, spell-fix, clause-split, language detection
  2. Intent Detection        — 9-class weighted intent engine
  3. Structured JSON Schema  — task/domain/inputs/output/constraints/missing
  4. Constraint Extraction   — language, format, accuracy, dataset, region
  5. Missing Info Detection  — auto-detect gaps + generate clarifying questions
  6. Task Decomposition      — ordered subtask breakdown
  7. Domain Grounding        — RAG-style domain knowledge blocks
  8. Slot Filling            — force-fill fixed schema, all slots always populated

Backward Compatibility:
  All original keys (raw, intent, task_type, domain, keywords, fallback_refs,
  input_params, target_param, _scores) are preserved at the top level.

Usage:
  from dca_brain.prompt_parser import PromptParser          # within Data_Collection_Agent
  from shared.prompt_parser import PromptParser          # from project root (any agent)

  spec = PromptParser().parse("Predict house rent in India based on location")
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# PILLAR 1 — Normalization Helpers
# ══════════════════════════════════════════════════════════════════════════════

# Domain-specific spelling corrections (common typos in ML prompts)
_SPELL_MAP: dict[str, str] = {
    "preict": "predict", "preicts": "predicts", "preicted": "predicted",
    "clasify": "classify", "clasification": "classification",
    "clasifier": "classifier", "clasifiers": "classifiers",
    "regresion": "regression", "regressoin": "regression",
    "cluter": "cluster", "clustring": "clustering",
    "sentimant": "sentiment", "sentimnt": "sentiment",
    "recomend": "recommend", "recomendation": "recommendation",
    "forcast": "forecast", "forcasting": "forecasting",
    "analyis": "analysis", "analysys": "analysis",
    "accurcy": "accuracy", "acuracy": "accuracy",
    "traning": "training", "traing": "training",
    "builld": "build", "buid": "build",
    "genrate": "generate", "genearate": "generate",
    "algorythm": "algorithm", "algoritm": "algorithm",
    "databse": "database", "datset": "dataset",
    "smaple": "sample", "sampel": "sample",
}

# Clause boundary delimiters
_CLAUSE_DELIMITERS = re.compile(
    r"(?<=[.!?])\s+|\s+(?:and then|then|also|additionally|furthermore|"
    r"moreover|however|but also|as well as)\s+",
    re.IGNORECASE,
)


def _fix_spelling(text: str) -> str:
    """Apply domain-specific spell corrections word by word."""
    words = text.split()
    return " ".join(_SPELL_MAP.get(w.lower(), w) for w in words)


def _detect_language(text: str) -> str:
    """Lightweight language detection via ASCII ratio heuristic."""
    if not text:
        return "en"
    ascii_count = sum(1 for c in text if ord(c) < 128)
    ratio = ascii_count / len(text)
    return "en" if ratio > 0.85 else "non-en"


def _split_into_clauses(text: str) -> list[str]:
    """Split a long prompt into smaller semantic clauses."""
    # First split on explicit delimiters
    parts = _CLAUSE_DELIMITERS.split(text)
    # Also split on commas that separate independent clauses (heuristic: comma + verb)
    clauses: list[str] = []
    for part in parts:
        stripped = part.strip()
        if stripped:
            clauses.append(stripped)
    return clauses if clauses else [text.strip()]


def _normalize_prompt(raw: str) -> str:
    """Clean and standardize the raw prompt."""
    text = raw.strip()
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    # Apply spell correction
    text = _fix_spelling(text)
    return text


# ══════════════════════════════════════════════════════════════════════════════
# PILLAR 2 — Intent Detection (9 classes)
# ══════════════════════════════════════════════════════════════════════════════

_INTENT_SIGNALS: dict[str, set[str]] = {
    "ml_model": {
        "predict", "forecast", "estimate", "classify", "cluster", "detect",
        "regression", "classification", "clustering", "train", "model",
        "machine learning", "deep learning", "neural", "xgboost", "lightgbm",
        "random forest", "svm", "accuracy", "precision", "recall", "rmse",
        "recommend", "recommendation",
    },
    "generate_code": {
        "write", "generate", "create", "build", "code", "script", "program",
        "function", "api", "endpoint", "flask", "fastapi", "streamlit",
        "implement", "develop", "make a", "write a", "build a",
    },
    "analyze_data": {
        "analyze", "analyse", "explore", "eda", "visualize", "visualise",
        "plot", "chart", "graph", "distribution", "correlation", "statistics",
        "summary", "describe", "insight", "pattern", "trend",
    },
    "ask_explanation": {
        "explain", "what is", "what are", "how does", "why does", "describe",
        "tell me about", "definition", "meaning", "difference between",
        "how do", "can you explain", "elaborate",
    },
    "create_plan": {
        "plan", "design", "architect", "roadmap", "strategy", "approach",
        "outline", "steps to", "how would you", "best way to", "propose",
    },
    "search_information": {
        "find", "search", "look up", "locate", "where can", "dataset for",
        "data for", "information about", "fetch", "retrieve", "get data",
    },
    "debug_error": {
        "error", "bug", "fix", "debug", "traceback", "exception", "issue",
        "problem with", "not working", "fails", "broken", "crash",
        "typeerror", "valueerror", "keyerror", "indexerror", "attributeerror",
    },
    "summarize_content": {
        "summarize", "summarise", "summary", "tl;dr", "brief", "overview",
        "key points", "highlight", "condense", "shorten", "recap",
    },
    "automate_workflow": {
        "automate", "automation", "schedule", "pipeline", "workflow",
        "trigger", "batch", "cron", "recurring", "etl", "orchestrate",
    },
}

# These override others when ML signals are dominant
_ML_TASK_SIGNALS: dict[str, set[str]] = {
    "regression": {
        "predict", "price", "cost", "salary", "revenue", "forecast",
        "estimate", "value", "rent", "score", "rate", "amount", "sales",
        "demand", "profit", "temperature", "weight", "height", "income",
        "expense", "quantity", "how much", "how many", "regression",
    },
    "classification": {
        "classify", "classification", "detect", "detection", "spam", "fraud",
        "cancer", "disease", "sentiment", "category", "churn", "diagnosis",
        "binary", "multiclass", "label", "whether", "will it", "is it",
        "approve", "reject", "positive", "negative",
    },
    "clustering": {
        "cluster", "segment", "group", "similar", "similarity", "recommend",
        "recommendation", "suggest", "collaborative", "filter", "nearest",
        "unsupervised", "k-means", "topic", "community",
    },
    "chatbot": {
        "chatbot", "chat", "qa", "faq", "assistant", "knowledge base",
        "retrieval", "rag", "summarize", "question answer", "conversational",
    },
}


def _detect_intent(low: str) -> tuple[str, str, dict[str, int]]:
    """
    Returns (intent, task_type, intent_scores).
    intent    : one of 9 classes
    task_type : regression | classification | clustering | chatbot | general
    """
    # Score all intents
    scores: dict[str, int] = {}
    for intent_name, signals in _INTENT_SIGNALS.items():
        scores[intent_name] = sum(1 for sig in signals if sig in low)

    # Score ML sub-tasks
    ml_scores: dict[str, int] = {}
    for task_name, signals in _ML_TASK_SIGNALS.items():
        ml_scores[task_name] = sum(1 for sig in signals if sig in low)

    best_intent = max(scores, key=lambda k: scores[k])
    best_ml     = max(ml_scores, key=lambda k: ml_scores[k])

    # If ML signals dominate, use ml_model intent
    if scores["ml_model"] >= max(scores[k] for k in scores if k != "ml_model") or \
       scores["ml_model"] > 0:
        if scores["ml_model"] > 0:
            intent    = "ml_model"
            task_type = best_ml
        else:
            intent    = best_intent
            task_type = "general"
    else:
        intent    = best_intent
        task_type = "general"

    # Edge: all zeros → default
    if all(v == 0 for v in scores.values()):
        intent    = "ml_model"
        task_type = "regression"

    return intent, task_type, scores


# ══════════════════════════════════════════════════════════════════════════════
# PILLAR 4 — Constraint Extraction
# ══════════════════════════════════════════════════════════════════════════════

_LANG_PATTERNS = {
    "Python":     [r"\bpython\b"],
    "JavaScript": [r"\bjavascript\b", r"\bjs\b", r"\bnode(?:\.js)?\b"],
    "R":          [r"\blanguage r\b", r"\busing r\b", r"\bin r\b"],
    "Java":       [r"\bjava\b(?!script)"],
    "SQL":        [r"\bsql\b"],
}

_FORMAT_PATTERNS = {
    "Streamlit app":   [r"\bstreamlit\b"],
    "Flask API":       [r"\bflask\b"],
    "FastAPI":         [r"\bfastapi\b"],
    "REST API":        [r"\brest api\b", r"\bapi endpoint\b"],
    "CSV":             [r"\bcsv\b", r"\bspreadsheet\b"],
    "Dashboard":       [r"\bdashboard\b"],
    "Jupyter Notebook":[r"\bnotebook\b", r"\bjupyter\b"],
    "CLI Script":      [r"\bcli\b", r"\bcommand.?line\b", r"\bscript\b"],
}

_ACCURACY_PATTERNS = [
    r"(\d{2,3})\s*%\s*(?:accuracy|precision|recall|f1)",
    r"accuracy\s*(?:of|above|over|at least|>=?)\s*(\d{2,3})\s*%",
    r"(?:low|minimum|high)\s+(?:rmse|mae|mse|error)",
]

_REGION_TOKENS = {
    "india", "indian", "us", "usa", "united states", "uk", "europe", "global",
    "worldwide", "new york", "california", "china", "brazil", "australia",
}


def _extract_constraints(low: str, tokens: list[str]) -> dict:
    """Extract structured constraints from the prompt."""
    # Language
    lang = "Python"  # sensible default
    for lang_name, patterns in _LANG_PATTERNS.items():
        if any(re.search(p, low) for p in patterns):
            lang = lang_name
            break

    # Output format
    fmt = "not specified"
    for fmt_name, patterns in _FORMAT_PATTERNS.items():
        if any(re.search(p, low) for p in patterns):
            fmt = fmt_name
            break

    # Accuracy expectation
    accuracy = "not specified"
    for pat in _ACCURACY_PATTERNS:
        m = re.search(pat, low)
        if m:
            accuracy = m.group(0).strip()
            break

    # Region
    region = "not specified"
    for tok in _REGION_TOKENS:
        if tok in low:
            region = tok.title()
            break

    # Dataset feature constraints (explicit column name mentions)
    feature_constraints: list[str] = []
    col_pattern = re.compile(
        r"\b(location|area|size|bhk|bedrooms?|bathrooms?|floor|furnish|price|"
        r"income|age|experience|rating|genre|category|city|state|country)\b",
        re.IGNORECASE,
    )
    feature_constraints = list(dict.fromkeys(col_pattern.findall(low)))

    return {
        "language":         lang,
        "output_format":    fmt,
        "accuracy":         accuracy,
        "region":           region,
        "dataset_features": feature_constraints,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PILLAR 5 — Missing Information Detection
# ══════════════════════════════════════════════════════════════════════════════

def _detect_missing_info(
    low: str,
    task_type: str,
    input_params: list[str],
    target_param: str,
    constraints: dict,
) -> tuple[list[str], list[str]]:
    """Detect gaps and generate clarifying questions."""
    missing: list[str] = []
    questions: list[str] = []

    # Target variable clarity
    vague_targets = {"output", "result", "value", "label", "cluster", "response"}
    if target_param in vague_targets:
        missing.append("Target variable is not explicitly stated")
        questions.append(f"What specific value should the model predict or output?")

    # Input features
    if not input_params or (len(input_params) == 1 and input_params[0] in vague_targets):
        missing.append("Input features are not clearly specified")
        questions.append("What input columns or features should the model use?")

    # Data source
    if not any(kw in low for kw in ["upload", "csv", "dataset", "data", "kaggle", "file"]):
        missing.append("Data source not mentioned")
        questions.append("Where should the data come from? (upload CSV, Kaggle, or auto-collect?)")

    # Region/scope for geo tasks
    if any(kw in low for kw in ["location", "city", "state", "country", "region"]):
        if constraints.get("region") == "not specified":
            missing.append("Geographic scope not defined")
            questions.append("Which geographic region or country should the analysis cover?")

    # Time range for temporal tasks
    if any(kw in low for kw in ["forecast", "trend", "time", "year", "month", "daily", "weekly"]):
        if not re.search(r"\b(20\d{2}|last \d+|past \d+|recent)\b", low):
            missing.append("Time range or period not specified")
            questions.append("What time period or date range should be used?")

    # Accuracy expectations for ML
    if task_type in {"regression", "classification"} and constraints.get("accuracy") == "not specified":
        missing.append("No accuracy or performance target given")
        questions.append("What accuracy or metric threshold is expected (e.g., 90% accuracy, low RMSE)?")

    return missing, questions


# ══════════════════════════════════════════════════════════════════════════════
# PILLAR 6 — Task Decomposition
# ══════════════════════════════════════════════════════════════════════════════

_TASK_SUBTASKS: dict[str, list[dict]] = {
    "regression": [
        {"step": 1, "name": "data_collection",    "description": "Search and download relevant tabular datasets"},
        {"step": 2, "name": "data_cleaning",       "description": "Handle nulls, duplicates, and data type issues"},
        {"step": 3, "name": "feature_engineering", "description": "Encode categoricals, scale numerics, create derived features"},
        {"step": 4, "name": "model_training",      "description": "Train regression models (XGBoost / LightGBM / RF)"},
        {"step": 5, "name": "evaluation",          "description": "Evaluate RMSE, MAE, R² on held-out test split"},
        {"step": 6, "name": "deployment",          "description": "Build Streamlit UI and deploy to SageMaker endpoint"},
    ],
    "classification": [
        {"step": 1, "name": "data_collection",    "description": "Search and download labeled classification datasets"},
        {"step": 2, "name": "data_cleaning",       "description": "Handle class imbalance, nulls, and noise"},
        {"step": 3, "name": "feature_engineering", "description": "Encode labels, extract text/image features if needed"},
        {"step": 4, "name": "model_training",      "description": "Train classifier (XGBoost / SVM / Neural Net)"},
        {"step": 5, "name": "evaluation",          "description": "Evaluate Accuracy, F1, Precision, Recall, AUC-ROC"},
        {"step": 6, "name": "deployment",          "description": "Build prediction interface and SageMaker endpoint"},
    ],
    "clustering": [
        {"step": 1, "name": "data_collection",    "description": "Collect unlabeled dataset matching domain"},
        {"step": 2, "name": "data_cleaning",       "description": "Remove nulls, normalize scale"},
        {"step": 3, "name": "feature_engineering", "description": "Dimensionality reduction (PCA / UMAP if needed)"},
        {"step": 4, "name": "model_training",      "description": "Run K-Means / DBSCAN / Hierarchical clustering"},
        {"step": 5, "name": "evaluation",          "description": "Evaluate Silhouette Score, Elbow Method"},
        {"step": 6, "name": "deployment",          "description": "Build cluster visualization and recommendation UI"},
    ],
    "chatbot": [
        {"step": 1, "name": "data_collection",    "description": "Collect Q&A pairs or knowledge base documents"},
        {"step": 2, "name": "preprocessing",       "description": "Chunk documents, clean text"},
        {"step": 3, "name": "embedding",           "description": "Generate embeddings and build vector index"},
        {"step": 4, "name": "rag_pipeline",        "description": "Build retrieval-augmented generation pipeline"},
        {"step": 5, "name": "evaluation",          "description": "Test response quality and retrieval accuracy"},
        {"step": 6, "name": "deployment",          "description": "Deploy chat interface"},
    ],
    "generate_code": [
        {"step": 1, "name": "requirements_analysis", "description": "Extract functional requirements from prompt"},
        {"step": 2, "name": "architecture_design",   "description": "Choose tech stack, file structure, and patterns"},
        {"step": 3, "name": "code_generation",       "description": "Generate source files with full implementation"},
        {"step": 4, "name": "testing",               "description": "Write unit and integration tests"},
        {"step": 5, "name": "documentation",         "description": "Generate README and inline docstrings"},
    ],
    "analyze_data": [
        {"step": 1, "name": "data_loading",      "description": "Load and inspect dataset"},
        {"step": 2, "name": "eda",               "description": "Descriptive statistics, distributions, correlations"},
        {"step": 3, "name": "visualization",     "description": "Plot key charts (histograms, heatmaps, scatter)"},
        {"step": 4, "name": "insight_extraction","description": "Summarize findings and anomalies"},
        {"step": 5, "name": "reporting",         "description": "Compile insights into a structured report"},
    ],
    "general": [
        {"step": 1, "name": "understand_requirements", "description": "Parse and clarify the user request"},
        {"step": 2, "name": "execute_task",            "description": "Perform the requested operation"},
        {"step": 3, "name": "validate_output",         "description": "Verify correctness of output"},
        {"step": 4, "name": "deliver",                 "description": "Present results to user"},
    ],
}


def _decompose_tasks(intent: str, task_type: str) -> list[dict]:
    """Return ordered subtask list for the detected intent/task_type."""
    key = task_type if task_type in _TASK_SUBTASKS else intent
    return _TASK_SUBTASKS.get(key, _TASK_SUBTASKS["general"])


# ══════════════════════════════════════════════════════════════════════════════
# PILLAR 7 — Domain Grounding (RAG-style knowledge blocks)
# ══════════════════════════════════════════════════════════════════════════════

_DOMAIN_KNOWLEDGE: dict[str, dict] = {
    "real estate": {
        "domain": "real estate",
        "recommended_algo": ["XGBoost", "LightGBM", "Random Forest", "Linear Regression"],
        "common_features":  ["location", "area_sqft", "bhk", "bathrooms", "furnishing", "floor", "city"],
        "target_metric":    "RMSE, MAE, R²",
        "warnings": [
            "Location encoding needed — use target encoding or embeddings for high-cardinality",
            "Outlier prices can skew regression — apply log transform on target",
            "Filter listings by region for localized models",
        ],
        "typical_targets":  ["price", "rent", "sale_price"],
    },
    "finance": {
        "domain": "finance",
        "recommended_algo": ["XGBoost", "LightGBM", "LSTM", "ARIMA"],
        "common_features":  ["open", "high", "low", "close", "volume", "ma_7", "rsi"],
        "target_metric":    "RMSE, Sharpe Ratio, MAPE",
        "warnings": [
            "Time-series leakage risk — use TimeSeriesSplit for CV",
            "Normalize price series to returns for stationarity",
        ],
        "typical_targets":  ["price", "return", "close", "revenue"],
    },
    "medical": {
        "domain": "medical",
        "recommended_algo": ["XGBoost", "Random Forest", "Logistic Regression", "SVM"],
        "common_features":  ["age", "bmi", "glucose", "blood_pressure", "insulin", "skin_thickness"],
        "target_metric":    "AUC-ROC, F1-Score, Sensitivity, Specificity",
        "warnings": [
            "Class imbalance is common — use SMOTE or class_weight",
            "Ensure HIPAA/GDPR compliance for real patient data",
            "Interpretability matters — prefer SHAP explanations",
        ],
        "typical_targets":  ["diagnosis", "disease", "label", "outcome"],
    },
    "e-commerce": {
        "domain": "e-commerce",
        "recommended_algo": ["Collaborative Filtering", "Matrix Factorization", "XGBoost"],
        "common_features":  ["user_id", "product_id", "rating", "purchase_count", "category"],
        "target_metric":    "NDCG, MAP, Recall@K",
        "warnings": [
            "Cold-start problem for new users/items — use content-based fallback",
            "Sparse interaction matrix — apply SVD or ALS",
        ],
        "typical_targets":  ["rating", "purchase", "churn", "revenue"],
    },
    "nlp": {
        "domain": "nlp / text",
        "recommended_algo": ["BERT", "DistilBERT", "TF-IDF + Logistic Regression", "LSTM"],
        "common_features":  ["text", "review", "title", "description", "token_count"],
        "target_metric":    "F1-Score, Accuracy, BLEU (for generation)",
        "warnings": [
            "Tokenizer must match model vocabulary",
            "Handle class imbalance in sentiment datasets",
        ],
        "typical_targets":  ["sentiment", "label", "category", "entity"],
    },
    "weather": {
        "domain": "weather / climate",
        "recommended_algo": ["LSTM", "ARIMA", "Prophet", "XGBoost"],
        "common_features":  ["temperature", "humidity", "wind_speed", "pressure", "rainfall"],
        "target_metric":    "RMSE, MAE, MAPE",
        "warnings": [
            "Seasonality must be accounted for — use STL decomposition",
            "Lag features are critical for forecasting",
        ],
        "typical_targets":  ["temperature", "rainfall", "wind_speed"],
    },
    "education": {
        "domain": "education",
        "recommended_algo": ["Random Forest", "XGBoost", "Logistic Regression"],
        "common_features":  ["study_hours", "attendance", "grades", "age", "gender", "failures"],
        "target_metric":    "Accuracy, F1-Score",
        "warnings": [
            "Protect student privacy — anonymize PII",
        ],
        "typical_targets":  ["grade", "pass_fail", "score", "gpa"],
    },
    "general": {
        "domain": "general",
        "recommended_algo": ["XGBoost", "Random Forest", "Linear/Logistic Regression"],
        "common_features":  ["varies by dataset"],
        "target_metric":    "Task-dependent",
        "warnings":         ["Inspect data quality before modeling"],
        "typical_targets":  ["output"],
    },
}

_DOMAIN_MAP_TOKENS: dict[str, str] = {
    # Real estate
    "house": "real estate", "housing": "real estate", "apartment": "real estate",
    "rent": "real estate", "rental": "real estate", "estate": "real estate",
    "bedroom": "real estate", "bhk": "real estate", "property": "real estate",
    "realestate": "real estate",
    # Finance
    "stock": "finance", "finance": "finance", "credit": "finance",
    "fraud": "finance", "loan": "finance", "salary": "finance",
    "income": "finance", "bank": "finance", "investment": "finance",
    "trading": "finance", "forex": "finance",
    # Medical
    "diabetes": "medical", "heart": "medical", "cancer": "medical",
    "medical": "medical", "health": "medical", "patient": "medical",
    "disease": "medical", "clinical": "medical", "hospital": "medical",
    # E-commerce
    "customer": "e-commerce", "churn": "e-commerce", "sales": "e-commerce",
    "ecommerce": "e-commerce", "retail": "e-commerce", "product": "e-commerce",
    "recommendation": "e-commerce", "recommend": "e-commerce",
    # NLP
    "sentiment": "nlp", "review": "nlp", "spam": "nlp",
    "tweet": "nlp", "twitter": "nlp", "text": "nlp", "nlp": "nlp",
    "language": "nlp", "document": "nlp",
    # Weather
    "weather": "weather", "climate": "weather", "temperature": "weather",
    "rainfall": "weather", "forecast": "weather",
    # Education
    "student": "education", "education": "education", "academic": "education",
    "grade": "education", "score": "education",
}


def _ground_domain(tokens: list[str], low: str) -> tuple[str, dict]:
    """Map prompt tokens to a domain and return the knowledge block."""
    domain_votes: dict[str, int] = {}
    for tok in tokens:
        d = _DOMAIN_MAP_TOKENS.get(tok)
        if d:
            domain_votes[d] = domain_votes.get(d, 0) + 1

    if domain_votes:
        best_domain = max(domain_votes, key=lambda k: domain_votes[k])
    else:
        best_domain = "general"

    knowledge = _DOMAIN_KNOWLEDGE.get(best_domain, _DOMAIN_KNOWLEDGE["general"])
    return best_domain, knowledge


# ══════════════════════════════════════════════════════════════════════════════
# PILLAR 3 — Structured JSON Schema Builder
# ══════════════════════════════════════════════════════════════════════════════

def _build_structured_schema(
    prompt: str,
    task_type: str,
    domain: str,
    input_params: list[str],
    target_param: str,
    constraints: dict,
    missing: list[str],
) -> dict:
    """Convert free text into a structured JSON schema."""
    # Derive problem_type label
    problem_type_map = {
        "regression":     "Supervised Learning — Regression",
        "classification": "Supervised Learning — Classification",
        "clustering":     "Unsupervised Learning — Clustering",
        "chatbot":        "Natural Language Processing — RAG/Chatbot",
        "general":        "General Task",
    }
    problem_type = problem_type_map.get(task_type, "General Task")

    # Short task description (first clause or first 12 words)
    first_clause = re.split(r"[,.]", prompt)[0].strip()
    task_desc = " ".join(first_clause.split()[:12])

    return {
        "task":               task_desc,
        "domain":             domain,
        "problem_type":       problem_type,
        "inputs":             input_params,
        "output":             target_param,
        "constraints":        [
            f"{k}: {v}" for k, v in constraints.items()
            if v and v != "not specified" and v != [] and v != "Python"
        ],
        "missing_information": missing,
    }


# ══════════════════════════════════════════════════════════════════════════════
# PILLAR 8 — Slot Filling
# ══════════════════════════════════════════════════════════════════════════════

def _fill_slots(
    task_type: str,
    domain: str,
    target_param: str,
    input_params: list[str],
    constraints: dict,
    intent: str,
    confidence: float,
) -> dict:
    """Force-fill all slots — every slot always has a value."""
    framework_map = {
        "Flask API":    "Flask",
        "FastAPI":      "FastAPI",
        "REST API":     "Flask",
        "Dashboard":    "Streamlit",
        "Streamlit app":"Streamlit",
    }
    output_fmt = constraints.get("output_format", "not specified")
    return {
        "TASK_TYPE":      task_type if task_type != "general" else "regression",
        "DOMAIN":         domain,
        "TARGET_VAR":     target_param,
        "INPUT_VARS":     input_params if input_params else ["auto-detect"],
        "LANGUAGE":       constraints.get("language", "Python"),
        "FRAMEWORK":      framework_map.get(output_fmt, "Streamlit"),
        "DATA_SOURCE":    "auto-collect",
        "REGION":         constraints.get("region", "global"),
        "ACCURACY_GOAL":  constraints.get("accuracy", "not specified"),
        "OUTPUT_FORMAT":  output_fmt if output_fmt != "not specified" else "web application",
        "INTENT":         intent,
        "CONFIDENCE":     round(confidence, 3),
    }


def _compute_confidence(
    intent_scores: dict[str, int],
    input_params: list[str],
    missing: list[str],
    domain: str,
) -> float:
    """Heuristic confidence score 0.0–1.0."""
    score = 0.5
    top_intent_score = max(intent_scores.values()) if intent_scores else 0
    score += min(top_intent_score * 0.05, 0.25)        # up to +0.25 for clear intent
    score += 0.05 if input_params else -0.05            # known inputs
    score -= len(missing) * 0.05                        # penalise gaps
    score += 0.05 if domain != "general" else 0.0       # known domain
    return max(0.0, min(1.0, score))


# ══════════════════════════════════════════════════════════════════════════════
# Legacy helpers (preserved for backward compatibility)
# ══════════════════════════════════════════════════════════════════════════════

_NOISE = {
    "build", "create", "generate", "make", "want", "need", "use", "using",
    "like", "give", "get", "let", "please", "write", "production", "senior",
    "engineer", "code", "goal", "system", "application", "app", "model",
    "based", "given", "input", "output", "data", "dataset", "train", "test",
    "feature", "column", "machine", "learning", "deep", "neural", "network",
    "artificial", "intelligence", "algorithm", "pipeline", "workflow",
    "project", "develop", "implement", "design", "solution", "platform",
    "tool", "framework", "library", "module", "package", "service",
    "api", "backend", "frontend", "interface", "user", "client", "server",
    "predict", "classification", "regression", "clustering", "detection",
    "analysis", "analytics", "accurate", "simple", "complex", "robust",
    "efficient", "ready", "real", "world",
}

_STOP = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "can", "i", "me", "my", "we", "our", "you", "your",
    "he", "she", "it", "its", "they", "their", "this", "that", "these",
    "those", "what", "which", "who", "how", "when", "where", "why",
    "all", "each", "every", "some", "no", "not", "only", "so", "than",
    "very", "just", "also", "any", "about", "into", "both", "here", "there",
}

_LEGACY_DOMAIN_MAP: dict[str, dict] = {
    "house":      {"kw": ["house prices", "housing"],
                   "fb": ["harlfoxem/house-prices-dataset",
                          "camnugent/california-housing-prices",
                          "yasserh/housing-prices-dataset"]},
    "housing":    {"kw": ["housing", "house prices"],
                   "fb": ["camnugent/california-housing-prices",
                          "harlfoxem/house-prices-dataset"]},
    "bedroom":    {"kw": ["house prices", "real estate"],    "fb": ["harlfoxem/house-prices-dataset"]},
    "bedrooms":   {"kw": ["house prices", "real estate"],    "fb": ["harlfoxem/house-prices-dataset"]},
    "real":       {"kw": ["real estate"], "fb": []},
    "estate":     {"kw": ["real estate", "housing"],         "fb": ["harlfoxem/house-prices-dataset"]},
    "apartment":  {"kw": ["apartment", "housing"],           "fb": ["arnavkulkarni1998/apartments-data"]},
    "rent":       {"kw": ["rent", "rental"],
                   "fb": ["dgomonov/new-york-city-airbnb-open-data",
                          "iamsouravbanerjee/house-rent-prediction-dataset"]},
    "movie":      {"kw": ["movies", "film"],
                   "fb": ["rounakbanik/the-movies-dataset", "tmdb/tmdb-movie-metadata"]},
    "film":       {"kw": ["movies", "film"],                 "fb": ["rounakbanik/the-movies-dataset"]},
    "movies":     {"kw": ["movies"],                         "fb": ["rounakbanik/the-movies-dataset"]},
    "rating":     {"kw": ["ratings"],
                   "fb": ["rounakbanik/the-movies-dataset", "grouplens/movielens-20m-dataset"]},
    "ratings":    {"kw": ["ratings"],                        "fb": ["grouplens/movielens-20m-dataset"]},
    "genre":      {"kw": ["movies", "genre"],                "fb": ["rounakbanik/the-movies-dataset"]},
    "recommendation": {"kw": ["movies", "ratings"],
                   "fb": ["grouplens/movielens-20m-dataset", "rounakbanik/the-movies-dataset"]},
    "recommend":  {"kw": ["movies", "ratings"],              "fb": ["grouplens/movielens-20m-dataset"]},
    "stock":      {"kw": ["stocks", "stock market"],
                   "fb": ["jacksoncrow/nse-and-bse-stocks-with-fundamentals",
                          "borismarjanovic/price-volume-data-for-all-us-stocks-etfs"]},
    "finance":    {"kw": ["finance", "financial"],           "fb": ["mlg-ulb/creditcardfraud"]},
    "credit":     {"kw": ["credit", "loan"],
                   "fb": ["mlg-ulb/creditcardfraud", "uciml/default-of-credit-card-clients-dataset"]},
    "fraud":      {"kw": ["fraud", "credit card"],           "fb": ["mlg-ulb/creditcardfraud"]},
    "loan":       {"kw": ["loan", "credit"],
                   "fb": ["wordsforthewise/lending-club",
                          "uciml/default-of-credit-card-clients-dataset"]},
    "salary":     {"kw": ["salary", "wages"],
                   "fb": ["kaggle/sf-salaries", "ryanxjhan/us-salaries-1990-2016"]},
    "income":     {"kw": ["income", "salary"],               "fb": ["uciml/adult-census-income"]},
    "diabetes":   {"kw": ["diabetes"],
                   "fb": ["uciml/pima-indians-diabetes-database", "mathchi5/diabetes-data-set"]},
    "heart":      {"kw": ["heart disease"],
                   "fb": ["ronitf/heart-disease-uci", "cherngs/heart-disease-cleveland-uci"]},
    "cancer":     {"kw": ["cancer"],
                   "fb": ["uciml/breast-cancer-wisconsin-data", "erdemtaha/cancer-data"]},
    "medical":    {"kw": ["medical", "health"],              "fb": ["uciml/pima-indians-diabetes-database"]},
    "health":     {"kw": ["health", "medical"],              "fb": ["uciml/pima-indians-diabetes-database"]},
    "patient":    {"kw": ["medical", "patient"],             "fb": ["uciml/pima-indians-diabetes-database"]},
    "disease":    {"kw": ["disease", "medical"],             "fb": ["ronitf/heart-disease-uci"]},
    "customer":   {"kw": ["customer", "ecommerce"],
                   "fb": ["olistbr/brazilian-ecommerce", "blastchar/telco-customer-churn"]},
    "churn":      {"kw": ["churn", "customer churn"],
                   "fb": ["blastchar/telco-customer-churn", "becksddf/churn-modelling"]},
    "sales":      {"kw": ["sales"],
                   "fb": ["manjeetsingh/retaildataset", "rohitsahoo/sales-forecasting"]},
    "ecommerce":  {"kw": ["ecommerce", "retail"],            "fb": ["olistbr/brazilian-ecommerce"]},
    "retail":     {"kw": ["retail", "sales"],                "fb": ["manjeetsingh/retaildataset"]},
    "product":    {"kw": ["products", "ecommerce"],          "fb": ["olistbr/brazilian-ecommerce"]},
    "sentiment":  {"kw": ["sentiment", "reviews"],
                   "fb": ["marklvl/sentiment-analysis-dataset", "snap/amazon-fine-food-reviews"]},
    "review":     {"kw": ["reviews", "sentiment"],           "fb": ["snap/amazon-fine-food-reviews"]},
    "reviews":    {"kw": ["reviews"],                        "fb": ["snap/amazon-fine-food-reviews"]},
    "spam":       {"kw": ["spam", "email"],                  "fb": ["uciml/sms-spam-collection-dataset"]},
    "tweet":      {"kw": ["twitter", "tweets"],              "fb": ["kazanova/sentiment140"]},
    "twitter":    {"kw": ["twitter"],                        "fb": ["kazanova/sentiment140"]},
    "weather":    {"kw": ["weather", "climate"],
                   "fb": ["muthuj/weather-dataset", "jsphyg/weather-dataset-rattle-package"]},
    "temperature":{"kw": ["temperature", "weather"],         "fb": ["muthuj/weather-dataset"]},
    "climate":    {"kw": ["climate", "weather"],
                   "fb": ["berkeleyearth/climate-change-earth-surface-temperature-data"]},
    "taxi":       {"kw": ["taxi", "trips"],                  "fb": ["elemento/nyc-yellow-taxi-trip-data"]},
    "flight":     {"kw": ["flights", "airline"],
                   "fb": ["usdot/flight-delays", "open-flights/flight-route-database"]},
    "airline":    {"kw": ["airline", "flights"],             "fb": ["usdot/flight-delays"]},
    "uber":       {"kw": ["uber", "taxi"],
                   "fb": ["fivethirtyeight/uber-pickups-in-new-york-city"]},
    "traffic":    {"kw": ["traffic"],                        "fb": ["fedesoriano/traffic-volume-data-set"]},
    "student":    {"kw": ["student", "education"],
                   "fb": ["uciml/student-performance", "devansodariya/student-performance-data-set"]},
    "education":  {"kw": ["education", "student"],           "fb": ["uciml/student-performance"]},
    "academic":   {"kw": ["academic", "student"],            "fb": ["uciml/student-performance"]},
    "energy":     {"kw": ["energy", "electricity"],
                   "fb": ["uciml/electric-power-consumption",
                          "nicholasjhana/energy-consumption-generation-prices-and-weather"]},
    "electricity":{"kw": ["electricity", "energy"],          "fb": ["uciml/electric-power-consumption"]},
    "power":      {"kw": ["power", "energy"],                "fb": ["uciml/electric-power-consumption"]},
    "titanic":    {"kw": ["titanic"],                        "fb": ["heptapod/titanic"]},
    "iris":       {"kw": ["iris"],                           "fb": ["uciml/iris"]},
    "wine":       {"kw": ["wine"],                           "fb": ["uciml/wine-quality"]},
    "mnist":      {"kw": ["digit", "handwritten"],           "fb": ["hojjatk/mnist-dataset"]},
    "boston":     {"kw": ["boston housing", "house prices"], "fb": ["harlfoxem/house-prices-dataset"]},
    "california": {"kw": ["california housing"],             "fb": ["camnugent/california-housing-prices"]},
    "employee":   {"kw": ["employee", "hr"],
                   "fb": ["pavansubhasht/ibm-hr-analytics-attrition-dataset"]},
    "attrition":  {"kw": ["attrition", "hr"],
                   "fb": ["pavansubhasht/ibm-hr-analytics-attrition-dataset"]},
    "hiring":     {"kw": ["hr", "hiring"],
                   "fb": ["pavansubhasht/ibm-hr-analytics-attrition-dataset"]},
    "plant":      {"kw": ["plant", "species"],               "fb": ["uciml/iris"]},
    "crop":       {"kw": ["crop", "agriculture"],            "fb": ["atharvaingle/crop-recommendation-dataset"]},
    "agriculture":{"kw": ["agriculture", "crop"],            "fb": ["atharvaingle/crop-recommendation-dataset"]},
    "insurance":  {"kw": ["insurance"],                      "fb": ["mirichoi0218/insurance"]},
    "risk":       {"kw": ["risk", "insurance"],              "fb": ["mirichoi0218/insurance"]},
    "india":      {"kw": ["india", "indian"],
                   "fb": ["iamsouravbanerjee/house-rent-prediction-dataset",
                          "nehaprabhavalkar/av-housing-prices-prediction"]},
}

_UNIVERSAL_FALLBACKS = {
    "regression":     ["harlfoxem/house-prices-dataset",
                       "camnugent/california-housing-prices",
                       "mirichoi0218/insurance"],
    "classification": ["uciml/pima-indians-diabetes-database",
                       "blastchar/telco-customer-churn",
                       "mlg-ulb/creditcardfraud"],
    "clustering":     ["grouplens/movielens-20m-dataset",
                       "rounakbanik/the-movies-dataset"],
    "chatbot":        ["harlfoxem/house-prices-dataset"],
}


def _tokenize(text: str) -> list[str]:
    return [t for t in re.sub(r"[^\w\s]", " ", text.lower()).split() if t]


def _is_useful(token: str) -> bool:
    return (
        len(token) >= 3
        and token not in _STOP
        and token not in _NOISE
        and not token.isdigit()
        and bool(re.match(r"^[a-z][a-z0-9_\-]*$", token))
    )


def _extract_io_directives(prompt: str) -> tuple[list[str], str]:
    input_params: list[str] = []
    out_desc = ""
    p_lower = prompt.lower()
    i_idx = p_lower.find("input:")
    if i_idx == -1:
        i_idx = p_lower.find("input :")
    o_idx = p_lower.find("output:")
    if o_idx == -1:
        o_idx = p_lower.find("output :")
    if i_idx != -1:
        start = i_idx + p_lower[i_idx:].find(":") + 1
        end = o_idx if o_idx != -1 and o_idx > start else len(prompt)
        raw_inputs = prompt[start:end].strip()
        raw_inputs = re.sub(r'[\.\n]+$', '', raw_inputs)
        if raw_inputs:
            input_params = [x.strip() for x in raw_inputs.split(',') if x.strip()]
    if o_idx != -1:
        start = o_idx + p_lower[o_idx:].find(":") + 1
        end = len(prompt)
        if i_idx > o_idx:
            end = i_idx
        raw_output = prompt[start:end].strip()
        out_desc = re.sub(r'[\.\n]+$', '', raw_output)
    return input_params, out_desc


def _extract_input_params(low: str, tokens: list[str]) -> list[str]:
    params: list[str] = []
    normalized = (
        low.replace("no.of", "number of")
        .replace("no of", "number of")
        .replace("no.", "number ")
        .replace("&", ",")
        .replace("/", ",")
    )
    clause_patterns = [
        r"\bbased on\b\s+(.+?)(?:\s+to\s+(?:predict|estimate|forecast|classify)\b|$)",
        r"\busing\b\s+(.+?)(?:\s+to\s+(?:predict|estimate|forecast|classify)\b|$)",
        r"\bwith\b\s+(.+?)(?:\s+to\s+(?:predict|estimate|forecast|classify)\b|$)",
        r"\bgiven\b\s+(.+?)(?:\s+to\s+(?:predict|estimate|forecast|classify)\b|$)",
    ]

    def _canonicalize_param(raw_param: str) -> list[str]:
        value = re.sub(r"\b(the|a|an|of|for|input|inputs|provide|enter)\b", " ", raw_param)
        value = re.sub(r"\s+", " ", value).strip(" ,.")
        if not value:
            return []
        parts = [p.strip(" ,.") for p in re.split(r",|\band\b|\bor\b", value) if p.strip(" ,.")]
        if not parts:
            parts = [value]
        canonical: list[str] = []
        for part in parts:
            p = part.strip()
            if not p:
                continue
            replacements = [
                (r"\bnumber of bedrooms?\b", "bedrooms"),
                (r"\bnumber bedrooms?\b",    "bedrooms"),
                (r"\bno of bedrooms?\b",      "bedrooms"),
                (r"\bsize of population\b",   "population"),
                (r"\bsize population\b",      "population"),
                (r"\bpopulation size\b",      "population"),
                (r"\bnumber of bathrooms?\b", "bathrooms"),
                (r"\bnumber bathrooms?\b",    "bathrooms"),
                (r"\bno of bathrooms?\b",     "bathrooms"),
                (r"\bhouse location\b",       "location"),
                (r"\bproperty location\b",    "location"),
            ]
            for pattern, repl in replacements:
                p = re.sub(pattern, repl, p)
            p = re.sub(r"\s+", " ", p).strip()
            if p and p not in _STOP and p not in _NOISE:
                canonical.append(p)
        return canonical

    for pattern in clause_patterns:
        for match in re.finditer(pattern, normalized, flags=re.IGNORECASE):
            params.extend(_canonicalize_param(match.group(1)))

    if not params:
        feature_terms = [
            "location", "bedrooms", "bathrooms", "population", "rooms", "area",
            "size", "income", "salary", "experience", "rating", "genre",
            "bhk", "floor", "furnish", "city", "state", "country",
        ]
        for term in feature_terms:
            if re.search(rf"\b{re.escape(term)}\b", normalized):
                params.append(term)

    if not params:
        for tok in tokens:
            if _is_useful(tok):
                params.append(tok)

    seen: set[str] = set()
    return [p for p in params if not (p in seen or seen.add(p))][:8]  # type: ignore[func-returns-value]


def _extract_target(low: str, task_type: str) -> str:
    for explicit_target in (
        "price", "salary", "income", "cost", "rent", "revenue",
        "rating", "score", "grade", "label", "churn", "diagnosis",
    ):
        if re.search(rf"\b{explicit_target}\b", low):
            return explicit_target
    m = re.search(
        r"\b(predict|estimate|forecast|output|determine|classify)\s+([a-z0-9_ ]+)", low
    )
    if m:
        phrase = [tok for tok in m.group(2).strip().split() if tok not in _STOP and tok not in _NOISE]
        for cand in reversed(phrase):
            if cand not in _NOISE and cand not in _STOP:
                return cand
    return {
        "regression":     "price",
        "classification": "label",
        "clustering":     "cluster",
        "chatbot":        "response",
    }.get(task_type, "output")


# ══════════════════════════════════════════════════════════════════════════════
# MASTER PARSE FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def _build_enhanced_spec(prompt: str) -> dict:
    """Full 8-pillar analysis. Returns the enriched spec dict."""

    # ── Pillar 1: Normalize ────────────────────────────────────────────────
    normalized = _normalize_prompt(prompt)
    low         = normalized.lower()
    tokens      = _tokenize(low)
    language    = _detect_language(prompt)
    clauses     = _split_into_clauses(normalized)

    # ── Pillar 2: Intent Detection ─────────────────────────────────────────
    intent, task_type, intent_scores = _detect_intent(low)

    # ── Legacy keyword + fallback extraction (backward compat) ────────────
    search_keywords: list[str] = []
    fallback_refs:   list[str] = []
    domain_tokens:   list[str] = []
    seen_kw: set[str] = set()

    for tok in tokens:
        if tok in _LEGACY_DOMAIN_MAP:
            domain_tokens.append(tok)
            entry = _LEGACY_DOMAIN_MAP[tok]
            for kw in entry["kw"]:
                if kw not in seen_kw:
                    seen_kw.add(kw)
                    search_keywords.append(kw)
            for ref in entry["fb"]:
                if ref not in fallback_refs:
                    fallback_refs.append(ref)

    if not search_keywords:
        for tok in tokens:
            if _is_useful(tok) and tok not in seen_kw:
                seen_kw.add(tok)
                search_keywords.append(tok)

    if not fallback_refs:
        fallback_refs = _UNIVERSAL_FALLBACKS.get(task_type, [])

    # ── Pillar 4: Constraint Extraction ───────────────────────────────────
    constraints = _extract_constraints(low, tokens)

    # ── Legacy IO extraction (backward compat) ────────────────────────────
    raw_input_params           = _extract_input_params(low, tokens)
    target_param               = _extract_target(low, task_type)
    explicit_inputs, explicit_output = _extract_io_directives(prompt)
    input_params = explicit_inputs if explicit_inputs else raw_input_params

    # ── Pillar 7: Domain Grounding ─────────────────────────────────────────
    grounded_domain, domain_knowledge = _ground_domain(tokens, low)
    # Build legacy domain string
    legacy_domain = " ".join(domain_tokens[:2]) if domain_tokens else (
        search_keywords[0] if search_keywords else grounded_domain
    )

    # ── Pillar 5: Missing Info ─────────────────────────────────────────────
    missing, clarifying_questions = _detect_missing_info(
        low, task_type, input_params, target_param, constraints
    )

    # ── Pillar 3: Structured Schema ────────────────────────────────────────
    structured_schema = _build_structured_schema(
        normalized, task_type, grounded_domain,
        input_params, target_param, constraints, missing,
    )

    # ── Pillar 6: Task Decomposition ──────────────────────────────────────
    subtasks = _decompose_tasks(intent, task_type)

    # ── Confidence ────────────────────────────────────────────────────────
    confidence = _compute_confidence(intent_scores, input_params, missing, grounded_domain)

    # ── Pillar 8: Slot Filling ────────────────────────────────────────────
    slots = _fill_slots(
        task_type, grounded_domain, target_param, input_params,
        constraints, intent, confidence,
    )

    # ── Final dedup ───────────────────────────────────────────────────────
    search_keywords = list(dict.fromkeys(search_keywords))[:6]
    fallback_refs   = list(dict.fromkeys(fallback_refs))[:5]

    # ══════════════════════════════════════════════════════════════════════
    # Assemble final spec — backward-compatible keys first, new keys after
    # ══════════════════════════════════════════════════════════════════════
    spec: dict[str, Any] = {
        # ── ORIGINAL KEYS (preserved for backward compatibility) ──────────
        "raw":            prompt,
        "intent":         intent,
        "task_type":      task_type,
        "domain":         legacy_domain,
        "keywords":       search_keywords,
        "fallback_refs":  fallback_refs,
        "input_params":   input_params,
        "target_param":   target_param,
        "_scores": {
            "regression":     intent_scores.get("ml_model", 0),
            "classification": 0,
            "clustering":     0,
            "chatbot":        intent_scores.get("automate_workflow", 0),
        },

        # ── PILLAR 1: Normalization ───────────────────────────────────────
        "normalized_prompt": normalized,
        "detected_language": language,
        "clauses":           clauses,

        # ── PILLAR 2: Intent Scores ───────────────────────────────────────
        "intent_scores": intent_scores,

        # ── PILLAR 3: Structured Schema ───────────────────────────────────
        "structured_schema": structured_schema,

        # ── PILLAR 4: Constraints ─────────────────────────────────────────
        "constraints": constraints,

        # ── PILLAR 5: Missing Info ────────────────────────────────────────
        "missing_information":  missing,
        "clarifying_questions": clarifying_questions,

        # ── PILLAR 6: Task Decomposition ──────────────────────────────────
        "subtasks": subtasks,

        # ── PILLAR 7: Domain Grounding ────────────────────────────────────
        "domain_knowledge": domain_knowledge,

        # ── PILLAR 8: Slots ───────────────────────────────────────────────
        "slots": slots,

        # ── Meta ──────────────────────────────────────────────────────────
        "confidence": confidence,
    }

    if explicit_output:
        spec["output_description"] = explicit_output

    return spec


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

class PromptParser:
    """
    Enhanced, globally-shared prompt understanding engine for RAD-ML.

    Zero external dependencies. Pure Python 3.9+.
    Backward-compatible — all original keys preserved in parse() return dict.

    Import from any agent:
        from brain.prompt_parser import PromptParser        # Data Collection Agent
        from shared.prompt_parser import PromptParser       # any agent via project root

    Example:
        spec = PromptParser().parse("Predict house rent in India based on location")
        print(spec['intent'])           # ml_model
        print(spec['slots'])            # all slots filled
        print(spec['structured_schema'])# full JSON schema
        print(spec['subtasks'])         # ordered subtask list
        print(spec['missing_information'])  # detected gaps
    """

    def parse(self, prompt: str) -> dict:
        """
        Parse a natural language prompt into a fully enriched spec dict.

        Parameters
        ----------
        prompt : str
            Raw user prompt in any natural language.

        Returns
        -------
        dict
            EnhancedSpec with 16+ keys covering all 8 analysis pillars.
            All original v8 keys are present for backward compatibility.
        """
        result = _build_enhanced_spec(prompt)
        logger.info(
            "Parsed prompt | intent=%-20s task=%-15s domain=%-15s "
            "keywords=%s | fallback_refs=%d inputs=%s target=%s "
            "confidence=%.2f missing=%d",
            result["intent"],
            result["task_type"],
            result["domain"],
            result["keywords"],
            len(result["fallback_refs"]),
            result["input_params"],
            result["target_param"],
            result["confidence"],
            len(result["missing_information"]),
        )
        return result
