"""
tests/test_environment.py
=========================
Unit tests for core.environment.Environment using mocked collectors.
"""

import pytest
from unittest.mock import MagicMock, patch
from core.environment import Environment, ACTION_DDG, ACTION_KAGGLE, ACTION_REFINE


def _make_env(ddg_results=None, kaggle_results=None):
    """Build an Environment with fully mocked dependencies."""
    ddg = MagicMock()
    ddg.search.return_value = ddg_results or [
        {
            "title": "Battery tech article",
            "url": "http://example.com",
            "snippet": (
                "electric vehicle battery technology energy storage "
                "lithium ion performance capacity cycle life range"
            ) * 5,
            "text": "",
        }
    ]

    kaggle = MagicMock()
    kaggle.search_datasets.return_value = kaggle_results or [
        {
            "ref": "user/ev-battery-dataset",
            "title": "Electric Vehicle Battery Dataset",
            "size": 1024,
            "tags": ["electric", "battery", "vehicle"],
            "url": "https://www.kaggle.com/datasets/user/ev-battery-dataset",
        }
    ]

    from utils.data_cleaner import DataVerifier
    verifier = DataVerifier({
        "min_text_length": 20,
        "min_keyword_coverage": 0.1,
        "min_cosine_similarity": 0.01,
    })

    env = Environment(ddg, kaggle, verifier, config={})
    return env


KEYWORD_BUNDLE = {
    "primary": ["electric", "battery", "vehicle"],
    "secondary": ["energy", "storage"],
    "tags": ["electric", "battery"],
}


class TestEnvironment:

    def test_reset_returns_string_state(self):
        env = _make_env()
        state = env.reset(KEYWORD_BUNDLE)
        assert isinstance(state, str) and len(state) > 0

    def test_step_returns_correct_types(self):
        env = _make_env()
        env.reset(KEYWORD_BUNDLE)
        next_state, reward, done = env.step(ACTION_DDG)
        assert isinstance(next_state, str)
        assert isinstance(reward, float)
        assert isinstance(done, bool)

    def test_reward_in_valid_range(self):
        env = _make_env()
        env.reset(KEYWORD_BUNDLE)
        for action in (ACTION_DDG, ACTION_KAGGLE, ACTION_REFINE):
            env.reset(KEYWORD_BUNDLE)
            _, reward, _ = env.step(action)
            assert -1.0 <= reward <= 1.0, f"Reward {reward} out of range for action {action}"

    def test_done_after_10_steps(self):
        env = _make_env()
        env.reset(KEYWORD_BUNDLE)
        done = False
        steps = 0
        while not done:
            _, _, done = env.step(ACTION_DDG)
            steps += 1
            assert steps <= 11, "Episode exceeded 10 steps without done=True"
        assert steps == 10

    def test_invalid_action_raises(self):
        env = _make_env()
        env.reset(KEYWORD_BUNDLE)
        with pytest.raises(ValueError):
            env.step(action=99)

    def test_empty_ddg_results_gives_negative_reward(self):
        env = _make_env(ddg_results=[])
        env.reset(KEYWORD_BUNDLE)
        _, reward, _ = env.step(ACTION_DDG)
        assert reward < 0.0, "Empty DDG results should yield negative reward"

    def test_refine_shrinks_keywords(self):
        env = _make_env()
        env.reset(KEYWORD_BUNDLE)
        initial_count = len(env._current_keywords)
        env.step(ACTION_REFINE)
        assert len(env._current_keywords) < initial_count
