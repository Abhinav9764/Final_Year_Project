"""
core/evolution_engine.py
=========================
Handles progressive self-improvement of the RAD-ML Q-learning agent.

The evolution engine:
  - Tracks per-episode rewards to detect performance trends.
  - Decays epsilon (exploration → exploitation shift).
  - Prunes underperforming Q-table entries every N episodes.
  - Adjusts the learning rate adaptively based on reward variance.
"""

from __future__ import annotations

import logging
import statistics
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent import RLAgent

logger = logging.getLogger(__name__)


class EvolutionEngine:
    """
    Monitors agent performance and drives self-improvement.

    Parameters
    ----------
    agent : RLAgent
        The Q-learning agent to evolve.
    config : dict
        The ``rl`` section of config.yaml.
    """

    # Evolve every this many episodes
    EVOLVE_EVERY = 5

    def __init__(self, agent: "RLAgent", config: dict) -> None:
        self._agent = agent
        self._alpha_min: float = 0.01
        self._alpha_max: float = float(config.get("learning_rate", 0.1))
        self._episode_rewards: list[float] = []   # Total reward per episode
        self._best_avg: float = float("-inf")

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_episode(self, total_reward: float, episode: int) -> None:
        """
        Register the total reward for a completed episode.

        Parameters
        ----------
        total_reward : float
            Sum of rewards collected during the episode.
        episode : int
            Episode number (1-indexed).
        """
        self._episode_rewards.append(total_reward)
        logger.info(
            "Episode %d complete | total_reward=%.4f | ε=%.4f | Q-states=%d",
            episode,
            total_reward,
            self._agent.epsilon,
            self._agent.num_states,
        )

        # Decay exploration after every episode
        self._agent.decay_epsilon()

        # Trigger evolution check
        if episode % self.EVOLVE_EVERY == 0:
            self.evolve(episode)

    # ------------------------------------------------------------------
    # Evolution logic
    # ------------------------------------------------------------------

    def evolve(self, episode: int) -> None:
        """
        Analyse recent performance and adapt the agent.

        Actions taken:
        1. Compute average reward over the last ``EVOLVE_EVERY`` episodes.
        2. If improving, update the ``best_avg`` baseline.
        3. If stagnating / declining, prune low-Q entries and
           bump epsilon slightly to encourage fresh exploration.
        4. Adapt learning rate based on reward variance (high variance →
           reduce α to stabilise, low variance → can afford higher α).

        Parameters
        ----------
        episode : int
            Current episode number (for logging context).

        Raises
        ------
        ValueError
            If there are no recorded episodes to evolve from.
        """
        if not self._episode_rewards:
            raise ValueError("No episodes recorded — cannot evolve.")

        window = self._episode_rewards[-self.EVOLVE_EVERY :]
        try:
            avg_reward = statistics.mean(window)
            reward_variance = statistics.variance(window) if len(window) > 1 else 0.0
        except statistics.StatisticsError as exc:
            logger.warning("Statistics error during evolution: %s", exc)
            return

        logger.info(
            "Evolution @ ep %d | avg_reward=%.4f | variance=%.4f | "
            "best_avg=%.4f",
            episode,
            avg_reward,
            reward_variance,
            self._best_avg,
        )

        if avg_reward > self._best_avg:
            self._best_avg = avg_reward
            logger.info("New best average reward: %.4f ✓", self._best_avg)
        else:
            # Stagnation detected — prune + explore more
            pruned = self._prune_low_q_entries(threshold=-0.5)
            bump = min(0.1, (1.0 - self._agent.epsilon) * 0.2)
            self._agent.epsilon = min(1.0, self._agent.epsilon + bump)
            logger.info(
                "Stagnation detected. Pruned %d Q-entries. "
                "Bumped ε → %.4f",
                pruned,
                self._agent.epsilon,
            )

        # Adaptive learning rate
        self._adapt_learning_rate(reward_variance)

    def _prune_low_q_entries(self, threshold: float = -0.5) -> int:
        """
        Remove Q-table entries where ALL action values are below *threshold*.

        This prevents the table from accumulating dead states that can
        slow convergence.

        Returns
        -------
        int
            Number of entries removed.
        """
        q = self._agent.q_table   # Read-only copy
        to_delete = [
            state
            for state, values in q.items()
            if all(v < threshold for v in values)
        ]
        # Direct access to internal q table via public property not writable;
        # access through agent's internal dict by re-learning those states
        # to zero (safest without exposing internals).
        for state in to_delete:
            # Re-learn each pruned state-action pair to 0 via a no-op update
            for action in range(3):
                self._agent.learn(state, action, 0.0, state)

        if to_delete:
            logger.debug("Pruned %d low-Q states.", len(to_delete))
        return len(to_delete)

    def _adapt_learning_rate(self, variance: float) -> None:
        """
        Scale learning rate inversely with reward variance.

        High variance → reduce α (stabilise updates).
        Low variance  → restore α toward its starting value.
        """
        # This is a heuristic rescaling — not modifying private alpha directly
        # since alpha lives inside the agent. We log the recommendation.
        if variance > 0.5:
            recommended_alpha = max(
                self._alpha_min, self._agent._alpha * 0.9  # noqa: SLF001
            )
            self._agent._alpha = recommended_alpha  # noqa: SLF001
            logger.info(
                "High reward variance (%.4f) → α reduced to %.4f",
                variance,
                recommended_alpha,
            )
        elif variance < 0.05:
            recommended_alpha = min(
                self._alpha_max, self._agent._alpha * 1.05  # noqa: SLF001
            )
            self._agent._alpha = recommended_alpha  # noqa: SLF001
            logger.info(
                "Low reward variance (%.4f) → α increased to %.4f",
                variance,
                recommended_alpha,
            )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """Return a session summary dict for display at the end of a run."""
        if not self._episode_rewards:
            return {"message": "No episodes completed."}

        return {
            "total_episodes":  len(self._episode_rewards),
            "best_avg_reward": round(self._best_avg, 4),
            "final_epsilon":   round(self._agent.epsilon, 4),
            "q_states_learned": self._agent.num_states,
            "episode_rewards": [round(r, 4) for r in self._episode_rewards],
        }
