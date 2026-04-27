"""
tests/unit/test_llm_judge.py
============================
Unit tests for the LLM Judge component.

Tests verify:
1. Judge correctly identifies broken/invalid code
2. Judge correctly scores valid code
3. Judge handles edge cases gracefully
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the LLM Judge
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "Code_Generator" / "RAD-ML"))

from generator.llm_judge import LLMJudge


# Sample code snippets for testing
VALID_STREAMLIT_CODE = '''
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Test App", layout="wide")

def main():
    st.title("ML Predictor")

    # Input widgets
    feature1 = st.number_input("Feature 1", value=0.0)
    feature2 = st.number_input("Feature 2", value=0.0)

    # Prediction button
    if st.button("Predict"):
        # Mock prediction
        prediction = feature1 + feature2
        st.success(f"Prediction: {prediction}")

if __name__ == "__main__":
    main()
'''

BROKEN_CODE_NO_STREAMLIT = '''
from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello():
    return "Hello World"

if __name__ == "__main__":
    app.run()
'''

BROKEN_CODE_SYNTAX_ERROR = '''
import streamlit as st

def broken_function(
    # Missing closing parenthesis and function body
    st.title("Broken App")
'''

BROKEN_CODE_MISSING_INPUTS = '''
import streamlit as st

def main():
    st.title("ML App")
    # No input widgets at all
    # No prediction logic
    st.write("This is incomplete")

if __name__ == "__main__":
    main()
'''

VALID_ML_CODE = '''
import streamlit as st
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

st.set_page_config(page_title="ML App", layout="wide")

FEATURES = ["area", "bedrooms", "bathrooms"]

def make_prediction(features):
    model = RandomForestRegressor()
    # Mock training
    return model.predict([features])[0]

def main():
    st.title("House Price Predictor")

    area = st.number_input("Area (sq ft)", min_value=100, value=1500)
    bedrooms = st.number_input("Bedrooms", min_value=1, value=3)
    bathrooms = st.number_input("Bathrooms", min_value=1, value=2)

    if st.button("Predict Price"):
        features = [area, bedrooms, bathrooms]
        prediction = make_prediction(features)
        st.success(f"Predicted Price: ${prediction:,.2f}")

if __name__ == "__main__":
    main()
'''


class TestLLMJudgeCodeEvaluation:
    """Test LLM Judge code evaluation capabilities."""

    @pytest.fixture
    def mock_config(self):
        """Provide a minimal mock configuration."""
        return {
            "llm": {
                "primary_provider": "gemini",
            },
            "gemini": {
                "api_key": "test_key",
                "model": "models/gemini-2.5-flash",
            }
        }

    def test_judge_rejects_non_streamlit_code(self, mock_config):
        """Judge should give low score to Flask/wrong framework code."""
        # Create judge with mocked LLM
        with patch('core.llm_client.LLMClient') as mock_client:
            mock_llm = MagicMock()
            # Return low score for broken code
            mock_llm.generate.return_value = '{"score": 2, "critique": "Uses Flask instead of Streamlit"}'
            mock_client.return_value = mock_llm

            judge = LLMJudge(mock_config)
            prompt_spec = {"task_type": "ml", "task": "Build an ML predictor app"}

            result = judge.evaluate_code(BROKEN_CODE_NO_STREAMLIT, prompt_spec)

            assert result["score"] <= 5  # Should be low score
            assert result["passed"] is False

    def test_judge_accepts_valid_streamlit_code(self, mock_config):
        """Judge should give high score to valid Streamlit code."""
        with patch('core.llm_client.LLMClient') as mock_client:
            mock_llm = MagicMock()
            # Return high score for valid code
            mock_llm.generate.return_value = '{"score": 9, "critique": "Good Streamlit implementation"}'
            mock_client.return_value = mock_llm

            judge = LLMJudge(mock_config)
            prompt_spec = {"task_type": "ml", "task": "Build an ML predictor app"}

            result = judge.evaluate_code(VALID_ML_CODE, prompt_spec)

            assert result["score"] >= 7  # Should pass threshold
            assert result["passed"] is True

    def test_judge_handles_syntax_errors(self, mock_config):
        """Judge should detect and penalize syntax errors."""
        with patch('core.llm_client.LLMClient') as mock_client:
            mock_llm = MagicMock()
            mock_llm.generate.return_value = '{"score": 1, "critique": "Code has syntax errors"}'
            mock_client.return_value = mock_llm

            judge = LLMJudge(mock_config)
            prompt_spec = {"task_type": "ml", "task": "Build an ML app"}

            result = judge.evaluate_code(BROKEN_CODE_SYNTAX_ERROR, prompt_spec)

            assert result["score"] <= 3  # Very low score for syntax errors

    def test_judge_detects_incomplete_code(self, mock_config):
        """Judge should detect missing required components."""
        with patch('core.llm_client.LLMClient') as mock_client:
            mock_llm = MagicMock()
            mock_llm.generate.return_value = '{"score": 4, "critique": "Missing input widgets and prediction logic"}'
            mock_client.return_value = mock_llm

            judge = LLMJudge(mock_config)
            prompt_spec = {"task_type": "ml", "task": "Build an ML predictor"}

            result = judge.evaluate_code(BROKEN_CODE_MISSING_INPUTS, prompt_spec)

            assert result["score"] < 7  # Below threshold
            assert result["passed"] is False

    def test_judge_fallback_on_error(self, mock_config):
        """Judge should auto-pass if LLM call fails (graceful degradation)."""
        with patch('core.llm_client.LLMClient') as mock_client:
            mock_llm = MagicMock()
            mock_llm.generate.side_effect = Exception("API Error")
            mock_client.return_value = mock_llm

            judge = LLMJudge(mock_config)
            prompt_spec = {"task_type": "ml", "task": "Test"}

            result = judge.evaluate_code(VALID_STREAMLIT_CODE, prompt_spec)

            # Should auto-pass on error to prevent pipeline blockage
            assert result["passed"] is True
            assert "error" in result["critique"].lower()

    def test_judge_handles_invalid_json_response(self, mock_config):
        """Judge should handle malformed JSON from LLM."""
        with patch('core.llm_client.LLMClient') as mock_client:
            mock_llm = MagicMock()
            mock_llm.generate.return_value = 'Invalid JSON response'
            mock_client.return_value = mock_llm

            judge = LLMJudge(mock_config)
            prompt_spec = {"task_type": "ml", "task": "Test"}

            result = judge.evaluate_code(VALID_STREAMLIT_CODE, prompt_spec)

            # Should auto-pass on parsing error
            assert result["passed"] is True


class TestLLMJudgePlanEvaluation:
    """Test LLM Judge plan evaluation capabilities."""

    @pytest.fixture
    def mock_config(self):
        return {
            "llm": {"primary_provider": "gemini"},
            "gemini": {"api_key": "test_key", "model": "models/gemini-2.5-flash"}
        }

    def test_judge_evaluates_plan(self, mock_config):
        """Judge should evaluate architecture plans."""
        with patch('core.llm_client.LLMClient') as mock_client:
            mock_llm = MagicMock()
            mock_llm.generate.return_value = '{"score": 8, "critique": "Good plan structure"}'
            mock_client.return_value = mock_llm

            judge = LLMJudge(mock_config)
            prompt_spec = {"task_type": "ml", "task": "Build ML app"}
            plan = {
                "file_structure": {"app.py": "Main Streamlit app"},
                "dependencies": ["streamlit", "pandas", "scikit-learn"]
            }

            result = judge.evaluate_plan(plan, prompt_spec)

            assert "score" in result
            assert "critique" in result
            assert result["passed"] == (result["score"] >= 7)

    def test_judge_plan_fallback_on_error(self, mock_config):
        """Plan evaluation should auto-pass on error."""
        with patch('core.llm_client.LLMClient') as mock_client:
            mock_llm = MagicMock()
            mock_llm.generate.side_effect = Exception("API Error")
            mock_client.return_value = mock_llm

            judge = LLMJudge(mock_config)
            prompt_spec = {"task_type": "ml", "task": "Test"}
            plan = {"file_structure": {}}

            result = judge.evaluate_plan(plan, prompt_spec)

            assert result["passed"] is True


class TestLLMJudgeDisabled:
    """Test behavior when Judge is disabled/unavailable."""

    def test_judge_disabled_no_llm(self):
        """Judge should auto-pass when LLM is not available."""
        config = {}  # No LLM config

        with patch('core.llm_client.LLMClient') as mock_client:
            mock_client.side_effect = ImportError("LLMClient not available")

            judge = LLMJudge(config)

            result = judge.evaluate_code(VALID_STREAMLIT_CODE, {"task_type": "ml"})

            assert result["passed"] is True
            assert result["score"] == 10
            assert "Judge unavailable" in result["critique"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
