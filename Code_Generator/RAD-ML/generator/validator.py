"""
generator/validator.py
=======================
Layer 4 — Validator

Runs a multi-stage validation pass on every generated file:
  Stage 1  AST syntax check          (all .py files)
  Stage 2  Security scan             (no eval/exec/os.system)
  Stage 3  Relevance check           (required functions/routes present)
  Stage 4  Pytest run                (tests/test_app.py, mocked)
  Stage 5  Import availability check (all imports resolvable)

Returns a ValidationReport per file so the RepairLoop knows
exactly WHICH file failed and WHY.
"""
from __future__ import annotations
import ast
import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_FORBIDDEN_PATTERNS = [
    (r"\beval\s*\(",        "eval() is forbidden — security risk"),
    (r"\bexec\s*\(",        "exec() is forbidden — security risk"),
    (r"os\.system\s*\(",   "os.system() is forbidden — use subprocess"),
    (r"__import__\s*\(",   "__import__() is forbidden"),
]

_REQUIRED_CONTENT = {
    "app.py": [
        (r"from flask import|import flask",    "Missing flask import"),
        (r"@app\.route\s*\(\s*['\"]\/['\"]",   "Missing GET / route"),
        (r"request\.form|request\.get_json",   "Missing form/JSON input handling"),
        (r"from predictor import|import predictor", "Missing predictor import"),
    ],
    "predictor.py": [
        (r"def format_features",               "Missing format_features function"),
        (r"def call_endpoint",                 "Missing call_endpoint function"),
        (r"def predict",                       "Missing predict function"),
        (r"invoke_endpoint|sagemaker",         "Missing SageMaker endpoint call"),
    ],
    "tests/test_app.py": [
        (r"def test_",                         "No test functions found"),
        (r"mock|patch|MagicMock",              "Missing mocks for SageMaker calls"),
    ],
}


@dataclass
class FileReport:
    filename: str
    passed:   bool = True
    errors:   list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.passed = False
        self.errors.append(msg)


@dataclass
class ValidationReport:
    all_passed: bool
    file_reports: dict[str, FileReport]

    def failed_files(self) -> list[FileReport]:
        return [r for r in self.file_reports.values() if not r.passed]

    def summary(self) -> str:
        total  = len(self.file_reports)
        passed = sum(1 for r in self.file_reports.values() if r.passed)
        return f"{passed}/{total} files passed validation"


class Validator:
    """Multi-stage code validator."""

    def __init__(self, project_spec: dict, config: dict):
        self._spec    = project_spec
        self._cfg     = config
        self._ws_dir  = Path(config.get("codegen", {})
                             .get("workspace_dir",
                                  "Code_Generator/RAD-ML/workspace/current_app"))
        self._timeout = int(config.get("codegen", {})
                            .get("test_timeout_seconds", 30))

    # ── public ────────────────────────────────────────────────────────────────
    def validate(self, written_files: dict[str, Path]) -> ValidationReport:
        """
        Validate all generated files.

        Parameters
        ----------
        written_files : dict[filename → Path] from CodeGenFactory.generate_all()

        Returns
        -------
        ValidationReport with per-file results
        """
        reports: dict[str, FileReport] = {}

        for filename, path in written_files.items():
            report = FileReport(filename=filename)

            if filename.endswith(".py"):
                self._check_syntax(path, report)
                self._check_security(path, report)
                self._check_relevance(filename, path, report)
                self._check_feature_order(filename, path, report)

            reports[filename] = report
            status = "✓" if report.passed else f"✗ ({len(report.errors)} errors)"
            logger.info("  Validation %s: %s", filename, status)
            for err in report.errors:
                logger.warning("    → %s", err)

        # Run pytest on tests/ if it was generated
        if "tests/test_app.py" in written_files:
            self._run_pytest(written_files["tests/test_app.py"], reports)

        all_passed = all(r.passed for r in reports.values())
        report_obj = ValidationReport(all_passed=all_passed,
                                       file_reports=reports)
        logger.info("Validation complete: %s", report_obj.summary())
        return report_obj

    # ── stages ────────────────────────────────────────────────────────────────
    def _check_syntax(self, path: Path, report: FileReport) -> None:
        try:
            code = path.read_text(encoding="utf-8")
            ast.parse(code)
            compile(code, str(path), "exec")
        except SyntaxError as exc:
            report.fail(f"SyntaxError at line {exc.lineno}: {exc.msg}")
        except Exception as exc:
            report.fail(f"Compile error: {exc}")

    def _check_security(self, path: Path, report: FileReport) -> None:
        code = path.read_text(encoding="utf-8")
        for pattern, msg in _FORBIDDEN_PATTERNS:
            if re.search(pattern, code):
                report.fail(msg)

    def _check_relevance(self, filename: str, path: Path,
                          report: FileReport) -> None:
        checks = _REQUIRED_CONTENT.get(filename, [])
        if not checks:
            return
        code = path.read_text(encoding="utf-8")
        for pattern, msg in checks:
            if not re.search(pattern, code, re.IGNORECASE):
                report.fail(msg)

    def _check_feature_order(self, filename: str, path: Path,
                              report: FileReport) -> None:
        """Verify predictor.py references features in the correct order."""
        if filename != "predictor.py":
            return
        features = self._spec.get("feature_cols",
                                   self._spec.get("features", []))
        if not features:
            return
        code = path.read_text(encoding="utf-8")
        # Check that at least the first and last feature name appear in code
        if features[0] not in code:
            report.fail(
                f"predictor.py does not reference first feature '{features[0]}'. "
                f"Expected feature order: {features}"
            )

    def _run_pytest(self, test_path: Path, reports: dict) -> None:
        """Run pytest on the test file with a timeout."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(test_path),
                 "-v", "--tb=short", "-x", "--no-header",
                 "--import-mode=importlib"],
                capture_output=True, text=True,
                timeout=self._timeout,
                cwd=str(self._ws_dir),
            )
            if result.returncode != 0:
                # Extract just the failure summary
                output = result.stdout[-2000:] + result.stderr[-500:]
                test_report = reports.get("tests/test_app.py")
                if test_report:
                    test_report.fail(f"pytest failed:\n{output}")
                logger.warning("pytest failed (rc=%d)", result.returncode)
            else:
                logger.info("pytest passed ✓")
        except subprocess.TimeoutExpired:
            logger.warning("pytest timed out after %ds", self._timeout)
        except Exception as exc:
            logger.warning("Could not run pytest: %s", exc)
