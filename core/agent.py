"""
core/agent.py
=============
Q-Learning agent for the RAD-ML data collection pipeline.

Implements a tabular Q-learning agent with ε-greedy exploration.
The Q-table is persisted to a JSON file between runs so the agent
improves across sessions, not just within a single run.
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Optional

from core.environment import NUM_ACTIONS  # ACTION_DDG=0, ACTION_KAGGLE=1, ACTION_REFINE=2

logger = logging.getLogger(__name__)


class RLAgent:
    """
    Tabular Q-Learning agent.

    Parameters
    ----------
    config : dict
        The ``rl`` section of config.yaml.
    """

    def __init__(self, config: dict) -> None:
        self._alpha: float = config.get("learning_rate", 0.1)
        self._gamma: float = config.get("discount_factor", 0.9)
        self._epsilon: float = config.get("epsilon_start", 1.0)
        self._epsilon_min: float = config.get("epsilon_min", 0.05)
        self._epsilon_decay: float = config.get("epsilon_decay", 0.98)
        self._qtable_path: Path = Path(
            config.get("qtable_path", "data/qtable.json")
        )

        # Q-table: {state_hash: [q_ddg, q_kaggle, q_refine]}
        self._q: dict[str, list[float]] = {}

        self._validate_hyperparameters()
        self._load_qtable()

    # ------------------------------------------------------------------
    # Hyperparameter validation
    # ------------------------------------------------------------------

    def _validate_hyperparameters(self) -> None:
        errors: list[str] = []
        if not (0.0 < self._alpha <= 1.0):
            errors.append(f"learning_rate must be in (0, 1], got {self._alpha}")
        if not (0.0 <= self._gamma <= 1.0):
            errors.append(f"discount_factor must be in [0, 1], got {self._gamma}")
        if not (0.0 <= self._epsilon <= 1.0):
            errors.append(f"epsilon_start must be in [0, 1], got {self._epsilon}")
        if not (0.0 <= self._epsilon_min <= 1.0):
            errors.append(f"epsilon_min must be in [0, 1], got {self._epsilon_min}")
        if not (0.0 < self._epsilon_decay <= 1.0):
            errors.append(f"epsilon_decay must be in (0, 1], got {self._epsilon_decay}")

        if errors:
            raise ValueError(
                "Invalid RL hyperparameters:\n" + "\n".join(f"  - {e}" for e in errors)
            )

    # ------------------------------------------------------------------
    # Q-table persistence
    # ------------------------------------------------------------------

    def _load_qtable(self) -> None:
        """Load Q-table from disk if it exists, otherwise start fresh."""
        if self._qtable_path.exists():
            try:
                with self._qtable_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                # Validate structure
                if isinstance(data, dict):
                    self._q = {
                        k: v
                        for k, v in data.items()
                        if isinstance(v, list) and len(v) == NUM_ACTIONS
                    }
                    logger.info(
                        "Q-table loaded: %d states from '%s'.",
                        len(self._q),
                        self._qtable_path,
                    )
                else:
                    logger.warning(
                        "Q-table file has unexpected format. Starting fresh."
                    )
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Could not load Q-table from '%s': %s. Starting fresh.",
                    self._qtable_path,
                    exc,
                )
        else:
            logger.info("No existing Q-table found. Initialising fresh.")

    def save_qtable(self) -> None:
        """
        Persist the Q-table to disk.

        Raises
        ------
        OSError
            If the directory cannot be created or the file cannot be written.
        """
        try:
            self._qtable_path.parent.mkdir(parents=True, exist_ok=True)
            with self._qtable_path.open("w", encoding="utf-8") as f:
                json.dump(self._q, f, indent=2)
            logger.debug(
                "Q-table saved: %d states → '%s'.", len(self._q), self._qtable_path
            )
        except OSError as exc:
            logger.error("Failed to save Q-table: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Core Q-learning methods
    # ------------------------------------------------------------------

    def _get_q_row(self, state: str) -> list[float]:
        """Return or initialise the Q-values for *state*."""
        if state not in self._q:
            self._q[state] = [0.0] * NUM_ACTIONS
        return self._q[state]

    def choose_action(self, state: str) -> int:
        """
        Choose an action using ε-greedy policy.

        With probability ε explore randomly; otherwise exploit the
        action with the highest Q-value for *state*.

        Parameters
        ----------
        state : str
            Current state hash from the environment.

        Returns
        -------
        int
            Action index (0=DDG, 1=Kaggle, 2=Refine).
        """
        if random.random() < self._epsilon:
            action = random.randint(0, NUM_ACTIONS - 1)
            logger.debug(
                "ε-explore (ε=%.3f): random action %d", self._epsilon, action
            )
        else:
            q_row = self._get_q_row(state)
            action = int(q_row.index(max(q_row)))
            logger.debug(
                "Exploit: action %d (Q=%s)", action, [f"{q:.3f}" for q in q_row]
            )
        return action

    def learn(
        self,
        state: str,
        action: int,
        reward: float,
        next_state: str,
    ) -> None:
        """
        Apply the Bellman Q-update.

        Q(s,a) ← Q(s,a) + α · [r + γ · max_a' Q(s',a') − Q(s,a)]

        Parameters
        ----------
        state : str
            State hash before the action was taken.
        action : int
            Action index that was executed.
        reward : float
            Reward received from the environment.
        next_state : str
            State hash after the action.

        Raises
        ------
        ValueError
            If *action* is out of range.
        """
        if action not in range(NUM_ACTIONS):
            raise ValueError(
                f"Action must be in [0, {NUM_ACTIONS - 1}], got {action}."
            )

        q_row = self._get_q_row(state)
        next_q_row = self._get_q_row(next_state)

        old_value = q_row[action]
        td_target = reward + self._gamma * max(next_q_row)
        td_error = td_target - old_value
        q_row[action] = old_value + self._alpha * td_error

        logger.debug(
            "Q-update | s=%s a=%d r=%.4f → Q: %.4f → %.4f (δ=%.4f)",
            state[:6],
            action,
            reward,
            old_value,
            q_row[action],
            td_error,
        )

    def decay_epsilon(self) -> None:
        """Decay ε by the configured decay rate, floored at epsilon_min."""
        self._epsilon = max(self._epsilon_min, self._epsilon * self._epsilon_decay)
        logger.debug("Epsilon decayed → %.4f", self._epsilon)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def epsilon(self) -> float:
        return self._epsilon

    @epsilon.setter
    def epsilon(self, value: float) -> None:
        if not (0.0 <= value <= 1.0):
            raise ValueError(f"epsilon must be in [0, 1], got {value}")
        self._epsilon = value

    @property
    def q_table(self) -> dict[str, list[float]]:
        """Read-only view of the internal Q-table."""
        return dict(self._q)

    @property
    def num_states(self) -> int:
        return len(self._q)
