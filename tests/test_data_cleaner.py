"""
tests/test_data_cleaner.py
===========================
Unit tests for utils.data_cleaner (clean_text, clean_csv, DataVerifier).
"""

import csv
import pytest
import tempfile
from pathlib import Path


VERIFY_CONFIG = {
    "min_text_length": 50,
    "min_keyword_coverage": 0.3,
    "min_cosine_similarity": 0.05,
}


class TestCleanText:

    def test_strips_html_tags(self):
        from utils.data_cleaner import clean_text
        result = clean_text("<p>Hello <b>World</b></p>")
        assert "<" not in result
        assert "Hello" in result

    def test_collapses_whitespace(self):
        from utils.data_cleaner import clean_text
        result = clean_text("word1   \n  word2\t word3")
        assert "  " not in result   # No double spaces

    def test_empty_string_returns_empty(self):
        from utils.data_cleaner import clean_text
        assert clean_text("") == ""

    def test_non_string_raises_type_error(self):
        from utils.data_cleaner import clean_text
        with pytest.raises(TypeError):
            clean_text(123)  # type: ignore


class TestCleanCSV:

    def test_creates_cleaned_file(self, tmp_path: Path):
        from utils.data_cleaner import clean_csv
        raw_file = tmp_path / "raw.csv"
        raw_file.write_text(
            "Name,  Age , City\nAlice, 30, NYC\nAlice, 30, NYC\n, ,\n"
        )
        out = clean_csv(raw_file, tmp_path / "processed")
        assert out is not None
        assert out.exists()

    def test_missing_file_raises(self, tmp_path: Path):
        from utils.data_cleaner import clean_csv
        with pytest.raises(FileNotFoundError):
            clean_csv(tmp_path / "nonexistent.csv", tmp_path)

    def test_column_names_normalised(self, tmp_path: Path):
        from utils.data_cleaner import clean_csv
        import pandas as pd
        raw = tmp_path / "data.csv"
        raw.write_text("First Name,Last Name\nJohn,Doe\n")
        out = clean_csv(raw, tmp_path / "processed")
        df = pd.read_csv(out)
        assert "first_name" in df.columns
        assert "last_name" in df.columns


class TestDataVerifier:

    def _make_verifier(self):
        from utils.data_cleaner import DataVerifier
        return DataVerifier(VERIFY_CONFIG)

    def test_passes_high_quality_text(self):
        verifier = self._make_verifier()
        text = (
            "electric vehicles use battery systems for energy storage. "
            "Battery technology is critical for electric vehicles performance "
            "and range. Modern electric vehicle batteries are lithium-ion based."
        ) * 3
        passed, report = verifier.verify(text, ["electric", "battery", "vehicles"])
        assert passed is True

    def test_fails_too_short_text(self):
        verifier = self._make_verifier()
        passed, report = verifier.verify("short", ["electric", "battery"])
        assert passed is False
        assert report["length"]["passed"] is False

    def test_fails_zero_keyword_coverage(self):
        verifier = self._make_verifier()
        text = "the quick brown fox jumps over the lazy dog " * 10
        passed, report = verifier.verify(text, ["neural", "network", "deep"])
        assert passed is False

    def test_invalid_coverage_threshold_raises(self):
        from utils.data_cleaner import DataVerifier
        with pytest.raises(ValueError, match="min_keyword_coverage"):
            DataVerifier({**VERIFY_CONFIG, "min_keyword_coverage": 1.5})

    def test_report_has_expected_keys(self):
        verifier = self._make_verifier()
        _, report = verifier.verify("some text about nothing", ["word"])
        assert "length" in report
        assert "keyword_coverage" in report
        assert "cosine_similarity" in report
        assert "overall_passed" in report
