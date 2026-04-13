"""
Chatbot_Interface/backend/orchestrator.py
==========================================
Job lifecycle manager — now user-aware for persisted history sync.
"""
from __future__ import annotations
import importlib.util
import logging
import sys
import threading
import time
import uuid
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_HERE         = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent

for _p in [str(_PROJECT_ROOT),
           str(_PROJECT_ROOT / "Data_Collection_Agent"),
           str(_PROJECT_ROOT / "Code_Generator" / "RAD-ML")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _import_run_collection():
    spec = importlib.util.spec_from_file_location(
        "dca_main", _PROJECT_ROOT / "Data_Collection_Agent" / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run_collection


def _import_run_codegen():
    spec = importlib.util.spec_from_file_location(
        "cg_main", _PROJECT_ROOT / "Code_Generator" / "RAD-ML" / "main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run_codegen


@dataclass
class Job:
    id:        str
    prompt:    str
    user_id:   int   = 0
    status:    str   = "queued"
    logs:      list  = field(default_factory=list)
    result:    dict  = field(default_factory=dict)
    error:     str   = ""
    created:   float = field(default_factory=time.time)
    cancelled: bool  = False          # set True to request cancellation
    dataset_path: str = ""            # pre-supplied CSV path (skips collection)


class Orchestrator:
    def __init__(self, config: dict):
        self._config = config
        self._jobs: dict[str, Job] = {}
        self._lock  = threading.Lock()

    def create_job(self, prompt: str) -> str:
        job_id = str(uuid.uuid4())[:12]
        with self._lock:
            self._jobs[job_id] = Job(id=job_id, prompt=prompt)
        return job_id

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict]:
        with self._lock:
            return [
                {"id": j.id, "prompt": j.prompt[:60],
                 "status": j.status, "created": j.created}
                for j in sorted(self._jobs.values(),
                                key=lambda j: j.created, reverse=True)
            ]

    def delete_job(self, job_id: str) -> bool:
        with self._lock:
            return bool(self._jobs.pop(job_id, None))

    def cancel_job(self, job_id: str) -> bool:
        """Signal a running job to stop at the next checkpoint."""
        job = self._jobs.get(job_id)
        if not job or job.status not in ("queued", "running"):
            return False
        job.cancelled = True
        logger.info("Cancellation requested for job %s", job_id)
        return True

    def update_job_status(self, job_id: str, status: str) -> bool:
        """Update job status — helper for tests and external triggers."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.status = status
        return True

    def start_pipeline(self, job_id: str, user_id: int = 0,
                       history_db=None) -> None:
        job = self._jobs.get(job_id)
        if not job:
            raise KeyError(f"Job {job_id} not found")
        job.user_id = user_id
        thread = threading.Thread(
            target=self._run_pipeline,
            args=(job, history_db), daemon=True,
        )
        thread.start()

    def _run_pipeline(self, job: Job, history_db=None) -> None:
        job.status = "running"

        def log_fn(step: str, msg: str) -> None:
            entry = {"step": step, "message": msg, "ts": time.time()}
            job.logs.append(entry)
            logger.info("[job=%s][%s] %s", job.id, step, msg)
            # Sync logs to the history store every 5 entries to avoid extra writes
            if history_db and len(job.logs) % 5 == 0:
                try:
                    history_db.upsert_job(
                        user_id=job.user_id, job_id=job.id,
                        status="running", logs=job.logs[-50:],
                    )
                except Exception:
                    pass

        try:
            # ── Cancellation check ────────────────────────────────────────────
            def _check_cancelled():
                if job.cancelled:
                    raise RuntimeError("Job cancelled by user.")

            # ── Stage 0: Intent / Spec Extraction ────────────────────────────
            # Extract a structured IntentSpec BEFORE data collection so all
            # downstream layers receive richer structured data.
            _check_cancelled()
            try:
                from core.llm_client import LLMClient  # type: ignore
                from generator.prompt_spec_extractor import PromptSpecExtractor  # type: ignore

                _llm_client = LLMClient(self._config)
                _extractor  = PromptSpecExtractor(_llm_client, self._config)
                intent_spec = _extractor.extract(job.prompt, save=True)
                snippets    = _extractor.enrich_with_search(intent_spec)
                log_fn(
                    'extract',
                    f'IntentSpec extracted: task_type={intent_spec.get("task_type")}  '
                    f'inputs={len(intent_spec.get("inputs", []))}  '
                    f'search_snippets={len(snippets)}',
                )
                job.result['intent_spec']     = intent_spec
                job.result['search_snippets'] = snippets
            except Exception as _spec_exc:
                logger.warning('Intent extraction failed (non-fatal): %s', _spec_exc)
                intent_spec = {}
                snippets    = []

            # ── Stage 1: Data Collection (or use pre-supplied dataset) ────────
            _check_cancelled()
            if job.dataset_path:
                log_fn("collection", f"Using uploaded dataset: {job.dataset_path} (skipping data collection)")
                import importlib.util as _ilu
                _pp_spec = _ilu.spec_from_file_location(
                    "prompt_parser",
                    _PROJECT_ROOT / "Data_Collection_Agent" / "dca_brain" / "prompt_parser.py"
                )
                _pp_mod = _ilu.module_from_spec(_pp_spec)
                _pp_spec.loader.exec_module(_pp_mod)
                spec = _pp_mod.PromptParser().parse(job.prompt)
                import pandas as pd
                from pathlib import Path
                ds_path = Path(job.dataset_path)
                df = pd.read_csv(ds_path, nrows=5)
                db_results = {
                    "job_id": job.id,
                    "prompt": job.prompt,
                    "spec": spec,
                    "dataset": {
                        "local_path":   str(ds_path),
                        "s3_uri":       None,
                        "columns":      list(df.columns),
                        "row_count":    int(sum(1 for _ in open(ds_path)) - 1),
                        "source_count": 1,
                        "preview_rows": df.head(10).to_dict(orient="records"),
                        "merged":       False,
                    },
                    "top_sources": [],
                }
                log_fn("collection", f"Dataset ready — {db_results['dataset']['row_count']} rows, {len(db_results['dataset']['columns'])} cols")
            else:
                log_fn("collection", "Starting data collection …")
                run_collection = _import_run_collection()
                db_results = run_collection(
                    prompt=job.prompt, config=self._config,
                    job_id=job.id, log_fn=log_fn,
                )
                # Log summary only for the normal collection path (upload path already logged above)
                log_fn("collection",
                       f"Dataset ready — {db_results['dataset']['row_count']} rows, "
                       f"{len(db_results['dataset']['columns'])} cols")

            _check_cancelled()
            log_fn("codegen", "Starting code generation …")
            run_codegen = _import_run_codegen()
            cg_result = run_codegen(
                db_results=db_results, config=self._config,
                job_id=job.id, log_fn=log_fn,
            )
            log_fn("codegen", f"App ready → {cg_result.get('deploy_url')}")

            job.result = {
                "deploy_url":    cg_result.get("deploy_url"),
                "endpoint_name": cg_result.get("endpoint_name"),
                "app_path":      cg_result.get("app_path"),
                "sm_meta":       cg_result.get("sm_meta", {}),
                "training_data": cg_result.get("training_data", {}),
                "dataset": {
                    "s3_uri":       db_results["dataset"].get("s3_uri"),
                    "row_count":    db_results["dataset"]["row_count"],
                    "columns":      db_results["dataset"]["columns"],
                    "preview_rows": db_results["dataset"]["preview_rows"],
                    "merged":       db_results["dataset"].get("merged", False),
                },
                "model": {
                    "feature_cols": cg_result.get("preprocess", {}).get("feature_cols", []),
                    "target_col":   cg_result.get("preprocess", {}).get("target_col"),
                    "task_type":    cg_result.get("preprocess", {}).get("task_type"),
                    "stats":        cg_result.get("preprocess", {}).get("stats", {}),
                },
                "input_params":  db_results["spec"].get("input_params", []),
                "target_param":  db_results["spec"].get("target_param"),
                "generated_files": cg_result.get("generated_files", {}),
                "validation_summary": cg_result.get("validation_summary", ""),
                "explanation":     cg_result.get("explanation", {}),
            }
            job.status = "done"
            log_fn("done", "Pipeline complete ✓")

        except Exception as exc:
            logger.exception("Pipeline failed for job %s", job.id)
            job.error  = str(exc)
            job.status = "error"
            job.logs.append({"step": "error", "message": str(exc), "ts": time.time()})

        finally:
            # Final sync to the history store
            if history_db:
                try:
                    history_db.upsert_job(
                        user_id=job.user_id, job_id=job.id,
                        prompt=job.prompt, status=job.status,
                        logs=job.logs, result=job.result, error=job.error,
                    )
                except Exception as e:
                    logger.warning("Failed to sync job to history storage: %s", e)
