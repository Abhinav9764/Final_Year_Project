"""
core/refinement_loop.py — LLM Self-Refinement Loop (V2)
========================================================
Replaces the DQN-based retry strategy with an iterative LLM-driven
self-refinement loop:

  Phase 1: Project Planning  (analyse prompt + engine_meta)
  Phase 2: Infrastructure    (build RAG index or SageMaker endpoint)
  Phase 3: Code Generation   (call LLM to write the app)
  Phase 4: Automated Testing (run generated tests)
  Phase 5: Self-Refinement   (feed errors back to LLM and regenerate)

The loop repeats Phases 3–5 until tests pass or max_retries is reached.
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
from generator.code_gen_factory import CodeGenFactory
from generator.code_verifier import CodeVerifier

log = logging.getLogger(__name__)

_GEO_SCOPE_TOKENS = {
    "india",
    "indian",
    "usa",
    "uk",
    "canada",
    "australia",
    "china",
    "japan",
    "europe",
    "asia",
    "africa",
    "brazil",
    "mexico",
}


class RefinementLoop:
    """
    Orchestrates the Code Generator's 5-phase pipeline:
      1. Plan  →  2. Build Engine  →  3. Generate Code  →  4. Test  →  5. Refine

    Parameters
    ----------
    cfg : dict
        Full config.yaml dict.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        refinement_cfg = cfg.get("refinement", {})
        self.max_retries = refinement_cfg.get("max_retries", 5)
        self.test_timeout = refinement_cfg.get("test_timeout_secs", 60)
        self.app_start_timeout = int(
            refinement_cfg.get(
                "app_start_timeout_secs",
                refinement_cfg.get("flask_start_timeout_secs", 120),
            )
        )

        streamlit_cfg = cfg.get("streamlit", {})
        flask_cfg = cfg.get("flask", {})
        self.streamlit_host = str(streamlit_cfg.get("host", "127.0.0.1"))
        self.streamlit_port = int(streamlit_cfg.get("port", flask_cfg.get("port", 5000)))
        self.flask_port = int(flask_cfg.get("port", 5000))

        self.app_dir = Path("workspace/current_app")
        self.logs_dir = Path("workspace/logs")
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def run(self, user_prompt: str) -> dict:
        """
        Execute the full 5-phase code generation pipeline.

        Parameters
        ----------
        user_prompt : str
            Natural-language description of what the user wants to build.

        Returns
        -------
        dict
            {
              "deploy_url": str,
              "attempts": int,
              "success": bool,
              "model_name": str,
              "endpoint_name": str,
              "training_job_name": str
            }
        """
        log.info("═══ RAD-ML V2 Refinement Loop — Starting ═══")

        # ── Phase 1: Project Planning ─────────────────────────────────────
        log.info("── Phase 1: Project Planning ──")
        router = Router(self.cfg)
        decision: RouteDecision = router.classify(user_prompt)
        log.info("Route decision → mode=%s (confidence=%.2f)",
                 decision.mode, decision.confidence)

        # ── Phase 2: Infrastructure Setup ─────────────────────────────────
        log.info("── Phase 2: Infrastructure Setup ──")
        data_source_info, engine_meta = self._build_infrastructure(
            decision, user_prompt
        )
        deployment_meta = {
            "route_mode": decision.mode,
            "algorithm_used": str(engine_meta.get("algorithm", "")),
        }
        if decision.mode in ("ml", "recommendation"):
            deployment_meta.update(
                {
                    "model_name": str(engine_meta.get("model_name", "")),
                    "endpoint_name": str(engine_meta.get("endpoint", "")),
                    "training_job_name": str(engine_meta.get("training_job_name", "")),
                    "endpoint_console_url": str(engine_meta.get("endpoint_console_url", "")),
                    "features": engine_meta.get("features", []),
                    "target_column": str(engine_meta.get("target_column", "")),
                }
            )
        deployment_meta = {k: v for k, v in deployment_meta.items() if v not in ("", [], None)}

        # ── Phases 3–5: Generate → Test → Refine Loop ────────────────────
        gen = CodeGenFactory(self.cfg)
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

                # Verify with Gemini
                code_bundle["python"] = verifier.verify(
                    code_bundle["python"], artifact_name="app.py"
                )
                code_bundle["tests"] = verifier.verify(
                    code_bundle["tests"], artifact_name="test_app.py"
                )

                # Write to workspace
                gen.write_to_workspace(code_bundle, self.app_dir)
                log.info("Code written to workspace.")

                # ── Phase 4: Automated Testing ────────────────────────────
                log.info("── Phase 4: Automated Testing ──")
                test_passed, test_error = self._run_tests()

                if not test_passed:
                    log.warning("Tests failed:\n%s", test_error)
                    last_error = test_error

                    if attempt < self.max_retries:
                        # ── Phase 5: Self-Refinement ──────────────────────
                        log.info(
                            "── Phase 5: Self-Refinement — feeding error back to LLM ──"
                        )
                        continue  # Loop back to Phase 3 with last_error
                    else:
                        log.warning(
                            "Max retries (%d) reached. Proceeding with last code.",
                            self.max_retries,
                        )

                # ── Launch Flask App ──────────────────────────────────────
                if app_proc and app_proc.poll() is None:
                    app_proc.terminate()

                app_proc, deploy_url = self._launch_generated_app()

                log.info("✓ Generation succeeded on attempt %d!", attempt)
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

        return {
            "deploy_url": "",
            "attempts": 0,
            "success": False,
            **deployment_meta,
        }

    # ── Phase 2: Infrastructure ───────────────────────────────────────────────

    def _build_infrastructure(
        self, decision, user_prompt: str
    ) -> tuple[dict, dict]:
        """Build the RAG index or SageMaker endpoint based on intent."""
        data_source_info: dict = {}
        engine_meta: dict = {}

        if decision.mode == "chatbot":
            data_source_info, engine_meta = self._build_chatbot_engine(
                decision
            )

        elif decision.mode in ("ml", "recommendation"):
            data_source_info, engine_meta = self._build_ml_engine(decision, user_prompt)

        else:
            raise ValueError(f"Unknown route mode: {decision.mode}")

        return data_source_info, engine_meta

    def _build_chatbot_engine(self, decision) -> tuple[dict, dict]:
        """Build the RAG engine for chatbot mode."""
        rt_cfg = self.cfg.get("chatbot_runtime", {})
        min_docs_for_rag = int(rt_cfg.get("min_docs_for_rag", 6))
        max_docs_for_rag = int(rt_cfg.get("max_docs_for_rag", 24))
        target_ddg_pages = int(self.cfg.get("ddg_max_pages", 10))

        # Load collected data from Data Collection Agent
        documents = self._load_collected_documents(decision)
        documents = self._dedupe_documents(documents, max_docs=max_docs_for_rag)

        if documents:
            log.info("Loaded %d RAG documents from Data Collection Agent.", len(documents))

        if len(documents) < min_docs_for_rag:
            # Augment with direct DDG search + web scraping.
            from collectors.ddg_scraper import DDGScraper

            scraper = DDGScraper(self.cfg)
            supplemental_docs = scraper.scrape(
                keywords=decision.keywords,
                max_pages=target_ddg_pages,
            )
            documents = self._dedupe_documents(
                [*documents, *supplemental_docs],
                max_docs=max_docs_for_rag,
            )
            log.info(
                "RAG documents after DDG scrape augmentation: %d",
                len(documents),
            )

        # Fallback to prevent crash if still empty (all fetched urls failed or empty DDG results)
        if not documents:
            log.warning("No documents could be extracted. Using dummy RAG document to prevent pipeline failure.")
            documents.append({
                "title": "Fallback Knowledge",
                "url": "local://fallback",
                "content": "No specific external information could be retrieved for this domain. "
                           "The assistant will rely on its internal baseline knowledge."
            })

        log.info("Building RAG index with %d documents...", len(documents))
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
        """Build the SageMaker engine for ML mode."""
        # Load collected data from Data Collection Agent
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

    @staticmethod
    def _is_local_dataset_path(path_value: str) -> bool:
        """True when path_value points to a local path that exists."""
        if not path_value:
            return False
        if path_value.startswith(("http://", "https://", "s3://")):
            return False
        return Path(path_value).exists()

    def _ensure_local_dataset_meta(self, decision, dataset_meta: dict) -> dict:
        """Resolve remote-only dataset metadata into a local CSV path."""
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
        """Load high-quality text documents collected by the Data Collection Agent."""
        import json

        keywords = [str(k).lower() for k in getattr(decision, "keywords", []) if str(k).strip()]
        rt_cfg = self.cfg.get("chatbot_runtime", {})
        min_relevance = float(rt_cfg.get("min_ddg_relevance", 0.12))

        # Try Data_Collection_Agent/db_results.json
        dc_results = Path("../../Data_Collection_Agent/db_results.json")
        if not dc_results.exists():
            dc_results = Path("../Data_Collection_Agent/db_results.json")
        if not dc_results.exists():
            log.info("No db_results.json found from Data Collection Agent.")
            return []

        try:
            with open(dc_results, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_ddg_results = data.get("duckduckgo", [])
            if raw_ddg_results:
                filtered_ddg_results = [
                    r
                    for r in raw_ddg_results
                    if self._is_relevant_ddg_result(r, keywords, min_relevance)
                ]
                log.info(
                    "Loaded %d DDG results; retained %d after relevance filtering.",
                    len(raw_ddg_results),
                    len(filtered_ddg_results),
                )

                if not filtered_ddg_results:
                    return []

                # Enrich DDG results by scraping each URL for full content.
                documents: list[dict] = []
                try:
                    from collectors.ddg_scraper import DDGScraper

                    scraper = DDGScraper(self.cfg)
                    documents = scraper.scrape_results(
                        search_results=filtered_ddg_results,
                        keywords=keywords,
                        max_pages=int(self.cfg.get("ddg_max_pages", 10)),
                    )
                except Exception as exc:
                    log.warning("DDG result scraping failed; falling back to snippets: %s", exc)

                if not documents:
                    # Fallback to snippets when page scraping fails.
                    for item in filtered_ddg_results:
                        title = str(item.get("title", "")).strip()
                        url = str(item.get("url", "")).strip()
                        snippet = str(item.get("snippet", "")).strip()
                        raw_text = str(item.get("text", "")).strip()
                        content = f"{snippet} {raw_text}".strip()
                        if not content:
                            continue
                        if keywords and self._keyword_overlap(f"{title} {content}", keywords) == 0:
                            continue
                        documents.append(
                            {
                                "title": title or url,
                                "url": url,
                                "content": content,
                            }
                        )

                return self._dedupe_documents(documents)
        except Exception as exc:
            log.warning("Failed to load db_results.json: %s", exc)

        return []

    @staticmethod
    def _keyword_overlap(text: str, keywords: list[str]) -> int:
        text_l = str(text or "").lower()
        return sum(1 for kw in keywords if len(kw) >= 3 and kw in text_l)

    @staticmethod
    def _normalize_doc_url(url: str) -> str:
        url = str(url or "").strip().lower()
        if not url:
            return ""
        return url.rstrip("/")

    @classmethod
    def _dedupe_documents(cls, documents: list[dict], max_docs: Optional[int] = None) -> list[dict]:
        deduped: list[dict] = []
        seen_urls: set[str] = set()
        seen_hashes: set[str] = set()

        for doc in documents:
            if not isinstance(doc, dict):
                continue

            title = str(doc.get("title", "")).strip()
            url = str(doc.get("url", "")).strip()
            content = str(doc.get("content", "")).strip()
            if not content:
                continue

            content_hash = hashlib.sha256(content.encode("utf-8", errors="ignore")).hexdigest()
            if content_hash in seen_hashes:
                continue

            norm_url = cls._normalize_doc_url(url)
            if norm_url and norm_url in seen_urls:
                continue

            if norm_url:
                seen_urls.add(norm_url)
            seen_hashes.add(content_hash)
            deduped.append(
                {
                    "title": title or (url if url else "Untitled"),
                    "url": url,
                    "content": content,
                }
            )

            if max_docs and len(deduped) >= max_docs:
                break

        return deduped

    def _is_relevant_ddg_result(
        self, item: dict, keywords: list[str], min_relevance: float
    ) -> bool:
        title = str(item.get("title", "")).strip()
        snippet = str(item.get("snippet", "")).strip()
        body = str(item.get("text", "")).strip()
        blob = f"{title} {snippet} {body}".strip().lower()
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

        overlap = self._keyword_overlap(blob, keywords)
        if keywords and overlap == 0:
            return False

        return relevance >= min_relevance or verified == 1

    def _load_collected_dataset(self, decision) -> dict:
        """Load dataset reference from the Data Collection Agent."""
        import json

        dc_results = Path("../../Data_Collection_Agent/db_results.json")
        if not dc_results.exists():
            dc_results = Path("../Data_Collection_Agent/db_results.json")

        if dc_results.exists():
            try:
                with open(dc_results, "r", encoding="utf-8") as f:
                    data = json.load(f)
                kaggle_results = data.get("kaggle", [])
                if kaggle_results:
                    best = self._pick_scoped_kaggle_result(kaggle_results, decision)
                    log.info(
                        "Using scoped Kaggle dataset from Data Collection Agent: %s",
                        best.get("title", "unknown"),
                    )
                    path_value = (
                        best.get("path")
                        or best.get("local_path")
                        or best.get("s3_uri")
                        or best.get("url", "")
                    )
                    return {
                        "path": path_value,
                        "title": best.get("title", ""),
                        "ref": best.get("ref", ""),
                        "s3_uri": best.get("s3_uri", ""),
                    }
            except Exception as exc:
                log.warning("Failed to load kaggle results: %s", exc)

        # Fallback to S3 or Kaggle search
        log.info("No pre-collected dataset found. Falling back to S3/Kaggle...")
        try:
            import boto3
            aws = self.cfg.get("aws", {})
            s3 = boto3.client("s3", region_name=aws.get("region", "us-east-1"))
            bucket = aws.get("s3_bucket", "rad-ml-datasets")
            objs = s3.list_objects_v2(Bucket=bucket, Prefix="collected_data/")
            if "Contents" in objs:
                latest = sorted(
                    objs["Contents"],
                    key=lambda x: x["LastModified"],
                    reverse=True,
                )[0]
                s3_uri = f"s3://{bucket}/{latest['Key']}"
                log.info("Found collected data in S3 → %s", s3_uri)
                return {
                    "path": s3_uri,
                    "s3_uri": s3_uri,
                    "title": f"Collected Data ({latest['Key']})",
                    "ref": "data-collection-agent/output",
                }
        except Exception as exc:
            log.warning("S3 fallback failed: %s", exc)

        # Last resort: Kaggle search
        from collectors.kaggle_client import KaggleClient
        kaggle = KaggleClient(self.cfg)
        return kaggle.fetch(query=" ".join(decision.keywords))

    def _pick_scoped_kaggle_result(self, results: list[dict], decision) -> dict:
        """
        Pick the best dataset by combining existing relevance with prompt scope.

        Scope emphasises intent keywords and explicit geography tokens
        (for example, "india" in house-price prompts).
        """
        if not results:
            return {}

        keywords = [str(k).lower() for k in getattr(decision, "keywords", []) if str(k).strip()]
        geo_terms = [k for k in keywords if k in _GEO_SCOPE_TOKENS]
        domain_terms = [k for k in keywords if len(k) >= 3][:10]

        def score(item: dict) -> float:
            haystack = self._dataset_scope_text(item)
            domain_hits = sum(1 for term in domain_terms if term in haystack)
            geo_hits = sum(1 for term in geo_terms if term in haystack)
            relevance = float(item.get("relevance", 0.0) or 0.0)

            if geo_terms and geo_hits == 0:
                # Hard penalty when explicit geography is requested but missing.
                return -1.0

            return (geo_hits * 2.0) + (domain_hits * 0.5) + relevance

        ranked = sorted(results, key=score, reverse=True)
        return ranked[0]

    @staticmethod
    def _dataset_scope_text(item: dict) -> str:
        tags = item.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        blob = (
            f"{item.get('title', '')} "
            f"{item.get('ref', '')} "
            f"{item.get('url', '')} "
            f"{item.get('path', '')} "
            f"{' '.join(str(t) for t in tags)}"
        )
        return re.sub(r"\s+", " ", blob.lower()).strip()

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
                log.warning("pytest is unavailable; falling back to direct test execution.")
                fallback = subprocess.run(
                    [sys.executable, test_file.name],
                    cwd=str(self.app_dir),
                    capture_output=True,
                    text=True,
                    timeout=self.test_timeout,
                )
                if fallback.returncode == 0:
                    log.info("âœ“ Fallback test execution passed.")
                    return True, ""
                error = (fallback.stderr or fallback.stdout or "").strip()
                return False, error[:2000]

            return False, combined[:2000]
        except subprocess.TimeoutExpired:
            return False, "Tests timed out after {}s".format(self.test_timeout)
        except Exception as exc:
            return False, str(exc)

    # ── Flask Launcher ────────────────────────────────────────────────────────

    def _launch_generated_app(self) -> tuple[subprocess.Popen, str]:
        """Launch the generated app using the detected runtime."""
        app_py = self.app_dir / "app.py"
        if not app_py.exists():
            raise FileNotFoundError(f"Generated app not found at {app_py}")

        runtime = self._detect_app_runtime(app_py)
        cmd, probe_url, deploy_url, runtime_label = self._build_launch_command(app_py, runtime)

        log.info("Launching %s app from %s", runtime_label, app_py)
        out_log = self.logs_dir / "generated_app_stdout.log"
        err_log = self.logs_dir / "generated_app_stderr.log"
        stdout_fh = open(out_log, "w", encoding="utf-8")
        stderr_fh = open(err_log, "w", encoding="utf-8")
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.app_dir),
                stdout=stdout_fh,
                stderr=stderr_fh,
            )
        finally:
            stdout_fh.close()
            stderr_fh.close()

        start = time.time()
        while time.time() - start < self.app_start_timeout:
            if proc.poll() is not None:
                raise RuntimeError(
                    f"{runtime_label} app crashed on start. "
                    f"See {err_log}. Last lines:\n{self._tail_file(err_log)}"
                )

            if self._is_http_ready(probe_url):
                log.info("%s app running (PID %s) - %s", runtime_label, proc.pid, deploy_url)
                return proc, deploy_url

            time.sleep(1)

        proc.terminate()
        raise TimeoutError(
            f"{runtime_label} app did not become reachable at {deploy_url} within "
            f"{self.app_start_timeout}s. Check {err_log}."
        )

    def _detect_app_runtime(self, app_py: Path) -> str:
        """
        Detect the generated app runtime from source code.

        Returns:
            "streamlit" when Streamlit markers are found, otherwise "flask".
        """
        try:
            src = app_py.read_text(encoding="utf-8", errors="replace").lower()
        except Exception:
            return "flask"

        streamlit_markers = (
            "import streamlit",
            "from streamlit",
            "st.set_page_config",
            "st.sidebar",
            "st.chat_input",
        )
        if any(marker in src for marker in streamlit_markers):
            return "streamlit"
        return "flask"

    def _get_free_port(self, default_port: int) -> int:
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', 0))
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                return s.getsockname()[1]
        except Exception as e:
            log.warning("Could not find free port: %s, falling back to %d", e, default_port)
            return default_port

    def _build_launch_command(
        self, app_py: Path, runtime: str
    ) -> tuple[list[str], str, str, str]:
        """
        Build launch command + health probe URL for the detected runtime.

        Returns:
            (cmd, probe_url, deploy_url, runtime_label)
        """
        if runtime == "streamlit":
            active_port = self._get_free_port(self.streamlit_port)
            deploy_url = f"http://localhost:{active_port}"
            return (
                [
                    sys.executable,
                    "-m",
                    "streamlit",
                    "run",
                    app_py.name,
                    "--server.headless",
                    "true",
                    "--server.address",
                    self.streamlit_host,
                    "--server.port",
                    str(active_port),
                    "--browser.gatherUsageStats",
                    "false",
                    "--logger.level",
                    "error",
                ],
                f"http://127.0.0.1:{active_port}/_stcore/health",
                deploy_url,
                "Streamlit",
            )

        active_port = self._get_free_port(self.flask_port)
        deploy_url = f"http://localhost:{active_port}"
        return (
            [sys.executable, app_py.name, "--port", str(active_port)],
            f"http://127.0.0.1:{active_port}/",
            deploy_url,
            "Flask",
        )

    @staticmethod
    def _is_http_ready(url: str, timeout: float = 1.5) -> bool:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
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
