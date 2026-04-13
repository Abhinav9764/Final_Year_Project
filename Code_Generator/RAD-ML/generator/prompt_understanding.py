"""
generator/prompt_understanding.py
===================================
Layer 1 — Prompt Understanding

Converts the raw user prompt + parsed spec into a rich, structured
ProjectSpec JSON that every downstream layer consumes.

Example output:
{
  "task":         "movie recommendation system",
  "language":     "Python",
  "framework":    "Streamlit",
  "task_type":    "clustering",          # regression | classification | clustering
  "model_type":   "content-based filtering",
  "features":     ["genre", "language", "rating"],
  "target":       "recommended_movies",
  "deliverables": ["app.py", "train.py", "requirements.txt", "README.md", "tests/"],
  "constraints":  ["must use SageMaker endpoint", "no external CSS"],
  "coding_style": "production",          # production | academic | minimal
  "dataset_info": { ... }               # from db_results
}
"""
from __future__ import annotations
import json
import logging
import re

logger = logging.getLogger(__name__)

_UNDERSTANDING_PROMPT = """\
You are a senior ML solutions architect.

Convert the following user prompt and context into a structured JSON project specification.

=== USER PROMPT ===
{prompt}

=== PARSED CONTEXT ===
Task type       : {task_type}
Input features  : {input_params}
Prediction target: {target_param}
Dataset columns : {dataset_columns}
Dataset rows    : {row_count}
SageMaker endpoint: {endpoint_name}
AWS region      : {aws_region}

=== INSTRUCTIONS ===
Produce a JSON object with EXACTLY these keys:
- "task"         : short task description (≤10 words)
- "language"     : always "Python"
- "framework"    : "Streamlit"
- "task_type"    : one of "regression", "classification", "clustering"
- "model_type"   : brief ML model description
- "features"     : list of the actual input feature column names from the dataset
- "target"       : the prediction target column name
- "deliverables" : list of files to generate — always include:
                   ["app.py", "train.py", "predictor.py", "requirements.txt", "README.md", "tests/test_app.py", "templates/index.html"]
- "constraints"  : list of hard requirements
- "coding_style" : "production" (type hints, docstrings, logging, error handling)
- "endpoint_name": the SageMaker endpoint name
{output_desc_instruction}

Return ONLY valid JSON. No markdown. No explanation.
"""


class PromptUnderstandingLayer:
    """Convert raw prompt + spec → structured ProjectSpec dict."""

    def __init__(self, llm_client):
        self._llm = llm_client

    def build_spec(self, prompt: str, parsed_spec: dict,
                   dataset_info: dict, sm_meta: dict,
                   preprocess_result: dict, config: dict) -> dict:
        """
        Parameters
        ----------
        prompt           : original user prompt
        parsed_spec      : output of PromptParser.parse()
        dataset_info     : dataset section from db_results
        sm_meta          : SageMaker metadata
        preprocess_result: output of DataPreprocessor.preprocess()
        config           : root config dict

        Returns
        -------
        ProjectSpec dict (always valid even if LLM fails — falls back to rule-based)
        """
        aws_region    = config.get("aws", {}).get("region", "us-east-1")
        endpoint_name = sm_meta.get("endpoint_name", "radml-endpoint")
        feature_cols  = preprocess_result.get("feature_cols", parsed_spec.get("input_params", []))
        target_col    = preprocess_result.get("target_col",   parsed_spec.get("target_param", "output"))

        out_desc = parsed_spec.get("output_description", "")
        out_desc_instruction = f'- "output_description": "{out_desc}"' if out_desc else ""

        prompt_text = _UNDERSTANDING_PROMPT.format(
            prompt           = prompt,
            task_type        = parsed_spec.get("task_type", "regression"),
            input_params     = ", ".join(parsed_spec.get("input_params", [])),
            target_param     = target_col,
            dataset_columns  = ", ".join(dataset_info.get("columns", [])[:20]),
            row_count        = dataset_info.get("row_count", 0),
            endpoint_name    = endpoint_name,
            aws_region       = aws_region,
            output_desc_instruction = out_desc_instruction
        )

        try:
            raw  = self._llm.generate(prompt_text)
            spec = self._parse_json(raw)
            # Ensure critical fields are never empty
            spec.setdefault("features",      feature_cols)
            spec.setdefault("target",        target_col)
            spec.setdefault("endpoint_name", endpoint_name)
            spec.setdefault("aws_region",    aws_region)
            spec.setdefault("task_type",     parsed_spec.get("task_type", "regression"))
            spec.setdefault("requested_features", parsed_spec.get("input_params", []))
            spec["feature_cols"] = feature_cols   # always use preprocessor's columns
            spec["target_col"]   = target_col
            if out_desc:
                spec["output_description"] = out_desc
            logger.info("ProjectSpec built: task=%s  features=%d  deliverables=%d",
                        spec.get("task"), len(spec.get("features", [])),
                        len(spec.get("deliverables", [])))
            return spec
        except Exception as exc:
            logger.warning("LLM spec generation failed (%s) — using rule-based fallback", exc)
            return self._fallback_spec(parsed_spec, feature_cols, target_col,
                                       endpoint_name, aws_region, config)

    # ── internals ─────────────────────────────────────────────────────────────
    @staticmethod
    def _parse_json(text: str) -> dict:
        # Strip markdown fences
        text = re.sub(r"^```[a-z]*\n?", "", text.strip(), flags=re.MULTILINE)
        text = re.sub(r"\n?```$",        "", text.strip(), flags=re.MULTILINE)
        return json.loads(text.strip())

    @staticmethod
    def _fallback_spec(parsed_spec: dict, feature_cols: list, target_col: str,
                       endpoint_name: str, aws_region: str, config: dict) -> dict:
        task_type = parsed_spec.get("task_type", "regression")
        return {
            "task":          parsed_spec.get("raw", "ML prediction")[:60],
            "language":      "Python",
            "framework":     "Streamlit",
            "task_type":     task_type,
            "model_type":    {"regression": "XGBoost regressor",
                              "classification": "XGBoost classifier",
                              "clustering": "similarity model"}.get(task_type, "XGBoost"),
            "features":      feature_cols,
            "feature_cols":  feature_cols,
            "target":        target_col,
            "target_col":    target_col,
            "deliverables":  ["app.py", "train.py", "predictor.py",
                              "requirements.txt", "README.md", "tests/test_app.py",
                              "templates/index.html"],
            "constraints":   ["use SageMaker endpoint for inference",
                              "production-grade code with error handling"],
            "coding_style":  "production",
            "endpoint_name": endpoint_name,
            "aws_region":    aws_region,
            "requested_features": parsed_spec.get("input_params", []),
            "output_description": parsed_spec.get("output_description", ""),
        }
