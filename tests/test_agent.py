"""
tests/test_agent.py
===================
Unit tests for core.agent.RLAgent (Q-Learning).
"""

import json
import pytest
import tempfile
from pathlib import Path


RL_CONFIG = {
    "learning_rate": 0.1,
    "discount_factor": 0.9,
    "epsilon_start": 1.0,
    "epsilon_min": 0.05,
    "epsilon_decay": 0.98,
    "qtable_path": "",   # Set per-test via tmp dir
}


def _make_agent(tmp_path: Path):
    from core.agent import RLAgent
    cfg = {**RL_CONFIG, "qtable_path": str(tmp_path / "qtable.json")}
    return RLAgent(cfg)


class TestRLAgent:

    def test_choose_action_valid_range(self, tmp_path):
        """choose_action must return 0, 1, or 2."""
        agent = _make_agent(tmp_path)
        for _ in range(50):
            action = agent.choose_action("test_state")
            assert action in (0, 1, 2)

    def test_learn_updates_q_value(self, tmp_path):
        """Q-value for a (state, action) pair must change after learn()."""
        agent = _make_agent(tmp_path)
        state, next_state = "s0", "s1"
        action = 0

        q_before = agent.q_table.get(state, [0.0, 0.0, 0.0])[action]
        agent.learn(state, action, reward=1.0, next_state=next_state)
        q_after = agent.q_table[state][action]

        assert q_after != q_before, "Q-value should have changed after learn()"

    def test_learn_invalid_action_raises(self, tmp_path):
        """Action outside [0,2] must raise ValueError."""
        agent = _make_agent(tmp_path)
        with pytest.raises(ValueError):
            agent.learn("state", action=5, reward=0.0, next_state="next")

    def test_epsilon_decays(self, tmp_path):
        """decay_epsilon must reduce epsilon toward epsilon_min."""
        agent = _make_agent(tmp_path)
        initial = agent.epsilon
        agent.decay_epsilon()
        assert agent.epsilon < initial

    def test_epsilon_floored_at_min(self, tmp_path):
        """Epsilon must never go below epsilon_min."""
        from core.agent import RLAgent
        cfg = {**RL_CONFIG, "epsilon_start": 0.05, "epsilon_min": 0.05,
               "qtable_path": str(tmp_path / "qtable.json")}
        agent = RLAgent(cfg)
        for _ in range(100):
            agent.decay_epsilon()
        assert agent.epsilon >= agent._epsilon_min

    def test_qtable_save_and_load(self, tmp_path):
        """Q-table should persist correctly across agent instances."""
        agent1 = _make_agent(tmp_path)
        agent1.learn("s_persist", 1, reward=0.8, next_state="s_next")
        agent1.save_qtable()

        agent2 = _make_agent(tmp_path)   # Loads from same path
        assert "s_persist" in agent2.q_table
        assert abs(agent2.q_table["s_persist"][1] - agent1.q_table["s_persist"][1]) < 1e-6

    def test_invalid_hyperparameters_raise(self, tmp_path):
        """Out-of-range hyperparameters must raise ValueError on init."""
        from core.agent import RLAgent
        bad_cfg = {**RL_CONFIG, "learning_rate": 2.0,
                   "qtable_path": str(tmp_path / "qtable.json")}
        with pytest.raises(ValueError, match="learning_rate"):
            RLAgent(bad_cfg)
