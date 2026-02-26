"""
tests/test_data_store.py
=========================
Unit tests for utils.data_store.DataStore (SQLite persistence).
"""

import json
import sqlite3
import pytest
from pathlib import Path
from utils.data_store import DataStore


@pytest.fixture
def store(tmp_path: Path) -> DataStore:
    """Fresh DataStore backed by a temp SQLite file."""
    return DataStore(tmp_path / "test_rad_ml.db")


DDG_RESULTS = [
    {"title": "EV Battery Tech", "url": "http://example.com/ev", "snippet": "Electric vehicle battery", "text": ""},
    {"title": "Lithium Ion", "url": "http://example.com/li", "snippet": "Lithium ion cells", "text": ""},
]

KAGGLE_RESULTS = [
    {"ref": "user/ev-dataset", "title": "EV Dataset", "size": 1024, "tags": ["ev", "battery"], "url": "http://kaggle.com/datasets/user/ev-dataset"},
]

VERIFY_PASSED = {
    "overall_passed": True,
    "length": {"value": 200, "passed": True},
    "keyword_coverage": {"value": 0.6, "passed": True},
    "cosine_similarity": {"value": 0.35, "passed": True},
}

VERIFY_FAILED = {
    "overall_passed": False,
    "length": {"value": 10, "passed": False},
    "keyword_coverage": {"value": 0.0, "passed": False},
    "cosine_similarity": {"value": 0.01, "passed": False},
}


class TestDataStore:

    def test_db_file_created(self, tmp_path: Path):
        """DataStore must create the SQLite file on init."""
        db_path = tmp_path / "new_sub" / "rad_ml.db"
        DataStore(db_path)
        assert db_path.exists()

    def test_start_session_returns_int(self, store: DataStore):
        sid = store.start_session("test prompt", 10)
        assert isinstance(sid, int) and sid > 0

    def test_start_and_close_session(self, store: DataStore):
        sid = store.start_session("battery datasets", 5)
        store.close_session(final_epsilon=0.3, q_states=12)
        summary = store.get_session_summary(sid)
        assert summary["final_epsilon"] == pytest.approx(0.3)
        assert summary["q_states"] == 12

    def test_save_ddg_results_persisted(self, store: DataStore):
        sid = store.start_session("test", 3)
        store.save_ddg_results(
            episode=1, step=1,
            query="electric battery",
            results=DDG_RESULTS,
            verification_report=VERIFY_PASSED,
            cleaned_text="electric vehicle battery content data",
        )
        summary = store.get_session_summary(sid)
        assert summary["ddg_total"] == len(DDG_RESULTS)
        assert summary["ddg_verified"] == len(DDG_RESULTS)   # all verified=1

    def test_save_ddg_failed_verification(self, store: DataStore):
        sid = store.start_session("test", 3)
        store.save_ddg_results(
            episode=1, step=1,
            query="random query",
            results=DDG_RESULTS,
            verification_report=VERIFY_FAILED,
            cleaned_text="short",
        )
        summary = store.get_session_summary(sid)
        assert summary["ddg_verified"] == 0   # verified=0 for all rows

    def test_save_kaggle_results(self, store: DataStore):
        sid = store.start_session("test", 3)
        store.save_kaggle_results(
            episode=1, step=2,
            results=KAGGLE_RESULTS,
            verification_report=VERIFY_PASSED,
        )
        summary = store.get_session_summary(sid)
        assert summary["kaggle_total"] == len(KAGGLE_RESULTS)

    def test_log_episode(self, store: DataStore):
        sid = store.start_session("test", 5)
        store.log_episode(episode=1, total_reward=0.75,
                          epsilon_after=0.95, q_states_after=3)
        # Verify record exists directly in DB
        conn = sqlite3.connect(store._db_path)
        row = conn.execute(
            "SELECT total_reward FROM episode_log WHERE session_id = ?", (sid,)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == pytest.approx(0.75)

    def test_log_step(self, store: DataStore):
        sid = store.start_session("test", 5)
        store.log_step(
            episode=1, step=1,
            state="abc123", action=0, reward=0.4,
            next_state="def456", keywords=["electric", "battery"], done=False,
        )
        conn = sqlite3.connect(store._db_path)
        row = conn.execute(
            "SELECT action, reward, keywords FROM step_log WHERE session_id = ?", (sid,)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 0
        assert row[1] == pytest.approx(0.4)
        assert json.loads(row[2]) == ["electric", "battery"]

    def test_get_top_ddg_results_ordering(self, store: DataStore):
        sid = store.start_session("test", 5)
        # Save two batches with different similarity scores
        store.save_ddg_results(1, 1, "q1", DDG_RESULTS,
                                {**VERIFY_PASSED, "cosine_similarity": {"value": 0.8, "passed": True}},
                                "high sim text")
        store.save_ddg_results(1, 2, "q2", DDG_RESULTS[:1],
                                {**VERIFY_PASSED, "cosine_similarity": {"value": 0.2, "passed": True}},
                                "low sim text")
        top = store.get_top_ddg_results(sid, limit=5)
        assert len(top) >= 2
        # First result should have higher cosine_sim
        assert top[0]["cosine_sim"] >= top[-1]["cosine_sim"]

    def test_no_session_raises(self, tmp_path: Path):
        """Saving without starting a session raises RuntimeError."""
        store = DataStore(tmp_path / "no_session.db")
        with pytest.raises(RuntimeError, match="start_session"):
            store.save_ddg_results(1, 1, "q", [], None, "")
