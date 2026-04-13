"""
test_app.py — Unit tests for the generated Streamlit ML app.
Tests only pure Python logic; Streamlit is mocked at import time so these
tests work in any environment regardless of whether Streamlit is installed.
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

# ── Mock Streamlit and boto3 before importing app ─────────────────────────────
# This prevents ModuleNotFoundError when Streamlit / boto3 are not installed
# in the test environment, and stops Streamlit from trying to start a server.
_st_mock = MagicMock()
_boto3_mock = MagicMock()
sys.modules.setdefault("streamlit", _st_mock)
sys.modules.setdefault("boto3", _boto3_mock)
sys.modules.setdefault("pandas", MagicMock())
sys.modules.setdefault("yaml", MagicMock())

# Patch open + yaml.safe_load so app-level config loading doesn't fail
import builtins
_real_open = builtins.open


def _safe_open(file, *args, **kwargs):
    if str(file).endswith("config.yaml"):
        from io import StringIO
        return StringIO("")
    return _real_open(file, *args, **kwargs)


with patch("builtins.open", side_effect=_safe_open), \
     patch.dict(sys.modules, {"yaml": MagicMock(safe_load=lambda f: {})}):
    import app as app_module  # noqa: E402


class TestEncodeFeature(unittest.TestCase):
    def test_numeric_value(self):
        self.assertEqual(app_module._encode_feature("area", " 1500.5 "), "1500.5")

    def test_strips_units(self):
        # "200sq.ft" → 200.0
        result = app_module._encode_feature("area", "200sq.ft")
        self.assertEqual(result, "200.0")

    def test_strips_currency(self):
        result = app_module._encode_feature("price", "$1,200")
        self.assertIn("1200", result.replace(".0", ""))

    def test_region_ordinal_encoding(self):
        val = app_module._encode_feature("region", "north")
        self.assertTrue(val.isdigit(), f"Expected digit string, got {val!r}")

    def test_location_ordinal_encoding(self):
        val = app_module._encode_feature("location", "Mumbai")
        self.assertTrue(val.isdigit())


class TestValidatePayload(unittest.TestCase):
    def test_all_missing(self):
        ok, msg = app_module.validate_payload({})
        self.assertFalse(ok)
        self.assertIn("Missing required fields", msg)

    def test_partial_missing(self):
        # Provide only the first feature
        features = app_module.FEATURES
        payload = {features[0]: "42"} if features else {}
        if len(features) > 1:
            ok, msg = app_module.validate_payload(payload)
            self.assertFalse(ok)

    def test_all_present(self):
        payload = {f: "1" for f in app_module.FEATURES}
        ok, msg = app_module.validate_payload(payload)
        # May still fail on geo validation if region is in features,
        # but must not say "Missing required fields"
        if not ok:
            self.assertNotIn("Missing required fields", msg)


class TestMakePrediction(unittest.TestCase):
    def test_local_fallback_returns_string(self):
        with patch.object(app_module, "sm_runtime", None):
            result = app_module.make_prediction(["100.0", "200.0"])
        self.assertIsInstance(result, str)

    def test_local_fallback_numeric(self):
        with patch.object(app_module, "sm_runtime", None):
            result = app_module.make_prediction(["100.0", "200.0"])
        self.assertEqual(result, "150.0")

    def test_sagemaker_invocation(self):
        mock_rt = MagicMock()
        mock_rt.invoke_endpoint.return_value = {
            "Body": MagicMock(read=lambda: b"42.5")
        }
        with patch.object(app_module, "sm_runtime", mock_rt):
            result = app_module.make_prediction(["1.0", "2.0"])
        self.assertEqual(result, "42.5")
        mock_rt.invoke_endpoint.assert_called_once()


if __name__ == "__main__":
    unittest.main()
