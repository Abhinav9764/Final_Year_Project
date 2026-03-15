"""
core/reward_system.py — RL Reward Scoring
==========================================
Evaluates each code-generation attempt and returns a float reward
that is fed back into the DQN agent.

Scoring rubric (cumulative, max ~10.0 per attempt):
  +4.0  Flask app started without crash
  +2.0  Generated Python passes AST syntax check
  +1.0  Required imports present (flask, boto3 or langchain)
  +1.0  POST route defined in generated code
  +1.0  try-except error handling block present
  +1.0  HTML template references a result / message block
  -5.0  App crashed / failed to start (applied instead of above)
  -1.0  Per attempt penalty (discourages wasted cycles)
"""

from __future__ import annotations

import ast
import logging
import re
from typing import Optional

log = logging.getLogger(__name__)


class RewardSystem:
    """Compute a scalar reward for one generation attempt."""

    # ── Main Interface ────────────────────────────────────────────────────────
    def score(
        self,
        code:        str,
        app_started: bool,
        error:       Optional[str],
        attempt:     int,
        html:        str = "",
        mode:        str = "",
    ) -> float:
        """
        Args:
            code:        Generated Python (app.py) content.
            app_started: True if Flask launched without crash.
            error:       Error string if generation/launch failed, else None.
            attempt:     Attempt number (1-indexed). Used for decay penalty.
            html:        Generated HTML content (optional, for extra checks).
            mode:        "chatbot" | "ml" — can gate mode-specific rewards.

        Returns:
            Float reward signal.
        """
        reward = 0.0

        # Attempt penalty — mild decay to prefer fewer cycles
        reward -= 0.5 * (attempt - 1)

        if not app_started or not code:
            reward -= 5.0
            log.debug("Reward: app crashed/empty code → -5.0 base")
            return round(reward, 4)

        # App started successfully
        reward += 4.0

        # Syntax validity
        if self._syntax_ok(code):
            reward += 2.0
        else:
            reward -= 1.0

        # Required imports
        if self._has_required_imports(code, mode):
            reward += 1.0

        # POST route present
        if self._has_post_route(code):
            reward += 1.0

        # Error handling present
        if self._has_error_handling(code):
            reward += 1.0

        # HTML result block (if html provided)
        if html and self._html_has_result_block(html):
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
    def _has_required_imports(code: str, mode: str) -> bool:
        code_l = code.lower()
        has_flask = "import flask" in code_l or "from flask" in code_l
        if mode == "ml":
            return has_flask and ("import boto3" in code_l or "boto3" in code_l)
        elif mode == "chatbot":
            return has_flask and ("llama_index" in code_l or "chroma" in code_l)
        return has_flask

    @staticmethod
    def _has_post_route(code: str) -> bool:
        return bool(re.search(r"methods\s*=\s*\[.*'POST'.*\]", code, re.IGNORECASE))

    @staticmethod
    def _has_error_handling(code: str) -> bool:
        return "try:" in code and "except" in code

    @staticmethod
    def _html_has_result_block(html: str) -> bool:
        html_l = html.lower()
        return any(kw in html_l for kw in ["prediction", "result", "response", "chat-box", "message"])

    # ── Batch Evaluation (optional, for analysis) ─────────────────────────────
    def evaluate_history(self, log_entries: list[dict]) -> dict:
        """
        Summarise a list of log dicts (loaded from workspace/logs/*.json).
        Returns stats: total_reward, avg_reward, best_attempt, attempts.
        """
        if not log_entries:
            return {}
        rewards = [e.get("reward", 0.0) for e in log_entries]
        best   = max(range(len(rewards)), key=lambda i: rewards[i])
        return {
            "attempts":     len(rewards),
            "total_reward": round(sum(rewards), 4),
            "avg_reward":   round(sum(rewards) / len(rewards), 4),
            "best_attempt": log_entries[best].get("attempt"),
            "best_reward":  rewards[best],
        }
