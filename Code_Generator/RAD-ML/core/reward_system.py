"""
core/reward_system.py — RL Reward Scoring (Streamlit edition)
=============================================================
Evaluates each code-generation attempt and returns a float reward
that can be fed back into a learning agent or used for logging.

Scoring rubric (cumulative, max ~10.0 per attempt):
  +4.0  Streamlit app started without crash
  +2.0  Generated Python passes AST syntax check
  +1.0  Required imports present (streamlit + domain library)
  +1.0  Expected Streamlit widget pattern found
  +1.0  try-except error handling block present
  +1.0  st.session_state usage (good Streamlit practice)
  -5.0  App crashed / failed to start
  -2.0  Flask contamination detected (wrong framework)
  -0.5  Per-attempt penalty (discourages wasted cycles)
"""

from __future__ import annotations

import ast
import logging
from typing import Optional

log = logging.getLogger(__name__)


class RewardSystem:
    """Compute a scalar reward for one Streamlit generation attempt."""

    def score(
        self,
        code: str,
        app_started: bool,
        error: Optional[str],
        attempt: int,
        html: str = "",   # kept for API compatibility; unused in Streamlit mode
        mode: str = "",
    ) -> float:
        """
        Args:
            code:        Generated Python (app.py) content.
            app_started: True if the Streamlit process started cleanly.
            error:       Error string if generation/launch failed, else None.
            attempt:     Attempt number (1-indexed).
            html:        Unused in Streamlit mode (kept for backward compat).
            mode:        "chatbot" | "ml" | "recommendation"

        Returns:
            Float reward signal.
        """
        reward = 0.0

        # Per-attempt decay penalty
        reward -= 0.5 * (attempt - 1)

        if not app_started or not code:
            reward -= 5.0
            log.debug("Reward: app crashed / empty code → -5.0")
            return round(reward, 4)

        # Flask contamination check — heavy penalty
        if self._has_flask(code):
            reward -= 2.0
            log.warning("Reward: Flask contamination detected in Streamlit app → -2.0")

        # Streamlit app started
        reward += 4.0

        # Syntax validity
        if self._syntax_ok(code):
            reward += 2.0
        else:
            reward -= 1.0

        # Required imports
        if self._has_required_imports(code, mode):
            reward += 1.0

        # Expected Streamlit widget pattern
        if self._has_streamlit_widget_pattern(code, mode):
            reward += 1.0

        # Error handling
        if self._has_error_handling(code):
            reward += 1.0

        # Good Streamlit practice: session_state usage (chatbot) or form usage (ml)
        if self._has_streamlit_best_practice(code, mode):
            reward += 1.0

        log.info("Attempt %d reward → %.3f", attempt, reward)
        return round(reward, 4)

    # ── Sub-checks ────────────────────────────────────────────────────────────
    @staticmethod
    def _syntax_ok(code: str) -> bool:
        try:
            ast.parse(code)
            return True
        except SyntaxError as exc:
            log.debug("Syntax error in generated code: %s", exc)
            return False

    @staticmethod
    def _has_flask(code: str) -> bool:
        src = str(code or "").lower()
        return any(p in src for p in ("from flask", "import flask", "@app.route", "render_template"))

    @staticmethod
    def _has_required_imports(code: str, mode: str) -> bool:
        src = str(code or "").lower()
        has_st = "import streamlit" in src or "from streamlit" in src
        if mode == "ml" or mode == "recommendation":
            return has_st and ("boto3" in src or "sagemaker" in src)
        if mode == "chatbot":
            return has_st and ("llama_index" in src or "chroma" in src or "ragbuilder" in src)
        return has_st

    @staticmethod
    def _has_streamlit_widget_pattern(code: str, mode: str) -> bool:
        src = str(code or "").lower()
        if mode == "chatbot":
            return "st.chat_input" in src or "st.chat_message" in src
        if mode == "recommendation":
            return "st.columns" in src or "st.container" in src
        # ml
        return "st.form" in src or "st.text_input" in src or "st.number_input" in src

    @staticmethod
    def _has_error_handling(code: str) -> bool:
        return "try:" in code and "except" in code

    @staticmethod
    def _has_streamlit_best_practice(code: str, mode: str) -> bool:
        src = str(code or "").lower()
        if mode == "chatbot":
            return "st.session_state" in src
        return "st.form" in src or "st.tabs" in src

    # ── Batch Evaluation ──────────────────────────────────────────────────────
    def evaluate_history(self, log_entries: list[dict]) -> dict:
        if not log_entries:
            return {}
        rewards = [e.get("reward", 0.0) for e in log_entries]
        best = max(range(len(rewards)), key=lambda i: rewards[i])
        return {
            "attempts": len(rewards),
            "total_reward": round(sum(rewards), 4),
            "avg_reward": round(sum(rewards) / len(rewards), 4),
            "best_attempt": log_entries[best].get("attempt"),
            "best_reward": rewards[best],
        }
