"""
tests/test_extractor.py
=======================
Unit tests for brain.extractor.KeywordExtractor.
"""

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

SAMPLE_CONFIG = {
    "spacy_model": "en_core_web_sm",
    "top_keywords": 5,
    "language": "en",
}


def _make_extractor():
    from brain.extractor import KeywordExtractor
    return KeywordExtractor(SAMPLE_CONFIG)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestKeywordExtractor:

    def test_extract_returns_keyword_bundle_keys(self):
        """extract() must return a dict with primary, secondary, tags keys."""
        extractor = _make_extractor()
        result = extractor.extract("electric vehicle battery datasets")
        assert "primary" in result
        assert "secondary" in result
        assert "tags" in result

    def test_primary_not_empty_for_valid_prompt(self):
        """A meaningful prompt should yield at least one primary keyword."""
        extractor = _make_extractor()
        result = extractor.extract("machine learning classification algorithms")
        assert len(result["primary"]) >= 1

    def test_tags_are_single_words(self):
        """Tags must be single tokens (no spaces)."""
        extractor = _make_extractor()
        result = extractor.extract("deep learning neural network image recognition")
        for tag in result["tags"]:
            assert " " not in tag, f"Tag '{tag}' contains a space."

    def test_empty_prompt_raises_value_error(self):
        """Empty prompt must raise ValueError."""
        extractor = _make_extractor()
        with pytest.raises(ValueError, match="non-empty"):
            extractor.extract("")

    def test_whitespace_only_prompt_raises_value_error(self):
        """Whitespace-only prompt must raise ValueError."""
        extractor = _make_extractor()
        with pytest.raises(ValueError):
            extractor.extract("   ")

    def test_top_keywords_limit_respected(self):
        """primary must not exceed top_keywords from config."""
        extractor = _make_extractor()
        result = extractor.extract(
            "reinforcement learning Q-learning exploration exploitation "
            "reward discount factor epsilon greedy policy gradient"
        )
        assert len(result["primary"]) <= SAMPLE_CONFIG["top_keywords"]
