"""
tests/unit/test_tuning_engine.py
=================================
Unit tests for the Self-Learning Tuning Engine.

Tests verify:
1. Tuning pipeline trigger when DPO threshold is met
2. Tuning pipeline does NOT trigger when threshold is not met
3. DPO dataset counting and validation
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the tuning engine
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "Code_Generator" / "RAD-ML"))

from cg_brain.tuning_engine import TuningEngine, DEFAULT_TUNING_THRESHOLD


class TestTuningEngineThreshold:
    """Test the DPO threshold triggering mechanism."""

    @pytest.fixture
    def mock_config(self):
        """Provide a minimal mock configuration."""
        return {
            "tuning": {
                "dpo_threshold": 5,  # Low threshold for testing
                "lora_rank": 8,
                "lora_alpha": 16,
                "epochs": 1,
                "batch_size": 2,
            }
        }

    @pytest.fixture
    def temp_brain_dir(self, tmp_path):
        """Create a temporary brain directory for testing."""
        brain_dir = tmp_path / "brain"
        brain_dir.mkdir()
        return brain_dir

    def test_threshold_not_met(self, mock_config, temp_brain_dir):
        """Tuning should NOT trigger when DPO pairs < threshold."""
        with patch.object(TuningEngine, '__init__', lambda self, cfg: None):
            engine = TuningEngine.__new__(TuningEngine)
            engine.dpo_threshold = mock_config["tuning"]["dpo_threshold"]
            engine.dpo_path = temp_brain_dir / "qwen_dpo_dataset.jsonl"
            engine.last_tuning_date = None
            engine.total_tuning_runs = 0

            # Create DPO file with fewer entries than threshold
            with open(engine.dpo_path, "w") as f:
                for i in range(3):  # Only 3 entries, threshold is 5
                    f.write(json.dumps({
                        "instruction": f"Test {i}",
                        "chosen": "Good code",
                        "rejected": "Bad code"
                    }) + "\n")

            triggered, message = engine.check_and_trigger_tuning()

            assert triggered is False
            assert "more DPO pairs" in message.lower() or "Need" in message

    def test_threshold_met_triggers_tuning(self, mock_config, temp_brain_dir):
        """Tuning SHOULD trigger when DPO pairs >= threshold."""
        with patch.object(TuningEngine, '__init__', lambda self, cfg: None):
            engine = TuningEngine.__new__(TuningEngine)
            engine.dpo_threshold = mock_config["tuning"]["dpo_threshold"]
            engine.dpo_path = temp_brain_dir / "qwen_dpo_dataset.jsonl"
            engine.last_tuning_date = None
            engine.total_tuning_runs = 0
            engine.tuning_dir = temp_brain_dir / "tuning_cache"
            engine.tuning_dir.mkdir()
            engine.training_log_path = engine.tuning_dir / "training_log.json"

            # Create DPO file with entries meeting threshold
            with open(engine.dpo_path, "w") as f:
                for i in range(5):  # Exactly 5 entries, meets threshold
                    f.write(json.dumps({
                        "instruction": f"Test {i}",
                        "chosen": "Good code",
                        "rejected": "Bad code"
                    }) + "\n")

            # Mock Ollama availability check
            with patch.object(engine, '_check_ollama_available', return_value=False):
                triggered, message = engine.check_and_trigger_tuning()

                # Should trigger but fail due to Ollama not available
                assert triggered is True
                assert "Ollama" in message or "not available" in message.lower()

    def test_count_dpo_pairs(self, mock_config, temp_brain_dir):
        """Test DPO pair counting."""
        engine = TuningEngine.__new__(TuningEngine)
        engine.dpo_path = temp_brain_dir / "qwen_dpo_dataset.jsonl"

        # Empty file
        engine.dpo_path.touch()
        assert engine._count_dpo_pairs() == 0

        # Add entries
        with open(engine.dpo_path, "w") as f:
            for i in range(10):
                f.write(json.dumps({
                    "instruction": f"Test {i}",
                    "chosen": "Good code",
                    "rejected": "Bad code"
                }) + "\n")

        assert engine._count_dpo_pairs() == 10

    def test_no_dpo_file_returns_zero(self, mock_config, temp_brain_dir):
        """Test counting when DPO file doesn't exist."""
        engine = TuningEngine.__new__(TuningEngine)
        engine.dpo_path = temp_brain_dir / "nonexistent.jsonl"

        assert engine._count_dpo_pairs() == 0

    def test_recent_tuning_skip(self, mock_config, temp_brain_dir):
        """Tuning should skip if recently tuned (within 1 day)."""
        from datetime import datetime, timedelta

        with patch.object(TuningEngine, '__init__', lambda self, cfg: None):
            engine = TuningEngine.__new__(TuningEngine)
            engine.dpo_threshold = 5
            engine.dpo_path = temp_brain_dir / "qwen_dpo_dataset.jsonl"
            engine.last_tuning_date = (datetime.now() - timedelta(hours=12)).isoformat()
            engine.total_tuning_runs = 1

            # Create enough DPO entries
            with open(engine.dpo_path, "w") as f:
                for i in range(10):
                    f.write(json.dumps({
                        "instruction": f"Test {i}",
                        "chosen": "Good code",
                        "rejected": "Bad code"
                    }) + "\n")

            triggered, message = engine.check_and_trigger_tuning()

            assert triggered is False
            assert "Recently tuned" in message or "days ago" in message


class TestTuningEngineValidation:
    """Test DPO dataset validation."""

    @pytest.fixture
    def mock_config(self):
        return {
            "tuning": {"dpo_threshold": 5}
        }

    def test_validate_valid_dpo_dataset(self, mock_config, tmp_path):
        """Valid DPO dataset should pass validation."""
        engine = TuningEngine.__new__(TuningEngine)
        engine.dpo_path = tmp_path / "valid_dataset.jsonl"
        engine.dpo_threshold = 3

        with open(engine.dpo_path, "w") as f:
            for i in range(3):
                f.write(json.dumps({
                    "instruction": f"Test {i}",
                    "chosen": "Good code",
                    "rejected": "Bad code"
                }) + "\n")

        assert engine._validate_dpo_dataset() is True

    def test_validate_invalid_dpo_dataset_missing_fields(self, mock_config, tmp_path):
        """Invalid DPO entries should be detected."""
        engine = TuningEngine.__new__(TuningEngine)
        engine.dpo_path = tmp_path / "invalid_dataset.jsonl"
        engine.dpo_threshold = 3

        # Write entries missing required fields
        with open(engine.dpo_path, "w") as f:
            f.write(json.dumps({"instruction": "Test"}) + "\n")  # Missing chosen/rejected
            f.write(json.dumps({"chosen": "code"}) + "\n")  # Missing instruction/rejected

        assert engine._validate_dpo_dataset() is False

    def test_validate_empty_dpo_dataset(self, mock_config, tmp_path):
        """Empty DPO file should fail validation."""
        engine = TuningEngine.__new__(TuningEngine)
        engine.dpo_path = tmp_path / "empty_dataset.jsonl"
        engine.dpo_path.touch()  # Create empty file

        assert engine._validate_dpo_dataset() is False


class TestTuningEngineState:
    """Test state persistence."""

    def test_save_and_load_state(self, tmp_path):
        """Test state is saved and loaded correctly."""
        tuning_dir = tmp_path / "tuning_cache"
        tuning_dir.mkdir()

        engine = TuningEngine.__new__(TuningEngine)
        engine.tuning_dir = tuning_dir
        engine.training_log_path = tuning_dir / "training_log.json"
        engine.last_tuning_date = "2024-01-01T00:00:00"
        engine.total_tuning_runs = 5
        engine.dpo_threshold = 50
        engine.base_model = "qwen2.5-coder:3b"
        engine.ollama_model_name = "qwen2.5-coder:3b-radml"

        engine._save_state()

        # Create new engine and load state
        engine2 = TuningEngine.__new__(TuningEngine)
        engine2.tuning_dir = tuning_dir
        engine2.training_log_path = tuning_dir / "training_log.json"
        engine2.last_tuning_date = None
        engine2.total_tuning_runs = 0

        engine2._load_state()

        assert engine2.last_tuning_date == "2024-01-01T00:00:00"
        assert engine2.total_tuning_runs == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
