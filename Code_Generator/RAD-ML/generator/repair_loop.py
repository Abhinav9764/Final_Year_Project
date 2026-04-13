"""
generator/repair_loop.py
=========================
Layer 5 — Repair Loop

Sends validation failures back to the LLM with precise error context
and asks it to fix ONLY the affected files — preserving working code.

Key design:
  - Repairs one file at a time (focused context = better fixes)
  - Passes the full spec + plan + current file + error list
  - Tracks attempt count per file independently
  - Stops retrying a file once it passes or max attempts exhausted
  - Reports unfixable files but doesn't crash the whole pipeline
"""
from __future__ import annotations
import logging
import re
from pathlib import Path

from generator.validator import ValidationReport

logger = logging.getLogger(__name__)

_REPAIR_PROMPT = """\
You are a senior Python engineer fixing a bug in a generated file.

=== PROJECT SPEC (summary) ===
Task         : {task}
Features     : {feature_list}
Target       : {target}
Endpoint     : {endpoint_name}
Framework    : Flask + boto3 + SageMaker

=== ARCHITECTURE PLAN (relevant excerpt) ===
{plan_excerpt}

=== FILE TO FIX: `{filename}` ===
{current_code}

=== VALIDATION ERRORS FOUND ===
{error_list}

=== YOUR TASK ===
Fix ALL the errors listed above in the file `{filename}`.
Rules:
- Fix ONLY what is broken — preserve all working code
- Return the COMPLETE corrected file (not just the changed parts)
- Production-grade: type hints, docstrings, error handling
- No markdown fences, no explanation
- Return only the corrected Python/text content
"""


class RepairLoop:
    """Repair failing files using LLM feedback."""

    def __init__(self, llm_client, project_spec: dict,
                 plan: dict, config: dict):
        self._llm       = llm_client
        self._spec      = project_spec
        self._plan      = plan
        self._max_tries = int(config.get("codegen", {})
                              .get("max_fix_attempts", 5))

    # ── public ────────────────────────────────────────────────────────────────
    def repair(self, written_files: dict[str, Path],
               validation_report: ValidationReport,
               validator_cls) -> tuple[dict[str, Path], ValidationReport]:
        """
        Attempt to repair all failing files, re-validating after each fix.

        Parameters
        ----------
        written_files      : dict[filename → Path]
        validation_report  : current ValidationReport from Validator
        validator_cls      : Validator instance (to re-run after each fix)

        Returns
        -------
        (updated written_files, final ValidationReport)
        """
        features      = self._spec.get("feature_cols",
                                        self._spec.get("features", []))
        target        = self._spec.get("target_col",
                                        self._spec.get("target", "output"))
        endpoint_name = self._spec.get("endpoint_name", "radml-endpoint")
        task          = self._spec.get("task", "ML prediction")

        # Track per-file attempt count
        attempts: dict[str, int] = {}
        report = validation_report

        while True:
            failing = report.failed_files()
            if not failing:
                logger.info("All files passed — repair loop complete.")
                break

            made_any_fix = False

            for file_report in failing:
                fname = file_report.filename
                path  = written_files.get(fname)
                if path is None or not path.exists():
                    continue

                att = attempts.get(fname, 0)
                if att >= self._max_tries:
                    logger.warning(
                        "%s still failing after %d attempts — skipping.",
                        fname, self._max_tries,
                    )
                    continue

                attempts[fname] = att + 1
                logger.info("Repairing %s (attempt %d/%d) …",
                            fname, att + 1, self._max_tries)

                fixed_code = self._fix_file(
                    filename      = fname,
                    current_code  = path.read_text(encoding="utf-8"),
                    errors        = file_report.errors,
                    features      = features,
                    target        = target,
                    endpoint_name = endpoint_name,
                    task          = task,
                )

                if fixed_code:
                    path.write_text(fixed_code, encoding="utf-8")
                    made_any_fix = True
                    logger.info("  Applied fix to %s", fname)

            if not made_any_fix:
                logger.warning("No fixes applied — breaking repair loop.")
                break

            # Re-validate all files after fixes
            report = validator_cls.validate(written_files)
            logger.info("Post-repair validation: %s", report.summary())

        return written_files, report

    # ── internals ─────────────────────────────────────────────────────────────
    def _fix_file(self, filename: str, current_code: str,
                  errors: list[str], features: list,
                  target: str, endpoint_name: str, task: str) -> str | None:
        """Ask LLM to fix a specific file. Returns fixed code or None."""
        import json

        # Build a focused plan excerpt relevant to this file
        plan_files = self._plan.get("key_functions", {})
        plan_excerpt = json.dumps(
            {filename: plan_files.get(filename, [])}, indent=2
        )

        error_text = "\n".join(f"  {i+1}. {e}"
                                for i, e in enumerate(errors))

        prompt = _REPAIR_PROMPT.format(
            task          = task,
            feature_list  = ", ".join(features),
            target        = target,
            endpoint_name = endpoint_name,
            plan_excerpt  = plan_excerpt,
            filename      = filename,
            current_code  = current_code[:6000],   # truncate to fit context
            error_list    = error_text,
        )

        try:
            raw   = self._llm.generate(prompt)
            fixed = re.sub(r"^```[a-zA-Z]*\n?", "", raw.strip(),
                           flags=re.MULTILINE)
            fixed = re.sub(r"\n?```\s*$",        "", fixed.strip(),
                           flags=re.MULTILINE)
            return fixed.strip() or None
        except Exception as exc:
            logger.error("LLM repair call failed for %s: %s", filename, exc)
            return None
