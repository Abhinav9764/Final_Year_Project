"""
core/environment.py
====================
The RL "World" — defines states, actions, and the reward function for RAD-ML.

The environment executes the action chosen by the agent (collect from DDG,
collect from Kaggle, or refine keywords), then computes a reward by:
  1. Running ``DataVerifier`` to ensure data quality.
  2. Computing TF-IDF cosine similarity between collected data and keywords.

Only verified data contributes a positive reward.
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from brain.extractor import KeywordBundle
    from collectors.ddg_search import DDGSearchClient
    from collectors.kaggle_client import KaggleClient
    from utils.data_cleaner import DataVerifier

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Action constants (used across agent + environment)
# ---------------------------------------------------------------------------
ACTION_DDG    = 0   # Search DuckDuckGo
ACTION_KAGGLE = 1   # Search Kaggle
ACTION_REFINE = 2   # Refine / rotate keywords
NUM_ACTIONS   = 3   # Total number of possible actions


class Environment:
    """
    Manages the state of the data-collection episode and computes rewards.

    Parameters
    ----------
    ddg_client : DDGSearchClient
    kaggle_client : KaggleClient
    verifier : DataVerifier
    config : dict
        Full config dict (used for verification thresholds).
    """

    NUM_ACTIONS = 3

    def __init__(
        self,
        ddg_client: "DDGSearchClient",
        kaggle_client: "KaggleClient",
        verifier: "DataVerifier",
        config: dict,
    ) -> None:
        self._ddg = ddg_client
        self._kaggle = kaggle_client
        self._verifier = verifier
        self._cfg = config

        # Episode state
        self._current_keywords: list[str] = []
        self._last_action: int = -1
        self._quality_score: float = 0.0
        self._step_count: int = 0
        self._collected_texts: list[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self, keyword_bundle: "KeywordBundle") -> str:
        """
        Reset the environment for a new episode.

        Parameters
        ----------
        keyword_bundle : KeywordBundle
            Keywords extracted from the user prompt.

        Returns
        -------
        str
            The initial state hash.
        """
        self._current_keywords = keyword_bundle["primary"]
        self._last_action = -1
        self._quality_score = 0.0
        self._step_count = 0
        self._collected_texts = []
        logger.debug("Environment reset with keywords: %s", self._current_keywords)
        return self._state_hash()

    def step(
        self,
        action: int,
    ) -> tuple[str, float, bool]:
        """
        Execute *action* and return (next_state, reward, done).

        Parameters
        ----------
        action : int
            One of ``ACTION_DDG``, ``ACTION_KAGGLE``, ``ACTION_REFINE``.

        Returns
        -------
        tuple[str, float, bool]
            ``next_state`` — new state hash.
            ``reward``     — [-1.0, +1.0] based on data quality.
            ``done``       — True after 10 steps per episode.

        Raises
        ------
        ValueError
            If *action* is not a valid action index.
        """
        if action not in (ACTION_DDG, ACTION_KAGGLE, ACTION_REFINE):
            raise ValueError(
                f"Invalid action {action}. Must be 0, 1, or 2."
            )

        self._last_action = action
        self._step_count += 1
        reward = 0.0
        collected_text = ""

        try:
            if action == ACTION_DDG:
                collected_text = self._run_ddg()
            elif action == ACTION_KAGGLE:
                collected_text = self._run_kaggle()
            elif action == ACTION_REFINE:
                collected_text = self._run_refine()

        except RuntimeError as exc:
            logger.warning("Action %d execution error: %s", action, exc)
            reward = -0.5   # Penalise failures

        else:
            # --- Verification gate ---
            if collected_text:
                from utils.data_cleaner import clean_text  # noqa: PLC0415

                cleaned = clean_text(collected_text)
                passed, report = self._verifier.verify(
                    cleaned, self._current_keywords
                )

                if passed:
                    similarity = float(
                        report.get("cosine_similarity", {}).get("value", 0.0)  # type: ignore[union-attr]
                    )
                    coverage = float(
                        report.get("keyword_coverage", {}).get("value", 0.0)  # type: ignore[union-attr]
                    )
                    # Reward: average of similarity and coverage, clipped to [-1, 1]
                    reward = min(1.0, max(-1.0, (similarity + coverage) / 2.0))
                    self._quality_score = reward
                    self._collected_texts.append(cleaned)
                    logger.info(
                        "Step %d — Action %d → reward=%.4f (sim=%.4f, cov=%.4f)",
                        self._step_count,
                        action,
                        reward,
                        similarity,
                        coverage,
                    )
                else:
                    reward = -0.2   # Data failed verification — mild penalty
                    logger.info(
                        "Step %d — Action %d → reward=%.4f (verification failed)",
                        self._step_count,
                        action,
                        reward,
                    )
            else:
                reward = -0.3   # No data collected at all
                logger.info(
                    "Step %d — Action %d → reward=%.4f (no data returned)",
                    self._step_count,
                    action,
                    reward,
                )

        done = self._step_count >= 10
        return self._state_hash(), reward, done

    def get_collected_texts(self) -> list[str]:
        """Return all verified text collected so far in this episode."""
        return list(self._collected_texts)

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------

    def _run_ddg(self) -> str:
        """Execute a DuckDuckGo search and return combined snippet text."""
        query = " ".join(self._current_keywords)
        results = self._ddg.search(query, fetch_text=False)

        if not results:
            logger.debug("DDG returned zero results for '%s'.", query)
            return ""

        combined = " ".join(
            r.get("snippet", "") + " " + r.get("text", "")
            for r in results
        )
        return combined.strip()

    def _run_kaggle(self) -> str:
        """Execute a Kaggle search, return concatenated title + tag text."""
        results = self._kaggle.search_datasets(self._current_keywords)

        if not results:
            logger.debug("Kaggle returned zero datasets.")
            return ""

        combined = " ".join(
            r.get("title", "") + " " + " ".join(r.get("tags", []))
            for r in results
        )
        return combined.strip()

    def _run_refine(self) -> str:
        """
        Rotate to secondary keywords (simulated refinement).

        Returns an empty string — the refinement step doesn't collect data
        itself, but shifts the keyword context for the next step.
        """
        if len(self._current_keywords) > 1:
            # Rotate: drop first keyword, promoting secondary ones
            self._current_keywords = self._current_keywords[1:]
            logger.info(
                "Keywords refined → %s", self._current_keywords
            )
        else:
            logger.debug("Cannot refine further — only one keyword left.")
        return ""

    # ------------------------------------------------------------------
    # State hashing
    # ------------------------------------------------------------------

    def _state_hash(self) -> str:
        """
        Produce a compact string representation of the current state.

        The state is: (frozenset of keywords, last_action, quality_bin).
        Quality is binned into 5 levels to keep the Q-table compact.
        """
        quality_bin = int(self._quality_score * 4)   # 0, 1, 2, 3, or 4
        raw = f"kw={'|'.join(sorted(self._current_keywords))}" \
              f"_act={self._last_action}_q={quality_bin}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]   # Short hash
