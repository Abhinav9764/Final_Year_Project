"""
generator/algorithm_selector.py
================================
Intelligent algorithm selection based on task type.

Selects the best FREE/open-source algorithm for:
- Regression: LightGBM, XGBoost, Random Forest, Lasso, SVR
- Classification: LightGBM, XGBoost, Random Forest, Logistic Regression, SVC, KNN
- Clustering: K-Means, DBSCAN, Hierarchical, GMM

Features:
- Multi-dimensional rule-based scoring fallback.
- LLM constraint matching (if LLMClient is available).
- Template-based code generation.
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# CODE TEMPLATES
# ────────────────────────────────────────────────────────────────────────────

_REGRESSION_LGBM_TPL = """\
# {name}
import lightgbm as lgb
from sklearn.metrics import mean_squared_error, r2_score

# Initialize model
model = lgb.LGBMRegressor(
{hyperparams}
)

# Train model
model.fit(
    X_train, y_train,
    eval_set=[(X_val, y_val)],
    early_stopping_rounds=10,
    verbose=10,
)

# Predictions
y_pred = model.predict(X_test)
"""

_REGRESSION_XGB_TPL = """\
# {name}
import xgboost as xgb
from sklearn.metrics import mean_squared_error, r2_score

# Initialize model
model = xgb.XGBRegressor(
{hyperparams}
)

# Train model
model.fit(
    X_train, y_train,
    eval_set=[(X_val, y_val)],
    early_stopping_rounds=10,
    verbose=True,
)

# Predictions
y_pred = model.predict(X_test)
"""

_REGRESSION_RF_TPL = """\
# {name}
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score

# Initialize model
model = RandomForestRegressor(
{hyperparams}
)

# Train model
model.fit(X_train, y_train)

# Predictions
y_pred = model.predict(X_test)
"""

_REGRESSION_LASSO_TPL = """\
# {name}
from sklearn.linear_model import Lasso
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import mean_squared_error, r2_score

# Initialize model with scaling (vital for regularized linear models)
model = make_pipeline(
    StandardScaler(),
    Lasso(
{hyperparams}
    )
)

# Train model
model.fit(X_train, y_train)

# Predictions
y_pred = model.predict(X_test)
"""

_REGRESSION_SVR_TPL = """\
# {name}
from sklearn.svm import SVR
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import mean_squared_error, r2_score

# Initialize model with scaling
model = make_pipeline(
    StandardScaler(),
    SVR(
{hyperparams}
    )
)

# Train model
model.fit(X_train, y_train)

# Predictions
y_pred = model.predict(X_test)
"""

_CLASSIFICATION_LGBM_TPL = """\
# {name}
import lightgbm as lgb
from sklearn.metrics import accuracy_score, classification_report

# Initialize model
model = lgb.LGBMClassifier(
{hyperparams}
)

# Train model
model.fit(
    X_train, y_train,
    eval_set=[(X_val, y_val)],
    early_stopping_rounds=10,
    verbose=10,
)

# Predictions
y_pred = model.predict(X_test)
try:
    y_pred_proba = model.predict_proba(X_test)
except Exception:
    y_pred_proba = None
"""

_CLASSIFICATION_XGB_TPL = """\
# {name}
import xgboost as xgb
from sklearn.metrics import accuracy_score, classification_report

# Initialize model
model = xgb.XGBClassifier(
{hyperparams}
)

# Train model
model.fit(
    X_train, y_train,
    eval_set=[(X_val, y_val)],
    early_stopping_rounds=10,
    verbose=True,
)

# Predictions
y_pred = model.predict(X_test)
try:
    y_pred_proba = model.predict_proba(X_test)
except Exception:
    y_pred_proba = None
"""

_CLASSIFICATION_RF_TPL = """\
# {name}
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

# Initialize model
model = RandomForestClassifier(
{hyperparams}
)

# Train model
model.fit(X_train, y_train)

# Predictions
y_pred = model.predict(X_test)
try:
    y_pred_proba = model.predict_proba(X_test)
except Exception:
    y_pred_proba = None
"""

_CLASSIFICATION_LR_TPL = """\
# {name}
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import accuracy_score, classification_report

# Initialize model
model = make_pipeline(
    StandardScaler(),
    LogisticRegression(
{hyperparams}
    )
)

# Train model
model.fit(X_train, y_train)

# Predictions
y_pred = model.predict(X_test)
try:
    y_pred_proba = model.predict_proba(X_test)
except Exception:
    y_pred_proba = None
"""

_CLASSIFICATION_SVC_TPL = """\
# {name}
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import accuracy_score, classification_report

# Initialize model
model = make_pipeline(
    StandardScaler(),
    SVC(
{hyperparams}
    )
)

# Train model
model.fit(X_train, y_train)

# Predictions
y_pred = model.predict(X_test)
try:
    y_pred_proba = model.predict_proba(X_test)
except Exception:
    y_pred_proba = None
"""

_CLASSIFICATION_KNN_TPL = """\
# {name}
from sklearn.neighbors import KNeighborsClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import accuracy_score, classification_report

# Initialize model
model = make_pipeline(
    StandardScaler(),
    KNeighborsClassifier(
{hyperparams}
    )
)

# Train model
model.fit(X_train, y_train)

# Predictions
y_pred = model.predict(X_test)
try:
    y_pred_proba = model.predict_proba(X_test)
except Exception:
    y_pred_proba = None
"""

_CLUSTERING_KMEANS_TPL = """\
# {name}
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

# Initialize model
model = KMeans(
{hyperparams}
)

# Fit model
model.fit(X)

# Get cluster assignments
labels = model.labels_
centers = model.cluster_centers_
"""

_CLUSTERING_DBSCAN_TPL = """\
# {name}
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score

# Initialize model
model = DBSCAN(
{hyperparams}
)

# Fit model
labels = model.fit_predict(X)

# Get cluster counts
n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
n_noise = list(labels).count(-1)
"""

_CLUSTERING_HIERARCHICAL_TPL = """\
# {name}
from scipy.cluster.hierarchy import dendrogram, linkage, fcluster
from scipy.spatial.distance import pdist

# Compute linkage
Z = linkage(X, method='{linkage_method}')

# Get cluster assignments
n_clust = {n_clusters}
labels = fcluster(Z, n_clust, criterion='maxclust')
"""

_CLUSTERING_GMM_TPL = """\
# {name}
from sklearn.mixture import GaussianMixture

# Initialize model
model = GaussianMixture(
{hyperparams}
)

# Fit model
model.fit(X)

# Predict clusters
labels = model.predict(X)
"""


# ────────────────────────────────────────────────────────────────────────────
# ALGORITHM REGISTRIES
# ────────────────────────────────────────────────────────────────────────────

_REGRESSION_ALGORITHMS = {
    "lightgbm": {
        "name": "LightGBM (Light Gradient Boosting)",
        "reason": "Fastest gradient boosting. Low memory. Best for large tabular datasets.",
        "pros": ["Fast training", "Low memory", "Handles large data", "Built-in feature importance"],
        "cons": ["Overfitting risk on small data", "Needs parameter tuning"],
        "package": "lightgbm",
        "hyperparams": {"n_estimators": 100, "learning_rate": 0.1, "max_depth": 5, "random_state": 42},
        "metrics": ["mse", "rmse", "mae", "r2_score"],
        "cross_validation": 5,
        "train_test_split": 0.2,
        "code_template": _REGRESSION_LGBM_TPL,
        "tags": ["tree", "boosting", "large_data", "fast"],
    },
    "xgboost": {
        "name": "XGBoost (Extreme Gradient Boosting)",
        "reason": "Most robust gradient boosting. Excellent generalization.",
        "pros": ["Highly accurate", "Robust", "Good regularization"],
        "cons": ["Slower than LightGBM", "More memory heavy"],
        "package": "xgboost",
        "hyperparams": {"n_estimators": 100, "learning_rate": 0.1, "max_depth": 5, "random_state": 42},
        "metrics": ["mse", "rmse", "mae", "r2_score"],
        "cross_validation": 5,
        "train_test_split": 0.2,
        "code_template": _REGRESSION_XGB_TPL,
        "tags": ["tree", "boosting", "accurate"],
    },
    "random_forest": {
        "name": "Random Forest",
        "reason": "Highly interpretable out-of-the-box performance without much tuning.",
        "pros": ["Easy to use", "Interpretable", "Fast inference"],
        "cons": ["Large model size", "Slower training on large datasets"],
        "package": "scikit-learn",
        "hyperparams": {"n_estimators": 100, "max_depth": 10, "random_state": 42},
        "metrics": ["mse", "rmse", "mae", "r2_score"],
        "cross_validation": 5,
        "train_test_split": 0.2,
        "code_template": _REGRESSION_RF_TPL,
        "tags": ["tree", "bagging", "interpretable"],
    },
    "lasso": {
        "name": "Lasso Regression",
        "reason": "Linear model with L1 penalty. Excellent for high-dimensional data as it performs feature selection.",
        "pros": ["Highly interpretable", "Built-in feature selection", "Very fast"],
        "cons": ["Only models linear relationships", "Struggles with highly correlated features"],
        "package": "scikit-learn",
        "hyperparams": {"alpha": 1.0, "random_state": 42},
        "metrics": ["mse", "rmse", "mae", "r2_score"],
        "cross_validation": 5,
        "train_test_split": 0.2,
        "code_template": _REGRESSION_LASSO_TPL,
        "tags": ["linear", "interpretable", "feature_selection", "fast"],
    },
    "svr": {
        "name": "Support Vector Regressor",
        "reason": "Robust to outliers and effective in high-dimensional spaces.",
        "pros": ["Effective in high dimensions", "Memory efficient (uses support vectors)"],
        "cons": ["Does not scale well to >100k rows", "Harder to tune"],
        "package": "scikit-learn",
        "hyperparams": {"kernel": "'rbf'", "C": 1.0, "epsilon": 0.1},
        "metrics": ["mse", "rmse", "mae", "r2_score"],
        "cross_validation": 5,
        "train_test_split": 0.2,
        "code_template": _REGRESSION_SVR_TPL,
        "tags": ["svm", "robust", "high_dim"],
    },
}

_CLASSIFICATION_ALGORITHMS = {
    "lightgbm": {
        "name": "LightGBM (Light Gradient Boosting)",
        "reason": "Fast classification. Best for large datasets.",
        "pros": ["Fast", "Low memory", "Handles imbalanced data", "Feature importance"],
        "cons": ["Overfitting risk on small datasets", "Needs tuning"],
        "package": "lightgbm",
        "hyperparams": {"n_estimators": 100, "learning_rate": 0.1, "max_depth": 5, "random_state": 42},
        "metrics": ["accuracy", "precision", "recall", "f1_score", "roc_auc"],
        "cross_validation": 5,
        "train_test_split": 0.2,
        "code_template": _CLASSIFICATION_LGBM_TPL,
        "tags": ["tree", "boosting", "large_data", "fast"],
    },
    "xgboost": {
        "name": "XGBoost (Extreme Gradient Boosting)",
        "reason": "Most accurate classification. Industry standard.",
        "pros": ["Highly accurate", "Robust", "Good calibration"],
        "cons": ["Slower", "More memory"],
        "package": "xgboost",
        "hyperparams": {"n_estimators": 100, "learning_rate": 0.1, "max_depth": 5, "random_state": 42},
        "metrics": ["accuracy", "precision", "recall", "f1_score", "roc_auc"],
        "cross_validation": 5,
        "train_test_split": 0.2,
        "code_template": _CLASSIFICATION_XGB_TPL,
        "tags": ["tree", "boosting", "accurate"],
    },
    "random_forest": {
        "name": "Random Forest",
        "reason": "Simple, interpretable classification.",
        "pros": ["Easy", "Interpretable", "Fast inference"],
        "cons": ["Slower training", "More memory", "Less accurate than XGBoost"],
        "package": "scikit-learn",
        "hyperparams": {"n_estimators": 100, "max_depth": 10, "random_state": 42},
        "metrics": ["accuracy", "precision", "recall", "f1_score"],
        "cross_validation": 5,
        "train_test_split": 0.2,
        "code_template": _CLASSIFICATION_RF_TPL,
        "tags": ["tree", "bagging", "interpretable"],
    },
    "logistic_regression": {
        "name": "Logistic Regression",
        "reason": "Baseline interpretability. Output represents exact probabilities.",
        "pros": ["Highly interpretable", "Fast", "Outputs calibrated probabilities"],
        "cons": ["Assumes linear decision boundary"],
        "package": "scikit-learn",
        "hyperparams": {"penalty": "'l2'", "C": 1.0, "random_state": 42, "max_iter": 1000},
        "metrics": ["accuracy", "precision", "recall", "f1_score", "roc_auc"],
        "cross_validation": 5,
        "train_test_split": 0.2,
        "code_template": _CLASSIFICATION_LR_TPL,
        "tags": ["linear", "interpretable", "probabilistic", "fast"],
    },
    "svc": {
        "name": "Support Vector Classifier",
        "reason": "Max-margin classifier, powerful for high-dimensional boundaries.",
        "pros": ["Effective in high dim spaces", "Versatile via kernel trick"],
        "cons": ["Scales poorly to >100k rows", "No native probability estimates (requires Platt scaling)"],
        "package": "scikit-learn",
        "hyperparams": {"kernel": "'rbf'", "C": 1.0, "probability": True, "random_state": 42},
        "metrics": ["accuracy", "precision", "recall", "f1_score"],
        "cross_validation": 5,
        "train_test_split": 0.2,
        "code_template": _CLASSIFICATION_SVC_TPL,
        "tags": ["svm", "accurate", "high_dim"],
    },
    "knn": {
        "name": "K-Nearest Neighbors",
        "reason": "Instance-based learning, brilliant for geographical or strictly distance-based datasets.",
        "pros": ["Simple to understand", "No immediate training phase (lazy learning)"],
        "cons": ["Slow inference", "Very sensitive to irrelevant features (curse of dimensionality)"],
        "package": "scikit-learn",
        "hyperparams": {"n_neighbors": 5, "weights": "'uniform'"},
        "metrics": ["accuracy", "precision", "recall", "f1_score"],
        "cross_validation": 5,
        "train_test_split": 0.2,
        "code_template": _CLASSIFICATION_KNN_TPL,
        "tags": ["distance", "simple"],
    },
}

_CLUSTERING_ALGORITHMS = {
    "kmeans": {
        "name": "K-Means",
        "reason": "Fast clustering. Works for most datasets.",
        "pros": ["Fast", "Scalable", "Simple to understand"],
        "cons": ["Need to specify k", "Sensitive to initialization"],
        "package": "scikit-learn",
        "hyperparams": {"n_clusters": 3, "random_state": 42},
        "metrics": ["silhouette_score", "davies_bouldin_score"],
        "cross_validation": None,
        "train_test_split": None,
        "code_template": _CLUSTERING_KMEANS_TPL,
        "tags": ["centroid", "fast"],
    },
    "dbscan": {
        "name": "DBSCAN",
        "reason": "Finds arbitrarily shaped clusters. No need to specify k.",
        "pros": ["No k needed", "Finds arbitrary shapes", "Outlier detection"],
        "cons": ["Parameter tuning hard", "Slow on large data"],
        "package": "scikit-learn",
        "hyperparams": {"eps": 0.5, "min_samples": 5},
        "metrics": ["silhouette_score"],
        "cross_validation": None,
        "train_test_split": None,
        "code_template": _CLUSTERING_DBSCAN_TPL,
        "tags": ["density", "outliers"],
    },
    "hierarchical": {
        "name": "Hierarchical Clustering",
        "reason": "Produces dendrogram. Good for exploratory analysis.",
        "pros": ["Dendrogram visualization", "No k needed upfront"],
        "cons": ["Slow on large data", "Memory intensive"],
        "package": "scikit-learn",
        "hyperparams": {"n_clusters": 3, "linkage": "ward"},
        "metrics": ["silhouette_score"],
        "cross_validation": None,
        "train_test_split": None,
        "code_template": _CLUSTERING_HIERARCHICAL_TPL,
        "tags": ["tree", "exploratory"],
    },
    "gmm": {
        "name": "Gaussian Mixture Model",
        "reason": "Soft clustering based on probability distributions. Handles elliptical clusters well.",
        "pros": ["Soft assignments (probabilities)", "Cluster shape flexibility"],
        "cons": ["Need to specify k", "Can fail to converge"],
        "package": "scikit-learn",
        "hyperparams": {"n_components": 3, "covariance_type": "'full'", "random_state": 42},
        "metrics": ["silhouette_score", "bic", "aic"],
        "cross_validation": None,
        "train_test_split": None,
        "code_template": _CLUSTERING_GMM_TPL,
        "tags": ["probabilistic", "soft_clustering"],
    },
}


class AlgorithmSelector:
    """Intelligently select best algorithm based on task type and dataset properties."""

    @staticmethod
    def select(
        task_type: str,
        dataset_size: int | None = None,
        n_features: int | None = None,
        constraints: list[str] | None = None,
        config: dict | None = None,
    ) -> dict:
        """
        Select best algorithm for task type.

        Parameters
        ----------
        task_type : str
            One of: "regression", "classification", "clustering"
        dataset_size : int, optional
            Number of rows in dataset. Helps optimize choice.
        n_features : int, optional
            Number of features in the dataset.
        constraints : list[str], optional
            String constraints from the user (e.g., "Must be interpretable").
        config : dict, optional
            System config (used to instantiate LLMClient if available).

        Returns
        -------
        dict with algorithm details, reason, pros/cons, metrics, and template.
        """
        task_type = task_type.lower().strip()
        
        # 1. Map to registry
        if task_type == "regression":
            registry = _REGRESSION_ALGORITHMS
        elif task_type == "classification":
            registry = _CLASSIFICATION_ALGORITHMS
        elif task_type == "clustering":
            registry = _CLUSTERING_ALGORITHMS
        else:
            raise ValueError(f"Unknown task_type: {task_type}. Must be regression, classification, or clustering.")

        algo_name, reason = AlgorithmSelector._evaluate_selection(
            task_type, registry, dataset_size, n_features, constraints, config
        )

        config_dict = registry[algo_name]
        return {
            "task_type": task_type,
            "algorithm": algo_name,
            "name": config_dict["name"],
            "reason": reason,
            "pros": config_dict["pros"],
            "cons": config_dict["cons"],
            "package": config_dict["package"],
            "hyperparams": config_dict["hyperparams"],
            "metrics": config_dict["metrics"],
            "cross_validation_folds": config_dict.get("cross_validation"),
            "train_test_split": config_dict.get("train_test_split"),
            "code_template": config_dict["code_template"],
            "all_options": list(registry.keys()),
        }

    @staticmethod
    def get_algorithm_code(algo_selection: dict) -> str:
        """
        Generate Python code snippet for the selected algorithm.

        Parameters
        ----------
        algo_selection : dict
            Result from select()

        Returns
        -------
        Python code string that trains the model
        """
        template = algo_selection.get("code_template", "")
        if not template:
            return "# Algorithm generation failed: No template found."

        hp_str = _format_params(algo_selection.get("hyperparams", {}))
        
        # We allow some explicit formatted overrides for hierarchical, etc.
        try:
            return template.format(
                name=algo_selection["name"],
                hyperparams=hp_str,
                linkage_method=algo_selection["hyperparams"].get("linkage", "ward").strip("'\""),
                n_clusters=algo_selection["hyperparams"].get("n_clusters", 3),
            )
        except Exception as exc:
            logger.error("Failed to render code template for %s: %s", algo_selection["algorithm"], exc)
            return f"# Template generation error: {exc}"

    # ── Internals ────────────────────────────────────────────────────────────────

    @staticmethod
    def _evaluate_selection(
        task_type: str,
        registry: dict,
        rows: int | None,
        features: int | None,
        constraints: list[str] | None,
        config: dict | None,
    ) -> tuple[str, str]:
        """
        Evaluate the optimal algorithm using LLM (if available+constraints exist)
        or fall back to the multi-dimensional rule engine.
        Returns: (algo_key, reason_string)
        """
        # Ensure ints
        rows = rows if rows is not None else 1000
        features = features if features is not None else 10
        constraints_str = " ".join(constraints).lower() if constraints else ""

        # 1. LLM Evaluation (Only if we have constraints that require semantic understanding)
        if constraints_str and config and config.get("llm", {}).get("enabled", True):
            try:
                from core.llm_client import LLMClient
                llm = LLMClient(config)
                prompt = (
                    f"You are an expert Data Scientist selecting an algorithm.\n"
                    f"Task: {task_type}\n"
                    f"Dataset: {rows} rows, {features} columns.\n"
                    f"User constraints: '{constraints_str}'\n\n"
                    f"Available options: {', '.join(registry.keys())}.\n"
                    f"Reply ONLY with valid JSON exactly like this:\n"
                    f'{{"algorithm": "one_of_the_keys", "reason": "why it is the best fit"}}'
                )
                response = llm.generate(prompt)
                
                # strip markdown fences
                import re
                cleaned = re.sub(r"^```(?:json)?\s*", "", response.strip(), flags=re.IGNORECASE)
                cleaned = re.sub(r"\s*```$", "", cleaned)
                data = json.loads(cleaned)
                
                selected = data.get("algorithm", "").strip().lower()
                if selected in registry:
                    logger.info("AlgorithmSelector (LLM): Selected %s based on constraints.", selected)
                    return selected, data.get("reason", "Selected via LLM constraint matching.")
            except Exception as exc:
                logger.warning("LLM constraint matching failed (%s). Falling back to Rule Engine.", exc)

        # 2. Multi-Dimensional Rule Engine Fallback
        if task_type == "clustering":
            if rows > 100_000:
                return "kmeans", f"{rows:,} rows → K-Means scales best."
            if constraints_str and ("outlier" in constraints_str or "density" in constraints_str):
                return "dbscan", "User constraint implies density-based clustering."
            return "kmeans", "K-Means is the most robust general-purpose clustering."

        elif task_type in ("regression", "classification"):
            is_classification = (task_type == "classification")

            # Condition: Small Data & High Dim -> Linear / SVM
            if rows < 1000 and features > 50:
                if is_classification:
                    return "svc", "High dim & small data → SVC prevents overfitting."
                else:
                    return "lasso", "High dim & small data → Lasso provides feature selection."

            # Condition: High Interpretability required
            if "interpret" in constraints_str or "explain" in constraints_str:
                if is_classification:
                    return "logistic_regression", "Interpretability constraint → Logistic Regression."
                else:
                    return "lasso", "Interpretability constraint → Lasso Regression."

            # Condition: Massive data
            if rows > 100_000:
                return "lightgbm", f"{rows:,} rows → LightGBM is fastest and most memory efficient."

            # Default: Best generalization
            return "xgboost", "Default choice for standard tabular data (highest accuracy)."

        return list(registry.keys())[0], "Default fallback active."


def _format_params(params: dict) -> str:
    """Format hyperparameters for code generation."""
    lines = []
    for key, value in params.items():
        if isinstance(value, str) and not value.startswith(("'","\"")):
            # It's a string that already has quotes in the def, e.g. "'rbf'"
            lines.append(f"    {key}={value},")
        elif isinstance(value, str):
            lines.append(f"    {key}='{value}',")
        else:
            lines.append(f"    {key}={value},")
    return "\n".join(lines)
