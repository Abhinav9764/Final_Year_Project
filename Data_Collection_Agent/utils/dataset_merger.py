"""
utils/dataset_merger.py
========================
Merges multiple CSVs into one when no single dataset meets the row threshold.

Strategy
--------
1. Normalise all column names (lowercase, underscores).
2. If the best-scored CSV has >= threshold rows → use it as-is (no merge).
3. Otherwise load every unique CSV path and concatenate:
   a. On shared columns if any exist.
   b. Union merge (all columns, many NaNs) if no shared columns.
4. Drop all-NaN columns, deduplicate rows, reset index.
5. Save final CSV to processed_dir and return metadata.
"""
from __future__ import annotations
import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def _norm_col(name: str) -> str:
    """Normalise a column name to lowercase_with_underscores."""
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name


class DatasetMerger:
    def __init__(self, config: dict):
        col = config.get("collection", {})
        self._threshold = int(col.get("min_row_threshold", 500))
        self._proc_dir  = Path(col.get("processed_data_dir", "data/processed"))
        self._proc_dir.mkdir(parents=True, exist_ok=True)

    # ── public ────────────────────────────────────────────────────────────────
    def build_final_dataset(self,
                             scored_csvs: list[tuple[Path, float, dict]],
                             job_id: str) -> dict:
        """
        Parameters
        ----------
        scored_csvs : list of (csv_path, score, meta_dict), sorted best-first
        job_id      : unique job identifier used in the output filename

        Returns
        -------
        {
          "path":         Path to final CSV,
          "columns":      [str],
          "row_count":    int,
          "source_count": int,
          "preview_rows": [dict],   # first 10 rows as records
          "merged":       bool,
        }
        """
        if not scored_csvs:
            raise ValueError("No scored CSVs provided to merger.")

        best_path, _, _ = scored_csvs[0]
        best_df = self._load(best_path)

        if best_df is None:
            raise ValueError(f"Could not load best-scored CSV: {best_path}")

        # ── Case 1: single dataset already meets threshold ────────────────────
        if len(best_df) >= self._threshold:
            logger.info("Best dataset has %d rows — no merge needed.", len(best_df))
            return self._finalise(best_df, [best_path], job_id, merged=False)

        # ── Case 2: merge all unique CSVs ─────────────────────────────────────
        logger.info(
            "Best dataset has only %d rows (< %d threshold) — merging candidates.",
            len(best_df), self._threshold,
        )

        # Deduplicate by resolved absolute path so the same file is never
        # loaded twice (which would cause drop_duplicates to eat all new rows).
        seen: set = set()
        dfs: list[pd.DataFrame] = []
        used_paths: list[Path] = []

        for csv_path, _, _ in scored_csvs:
            key = csv_path.resolve()
            if key in seen:
                continue
            seen.add(key)

            df = self._load(csv_path)
            if df is not None:
                dfs.append(df)
                used_paths.append(csv_path)

        if not dfs:
            logger.warning("All loads failed — falling back to best_df alone.")
            dfs       = [best_df]
            used_paths = [best_path]

        combined = self._merge_dfs(dfs)
        return self._finalise(combined, used_paths, job_id, merged=len(dfs) > 1)

    # ── internals ─────────────────────────────────────────────────────────────
    def _load(self, path: Path) -> pd.DataFrame | None:
        try:
            df = pd.read_csv(path, low_memory=False, nrows=100_000)
            df.columns = [_norm_col(c) for c in df.columns]
            return df
        except Exception as exc:
            logger.warning("Cannot load %s: %s", path, exc)
            return None

    def _merge_dfs(self, dfs: list[pd.DataFrame]) -> pd.DataFrame:
        if len(dfs) == 1:
            return dfs[0]

        # Find columns shared across ALL dataframes
        shared = set(dfs[0].columns)
        for d in dfs[1:]:
            shared &= set(d.columns)

        if shared:
            logger.info("Shared-column merge on %d columns: %s",
                        len(shared), sorted(shared))
            aligned = [d[sorted(shared)] for d in dfs]
        else:
            logger.warning("No shared columns — union merge (expect NaNs).")
            aligned = dfs

        return pd.concat(aligned, ignore_index=True, sort=False)

    def _finalise(self, df: pd.DataFrame, sources: list[Path],
                  job_id: str, merged: bool) -> dict:
        # Drop all-NaN columns, deduplicate rows, reset index
        df = df.dropna(axis=1, how="all")
        df = df.drop_duplicates()
        df = df.reset_index(drop=True)

        out = self._proc_dir / f"{job_id}_dataset.csv"
        df.to_csv(out, index=False)

        row_count = len(df)
        logger.info("Final dataset: %d rows × %d cols → %s",
                    row_count, len(df.columns), out.name)

        if row_count < self._threshold:
            logger.warning(
                "Final dataset has only %d rows — below threshold of %d. "
                "Consider adding more data sources.",
                row_count, self._threshold,
            )

        return {
            "path":         out,
            "columns":      list(df.columns),
            "row_count":    row_count,
            "source_count": len(sources),
            "preview_rows": df.head(10).to_dict(orient="records"),
            "merged":       merged,
        }
