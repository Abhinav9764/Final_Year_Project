"""
generator/code_verifier.py — Gemini API Code Verifier
=======================================================
Sends generated Python (app.py) to the Gemini API for a logic + syntax check.
Gemini returns either:
  - The corrected code (if issues were found)
  - The original code with an "OK" prefix (if no issues found)

The verifier applies a fast AST pre-check before calling the API to skip
trivial syntax errors and save API usage.
"""

from __future__ import annotations

import ast
import logging
import re
from typing import Optional

log = logging.getLogger(__name__)


# ── Gemini SDK (pip install google-generativeai) ──────────────────────────────
try:
    import google.generativeai as genai                                  # type: ignore
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    log.warning("google-generativeai not installed — CodeVerifier will skip API verification.")


VERIFICATION_SYSTEM = """\
You are an expert Python code reviewer for generated application files.
You will be given one generated Python file (for example app.py or test_app.py).

Your job:
1. Check for syntax errors (use your internal parser).
2. Check for logic errors (for example missing imports, undefined variables, broken logic).
3. Preserve the framework and style already used in the file (Streamlit/Flask/pytest/unittest).
4. If the code is correct, reply with exactly: OK
5. If the code has issues, reply with ONLY the corrected Python code and nothing else.
   No explanations, no markdown, just the fixed Python code.
"""


class CodeVerifier:
    """
    Verifies and auto-corrects generated Python code via Gemini API.

    Args:
        cfg: Full config dict (reads [gemini] section).
    """

    def __init__(self, cfg: dict):
        gemini_cfg = cfg.get("gemini", {})
        self.api_key   = gemini_cfg.get("api_key", "")
        self.model_name = gemini_cfg.get("model", "gemini-1.5-pro-latest")
        self._model    = None
        self._disabled = False

    # ── Public API ────────────────────────────────────────────────────────────
    def verify(self, python_code: str, artifact_name: str = "app.py") -> str:
        """
        Verify and optionally correct the given Python code.

        Args:
            python_code: Content of the generated Python file.
            artifact_name: File label passed to Gemini for context.

        Returns:
            Corrected (or unchanged) Python code string.
        """
        # Fast local syntax check first
        syntax_error = self._local_syntax_check(python_code)
        if syntax_error:
            log.warning("Local syntax error detected before Gemini call: %s", syntax_error)

        if self._disabled:
            return python_code

        if not GEMINI_AVAILABLE or not self.api_key or "YOUR" in self.api_key:
            log.info("Gemini verification skipped (API unavailable/unconfigured).")
            return python_code

        try:
            corrected = self._call_gemini(python_code, artifact_name)
            if corrected.strip().upper().startswith("OK"):
                log.info("✓ Gemini verified code — no issues found.")
                return python_code
            else:
                log.info("✓ Gemini applied corrections to generated code.")
                return corrected
        except Exception as exc:
            self._disabled = True
            log.warning("Gemini verification failed: %s. Disabling verifier for this run.", exc)
            return python_code

    def verify_html(self, html_code: str) -> str:
        """
        Light structural check on the HTML (no API call).
        Ensures required elements exist: <form>/<input> or chat structure.
        """
        checks = {
            "has_form_or_chat": "<form" in html_code or "chat" in html_code.lower(),
            "has_script":       "<script" in html_code,
            "has_body":         "<body" in html_code,
        }
        failed = [k for k, v in checks.items() if not v]
        if failed:
            log.warning("HTML structural check failed: %s", failed)
        return html_code   # return as-is; Gemini only fixes Python

    # ── Internal ──────────────────────────────────────────────────────────────
    @staticmethod
    def _local_syntax_check(code: str) -> Optional[str]:
        try:
            ast.parse(code)
            return None
        except SyntaxError as exc:
            return str(exc)

    def _call_gemini(self, python_code: str, artifact_name: str) -> str:
        if self._model is None:
            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=VERIFICATION_SYSTEM,
            )

        prompt = (
            f"Review this generated Python file ({artifact_name}). "
            f"Keep the same framework/style as already present.\n\n"
            f"```python\n{python_code}\n```"
        )
        response = self._model.generate_content(prompt)
        raw = response.text or ""

        # Strip markdown fences if Gemini added them
        raw = re.sub(r"```(?:python)?\s*", "", raw).strip().rstrip("```").strip()
        return raw
