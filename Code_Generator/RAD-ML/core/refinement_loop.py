"""
core/refinement_loop.py — LLM Self-Refinement Loop (Streamlit edition)
=======================================================================
Orchestrates the 5-phase pipeline.  Phase 5 (app launch) now always
starts a Streamlit process — Flask is no longer involved.

  Phase 1: Project Planning  (Router classifies the user prompt)
  Phase 2: Infrastructure    (build RAG index OR SageMaker endpoint)
  Phase 3: Code Generation   (LLM generates Streamlit app.py + test_app.py)
  Phase 4: Automated Testing (pytest / unittest on test_app.py)
  Phase 5: Self-Refinement   (feed errors back to LLM and regenerate)

The loop repeats Phases 3–5 until tests pass or max_retries is reached.
On success, app.py is launched with `streamlit run`.
"""

from __future__ import annotations

import hashlib
import logging
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from core.router import Router, RouteDecision
from core.llm_client import LLMClient
from generator.code_gen_factory import CodeGenFactory
from generator.code_verifier import CodeVerifier

log = logging.getLogger(__name__)

_GEO_SCOPE_TOKENS = {
    "india", "indian", "usa", "uk", "canada", "australia",
    "china", "japan", "europe", "asia", "africa", "brazil", "mexico",
}


class RefinementLoop:
    """
    Orchestrates the 5-phase Streamlit code-generation pipeline.

    Parameters
    ----------
    cfg : dict
        Full config.yaml dict.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        refinement_cfg = cfg.get("refinement", {})
        self.max_retries = int(refinement_cfg.get("max_retries", 5))
        self.test_timeout = int(refinement_cfg.get("test_timeout_secs", 60))
        self.app_start_timeout = int(
            refinement_cfg.get(
                "app_start_timeout_secs",
                refinement_cfg.get("flask_start_timeout_secs", 120),
            )
        )

        streamlit_cfg = cfg.get("streamlit", {})
        self.streamlit_host = str(streamlit_cfg.get("host", "127.0.0.1"))
        self.streamlit_port = int(streamlit_cfg.get("port", 8501))

        self.app_dir = Path("workspace/current_app")
        self.logs_dir = Path("workspace/logs")
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    # ── Public Entry Point ────────────────────────────────────────────────────
    def run(self, user_prompt: str) -> dict:
        """
        Execute the full 5-phase pipeline.

        Returns
        -------
        dict
            {
              "deploy_url": str,
              "attempts": int,
              "success": bool,
              "model_name": str,          # ml/recommendation only
              "endpoint_name": str,       # ml/recommendation only
              "training_job_name": str,   # ml/recommendation only
            }
        """
        log.info("═══ RAD-ML Streamlit Pipeline — Starting ═══")

        # ── Phase 1: Project Planning ─────────────────────────────────────
        log.info("── Phase 1: Project Planning ──")
        router = Router(self.cfg)
        decision: RouteDecision = router.classify(user_prompt)
        log.info(
            "Route decision → mode=%s (confidence=%.2f)", decision.mode, decision.confidence
        )

        # ── Phase 2: Infrastructure Setup ─────────────────────────────────
        log.info("── Phase 2: Infrastructure Setup ──")
        data_source_info, engine_meta = self._build_infrastructure(decision, user_prompt)

        deployment_meta: dict = {"route_mode": decision.mode}
        if decision.mode in ("ml", "recommendation"):
            deployment_meta.update(
                {
                    "model_name": str(engine_meta.get("model_name", "")),
                    "endpoint_name": str(engine_meta.get("endpoint", "")),
                    "training_job_name": str(engine_meta.get("training_job_name", "")),
                    "algorithm_used": str(engine_meta.get("algorithm", "")),
                    "features": engine_meta.get("features", []),
                    "target_column": str(engine_meta.get("target_column", "")),
                }
            )
        deployment_meta = {k: v for k, v in deployment_meta.items() if v not in ("", [], None)}

        # ── Phases 3–5: Generate → Test → Refine ─────────────────────────
        gen = CodeGenFactory(LLMClient(self.cfg), self.cfg)
        verifier = CodeVerifier(self.cfg)

        last_error: Optional[str] = None
        app_proc: Optional[subprocess.Popen] = None

        for attempt in range(1, self.max_retries + 1):
            log.info("═══ Attempt %d / %d ═══", attempt, self.max_retries)

            try:
                # ── Phase 3: Code Generation ──────────────────────────────
                log.info("── Phase 3: Code Generation (attempt %d) ──", attempt)
                code_bundle = gen.generate(
                    mode=decision.mode,
                    engine_meta=engine_meta,
                    data_source_info=data_source_info,
                    user_prompt=user_prompt,
                    prev_error=last_error,
                )

                # Verify app.py and test_app.py with Gemini (optional)
                code_bundle["python"] = verifier.verify(
                    code_bundle["python"], artifact_name="app.py"
                )
                code_bundle["tests"] = verifier.verify(
                    code_bundle["tests"], artifact_name="test_app.py"
                )

                # Write app.py + test_app.py to workspace
                gen.write_to_workspace(code_bundle, self.app_dir)
                log.info("Code written to workspace.")

                # ── Phase 4: Automated Testing ────────────────────────────
                log.info("── Phase 4: Automated Testing ──")
                test_passed, test_error = self._run_tests()

                if not test_passed:
                    log.warning("Tests failed:\n%s", test_error)
                    last_error = test_error

                    if attempt < self.max_retries:
                        log.info("── Phase 5: Self-Refinement — feeding error back to LLM ──")
                        continue
                    else:
                        log.warning(
                            "Max retries (%d) reached. Proceeding with last code.", self.max_retries
                        )

                # ── Launch Streamlit App ──────────────────────────────────
                if app_proc and app_proc.poll() is None:
                    app_proc.terminate()

                app_proc, deploy_url = self._launch_streamlit_app()

                log.info("✓ Streamlit app launched on attempt %d at %s", attempt, deploy_url)
                return {
                    "deploy_url": deploy_url,
                    "attempts": attempt,
                    "success": True,
                    **deployment_meta,
                }

            except Exception as exc:
                last_error = str(exc)
                log.error("Attempt %d failed: %s", attempt, last_error)

                if attempt == self.max_retries:
                    log.error("All %d attempts exhausted.", self.max_retries)
                    return {
                        "deploy_url": "",
                        "attempts": attempt,
                        "success": False,
                        "error": last_error,
                        **deployment_meta,
                    }

        return {"deploy_url": "", "attempts": 0, "success": False, **deployment_meta}

    # ── Phase 2: Infrastructure ───────────────────────────────────────────────
    def _build_infrastructure(self, decision, user_prompt: str) -> tuple[dict, dict]:
        if decision.mode == "chatbot":
            return self._build_chatbot_engine(decision)
        if decision.mode in ("ml", "recommendation"):
            return self._build_ml_engine(decision, user_prompt)
        raise ValueError(f"Unknown route mode: {decision.mode}")

    def _build_chatbot_engine(self, decision) -> tuple[dict, dict]:
        rt_cfg = self.cfg.get("chatbot_runtime", {})
        min_docs = int(rt_cfg.get("min_docs_for_rag", 6))
        max_docs = int(rt_cfg.get("max_docs_for_rag", 24))
        target_pages = int(self.cfg.get("ddg_max_pages", 10))

        documents = self._load_collected_documents(decision)
        documents = self._dedupe_documents(documents, max_docs=max_docs)

        if len(documents) < min_docs:
            from collectors.ddg_scraper import DDGScraper
            scraper = DDGScraper(self.cfg)
            supplemental = scraper.scrape(keywords=decision.keywords, max_pages=target_pages)
            documents = self._dedupe_documents([*documents, *supplemental], max_docs=max_docs)
            log.info("RAG documents after DDG augmentation: %d", len(documents))

        if not documents:
            log.warning("No documents extracted. Using fallback RAG document.")
            documents.append({
                "title": "Fallback Knowledge",
                "url": "local://fallback",
                "content": (
                    "No external information could be retrieved for this domain. "
                    "The assistant will rely on its internal baseline knowledge."
                ),
            })

        log.info("Building RAG index with %d documents…", len(documents))
        from engines.chatbot_engine.rag_builder import RAGBuilder
        rag = RAGBuilder(self.cfg)
        rag.build(documents)

        data_source_info = {"type": "rag", "doc_count": len(documents)}
        engine_meta = {
            "type": "rag+slm",
            "vector_store": str(rag.index_path),
            "slm_model": self.cfg.get("slm_model", "phi-3"),
            "algorithm": f"RAG + SLM ({self.cfg.get('slm_model', 'phi-3')})",
        }
        log.info("RAG index built at %s", rag.index_path)
        return data_source_info, engine_meta

    def _build_ml_engine(self, decision, user_prompt: str) -> tuple[dict, dict]:
        dataset_meta = self._load_collected_dataset(decision)
        dataset_meta = self._ensure_local_dataset_meta(decision, dataset_meta)
        dataset_path = str(dataset_meta.get("path", "")).strip()
        if not dataset_path:
            raise ValueError("No dataset path available for ML preprocessing.")

        from engines.ml_engine.data_preprocessor import DataPreprocessor
        preprocessor = DataPreprocessor(self.cfg)
        clean_meta = preprocessor.process(dataset_path, user_prompt=user_prompt)
        log.info("Dataset preprocessed — features: %s", clean_meta["features"])

        from engines.ml_engine.sagemaker_handler import SageMakerHandler
        sagemaker = SageMakerHandler(self.cfg)
        sm_meta = sagemaker.run_training(
            s3_input_uri=clean_meta["s3_uri"],
            target_column=clean_meta["target_column"],
        )

        data_source_info = dataset_meta
        engine_meta = {
            "type": "sagemaker",
            "endpoint": sm_meta["endpoint_name"],
            "endpoint_console_url": sm_meta.get("endpoint_console_url", ""),
            "model_name": sm_meta.get("model_name", ""),
            "training_job_name": sm_meta.get("job_name", ""),
            "features": clean_meta["features"],
            "target_column": clean_meta.get("target_column", ""),
            "s3_uri": clean_meta["s3_uri"],
            "algorithm": "XGBoost (SageMaker Built-in Algorithm)",
        }
        log.info("SageMaker endpoint ready → %s", sm_meta["endpoint_name"])
        return data_source_info, engine_meta

    # ── Dataset helpers (unchanged from original) ─────────────────────────────
    @staticmethod
    def _is_local_dataset_path(path_value: str) -> bool:
        if not path_value:
            return False
        if path_value.startswith(("http://", "https://", "s3://")):
            return False
        return Path(path_value).exists()

    def _ensure_local_dataset_meta(self, decision, dataset_meta: dict) -> dict:
        current_path = str(dataset_meta.get("path", "")).strip()
        if self._is_local_dataset_path(current_path):
            return dataset_meta
        from collectors.kaggle_client import KaggleClient
        kaggle = KaggleClient(self.cfg)
        ref = str(dataset_meta.get("ref", "")).strip()
        if ref and "/" in ref:
            log.info("Resolving local dataset from Kaggle ref: %s", ref)
            resolved = kaggle.fetch_by_ref(ref)
        else:
            query = " ".join(getattr(decision, "keywords", []) or [])
            if not query:
                query = str(dataset_meta.get("title", "dataset")).strip()
            log.info("Resolving local dataset from Kaggle search: %s", query)
            resolved = kaggle.fetch(query=query)
        if dataset_meta.get("s3_uri") and not resolved.get("s3_uri"):
            resolved["s3_uri"] = dataset_meta["s3_uri"]
        return resolved

    def _load_collected_documents(self, decision=None) -> list[dict]:
        import json
        keywords = [str(k).lower() for k in getattr(decision, "keywords", []) if str(k).strip()]
        rt_cfg = self.cfg.get("chatbot_runtime", {})
        min_relevance = float(rt_cfg.get("min_ddg_relevance", 0.12))

        for candidate in [
            Path("../../Data_Collection_Agent/db_results.json"),
            Path("../Data_Collection_Agent/db_results.json"),
        ]:
            if candidate.exists():
                dc_results = candidate
                break
        else:
            log.info("No db_results.json found from Data Collection Agent.")
            return []

        try:
            with open(dc_results, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_ddg_results = data.get("duckduckgo", [])
            if not raw_ddg_results:
                return []
            filtered = [
                r for r in raw_ddg_results
                if self._is_relevant_ddg_result(r, keywords, min_relevance)
            ]
            log.info("DDG results: %d total, %d retained after relevance filter.", len(raw_ddg_results), len(filtered))
            if not filtered:
                return []

            try:
                from collectors.ddg_scraper import DDGScraper
                scraper = DDGScraper(self.cfg)
                documents = scraper.scrape_results(
                    search_results=filtered,
                    keywords=keywords,
                    max_pages=int(self.cfg.get("ddg_max_pages", 10)),
                )
                if documents:
                    return self._dedupe_documents(documents)
            except Exception as exc:
                log.warning("DDG scraping failed; falling back to snippets: %s", exc)

            # Snippet fallback
            documents = []
            for item in filtered:
                title = str(item.get("title", "")).strip()
                url = str(item.get("url", "")).strip()
                content = f"{item.get('snippet', '')} {item.get('text', '')}".strip()
                if content and self._keyword_overlap(f"{title} {content}", keywords) > 0:
                    documents.append({"title": title or url, "url": url, "content": content})
            return self._dedupe_documents(documents)

        except Exception as exc:
            log.warning("Failed to load db_results.json: %s", exc)
        return []

    def _load_collected_dataset(self, decision) -> dict:
        import json
        for candidate in [
            Path("../../Data_Collection_Agent/db_results.json"),
            Path("../Data_Collection_Agent/db_results.json"),
        ]:
            if candidate.exists():
                try:
                    with open(candidate, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    kaggle_results = data.get("kaggle", [])
                    if kaggle_results:
                        best = self._pick_scoped_kaggle_result(kaggle_results, decision)
                        log.info("Using Kaggle dataset: %s", best.get("title", "unknown"))
                        return {
                            "path": best.get("path") or best.get("local_path") or best.get("s3_uri", ""),
                            "title": best.get("title", ""),
                            "ref": best.get("ref", ""),
                            "s3_uri": best.get("s3_uri", ""),
                        }
                except Exception as exc:
                    log.warning("Failed to load kaggle results: %s", exc)

        log.info("No pre-collected dataset. Falling back to S3/Kaggle…")
        try:
            import boto3
            aws = self.cfg.get("aws", {})
            s3 = boto3.client("s3", region_name=aws.get("region", "us-east-1"))
            bucket = aws.get("s3_bucket", "rad-ml-datasets")
            objs = s3.list_objects_v2(Bucket=bucket, Prefix="collected_data/")
            if "Contents" in objs:
                latest = sorted(objs["Contents"], key=lambda x: x["LastModified"], reverse=True)[0]
                s3_uri = f"s3://{bucket}/{latest['Key']}"
                log.info("Found collected data in S3 → %s", s3_uri)
                return {"path": s3_uri, "s3_uri": s3_uri, "title": latest["Key"], "ref": ""}
        except Exception as exc:
            log.warning("S3 fallback failed: %s", exc)

        from collectors.kaggle_client import KaggleClient
        return KaggleClient(self.cfg).fetch(query=" ".join(getattr(decision, "keywords", [])))

    def _pick_scoped_kaggle_result(self, results: list[dict], decision) -> dict:
        if not results:
            return {}
        keywords = [str(k).lower() for k in getattr(decision, "keywords", []) if str(k).strip()]
        geo_terms = [k for k in keywords if k in _GEO_SCOPE_TOKENS]
        domain_terms = [k for k in keywords if len(k) >= 3][:10]

        def score(item: dict) -> float:
            haystack = self._dataset_scope_text(item)
            geo_hits = sum(1 for t in geo_terms if t in haystack)
            domain_hits = sum(1 for t in domain_terms if t in haystack)
            relevance = float(item.get("relevance", 0.0) or 0.0)
            if geo_terms and geo_hits == 0:
                return -1.0
            return (geo_hits * 2.0) + (domain_hits * 0.5) + relevance

        return sorted(results, key=score, reverse=True)[0]

    @staticmethod
    def _dataset_scope_text(item: dict) -> str:
        tags = item.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        blob = (
            f"{item.get('title', '')} {item.get('ref', '')} "
            f"{item.get('url', '')} {item.get('path', '')} "
            f"{' '.join(str(t) for t in tags)}"
        )
        return re.sub(r"\s+", " ", blob.lower()).strip()

    @staticmethod
    def _keyword_overlap(text: str, keywords: list[str]) -> int:
        text_l = str(text or "").lower()
        return sum(1 for kw in keywords if len(kw) >= 3 and kw in text_l)

    @staticmethod
    def _normalize_doc_url(url: str) -> str:
        return str(url or "").strip().lower().rstrip("/")

    @classmethod
    def _dedupe_documents(cls, documents: list[dict], max_docs: Optional[int] = None) -> list[dict]:
        deduped: list[dict] = []
        seen_urls: set = set()
        seen_hashes: set = set()
        for doc in documents:
            if not isinstance(doc, dict):
                continue
            content = str(doc.get("content", "")).strip()
            if not content:
                continue
            content_hash = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
            if content_hash in seen_hashes:
                continue
            url = str(doc.get("url", "")).strip()
            norm_url = cls._normalize_doc_url(url)
            if norm_url and norm_url in seen_urls:
                continue
            if norm_url:
                seen_urls.add(norm_url)
            seen_hashes.add(content_hash)
            deduped.append({"title": doc.get("title", url or "Untitled"), "url": url, "content": content})
            if max_docs and len(deduped) >= max_docs:
                break
        return deduped

    def _is_relevant_ddg_result(self, item: dict, keywords: list[str], min_relevance: float) -> bool:
        blob = f"{item.get('title', '')} {item.get('snippet', '')} {item.get('text', '')}".strip().lower()
        if not blob:
            return False
        try:
            relevance = float(item.get("relevance", 0.0) or 0.0)
        except Exception:
            relevance = 0.0
        try:
            verified = int(item.get("verified", 0) or 0)
        except Exception:
            verified = 0
        if keywords and self._keyword_overlap(blob, keywords) == 0:
            return False
        return relevance >= min_relevance or verified == 1

    # ── Phase 4: Testing ──────────────────────────────────────────────────────
    def _run_tests(self) -> tuple[bool, str]:
        """Run generated unit tests and return (passed, error_output)."""
        test_file = self.app_dir / "test_app.py"
        if not test_file.exists():
            log.warning("No test_app.py found — skipping tests.")
            return True, ""

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", test_file.name],
                cwd=str(self.app_dir),
                capture_output=True,
                text=True,
                timeout=self.test_timeout,
            )
            if result.returncode == 0:
                log.info("✓ Unit tests passed!")
                return True, ""
            combined = (result.stderr or "") + "\n" + (result.stdout or "")
            if "No module named pytest" in combined:
                log.warning("pytest unavailable; running test file directly.")
                fallback = subprocess.run(
                    [sys.executable, test_file.name],
                    cwd=str(self.app_dir),
                    capture_output=True,
                    text=True,
                    timeout=self.test_timeout,
                )
                if fallback.returncode == 0:
                    log.info("✓ Fallback test execution passed.")
                    return True, ""
                return False, (fallback.stderr or fallback.stdout or "").strip()[:2000]
            return False, combined[:2000]
        except subprocess.TimeoutExpired:
            return False, f"Tests timed out after {self.test_timeout}s"
        except Exception as exc:
            return False, str(exc)

    # ── Phase 5: Streamlit Launcher ───────────────────────────────────────────
    def _launch_streamlit_app(self) -> tuple[subprocess.Popen, str]:
        """
        Launch the generated app.py with `streamlit run`.
        Returns (process, deploy_url).
        """
        app_py = self.app_dir / "app.py"
        if not app_py.exists():
            raise FileNotFoundError(f"Generated app not found at {app_py}")

        active_port = self._get_free_port(self.streamlit_port)
        deploy_url = f"http://localhost:{active_port}"
        probe_url = f"http://127.0.0.1:{active_port}/_stcore/health"

        cmd = [
            sys.executable, "-m", "streamlit", "run", app_py.name,
            "--server.headless", "true",
            "--server.address", self.streamlit_host,
            "--server.port", str(active_port),
            "--browser.gatherUsageStats", "false",
            "--logger.level", "error",
        ]

        out_log = self.logs_dir / "generated_app_stdout.log"
        err_log = self.logs_dir / "generated_app_stderr.log"

        log.info("Launching Streamlit app from %s on port %d", app_py, active_port)
        with open(out_log, "w", encoding="utf-8") as out_fh, \
             open(err_log, "w", encoding="utf-8") as err_fh:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.app_dir),
                stdout=out_fh,
                stderr=err_fh,
            )

        start = time.time()
        while time.time() - start < self.app_start_timeout:
            if proc.poll() is not None:
                raise RuntimeError(
                    f"Streamlit app crashed on start. See {err_log}.\n"
                    f"Last lines:\n{self._tail_file(err_log)}"
                )
            if self._is_http_ready(probe_url):
                log.info("Streamlit app running (PID %d) → %s", proc.pid, deploy_url)
                return proc, deploy_url
            time.sleep(1)

        proc.terminate()
        raise TimeoutError(
            f"Streamlit app did not become reachable at {deploy_url} within "
            f"{self.app_start_timeout}s. Check {err_log}."
        )

    @staticmethod
    def _get_free_port(default_port: int) -> int:
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", 0))
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                return s.getsockname()[1]
        except Exception as exc:
            log.warning("Could not find free port (%s); using default %d.", exc, default_port)
            return default_port

    @staticmethod
    def _is_http_ready(url: str, timeout: float = 1.5) -> bool:
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, method="GET"), timeout=timeout
            ) as resp:
                return int(resp.status) < 500
        except Exception:
            return False

    @staticmethod
    def _tail_file(path: Path, max_lines: int = 30) -> str:
        try:
            if not path.exists():
                return "(no log file yet)"
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            return "\n".join(lines[-max_lines:]) if lines else "(empty log)"
        except Exception as exc:
            return f"(unable to read log: {exc})"
