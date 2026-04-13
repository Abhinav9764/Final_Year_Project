"""
Code_Generator/RAD-ML/engines/ml_engine/data_preprocessor.py
=============================================================
Cleans the collected CSV and produces train/validation splits for SageMaker.

For standard tabular tasks it keeps the original behavior.
For text-classification prompts it can detect a free-text column and build a
compact TF-IDF feature matrix so the pipeline can proceed with the user intent.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

logger = logging.getLogger(__name__)


class DataPreprocessor:
    def __init__(self, config: dict):
        self._proc_dir = Path(config.get("collection", {}).get("processed_data_dir", "data/processed"))
        self._proc_dir.mkdir(parents=True, exist_ok=True)

    def preprocess(self, csv_path: Path, spec: dict, job_id: str) -> dict:
        df = pd.read_csv(csv_path, low_memory=False)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        logger.info("Loaded CSV: %d rows x %d cols", *df.shape)

        target_col = self._resolve_target(df, spec)
        feature_cols = self._resolve_features(df, spec, target_col)
        task = spec.get("task_type", "regression")

        logger.info("Target column resolved to: %s", target_col)
        logger.info("Feature columns (%d): %s", len(feature_cols), feature_cols)

        keep = [col for col in feature_cols + [target_col] if col in df.columns]
        df = df[keep].copy()
        df.dropna(subset=[target_col], inplace=True)

        text_feature = self._detect_text_feature(df, feature_cols, spec)
        if task == "classification" and text_feature:
            logger.info("Using TF-IDF preprocessing on text feature: %s", text_feature)
            return self._preprocess_text_classification(df, target_col, text_feature, job_id)

        encoders: dict = {}
        for col in feature_cols:
            if col not in df.columns:
                continue
            is_numeric = pd.api.types.is_numeric_dtype(df[col])
            if is_numeric:
                median_val = float(df[col].median()) if not df[col].dropna().empty else 0.0
                df[col] = df[col].fillna(median_val)
            else:
                le = LabelEncoder()
                df[col] = le.fit_transform(df[col].fillna("").astype(str))
                encoders[col] = le

        if task == "classification":
            le = LabelEncoder()
            df[target_col] = le.fit_transform(df[target_col].astype(str))
            encoders[target_col] = le

        train_df, val_df = train_test_split(df, test_size=0.2, random_state=42, shuffle=True)
        train_path = self._proc_dir / f"{job_id}_train.csv"
        val_path = self._proc_dir / f"{job_id}_val.csv"

        cols_ordered = [target_col] + [col for col in feature_cols if col in df.columns]
        train_df[cols_ordered].to_csv(train_path, index=False, header=False)
        val_df[cols_ordered].to_csv(val_path, index=False, header=False)

        logger.info("Train: %d rows  Val: %d rows", len(train_df), len(val_df))
        return {
            "train_path": train_path,
            "val_path": val_path,
            "feature_cols": [col for col in feature_cols if col in df.columns],
            "target_col": target_col,
            "task_type": task,
            "encoders": encoders,
            "stats": {
                "total_rows": len(df),
                "train_rows": len(train_df),
                "val_rows": len(val_df),
                "num_features": len([col for col in feature_cols if col in df.columns]),
            },
        }

    def _preprocess_text_classification(self, df: pd.DataFrame, target_col: str, text_feature: str, job_id: str) -> dict:
        df = df[[text_feature, target_col]].copy()
        df[text_feature] = df[text_feature].fillna("").astype(str)

        target_encoder = LabelEncoder()
        y = target_encoder.fit_transform(df[target_col].astype(str))

        vectorizer = TfidfVectorizer(
            max_features=12,
            ngram_range=(1, 2),
            stop_words="english",
        )
        X = vectorizer.fit_transform(df[text_feature])
        feature_names = [f"tfidf_{name.replace(' ', '_')}" for name in vectorizer.get_feature_names_out()]
        feature_df = pd.DataFrame(X.toarray(), columns=feature_names, index=df.index)
        feature_df[target_col] = y

        stratify = feature_df[target_col] if feature_df[target_col].nunique() > 1 else None
        train_df, val_df = train_test_split(
            feature_df,
            test_size=0.2,
            random_state=42,
            shuffle=True,
            stratify=stratify,
        )

        train_path = self._proc_dir / f"{job_id}_train.csv"
        val_path = self._proc_dir / f"{job_id}_val.csv"
        cols_ordered = [target_col] + feature_names
        train_df[cols_ordered].to_csv(train_path, index=False, header=False)
        val_df[cols_ordered].to_csv(val_path, index=False, header=False)

        logger.info("Text train: %d rows  Val: %d rows", len(train_df), len(val_df))
        return {
            "train_path": train_path,
            "val_path": val_path,
            "feature_cols": feature_names,
            "target_col": target_col,
            "task_type": "classification",
            "encoders": {target_col: target_encoder},
            "stats": {
                "total_rows": len(feature_df),
                "train_rows": len(train_df),
                "val_rows": len(val_df),
                "num_features": len(feature_names),
                "text_feature": text_feature,
            },
        }

    def _resolve_target(self, df: pd.DataFrame, spec: dict) -> str:
        target_hint = str(spec.get("target_param") or "").lower().replace(" ", "_")
        cols_lower = {c.lower(): c for c in df.columns}

        if target_hint in cols_lower:
            return cols_lower[target_hint]

        for c_low, c_orig in cols_lower.items():
            if target_hint and (target_hint in c_low or c_low in target_hint):
                return c_orig

        classification_fallbacks = ("label", "category", "topic", "class", "target")
        if str(spec.get("task_type", "")).lower() == "classification":
            for candidate in classification_fallbacks:
                if candidate in cols_lower:
                    return cols_lower[candidate]
            for c in df.columns:
                if not pd.api.types.is_numeric_dtype(df[c]):
                    return c

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if numeric_cols:
            return numeric_cols[-1]
        return df.columns[-1]

    def _resolve_features(self, df: pd.DataFrame, spec: dict, target_col: str) -> list[str]:
        input_hints = [str(p).lower().replace(" ", "_") for p in spec.get("input_params", [])]
        cols_lower = {c.lower(): c for c in df.columns if c != target_col}
        matched: list[str] = []

        alias_groups = {
            "location": ("location", "region", "city", "state", "area", "zip", "postal", "latitude", "longitude", "lat", "lon"),
            "bedroom": ("bedroom", "bedrooms", "bed", "bedrm", "bedrms"),
            "bathroom": ("bathroom", "bathrooms", "bath", "baths"),
            "room": ("room", "rooms"),
            "population": ("population", "pop"),
            "price": ("price", "value", "cost", "sale"),
            "news": ("news", "article", "articles", "text", "content", "headline", "body"),
            # ── Movie / recommendation domain ──────────────────────────────────
            "genre": ("genre", "genres", "category", "categories", "type", "movie_type"),
            "rating": (
                "rating", "ratings", "no_of_ratings", "num_ratings",
                "number_of_ratings", "no_of_votes", "vote_total",
                "vote_average", "vote_count", "score", "imdb_score",
                "imdb_rating", "popularity", "user_rating",
            ),
            "title": ("title", "movie_title", "film_title", "name", "movie_name"),
            "year": ("year", "release_year", "release_date", "date"),
        }

        def _normalized_tokens(value: str) -> set[str]:
            raw = str(value or "").lower().replace("_", " ")
            tokens = set(raw.split())
            tokens.add(raw.replace(" ", ""))
            return {t for t in tokens if t}

        def _hint_aliases(hint: str) -> set[str]:
            hint_tokens = _normalized_tokens(hint)
            aliases = set(hint_tokens)
            for key, group in alias_groups.items():
                if key in hint_tokens or any(term in hint_tokens for term in group):
                    aliases.update(group)
            return aliases

        for hint in input_hints:
            aliases = _hint_aliases(hint)
            for c_low, c_orig in cols_lower.items():
                normalized_col = c_low.replace("_", "")
                if (
                    hint in c_low
                    or c_low in hint
                    or any(alias in c_low or alias in normalized_col for alias in aliases)
                ):
                    if c_orig not in matched:
                        matched.append(c_orig)

        if not matched:
            matched = [c for c in df.columns if c != target_col]

        clean = []
        for col in matched:
            null_frac = df[col].isnull().mean()
            if null_frac <= 0.5:
                clean.append(col)
        return clean

    def _detect_text_feature(self, df: pd.DataFrame, feature_cols: list[str], spec: dict) -> str | None:
        prompt_text = str(spec.get("raw", "")).lower()
        wanted = ("text", "news", "article", "articles", "topic", "tf-idf", "tfidf")
        for col in feature_cols:
            if col not in df.columns:
                continue
            series = df[col]
            if not pd.api.types.is_object_dtype(series):
                continue
            sample = series.dropna().astype(str).head(50)
            if sample.empty:
                continue
            avg_len = float(sample.str.len().mean())
            if col in {"text", "content", "article", "article_text", "headline", "body"}:
                return col
            if avg_len >= 25 and any(token in prompt_text for token in wanted):
                return col
        return None
