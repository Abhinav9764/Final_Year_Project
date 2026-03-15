"""
backend/orchestrator.py - Async Pipeline Orchestrator (V2)
===========================================================
Imports and calls agent functions directly with async job management.
Publishes live updates over WebSocket connections.
"""

import asyncio
import json
import logging
import re
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class JobState:
    """Tracks the state of a pipeline job."""

    job_id: str
    prompt: str
    uploaded_files: list[str] = field(default_factory=list)
    status: str = "queued"  # queued | running | done | error
    current_step: int = 0
    steps_total: int = 9
    logs: list = field(default_factory=list)
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class Orchestrator:
    """
    Async pipeline orchestrator that manages Data Collection and Code
    Generation agents without subprocesses.
    """

    def __init__(self, data_collector_dir: str, code_gen_dir: str):
        self.data_collector_dir = Path(data_collector_dir).resolve()
        self.code_gen_dir = Path(code_gen_dir).resolve()
        self.jobs: dict[str, JobState] = {}
        self._ws_connections: dict[str, list] = {}
        self._sse_queues: dict[str, list[asyncio.Queue]] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        # The agent runners mutate process-global state (cwd, sys.path, sys.modules).
        # Serialise these sections to prevent cross-job import races (e.g. "core" errors).
        self._agent_exec_lock = threading.Lock()

    # Job management
    def create_job(self, prompt: str, uploaded_files: list[str] = None) -> str:
        """Create a new pipeline job and return its ID."""
        job_id = str(uuid.uuid4())
        self.jobs[job_id] = JobState(job_id=job_id, prompt=prompt, uploaded_files=uploaded_files or [])
        logger.info("Job created: %s", job_id)
        return job_id

    def get_job(self, job_id: str) -> Optional[JobState]:
        return self.jobs.get(job_id)

    def register_ws(self, job_id: str, ws):
        """Register a WebSocket connection for live updates."""
        self._ws_connections.setdefault(job_id, []).append(ws)

    def unregister_ws(self, job_id: str, ws):
        conns = self._ws_connections.get(job_id, [])
        if ws in conns:
            conns.remove(ws)

    def register_sse(self, job_id: str, queue: asyncio.Queue):
        """Register an SSE queue for push-style event delivery."""
        self._sse_queues.setdefault(job_id, []).append(queue)

    def unregister_sse(self, job_id: str, queue: asyncio.Queue):
        queues = self._sse_queues.get(job_id, [])
        if queue in queues:
            queues.remove(queue)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running pipeline task if it exists."""
        job = self.jobs.get(job_id)
        if job and job.status == "running":
            job.status = "error"
            job.error = "Cancelled by user."
            job.updated_at = time.time()
            # Inform any active SSE clients
            asyncio.create_task(self._emit(job, job.current_step, "error", "Pipeline cancelled by user."))

        task = self._running_tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    # Pipeline execution
    async def run_pipeline(self, job_id: str) -> None:
        """
        Execute the full pipeline for a job:
        1. Data Collection Agent
        2. Code Generator Agent
        """
        job = self.jobs.get(job_id)
        if not job:
            logger.error("Job %s not found.", job_id)
            return

        job.status = "running"
        job.updated_at = time.time()

        try:
            await self._emit(job, 1, "processing", "Prompt received. Initializing pipeline...")
            prompt_keywords = self._extract_keywords_from_prompt(job.prompt)
            if prompt_keywords:
                await self._emit(
                    job,
                    2,
                    "processing",
                    f"Keywords extracted: {', '.join(prompt_keywords)}",
                )
            else:
                await self._emit(job, 2, "processing", "No explicit keywords found. Continuing...")

            await self._emit(job, 3, "collecting", "Dispatching request to Data Collection Agent...")

            if job.uploaded_files:
                await self._emit(job, 3, "collecting", f"Bypassing scrape: Using {len(job.uploaded_files)} provided files.")
                
                # Mock ML Dataset file kaggle_result.json
                kaggle_path = Path(self.data_collector_dir) / "kaggle_result.json"
                kaggle_data = {"path": job.uploaded_files[0], "features": [], "s3_uri": ""}
                kaggle_path.write_text(json.dumps(kaggle_data), encoding="utf-8")
                
                # Mock RAG Text Documents db_results.json
                ddg_path = Path(self.data_collector_dir) / "db_results.json"
                duckduckgo_mocks = []
                for f in job.uploaded_files:
                    try:
                        text_content = Path(f).read_text(encoding="utf-8", errors="ignore")[:4000]
                    except:
                        text_content = f"Attached document {Path(f).name}"
                    duckduckgo_mocks.append({
                        "title": Path(f).name,
                        "url": f"local://{Path(f).name}",
                        "snippet": "User uploaded document.",
                        "text": text_content
                    })
                ddg_path.write_text(json.dumps({"duckduckgo": duckduckgo_mocks}), encoding="utf-8")
                
                data_result = {"results": duckduckgo_mocks, "dataset_meta": kaggle_data}
                
                # Mutate prompt so Code Generator is aware of these files
                files_csv = ", ".join(job.uploaded_files)
                job.prompt += (
                    f"\n\n[SYSTEM]: The user has explicitly uploaded custom data files for this task: {files_csv}. "
                    "You MUST write code that utilizes these provided absolute paths natively (e.g. pd.read_csv() or SimpleDirectoryReader)."
                )
                
                await asyncio.sleep(1) # Visual pacing 
            else:
                data_result = await self._run_data_collector(job)

            data_keywords = data_result.get("keywords", []) if isinstance(data_result, dict) else []
            if data_keywords:
                await self._emit(
                    job,
                    4,
                    "collecting",
                    f"Data collector confirmed keywords: {', '.join(str(k) for k in data_keywords[:8])}",
                )
            else:
                await self._emit(job, 4, "collecting", "Data collector finished keyword pass.")

            results_count = len((data_result or {}).get("results", [])) if isinstance(data_result, dict) else 0
            await self._emit(job, 5, "collecting", f"Data collection completed ({results_count} records).")

            await self._emit(job, 6, "developing", "Sending collected data to Code Generator...")
            await self._emit(job, 7, "training", "Code generation and model training started...")

            gen_result = await self._run_code_generator(job)
            if not bool(gen_result.get("success", False)):
                details = str(gen_result.get("error", "Generated application failed to deploy.")).strip()
                raise RuntimeError(f"Code generator failed to deploy app: {details}")

            await self._emit(job, 8, "deploying", "Model deployment in progress...")

            deploy_url = str(gen_result.get("deploy_url", "")).strip()
            if not deploy_url:
                raise RuntimeError(
                    "Code generator did not return a deploy URL for a successful build."
                )
            model_name = str(gen_result.get("model_name", "")).strip()
            endpoint_name = str(gen_result.get("endpoint_name", "")).strip()
            training_job_name = str(gen_result.get("training_job_name", "")).strip()
            endpoint_console_url = str(gen_result.get("endpoint_console_url", "")).strip()
            algorithm_used = str(gen_result.get("algorithm_used", "")).strip()

            collected_data_summary = self._summarize_collection_results(data_result or {})
            code_artifacts = self._collect_generated_code_artifacts()

            job.status = "done"
            result_payload = {"deploy_url": deploy_url}
            if model_name:
                result_payload["model_name"] = model_name
            if endpoint_name:
                result_payload["endpoint_name"] = endpoint_name
            if training_job_name:
                result_payload["training_job_name"] = training_job_name
            if endpoint_console_url:
                result_payload["endpoint_console_url"] = endpoint_console_url
            if algorithm_used:
                result_payload["algorithm_used"] = algorithm_used
            if collected_data_summary:
                result_payload["collected_data"] = collected_data_summary
            if code_artifacts:
                result_payload["generated_code"] = code_artifacts
            job.result = result_payload
            job.updated_at = time.time()
            await self._emit(
                job,
                9,
                "done",
                "Pipeline complete!",
                deploy_url=deploy_url,
                extra=result_payload,
            )

        except asyncio.CancelledError:
            logger.warning("Job %s was cancelled by user.", job_id)
            job.status = "error"
            job.error = "Cancelled by user."
            await self._emit(job, job.current_step, "error", "Pipeline cancelled by user.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.exception("Job %s failed:", job_id)
            job.status = "error"
            job.error = str(e)
            await self._emit(job, job.current_step, "error", f"Error: {e}")
        finally:
            job.updated_at = time.time()
            if job_id in self._running_tasks:
                del self._running_tasks[job_id]

    async def _run_data_collector(self, job: JobState) -> dict:
        """
        Run the Data Collection Agent by importing and calling it directly.
        Falls back to subprocess if direct import fails.
        """
        try:
            dc_dir = str(self.data_collector_dir)
            if dc_dir not in sys.path:
                sys.path.insert(0, dc_dir)

            loop = asyncio.get_running_loop()
            future = loop.run_in_executor(
                None,
                self._data_collector_sync,
                job.prompt,
                dc_dir,
            )
            elapsed = 0
            while not future.done():
                await asyncio.sleep(8)
                elapsed += 8
                if not future.done():
                    await self._emit(
                        job,
                        3,
                        "collecting",
                        f"Data collection in progress... ({elapsed}s)",
                    )

            result = await future
            return result or {}

        except Exception as exc:
            import traceback

            print("--- DATA COLLECTOR ERROR IN ORCHESTRATOR ---")
            traceback.print_exc()
            logger.exception("Data collector failed critically: %s", exc)
            await self._emit(job, 3, "collecting", f"Data collection error: {exc}")
            return {}

    def _clear_agent_modules(self) -> None:
        """Remove agent package namespaces so the next import is clean."""
        for mod in ["core", "utils", "collectors", "brain", "engines", "generator"]:
            for key in list(sys.modules.keys()):
                if key == mod or key.startswith(mod + "."):
                    del sys.modules[key]

    def _data_collector_sync(self, prompt: str, dc_dir: str) -> dict:
        """Synchronous wrapper for the data collection agent."""
        import yaml

        orig_dir = str(Path.cwd())
        orig_path = sys.path.copy()
        with self._agent_exec_lock:
            try:
                import os

                os.chdir(dc_dir)

                if dc_dir in sys.path:
                    sys.path.remove(dc_dir)
                sys.path.insert(0, dc_dir)

                cfg_path = Path(dc_dir) / "config.yaml"
                with open(cfg_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)

                try:
                    from utils.logger import setup_logger

                    setup_logger(config.get("logging", {}))
                except Exception:
                    pass

                self._clear_agent_modules()

                from core.pipeline import DataCollectionPipeline

                engine = DataCollectionPipeline(config)
                result = engine.run(prompt)
                logger.info("Data collector returned %d results.", len(result.get("results", [])))
                return result
            except Exception as exc:
                import traceback

                print("--- DATA COLLECTOR SYNC ERROR ---")
                traceback.print_exc()
                logger.exception("Data collector sync failed: %s", exc)
                raise
            finally:
                import os

                os.chdir(orig_dir)
                if dc_dir in sys.path and dc_dir not in orig_path:
                    sys.path.remove(dc_dir)

    async def _run_code_generator(self, job: JobState) -> dict:
        """
        Run the Code Generator Agent by importing and calling it directly.
        """
        try:
            cg_dir = str(self.code_gen_dir)
            if cg_dir not in sys.path:
                sys.path.insert(0, cg_dir)

            loop = asyncio.get_running_loop()
            future = loop.run_in_executor(
                None,
                self._code_generator_sync,
                job.prompt,
                cg_dir,
            )
            elapsed = 0
            while not future.done():
                await asyncio.sleep(15)
                elapsed += 15
                if not future.done():
                    await self._emit(
                        job,
                        7,
                        "training",
                        f"Code generation/training in progress... ({elapsed}s)",
                    )

            result = await future
            return result or {}

        except Exception as exc:
            logger.error("Code generator failed: %s", exc)
            await self._emit(job, 7, "training", f"Code generation error: {exc}")
            raise RuntimeError(f"Code generation failed: {exc}")

    def _code_generator_sync(self, prompt: str, cg_dir: str) -> dict:
        """Synchronous wrapper for the code generator agent."""
        import yaml

        orig_dir = str(Path.cwd())
        orig_path = sys.path.copy()
        with self._agent_exec_lock:
            try:
                import os

                os.chdir(cg_dir)

                if cg_dir in sys.path:
                    sys.path.remove(cg_dir)
                sys.path.insert(0, cg_dir)

                cfg_path = Path(cg_dir) / "config.yaml"
                with open(cfg_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)

                for attempt in range(1, 3):
                    self._clear_agent_modules()
                    try:
                        from core.refinement_loop import RefinementLoop

                        loop_obj = RefinementLoop(config)
                        result = loop_obj.run(prompt)
                        logger.info("Code generator returned: success=%s", result.get("success"))
                        return result
                    except Exception as exc:
                        msg = str(exc).lower()
                        transient_client_error = (
                            "client has been closed" in msg
                            or "cannot send a request" in msg
                        )

                        if transient_client_error and attempt == 1:
                            logger.warning(
                                "Code generator hit transient closed-client error. "
                                "Retrying once with a fresh session state: %s",
                                exc,
                            )
                            try:
                                from huggingface_hub.utils._http import close_session  # type: ignore

                                close_session()
                            except Exception:
                                pass
                            continue
                        raise
            except Exception as exc:
                logger.exception("Code generator sync failed: %s", exc)
                raise
            finally:
                import os

                os.chdir(orig_dir)
                if cg_dir in sys.path and cg_dir not in orig_path:
                    sys.path.remove(cg_dir)

    async def _emit(
        self,
        job: JobState,
        step: int,
        status: str,
        message: str,
        deploy_url: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> None:
        """Push a live update to job state and connected WebSocket clients."""
        job.current_step = step
        job.updated_at = time.time()
        log_entry = {
            "step": step,
            "status": status,
            "message": message,
            "timestamp": job.updated_at,
        }
        if deploy_url:
            log_entry["deploy_url"] = deploy_url
        if extra:
            for key, value in extra.items():
                if value is not None:
                    log_entry[key] = value
        job.logs.append(log_entry)

        logger.info("[Job %s] Step %d: %s", job.job_id, step, message)

        payload = json.dumps(log_entry)
        dead = []
        for ws in self._ws_connections.get(job.job_id, []):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.unregister_ws(job.job_id, ws)

        dead_queues = []
        for queue in self._sse_queues.get(job.job_id, []):
            try:
                queue.put_nowait(log_entry)
            except Exception:
                dead_queues.append(queue)
        for queue in dead_queues:
            self.unregister_sse(job.job_id, queue)

    @staticmethod
    def _extract_keywords_from_prompt(prompt: str, limit: int = 8) -> list[str]:
        tokens = re.findall(r"[a-zA-Z0-9_]+", (prompt or "").lower())
        if not tokens:
            return []

        stopwords = {
            "a", "an", "and", "are", "as", "at", "be", "build", "can", "for", "from",
            "how", "i", "in", "is", "it", "me", "model", "of", "on", "or", "please",
            "the", "to", "want", "with", "you", "your",
        }
        seen = set()
        keywords = []
        for token in tokens:
            if len(token) < 3 or token in stopwords or token in seen:
                continue
            seen.add(token)
            keywords.append(token)
            if len(keywords) >= limit:
                break
        return keywords

    @staticmethod
    def _safe_read_text(path: Path, max_chars: int = 6000) -> dict:
        if not path.exists() or not path.is_file():
            return {}
        text = path.read_text(encoding="utf-8", errors="replace")
        trimmed = text[:max_chars]
        return {
            "path": str(path),
            "line_count": len(text.splitlines()),
            "preview": trimmed,
            "truncated": len(text) > max_chars,
        }

    def _collect_generated_code_artifacts(self) -> dict:
        app_dir = self.code_gen_dir / "workspace" / "current_app"
        tpl_dir = app_dir / "templates"
        files = {
            "app_py": self._safe_read_text(app_dir / "app.py"),
            "test_py": self._safe_read_text(app_dir / "test_app.py"),
            "html": self._safe_read_text(tpl_dir / "index.html"),
            "css": self._safe_read_text(tpl_dir / "style.css"),
        }
        return {k: v for k, v in files.items() if v}

    @staticmethod
    def _summarize_collection_results(data_result: dict) -> dict:
        if not isinstance(data_result, dict):
            return {}

        keywords = data_result.get("keywords", [])
        mode = data_result.get("mode", "")
        raw_results = data_result.get("results", [])
        combined_dataset = data_result.get("combined_dataset", {}) if isinstance(data_result, dict) else {}
        top = []

        for item in raw_results[:8]:
            if not isinstance(item, dict):
                continue
            top.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "ref": item.get("ref", ""),
                    "relevance": item.get("relevance", 0),
                    "path": item.get("path", ""),
                }
            )

        return {
            "mode": mode,
            "keywords": keywords,
            "count": len(raw_results),
            "top_results": top,
            "combined_dataset": {
                "path": combined_dataset.get("path", ""),
                "s3_uri": combined_dataset.get("s3_uri", ""),
                "columns": combined_dataset.get("columns", []),
                "row_count": combined_dataset.get("row_count", 0),
                "column_count": combined_dataset.get("column_count", 0),
                "source_datasets": combined_dataset.get("source_datasets", []),
                "preview_rows": combined_dataset.get("preview_rows", [])[:10],
            } if isinstance(combined_dataset, dict) and combined_dataset else {},
        }
