"""
Tabular dataset cleaning, splitting, benchmarking, and S3 upload for SageMaker.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

log = logging.getLogger(__name__)

try:
    import pandas as pd  # type: ignore

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    log.warning("pandas not installed - DataPreprocessor will use mock mode.")

try:
    import boto3  # type: ignore

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


PreprocessMeta = Dict[str, object]


class DataPreprocessor:
    MISSING_THRESHOLD = 0.50

    def __init__(self, cfg: dict):
        aws = cfg.get("aws", {})
        self.s3_bucket = aws.get("s3_bucket", "rad-ml-datasets")
        self.region = aws.get("region", "us-east-1")
        self.clean_dir = Path("data/datasets/cleaned")
        self.clean_dir.mkdir(parents=True, exist_ok=True)

    def process(
        self,
        csv_path: str,
        target_column: Optional[str] = None,
        user_prompt: Optional[str] = None,
    ) -> PreprocessMeta:
        if not PANDAS_AVAILABLE:
            return self._mock_meta(csv_path)

        df = self._load(csv_path)
        log.info("Loaded CSV %s with shape %s", csv_path, df.shape)

        df = self._drop_high_missing(df)
        df = self._fill_missing(df)

        target = target_column or df.columns[-1]
        if target not in df.columns:
            raise ValueError(f"Target column {target!r} not found in dataset.")

        task_type = self._infer_task_type(df, target)
        df = self._prepare_target(df, target, task_type)

        if user_prompt:
            df = self._filter_feature_columns(df, target, user_prompt)

        df = self._encode_categoricals(df, exclude={target})
        ordered_cols = [target] + [c for c in df.columns if c != target]
        df = df[ordered_cols]
        features = [c for c in df.columns if c != target]
        if not features:
            raise ValueError("No usable feature columns remained after preprocessing.")

        clean_path = self.clean_dir / Path(csv_path).name
        df.to_csv(clean_path, index=False)

        split_paths = self._create_train_validation_split(df)
        train_path = clean_path.with_name(f"{clean_path.stem}_train.csv")
        validation_path = clean_path.with_name(f"{clean_path.stem}_validation.csv")
        split_paths["train"].to_csv(train_path, index=False)
        split_paths["validation"].to_csv(validation_path, index=False)

        benchmark = self._estimate_generalization(df, target, task_type)
        train_uri = self._upload_to_s3(train_path, key_prefix="datasets/train")
        validation_uri = self._upload_to_s3(validation_path, key_prefix="datasets/validation")

        return {
            "local_path": str(clean_path),
            "s3_uri": train_uri,
            "s3_validation_uri": validation_uri,
            "features": features,
            "target_column": target,
            "task_type": task_type,
            "quality_gate_passed": bool(benchmark.get("meets_threshold", False)),
            "benchmark_metrics": benchmark,
            "shape": list(df.shape),
        }

    @staticmethod
    def _filter_feature_columns(df: "pd.DataFrame", target: str, user_prompt: str) -> "pd.DataFrame":
        import re

        if not user_prompt:
            return df

        prompt_tokens = set(re.findall(r"[a-zA-Z0-9_]+", user_prompt.lower()))
        stop_words = {
            "build", "create", "make", "generate", "develop", "a", "an", "the", "and", "or", "for",
            "that", "with", "in", "on", "to", "of", "is", "are", "based", "using", "dataset", "data",
            "ml", "ai", "model", "system", "app", "application", "predict", "prediction", "classifier",
            "classification", "regression", "analyze", "analysis", "forecast", "from", "by", "columns",
            "fields", "input", "output", "target", "label", "labels", "attributes",
        }
        prompt_tokens -= stop_words

        cols_to_keep = [target]
        for col in df.columns:
            if col == target:
                continue
            col_tokens = set(str(col).lower().replace("_", " ").replace("-", " ").split())
            if col_tokens.intersection(prompt_tokens):
                cols_to_keep.append(col)
                continue
            if any(len(c) > 3 and len(p) > 3 and (c in p or p in c) for c in col_tokens for p in prompt_tokens):
                cols_to_keep.append(col)

        return df[cols_to_keep] if len(cols_to_keep) > 1 else df

    @staticmethod
    def _load(path: str) -> "pd.DataFrame":
        try:
            return pd.read_csv(path, encoding="utf-8")
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="latin-1")

    def _drop_high_missing(self, df: "pd.DataFrame") -> "pd.DataFrame":
        threshold = int(len(df) * self.MISSING_THRESHOLD)
        return df.dropna(thresh=threshold, axis=1)

    @staticmethod
    def _fill_missing(df: "pd.DataFrame") -> "pd.DataFrame":
        filled = df.copy()
        for col in filled.columns:
            if not filled[col].isnull().any():
                continue
            if pd.api.types.is_numeric_dtype(filled[col]):
                filled[col] = filled[col].fillna(filled[col].median())
            else:
                mode = filled[col].mode()
                filled[col] = filled[col].fillna(mode.iloc[0] if not mode.empty else "Unknown")
        return filled

    @staticmethod
    def _infer_task_type(df: "pd.DataFrame", target: str) -> str:
        series = df[target]
        unique_count = int(series.nunique(dropna=True))
        if str(series.dtype) in {"object", "category", "bool"}:
            return "classification"
        if pd.api.types.is_integer_dtype(series) and unique_count <= 20:
            return "classification"
        if unique_count <= 10 and unique_count < max(20, int(len(series) * 0.05)):
            return "classification"
        return "regression"

    @staticmethod
    def _prepare_target(df: "pd.DataFrame", target: str, task_type: str) -> "pd.DataFrame":
        if task_type != "classification":
            return df

        from sklearn.preprocessing import LabelEncoder  # type: ignore

        out = df.copy()
        encoder = LabelEncoder()
        out[target] = encoder.fit_transform(out[target].fillna("Unknown").astype(str))
        return out

    @staticmethod
    def _encode_categoricals(df: "pd.DataFrame", exclude: set[str]) -> "pd.DataFrame":
        from sklearn.preprocessing import LabelEncoder  # type: ignore

        encoded = df.copy()
        encoder = LabelEncoder()
        for col in encoded.select_dtypes(include=["object", "category"]).columns:
            if col in exclude:
                continue
            if encoded[col].nunique(dropna=True) <= 50:
                encoded[col] = encoder.fit_transform(encoded[col].astype(str))
            else:
                encoded = encoded.drop(columns=[col])
        return encoded

    @staticmethod
    def _create_train_validation_split(df: "pd.DataFrame") -> Dict[str, "pd.DataFrame"]:
        from sklearn.model_selection import train_test_split  # type: ignore

        target = df.columns[0]
        y = df[target]
        stratify = y if y.nunique(dropna=True) <= 20 else None
        train_df, validation_df = train_test_split(
            df,
            test_size=0.2,
            random_state=42,
            stratify=stratify,
        )
        return {"train": train_df, "validation": validation_df}

    @staticmethod
    def _estimate_generalization(df: "pd.DataFrame", target: str, task_type: str) -> Dict[str, object]:
        try:
            from sklearn.compose import ColumnTransformer  # type: ignore
            from sklearn.impute import SimpleImputer  # type: ignore
            from sklearn.linear_model import ElasticNet, LogisticRegression  # type: ignore
            from sklearn.metrics import accuracy_score, f1_score, r2_score  # type: ignore
            from sklearn.model_selection import train_test_split  # type: ignore
            from sklearn.pipeline import Pipeline  # type: ignore
            from sklearn.preprocessing import OneHotEncoder, StandardScaler  # type: ignore
        except Exception as exc:
            log.warning("sklearn benchmark unavailable: %s", exc)
            return {"metric_name": "unavailable", "metric_value": 0.0, "meets_threshold": False}

        X = df.drop(columns=[target])
        y = df[target]
        numeric_cols = X.select_dtypes(include=["number"]).columns.tolist()
        categorical_cols = [col for col in X.columns if col not in numeric_cols]

        prep = ColumnTransformer(
            transformers=[
                (
                    "num",
                    Pipeline(
                        [
                            ("imputer", SimpleImputer(strategy="median")),
                            ("scaler", StandardScaler()),
                        ]
                    ),
                    numeric_cols,
                ),
                (
                    "cat",
                    Pipeline(
                        [
                            ("imputer", SimpleImputer(strategy="most_frequent")),
                            ("onehot", OneHotEncoder(handle_unknown="ignore")),
                        ]
                    ),
                    categorical_cols,
                ),
            ]
        )

        stratify = y if task_type == "classification" and y.nunique(dropna=True) <= 20 else None
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=stratify
        )

        if task_type == "classification":
            estimator = LogisticRegression(max_iter=2000, penalty="l2", C=0.7, class_weight="balanced")
            pipeline = Pipeline([("prep", prep), ("model", estimator)])
            pipeline.fit(X_train, y_train)
            preds = pipeline.predict(X_val)
            accuracy = float(accuracy_score(y_val, preds))
            weighted_f1 = float(f1_score(y_val, preds, average="weighted"))
            return {
                "metric_name": "accuracy",
                "metric_value": round(accuracy, 4),
                "support_metric_name": "weighted_f1",
                "support_metric_value": round(weighted_f1, 4),
                "meets_threshold": accuracy >= 0.90,
            }

        estimator = ElasticNet(alpha=0.05, l1_ratio=0.2, random_state=42, max_iter=5000)
        pipeline = Pipeline([("prep", prep), ("model", estimator)])
        pipeline.fit(X_train, y_train)
        preds = pipeline.predict(X_val)
        r2 = float(r2_score(y_val, preds))
        return {
            "metric_name": "r2",
            "metric_value": round(r2, 4),
            "meets_threshold": r2 >= 0.90,
        }

    def _upload_to_s3(self, local_path: Path, key_prefix: str = "datasets") -> str:
        s3_key = f"{key_prefix}/{local_path.name}"
        s3_uri = f"s3://{self.s3_bucket}/{s3_key}"

        if not BOTO3_AVAILABLE:
            log.warning("boto3 not available - using local file URI for %s", local_path)
            return f"file://{local_path.as_posix()}"

        try:
            s3 = boto3.client("s3", region_name=self.region)
            s3.upload_file(str(local_path), self.s3_bucket, s3_key)
        except Exception as exc:
            log.error("S3 upload failed for %s: %s", local_path, exc)
            return f"file://{local_path.as_posix()}"

        return s3_uri

    @staticmethod
    def _mock_meta(csv_path: str) -> PreprocessMeta:
        return {
            "local_path": csv_path,
            "s3_uri": "s3://rad-ml-datasets/datasets/train/mock_dataset.csv",
            "s3_validation_uri": "s3://rad-ml-datasets/datasets/validation/mock_dataset_validation.csv",
            "features": ["feature_1", "feature_2", "feature_3"],
            "target_column": "target",
            "task_type": "classification",
            "quality_gate_passed": False,
            "benchmark_metrics": {"metric_name": "accuracy", "metric_value": 0.0, "meets_threshold": False},
            "shape": [100, 4],
        }
