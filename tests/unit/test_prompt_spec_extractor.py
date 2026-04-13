"""
tests/test_prompt_spec_extractor.py
=====================================
Unit tests for the PromptSpecExtractor.
All LLM and HTTP calls are mocked — no API key needed.
"""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ── Path setup ─────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
for p in [
    str(ROOT / "Code_Generator" / "RAD-ML"),
    str(ROOT / "Code_Generator" / "RAD-ML" / "core"),
    str(ROOT / "Code_Generator" / "RAD-ML" / "generator"),
]:
    if p not in sys.path:
        sys.path.insert(0, p)

from generator.prompt_spec_extractor import PromptSpecExtractor, TASK_TYPES  # noqa: E402


# ── Helpers ────────────────────────────────────────────────────────────────
def _make_extractor(llm_response: str = "", search_key: str = "") -> PromptSpecExtractor:
    llm = MagicMock()
    llm.generate.return_value = llm_response
    config = {
        "codegen": {"workspace_dir": "/tmp/test_workspace"},
        "google_search": {
            "api_key": search_key,
            "cx": "test_cx" if search_key else "",
            "max_results": 3,
            "timeout_secs": 5,
        },
    }
    return PromptSpecExtractor(llm, config)


def _classification_spec_json() -> str:
    return json.dumps({
        "problem_summary": "Classify emails as spam or not spam",
        "task_type": "classification",
        "inputs": [
            {"name": "email_text", "type": "string", "required": True, "description": "Raw email body"},
            {"name": "sender", "type": "string", "required": False, "description": "Sender email address"},
        ],
        "outputs": [
            {"name": "label", "type": "string", "description": "spam or not_spam"},
        ],
        "constraints": ["Must run in under 2 seconds"],
        "assumptions": ["English emails only"],
        "edge_cases": ["Empty email body", "Non-ASCII characters"],
        "success_criteria": ["Accuracy > 95%"],
        "missing_info": ["Training dataset location"],
    })


def _regression_spec_json() -> str:
    return json.dumps({
        "problem_summary": "Predict house prices from bedroom count and area",
        "task_type": "regression",
        "inputs": [
            {"name": "bedrooms", "type": "integer", "required": True, "description": "Number of bedrooms"},
            {"name": "area_sqft", "type": "float", "required": True, "description": "Area in square feet"},
        ],
        "outputs": [
            {"name": "price_usd", "type": "float", "description": "Predicted price in USD"},
        ],
        "constraints": [],
        "assumptions": ["US housing market"],
        "edge_cases": ["Negative bedroom count"],
        "success_criteria": ["RMSE < 10000"],
        "missing_info": [],
    })


def _api_spec_json() -> str:
    return json.dumps({
        "problem_summary": "Build a REST API that accepts customer ID and returns purchase history",
        "task_type": "api",
        "inputs": [
            {"name": "customer_id", "type": "string", "required": True, "description": "Unique customer ID"},
        ],
        "outputs": [
            {"name": "purchase_history", "type": "list", "description": "List of past purchases"},
        ],
        "constraints": ["JSON response format"],
        "assumptions": ["Customer exists in database"],
        "edge_cases": ["Unknown customer ID"],
        "success_criteria": ["Returns 200 with purchase list"],
        "missing_info": ["Database schema"],
    })


# ── Tests ──────────────────────────────────────────────────────────────────

class TestExtractClassificationIntent(unittest.TestCase):
    def test_extract_classification_intent(self):
        extractor = _make_extractor(_classification_spec_json())
        spec = extractor.extract("Classify emails as spam", save=False)
        self.assertEqual(spec["task_type"], "classification")
        self.assertIn("task_type", spec)
        self.assertIn("inputs", spec)
        self.assertIn("outputs", spec)
        self.assertIn("problem_summary", spec)

    def test_all_required_keys_present(self):
        extractor = _make_extractor(_classification_spec_json())
        spec = extractor.extract("Classify emails", save=False)
        required = [
            "problem_summary", "task_type", "inputs", "outputs",
            "constraints", "assumptions", "edge_cases",
            "success_criteria", "missing_info",
        ]
        for key in required:
            self.assertIn(key, spec, f"Missing required key: {key}")

    def test_task_type_is_known_value(self):
        extractor = _make_extractor(_classification_spec_json())
        spec = extractor.extract("Classify emails", save=False)
        self.assertIn(spec["task_type"], TASK_TYPES)


class TestExtractRegressionIntent(unittest.TestCase):
    def test_extract_regression_intent(self):
        extractor = _make_extractor(_regression_spec_json())
        spec = extractor.extract("Predict house price", save=False)
        self.assertEqual(spec["task_type"], "regression")

    def test_inputs_have_correct_structure(self):
        extractor = _make_extractor(_regression_spec_json())
        spec = extractor.extract("Predict house price", save=False)
        for inp in spec["inputs"]:
            self.assertIn("name", inp)
            self.assertIn("type", inp)
            self.assertIn("required", inp)
            self.assertIn("description", inp)


class TestExtractApiIntent(unittest.TestCase):
    def test_extract_api_intent(self):
        extractor = _make_extractor(_api_spec_json())
        spec = extractor.extract("Build a REST API for customer purchase history", save=False)
        self.assertEqual(spec["task_type"], "api")

    def test_outputs_have_correct_structure(self):
        extractor = _make_extractor(_api_spec_json())
        spec = extractor.extract("Build a REST API", save=False)
        for out in spec["outputs"]:
            self.assertIn("name", out)
            self.assertIn("type", out)
            self.assertIn("description", out)


class TestExtractScriptIntent(unittest.TestCase):
    def test_extract_script_intent(self):
        script_spec = json.dumps({
            "problem_summary": "A CLI script to batch-rename files",
            "task_type": "script",
            "inputs": [{"name": "directory", "type": "string", "required": True, "description": "Dir path"}],
            "outputs": [{"name": "renamed_files", "type": "list", "description": "Renamed file list"}],
            "constraints": [], "assumptions": [], "edge_cases": [],
            "success_criteria": [], "missing_info": [],
        })
        extractor = _make_extractor(script_spec)
        spec = extractor.extract("Write a script to batch rename files", save=False)
        self.assertEqual(spec["task_type"], "script")


class TestExtractUnknownType(unittest.TestCase):
    def test_extract_unknown_task_type(self):
        unknown_spec = json.dumps({
            "problem_summary": "Do something mysterious",
            "task_type": "unknown",
            "inputs": [{"name": "x", "type": "unknown", "required": True, "description": "some input"}],
            "outputs": [{"name": "y", "type": "unknown", "description": "some output"}],
            "constraints": [], "assumptions": [], "edge_cases": [],
            "success_criteria": [], "missing_info": [],
        })
        extractor = _make_extractor(unknown_spec)
        spec = extractor.extract("Do something unknown", save=False)
        self.assertEqual(spec["task_type"], "unknown")


class TestSearchEnrichment(unittest.TestCase):
    def test_search_enrichment_skipped_without_key(self):
        """No API key → enrich_with_search returns empty list, no exception."""
        extractor = _make_extractor(_classification_spec_json(), search_key="")
        spec = extractor.extract("Classify emails", save=False)
        snippets = extractor.enrich_with_search(spec)
        self.assertIsInstance(snippets, list)
        self.assertEqual(len(snippets), 0)

    @patch("urllib.request.urlopen")
    def test_search_enrichment_injects_snippets(self, mock_urlopen):
        """When API key present and search returns results, snippets are non-empty."""
        # Mock Google CSE API response
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = json.dumps({
            "items": [
                {"title": "Email Classification with sklearn", "snippet": "from sklearn import ...", "link": "https://example.com/1"},
                {"title": "Spam Detection Python", "snippet": "import pandas as pd ...", "link": "https://example.com/2"},
            ]
        }).encode("utf-8")
        mock_urlopen.return_value = mock_response

        extractor = _make_extractor(_classification_spec_json(), search_key="FAKE_KEY")
        spec = extractor.extract("Classify emails", save=False)
        snippets = extractor.enrich_with_search(spec)
        self.assertIsInstance(snippets, list)
        self.assertGreater(len(snippets), 0)
        self.assertIn("Email Classification", snippets[0])

    @patch("urllib.request.urlopen", side_effect=Exception("Network error"))
    def test_search_enrichment_handles_network_failure(self, _mock):
        """Network failure → returns empty list, no exception raised."""
        extractor = _make_extractor(_classification_spec_json(), search_key="FAKE_KEY")
        spec = extractor.extract("Classify emails", save=False)
        snippets = extractor.enrich_with_search(spec)
        self.assertIsInstance(snippets, list)
        self.assertEqual(len(snippets), 0)


class TestFallbackOnLLMFailure(unittest.TestCase):
    def test_fallback_on_llm_failure(self):
        """LLM raises RuntimeError → rule-based fallback returns valid IntentSpec."""
        llm = MagicMock()
        llm.generate.side_effect = RuntimeError("LLM is down")
        config = {
            "codegen": {"workspace_dir": "/tmp/fallback_test"},
            "google_search": {"api_key": "", "cx": ""},
        }
        extractor = PromptSpecExtractor(llm, config)
        spec = extractor.extract("Predict house prices", save=False)

        # Must return a valid dict with all required keys
        for key in ("problem_summary", "task_type", "inputs", "outputs",
                    "constraints", "assumptions", "edge_cases",
                    "success_criteria", "missing_info"):
            self.assertIn(key, spec, f"Fallback missing key: {key}")

        # Fallback should at least infer regression from keyword "predict"
        self.assertEqual(spec["task_type"], "regression")

    def test_fallback_on_invalid_json_from_llm(self):
        """LLM returns invalid JSON → fallback spec returned."""
        extractor = _make_extractor("this is not json at all")
        spec = extractor.extract("Classify spam emails", save=False)
        self.assertIn("problem_summary", spec)
        self.assertIn(spec["task_type"], TASK_TYPES)


class TestValidateAndFix(unittest.TestCase):
    def test_unknown_task_type_coerced(self):
        """task_type not in TASK_TYPES → coerced to 'unknown'."""
        bad_spec = json.dumps({
            "problem_summary": "Do X",
            "task_type": "banana",  # invalid
            "inputs": [{"name": "x", "type": "string", "required": True, "description": "input"}],
            "outputs": [{"name": "y", "type": "string", "description": "output"}],
            "constraints": [], "assumptions": [], "edge_cases": [],
            "success_criteria": [], "missing_info": [],
        })
        extractor = _make_extractor(bad_spec)
        spec = extractor.extract("Do something", save=False)
        self.assertEqual(spec["task_type"], "unknown")

    def test_empty_inputs_gets_default(self):
        """Empty inputs list → default placeholder input added."""
        partial_spec = json.dumps({
            "problem_summary": "Do something",
            "task_type": "script",
            "inputs": [],  # empty — should be filled with a placeholder
            "outputs": [{"name": "result", "type": "string", "description": "output"}],
            "constraints": [], "assumptions": [], "edge_cases": [],
            "success_criteria": [], "missing_info": [],
        })
        extractor = _make_extractor(partial_spec)
        spec = extractor.extract("Do something", save=False)
        self.assertGreater(len(spec["inputs"]), 0)


class TestSavesToDisk(unittest.TestCase):
    def test_extract_saves_json_to_disk(self):
        """When save=True, intent_spec.json is written to the workspace directory."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = _make_extractor(_classification_spec_json())
            extractor._config = {
                "codegen": {"workspace_dir": tmpdir},
                "google_search": {"api_key": "", "cx": ""},
            }
            spec = extractor.extract("Classify emails", save=True)
            out = Path(tmpdir) / "intent_spec.json"
            self.assertTrue(out.exists(), "intent_spec.json was not created")
            loaded = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(loaded["task_type"], spec["task_type"])


if __name__ == "__main__":
    unittest.main()
