"""
Data_Collection_Agent/brain/reflection.py
==========================================
LLM-powered failure analysis and search strategy refinement.

When the data collection pipeline fails (no datasets found, or all downloaded
datasets fail feature verification), the SearchReflector is called.  It sends
the failure context to the LLM and asks for a revised search strategy.

The LLM returns a structured JSON object with:
  - revised_keywords  : list of new, broader search terms
  - drop_constraints  : list of constraints to relax (region, features, etc.)
  - reasoning         : plain-English explanation of the failure

The SearchReflector then patches the spec so the main loop can retry.

Usage:
    from dca_brain.reflection import SearchReflector

    reflector = SearchReflector(config)
    revised_spec = reflector.reflect_on_search_failure(spec, failure_reason)
    revised_spec = reflector.reflect_on_feature_mismatch(spec, csv_columns, missing_features)
"""
from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Path setup for LLMClient import ───────────────────────────────────────────
_HERE         = Path(__file__).resolve().parent.parent          # Data_Collection_Agent/
_PROJECT_ROOT = _HERE.parent                                     # RAD-ML-v8/
_CG_CORE      = _PROJECT_ROOT / "Code_Generator" / "RAD-ML"    # has core/llm_client.py

for _p in (str(_HERE), str(_PROJECT_ROOT), str(_CG_CORE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ── Prompt templates ──────────────────────────────────────────────────────────

_SEARCH_FAILURE_PROMPT = """\
You are a data science search strategist.

The data collection agent failed to find any usable datasets after searching
multiple providers (Kaggle, OpenML, UCI, HuggingFace).

=== ORIGINAL REQUEST ===
Intent:      {intent}
Task type:   {task_type}
Domain:      {domain}
Keywords tried: {keywords}
Input features: {input_params}
Target:      {target_param}
Failure reason: {failure_reason}

=== YOUR JOB ===
The search was likely too specific or used the wrong terminology.
Generate a revised search strategy that is broader and more likely to succeed.

Respond with ONLY valid JSON (no markdown fences):
{{
  "revised_keywords": ["keyword1", "keyword2", "keyword3"],
  "alternative_domains": ["domain1", "domain2"],
  "drop_constraints": ["constraint to relax, e.g. 'India region'"],
  "reasoning": "Brief explanation of why the original failed and what to try instead"
}}
"""

_FEATURE_MISMATCH_PROMPT = """\
You are a data engineering expert.

A downloaded dataset was rejected because its column names don't match what
the user asked for.  Your job is to suggest how to salvage this dataset.

=== USER'S REQUEST ===
Input features needed: {input_params}
Target variable needed: {target_param}

=== DATASET COLUMN NAMES ===
{csv_columns}

=== MISSING FEATURES ===
{missing_features}

=== YOUR JOB ===
1. Check if any "missing features" can be mapped to existing column names
   (e.g. "bhk" → "BHK_or_Rk", "price" → "Rent", etc.)
2. Check if any missing feature can be derived from existing columns.
3. If nothing can be done, say so.

Respond with ONLY valid JSON (no markdown fences):
{{
  "column_mappings": {{"missing_feature": "existing_column_name"}},
  "derivations": {{"new_col_name": "pandas expression using existing columns"}},
  "salvageable": true,
  "reasoning": "Why this dataset is or isn't usable"
}}
"""


class SearchReflector:
    """
    LLM-powered reflection module for the self-learning data collection agent.

    Two reflection modes:
      1. reflect_on_search_failure  — called when search finds 0 results
      2. reflect_on_feature_mismatch — called when downloads fail verification

    Falls back gracefully (returns original spec) if LLM is unavailable.
    """

    def __init__(self, config: dict) -> None:
        self._config = config
        self._enabled = True
        self._llm = None
        try:
            from core.llm_client import LLMClient  # type: ignore
            self._llm = LLMClient(config)
            logger.info("SearchReflector: LLMClient ready")
        except Exception as exc:
            logger.warning(
                "SearchReflector: LLMClient unavailable (%s) — reflection disabled", exc
            )
            self._enabled = False

    # ── Public API ─────────────────────────────────────────────────────────────

    def reflect_on_search_failure(
        self, spec: dict, failure_reason: str
    ) -> dict:
        """
        Analyze a search failure and return a revised spec with broader keywords.

        If the LLM is unavailable, applies simple rule-based broadening instead.
        Returns the (potentially modified) spec always — never raises.
        """
        logger.info("SearchReflector: reflecting on search failure — %s", failure_reason[:80])

        if self._enabled and self._llm is not None:
            revised = self._llm_reflect_search(spec, failure_reason)
            if revised:
                return self._apply_search_revision(spec, revised)

        # Fallback: rule-based broadening (no LLM)
        return self._rule_based_search_broadening(spec)

    def reflect_on_feature_mismatch(
        self,
        spec: dict,
        csv_columns: list[str],
        missing_features: list[str],
    ) -> dict | None:
        """
        Analyze a feature mismatch and return a repair plan or None.

        Returns a dict with:
          - "column_mappings": {missing_feature: existing_col}
          - "derivations":     {new_col: pandas_expression}
          - "salvageable":     bool
        Returns None if the LLM is unavailable or repair is impossible.
        """
        if not missing_features:
            return {"column_mappings": {}, "derivations": {}, "salvageable": True, "reasoning": "No missing features."}

        logger.info(
            "SearchReflector: reflecting on feature mismatch — missing=%s  csv_cols=%s",
            missing_features[:5], csv_columns[:8],
        )

        if self._enabled and self._llm is not None:
            return self._llm_reflect_features(spec, csv_columns, missing_features)

        # Fallback: fuzzy self-matching without LLM
        return self._rule_based_feature_repair(missing_features, csv_columns)

    # ── LLM reflection internals ───────────────────────────────────────────────

    def _llm_reflect_search(self, spec: dict, failure_reason: str) -> dict | None:
        prompt = _SEARCH_FAILURE_PROMPT.format(
            intent=spec.get("intent", "ml_model"),
            task_type=spec.get("task_type", "regression"),
            domain=spec.get("domain", ""),
            keywords=spec.get("keywords", []),
            input_params=spec.get("input_params", []),
            target_param=spec.get("target_param", ""),
            failure_reason=failure_reason[:400],
        )
        try:
            raw = self._llm.generate(prompt)  # type: ignore[union-attr]
            return _parse_json(raw)
        except Exception as exc:
            logger.warning("SearchReflector LLM call failed: %s", exc)
            return None

    def _llm_reflect_features(
        self,
        spec: dict,
        csv_columns: list[str],
        missing_features: list[str],
    ) -> dict | None:
        prompt = _FEATURE_MISMATCH_PROMPT.format(
            input_params=spec.get("input_params", []),
            target_param=spec.get("target_param", ""),
            csv_columns=csv_columns[:30],
            missing_features=missing_features,
        )
        try:
            raw = self._llm.generate(prompt)  # type: ignore[union-attr]
            result = _parse_json(raw)
            return result
        except Exception as exc:
            logger.warning("SearchReflector LLM feature reflect failed: %s", exc)
            return None

    # ── Spec patching ──────────────────────────────────────────────────────────

    @staticmethod
    def _apply_search_revision(spec: dict, revision: dict) -> dict:
        """
        Merge the LLM's revised strategy into the spec dict.
        Adds new keywords without removing old ones (union).
        """
        revised = dict(spec)  # shallow copy

        # Merge new keywords at the front (higher priority)
        new_kw = revision.get("revised_keywords", [])
        existing = set(revised.get("keywords", []))
        merged = new_kw + [k for k in revised.get("keywords", []) if k not in set(new_kw)]
        revised["keywords"] = list(dict.fromkeys(merged))[:8]

        # Add alternative domains to fallback search
        alt_domains = revision.get("alternative_domains", [])
        if alt_domains:
            revised["_alt_domains"] = alt_domains

        # Record what we're dropping for the logs
        drops = revision.get("drop_constraints", [])
        if drops:
            revised["_dropped_constraints"] = drops
            logger.info("SearchReflector: relaxing constraints — %s", drops)

        reasoning = revision.get("reasoning", "")
        if reasoning:
            revised["_reflection_reasoning"] = reasoning
            logger.info("SearchReflector reasoning: %s", reasoning[:160])

        return revised

    # ── Rule-based fallbacks (no LLM) ─────────────────────────────────────────

    @staticmethod
    def _rule_based_search_broadening(spec: dict) -> dict:
        """
        Simple broadening heuristics when LLM is unavailable.
        Strips location constraints, expands to generic task terms.
        """
        revised = dict(spec)
        task_generic = {
            "regression":     ["tabular prediction", "supervised regression"],
            "classification": ["tabular classification", "binary classification"],
            "clustering":     ["unsupervised clustering", "customer segmentation"],
            "chatbot":        ["text qa", "question answering"],
        }
        generic_kw = task_generic.get(spec.get("task_type", ""), ["tabular dataset"])
        existing = list(spec.get("keywords", []))
        revised["keywords"] = list(dict.fromkeys(generic_kw + existing))[:8]
        revised["_dropped_constraints"] = ["region constraint dropped (rule-based broadening)"]
        logger.info("SearchReflector: applied rule-based broadening (no LLM)")
        return revised

    @staticmethod
    def _rule_based_feature_repair(
        missing_features: list[str], csv_columns: list[str]
    ) -> dict:
        """
        Attempt fuzzy mapping without LLM — tokenize and match substrings.
        """
        mappings: dict[str, str] = {}
        cols_lower = [(c, re.sub(r"[^a-z0-9]", "", c.lower())) for c in csv_columns]
        for feat in missing_features:
            feat_norm = re.sub(r"[^a-z0-9]", "", feat.lower())
            for orig_col, col_norm in cols_lower:
                if feat_norm in col_norm or col_norm in feat_norm:
                    mappings[feat] = orig_col
                    break
        salvageable = len(mappings) >= max(1, len(missing_features) // 2)
        return {
            "column_mappings": mappings,
            "derivations": {},
            "salvageable": salvageable,
            "reasoning": f"Rule-based fuzzy match: found {len(mappings)}/{len(missing_features)} mappings",
        }


# ── JSON parsing helper ────────────────────────────────────────────────────────

def _parse_json(text: str) -> dict:
    """Strip markdown fences and parse JSON."""
    text = text.strip()
    text = re.sub(r"^```[a-z]*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```$", "", text, flags=re.MULTILINE)
    return json.loads(text.strip())
