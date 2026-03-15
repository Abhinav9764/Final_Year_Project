"""
backend/agent_runner.py — Full Pipeline Orchestrator
=====================================================
Flow:
  1. User prompt → Data_Collection_Agent (collects data + uploads to S3)
  2. Same prompt  → Code_Generator/RAD-ML (reads S3 data, trains via SageMaker)
  3. Captures SageMaker endpoint URL from stdout
  4. Returns real deploy link to frontend via SSE
"""

import queue
import subprocess
import sys
import threading
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class AgentRunner:
    """
    Orchestrates Data_Collection_Agent and Code_Generator as subprocesses.
    Publishes pipeline step events to status_queue for SSE streaming.
    """

    ENDPOINT_PATTERNS = [
        r"SAGEMAKER_ENDPOINT_URL:\s*(https?://\S+)",   # primary parseable log
        r"SageMaker endpoint ready.*?→\s*(\S+)",
        r"endpoint_name.*?['\"](\S+)['\"]",
        r"Flask app running.*?visit\s+(https?://\S+)",
        r"Flask app.*?at\s+(https?://\S+)",
        r"http://localhost:5000",                        # fallback
    ]

    def __init__(self, data_collector_dir: str, code_gen_dir: str):
        self.data_collector_dir = Path(data_collector_dir).resolve()
        self.code_gen_dir       = Path(code_gen_dir).resolve()
        self.status_queue       = queue.Queue()
        self.is_running         = False
        self._endpoint_url      = None

    # ── Public API ─────────────────────────────────────────────────────────────
    def run_pipeline(self, user_prompt: str) -> None:
        if self.is_running:
            logger.warning("Pipeline already running; ignoring duplicate trigger.")
            return
        self.is_running   = True
        self._endpoint_url = None

        t = threading.Thread(target=self._pipeline_thread, args=(user_prompt,), daemon=True)
        t.start()

    # ── Internal ───────────────────────────────────────────────────────────────
    def _pipeline_thread(self, user_prompt: str) -> None:
        try:
            # ── Stage 1: Data Collection + S3 Upload ─────────────────────────
            self._emit(1, "collecting",  "🔍 Collecting dataset from Kaggle & DuckDuckGo...")
            self._run_subprocess(
                label   = "Data_Collection_Agent",
                cwd     = self.data_collector_dir,
                cmd     = [sys.executable, "main.py",
                           "--prompt", user_prompt,
                           "--episodes", "3"],   # short run for demo
                patterns = {
                    r"Kaggle search completed":        (1, "🔍 Kaggle dataset found"),
                    r"DuckDuckGo|ddg":                 (1, "🔍 Scraping web results…"),
                    r"Triggering S3 synchronization":  (1, "☁️  Uploading data to AWS S3…"),
                    r"Upload successful|S3 synchronization": (2, "☁️  Dataset uploaded to S3 successfully"),
                },
            )

            # ── Stage 2: Code Generation ──────────────────────────────────────
            self._emit(2, "developing", "🧠 Code Generator developing model pipeline…")
            self._run_subprocess(
                label   = "Code_Generator",
                cwd     = self.code_gen_dir,
                cmd     = [sys.executable, "main.py", "--prompt", user_prompt],
                patterns = {
                    r"Route decision":                  (2, "🧠 Intent classified — building ML pipeline"),
                    r"Found collected data in S3":      (2, "☁️  Using your S3 dataset"),
                    r"No collected data|Falling back":  (2, "🧠 Falling back to Kaggle search"),
                    r"Code bundle generated":           (2, "🧠 Code successfully generated"),
                    r"Creating Autopilot job":          (3, "🏋️  Starting AWS SageMaker AutoML job…"),
                    r"Job status.*InProgress":          (3, "🏋️  SageMaker training in progress…"),
                    r"Dataset preprocessed":            (3, "🏋️  Dataset preprocessed for training"),
                    r"SageMaker endpoint ready":        (4, "🔧  Model trained — aligning hyperparameters…"),
                    r"features:":                       (4, "🔧  Feature set aligned"),
                    r"DQN action selected":             (5, "🤖 DQN scoring strategy…"),
                    r"Generation Attempt":              (5, "🤖 DQN selecting best code strategy"),
                    r"Unit tests passed":               (5, "✅ Unit tests passing"),
                    r"Starting Flask app|Flask app running": (6, "🚀 Deploying generated application…"),
                },
            )

            # ── Stage 7: Done ────────────────────────────────────────────────
            if self._endpoint_url:
                deploy_url = self._endpoint_url
                logger.info("Pipeline complete. Deploy URL: %s", deploy_url)
            else:
                deploy_url = "http://localhost:5000"
                logger.warning("No SageMaker endpoint captured — using local Flask fallback.")
            self._emit_done(deploy_url)

        except subprocess.CalledProcessError as e:
            logger.error("Agent subprocess failed: %s", e)
            self._emit(-1, "error", f"❌ Agent failed: {e}")
        except Exception as e:
            logger.exception("Unexpected pipeline error")
            self._emit(-1, "error", f"❌ Error: {e}")
        finally:
            self.is_running = False

    def _run_subprocess(self, label: str, cwd: Path, cmd: list, patterns: dict) -> None:
        """
        Runs an agent subprocess, maps log lines to pipeline events, and
        captures the SageMaker endpoint URL from stdout.
        """
        logger.info("[%s] Starting: %s", label, " ".join(str(c) for c in cmd))

        if not cwd.exists():
            raise FileNotFoundError(f"Agent directory not found: {cwd}")

        proc = subprocess.Popen(
            [str(c) for c in cmd],
            cwd         = str(cwd),
            stdout      = subprocess.PIPE,
            stderr      = subprocess.STDOUT,
            text        = True,
            bufsize     = 1,
            encoding    = "utf-8",
            errors      = "replace",
        )

        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue

            logger.debug("[%s] %s", label, line)

            # Check for SageMaker endpoint URL in output
            for ep_pat in self.ENDPOINT_PATTERNS:
                m = re.search(ep_pat, line, re.IGNORECASE)
                if m:
                    url = m.group(1) if m.lastindex else "http://localhost:5000"
                    if not url.startswith("http"):
                        url = f"https://runtime.sagemaker.us-east-1.amazonaws.com/endpoints/{url}/invocations"
                    logger.info("Captured deploy URL: %s", url)
                    self._endpoint_url = url
                    break

            # Map line to pipeline event
            for pattern, (step, msg) in patterns.items():
                if re.search(pattern, line, re.IGNORECASE):
                    self._emit(step, None, msg)
                    break

        proc.wait()
        if proc.returncode not in (0, None):
            raise subprocess.CalledProcessError(proc.returncode, cmd)

    # ── Queue helpers ──────────────────────────────────────────────────────────
    def _emit(self, step: int, status: str | None, message: str) -> None:
        event = {"step": step, "message": message}
        if status:
            event["status"] = status
        self.status_queue.put(event)

    def _emit_done(self, deploy_url: str) -> None:
        self.status_queue.put({
            "step":       7,
            "status":     "done",
            "message":    "✅ Pipeline complete!",
            "deploy_url": deploy_url,
        })
