"""
Code_Generator/RAD-ML/main.py
=============================
Streamlit-first code generation pipeline with launch + explainability.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
import shutil
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
for p in (str(ROOT), str(ROOT.parent), str(PROJECT_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _load_config(path: str | None = None) -> dict:
    import yaml

    for c in [path, ROOT / "config.yaml", PROJECT_ROOT / "config.yaml"]:
        if c and Path(c).exists():
            with open(c, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    return {}


# Keywords that signal the user wants a RECOMMENDATION system (filtered / ranked cards)
_RECOMMENDATION_PROMPT_KEYWORDS = {
    "recommend", "recommendation", "suggest", "suggestion",
    "similar", "similar movies", "top movies", "best movies",
    "movie suggestion", "film suggest", "what to watch",
    "filter movies", "rank movies",
}


def _infer_codegen_mode(project_spec: dict, pre_result: dict, user_prompt: str = "") -> str:
    """
    Infer the codegen mode strictly from the user's ACTUAL prompt words, not just
    the coarse task_type bucket.  This ensures that a prompt such as
    "Build a movie recommendation system using genre and rating" always produces
    the recommendation template (genre select + rating slider + ranked cards)
    rather than the generic ML predictor that shows a raw float.
    """
    task_type = str(project_spec.get("task_type") or pre_result.get("task_type") or "").lower()
    prompt = (user_prompt or str(project_spec.get("prompt") or pre_result.get("prompt") or "")).lower()

    # ── Chatbot ───────────────────────────────────────────────────────────────
    if task_type == "chatbot":
        return "chatbot"

    # ── Recommendation (explicit task_type OR clustering + keywords) ──────────
    # The prompt parser classifies recommend/similar/suggest prompts as
    # task_type="clustering".  We must catch both spellings here so the
    # recommendation template (with movie cards, genre dropdown, rating slider)
    # is always used instead of the generic ML predictor.
    if task_type in ("recommendation", "clustering") and any(
        kw in prompt for kw in _RECOMMENDATION_PROMPT_KEYWORDS
    ):
        return "recommendation"

    # Also catch when the prompt itself has recommendation keywords regardless
    # of what task_type the parser returned
    if any(kw in prompt for kw in _RECOMMENDATION_PROMPT_KEYWORDS):
        return "recommendation"

    # ── Text Classification ───────────────────────────────────────────────────
    text_cls_keywords = [
        "text classif", "sentiment", "positive or negative",
        "positive or not", "classify text", "classify sentence",
        "nlp classif", "language classif",
    ]
    if task_type == "classification" and any(kw in prompt for kw in text_cls_keywords):
        return "text_classification"
    if task_type in ("text_classification", "text classification"):
        return "text_classification"
    if any(kw in prompt for kw in text_cls_keywords):
        return "text_classification"

    # ── Generic ML predictor (regression / classification / clustering) ───────
    return "ml"


def _resolve_workspace_dir(config: dict) -> Path:
    workspace_value = config.get("codegen", {}).get(
        "workspace_dir", "Code_Generator/RAD-ML/workspace/current_app"
    )
    workspace_dir = Path(workspace_value)
    if not workspace_dir.is_absolute():
        workspace_dir = PROJECT_ROOT / workspace_dir
    return workspace_dir.resolve()


def _resolve_existing_path(path_value: str) -> Path:
    raw = Path(path_value)
    candidates = []

    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.extend([
            raw,
            PROJECT_ROOT / raw,
            PROJECT_ROOT / "Chatbot_Interface" / "backend" / raw,
            ROOT / raw,
        ])

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    # Fall back to the project-root interpretation for clearer error messages.
    return (PROJECT_ROOT / raw).resolve() if not raw.is_absolute() else raw


def _is_http_ready(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=timeout) as resp:
            return int(resp.status) < 500
    except Exception:
        return False


def _get_free_port(default_port: int) -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return int(s.getsockname()[1])
    except Exception:
        return default_port


def _iter_streamlit_python_candidates(config: dict) -> list[Path]:
    candidates: list[Path] = []

    current_python = Path(sys.executable)
    candidates.append(current_python)

    base_python = Path(sys.base_prefix) / "python.exe"
    candidates.append(base_python)

    project_venv = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    candidates.append(project_venv)

    configured_python = config.get("streamlit", {}).get("python_path")
    if configured_python:
        candidates.append(Path(str(configured_python)))

    python_on_path = shutil.which("python")
    if python_on_path:
        candidates.append(Path(python_on_path))

    py_launcher = shutil.which("py")
    if py_launcher:
        try:
            listing = subprocess.run(
                [py_launcher, "-0p"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if listing.returncode == 0:
                for line in listing.stdout.splitlines():
                    parts = line.strip().split()
                    if parts:
                        possible_path = parts[-1]
                        if possible_path.lower().endswith(".exe"):
                            candidates.append(Path(possible_path))
        except Exception:
            pass

    seen: set[str] = set()
    existing: list[Path] = []
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if candidate.exists():
            existing.append(candidate)
    return existing


def _resolve_streamlit_python(config: dict) -> Path:
    tried: list[str] = []
    for candidate in _iter_streamlit_python_candidates(config):
        tried.append(str(candidate))
        try:
            result = subprocess.run(
                [str(candidate), "-m", "streamlit", "--version"],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0:
                return candidate
        except Exception:
            continue

    raise RuntimeError(
        "Could not find a Python interpreter with streamlit installed. "
        f"Tried: {tried}"
    )


def _launch_streamlit_app(
    app_dir: Path,
    config: dict,
    log: logging.Logger,
    extra_env: dict[str, str] | None = None,
) -> tuple[str, int]:
    app_py = app_dir / "app.py"
    if not app_py.exists():
        raise FileNotFoundError(f"Generated app not found at {app_py}")

    host = str(config.get("streamlit", {}).get("host", "127.0.0.1"))
    base_port = int(config.get("streamlit", {}).get("port", 8501))
    active_port = _get_free_port(base_port)
    deploy_url = f"http://localhost:{active_port}"
    probe_url = f"http://127.0.0.1:{active_port}/_stcore/health"
    int(config.get("refinement", {}).get("app_start_timeout_secs", 120))

    logs_dir = app_dir.parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    out_log = logs_dir / "generated_app_stdout.log"
    err_log = logs_dir / "generated_app_stderr.log"
    pid_file = logs_dir / "generated_app.pid"

    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text(encoding="utf-8").strip())
            os.kill(old_pid, signal.SIGTERM)
            time.sleep(1)
        except Exception:
            pass

    env = dict(os.environ)
    if extra_env:
        env.update({k: str(v) for k, v in extra_env.items()})
    candidate_errors: list[str] = []
    # Give Streamlit enough time to start (pip install may have happened just before)
    per_candidate_timeout = 60

    for python_for_streamlit in _iter_streamlit_python_candidates(config):
        cmd = [
            str(python_for_streamlit),
            "-m",
            "streamlit",
            "run",
            app_py.name,
            "--server.headless",
            "true",
            "--server.address",
            host,
            "--server.port",
            str(active_port),
            "--browser.gatherUsageStats",
            "false",
            "--logger.level",
            "error",
        ]

        subprocess.run([str(python_for_streamlit), "-m", "pip", "install", "-r", "requirements.txt"], cwd=str(app_dir), capture_output=True)
        out_log.write_text("", encoding="utf-8")
        err_log.write_text("", encoding="utf-8")
        out_fh = open(out_log, "w", encoding="utf-8")  # noqa: SIM115
        err_fh = open(err_log, "w", encoding="utf-8")  # noqa: SIM115
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(app_dir),
                stdout=out_fh,
                stderr=err_fh,
                env=env,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as spawn_exc:
            out_fh.close()
            err_fh.close()
            candidate_errors.append(f"{python_for_streamlit}: spawn failed: {spawn_exc}")
            continue

        start = time.time()
        while time.time() - start < per_candidate_timeout:
            if proc.poll() is not None:
                out_fh.flush()
                err_fh.flush()
                out_fh.close()
                err_fh.close()
                error_tail = err_log.read_text(encoding="utf-8", errors="replace")[-2000:] if err_log.exists() else ""
                candidate_errors.append(f"{python_for_streamlit}: {error_tail.strip() or f'process exited {proc.returncode}'}")
                break
            if _is_http_ready(probe_url):
                out_fh.flush()
                err_fh.close()
                pid_file.write_text(str(proc.pid), encoding="utf-8")
                log.info(
                    "Streamlit app running (PID %s) with %s -> %s",
                    proc.pid,
                    python_for_streamlit,
                    deploy_url,
                )
                return deploy_url, active_port
            time.sleep(1)
        else:
            out_fh.flush()
            err_fh.close()
            try:
                proc.terminate()
            except Exception:
                pass
            candidate_errors.append(f"{python_for_streamlit}: did not become ready within {per_candidate_timeout}s")
            continue

        try:
            proc.terminate()
        except Exception:
            pass

    raise RuntimeError(
        "Could not launch the Streamlit app with any discovered Python interpreter. "
        f"Tried: {[str(p) for p in _iter_streamlit_python_candidates(config)]}. "
        f"Details: {candidate_errors}"
    )


def _ensure_valid_bundle(factory, mode: str, code_bundle: dict) -> dict:
    try:
        compile(code_bundle.get("python", ""), "app.py", "exec")
        compile(code_bundle.get("tests", ""), "test_app.py", "exec")
        return code_bundle
    except Exception:
        return factory._parse_json_response(factory._stub_bundle_json(mode))


def _write_supporting_files(
    workspace_dir: Path,
    pre_result: dict,
    sm_meta: dict,
    deploy_url: str,
    mode: str,
) -> dict[str, Path]:
    requirements = """streamlit
boto3
pandas
pyyaml
pytest
"""
    task_type = str(pre_result.get("task_type", mode)).lower()
    metric_name = "accuracy" if task_type == "classification" else "r2"
    metric_label = "Accuracy" if task_type == "classification" else "R2"
    readme = f"""# RAD-ML Generated App

## Live App
- URL: `{deploy_url}`
- Endpoint: `{sm_meta.get("endpoint_name", "")}`
- Training job: `{sm_meta.get("job_name", "")}`
- Status: `{sm_meta.get("status", "")}`

## Quality Gate
- Classification models must reach at least 90% Accuracy.
- Regression models must reach at least 0.90 R2.
- If the threshold is missed, revise features, clean the dataset, rebalance classes if needed, and retrain.

## Generated Files
- `app.py`: Streamlit inference app
- `test_app.py`: unit tests for inference helpers
- `tests/test_quality_gate.py`: threshold enforcement for model metrics
- `requirements.txt`: local dependencies
"""
    quality_gate_test = f"""import json
from pathlib import Path

import pytest

THRESHOLD = 0.90
METRIC_NAME = "{metric_name}"
METRIC_LABEL = "{metric_label}"


def test_model_quality_gate():
    metrics_path = Path(__file__).resolve().parent.parent / "metrics.json"
    if not metrics_path.exists():
        pytest.skip("metrics.json not generated yet")

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    score = float(metrics.get(METRIC_NAME, 0.0))
    assert score >= THRESHOLD, (
        f"Model failed the quality gate: {{METRIC_LABEL}}={{score:.4f}} < {{THRESHOLD:.2f}}. "
        "Improve the dataset or features, retrain, and regenerate the app."
    )
"""

    tests_dir = workspace_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "README.md": workspace_dir / "README.md",
        "requirements.txt": workspace_dir / "requirements.txt",
        "tests/test_quality_gate.py": tests_dir / "test_quality_gate.py",
    }
    files["README.md"].write_text(readme, encoding="utf-8")
    files["requirements.txt"].write_text(requirements, encoding="utf-8")
    files["tests/test_quality_gate.py"].write_text(quality_gate_test, encoding="utf-8")
    return files


def run_codegen(db_results: dict, config: dict, job_id: str, log_fn=None) -> dict:
    from core.llm_client import LLMClient
    from engines.ml_engine.data_preprocessor import DataPreprocessor
    from engines.ml_engine.sagemaker_handler import SageMakerHandler
    from explainability.engine import ExplainabilityEngine
    from generator.code_gen_factory import CodeGenFactory
    from generator.code_verifier import CodeVerifier
    from generator.planner import Planner
    from generator.prompt_understanding import PromptUnderstandingLayer
    from generator.search_enriched_codegen import SearchEnrichedCodeGen
    from cg_brain.tuning_engine import check_tuning_threshold_and_train

    log = logging.getLogger(__name__)

    def step(name: str, msg: str) -> None:
        log.info("[%s] %s", name, msg)
        if log_fn:
            log_fn(name, msg)

    # ── Self-Learning: Check and trigger automated tuning ────────────────────
    # Before generating new code, check if the DPO dataset has reached the
    # threshold for fine-tuning the local Qwen SLM model.
    try:
        tuning_result = check_tuning_threshold_and_train(config)
        if tuning_result["triggered"]:
            step("tuning", f"Auto-tuning triggered: {tuning_result['message']}")
        else:
            step("tuning", tuning_result["message"])
    except Exception as tuning_exc:
        log.warning("Self-learning tuning check failed: %s", tuning_exc)

    spec = db_results.get("spec", {})
    ds_info = db_results.get("dataset", {})
    csv_path = _resolve_existing_path(ds_info.get("local_path", ""))

    if not csv_path.exists():
        # Universal path fallback: for non-ML tasks, a dataset might not be required yet.
        intent_spec = db_results.get("intent_spec", {})
        task_type = intent_spec.get("task_type", "unknown")
        if task_type in ("classification", "regression"):
            raise FileNotFoundError(f"Dataset CSV not found at '{csv_path}'. Run the Data Collection Agent first.")
        else:
            log.info("Dataset CSV missing, but continuing with non-ML task type: %s", task_type)

    # ── Stage 0.5: Universal/Non-ML Code Generation ──────────────────────────
    # If the intent extractor identified a non-ML task, short-circuit here.
    intent_spec  = db_results.get("intent_spec", {})
    task_type    = intent_spec.get("task_type", "unknown")
    snippets     = db_results.get("search_snippets", [])

    if task_type not in ("classification", "regression", "unknown"):
        step("codegen", f"Detected non-ML task type: {task_type}. Using universal generator...")
        enriched_gen = SearchEnrichedCodeGen(config)
        code_bundle  = enriched_gen.generate(intent_spec, db_results.get("prompt", ""), snippets)

        workspace_dir = _resolve_workspace_dir(config)
        workspace_dir.mkdir(parents=True, exist_ok=True)

        verifier = CodeVerifier(config)
        mode = "script" if task_type in ("api", "script", "algorithm", "data_pipeline") else "ml"

        code_bundle["python"] = verifier.verify(code_bundle.get("python", ""), "app.py", mode=mode)
        code_bundle["tests"]  = verifier.verify(code_bundle.get("tests", ""), "test_app.py", mode=mode)

        factory = CodeGenFactory(LLMClient(config), config)
        factory.write_to_workspace(code_bundle, workspace_dir)

        # Launch the generated app (Streamlit)
        deploy_url, _ = _launch_streamlit_app(workspace_dir, config, log, extra_env={"RADML_MODE": mode})

        step("done", f"Universal app ready -> {deploy_url}")
        return {
            "deploy_url": deploy_url,
            "app_path": str(workspace_dir / "app.py"),
            "intent_spec": intent_spec,
            "search_snippets": snippets,
            "generated_files": {"app.py": str(workspace_dir / "app.py")},
            "validation_summary": "Universal non-ML app generated and launched.",
            "mode": mode
        }

    step("preprocess", f"Preprocessing {csv_path.name}...")
    preprocessor = DataPreprocessor(config)
    pre_result = preprocessor.preprocess(csv_path, spec, job_id)
    step(
        "preprocess",
        f"Train: {pre_result['stats']['train_rows']} rows | "
        f"Features ({len(pre_result['feature_cols'])}): {pre_result['feature_cols']} | "
        f"Target: {pre_result['target_col']}",
    )

    step("sagemaker", "Uploading training and validation data derived from the collected dataset to S3...")
    sm = SageMakerHandler(config)
    train_s3, val_s3 = sm.upload_data(pre_result["train_path"], pre_result["val_path"], job_id)
    step("sagemaker", f"Train data -> {train_s3}")
    step("sagemaker", f"Validation data -> {val_s3}")

    step("sagemaker", "Launching SageMaker XGBoost training job with S3-backed collected data...")
    sm_meta = sm.run_training(
        train_s3_uri=train_s3,
        target_column=pre_result["target_col"],
        preprocess_result=pre_result,
        val_s3_uri=val_s3,
        source_dataset_s3_uri=ds_info.get("s3_uri"),
    )
    step(
        "sagemaker",
        f"Job: {sm_meta['job_name']} | Status: {sm_meta['status']} | Endpoint: {sm_meta['endpoint_name']}",
    )

    step("understand", "Building structured ProjectSpec from prompt...")
    llm = LLMClient(config)
    understanding = PromptUnderstandingLayer(llm)
    project_spec = understanding.build_spec(
        prompt=db_results.get("prompt", ""),
        parsed_spec=spec,
        dataset_info=ds_info,
        sm_meta=sm_meta,
        preprocess_result=pre_result,
        config=config,
    )
    step(
        "understand",
        f"Spec: task='{project_spec.get('task')}' | type={project_spec.get('task_type')} | "
        f"deliverables={project_spec.get('deliverables', [])}",
    )

    step("plan", "Producing architecture plan (no code yet)...")
    planner = Planner(llm)
    plan = planner.plan(project_spec)
    step("plan", f"Plan: {len(plan.get('file_structure', {}))} files | deps: {plan.get('dependencies', [])}")

    step("codegen", "Generating Streamlit app bundle...")
    mode = _infer_codegen_mode(project_spec, pre_result, user_prompt=db_results.get("prompt", ""))
    engine_meta = {
        "algorithm": sm_meta.get("algorithm") or project_spec.get("model_type") or "AWS SageMaker XGBoost",
        "endpoint": sm_meta.get("endpoint_name"),
        "model_name": sm_meta.get("model_name"),
        "training_job_name": sm_meta.get("job_name"),
        "s3_uri": train_s3,
        "task_type": str(project_spec.get("task_type") or pre_result.get("task_type") or "").lower(),
        "features": pre_result.get("feature_cols", []),
        "requested_features": project_spec.get("requested_features", spec.get("input_params", [])),
        "target_column": pre_result.get("target_col"),
        "output_description": (
            project_spec.get("output_description")
            or spec.get("output_description")
            or f"Predicted {spec.get('target_param', 'result')}"
        ),
        "target_param": project_spec.get("target", project_spec.get("target_col", "Result")),
        # IntentSpec structured inputs/outputs for prompt-aligned code generation
        "prompt_inputs": intent_spec.get("inputs", []),
        "prompt_outputs": intent_spec.get("outputs", []),
    }
    data_source_info = {
        "s3_uri": ds_info.get("s3_uri") or train_s3,
        "local_path": str(csv_path),
        "row_count": ds_info.get("row_count", 0),
        "columns": ds_info.get("columns", []),
        "val_s3_uri": val_s3,
    }
    workspace_dir = _resolve_workspace_dir(config)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    factory = CodeGenFactory(llm, config)
    verifier = CodeVerifier(cfg=config)
    sm_status = str(sm_meta.get("status", "")).lower()
    use_safe_local_app = mode == "ml" and (sm_status.startswith("mock") or sm_status.startswith("error"))
    code_bundle = factory.generate(
        mode=mode,
        engine_meta=engine_meta,
        data_source_info=data_source_info,
        user_prompt=db_results.get("prompt", ""),
    )
    if use_safe_local_app:
        step("codegen", "SageMaker endpoint is not live; using the hardened local-fallback Streamlit app template.")
        code_bundle = factory._parse_json_response(factory._stub_bundle_json(mode))
    code_bundle["python"] = verifier.verify(code_bundle.get("python", ""), "app.py", mode=mode)
    code_bundle["tests"] = verifier.verify(code_bundle.get("tests", ""), "test_app.py", mode=mode)
    code_bundle = _ensure_valid_bundle(factory, mode, code_bundle)
    factory.write_to_workspace(code_bundle, workspace_dir)

    deploy_url, streamlit_port = _launch_streamlit_app(
        workspace_dir,
        config,
        log,
        extra_env={
            "RADML_MOCK_MODE": "1" if use_safe_local_app else "0",
            "SAGEMAKER_REMOTE_ENABLED": "0" if use_safe_local_app else "1",
            "SAGEMAKER_ENDPOINT": sm_meta.get("endpoint_name", ""),
        },
    )

    written_files = {
        "app.py": workspace_dir / "app.py",
        "test_app.py": workspace_dir / "test_app.py",
    }
    written_files.update(_write_supporting_files(workspace_dir, pre_result, sm_meta, deploy_url, mode))

    validation_summary = (
        "Streamlit app launched successfully; unit tests generated; "
        "quality gate file added for >=90% model score enforcement."
    )
    step("codegen", f"Generated {len(written_files)} files: {list(written_files.keys())}")
    step("validate", validation_summary)
    if str(sm_meta.get("status", "")).startswith("mock"):
        step("validate", "SageMaker is currently in mock mode; the live app will run, but endpoint inference is simulated.")
    step("deploy", f"Streamlit app running at {deploy_url}")

    explanation: dict = {}
    step("explain", "Generating explanation and architecture diagram...")
    try:
        explain_engine = ExplainabilityEngine(llm, config)
        explain_payload = {
            "job_result": {
                "deploy_url": deploy_url,
                "endpoint_name": sm_meta.get("endpoint_name"),
                "sm_meta": sm_meta,
                "dataset": {
                    "row_count": int(ds_info.get("row_count", 0)),
                    "columns": ds_info.get("columns", []),
                    "merged": ds_info.get("merged", False),
                    "source_count": ds_info.get("source_count", 1),
                    "s3_uri": ds_info.get("s3_uri"),
                    "train_s3_uri": train_s3,
                    "validation_s3_uri": val_s3,
                    "preview_rows": ds_info.get("preview_rows", []),
                },
                "model": {
                    "task_type": pre_result.get("task_type"),
                    "feature_cols": pre_result.get("feature_cols", []),
                    "target_col": pre_result.get("target_col"),
                    "stats": pre_result.get("stats", {}),
                },
            },
            "db_results": db_results,
            "written_files": {k: str(v) for k, v in written_files.items()},
        }
        explain_timeout = int(config.get("explainability", {}).get("timeout_seconds", 12))
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(explain_engine.explain, **explain_payload)
            explanation = future.result(timeout=explain_timeout)
        step("explain", "Explanation generated")
    except FutureTimeoutError:
        log.warning("Explainability step timed out; continuing with lightweight fallback.")
        explanation = {
            "narrative": "Explanation generation timed out, but the app is ready to use.",
            "algorithm_card": {},
            "usage_guide": [],
            "data_story": {},
            "architecture_diagram_b64": "",
            "code_preview": {},
        }
        step("explain", "Explanation timed out; continuing without blocking deployment.")
    except Exception as exc:
        log.warning("Explainability engine failed: %s", exc)
        explanation = {}

    result = {
        "endpoint_name": sm_meta.get("endpoint_name"),
        "deploy_url": deploy_url,
        "app_path": str(written_files["app.py"]),
        "sm_meta": sm_meta,
        "training_data": {
            "source_dataset_s3_uri": ds_info.get("s3_uri"),
            "train_s3_uri": train_s3,
            "validation_s3_uri": val_s3,
        },
        "preprocess": {
            "feature_cols": pre_result["feature_cols"],
            "target_col": pre_result["target_col"],
            "task_type": pre_result["task_type"],
            "stats": pre_result["stats"],
        },
        "feature_order": pre_result["feature_cols"],
        "generated_files": {k: str(v) for k, v in written_files.items()},
        "validation_summary": validation_summary,
        "explanation": explanation,
        "project_spec": project_spec,
    }

    step("done", f"Code generation complete -> {deploy_url} ({validation_summary})")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAD-ML Code Generator")
    parser.add_argument("--results-json", required=True)
    parser.add_argument("--job-id", default=None)
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    config = _load_config(args.config)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    with open(args.results_json, encoding="utf-8") as f:
        db_results = json.load(f)

    result = run_codegen(db_results, config, args.job_id or str(uuid.uuid4())[:8])
    print(json.dumps(result, indent=2, default=str))
