"""
utils/feature_verifier.py  (v9 — Self-Healing)
================================================
Verifies that a downloaded CSV contains the features (columns) requested
by the user's prompt. This acts as a HARD GATE in the pipeline.

NEW in v9:
  - LLMFeatureRepairer: if a dataset almost matches (>= repair_ratio),
    apply column_mappings and pandas derivations from SearchReflector
    to fix column name discrepancies BEFORE giving up on the dataset.
  - FeatureVerifier.verify_and_repair() combines both steps.

Matching uses fuzzy substring logic:
  spec feature "bedrooms" matches CSV column "num_bedrooms" or "Bedrooms".
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FeatureVerifyResult:
    """Result of a feature verification check."""
    passed:           bool
    match_ratio:      float
    matched_features: List[str] = field(default_factory=list)
    missing_features: List[str] = field(default_factory=list)
    csv_columns:      List[str] = field(default_factory=list)
    repaired:         bool = False   # True if auto-repair was applied


class LLMFeatureRepairer:
    """
    Applies column_mappings and pandas derivations from SearchReflector
    to repair a CSV in-place, so FeatureVerifier can re-check it.

    Usage:
        repairer = LLMFeatureRepairer()
        repaired_path = repairer.repair(csv_path, repair_plan)
        # repair_plan: dict from SearchReflector.reflect_on_feature_mismatch()
    """

    def repair(self, csv_path: Path, repair_plan: dict) -> Path | None:
        """
        Apply a repair plan to a CSV and save the result.

        Parameters
        ----------
        csv_path   : path to the original CSV file
        repair_plan: dict with keys "column_mappings" and "derivations"

        Returns
        -------
        Path to the repaired CSV (same file, overwritten) or None on failure.
        """
        if not repair_plan:
            return None

        column_mappings: dict[str, str] = repair_plan.get("column_mappings", {})
        derivations: dict[str, str]     = repair_plan.get("derivations", {})
        salvageable: bool               = repair_plan.get("salvageable", False)

        if not salvageable or (not column_mappings and not derivations):
            logger.info("LLMFeatureRepairer: repair plan says not salvageable — skipping")
            return None

        try:
            df = pd.read_csv(csv_path, low_memory=False, nrows=100_000)
        except Exception as exc:
            logger.warning("LLMFeatureRepairer: cannot read CSV %s: %s", csv_path, exc)
            return None

        any_fix = False

        # Apply column renames
        rename_map: dict[str, str] = {}
        for missing_feat, existing_col in column_mappings.items():
            if existing_col in df.columns:
                rename_map[existing_col] = missing_feat
                any_fix = True
                logger.info(
                    "LLMFeatureRepairer: renaming column '%s' -> '%s'",
                    existing_col, missing_feat,
                )
        if rename_map:
            df = df.rename(columns=rename_map)

        # Apply pandas derivations
        for new_col, expression in derivations.items():
            if new_col not in df.columns:
                try:
                    # Safe eval: only access df columns
                    df[new_col] = df.eval(expression)
                    any_fix = True
                    logger.info(
                        "LLMFeatureRepairer: derived column '%s' via '%s'",
                        new_col, expression,
                    )
                except Exception as exc:
                    logger.warning(
                        "LLMFeatureRepairer: could not derive '%s' (%s): %s",
                        new_col, expression, exc,
                    )

        if not any_fix:
            logger.info("LLMFeatureRepairer: no fixes were applicable")
            return None

        try:
            df.to_csv(csv_path, index=False)
            logger.info(
                "LLMFeatureRepairer: saved repaired CSV to %s (%d rows × %d cols)",
                csv_path, len(df), len(df.columns),
            )
            return csv_path
        except Exception as exc:
            logger.warning("LLMFeatureRepairer: could not save repaired CSV: %s", exc)
            return None


class FeatureVerifier:
    """
    Check whether a CSV dataset contains columns matching the
    user-specified input features and target from the prompt spec.

    Parameters
    ----------
    config : dict
        Root config. Reads:
          collection.min_feature_match_ratio  (default 0.5)
          collection.repair_feature_match_ratio (default 0.6)
    """

    def __init__(self, config: dict) -> None:
        coll = config.get("collection", {})
        self._min_ratio    = float(coll.get("min_feature_match_ratio",    0.5))
        self._repair_ratio = float(coll.get("repair_feature_match_ratio", 0.6))
        self._repairer     = LLMFeatureRepairer()

    # ── Public API ─────────────────────────────────────────────────────────────

    def verify(self, csv_path: Path, spec: dict) -> FeatureVerifyResult:
        """
        Standard verification gate (unchanged behaviour from v8).
        Returns FeatureVerifyResult with pass/fail.
        """
        return self._run_verify(csv_path, spec)

    def verify_and_repair(
        self,
        csv_path: Path,
        spec: dict,
        repair_plan: dict | None = None,
    ) -> FeatureVerifyResult:
        """
        Extended verification with optional auto-repair.

        If initial verification fails but match_ratio >= repair_ratio,
        and a repair_plan is provided, apply the plan and re-verify.

        Parameters
        ----------
        csv_path    : path to the CSV
        spec        : parsed prompt spec
        repair_plan : output of SearchReflector.reflect_on_feature_mismatch()
                      (may be None — then behaves like verify())

        Returns
        -------
        FeatureVerifyResult with repaired=True if repair was applied.
        """
        result = self._run_verify(csv_path, spec)

        if result.passed:
            return result

        # Only attempt repair if we're "close" (above repair threshold)
        if (
            repair_plan
            and result.match_ratio >= self._repair_ratio
            and repair_plan.get("salvageable", False)
        ):
            logger.info(
                "FeatureVerifier: match_ratio=%.0f%% >= repair threshold=%.0f%% — attempting repair",
                result.match_ratio * 100,
                self._repair_ratio * 100,
            )
            repaired_path = self._repairer.repair(csv_path, repair_plan)
            if repaired_path:
                re_result = self._run_verify(repaired_path, spec)
                if re_result.passed or re_result.match_ratio > result.match_ratio:
                    re_result.repaired = True
                    logger.info(
                        "FeatureVerifier: repair succeeded — new match_ratio=%.0f%%",
                        re_result.match_ratio * 100,
                    )
                    return re_result
                logger.info(
                    "FeatureVerifier: repair did not improve match ratio (%.0f%% -> %.0f%%)",
                    result.match_ratio * 100, re_result.match_ratio * 100,
                )
        return result

    # ── Core verification logic ────────────────────────────────────────────────

    def _run_verify(self, csv_path: Path, spec: dict) -> FeatureVerifyResult:
        required = self._extract_required_features(spec)

        if not required:
            logger.debug("No features specified in spec — auto-passing verification.")
            return FeatureVerifyResult(
                passed=True, match_ratio=1.0,
                matched_features=[], missing_features=[], csv_columns=[],
            )

        try:
            df = pd.read_csv(csv_path, nrows=5)
            csv_cols       = list(df.columns)
            csv_cols_lower = [c.lower().strip() for c in csv_cols]
        except Exception as exc:
            logger.warning("Cannot read %s for feature verification: %s", csv_path, exc)
            return FeatureVerifyResult(
                passed=False, match_ratio=0.0,
                matched_features=[], missing_features=required, csv_columns=[],
            )

        matched: list[str] = []
        missing: list[str] = []

        for feature in required:
            if self._feature_matches_any_column(feature, csv_cols_lower):
                matched.append(feature)
            else:
                missing.append(feature)

        ratio  = len(matched) / len(required) if required else 1.0
        passed = ratio >= self._min_ratio

        logger.info(
            "Feature verification for %s: %d/%d matched (%.0f%%) — %s  "
            "matched=%s  missing=%s",
            csv_path.name, len(matched), len(required), ratio * 100,
            "PASS" if passed else "FAIL", matched, missing,
        )

        return FeatureVerifyResult(
            passed=passed, match_ratio=ratio,
            matched_features=matched, missing_features=missing,
            csv_columns=csv_cols,
        )

    # ── Static helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _extract_required_features(spec: dict) -> list[str]:
        features: list[str] = []
        for p in spec.get("input_params", []):
            p = str(p).strip()
            if p and p.lower() not in {f.lower() for f in features}:
                features.append(p)
        target = str(spec.get("target_param", "")).strip()
        if target and target.lower() not in {f.lower() for f in features}:
            features.append(target)
        return features

    @staticmethod
    def _feature_matches_any_column(feature: str, csv_cols_lower: list[str]) -> bool:
        feat_lower = feature.lower().strip()
        feat_norm  = re.sub(r"[^a-z0-9]", "", feat_lower)
        for col in csv_cols_lower:
            col_norm = re.sub(r"[^a-z0-9]", "", col)
            if feat_norm in col_norm or col_norm in feat_norm:
                return True
        return False
