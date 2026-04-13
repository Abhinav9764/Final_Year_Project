"""
generator/prompt_spec_extractor.py
====================================
Universal Prompt → IntentSpec extractor.

Converts any user prompt into a fully-structured IntentSpec JSON:

{
  "problem_summary": "string",
  "task_type": "classification|regression|api|script|algorithm|web_app|data_pipeline|unknown",
  "inputs":  [{"name":"","type":"","required":true,"description":""}],
  "outputs": [{"name":"","type":"","description":""}],
  "constraints":       ["string"],
  "assumptions":       ["string"],
  "edge_cases":        ["string"],
  "success_criteria":  ["string"],
  "missing_info":      ["string"]
}

Enrichment pipeline
-------------------
1. LLM (Gemini via LLMClient) extracts the initial IntentSpec from the raw prompt.
2. Google Custom Search API (optional) fetches relevant code snippets for the
   extracted problem_summary + task_type and returns them as plain-text strings.
3. If search snippets are available, a second LLM call refines / fills gaps in
   the IntentSpec using that additional context.
4. The final IntentSpec is saved to  workspace/current_app/intent_spec.json.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# IntentSpec type alias (dict with expected keys)
# ---------------------------------------------------------------------------
IntentSpec = Dict[str, Any]

# ---------------------------------------------------------------------------
# Known task types
# ---------------------------------------------------------------------------
TASK_TYPES = frozenset(
    [
        "classification",
        "regression",
        "api",
        "script",
        "algorithm",
        "web_app",
        "data_pipeline",
        "unknown",
    ]
)

# ---------------------------------------------------------------------------
# LLM extraction prompt
# ---------------------------------------------------------------------------
_EXTRACT_PROMPT = """\
You are an expert software architect and AI engineer.

Your job is to analyse the prompt below and return a structured JSON specification.

=== USER PROMPT ===
{prompt}

=== ADDITIONAL CONTEXT (from Google Search) ===
{search_context}

=== OUTPUT SCHEMA (return ONLY valid JSON — no markdown, no explanation) ===
{{
  "problem_summary":  "<1-2 sentence summary of what needs to be built>",
  "task_type": "<one of: classification | regression | api | script | algorithm | web_app | data_pipeline | unknown>",
  "inputs": [
    {{
      "name": "<field name>",
      "type": "<string | integer | float | list | dict | file | dataframe | image | unknown>",
      "required": true,
      "description": "<what this input represents>"
    }}
  ],
  "outputs": [
    {{
      "name": "<output name>",
      "type": "<string | integer | float | list | dict | file | plot | model | api_response | unknown>",
      "description": "<what this output represents>"
    }}
  ],
  "constraints":      ["<hard requirement>"],
  "assumptions":      ["<assumed fact about the domain or data>"],
  "edge_cases":       ["<potential failure mode or unusual input>"],
  "success_criteria": ["<measurable condition that proves success>"],
  "missing_info":     ["<something the prompt does NOT specify that may be needed>"]
}}

Rules:
- task_type MUST be exactly one of the values listed above.
- If the prompt describes a binary/multi-class labelling problem → "classification".
- If the prompt describes predicting a continuous value → "regression".
- If the prompt describes building an HTTP service / REST endpoint → "api".
- If the prompt describes a standalone executable script → "script".
- If the prompt describes implementing a specific algorithm (sort, search, etc.) → "algorithm".
- If the prompt describes a browser-facing application → "web_app".
- If the prompt describes an ETL/ELT or batch processing workflow → "data_pipeline".
- When unsure, use "unknown".
- inputs and outputs must have at least one item each.
- Return ONLY the JSON object — no markdown fences, no surrounding text.
"""


class PromptSpecExtractor:
    """
    Extract a structured IntentSpec from a raw user prompt.

    Parameters
    ----------
    llm_client : LLMClient
        The configured Gemini LLM client (from core/llm_client.py).
    config : dict
        Root config dict (config.yaml).  The following sub-section is used:

        google_search:
          api_key: ""   # Google Custom Search JSON API key
          cx:      ""   # Programmable Search Engine ID
          max_results: 5
          timeout_secs: 8

        workspace_dir is taken from  codegen.workspace_dir  (default
        Code_Generator/RAD-ML/workspace/current_app relative to project root).
    """

    def __init__(self, llm_client, config: dict) -> None:
        self._llm = llm_client
        self._config = config
        self._search_cfg = config.get("google_search", {}) or {}

    # ── Public API ─────────────────────────────────────────────────────────────

    def extract(self, prompt: str, *, save: bool = True) -> IntentSpec:
        """
        Full pipeline: LLM extraction → optional search enrichment → save.

        Parameters
        ----------
        prompt : str   Raw user prompt.
        save   : bool  If True, write intent_spec.json to workspace.

        Returns
        -------
        IntentSpec dict — always valid (falls back to rule-based on LLM failure).
        """
        # Step 1: initial spec without search context
        spec = self._extract_with_llm(prompt, search_snippets=[])

        # Step 2: enrich with Google Search snippets (may be empty)
        snippets = self.enrich_with_search(spec)

        # Step 3: if snippets found, refine the spec with extra context
        if snippets:
            logger.info("Re-running LLM with %d search snippets for enrichment.", len(snippets))
            spec = self._extract_with_llm(prompt, search_snippets=snippets)

        # Step 4: persist to disk
        if save:
            self._save(spec)

        logger.info(
            "IntentSpec extracted: task_type=%s  inputs=%d  outputs=%d",
            spec.get("task_type"),
            len(spec.get("inputs", [])),
            len(spec.get("outputs", [])),
        )
        return spec

    def enrich_with_search(self, intent_spec: IntentSpec) -> List[str]:
        """
        Query Google Custom Search API for code snippets relevant to the spec.

        Returns a list of plain-text snippet strings (may be empty if the API
        key is not configured or if the request fails).
        """
        api_key = self._search_cfg.get("api_key", "")
        cx = self._search_cfg.get("cx", "")
        max_results = int(self._search_cfg.get("max_results", 5))
        timeout = int(self._search_cfg.get("timeout_secs", 8))

        if not api_key or "YOUR" in api_key or not cx or "YOUR" in cx:
            logger.debug("Google Search API key not configured — skipping enrichment.")
            return []

        problem = intent_spec.get("problem_summary", "")
        task_type = intent_spec.get("task_type", "")
        query = f"python {task_type} code example {problem}"[:150]

        url = (
            "https://www.googleapis.com/customsearch/v1?"
            + urllib.parse.urlencode(
                {
                    "key": api_key,
                    "cx": cx,
                    "q": query,
                    "num": min(max_results, 10),
                    "safe": "active",
                }
            )
        )

        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            items = data.get("items", [])
            snippets: List[str] = []
            for item in items[:max_results]:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                if snippet.strip():
                    snippets.append(f"# {title}\n{snippet}\n# Source: {link}")
            logger.info("Google Search returned %d snippets for query: %s", len(snippets), query[:80])
            return snippets
        except Exception as exc:
            logger.warning("Google Search enrichment failed: %s", exc)
            return []

    # ── Internal helpers ────────────────────────────────────────────────────────

    def _extract_with_llm(self, prompt: str, search_snippets: List[str]) -> IntentSpec:
        """Call the LLM and parse the returned JSON. Falls back on failure."""
        search_context = (
            "\n\n---\n\n".join(search_snippets)
            if search_snippets
            else "(no additional search context available)"
        )
        full_prompt = _EXTRACT_PROMPT.format(
            prompt=prompt.strip(),
            search_context=search_context,
        )
        try:
            raw = self._llm.generate(full_prompt)
            spec = self._parse_json(raw)
            spec = self._validate_and_fix(spec, prompt)
            return spec
        except Exception as exc:
            logger.warning("LLM spec extraction failed (%s) — using rule-based fallback.", exc)
            return self._fallback_spec(prompt)

    @staticmethod
    def _parse_json(text: str) -> IntentSpec:
        """Strip markdown fences and parse JSON."""
        text = re.sub(r"^```[a-z]*\n?", "", text.strip(), flags=re.MULTILINE)
        text = re.sub(r"\n?```$", "", text.strip(), flags=re.MULTILINE)
        return json.loads(text.strip())

    @staticmethod
    def _validate_and_fix(spec: dict, prompt: str) -> IntentSpec:
        """
        Ensure all required keys exist with the right types.
        Fill in sensible defaults for any missing / malformed fields.
        """
        required_str = ("problem_summary", "task_type")
        required_list = (
            "inputs", "outputs", "constraints",
            "assumptions", "edge_cases", "success_criteria", "missing_info",
        )

        for key in required_str:
            if not isinstance(spec.get(key), str) or not spec[key].strip():
                if key == "problem_summary":
                    spec[key] = prompt[:120]
                elif key == "task_type":
                    spec[key] = "unknown"

        # Coerce task_type to a known value
        if spec.get("task_type") not in TASK_TYPES:
            spec["task_type"] = "unknown"

        for key in required_list:
            if not isinstance(spec.get(key), list):
                spec[key] = []

        # Ensure at least one input / output item
        if not spec["inputs"]:
            spec["inputs"] = [
                {"name": "input_data", "type": "unknown", "required": True, "description": "Primary input"}
            ]
        if not spec["outputs"]:
            spec["outputs"] = [
                {"name": "output", "type": "unknown", "description": "Primary output"}
            ]

        # Normalise input items
        for item in spec["inputs"]:
            if not isinstance(item, dict):
                continue
            item.setdefault("name", "unnamed_input")
            item.setdefault("type", "unknown")
            item.setdefault("required", True)
            item.setdefault("description", "")

        # Normalise output items
        for item in spec["outputs"]:
            if not isinstance(item, dict):
                continue
            item.setdefault("name", "unnamed_output")
            item.setdefault("type", "unknown")
            item.setdefault("description", "")

        return spec

    @staticmethod
    def _fallback_spec(prompt: str) -> IntentSpec:
        """
        Rule-based fallback when LLM completely fails.
        Infers task_type from simple keyword matching.
        """
        pl = prompt.lower()

        if any(k in pl for k in ("classify", "classification", "detect", "predict label", "spam")):
            task_type = "classification"
        elif any(k in pl for k in ("predict", "forecast", "regression", "estimate price", "price")):
            task_type = "regression"
        elif any(k in pl for k in ("api", "rest", "endpoint", "http", "webhook", "fastapi", "flask")):
            task_type = "api"
        elif any(k in pl for k in ("script", "automate", "batch", "cron", "cli")):
            task_type = "script"
        elif any(k in pl for k in ("algorithm", "sort", "search", "graph", "dynamic programming")):
            task_type = "algorithm"
        elif any(k in pl for k in ("web app", "website", "dashboard", "ui", "frontend", "streamlit")):
            task_type = "web_app"
        elif any(k in pl for k in ("pipeline", "etl", "elt", "data flow", "ingest", "transform")):
            task_type = "data_pipeline"
        else:
            task_type = "unknown"

        return {
            "problem_summary": prompt[:120],
            "task_type": task_type,
            "inputs": [
                {"name": "input_data", "type": "unknown", "required": True, "description": "Primary input"}
            ],
            "outputs": [
                {"name": "output", "type": "unknown", "description": "Primary output"}
            ],
            "constraints": [],
            "assumptions": ["Inferred by rule-based fallback due to LLM failure"],
            "edge_cases": ["Invalid or missing input"],
            "success_criteria": ["Produces valid output without errors"],
            "missing_info": ["Full prompt details could not be parsed by LLM"],
        }

    def _save(self, spec: IntentSpec) -> Optional[Path]:
        """Persist the spec as intent_spec.json in the workspace directory."""
        try:
            from pathlib import Path as _Path

            workspace_str = self._config.get("codegen", {}).get(
                "workspace_dir", "Code_Generator/RAD-ML/workspace/current_app"
            )
            workspace = _Path(workspace_str)
            if not workspace.is_absolute():
                # Resolve relative to project root (two levels up from this file)
                project_root = _Path(__file__).resolve().parent.parent.parent.parent
                workspace = project_root / workspace
            workspace.mkdir(parents=True, exist_ok=True)
            out = workspace / "intent_spec.json"
            out.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info("IntentSpec saved → %s", out)
            return out
        except Exception as exc:
            logger.warning("Could not save intent_spec.json: %s", exc)
            return None
