"""
generator/code_gen_factory.py — LLM Code Generator (Streamlit-only)
====================================================================
Builds the prompt and calls the configured LLM to generate a complete
Streamlit application.  No Flask, no HTML templates, no CSS files are
produced — the only output artifact is a self-contained app.py and a
matching test_app.py.

LLM backend priority (Qwen path):
  1. HuggingFace Hub Inference API   — free tier, public models
  2. Ollama local server             — fully offline
  3. Offline stub                    — Streamlit base template fallback
"""

from __future__ import annotations

import ast
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)
try:
    from generator.base_streamlit import (
        STREAMLIT_APP_CHATBOT,
        STREAMLIT_APP_ML,
        STREAMLIT_APP_RECOMMENDATION,
        STREAMLIT_APP_TEXT_CLASSIFICATION,
    )
except ImportError:
    log.warning("Could not import base_streamlit templates. Stub generation will be limited.")
    STREAMLIT_APP_CHATBOT = ""
    STREAMLIT_APP_ML = ""
    STREAMLIT_APP_RECOMMENDATION = ""
    STREAMLIT_APP_TEXT_CLASSIFICATION = ""

# Self-learning imports
try:
    from cg_brain.code_memory import CodeExperienceMemory
    from generator.llm_judge import LLMJudge
except ImportError:
    log.warning("Self-learning modules not available. Code memory and LLM judge disabled.")
    CodeExperienceMemory = None  # type: ignore
    LLMJudge = None  # type: ignore

# A CodeBundle now carries "python", "tests", and "developer_script".
# "html" and "css" are obsolete but kept for strict backward compatibility.
CodeBundle = Dict[str, str]  # {"python": ..., "tests": ..., "developer_script": ..., "html": "", "css": ""}

WORKSPACE_APP_DIR = Path("workspace/current_app")


class CodeGenFactory:
    """
    Calls DeepSeek or Qwen with the structured prompt template and writes
    the generated Streamlit app to the workspace.

    Args:
        llm: Optional pre-configured LLM client.
        cfg: Full config dict.
    """

    def __init__(self, llm=None, cfg: Optional[dict] = None):
        # Support both legacy CodeGenFactory(cfg) and newer CodeGenFactory(llm, cfg).
        if cfg is None and isinstance(llm, dict):
            cfg = llm
            llm = None

        self.cfg = cfg or {}
        self.llm = llm or self._build_default_llm(self.cfg)
        self.primary_llm = self.cfg.get("primary_llm", "qwen")
        self.deepseek_cfg = self.cfg.get("deepseek", {})
        self.qwen_cfg = self.cfg.get("qwen", {})
        self._qwen_backend: Optional[str] = None  # determined lazily
        self._current_engine_meta: dict = {}

        # Self-learning components
        self._code_memory: Optional[CodeExperienceMemory] = None
        self._llm_judge: Optional[LLMJudge] = None
        self._last_attempt_id: Optional[str] = None

        if CodeExperienceMemory is not None:
            try:
                self._code_memory = CodeExperienceMemory(cfg)
                log.info("CodeExperienceMemory initialized")
            except Exception as e:
                log.warning("Failed to initialize CodeExperienceMemory: %s", e)

        if LLMJudge is not None:
            try:
                self._llm_judge = LLMJudge(cfg)
                log.info("LLMJudge initialized")
            except Exception as e:
                log.warning("Failed to initialize LLMJudge: %s", e)

    @staticmethod
    def _build_default_llm(cfg: dict):
        try:
            from core.llm_client import LLMClient

            return LLMClient(cfg)
        except Exception as exc:
            log.warning("Falling back to stub-only code generation because LLM init failed: %s", exc)
            return None

    # ── Public API ────────────────────────────────────────────────────────────
    def generate(
        self,
        mode: str,
        engine_meta: dict,
        data_source_info: dict,
        user_prompt: str,
        anti_patterns: str = "",
        prev_error: Optional[str] = None,
    ) -> CodeBundle:
        """
        Build prompt → call LLM → parse JSON → return CodeBundle.

        The LLM is instructed to return ONLY Streamlit code.  If the output
        fails validation it falls back to the offline Streamlit stub.

        Self-learning integration:
        - Retrieves anti-patterns from CodeExperienceMemory
        - Evaluates generated code with LLMJudge
        - Records success/failure for DPO dataset
        """
        # Step 1: Get anti-patterns from code memory (if available)
        memory_anti_patterns = ""
        if self._code_memory and not anti_patterns:
            memory_anti_patterns = self._code_memory.get_anti_patterns(mode, user_prompt)
            if memory_anti_patterns:
                log.info("Retrieved anti-patterns from code memory")

        # Combine anti-patterns
        combined_anti_patterns = memory_anti_patterns or anti_patterns

        system_prompt = self._build_system_prompt()
        task_prompt = self._build_task_prompt(
            mode, engine_meta, data_source_info, user_prompt, combined_anti_patterns, prev_error
        )
        self._current_engine_meta = engine_meta

        # Enforce local Ollama (Qwen) as the primary engine for Code Generation
        # (Based on the new SLM-first architectural directive)
        llm_key = "qwen_ollama"
        temp = self._get_temperature(llm_key)
        try:
            full_resp = self._call_llm(llm_key, system_prompt, task_prompt, temp)
        except Exception as llm_exc:
            log.warning(
                "All LLM providers unavailable (%s). Falling back to offline stub.", llm_exc
            )
            return self._parse_json_response(self._stub_bundle_json(mode, user_prompt))

        features: List[str] = engine_meta.get("features", [])

        try:
            bundle = self._parse_json_response(full_resp)
        except Exception as exc:
            log.warning("Failed to parse LLM output as JSON (%s). Using stub.", exc)
            bundle = self._parse_json_response(self._stub_bundle_json(mode, user_prompt))

        python_code = bundle.get("python", "")
        if not python_code.strip():
            log.warning("Generated bundle missing python code. Using stub.")
            bundle = self._parse_json_response(self._stub_bundle_json(mode, user_prompt))
        elif not self._is_streamlit_python(python_code):
            log.warning("Generated code is not valid Streamlit. Using stub.")
            bundle = self._parse_json_response(self._stub_bundle_json(mode, user_prompt))
        elif not self._matches_expected_mode(
            python_code,
            mode,
            prompt_task_type=str(engine_meta.get("task_type", "")).lower(),
            user_prompt=user_prompt,
        ):
            log.warning("Generated code does not match mode '%s'. Using stub.", mode)
            bundle = self._parse_json_response(self._stub_bundle_json(mode, user_prompt))
        elif not self._validate_prompt_alignment(python_code, user_prompt, features):
            log.warning("Generated code does not align with prompt. Using contextual stub.")
            bundle = self._parse_json_response(self._stub_bundle_json(mode, user_prompt))

        # Ensure html/css are always empty — Streamlit handles its own UI
        bundle["html"] = ""
        bundle["css"] = ""
        if "developer_script" not in bundle:
            bundle["developer_script"] = "# No developer script generated by SLM."

        # Step 2: Evaluate with LLM Judge (if available)
        if self._llm_judge:
            try:
                prompt_spec = {
                    "task_type": mode,
                    "task": user_prompt,
                    "prompt": user_prompt,
                }
                # Create a combined code string for evaluation
                eval_code = bundle.get("python", "") + "\n\n" + bundle.get("developer_script", "")
                judge_result = self._llm_judge.evaluate_code(eval_code, prompt_spec)
                log.info("LLM Judge score: %d/10 - %s", judge_result["score"],
                         "PASSED" if judge_result["passed"] else "FAILED")

                # Step 3: Record experience based on judge result
                if self._code_memory:
                    if judge_result["passed"]:
                        self._code_memory.record_success_and_save_dpo(
                            prompt_spec, eval_code, self._last_attempt_id
                        )
                    else:
                        self._last_attempt_id = self._code_memory.record_failure(
                            prompt_spec, eval_code,
                            f"LLM Judge score {judge_result['score']}/10",
                            judge_result["critique"]
                        )
            except Exception as e:
                log.warning("LLM Judge evaluation failed: %s", e)

        log.info(
            "Code bundle generated — py=%d chars  tests=%d chars",
            len(bundle.get("python", "")),
            len(bundle.get("tests", "")),
        )
        return bundle

    def generate_all(self, spec: dict, plan: dict) -> Dict[str, Path]:
        """Compatibility wrapper for legacy tests."""
        try:
            bundle = self.generate(
            mode=spec.get("task_type", "ml"),
            engine_meta=spec,
            data_source_info={},
            user_prompt=spec.get("task", ""),
        )
        except Exception:
            # For Test compatibility - return a stub if generation fails
            bundle = self._parse_json_response(self._stub_bundle_json(spec.get("task_type", "ml"), spec.get("task", "")))
            self.write_to_workspace(bundle)

        return {
            "app.py": WORKSPACE_APP_DIR / "app.py",
            "test_app.py": WORKSPACE_APP_DIR / "test_app.py",
        }


    def write_to_workspace(self, bundle: CodeBundle, app_dir: Path = WORKSPACE_APP_DIR) -> None:
        """
        Write app.py and test_app.py to workspace/current_app/.
        Also writes a local config.yaml to persist metadata for the UI.
        """
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / "app.py").write_text(bundle.get("python", ""), encoding="utf-8")
        (app_dir / "test_app.py").write_text(bundle.get("tests", ""), encoding="utf-8")
        
        dev_script = bundle.get("developer_script", "").strip()
        if dev_script and dev_script != "# No developer script generated by SLM.":
            (app_dir / "train_pipeline.py").write_text(dev_script, encoding="utf-8")
        
        # Write specialized config.yaml for the app UI
        if self._current_engine_meta:
            try:
                import yaml
                app_cfg = {
                    "aws": {
                        "region": self.cfg.get("aws", {}).get("region", "us-east-1"),
                        "sagemaker_endpoint_name": self._current_engine_meta.get("endpoint"),
                    },
                    "ml_features": self._current_engine_meta.get("features", []),
                    "output_description": self._current_engine_meta.get("output_description", ""),
                    "target_param": self._current_engine_meta.get("target_param", "Prediction"),
                }
                with open(app_dir / "config.yaml", "w", encoding="utf-8") as f:
                    yaml.safe_dump(app_cfg, f)
            except Exception as exc:
                log.warning("Failed to write app-specific config.yaml: %s", exc)

        log.info("Workspace written: app.py, test_app.py, config.yaml → %s", app_dir)

    # ── Prompt Builders ───────────────────────────────────────────────────────
    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "You are an expert Python developer specialising in Streamlit applications. "
            "Always respond in English only. "
            "Never use Flask, FastAPI, Django, or any other web framework. "
            "All UI must be built with Streamlit widgets only."
        )

    def _build_task_prompt(
        self,
        mode: str,
        engine_meta: dict,
        data_source_info: dict,
        user_prompt: str,
        anti_patterns: str,
        prev_error: Optional[str],
    ) -> str:
        mode_label = {
            "chatbot": "Chatbot",
            "recommendation": "Recommendation System",
        }.get(mode, "Predictive ML")

        data_source_lbl = self._format_data_source(mode, engine_meta, data_source_info)
        algorithm_lbl = self._format_algorithm(mode, engine_meta)
        features_block = self._format_features(mode, engine_meta)
        connectivity = "llama-index and chromadb" if mode == "chatbot" else "boto3"
        chat_or_form = self._form_or_chat_instruction(mode, engine_meta)
        scope_hint = self._scope_guardrail_instruction(user_prompt)
        region_hint = self._region_input_instruction(user_prompt, mode)
        metrics_hint = self._metrics_instruction(mode, user_prompt)
        graphical_metrics_block = self._graphical_metrics_requirement(user_prompt, mode)
        graphical_metrics_developer_script_hint = (
            "- After training, compute metrics and save matplotlib/seaborn plots as PNG files "
            "(e.g. `fig.savefig('metrics_report.png', dpi=150, bbox_inches='tight')`). "
            "Include bar charts, confusion matrix / scatter plots as appropriate."
            if self._detect_graphical_metrics_intent(user_prompt) else ""
        )

        prompt = f"""Task: Build a full-stack Streamlit application AND a standalone developer training script based on the following context.
DO NOT use Flask, FastAPI, or any web framework. ALL UI must be Streamlit-native.

Mode: {mode_label}
Data Source: {data_source_lbl}
Algorithm/Model: {algorithm_lbl}

User Goal: {user_prompt}
"""
        if graphical_metrics_block:
            prompt += graphical_metrics_block
        if anti_patterns:
            prompt += f"\n{anti_patterns}\n"
        # ── Inject structured input/output specs from the user's prompt ──────
        prompt_inputs = engine_meta.get("prompt_inputs", [])
        prompt_outputs = engine_meta.get("prompt_outputs", [])

        if prompt_inputs:
            prompt += "\nPrompt-Specified Inputs (the user explicitly asked for these features as input):\n"
            for inp in prompt_inputs:
                if isinstance(inp, dict):
                    name = inp.get("name", "unknown")
                    itype = inp.get("type", "unknown")
                    desc = inp.get("description", "")
                    required = inp.get("required", True)
                    prompt += f"  - {name} ({itype}, {'required' if required else 'optional'}): {desc}\n"
                else:
                    prompt += f"  - {inp}\n"
            prompt += "The generated app MUST create Streamlit input widgets for ALL of the above features.\n"

        if prompt_outputs:
            prompt += "\nExpected Outputs (what the user expects the app to return):\n"
            for out in prompt_outputs:
                if isinstance(out, dict):
                    name = out.get("name", "output")
                    otype = out.get("type", "unknown")
                    desc = out.get("description", "")
                    prompt += f"  - {name} ({otype}): {desc}\n"
                else:
                    prompt += f"  - {out}\n"
            prompt += "The generated app MUST format and display the output as described above.\n"

        out_desc = engine_meta.get("output_description")
        if out_desc:
            prompt += f"\nExpected Output Format: {out_desc}\n"

        prompt += f"""
Requirements:

Requirement 1 — app.py (Streamlit only):
   - Start with `st.set_page_config(page_title="...", layout="wide")`.
   - Inject a dark theme via `st.markdown("<style>...</style>", unsafe_allow_html=True)`.
   - Use ONLY Streamlit widgets: `st.text_input`, `st.number_input`, `st.selectbox`,
     `st.columns`, `st.tabs`, `st.form`, `st.chat_input`, `st.chat_message`, etc.
   - NEVER import or use Flask, FastAPI, render_template, jsonify, or @app.route.

   If ML or Recommendation:
     - Generate Streamlit widgets for features {features_block}.
     - Use ONLY the prompt-required inference inputs. Do not expose unrelated dataset columns.
     - If a requested business input must expand into multiple model columns, keep the UI minimal and only expose the unavoidable derived fields.
     - Data Parsing: strip non-numeric chars from string inputs (e.g. "200sq.ft" → 200.0)
       using regex before building the payload. Handle ValueError for float conversion.
     - Data Validation: show `st.error` for missing or invalid values.
     - Use `st.form` + `st.form_submit_button` for the prediction form.
     - Show results with `st.success` or a styled `st.markdown` block.
     {scope_hint}
     {region_hint}
     {metrics_hint}

   If Recommendation:
     - Display Top-N results as styled cards using `st.container` / `st.markdown`.
     - Separate input column from results column using `st.columns`.

   If Chatbot:
     - Use the LlamaIndex framework with Chroma Vector Store (data/vector_store/index).
     - Use the Ollama model for SLM generation.
     - Implement: Data → embeddings → vector DB → query → top-k retrieval → re-rank → LLM answer.
     - Use `st.chat_message` / `st.chat_input` for the conversation UI.
     - Keep chat history in `st.session_state`; render all messages each rerun.
     - Lazy-load the RAG index with `@st.cache_resource` — do NOT load at module import time.
     - Fall back gracefully if the SLM returns an empty response.
     - Resolve project root from `Path(__file__).resolve()`.

   General:
     - Connectivity: use the {connectivity} libraries.
     - Wrap prediction/inference in try-except; use `st.error("...")` on failure.
     - Use `st.spinner` while any request is in flight.
     - Include sidebar with algorithm badge, model info, and runtime metrics.
     - All text, labels, and widget titles in English only.

Requirement 2 — test_app.py:
   - Use `unittest` or `pytest`.
   - Test ONLY pure Python functions (data validation, encoding, payload building).
   - Do NOT import or call any Streamlit functions in tests.
   - For ML/Recommendation: mock SageMaker/boto3 calls.
   - For Chatbot: mock RAG retrieval.
   - If geographic input is needed, add a test that a missing region fails validation.

Requirement 3 — Layout:
   {chat_or_form}
   - For ML/Recommendation: add a "Bulk Predict" tab with `st.file_uploader` for CSV input.
   - Show a progress bar (`st.progress`) during bulk operations.
   - Display downloadable results with `st.download_button`.

Requirement 4 — train_pipeline.py (Developer Script):
   - Provide a highly readable, strictly Python standalone script (no Streamlit) that a developer could run locally to replicate the ML training/pipeline process.
   - Write standard Pandas/Scikit-learn/XGBoost code corresponding to `{algorithm_lbl}`. Include comments explaining the code architecture.
   {graphical_metrics_developer_script_hint}

Output ONLY valid JSON with exactly these keys:
{{ "python": "<app.py content>", "tests": "<test_app.py content>", "developer_script": "<train_pipeline.py content>" }}
Do NOT include any explanation, markdown fences, or text outside the JSON object."""

        if prev_error:
            prompt += (
                f"\n\nIMPORTANT — The previous attempt failed with this error. "
                f"Fix the code to resolve it:\n```\n{prev_error[:1500]}\n```"
            )
        return prompt

    # ── LLM Dispatch ──────────────────────────────────────────────────────────
    def _get_temperature(self, llm_key: str) -> float:
        cfg = self.deepseek_cfg if llm_key == "deepseek" else self.qwen_cfg
        return float(cfg.get("temperature", 0.3))

    def _call_llm(self, llm_key: str, system: str, task: str, temp: float) -> str:
        if llm_key == "qwen_ollama":
            # Force Ollama generation logic
            res = self._call_qwen_ollama(system, task, temp)
            if res: return res
            
        if self.llm and hasattr(self.llm, "generate"):
            return self.llm.generate(system + "\n" + task)
        if llm_key == "deepseek":
            return self._call_deepseek(system, task, temp)
        return self._call_qwen(system, task, temp)

    def _call_deepseek(self, system: str, task: str, temp: float) -> str:
        api_key = self.deepseek_cfg.get("api_key", "")
        model = self.deepseek_cfg.get("model", "deepseek-coder")
        max_tok = int(self.deepseek_cfg.get("max_tokens", 4096))

        # Infer mode for stub fallback
        mode_hint = self._infer_mode_hint(task)

        if not api_key or "YOUR" in api_key:
            log.warning("DeepSeek API key not set — returning stub.")
            return self._stub_bundle_json(mode_hint)

        try:
            from openai import OpenAI  # type: ignore
        except ImportError:
            log.warning("openai package missing — falling back to Qwen/stub.")
            return self._call_qwen(system, task, temp)

        try:
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": task},
                ],
                temperature=temp,
                max_tokens=max_tok,
            )
            return resp.choices[0].message.content
        except Exception as exc:
            log.warning("DeepSeek call failed: %s. Falling back to Qwen/stub.", exc)
            return self._call_qwen(system, task, temp)

    # ── Qwen — free backends ──────────────────────────────────────────────────
    def _call_qwen(self, system: str, task: str, temp: float) -> str:
        mode_hint = self._infer_mode_hint(task)

        if self._qwen_backend in (None, "hf"):
            result = self._call_qwen_hf(system, task, temp)
            if result is not None:
                self._qwen_backend = "hf"
                return result
            log.warning("HuggingFace Hub unavailable — trying Ollama.")

        if self._qwen_backend in (None, "ollama"):
            result = self._call_qwen_ollama(system, task, temp)
            if result is not None:
                self._qwen_backend = "ollama"
                return result
            log.warning("Ollama unavailable — falling back to offline stub.")

        self._qwen_backend = "stub"
        log.warning("Qwen: using offline Streamlit stub.")
        return self._stub_bundle_json(mode_hint)

    def _call_qwen_hf(self, system: str, task: str, temp: float) -> Optional[str]:
        try:
            from huggingface_hub import InferenceClient  # type: ignore
        except ImportError:
            log.debug("huggingface_hub not installed — skipping HF backend.")
            return None

        hf_token = self.qwen_cfg.get("hf_token", "")
        hf_model = self.qwen_cfg.get("hf_model", "Qwen/Qwen2.5-Coder-3B-Instruct")
        max_tok = int(self.qwen_cfg.get("max_tokens", 4096))

        try:
            client = InferenceClient(
                model=hf_model,
                token=hf_token if hf_token and "YOUR" not in hf_token else None,
            )
            response = client.chat_completion(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": task},
                ],
                max_tokens=max_tok,
                temperature=max(temp, 0.01),
            )
            content = response.choices[0].message.content
            log.info("Qwen via HuggingFace Hub (%s) — %d chars.", hf_model, len(content or ""))
            return content
        except Exception as exc:
            log.warning("HuggingFace Hub call failed: %s", exc)
            return None

    def _call_qwen_ollama(self, system: str, task: str, temp: float) -> Optional[str]:
        try:
            import ollama as _ollama  # type: ignore
        except ImportError:
            log.debug("ollama package not installed — skipping Ollama backend.")
            return None

        max_tok = int(self.qwen_cfg.get("max_tokens", 4096))
        candidates = self._resolve_ollama_candidates(self.qwen_cfg)
        available_models = self._list_ollama_models(_ollama)
        attempt_order = self._build_ollama_attempt_order(candidates, available_models)

        if not attempt_order:
            log.warning("No Ollama model candidates configured.")
            return None

        last_error: Optional[Exception] = None
        for ollama_model in attempt_order:
            try:
                response = _ollama.chat(
                    model=ollama_model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": task},
                    ],
                    options={"temperature": temp, "num_predict": max_tok},
                )
                content = self._extract_ollama_content(response)
                if content.strip():
                    log.info("Qwen via Ollama (%s) — %d chars.", ollama_model, len(content))
                    return content
                log.warning("Ollama model '%s' returned empty content.", ollama_model)
            except Exception as exc:
                last_error = exc
                log.warning("Ollama call failed for model '%s': %s", ollama_model, exc)

        if available_models:
            log.warning("Ollama available models: %s", ", ".join(available_models[:10]))
        if last_error:
            log.warning("All Ollama attempts failed. Last error: %s", last_error)
        return None

    # ── Response Parsing ──────────────────────────────────────────────────────
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
            "tests": str(bundle.get("tests", "") or ""),
            "developer_script": str(bundle.get("developer_script", "") or ""),
            "html": "",   # always empty — Streamlit handles its own UI
            "css": "",    # always empty
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
        depth, in_string, escaping = 0, False, False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_string:
                if escaping:
                    escaping = False
                elif ch == "\\":
                    escaping = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start: idx + 1]
        return ""

    # ── Validation Helpers ────────────────────────────────────────────────────
    @staticmethod
    def _is_streamlit_python(python_code: str) -> bool:
        src = str(python_code or "").lower()
        has_streamlit = (
            "import streamlit" in src
            or "from streamlit" in src
            or "st.set_page_config" in src
        )
        # Reject any Flask contamination
        has_flask = (
            "from flask" in src
            or "import flask" in src
            or "flask(" in src
            or "@app.route" in src
            or "render_template" in src
            or "jsonify" in src
        )
        return has_streamlit and not has_flask

    @staticmethod
    def _matches_expected_mode(
        python_code: str,
        mode: str,
        prompt_task_type: str = "",
        user_prompt: str = "",
    ) -> bool:
        src = str(python_code or "").lower()
        prompt_l = (user_prompt or "").lower()
        rec_prompt_markers = (
            "recommend", "recommendation", "suggest", "similar",
            "movie", "film", "top movies", "best movies",
        )
        expected_mode = mode
        if mode == "recommendation":
            expected_mode = "recommendation"
        elif prompt_task_type in ("recommendation", "clustering") and any(
            m in prompt_l for m in rec_prompt_markers
        ):
            expected_mode = "recommendation"

        markers = {
            "ml": (
                "make_prediction", "predict", "st.form", "st.file_uploader",
                "st.number_input", "st.text_input", "sagemaker",
            ),
            "chatbot": (
                "st.chat_input", "st.chat_message", "get_rag", "ragbuilder", "query(",
            ),
            "recommendation": (
                "recommendation", "recommend", "suggest", "top_n", "predict",
            ),
        }
        return any(m in src for m in markers.get(expected_mode, ()))

    # ── Formatting Helpers ────────────────────────────────────────────────────
    @staticmethod
    def _format_data_source(mode: str, engine_meta: dict, data_source_info: dict) -> str:
        if mode == "chatbot":
            count = data_source_info.get("doc_count", "?")
            return f"Local Chroma Vector DB — {count} web documents"
        s3 = engine_meta.get("s3_uri", data_source_info.get("s3_uri", "s3://bucket/data.csv"))
        return f"S3 CSV: {s3}"

    @staticmethod
    def _format_algorithm(mode: str, engine_meta: dict) -> str:
        if mode == "chatbot":
            slm = engine_meta.get("slm_model", "Phi-3 / Ollama")
            return f"SLM ({slm}) + Chroma RAG (LlamaIndex)"
        algorithm = str(engine_meta.get("algorithm", "")).strip()
        if algorithm:
            return algorithm
        endpoint = engine_meta.get("endpoint", "rad-ml-endpoint")
        model_name = engine_meta.get("model_name", "rad-ml-model")
        return f"AWS SageMaker Endpoint ({endpoint}) — model: {model_name}"

    @staticmethod
    def _format_features(mode: str, engine_meta: dict) -> str:
        if mode not in ("ml", "recommendation"):
            return ""
        features = engine_meta.get("features")
        if not isinstance(features, list):
            features = []
        requested = engine_meta.get("requested_features")
        if not isinstance(requested, list):
            requested = []
            
        if features and requested:
            return f"model features={features}, requested inputs={requested}"
        return str(features) if features else "['feature_1', 'feature_2', ...]"

    @staticmethod
    def _form_or_chat_instruction(mode: str, engine_meta: dict) -> str:
        if mode == "chatbot":
            return (
                "- Build a Streamlit chat interface using `st.chat_message` and `st.chat_input`.\n"
                "   - Keep chat history in `st.session_state`; render all messages on each rerun.\n"
                "   - Show a spinner while generating the assistant response.\n"
                "   - Display runtime metrics (response count, avg latency) in the sidebar."
            )
        if mode == "recommendation":
            features = engine_meta.get("features")
            if not isinstance(features, list):
                features = ["user_id", "item_id"]
            feat_list = ", ".join(str(f) for f in features[:15])
            return (
                f"- Build a Streamlit recommendation interface with inputs for: {feat_list}.\n"
                "   - Use `st.columns` to separate inputs from Top-N results.\n"
                "   - Render recommendations as styled cards using `st.markdown`."
            )
        features = engine_meta.get("features")
        if not isinstance(features, list):
            features = ["feature_1", "feature_2"]
        feat_list = ", ".join(str(f) for f in features[:15])
        return (
            f"- Build a Streamlit ML form with labelled widgets for: {feat_list}.\n"
            "   - Use `st.tabs` to separate Single Predict and Bulk Predict.\n"
            "   - Use `st.form` + `st.form_submit_button` for clean submit flow.\n"
            "   - Display prediction with `st.success` or a styled markdown div."
        )

    @staticmethod
    def _scope_guardrail_instruction(user_prompt: str) -> str:
        prompt_l = (user_prompt or "").lower()
        if any(t in prompt_l for t in ("house", "housing", "real estate", "price", "rent")):
            return (
                "- Restrict inference data to property-price records only; "
                "exclude unrelated domains."
            )
        if any(t in prompt_l for t in (
            "recommend", "recommendation", "suggest", "movie", "film",
            "genre", "rating", "similar", "collaborative", "clustering",
        )):
            return (
                "- This is a RECOMMENDATION system. Display results as ranked cards "
                "with title, genre, rating and a description. Never show a raw float "
                "or numeric prediction as the main result."
            )
        return (
            "- Restrict inference data to rows directly relevant to the prompt domain."
        )

    @staticmethod
    def _region_input_instruction(user_prompt: str, mode: str) -> str:
        if mode != "ml":
            return ""
        prompt_l = (user_prompt or "").lower()
        needs_region = any(
            t in prompt_l for t in ("region", "state", "city", "location", "area", "india", "indian")
        )
        if needs_region:
            return (
                "- Add a required categorical input for the location/region field. "
                "Show `st.error` when missing and stop prediction."
            )
        return (
            "- If location-specific prediction is requested, include and validate a required region input."
        )

    @staticmethod
    def _detect_graphical_metrics_intent(user_prompt: str) -> bool:
        """
        Returns True when the user's prompt explicitly requests graphical /
        diagrammatic metric results — e.g. bar charts, confusion matrices,
        ROC curves, line plots of model performance, etc.

        Trigger keywords (case-insensitive):
          - "graphical", "graph", "diagram", "diagrammatic", "visual",
            "visualize", "chart", "plot", "bar chart", "line graph",
            "confusion matrix", "roc curve", "metric report",
            "show metrics", "metric result", "performance graph",
            "matplotlib", "seaborn"
        """
        pl = (user_prompt or "").lower()
        graphical_keywords = (
            "graphical", "graph", "diagram", "diagrammatic",
            "visual", "visualize", "visualise", "visualization", "visualisation",
            "chart", "plot", "bar chart", "line graph", "pie chart",
            "confusion matrix", "roc curve", "auc curve", "learning curve",
            "metric report", "metric result", "metrics report",
            "show metrics", "performance graph", "performance chart",
            "matplotlib", "seaborn", "plotly",
            "graphical representation", "graphical format",
            "show the working", "working of the model",
        )
        return any(kw in pl for kw in graphical_keywords)

    @staticmethod
    def _metrics_instruction(mode: str, user_prompt: str = "") -> str:
        """
        Returns the metrics instruction string injected into the LLM task prompt.
        When the user's prompt indicates graphical/diagrammatic output intent,
        a richer directive (using matplotlib / seaborn via st.pyplot) is returned.
        """
        wants_graph = CodeGenFactory._detect_graphical_metrics_intent(user_prompt)

        if mode == "chatbot":
            base = (
                "- Show lightweight runtime metrics in the sidebar "
                "(response count, average latency ms)."
            )
            if wants_graph:
                base += (
                    "\n     - Use matplotlib to plot a bar chart of response latencies over time "
                    "and display it in the sidebar with `st.pyplot(fig, clear_figure=True)`."
                )
            return base

        if mode == "recommendation":
            base = (
                "- Display relevance score, item category, or matching confidence "
                "alongside each recommendation."
            )
            if wants_graph:
                base += (
                    "\n     - Use seaborn / matplotlib to plot a horizontal bar chart of "
                    "Top-N recommendation scores and render it with `st.pyplot(fig, clear_figure=True)`."
                )
            return base

        # ── Standard ML / regression / classification ─────────────────────────
        if wants_graph:
            return (
                "- Compute algorithm-specific metrics AND render them as graphical plots "
                "using matplotlib and seaborn (both imported at the top of app.py).\n"
                "  Specifically:\n"
                "  * For REGRESSION: compute MAE, RMSE, R² and plot a bar chart of these "
                "metric values using `matplotlib.pyplot`. Also plot a scatter plot of "
                "Actual vs Predicted values (use seaborn.scatterplot or matplotlib.pyplot.scatter).\n"
                "  * For CLASSIFICATION: compute Accuracy, Precision, Recall, F1 and plot "
                "a grouped bar chart using seaborn.barplot. Also render a Confusion Matrix "
                "using seaborn.heatmap with annotations.\n"
                "  * For CLUSTERING: plot a cluster scatter chart (PCA-reduced to 2D if needed) "
                "using seaborn.scatterplot colored by cluster label.\n"
                "  * Wrap every figure in a `fig, ax = plt.subplots(...)` block and display with "
                "`st.pyplot(fig, clear_figure=True)` inside a dedicated Streamlit tab called "
                "'📊 Metrics & Charts'.\n"
                "  * In the sidebar, also display the numeric metric values using `st.metric()`.\n"
                "  * IMPORTANT: import matplotlib.pyplot as plt and import seaborn as sns at the "
                "top of app.py alongside other imports."
            )
        return (
            "- Compute and display algorithm-specific metrics in the sidebar using `st.metric()`. "
            "For regression: MAE, RMSE, R². For classification: Accuracy, Precision, Recall, F1."
        )

    @staticmethod
    def _graphical_metrics_requirement(user_prompt: str, mode: str) -> str:
        """
        Returns an additional requirements block injected at the top of the task
        prompt when the user explicitly requests graphical/diagrammatic metrics.
        Returns an empty string when not needed.
        """
        if not CodeGenFactory._detect_graphical_metrics_intent(user_prompt):
            return ""

        chart_type_map = {
            "regression": "bar chart (MAE/RMSE/R²) + Actual vs Predicted scatter plot",
            "classification": "grouped bar chart (Accuracy/Precision/Recall/F1) + Confusion Matrix heatmap",
            "clustering": "2-D scatter plot of clusters (PCA-reduced) colored by cluster label",
        }
        mode_normalize = {
            "ml": "regression",
            "chatbot": "regression",
            "recommendation": "clustering",
            "text_classification": "classification",
        }
        resolved = mode_normalize.get(mode, mode)
        chart_desc = chart_type_map.get(resolved, "bar chart of key performance metrics")

        return (
            f"\n⚠️  GRAPHICAL METRICS REQUIREMENT (user explicitly requested this):\n"
            f"   The user wants metric results displayed as GRAPHICAL / DIAGRAMMATIC output."
            f" You MUST:\n"
            f"   1. Import `import matplotlib.pyplot as plt` and `import seaborn as sns` "
            f"at the very top of app.py.\n"
            f"   2. After obtaining model predictions, compute performance metrics and generate "
            f"a {chart_desc}.\n"
            f"   3. Render each figure using `st.pyplot(fig, clear_figure=True)` inside a "
            f"dedicated Streamlit tab labelled '📊 Metrics & Charts'.\n"
            f"   4. Additionally display numeric metric summaries in the sidebar via `st.metric()`.\n"
            f"   5. In train_pipeline.py, after training, also save all metric plots as PNG files "
            f"(e.g. `fig.savefig('metrics_report.png', dpi=150, bbox_inches='tight')`) so they "
            f"can be reviewed offline.\n"
        )

    # ── Offline Stub ──────────────────────────────────────────────────────────
    def _stub_bundle_json(self, mode: str, user_prompt: str = "") -> str:
        template_map = {
            "chatbot": STREAMLIT_APP_CHATBOT,
            "recommendation": STREAMLIT_APP_RECOMMENDATION,
            "text_classification": STREAMLIT_APP_TEXT_CLASSIFICATION,
        }
        python_code = template_map.get(mode, STREAMLIT_APP_ML) or ""

        # ── Patch FEATURES list using a reliable literal replacement ─────────
        if mode in ("ml", "recommendation") and self._current_engine_meta:
            features = self._current_engine_meta.get("features")
            if not isinstance(features, list):
                features = []
            endpoint: str = self._current_engine_meta.get("endpoint", "rad-ml-endpoint")
            
            if features and python_code:
                # Build the new FEATURES declaration
                feat_lines = ",\n".join(f'    "{f}"' for f in features)
                new_features_decl = f'FEATURES: List[str] = [\n{feat_lines}\n]'

                # Replace the exact placeholder that exists in the ML template
                old_features_decl = (
                    'FEATURES: List[str] = list(CFG.get("ml_features", [])) or [\n'
                    '    "region",\n'
                    '    "area",\n'
                    '    "bedrooms",\n'
                    '    "bathrooms",\n'
                    '    "age_of_property",\n'
                    ']'
                )
                if old_features_decl in python_code:
                    python_code = python_code.replace(old_features_decl, new_features_decl)
                else:
                    # Fallback: replace whatever FEATURES = [...] block is present
                    python_code = re.sub(
                        r'FEATURES:\s*List\[str\]\s*=.*?(?=\nFEATURE_LABELS|\ndef )',
                        new_features_decl + "\n",
                        python_code,
                        count=1,
                        flags=re.DOTALL,
                    )

            # Replace ENDPOINT_NAME with the actual endpoint
            if endpoint:
                old_endpoint = (
                    'ENDPOINT_NAME = os.environ.get(\n'
                    '    "SAGEMAKER_ENDPOINT",\n'
                    '    CFG.get("aws", {}).get("sagemaker_endpoint_name", "rad-ml-endpoint"),\n'
                    ')'
                )
                new_endpoint = f'ENDPOINT_NAME = os.environ.get("SAGEMAKER_ENDPOINT", "{endpoint}")'
                python_code = python_code.replace(old_endpoint, new_endpoint)
            
            # ── Patch OUTPUT_DESCRIPTION and TARGET_PARAM ────────────────────
            out_desc = self._current_engine_meta.get("output_description", "")
            target_p = self._current_engine_meta.get("target_param", "Prediction")
            
            if out_desc:
                old_out_desc = 'OUTPUT_DESCRIPTION = CFG.get("output_description", "")'
                new_out_desc = f'OUTPUT_DESCRIPTION = "{out_desc}"'
                python_code = python_code.replace(old_out_desc, new_out_desc)
                
            if target_p:
                old_target_p = 'TARGET_PARAM = CFG.get("target_param", "Prediction")'
                new_target_p = f'TARGET_PARAM = "{target_p}"'
                python_code = python_code.replace(old_target_p, new_target_p)

        # ── Inject prompt-derived app name / page title ──────────────────────
        if user_prompt and mode in ("ml", "recommendation", "text_classification"):
            app_name = self._derive_app_name_from_prompt(user_prompt)
            if mode == "text_classification":
                python_code = python_code.replace(
                    'page_title="RAD-ML Text Classifier"', f'page_title="{app_name}"'
                )
                python_code = python_code.replace(
                    '"📝 Text Classification"', f'"📝 {app_name}"'
                )
            elif mode == "ml":
                python_code = python_code.replace(
                    'page_title="RAD-ML Predictor"', f'page_title="{app_name}"'
                )
                python_code = python_code.replace(
                    '"## 🔮 RAD-ML Predictor"', f'"## 🔮 {app_name}"'
                )
                python_code = python_code.replace(
                    '"🔮 RAD-ML Predictor"', f'"🔮 {app_name}"'
                )
            else:  # recommendation
                python_code = python_code.replace(
                    'page_title="Movie Recommender"', f'page_title="{app_name}"'
                )
                python_code = python_code.replace(
                    '"## 🎬 RAD-ML Movie Recommender"', f'"## 🎬 {app_name}"'
                )
                python_code = python_code.replace(
                    '"## 🎬 Movie Recommender"', f'"## 🎬 {app_name}"'
                )
                # Also update the main title
                python_code = python_code.replace(
                    '"🎬 Movie Recommendation Engine"', f'"🎬 {app_name}"'
                )

        # Build matching test stubs
        if mode == "chatbot":
            tests_code = (
                "import unittest\n"
                "from unittest.mock import MagicMock, patch\n\n"
                "class TestChatbotApp(unittest.TestCase):\n"
                "    def test_generate_answer_empty_question(self):\n"
                "        import importlib, sys\n"
                "        # Import without triggering Streamlit at module level\n"
                "        with patch.dict(sys.modules, {'streamlit': MagicMock()}):\n"
                "            import app as app_module\n"
                "            result = app_module.generate_answer('')\n"
                "            self.assertIsInstance(result, str)\n"
                "            self.assertGreater(len(result), 0)\n\n"
                "    def test_generate_answer_no_rag(self):\n"
                "        with patch('app.get_rag', return_value=None):\n"
                "            import app as app_module\n"
                "            result = app_module.generate_answer('What is AI?')\n"
                "            self.assertIn('unavailable', result.lower())\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            )
        elif mode == "recommendation":
            tests_code = (
                "import unittest\n"
                "from unittest.mock import MagicMock, patch\n\n"
                "class TestRecommenderApp(unittest.TestCase):\n"
                "    def test_encode_feature_numeric(self):\n"
                "        import importlib, sys\n"
                "        with patch.dict(sys.modules, {'streamlit': MagicMock()}):\n"
                "            import app as app_module\n"
                "            self.assertEqual(app_module._encode_feature('score', '3.5'), '3.5')\n\n"
                "    def test_validate_payload_missing(self):\n"
                "        with patch.dict(__import__('sys').modules, {'streamlit': MagicMock()}):\n"
                "            import app as app_module\n"
                "            ok, msg = app_module.validate_payload({})\n"
                "            self.assertFalse(ok)\n"
                "            self.assertIn('Missing', msg)\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            )
        else:  # ml
            tests_code = (
                "import unittest\n"
                "from unittest.mock import MagicMock, patch\n\n"
                "def _mock_streamlit_module():\n"
                "    st = MagicMock()\n"
                "    st.sidebar.__enter__.return_value = st\n"
                "    st.sidebar.__exit__.return_value = False\n"
                "    tab_a = MagicMock()\n"
                "    tab_b = MagicMock()\n"
                "    tab_a.__enter__.return_value = st\n"
                "    tab_a.__exit__.return_value = False\n"
                "    tab_b.__enter__.return_value = st\n"
                "    tab_b.__exit__.return_value = False\n"
                "    st.tabs.return_value = [tab_a, tab_b]\n"
                "    col_a = MagicMock()\n"
                "    col_b = MagicMock()\n"
                "    col_a.__enter__.return_value = st\n"
                "    col_a.__exit__.return_value = False\n"
                "    col_b.__enter__.return_value = st\n"
                "    col_b.__exit__.return_value = False\n"
                "    st.columns.return_value = [col_a, col_b]\n"
                "    form_ctx = MagicMock()\n"
                "    form_ctx.__enter__.return_value = st\n"
                "    form_ctx.__exit__.return_value = False\n"
                "    st.form.return_value = form_ctx\n"
                "    spinner_ctx = MagicMock()\n"
                "    spinner_ctx.__enter__.return_value = st\n"
                "    spinner_ctx.__exit__.return_value = False\n"
                "    st.spinner.return_value = spinner_ctx\n"
                "    progress_bar = MagicMock()\n"
                "    progress_bar.progress.return_value = None\n"
                "    st.progress.return_value = progress_bar\n"
                "    st.file_uploader.return_value = None\n"
                "    st.form_submit_button.return_value = False\n"
                "    st.button.return_value = False\n"
                "    return st\n\n"
                "class TestMLApp(unittest.TestCase):\n"
                "    def setUp(self):\n"
                "        import sys\n"
                "        self._st_patcher = patch.dict(sys.modules, {'streamlit': _mock_streamlit_module()})\n"
                "        self._st_patcher.start()\n"
                "        import importlib\n"
                "        import app as app_module\n"
                "        importlib.reload(app_module)\n"
                "        self.app = app_module\n\n"
                "    def tearDown(self):\n"
                "        self._st_patcher.stop()\n\n"
                "    def test_encode_feature_numeric(self):\n"
                "        self.assertEqual(self.app._encode_feature('area', ' 1500.5 '), '1500.5')\n\n"
                "    def test_encode_feature_strips_units(self):\n"
                "        self.assertEqual(self.app._encode_feature('area', '200sq.ft'), '200.0')\n\n"
                "    def test_encode_feature_region(self):\n"
                "        val = self.app._encode_feature('region', 'north')\n"
                "        self.assertTrue(val.isdigit())\n\n"
                "    def test_validate_payload_missing(self):\n"
                "        ok, msg = self.app.validate_payload({})\n"
                "        self.assertFalse(ok)\n"
                "        self.assertIn('Missing required fields', msg)\n\n"
                "    def test_make_prediction_local_fallback(self):\n"
                "        with patch.object(self.app, 'get_sm_runtime', return_value=None):\n"
                "            result = self.app.make_prediction(['100.0', '200.0'])\n"
                "            self.assertIsInstance(result, str)\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            )

        return json.dumps({"python": python_code, "tests": tests_code, "html": "", "css": ""})

    # ── Prompt Alignment Validator ────────────────────────────────────────────
    @staticmethod
    def _validate_prompt_alignment(
        python_code: str,
        user_prompt: str,
        features: List[str],
    ) -> bool:
        """
        Returns True if the generated app plausibly matches the user's prompt.

        For RECOMMENDATION mode the check is intentionally lenient: the stub
        already contains genre/rating widgets and ranked movie cards, so we
        verify presence of those markers instead of raw feature column names.

        For standard ML mode we verify that at least one feature name from the
        dataset appears in the code.
        """
        src = (python_code or "").lower()
        prompt_l = (user_prompt or "").lower()

        # ── Recommendation prompts ────────────────────────────────────────────
        recommendation_keywords = (
            "recommend", "recommendation", "suggest", "top movies",
            "best movies", "similar",
        )
        if any(kw in prompt_l for kw in recommendation_keywords):
            # The recommendation stub always contains these markers.
            # If they're present the code is correct for the prompt.
            rec_markers = ("genre", "rating", "recommend", "catalogue", "top_n")
            if any(m in src for m in rec_markers):
                return True
            log.warning(
                "Prompt alignment: recommendation prompt but no recommendation markers in code."
            )
            return False

        # ── Chatbot prompts ───────────────────────────────────────────────────
        chatbot_keywords = ("chatbot", "chat bot", "rag", "conversation", "assistant")
        if any(kw in prompt_l for kw in chatbot_keywords):
            return "chat_input" in src or "chat_message" in src

        # ── Standard ML prompts — must have at least one feature name ─────────
        has_feature = any(f.lower() in src for f in features or [])
        if features and not has_feature:
            log.warning(
                "Prompt alignment: none of the features %s appear in generated code.", features
            )
            return False

        # Default placeholder features that should NOT appear in a fitted stub
        default_placeholders = ["age_of_property", "region", "area", "bedrooms", "bathrooms"]
        if features:
            # If we have actual features, none of the defaults should dominate
            wrong = [p for p in default_placeholders if f'"{p}"' in src]
            if wrong and not has_feature:
                log.warning(
                    "Prompt alignment: default placeholder features found %s, expected %s.",
                    wrong, features
                )
                return False
        return True

    @staticmethod
    def _derive_app_name_from_prompt(prompt: str) -> str:
        """
        Derive a clean, human-readable app title from the user's prompt.
        E.g.: 'Build a classification model to predict customer churn' -> 'Customer Churn Predictor'
        """
        prompt_l = (prompt or "").lower()
        # Common ML domain name patterns
        domain_map = [
            (["churn"], "Customer Churn Predictor"),
            (["fraud", "anomaly"], "Fraud Detection"),
            (["price", "house", "housing", "real estate"], "House Price Predictor"),
            (["salary", "income", "wage"], "Salary Predictor"),
            (["diabetes", "disease", "medical", "health"], "Medical Risk Predictor"),
            (["sentiment", "review", "opinion"], "Sentiment Analyser"),
            (["text classification", "classify text", "positive or negative", "positive or not"], "Text Classifier"),
            (["spam", "phishing", "malware"], "Spam / Threat Detector"),
            (["sales", "revenue", "demand"], "Sales Forecast"),
            (["stock", "market", "price prediction"], "Stock Price Predictor"),
            (["loan", "credit", "default"], "Loan Default Predictor"),
            (["weather", "temperature", "rainfall"], "Weather Predictor"),
            (["news", "topic"], "News Topic Classifier"),
            (["recommend", "suggestion", "collaborative"], "Recommendation Engine"),
        ]
        for keywords, name in domain_map:
            if any(kw in prompt_l for kw in keywords):
                return name
        # Generic fallback: capitalise first meaningful noun phrase
        words = re.sub(r"(build|create|make|train|generate|a|an|the|model|to|for|with|based|on|using|ml|ai)", "", prompt_l)
        words = words.strip().split()
        clean = " ".join(w.capitalize() for w in words[:4] if w)
        return clean or "RAD-ML Predictor"

    # ── Utility Helpers ───────────────────────────────────────────────────────
    @staticmethod
    def _infer_mode_hint(task: str) -> str:
        t = task.lower()
        if "chatbot" in t:
            return "chatbot"
        if "recommendation" in t or "recommend" in t:
            return "recommendation"
        text_cls_keywords = [
            "text classif", "sentiment", "positive or negative",
            "positive or not", "classify text", "classify sentence",
            "nlp classif", "language classif",
        ]
        if any(kw in t for kw in text_cls_keywords):
            return "text_classification"
        return "ml"

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
            primary, "qwen2.5-coder:3b", "qwen2.5:3b", "qwen2.5-coder:1.5b",
            "deepseek-coder:1.3b", "phi3.5:3.8b", "llama3.2:3b",
        ]
        ordered: List[str] = []
        seen: set = set()
        for item in [*candidates, *defaults]:
            model = str(item or "").strip()
            if model and model.lower() not in seen:
                seen.add(model.lower())
                ordered.append(model)
        return ordered

    @staticmethod
    def _list_ollama_models(ollama_module) -> List[str]:
        try:
            listing = ollama_module.list()
        except Exception as exc:
            log.debug("Could not list Ollama models: %s", exc)
            return []
        models: List[str] = []
        raw = (
            listing.get("models", []) if isinstance(listing, dict)
            else getattr(listing, "models", []) or []
        )
        for entry in raw:
            name = (
                entry.get("name") or entry.get("model")
                if isinstance(entry, dict)
                else getattr(entry, "name", None) or getattr(entry, "model", None)
            )
            if name:
                models.append(str(name).strip())
        return [m for m in models if m]

    @staticmethod
    def _build_ollama_attempt_order(candidates: List[str], available: List[str]) -> List[str]:
        if not available:
            return candidates
        avail_set = {m.lower() for m in available}
        ordered: List[str] = []
        seen: set = set()
        for c in candidates:
            k = c.lower()
            if k in avail_set and k not in seen:
                ordered.append(c)
                seen.add(k)
        preferred = ("coder", "qwen", "deepseek", "phi", "llama3")
        for m in available:
            k = m.lower()
            if k in seen:
                continue
            if any(size in k for size in ["7b", "6.7b", "8b", "14b", "32b", "33b"]):
                continue
            if any(t in k for t in preferred):
                ordered.append(m)
                seen.add(k)
        for c in candidates:
            k = c.lower()
            if k not in seen:
                ordered.append(c)
                seen.add(k)
        return ordered

    @staticmethod
    def _extract_ollama_content(response) -> str:
        if isinstance(response, dict):
            msg = response.get("message")
            if isinstance(msg, dict):
                return str(msg.get("content", "") or "")
            return str(response.get("response", "") or "")
        msg = getattr(response, "message", None)
        if msg is not None:
            content = getattr(msg, "content", None)
            if content is not None:
                return str(content)
        return str(getattr(response, "response", None) or response or "")
