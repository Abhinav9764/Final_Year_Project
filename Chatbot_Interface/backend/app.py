"""
Chatbot_Interface/backend/app.py
=================================
Flask REST API — Auth + Pipeline + Chat History

Auth endpoints
--------------
POST /api/auth/register     { username, password, email? }
POST /api/auth/login        { username, password }
POST /api/auth/google       { id_token }               (optional)
GET  /api/auth/me           → current user (JWT required)
POST /api/auth/logout

Pipeline endpoints (JWT required)
----------------------------------
POST /api/pipeline/run          { prompt }  → { job_id }
GET  /api/pipeline/status/<id>
GET  /api/pipeline/stream/<id>  SSE

History endpoints (JWT required)
----------------------------------
GET    /api/history             → list user's jobs
GET    /api/history/<job_id>    → full job detail
DELETE /api/history/<job_id>    → delete one job
DELETE /api/history             → delete all user history

Misc
----
GET /api/health
"""
from __future__ import annotations
import json
import logging
import sys
import time
from pathlib import Path

import os
from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity,
    set_access_cookies, unset_jwt_cookies,
)
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv

# ── Path setup ─────────────────────────────────────────────────────────────────
load_dotenv(override=True)
_HERE         = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent
for _p in [str(_HERE), str(_PROJECT_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ── Config ─────────────────────────────────────────────────────────────────────
def _load_config() -> dict:
    try:
        import yaml
    except ImportError:
        return {}
    for candidate in (_PROJECT_ROOT / "config.yaml", _HERE / "config.yaml"):
        if candidate.exists():
            with open(candidate, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
                auth_cfg = config.setdefault("auth", {})
                aws_cfg = config.setdefault("aws", {})
                gemini_cfg = config.setdefault("gemini", {})
                openai_cfg = config.setdefault("openai", {})
                deepseek_cfg = config.setdefault("deepseek", {})
                kaggle_cfg = config.setdefault("kaggle", {})
                openml_cfg = config.setdefault("openml", {})
                nosql_cfg = config.setdefault("nosql", {})

                auth_cfg["jwt_secret_key"] = os.getenv("JWT_SECRET_KEY", auth_cfg.get("jwt_secret_key", ""))
                auth_cfg["google_client_id"] = os.getenv("GOOGLE_CLIENT_ID", auth_cfg.get("google_client_id", ""))
                auth_cfg["google_client_secret"] = os.getenv("GOOGLE_CLIENT_SECRET", auth_cfg.get("google_client_secret", ""))

                aws_cfg["access_key_id"] = os.getenv("AWS_ACCESS_KEY_ID", aws_cfg.get("access_key_id", ""))
                aws_cfg["secret_access_key"] = os.getenv("AWS_SECRET_ACCESS_KEY", aws_cfg.get("secret_access_key", ""))
                aws_cfg["region"] = os.getenv("AWS_REGION", aws_cfg.get("region", "us-east-1"))
                aws_cfg["s3_bucket"] = os.getenv("AWS_S3_BUCKET", aws_cfg.get("s3_bucket", ""))
                aws_cfg["s3_prefix"] = os.getenv("AWS_S3_PREFIX", aws_cfg.get("s3_prefix", "collected_data"))
                aws_cfg["sagemaker_role"] = os.getenv("AWS_SAGEMAKER_ROLE", aws_cfg.get("sagemaker_role", ""))

                gemini_cfg["api_key"] = os.getenv("GEMINI_API_KEY", gemini_cfg.get("api_key", ""))
                # Forward OpenAI and DeepSeek keys from environment (overrides config.yaml)
                if os.getenv("OPENAI_API_KEY"):
                    openai_cfg["api_key"] = os.getenv("OPENAI_API_KEY")
                if os.getenv("DEEPSEEK_API_KEY"):
                    deepseek_cfg["api_key"] = os.getenv("DEEPSEEK_API_KEY")

                kaggle_cfg["username"] = os.getenv("KAGGLE_USERNAME", kaggle_cfg.get("username", ""))
                kaggle_cfg["key"] = os.getenv("KAGGLE_KEY", kaggle_cfg.get("key", ""))
                openml_cfg["api_key"] = os.getenv("OPENML_API_KEY", openml_cfg.get("api_key", ""))

                nosql_cfg["provider"] = os.getenv("NOSQL_PROVIDER", nosql_cfg.get("provider", "dynamodb"))
                nosql_cfg["region"] = os.getenv("NOSQL_REGION", nosql_cfg.get("region", aws_cfg["region"]))
                nosql_cfg["table_name"] = os.getenv("NOSQL_TABLE_NAME", nosql_cfg.get("table_name", "radml-chat-history"))
                nosql_cfg["endpoint_url"] = os.getenv("NOSQL_ENDPOINT_URL", nosql_cfg.get("endpoint_url", ""))
                return config
    return {}


CONFIG = _load_config()

# ── Logging ────────────────────────────────────────────────────────────────────
_log_cfg = CONFIG.get("logging", {})
(_PROJECT_ROOT / "logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=getattr(logging, _log_cfg.get("console_level", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Flask ──────────────────────────────────────────────────────────────────────
app = Flask(__name__)

_auth_cfg = CONFIG.get("auth", {})
app.config["JWT_SECRET_KEY"]             = _auth_cfg.get("jwt_secret_key", "dev-secret-change-me")
app.config["JWT_ACCESS_TOKEN_EXPIRES"]   = False   # handled by expires_delta in create_access_token
app.config["JWT_TOKEN_LOCATION"]         = ["headers", "cookies", "query_string"]
app.config["JWT_COOKIE_SECURE"]          = False   # True in production with HTTPS
app.config["JWT_COOKIE_CSRF_PROTECT"]    = False   # simplify for SPA
app.config["JWT_QUERY_STRING_NAME"]      = "token"

jwt = JWTManager(app)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# ── Database instances ─────────────────────────────────────────────────────────
from auth_db import AuthDB             # noqa: E402
from chat_history_db import ChatHistoryDB  # noqa: E402
from orchestrator import Orchestrator  # noqa: E402

_auth_db    = AuthDB(CONFIG.get("auth", {}).get("sqlite_path", "data/users.db"))
_history_db = ChatHistoryDB(CONFIG)
_orc        = Orchestrator(CONFIG)

from datetime import timedelta
_JWT_EXPIRES = timedelta(hours=int(_auth_cfg.get("jwt_expires_hours", 24)))


# ── JWT error handlers ─────────────────────────────────────────────────────────
@jwt.unauthorized_loader
def unauthorized(_err):
    return jsonify({"error": "Authentication required"}), 401

@jwt.expired_token_loader
def expired(_header, _payload):
    return jsonify({"error": "Token expired, please log in again"}), 401

@jwt.invalid_token_loader
def invalid(_err):
    return jsonify({"error": "Invalid token"}), 422


@app.errorhandler(Exception)
def handle_api_error(exc):
    if not request.path.startswith("/api/"):
        if isinstance(exc, HTTPException):
            return exc
        logger.exception("Unhandled non-API error: %s", exc)
        return jsonify({"error": "Internal server error"}), 500

    if isinstance(exc, HTTPException):
        return jsonify({"ok": False, "error": exc.description}), exc.code

    logger.exception("Unhandled API error on %s: %s", request.path, exc)
    return jsonify({"ok": False, "error": "Internal server error"}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/auth/register", methods=["POST"])
def register():
    data     = request.get_json(force=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    email    = str(data.get("email",    "")).strip()
    try:
        user  = _auth_db.register(username, password, email)
        token = create_access_token(
            identity=str(user["id"]),
            expires_delta=_JWT_EXPIRES,
        )
        resp = jsonify({
            "ok": True,
            "token": token,
            "user": {"id": user["id"], "username": user["username"],
                     "email": user.get("email", "")},
        })
        set_access_cookies(resp, token)
        logger.info("Registered: %s", username)
        return resp, 201
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        logger.exception("Registration failed for %s: %s", username, exc)
        return jsonify({"ok": False, "error": "Registration failed"}), 500


@app.route("/api/auth/login", methods=["POST"])
def login():
    data     = request.get_json(force=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password are required"}), 400
    try:
        user = _auth_db.login(username, password)
        if not user:
            return jsonify({"ok": False, "error": "Invalid username or password"}), 401
        token = create_access_token(
            identity=str(user["id"]),
            expires_delta=_JWT_EXPIRES,
        )
        resp = jsonify({
            "ok": True,
            "token": token,
            "user": {"id": user["id"], "username": user["username"],
                     "email": user.get("email",""),
                     "avatar_url": user.get("avatar_url","")},
        })
        set_access_cookies(resp, token)
        logger.info("Login: %s", username)
        return resp
    except Exception as exc:
        logger.exception("Login failed for %s: %s", username, exc)
        return jsonify({"ok": False, "error": "Login failed"}), 500


@app.route("/api/auth/google", methods=["POST"])
def google_auth():
    """Verify Google ID token and upsert user."""
    data     = request.get_json(force=True) or {}
    id_token = data.get("id_token", "")
    if not id_token:
        return jsonify({"ok": False, "error": "id_token is required"}), 400
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        client_id = CONFIG.get("auth", {}).get("google_client_id", "")
        info = google_id_token.verify_oauth2_token(
            id_token, google_requests.Request(), client_id
        )
        user = _auth_db.upsert_google_user(
            google_id  = info["sub"],
            email      = info.get("email", ""),
            name       = info.get("name", ""),
            avatar_url = info.get("picture", ""),
        )
        token = create_access_token(
            identity=str(user["id"]), expires_delta=_JWT_EXPIRES
        )
        resp = jsonify({"ok": True, "token": token, "user": user})
        set_access_cookies(resp, token)
        return resp
    except Exception as exc:
        logger.warning("Google auth failed: %s", exc)
        return jsonify({"ok": False, "error": "Google sign-in failed"}), 401


@app.route("/api/auth/me")
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user    = _auth_db.get_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": user})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    resp = jsonify({"ok": True})
    unset_jwt_cookies(resp)
    return resp


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE ROUTES  (JWT required)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/pipeline/run", methods=["POST"])
@jwt_required()
def run_pipeline():
    user_id = int(get_jwt_identity())
    data    = request.get_json(force=True) or {}
    prompt  = str(data.get("prompt", "")).strip()
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    job_id = _orc.create_job(prompt)
    # Create history record immediately (status=running)
    _history_db.upsert_job(
        user_id=user_id, job_id=job_id,
        prompt=prompt, status="running", logs=[], result={}, error="",
    )
    _orc.start_pipeline(job_id, user_id=user_id, history_db=_history_db)
    logger.info("User %s started job %s: %.60s", user_id, job_id, prompt)
    return jsonify({"job_id": job_id, "status": "running"})


@app.route("/api/pipeline/status/<job_id>")
@jwt_required()
def pipeline_status(job_id: str):
    user_id = int(get_jwt_identity())
    job     = _orc.get_job(job_id)
    if not job:
        # Try persisted history storage
        doc = _history_db.get_job(user_id, job_id)
        if not doc:
            return jsonify({"error": "job not found"}), 404
        return jsonify(doc)
    return jsonify({
        "job_id":  job.id,
        "status":  job.status,
        "logs":    job.logs,
        "result":  job.result,
        "error":   job.error,
        "prompt":  job.prompt,
    })


import math
def _clean_nans(obj):
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if isinstance(obj, dict):
        return {k: _clean_nans(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_nans(v) for v in obj]
    return obj

@app.route("/api/pipeline/stream/<job_id>")
@jwt_required()
def pipeline_stream(job_id: str):
    """SSE — live log streaming."""
    job = _orc.get_job(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404

    def generate():
        sent = 0
        while True:
            while sent < len(job.logs):
                yield f"data: {json.dumps(_clean_nans(job.logs[sent]))}\n\n"
                sent += 1
            if job.status in ("done", "error"):
                payload = {'type': job.status, 'result': job.result, 'error': job.error}
                yield f"data: {json.dumps(_clean_nans(payload))}\n\n"
                break
            yield 'data: {"type":"heartbeat"}\n\n'
            time.sleep(2)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# HISTORY ROUTES  (JWT required)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/history")
@jwt_required()
def history():
    user_id = int(get_jwt_identity())
    jobs    = _history_db.get_history(user_id, limit=60)
    # Also merge any in-memory running jobs belonging to this user
    for jid, job in _orc._jobs.items():
        if getattr(job, 'user_id', None) == user_id:
            if not any(j.get("job_id") == jid for j in jobs):
                jobs.insert(0, {
                    "job_id": job.id, "prompt": job.prompt,
                    "status": job.status, "created_at": job.created,
                })
    return jsonify({"jobs": jobs})


@app.route("/api/history/<job_id>")
@jwt_required()
def get_history_job(job_id: str):
    user_id = int(get_jwt_identity())
    doc     = _history_db.get_job(user_id, job_id)
    if not doc:
        return jsonify({"error": "not found"}), 404
    return jsonify(doc)


@app.route("/api/history/<job_id>", methods=["DELETE"])
@jwt_required()
def delete_history_job(job_id: str):
    user_id = int(get_jwt_identity())
    deleted = _history_db.delete_job(user_id, job_id)
    _orc.delete_job(job_id)
    return jsonify({"deleted": deleted})


@app.route("/api/history", methods=["DELETE"])
@jwt_required()
def delete_all_history():
    user_id = int(get_jwt_identity())
    count   = _history_db.delete_all(user_id)
    return jsonify({"deleted_count": count})



@app.route("/api/pipeline/stop/<job_id>", methods=["POST"])
@jwt_required()
def stop_pipeline(job_id: str):
    """Cancel a running pipeline job."""
    cancelled = _orc.cancel_job(job_id)
    if not cancelled:
        return jsonify({"error": "Job not found or already finished"}), 404
    # Update history record
    user_id = int(get_jwt_identity())
    try:
        _history_db.upsert_job(user_id=user_id, job_id=job_id,
                               status="error", error="Cancelled by user.")
    except Exception:
        pass
    logger.info("Job %s cancelled by user %s", job_id, user_id)
    return jsonify({"cancelled": True, "job_id": job_id})


@app.route("/api/pipeline/upload", methods=["POST"])
@jwt_required()
def upload_dataset():
    """
    Upload a CSV dataset file.
    Returns {job_id} — the job skips data collection and goes straight to codegen.
    """
    user_id = int(get_jwt_identity())

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400
    if not f.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only CSV files are supported"}), 400

    prompt = request.form.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    # Save uploaded file
    import uuid as _uuid
    upload_dir = _PROJECT_ROOT / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name  = f"{_uuid.uuid4().hex[:8]}_{f.filename.replace(' ','_')}"
    save_path  = upload_dir / safe_name
    f.save(str(save_path))
    logger.info("User %s uploaded dataset: %s (%d bytes)",
                user_id, safe_name, save_path.stat().st_size)

    # Create job with dataset_path set — skips data collection
    job_id = _orc.create_job(prompt)
    job    = _orc.get_job(job_id)
    job.dataset_path = str(save_path)

    _history_db.upsert_job(
        user_id=user_id, job_id=job_id,
        prompt=prompt, status="running",
        logs=[], result={}, error="",
    )
    _orc.start_pipeline(job_id, user_id=user_id, history_db=_history_db)
    logger.info("User %s started upload job %s: %.60s", user_id, job_id, prompt)
    return jsonify({"job_id": job_id, "status": "running",
                    "dataset_file": safe_name})


@app.route("/api/apk/upload", methods=["POST"])
@jwt_required()
def upload_apk():
    """
    Upload an APK file for malware analysis.
    Returns visual fingerprint, risk score, and permission analysis.
    """
    from apk_processor import APKProcessor
    from ensemble_predictor import EnsemblePredictor
    import base64
    from io import BytesIO

    user_id = int(get_jwt_identity())

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400
    if not f.filename.lower().endswith(".apk"):
        return jsonify({"error": "Only APK files are supported"}), 400

    # Save uploaded file
    import uuid as _uuid
    upload_dir = _PROJECT_ROOT / "data" / "uploads" / "apk"
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{_uuid.uuid4().hex[:8]}_{f.filename.replace(' ', '_')}"
    save_path = upload_dir / safe_name
    f.save(str(save_path))

    logger.info("User %s uploaded APK: %s (%d bytes)",
                user_id, safe_name, save_path.stat().st_size)

    try:
        # Process APK
        processor = APKProcessor(fingerprint_size=128)
        result = processor.process_apk(str(save_path))

        # Get ensemble prediction
        model_dir = _PROJECT_ROOT / "models"  # Adjust path as needed
        predictor = EnsemblePredictor(model_dir=str(model_dir) if model_dir.exists() else None)
        predictor.load_models()

        prediction = predictor.predict_ensemble(
            result["fingerprint_array"],
            result["permissions"].get("risk_score", 0)
        )

        # Convert fingerprint image to base64 for frontend
        img_buffer = BytesIO()
        result["fingerprint_image"].save(img_buffer, format='PNG')
        img_buffer.seek(0)
        fingerprint_b64 = base64.b64encode(img_buffer.read()).decode('utf-8')

        response = {
            "ok": True,
            "file_name": safe_name,
            "apk_size": result["apk_size"],
            "dex_size": result["dex_size"],
            "fingerprint": fingerprint_b64,
            "prediction": prediction,
            "permissions": {
                "all": result["permissions"]["all_permissions"],
                "high_risk": result["permissions"]["high_risk"],
                "risk_score": result["permissions"]["risk_score"],
                "categories": result["permissions"]["categories"],
                "analysis_method": result["permissions"]["analysis_method"]
            }
        }

        logger.info("APK analysis complete: risk=%.2f, verdict=%s",
                    prediction["final_risk_score"], prediction["verdict"])

        return jsonify(response)

    except FileNotFoundError as e:
        logger.error("APK processing failed: %s", e)
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.exception("APK analysis failed for user %s: %s", user_id, e)
        return jsonify({"error": "Analysis failed: " + str(e)}), 500


@app.route("/api/explain/<job_id>")
@jwt_required()
def get_explanation(job_id: str):
    """Return the explanation payload for a completed job."""
    user_id = int(get_jwt_identity())
    # Check in-memory running jobs first
    job = _orc.get_job(job_id)
    if job and job.result:
        expl = job.result.get("explanation", {})
        if expl:
            return jsonify(expl)
    # Fall back to persisted history storage
    doc = _history_db.get_job(user_id, job_id)
    if not doc:
        return jsonify({"error": "job not found"}), 404
    expl = doc.get("result", {}).get("explanation", {})
    return jsonify(expl if expl else {"error": "explanation not available"})


# ═══════════════════════════════════════════════════════════════════════════════
# INTENT / SPEC EXTRACTION  — prompt → structured IntentSpec JSON
# ═══════════════════════════════════════════════════════════════════════════════

def _run_extraction(prompt: str) -> dict:
    """
    Shared helper used by both the public and JWT-protected extract-spec routes.
    Returns (intent_spec dict, snippets list).
    """
    import sys
    _code_gen_root = _PROJECT_ROOT / "Code_Generator" / "RAD-ML"
    for _p in [str(_code_gen_root), str(_code_gen_root / "core")]:
        if _p not in sys.path:
            sys.path.insert(0, _p)

    from core.llm_client import LLMClient  # type: ignore
    from generator.prompt_spec_extractor import PromptSpecExtractor  # type: ignore

    llm     = LLMClient(CONFIG)
    extractor = PromptSpecExtractor(llm, CONFIG)
    spec    = extractor.extract(prompt, save=True)
    snippets = extractor.enrich_with_search(spec)
    return spec, snippets


@app.route("/api/extract-spec", methods=["POST"])
def extract_spec_public():
    """
    POST /api/extract-spec
    ----------------------
    Public endpoint (no JWT required) — for quick UI-level intent inspection.

    Body   : { "prompt": "string" }
    Returns: IntentSpec JSON + list of Google Search snippet strings.

    Example response:
    {
      "ok": true,
      "intent_spec": { ... },
      "search_snippets": ["snippet 1", "snippet 2"]
    }
    """
    data   = request.get_json(force=True) or {}
    prompt = str(data.get("prompt", "")).strip()
    if not prompt:
        return jsonify({"ok": False, "error": "prompt is required"}), 400

    try:
        spec, snippets = _run_extraction(prompt)
        logger.info("extract-spec (public): task_type=%s  inputs=%d",
                    spec.get("task_type"), len(spec.get("inputs", [])))
        return jsonify({"ok": True, "intent_spec": spec, "search_snippets": snippets})
    except Exception as exc:
        logger.exception("extract-spec failed for prompt: %.80s — %s", prompt, exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/extract-spec/secure", methods=["POST"])
@jwt_required()
def extract_spec_secure():
    """
    POST /api/extract-spec/secure
    ------------------------------
    JWT-protected version — same as above but records who called it.

    Additionally returns the generated code bundle if  generate_code=true  is
    passed in the request body.

    Body   : { "prompt": "string", "generate_code": false }
    Returns: intent_spec JSON + optional code_bundle.
    """
    user_id = int(get_jwt_identity())
    data    = request.get_json(force=True) or {}
    prompt  = str(data.get("prompt", "")).strip()
    gen_code = bool(data.get("generate_code", False))

    if not prompt:
        return jsonify({"ok": False, "error": "prompt is required"}), 400

    try:
        spec, snippets = _run_extraction(prompt)
        logger.info("extract-spec (user=%s): task_type=%s  inputs=%d  gen_code=%s",
                    user_id, spec.get("task_type"),
                    len(spec.get("inputs", [])), gen_code)

        response_payload: dict = {
            "ok": True,
            "intent_spec": spec,
            "search_snippets": snippets,
        }

        if gen_code:
            import sys
            _code_gen_root = _PROJECT_ROOT / "Code_Generator" / "RAD-ML"
            if str(_code_gen_root) not in sys.path:
                sys.path.insert(0, str(_code_gen_root))
            from generator.search_enriched_codegen import SearchEnrichedCodeGen  # type: ignore

            gen     = SearchEnrichedCodeGen(CONFIG)
            bundle  = gen.generate(spec, prompt, search_snippets=snippets)
            response_payload["code_bundle"] = {
                "python": bundle.get("python", ""),
                "tests":  bundle.get("tests", ""),
            }
            logger.info("extract-spec: code bundle generated (%d chars py)",
                        len(bundle.get("python", "")))

        return jsonify(response_payload)

    except Exception as exc:
        logger.exception("extract-spec/secure failed for user=%s: %.80s — %s",
                         user_id, prompt, exc)
        return jsonify({"ok": False, "error": str(exc)}), 500



# ── Health ─────────────────────────────────────────────────────────────────────
@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "RAD-ML",
        "history_backend": "dynamodb" if getattr(_history_db, "_use_nosql", False) else "memory",
    })




@app.route("/api/debug")
def debug_system():
    """GET /api/debug — Full system diagnostic. No JWT required."""
    try:
        from debugger import run_full_debug
        report = run_full_debug(CONFIG)
        return jsonify(report)
    except Exception as exc:
        logger.exception("Debug endpoint failed: %s", exc)
        return jsonify({
            "overall_status": "error",
            "checks": [{"name": "Debug runner", "status": "error",
                         "message": str(exc), "fix": None}]
        }), 500

# ── Entry point ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _cfg  = CONFIG.get("chatbot", {})
    _host = _cfg.get("host", "0.0.0.0")
    _port = int(_cfg.get("port", 5001))
    logger.info("RAD-ML backend on http://%s:%d", _host, _port)
    app.run(host=_host, port=_port,
            debug=bool(_cfg.get("debug", False)), threaded=True)
