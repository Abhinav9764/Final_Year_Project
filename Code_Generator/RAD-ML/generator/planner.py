"""
generator/planner.py
=====================
Layer 2 — Planner

Takes the ProjectSpec and asks the LLM to produce a full architecture plan
BEFORE writing any code. This is the single biggest quality improvement —
the model plans the structure first, then generates file by file.

Plan output:
{
  "architecture_overview": str,
  "file_structure": { "filename": "purpose description", ... },
  "key_functions": { "filename": ["func1(args) -> return: purpose", ...], ... },
  "dependencies": ["flask", "boto3", ...],
  "validation_strategy": str,
  "edge_cases": [str, ...],
  "feature_order_note": str,   # how features map to endpoint CSV
}
"""
from __future__ import annotations
import json
import logging
import re

logger = logging.getLogger(__name__)

_PLAN_PROMPT = """\
You are a senior software architect planning a production ML inference application.

=== PROJECT SPEC ===
{spec_json}

=== YOUR TASK ===
Before any code is written, produce a complete architecture plan.

Return a JSON object with these keys:
- "architecture_overview"  : 2-3 sentence description of how the system works
- "file_structure"         : dict mapping each filename to its responsibility (one sentence each)
- "key_functions"          : dict mapping filename to list of function signatures with purpose
- "dependencies"           : list of pip packages needed (exact names, no versions)
- "validation_strategy"    : how to validate the generated code works correctly
- "edge_cases"             : list of error conditions that must be handled
- "feature_order_note"     : how the {n_features} input features map to the SageMaker endpoint CSV row

Be specific. Reference the actual feature names: {feature_list}
The target is: {target}

Return ONLY valid JSON. No markdown. No explanation.
"""


class Planner:
    """Produce an architecture plan from a ProjectSpec."""

    def __init__(self, llm_client):
        self._llm = llm_client

    def plan(self, project_spec: dict) -> dict:
        """
        Parameters
        ----------
        project_spec : output of PromptUnderstandingLayer.build_spec()

        Returns
        -------
        Architecture plan dict. Falls back gracefully if LLM fails.
        """
        features    = project_spec.get("features", project_spec.get("feature_cols", []))
        target      = project_spec.get("target",   project_spec.get("target_col", "output"))
        project_spec.get("deliverables", [])

        prompt = _PLAN_PROMPT.format(
            spec_json    = json.dumps(project_spec, indent=2),
            n_features   = len(features),
            feature_list = ", ".join(features),
            target       = target,
        )

        try:
            raw  = self._llm.generate(prompt)
            plan = self._parse_json(raw)
            logger.info("Architecture plan produced: %d files, %d dependencies",
                        len(plan.get("file_structure", {})),
                        len(plan.get("dependencies", [])))
            return plan
        except Exception as exc:
            logger.warning("Planner LLM failed (%s) — using default plan", exc)
            return self._default_plan(project_spec, features, target)

    # ── internals ─────────────────────────────────────────────────────────────
    @staticmethod
    def _parse_json(text: str) -> dict:
        text = re.sub(r"^```[a-z]*\n?", "", text.strip(), flags=re.MULTILINE)
        text = re.sub(r"\n?```$",        "", text.strip(), flags=re.MULTILINE)
        return json.loads(text.strip())

    @staticmethod
    def _default_plan(spec: dict, features: list, target: str) -> dict:
        endpoint = spec.get("endpoint_name", "radml-endpoint")
        spec.get("aws_region", "us-east-1")
        spec.get("flask_port", 7000)
        return {
            "architecture_overview": (
                f"Flask web application that accepts {len(features)} input features "
                f"via an HTML form, sends them as a CSV row to the SageMaker endpoint "
                f"'{endpoint}', and displays the predicted {target}. "
                f"The HTML UI is served from templates/index.html."
            ),
            "file_structure": {
                "app.py":              "Flask application: routes, form rendering, prediction endpoint",
                "templates/index.html": "Jinja2 HTML template for the dynamic web interface and modern styling",
                "predictor.py":        "SageMaker inference helper: format features, call endpoint, parse response",
                "train.py":            "Training utilities: data loading from S3, preprocessing, metrics",
                "requirements.txt":    "Pinned Python dependencies",
                "README.md":           "Setup, usage, and API documentation",
                "tests/test_app.py":   "Unit tests for predictor and Flask routes",
            },
            "key_functions": {
                "app.py": [
                    "index() -> str: render templates/index.html",
                    "predict() -> str: process form POST, call predictor, render result in templates/index.html",
                ],
                "templates/index.html": [
                    "Provide a properly styled HTML5 document structure",
                    f"Include a form with inputs for all {len(features)} model features",
                ],
                "predictor.py": [
                    f"format_features(inputs: dict) -> str: convert {features} to CSV row in correct order",
                    "call_endpoint(csv_row: str, endpoint: str, region: str) -> float: invoke SageMaker",
                    f"predict({', '.join(f'{f}: float' for f in features[:3])}, ...) -> dict: full prediction pipeline",
                ],
                "train.py": [
                    "load_from_s3(s3_uri: str) -> pd.DataFrame: load training data",
                    "compute_metrics(y_true, y_pred, task_type: str) -> dict: evaluation metrics",
                ],
                "tests/test_app.py": [
                    "test_format_features_correct_order(): verify CSV column order",
                    "test_predict_returns_dict(): mock endpoint call",
                    "test_index_route_200(): Flask route smoke test",
                ],
            },
            "dependencies": ["flask", "boto3", "pandas", "numpy"],
            "validation_strategy": (
                "1. AST parse each file. "
                "2. Run unit tests with mocked SageMaker endpoint. "
                "3. Check feature order matches preprocessor order. "
                "4. Lint with ruff."
            ),
            "edge_cases": [
                "Non-numeric form input → 400 error with helpful message",
                "SageMaker endpoint not found → 503 error",
                "Missing form fields → validation error shown in UI",
                "Negative or out-of-range input values → warn but proceed",
            ],
            "feature_order_note": (
                f"Features must be passed to the endpoint as a comma-separated "
                f"CSV string in EXACTLY this order: {', '.join(features)}"
            ),
        }
