"""
generator/search_enriched_codegen.py
======================================
Orchestrates:
  1. PromptSpecExtractor → IntentSpec JSON
  2. Google Search enrichment (optional)
  3. Code generation via CodeGenFactory (routed by task_type)

Supported task_type values and their CodeGenFactory modes:
  - classification  → "ml"
  - regression      → "ml"
  - api             → "script"   (generates a standalone FastAPI/Flask script)
  - script          → "script"
  - algorithm       → "script"
  - web_app         → "ml"       (Streamlit UI)
  - data_pipeline   → "script"
  - unknown         → "ml"       (generic Streamlit app)

For recommendation/chatbot prompts the existing _infer_codegen_mode() in
main.py takes precedence — SearchEnrichedCodeGen is called BEFORE the ML
pipeline, primarily to produce the intents spec and enrich the context.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# CodeBundle: {"python": ..., "tests": ..., "html": "", "css": ""}
CodeBundle = Dict[str, str]

# Maps IntentSpec task_type → CodeGenFactory mode
_TASK_TYPE_TO_MODE: Dict[str, str] = {
    "classification": "ml",
    "regression": "ml",
    "api": "script",
    "script": "script",
    "algorithm": "script",
    "web_app": "ml",
    "data_pipeline": "script",
    "unknown": "ml",
}

# ── System prompt used when generating code from IntentSpec ──────────────────
_SYSTEM_PROMPT = (
    "You are an expert Python developer. "
    "When given an IntentSpec JSON and optional code-search snippets, "
    "generate clean, production-quality Python code. "
    "For Streamlit tasks use ONLY Streamlit widgets. "
    "For API/script tasks use FastAPI or pure stdlib as appropriate. "
    "Always include type hints, docstrings, and error handling."
)

# ── Task prompt template ──────────────────────────────────────────────────────
_TASK_PROMPT = """\
=== INTENT SPEC ===
{intent_spec_json}

=== GOOGLE SEARCH CONTEXT ===
{search_context}

=== GENERATION INSTRUCTIONS ===
Based on the IntentSpec above, generate a complete Python implementation.

Task type  : {task_type}
Mode       : {mode}

Rules:
1. Implement ALL inputs listed in the spec with proper validation.
2. Produce ALL outputs described in the spec.
3. Handle every edge_case listed.
4. Satisfy every success_criteria listed.
5. Respect every constraint listed.
6. If mode is "script" or "api": output a self-contained Python script/FastAPI app.
7. If mode is "ml" or "web_app": output a Streamlit app (st.*, no Flask).
8. Include a matching test file using pytest.

Output ONLY valid JSON with EXACTLY these keys:
{{ "python": "<main code>", "tests": "<test code>", "html": "", "css": "" }}
No markdown. No explanation outside the JSON.
"""


class SearchEnrichedCodeGen:
    """
    High-level orchestrator: IntentSpec → search enrichment → code bundle.

    Usage
    -----
    extractor = PromptSpecExtractor(llm_client, config)
    generator = SearchEnrichedCodeGen(config)
    intent    = extractor.extract(user_prompt)
    bundle    = generator.generate(intent, user_prompt)
    """

    def __init__(self, config: dict) -> None:
        self._config = config

    # ── Public API ─────────────────────────────────────────────────────────────

    def generate(
        self,
        intent_spec: dict,
        user_prompt: str,
        search_snippets: Optional[list] = None,
    ) -> CodeBundle:
        """
        Generate a CodeBundle from an IntentSpec.

        Parameters
        ----------
        intent_spec     : output of PromptSpecExtractor.extract()
        user_prompt     : original raw prompt (used as fallback for CodeGenFactory)
        search_snippets : pre-fetched search snippets (or None to skip)

        Returns
        -------
        CodeBundle dict {"python": ..., "tests": ..., "html": "", "css": ""}
        """
        task_type = intent_spec.get("task_type", "unknown")
        mode = _TASK_TYPE_TO_MODE.get(task_type, "ml")

        logger.info("SearchEnrichedCodeGen: task_type=%s → mode=%s", task_type, mode)

        # Build engine_meta from IntentSpec so CodeGenFactory can work correctly
        engine_meta = self._build_engine_meta(intent_spec)
        data_source_info = self._build_data_source_info(intent_spec)

        # Build the enriched prompt for CodeGenFactory
        search_context = (
            "\n\n---\n\n".join(search_snippets)
            if search_snippets
            else "(no search context)"
        )
        enriched_prompt = _TASK_PROMPT.format(
            intent_spec_json=json.dumps(intent_spec, indent=2),
            search_context=search_context,
            task_type=task_type,
            mode=mode,
        )

        # Delegate to CodeGenFactory (it already handles LLM dispatch + stubs)
        try:
            from generator.code_gen_factory import CodeGenFactory
            from core.llm_client import LLMClient

            factory = CodeGenFactory(LLMClient(self._config), self._config)
            bundle = factory.generate(
                mode=mode if mode in ("ml", "chatbot", "recommendation") else "ml",
                engine_meta=engine_meta,
                data_source_info=data_source_info,
                user_prompt=user_prompt,
            )
        except Exception as exc:
            logger.warning("CodeGenFactory failed (%s) — using direct LLM call.", exc)
            bundle = self._direct_llm_generate(enriched_prompt, mode)

        # For api/script/algorithm/data_pipeline: if we got a Streamlit stub,
        # try again with a direct LLM call that understands the enriched prompt.
        if mode == "script" and self._is_streamlit_stub(bundle.get("python", "")):
            logger.info("Streamlit stub detected for script mode — retrying with direct LLM.")
            bundle = self._direct_llm_generate(enriched_prompt, mode)

        logger.info(
            "Bundle generated — py=%d chars  tests=%d chars",
            len(bundle.get("python", "")),
            len(bundle.get("tests", "")),
        )
        return bundle

    # ── Internal helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _build_engine_meta(intent_spec: dict) -> dict:
        """Translate IntentSpec into the engine_meta shape CodeGenFactory expects."""
        inputs = intent_spec.get("inputs", [])
        features = [i.get("name", f"input_{n}") for n, i in enumerate(inputs)]
        outputs = intent_spec.get("outputs", [])
        target = outputs[0].get("name", "output") if outputs else "output"
        out_desc = outputs[0].get("description", "") if outputs else ""

        task_type_map = {
            "classification": "classification",
            "regression": "regression",
            "api": "regression",
            "script": "regression",
            "algorithm": "regression",
            "web_app": "classification",
            "data_pipeline": "regression",
            "unknown": "regression",
        }
        task_type = task_type_map.get(intent_spec.get("task_type", "unknown"), "regression")

        return {
            "algorithm": f"Generated by RAD-ML intent extractor ({intent_spec.get('task_type')})",
            "endpoint": "radml-endpoint",
            "model_name": "radml-model",
            "training_job_name": "",
            "s3_uri": "",
            "task_type": task_type,
            "features": features,
            "requested_features": features,
            "target_column": target,
            "output_description": out_desc,
            "target_param": target,
        }

    @staticmethod
    def _build_data_source_info(intent_spec: dict) -> dict:
        """Build a minimal data_source_info dict from IntentSpec."""
        inputs = intent_spec.get("inputs", [])
        columns = [i.get("name", "") for i in inputs]
        return {
            "s3_uri": "",
            "local_path": "",
            "row_count": 0,
            "columns": columns,
        }

    def _direct_llm_generate(self, enriched_prompt: str, mode: str) -> CodeBundle:
        """
        Fallback: call LLMClient directly when CodeGenFactory is unavailable or
        returns a Streamlit stub for a non-UI task type.
        """
        try:
            from core.llm_client import LLMClient

            llm = LLMClient(self._config)
            full = f"{_SYSTEM_PROMPT}\n\n{enriched_prompt}"
            raw = llm.generate(full)
            return self._parse_bundle(raw)
        except Exception as exc:
            logger.error("Direct LLM code generation also failed: %s", exc)
            return self._empty_bundle()

    @staticmethod
    def _parse_bundle(raw: str) -> CodeBundle:
        """Parse a JSON CodeBundle from LLM output."""
        import ast
        import re

        cleaned = re.sub(r"```[a-z]*\n?", "", str(raw or ""), flags=re.IGNORECASE).strip().rstrip("`").strip()
        for loader in (json.loads, ast.literal_eval):
            try:
                data = loader(cleaned)
                if isinstance(data, dict):
                    return {
                        "python": str(data.get("python", "") or ""),
                        "tests": str(data.get("tests", "") or ""),
                        "html": "",
                        "css": "",
                    }
            except Exception:
                pass
        # Last resort: treat entire response as python
        return {"python": cleaned, "tests": "", "html": "", "css": ""}

    @staticmethod
    def _is_streamlit_stub(python_code: str) -> bool:
        """Return True if python_code looks like the generic ML Streamlit stub."""
        src = (python_code or "").lower()
        return "import streamlit" in src and "sagemaker" in src

    @staticmethod
    def _empty_bundle() -> CodeBundle:
        return {
            "python": "# Code generation failed — please retry.\n",
            "tests": "# Tests unavailable.\n",
            "html": "",
            "css": "",
        }
