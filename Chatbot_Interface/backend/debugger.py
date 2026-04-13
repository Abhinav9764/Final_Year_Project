"""
backend/debugger.py  (v7 — NEW)
================================
RAD-ML System Debugger — checks all API credentials, connectivity, and
package availability. Called by GET /api/debug in app.py.

Returns a structured health report so users know exactly what is broken
before running a pipeline.
"""
from __future__ import annotations
import importlib
import logging
import os
import socket
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def run_full_debug(config: dict) -> dict:
    """
    Run all diagnostic checks and return a structured report.

    Returns
    -------
    {
      "overall_status": "ok" | "warning" | "error",
      "checks": [
        {
          "name": str,
          "status": "ok" | "warning" | "error",
          "message": str,
          "fix": str | None,   # actionable fix instruction
        },
        ...
      ]
    }
    """
    checks = []

    # ── 1. Python version ─────────────────────────────────────────────────────
    py_ver = sys.version_info
    checks.append({
        "name":    "Python version",
        "status":  "ok",
        "message": f"Python {py_ver.major}.{py_ver.minor}.{py_ver.micro}",
        "fix":     None,
    })

    # ── 2. Required Python packages ───────────────────────────────────────────
    required_packages = {
        "flask":              "pip install flask",
        "flask_jwt_extended": "pip install flask-jwt-extended",
        "flask_cors":         "pip install flask-cors",
        "yaml":               "pip install pyyaml",
        "bcrypt":             "pip install bcrypt",
        "pandas":             "pip install pandas",
        "numpy":              "pip install numpy",
        "sklearn":            "pip install scikit-learn",
        "requests":           "pip install requests",
        "kaggle":             "pip install kaggle",
        "openml":             "pip install openml",
        "google.generativeai":"pip install google-generativeai",
        "boto3":              "pip install boto3",
    }
    optional_packages = {
        "sagemaker":"pip install sagemaker  (optional: for AWS ML training)",
        "diagrams": "pip install diagrams  (optional: for architecture diagrams)",
    }

    for pkg, install_cmd in required_packages.items():
        try:
            importlib.import_module(pkg)
            checks.append({"name": f"Package: {pkg}", "status": "ok",
                           "message": "Installed", "fix": None})
        except ImportError:
            checks.append({"name": f"Package: {pkg}", "status": "error",
                           "message": f"NOT installed",
                           "fix": install_cmd})

    for pkg, install_cmd in optional_packages.items():
        try:
            importlib.import_module(pkg)
            checks.append({"name": f"Package (opt): {pkg}", "status": "ok",
                           "message": "Installed", "fix": None})
        except ImportError:
            checks.append({"name": f"Package (opt): {pkg}", "status": "warning",
                           "message": "Not installed (optional)",
                           "fix": install_cmd})

    # ── 3. Kaggle credentials ─────────────────────────────────────────────────
    kg_user = config.get("kaggle", {}).get("username", "").strip()
    kg_key  = config.get("kaggle", {}).get("key", "").strip()

    if not kg_user:
        checks.append({
            "name": "Kaggle username", "status": "error",
            "message": "Not set in config.yaml",
            "fix": "Set kaggle.username in config.yaml. Get it from: https://www.kaggle.com/settings/account",
        })
    else:
        checks.append({"name": "Kaggle username", "status": "ok",
                       "message": f"Set: {kg_user}", "fix": None})

    if not kg_key or len(kg_key) < 10:
        checks.append({
            "name": "Kaggle API key", "status": "error",
            "message": "Not set or too short in config.yaml",
            "fix": (
                "1. Go to https://www.kaggle.com/settings/account\n"
                "2. Click 'Create New Token' → downloads kaggle.json\n"
                "3. Copy the key value into config.yaml under kaggle.key"
            ),
        })
    else:
        checks.append({"name": "Kaggle API key", "status": "ok",
                       "message": f"Set (ends ...{kg_key[-4:]})", "fix": None})

    # ── 4. Kaggle API auth test ───────────────────────────────────────────────
    if kg_user and kg_key:
        try:
            os.environ["KAGGLE_USERNAME"] = kg_user
            os.environ["KAGGLE_KEY"]      = kg_key
            from kaggle.api.kaggle_api_extended import KaggleApiExtended
            api = KaggleApiExtended()
            api.authenticate()
            checks.append({"name": "Kaggle auth test", "status": "ok",
                           "message": "Authentication succeeded", "fix": None})
        except Exception as exc:
            checks.append({
                "name": "Kaggle auth test", "status": "error",
                "message": f"Auth failed: {exc}",
                "fix": "Verify kaggle.username and kaggle.key in config.yaml are correct",
            })
    else:
        checks.append({"name": "Kaggle auth test", "status": "warning",
                       "message": "Skipped — credentials not set", "fix": None})

    # ── 5. Gemini API key ─────────────────────────────────────────────────────
    gemini_key = config.get("gemini", {}).get("api_key", "").strip()
    if not gemini_key or gemini_key.startswith("YOUR_") or len(gemini_key) < 10:
        checks.append({
            "name": "Gemini API key", "status": "error",
            "message": "Not set or placeholder in config.yaml",
            "fix": (
                "1. Go to https://aistudio.google.com/apikey\n"
                "2. Click 'Create API key'\n"
                "3. Set gemini.api_key in config.yaml"
            ),
        })
    else:
        checks.append({"name": "Gemini API key", "status": "ok",
                       "message": f"Set (ends ...{gemini_key[-4:]})", "fix": None})

    # ── 6. Gemini API connectivity ────────────────────────────────────────────
    if gemini_key and not gemini_key.startswith("YOUR_") and len(gemini_key) >= 10:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-1.5-flash")
            resp  = model.generate_content("Say OK", generation_config={"max_output_tokens": 5})
            checks.append({"name": "Gemini API test", "status": "ok",
                           "message": f"Connected: response='{resp.text.strip()}'", "fix": None})
        except Exception as exc:
            checks.append({
                "name": "Gemini API test", "status": "error",
                "message": f"API call failed: {exc}",
                "fix": "Check gemini.api_key in config.yaml. Ensure the key is valid and enabled.",
            })
    else:
        checks.append({"name": "Gemini API test", "status": "warning",
                       "message": "Skipped — key not set", "fix": None})

    # ── 7. OpenML connectivity ────────────────────────────────────────────────
    oml_key     = config.get("openml", {}).get("api_key", "")
    oml_enabled = config.get("openml", {}).get("enabled", True)
    if not oml_enabled:
        checks.append({"name": "OpenML", "status": "warning",
                       "message": "Disabled in config.yaml", "fix": "Set openml.enabled: true"})
    else:
        try:
            import openml
            if oml_key:
                openml.config.apikey = oml_key
            ds = openml.datasets.list_datasets(output_format="dataframe", size=1)
            checks.append({"name": "OpenML connectivity", "status": "ok",
                           "message": "Reachable and returned results", "fix": None})
        except ImportError:
            checks.append({"name": "OpenML", "status": "error",
                           "message": "openml package not installed",
                           "fix": "pip install openml"})
        except Exception as exc:
            checks.append({"name": "OpenML connectivity", "status": "warning",
                           "message": f"Connectivity issue: {exc}",
                           "fix": "Check internet connection. OpenML may be temporarily down."})

    # ── 8. UCI connectivity ───────────────────────────────────────────────────
    uci_enabled = config.get("uci", {}).get("enabled", True)
    if not uci_enabled:
        checks.append({"name": "UCI", "status": "warning",
                       "message": "Disabled in config.yaml", "fix": "Set uci.enabled: true"})
    else:
        try:
            import requests
            r = requests.get("https://archive.ics.uci.edu/api/datasets",
                             params={"search": "iris", "take": 1}, timeout=10)
            r.raise_for_status()
            count = len(r.json().get("result", {}).get("results", []))
            checks.append({"name": "UCI connectivity", "status": "ok",
                           "message": f"Reachable ({count} results for test query)", "fix": None})
        except ImportError:
            checks.append({"name": "UCI connectivity", "status": "error",
                           "message": "requests not installed", "fix": "pip install requests"})
        except Exception as exc:
            checks.append({"name": "UCI connectivity", "status": "warning",
                           "message": f"Connectivity issue: {exc}",
                           "fix": "Check internet connection. UCI may be temporarily down."})

    # ── 9. AWS credentials (optional) ─────────────────────────────────────────
    aws_key    = config.get("aws", {}).get("access_key_id", "").strip()
    aws_secret = config.get("aws", {}).get("secret_access_key", "").strip()
    aws_region = config.get("aws", {}).get("region", "us-east-1")
    aws_bucket = config.get("aws", {}).get("s3_bucket", "")

    if not aws_key or not aws_secret:
        checks.append({
            "name": "AWS credentials", "status": "warning",
            "message": "Not set — SageMaker training will run in MOCK mode",
            "fix": (
                "Set aws.access_key_id and aws.secret_access_key in config.yaml.\n"
                "Get credentials: https://console.aws.amazon.com/iam → Users → Security credentials"
            ),
        })
    else:
        checks.append({"name": "AWS credentials", "status": "ok",
                       "message": f"Set (key ends ...{aws_key[-4:]})", "fix": None})
        # Test S3 connectivity
        try:
            import boto3
            s3 = boto3.client("s3", region_name=aws_region,
                              aws_access_key_id=aws_key,
                              aws_secret_access_key=aws_secret)
            s3.head_bucket(Bucket=aws_bucket)
            checks.append({"name": "AWS S3 bucket", "status": "ok",
                           "message": f"Bucket '{aws_bucket}' accessible", "fix": None})
        except ImportError:
            checks.append({"name": "AWS S3 bucket", "status": "warning",
                           "message": "boto3 not installed", "fix": "pip install boto3"})
        except Exception as exc:
            checks.append({
                "name": "AWS S3 bucket", "status": "warning",
                "message": f"S3 check failed: {exc}",
                "fix": (
                    f"Ensure bucket '{aws_bucket}' exists in region '{aws_region}' "
                    "and your IAM user has s3:PutObject permission"
                ),
            })

    # ── 10. NoSQL history store (DynamoDB) ─────────────────────────────────────
    nosql_cfg = config.get("nosql", {})
    nosql_provider = str(nosql_cfg.get("provider", "dynamodb")).lower()
    nosql_region = nosql_cfg.get("region") or aws_region
    nosql_table = nosql_cfg.get("table_name", "radml-chat-history")
    nosql_endpoint = nosql_cfg.get("endpoint_url", "").strip()
    if nosql_provider != "dynamodb":
        checks.append({"name": "NoSQL history", "status": "warning",
                       "message": f"Unsupported provider '{nosql_provider}'",
                       "fix": "Use nosql.provider: dynamodb in config.yaml"})
    elif not aws_key or not aws_secret:
        checks.append({"name": "NoSQL history", "status": "warning",
                       "message": "AWS credentials not set - history will fall back to memory",
                       "fix": "Set aws.access_key_id and aws.secret_access_key for DynamoDB persistence"})
    else:
        try:
            import boto3
            kwargs = {
                "region_name": nosql_region,
                "aws_access_key_id": aws_key,
                "aws_secret_access_key": aws_secret,
            }
            if nosql_endpoint:
                kwargs["endpoint_url"] = nosql_endpoint
            dynamodb = boto3.resource("dynamodb", **kwargs)
            table = dynamodb.Table(nosql_table)
            table.load()
            checks.append({"name": "NoSQL history", "status": "ok",
                           "message": f"DynamoDB table '{nosql_table}' reachable", "fix": None})
        except Exception as exc:
            checks.append({"name": "NoSQL history", "status": "warning",
                           "message": f"DynamoDB not reachable ({exc}) - using in-memory history",
                           "fix": f"Create the DynamoDB table '{nosql_table}' or update nosql settings in config.yaml"})

    # ── 11. Config file found ─────────────────────────────────────────────────
    cfg_path = PROJECT_ROOT / "config.yaml" if "PROJECT_ROOT" in dir() else Path("config.yaml")
    for candidate in [Path("config.yaml"), Path(__file__).parent.parent.parent / "config.yaml"]:
        if candidate.exists():
            checks.append({"name": "config.yaml", "status": "ok",
                           "message": f"Found at {candidate.resolve()}", "fix": None})
            break
    else:
        checks.append({"name": "config.yaml", "status": "error",
                       "message": "config.yaml not found",
                       "fix": "Ensure config.yaml is in the project root (RAD-ML/)"})

    # ── Compute overall status ────────────────────────────────────────────────
    statuses = [c["status"] for c in checks]
    if "error" in statuses:
        overall = "error"
    elif "warning" in statuses:
        overall = "warning"
    else:
        overall = "ok"

    return {"overall_status": overall, "checks": checks}
