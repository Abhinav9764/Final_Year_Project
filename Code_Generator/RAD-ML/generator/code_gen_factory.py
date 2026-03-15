"""
generator/code_gen_factory.py — LLM Code Generator V2 (DeepSeek / Qwen3)
=========================================================================
Builds the prompt template and calls the configured LLM to generate a
complete Streamlit application.

V2 Changes:
  - Removed DQN action mapping (temperature, LLM switching)
  - prev_error is now a first-class parameter for self-refinement
  - Deterministic LLM selection with fallback

Qwen backend priority (no paid API required):
  1. HuggingFace Hub Inference API   — free tier, public models
  2. Ollama local server             — fully offline
  3. Offline stub                    — base template fallback
"""

from __future__ import annotations

import ast
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

CodeBundle = Dict[str, str]   # {"python": ..., "html": ..., "css": ...}

WORKSPACE_APP_DIR  = Path("workspace/current_app")
TEMPLATES_DIR      = WORKSPACE_APP_DIR / "templates"


class CodeGenFactory:
    """
    Calls DeepSeek or Qwen3 with the structured prompt template and
    writes the generated code to the workspace.

    Args:
        cfg: Full config dict.
    """

    def __init__(self, cfg: dict):
        self.cfg          = cfg
        self.primary_llm  = cfg.get("primary_llm", "deepseek")
        self.deepseek_cfg = cfg.get("deepseek", {})
        self.qwen_cfg     = cfg.get("qwen", {})
        # Resolve qwen backend: "hf" | "ollama" | "stub"
        self._qwen_backend: Optional[str] = None   # determined lazily on first call

    # ── Public API ────────────────────────────────────────────────────────────
    def generate(
        self,
        mode:             str,
        engine_meta:      dict,
        data_source_info: dict,
        user_prompt:      str,
        prev_error:       Optional[str] = None,
    ) -> CodeBundle:
        """
        Build prompt → call LLM → parse JSON → return CodeBundle.

        Args:
            mode:             "chatbot" | "ml"
            engine_meta:      Output from the engine builder (endpoint / index path)
            data_source_info: Output from the collector (s3_uri / doc_count)
            user_prompt:      Original user request (for context)
            prev_error:       Error from the previous attempt (for self-refinement)

        Returns:
            CodeBundle with keys "python", "html", "css", "tests".
        """
        system_prompt = self._build_system_prompt()
        task_prompt   = self._build_task_prompt(
            mode, engine_meta, data_source_info, user_prompt, prev_error
        )

        self._current_engine_meta = engine_meta

        llm_key   = self._pick_llm()
        temp      = self._get_temperature(llm_key)
        full_resp = self._call_llm(llm_key, system_prompt, task_prompt, temp)

        try:
            bundle = self._parse_json_response(full_resp)
        except Exception as exc:
            log.warning(
                "Failed to parse model output as JSON (%s). Falling back to stub bundle.",
                exc,
            )
            bundle = self._parse_json_response(self._stub_bundle_json(mode))

        python_code = bundle.get("python", "")
        if not python_code.strip():
            log.warning("Generated bundle is missing python code. Falling back to stub bundle.")
            bundle = self._parse_json_response(self._stub_bundle_json(mode))
        elif not self._is_streamlit_python(python_code):
            log.warning(
                "Generated code is not Streamlit-only. Falling back to Streamlit stub bundle."
            )
            bundle = self._parse_json_response(self._stub_bundle_json(mode))
        elif not self._matches_expected_mode(python_code, mode):
            log.warning(
                "Generated code does not match requested mode '%s'. Falling back to Streamlit stub bundle.",
                mode,
            )
            bundle = self._parse_json_response(self._stub_bundle_json(mode))
        log.info("Code bundle generated — py=%d chars  tests=%d chars  html=%d chars  css=%d chars",
                 len(bundle.get("python", "")),
                 len(bundle.get("tests", "")),
                 len(bundle.get("html", "")),
                 len(bundle.get("css", "")))
        return bundle

    def write_to_workspace(self, bundle: CodeBundle, app_dir: Path = WORKSPACE_APP_DIR) -> None:
        """Write the generated code files to workspace/current_app/."""
        app_dir.mkdir(parents=True, exist_ok=True)
        tpl_dir = app_dir / "templates"
        tpl_dir.mkdir(parents=True, exist_ok=True)

        (app_dir / "app.py").write_text(bundle.get("python", ""), encoding="utf-8")
        (app_dir / "test_app.py").write_text(bundle.get("tests", ""), encoding="utf-8")
        (tpl_dir / "index.html").write_text(bundle.get("html", ""), encoding="utf-8")
        (tpl_dir / "style.css").write_text(bundle.get("css", ""), encoding="utf-8")
        log.info("Workspace written: app.py, test_app.py, index.html, style.css → %s", app_dir)

    # ── Prompt Builders ───────────────────────────────────────────────────────
    @staticmethod
    def _build_system_prompt() -> str:
        return "You are an expert Python Developer. Always respond in English only."

    def _build_task_prompt(
        self,
        mode:             str,
        engine_meta:      dict,
        data_source_info: dict,
        user_prompt:      str,
        prev_error:       Optional[str],
    ) -> str:
        # ── Resolve template placeholders ──────────────────────────────────
        if mode == "chatbot":
            mode_label = "Chatbot"
        elif mode == "recommendation":
            mode_label = "Recommendation System"
        else:
            mode_label = "Predictive ML"
            
        data_source_lbl = self._format_data_source(mode, engine_meta, data_source_info)
        algorithm_lbl   = self._format_algorithm(mode, engine_meta)
        features_block  = self._format_features(mode, engine_meta)
        connectivity    = "llama-index and chromadb" if mode == "chatbot" else "boto3"
        form_or_chat    = self._form_or_chat_instruction(mode, engine_meta)
        scope_hint      = self._scope_guardrail_instruction(user_prompt)
        region_hint     = self._region_input_instruction(user_prompt, mode)
        metrics_hint    = self._metrics_instruction(mode)

        # ── Core prompt (verbatim template from spec) ──────────────────────
        prompt = f"""Task: Build a full-stack Streamlit application based on the following context:

Mode: {mode_label}
Data Source: {data_source_lbl}
Algorithm/Model: {algorithm_lbl}

User Goal: {user_prompt}

Requirements:

Requirement 1. Create app.py:
   - Must be a valid Streamlit application using `st.set_page_config` and an appealing dark theme injected via `st.markdown("<style>...</style>", unsafe_allow_html=True)`.
   - If ML or Recommendation: Generate Streamlit input widgets (`st.text_input`, `st.number_input`, etc.) for model features {features_block}.
     - Implement **Data Parsing**: You MUST strip all alphabetical characters, symbols, and units from string inputs (e.g., convert "200sq.ft" to `200.0` float) using Regex before assigning them to the payload. If doing `float()`, handle ValueError appropriately.
     - Implement **Data Validation**: Show `st.error` for missing or invalid feature values.
     - Implement **Overfitting/Underfitting Mitigations**: 
        - If training locally (fallback), use `train_test_split`, `StandardScaler`, and appropriate models.
        - If using SageMaker, ensure the payload is clean numeric floats, correctly formatted for the endpoint.
     - Never mix unrelated datasets; use only prompt-scoped data/features relevant to the user goal.
     {scope_hint}
     {region_hint}
     {metrics_hint}
   - If Recommendation: Generate UI components (cards or tables) to clearly render the Top-N suggested items returned by the model based on the input features.
   - If Chatbot: Use the LlamaIndex framework with Chroma Vector Store (data/vector_store/index)
     - Use the Ollama model online for the SLM generation.
     - Process flow: Data -> cleaning -> embeddings -> vector database -> user query -> query embedding -> top-k retrieval -> re-ranking -> LLM answer using retrieval.
     - For better ranking, use a "retrieve + re-rank" pipeline using sentence transformers (e.g. cross-encoder or SentenceTransformerRerank) for the semantic search.
     - Implement **Response Validation**: Fall back to a default answer if the SLM returns an empty or invalid response.
     - Resolve the project root from `Path(__file__).resolve()` and load the Chroma index using that root.
     - Do not eagerly load embeddings/index at import time; lazy-load using `@st.cache_resource` on first chat request.
   - Error Handling: Wrap the prediction/inference in a try-except block and use `st.error("<message>")` on failure.
   - Connectivity: Use the {connectivity} libraries.

Requirement 2. Create test_app.py:
   - Implement **Unit Tests** using `unittest` or `pytest`.
   - Test the core logic separated from Streamlit components (e.g. data validation functions).
   - For ML/Recommendation: Mock the SageMaker/boto3 call to verify input-to-feature mapping.
   - If geographic input is required by the prompt, add a test that missing region fails validation.
   - For Chatbot: Mock the RAG retrieval to verify response generation.

Requirement 3. Visuals and Layout:
   - Use a two-column layout using `st.columns()` for ML/Recommendation to separate inputs and metrics/info.
   {form_or_chat}
   - Allow **Multiple Input types**: For ML/Recommendation, include a "Bulk Predict" option using `st.file_uploader`.
   - Display an algorithm badge and metrics panel in the sidebar or an organized info panel.
   - Use `st.spinner` while the request is in flight.
   - Include all text, labels, and generated widget titles in English only.

Output ONLY the code in a JSON format with exactly these keys:
{{ "python": "<app.py content>", "tests": "<test_app.py content>", "html": "", "css": "" }}
Do NOT include any explanation, markdown fences, or text outside the JSON object."""

        # ── Self-Refinement: inject previous error ─────────────────────────
        if prev_error:
            prompt += (
                f"\n\nIMPORTANT — The previous attempt failed with this error. "
                f"Fix the code to resolve it:\n```\n{prev_error[:1500]}\n```"
            )

        return prompt

    # ── LLM Dispatch ──────────────────────────────────────────────────────────
    def _pick_llm(self) -> str:
        """Return the primary LLM key. Fallback handled in _call_llm."""
        return self.primary_llm

    def _get_temperature(self, llm_key: str) -> float:
        cfg = self.deepseek_cfg if llm_key == "deepseek" else self.qwen_cfg
        return cfg.get("temperature", 0.3)

    def _call_llm(self, llm_key: str, system: str, task: str, temp: float) -> str:
        if llm_key == "deepseek":
            return self._call_deepseek(system, task, temp)
        if llm_key == "qwen":
            return self._call_qwen(system, task, temp)
        log.warning("Unknown llm key '%s'. Falling back to Qwen.", llm_key)
        return self._call_qwen(system, task, temp)

    def _call_deepseek(self, system: str, task: str, temp: float) -> str:
        api_key = self.deepseek_cfg.get("api_key", "")
        model   = self.deepseek_cfg.get("model", "deepseek-coder")
        max_tok = self.deepseek_cfg.get("max_tokens", 4096)
        
        mode_hint = "chatbot" if "Chatbot" in task else ("recommendation" if "Recommendation" in task else "ml")

        if not api_key or "YOUR" in api_key:
            log.warning("DeepSeek API key not set — returning stub code.")
            return self._stub_bundle_json(mode_hint)

        try:
            from openai import OpenAI                                    # type: ignore
        except ImportError:
            log.warning("openai package missing - falling back to Qwen/stub.")
            return self._call_qwen(system, task, temp)

        try:
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": task},
                ],
                temperature=temp,
                max_tokens=max_tok,
            )
            return resp.choices[0].message.content
        except Exception as exc:
            log.warning("DeepSeek call failed: %s. Falling back to Qwen/stub.", exc)
            return self._call_qwen(system, task, temp)

    # ── Qwen — free backends (HuggingFace Hub → Ollama → stub) ───────────────
    def _call_qwen(self, system: str, task: str, temp: float) -> str:
        """
        Calls Qwen3 without any paid API key.
        Priority:
          1. HuggingFace Hub Inference API (free tier — public model)
          2. Ollama local server           (fully offline, no internet needed)
          3. Offline stub                  (base template fallback)
        """
        mode_hint = "chatbot" if "Chatbot" in task else ("recommendation" if "Recommendation" in task else "ml")

        # ── Try 1: HuggingFace Hub Inference ────────────────────────────────
        if self._qwen_backend in (None, "hf"):
            result = self._call_qwen_hf(system, task, temp)
            if result is not None:
                self._qwen_backend = "hf"
                return result
            log.warning("HuggingFace Hub unavailable — trying Ollama.")

        # ── Try 2: Ollama local server ───────────────────────────────────────
        if self._qwen_backend in (None, "ollama"):
            result = self._call_qwen_ollama(system, task, temp)
            if result is not None:
                self._qwen_backend = "ollama"
                return result
            log.warning("Ollama unavailable — falling back to offline stub.")

        # ── Try 3: Offline stub ──────────────────────────────────────────────
        self._qwen_backend = "stub"
        log.warning("Qwen using offline stub (no HF or Ollama available).")
        return self._stub_bundle_json(mode_hint)

    def _call_qwen_hf(self, system: str, task: str, temp: float) -> Optional[str]:
        """
        HuggingFace Hub Serverless Inference — free for public models.
        Uses Qwen/Qwen2.5-Coder-3B-Instruct (lighter code model).
        pip install huggingface_hub
        """
        try:
            from huggingface_hub import InferenceClient                   # type: ignore
        except ImportError:
            log.debug("huggingface_hub not installed — skipping HF backend.")
            return None

        qwen_cfg = self.qwen_cfg
        hf_token = qwen_cfg.get("hf_token", "")   # optional; improves rate limits
        hf_model = qwen_cfg.get(
            "hf_model",
            "Qwen/Qwen2.5-Coder-3B-Instruct",     # lighter public model
        )
        max_tok  = qwen_cfg.get("max_tokens", 4096)

        try:
            client = InferenceClient(
                model=hf_model,
                token=hf_token if hf_token and "YOUR" not in hf_token else None,
            )
            # Build a single combined prompt (HF chat_completion)
            response = client.chat_completion(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": task},
                ],
                max_tokens=max_tok,
                temperature=max(temp, 0.01),   # HF requires > 0
            )
            content = response.choices[0].message.content
            log.info("Qwen via HuggingFace Hub (%s) — %d chars returned.",
                     hf_model, len(content or ""))
            return content
        except Exception as exc:
            log.warning("HuggingFace Hub call failed: %s", exc)
            return None

    def _call_qwen_ollama(self, system: str, task: str, temp: float) -> Optional[str]:
        """
        Ollama local server — fully offline inference.
        Prerequisites:
          1. Install Ollama:  https://ollama.com/download
          2. Pull model:      ollama pull qwen2.5-coder:3b
          3. Ensure running:  ollama serve
        pip install ollama
        """
        try:
            import ollama as _ollama                                      # type: ignore
        except ImportError:
            log.debug("ollama package not installed — skipping Ollama backend.")
            return None

        qwen_cfg   = self.qwen_cfg
        ollama_model = qwen_cfg.get("ollama_model", "qwen2.5-coder:3b")
        max_tok      = qwen_cfg.get("max_tokens", 4096)

        try:
            response = _ollama.chat(
                model=ollama_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": task},
                ],
                options={"temperature": temp, "num_predict": max_tok},
            )
            content = response["message"]["content"]
            log.info("Qwen via Ollama (%s) — %d chars returned.",
                     ollama_model, len(content or ""))
            return content
        except Exception as exc:
            log.warning("Ollama call failed: %s", exc)
            return None

    # ── Response Parsing ──────────────────────────────────────────────────────
    @staticmethod
    def _parse_json_response(raw: str) -> CodeBundle:
        """Extract the JSON object from the LLM response (handles markdown fences)."""
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("```").strip()

        # Find first '{' to last '}' (LLM may add preamble text)
        start = cleaned.find("{")
        end   = cleaned.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError(f"No JSON object found in LLM response:\n{raw[:400]}")

        bundle = json.loads(cleaned[start:end])
        return {
            "python": bundle.get("python", ""),
            "tests":  bundle.get("tests", ""),
            "html":   bundle.get("html", ""),
            "css":    bundle.get("css", ""),
        }

    # ── Formatting Helpers ────────────────────────────────────────────────────
    @staticmethod
    def _format_data_source(mode: str, engine_meta: dict, data_source_info: dict) -> str:
        if mode == "chatbot":
            count = data_source_info.get("doc_count", "?")
            return f"Local Vector DB (Chroma) — {count} web documents"
        else:
            s3 = engine_meta.get("s3_uri", data_source_info.get("s3_uri", "s3://bucket/data.csv"))
            return f"S3 CSV: {s3}"

    @staticmethod
    def _format_algorithm(mode: str, engine_meta: dict) -> str:
        if mode == "chatbot":
            slm = engine_meta.get("slm_model", "Phi-3 or Ollama")
            return f"SLM ({slm}) + Chroma RAG"
        else:
            algorithm = str(engine_meta.get("algorithm", "")).strip()
            if algorithm:
                return algorithm
            endpoint = engine_meta.get("endpoint", "rad-ml-endpoint")
            model_name = engine_meta.get("model_name", "rad-ml-model")
            return f"AWS SageMaker Endpoint ({endpoint}) using model {model_name}"

    @staticmethod
    def _format_features(mode: str, engine_meta: dict) -> str:
        if mode != "ml":
            return ""
        features: List[str] = engine_meta.get("features", [])
        return f"{features}" if features else "['feature_1', 'feature_2', ...]"

    @staticmethod
    def _form_or_chat_instruction(mode: str, engine_meta: dict) -> str:
        if mode == "chatbot":
            return (
                "- Build a Streamlit chat interface using `st.chat_message` and `st.chat_input`.\n"
                "   - Keep chat history in `st.session_state` and render all messages each rerun.\n"
                "   - Show a spinner while generating the assistant response."
            )
        elif mode == "recommendation":
            features: List[str] = engine_meta.get("features", ["user_id", "item_id"])
            feat_list = ", ".join(features[:15])
            return (
                f"- Build a Streamlit recommendation interface for input features: {feat_list}.\n"
                "   - Display recommendation outputs natively using visual components like cards via `st.container` or `st.data_editor`.\n"
                "   - Separate the inputs from the Top-N rendered results."
            )

        features: List[str] = engine_meta.get("features", ["feature_1", "feature_2"])
        feat_list = ", ".join(features[:15])
        return (
            f"- Build a Streamlit ML form with labelled widgets for features: {feat_list}.\n"
            "   - Use `st.columns` and `st.form` for clean layout and submit flow.\n"
            "   - Display prediction outputs with `st.success` or a highlighted result container."
        )

    @staticmethod
    def _scope_guardrail_instruction(user_prompt: str) -> str:
        prompt_l = (user_prompt or "").lower()
        if any(term in prompt_l for term in ("house", "housing", "real estate", "price", "rent")):
            return (
                "- Restrict training/inference data to property-price records only; "
                "exclude unrelated domains."
            )
        return (
            "- Restrict training/inference data to rows directly relevant to the prompt domain; "
            "exclude unrelated records."
        )

    @staticmethod
    def _region_input_instruction(user_prompt: str, mode: str) -> str:
        if mode != "ml":
            return "- For non-ML modes, do not add region-specific validation unless explicitly needed."

        prompt_l = (user_prompt or "").lower()
        needs_region = any(
            token in prompt_l
            for token in ("region", "state", "city", "location", "area", "india", "indian")
        )

        if needs_region:
            return (
                "- Add a required categorical input `region` (or the user-requested location field). "
                "Show `st.error` when missing/invalid and stop prediction for that request."
            )
        return (
            "- If the user asks for location-specific prediction, include and validate a required "
            "`region` input."
        )

    @staticmethod
    def _metrics_instruction(mode: str) -> str:
        if mode == "chatbot":
            return (
                "- Include lightweight runtime metrics in the Streamlit sidebar/info panel "
                "(for example response count and average latency)."
            )
        elif mode == "recommendation":
            return (
                "- Compute and display relevant recommendation metrics or item metadata (e.g. relevance score, "
                "item category, or matching confidence) alongside the recommended outputs."
            )

        return (
            "- Compute and display algorithm-specific metrics in Streamlit. "
            "For regression include MAE, RMSE, and R2. For classification include Accuracy, "
            "Precision, Recall, and F1 (plus ROC-AUC when binary)."
        )

    # ── Stub (offline fallback) ───────────────────────────────────────────────
    # ── Stub (offline fallback) ───────────────────────────────────────────────
    def _stub_bundle_json(self, mode: str) -> str:
        from generator.templates.base_streamlit import STREAMLIT_APP_CHATBOT, STREAMLIT_APP_ML

        python_code = STREAMLIT_APP_CHATBOT if mode == "chatbot" else STREAMLIT_APP_ML
        
        if mode == "ml" and getattr(self, "_current_engine_meta", None):
            features = self._current_engine_meta.get("features", [])
            endpoint = self._current_engine_meta.get("endpoint", "rad-ml-endpoint")
            
            if features:
                features_str = "[\n" + ",\n".join(f'    "{f}"' for f in features) + "\n]"
                python_code = re.sub(
                    r'FEATURES = list\(CFG\.get\("ml_features", \[\]\)\) or \[.*?\]',
                    f'FEATURES = {features_str}',
                    python_code,
                    flags=re.DOTALL
                )
            if endpoint:
                python_code = re.sub(
                    r'ENDPOINT_NAME = os\.environ\.get\(\n    "SAGEMAKER_ENDPOINT",\n    CFG\.get\("aws", \{\}\)\.get\("sagemaker_endpoint_name", "rad-ml-endpoint"\),\n\)',
                    f'ENDPOINT_NAME = os.environ.get("SAGEMAKER_ENDPOINT", "{endpoint}")',
                    python_code,
                    flags=re.DOTALL
                )

        if mode == "chatbot":
            tests_code = (
                "import app as app_module\n\n"
                "def test_app_loads():\n"
                "    assert hasattr(app_module, 'get_rag')\n"
                "def test_generate_answer_empty():\n"
                "    answer = app_module.generate_answer('')\n"
                "    assert isinstance(answer, str)\n"
                "    assert len(answer) > 0\n"
            )
        else:
            tests_code = (
                "import app as app_module\n\n"
                "def test_encode_feature_numeric():\n"
                "    assert app_module._encode_feature('area', ' 1500.5 ') == '1500.5'\n"
                "def test_encode_feature_string():\n"
                "    val = app_module._encode_feature('region', 'north')\n"
                "    assert val.isdigit()\n"
                "def test_prediction_dummy(monkeypatch):\n"
                "    monkeypatch.setattr(app_module, 'sm_runtime', None)\n"
                "    assert app_module.make_prediction(['100', '200']) == '150.0'\n"
                "def test_validate_payload_missing():\n"
                "    ok, msg = app_module.validate_payload({})\n"
                "    assert ok is False\n"
                "    assert 'Missing required fields' in msg\n"
            )

        bundle = {
            "python": python_code,
            "tests": tests_code,
            "html": "",
            "css": "",
        }
        return json.dumps(bundle)

    @staticmethod
    def _is_streamlit_python(python_code: str) -> bool:
        src = str(python_code or "").lower()
        has_streamlit = (
            "import streamlit" in src
            or "from streamlit" in src
            or "st.set_page_config" in src
        )
        has_flask = (
            "from flask" in src
            or "import flask" in src
            or "flask(" in src
            or "@app.route" in src
            or "@app.get" in src
            or "@app.post" in src
        )
        return has_streamlit and not has_flask

    @staticmethod
    def _matches_expected_mode(python_code: str, mode: str) -> bool:
        src = str(python_code or "").lower()
        if mode == "ml":
            ml_markers = (
                "make_prediction",
                "predict",
                "st.form",
                "st.file_uploader",
                "st.number_input",
                "st.text_input",
                "sagemaker",
            )
            return any(marker in src for marker in ml_markers)
        if mode == "chatbot":
            chatbot_markers = (
                "st.chat_input",
                "st.chat_message",
                "get_rag",
                "ragbuilder",
                "query(",
            )
            return any(marker in src for marker in chatbot_markers)
        if mode == "recommendation":
            rec_markers = (
                "recommendation",
                "recommend",
                "suggest",
                "top",
                "top_n", 
                "predict"
            )
            return any(marker in src for marker in rec_markers)
        return True

    # Resilient Ollama + JSON parsing overrides.
    def _call_qwen_ollama(self, system: str, task: str, temp: float) -> Optional[str]:
        try:
            import ollama as _ollama                                      # type: ignore
        except ImportError:
            log.debug("ollama package not installed â€” skipping Ollama backend.")
            return None

        qwen_cfg = self.qwen_cfg
        max_tok = qwen_cfg.get("max_tokens", 4096)
        candidates = self._resolve_ollama_candidates(qwen_cfg)
        available_models = self._list_ollama_models(_ollama)
        attempt_order = self._build_ollama_attempt_order(candidates, available_models)

        if not attempt_order:
            log.warning("No Ollama model candidates are configured.")
            return None

        last_error: Optional[Exception] = None
        for ollama_model in attempt_order:
            try:
                response = _ollama.chat(
                    model=ollama_model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user",   "content": task},
                    ],
                    options={"temperature": temp, "num_predict": max_tok},
                )
                content = self._extract_ollama_content(response)
                if content.strip():
                    log.info(
                        "Qwen via Ollama (%s) â€” %d chars returned.",
                        ollama_model,
                        len(content),
                    )
                    return content

                log.warning("Ollama model '%s' returned empty content.", ollama_model)
            except Exception as exc:
                last_error = exc
                log.warning("Ollama call failed for model '%s': %s", ollama_model, exc)

        if available_models:
            preview = ", ".join(available_models[:10])
            log.warning("Ollama available models (first 10): %s", preview)
        if last_error:
            log.warning("All Ollama model attempts failed. Last error: %s", last_error)
        return None

    @staticmethod
    def _resolve_ollama_candidates(qwen_cfg: dict) -> List[str]:
        configured = qwen_cfg.get("ollama_model_candidates", [])
        candidates: List[str] = []

        if isinstance(configured, str):
            candidates.extend([p.strip() for p in configured.split(",") if p.strip()])
        elif isinstance(configured, list):
            candidates.extend([str(p).strip() for p in configured if str(p).strip()])

        primary = str(qwen_cfg.get("ollama_model", "qwen2.5-coder:3b")).strip()
        defaults = [
            primary,
            "qwen2.5-coder:3b",
            "qwen2.5:3b",
            "qwen2.5-coder:1.5b",
            "deepseek-coder:1.3b",
            "phi3.5:3.8b",
            "llama3.2:3b",
        ]

        ordered: List[str] = []
        seen: set[str] = set()
        for item in [*candidates, *defaults]:
            model = str(item or "").strip()
            if not model:
                continue
            key = model.lower()
            if key in seen:
                continue
            seen.add(key)
            ordered.append(model)
        return ordered

    @staticmethod
    def _list_ollama_models(ollama_module) -> List[str]:
        try:
            listing = ollama_module.list()
        except Exception as exc:
            log.debug("Could not list Ollama models: %s", exc)
            return []

        models = []
        if isinstance(listing, dict):
            raw_models = listing.get("models", [])
            if isinstance(raw_models, list):
                for entry in raw_models:
                    if isinstance(entry, dict):
                        name = entry.get("name") or entry.get("model")
                    else:
                        name = getattr(entry, "name", None) or getattr(entry, "model", None)
                    if name:
                        models.append(str(name).strip())
        else:
            raw_models = getattr(listing, "models", None) or []
            for entry in raw_models:
                name = getattr(entry, "name", None) or getattr(entry, "model", None)
                if name:
                    models.append(str(name).strip())
        return [m for m in models if m]

    @staticmethod
    def _build_ollama_attempt_order(candidates: List[str], available_models: List[str]) -> List[str]:
        if not available_models:
            return candidates

        available_set = {m.lower() for m in available_models}
        ordered: List[str] = []
        seen: set[str] = set()

        # 1) Try configured models that are installed.
        for candidate in candidates:
            key = candidate.lower()
            if key in available_set and key not in seen:
                ordered.append(candidate)
                seen.add(key)

        # 2) Then try any installed code-centric model.
        preferred_tokens = ("coder", "qwen", "deepseek", "phi", "llama3")
        for model in available_models:
            key = model.lower()
            if key in seen:
                continue
            if any(size in key for size in ["7b", "6.7b", "8b", "14b", "32b", "33b"]):
                continue
            if any(token in key for token in preferred_tokens):
                ordered.append(model)
                seen.add(key)

        # 3) Finally keep configured fallbacks for tag mismatch cases.
        for candidate in candidates:
            key = candidate.lower()
            if key not in seen:
                ordered.append(candidate)
                seen.add(key)

        return ordered

    @staticmethod
    def _extract_ollama_content(response) -> str:
        if isinstance(response, dict):
            message = response.get("message")
            if isinstance(message, dict):
                return str(message.get("content", "") or "")
            return str(response.get("response", "") or "")

        message = getattr(response, "message", None)
        if message is not None:
            content = getattr(message, "content", None)
            if content is not None:
                return str(content)

        content = getattr(response, "response", None)
        if content is not None:
            return str(content)
        return str(response or "")

    @staticmethod
    def _parse_json_response(raw: str) -> CodeBundle:
        cleaned = CodeGenFactory._strip_markdown_fences(str(raw or ""))

        bundle = CodeGenFactory._safe_json_load(cleaned)
        if bundle is None:
            candidate = CodeGenFactory._extract_json_object(cleaned)
            bundle = CodeGenFactory._safe_json_load(candidate)

        if not isinstance(bundle, dict):
            raise ValueError(f"No JSON object found in LLM response:\n{cleaned[:400]}")

        return {
            "python": str(bundle.get("python", "") or ""),
            "tests":  str(bundle.get("tests", "") or ""),
            "html":   str(bundle.get("html", "") or ""),
            "css":    str(bundle.get("css", "") or ""),
        }

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        text = re.sub(r"```(?:json|python|text)?\s*", "", text, flags=re.IGNORECASE)
        return text.strip().rstrip("```").strip()

    @staticmethod
    def _safe_json_load(payload: str) -> Optional[dict]:
        payload = (payload or "").strip()
        if not payload:
            return None
        try:
            data = json.loads(payload)
            return data if isinstance(data, dict) else None
        except Exception:
            pass
        try:
            data = ast.literal_eval(payload)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    @staticmethod
    def _extract_json_object(text: str) -> str:
        text = (text or "").strip()
        start = text.find("{")
        if start < 0:
            return ""

        depth = 0
        in_string = False
        escaping = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_string:
                if escaping:
                    escaping = False
                elif ch == "\\":
                    escaping = True
                elif ch == "\"":
                    in_string = False
                continue

            if ch == "\"":
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start: idx + 1]
        return ""
