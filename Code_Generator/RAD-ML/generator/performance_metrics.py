"""
generator/performance_metrics.py
=================================
Performance metrics calculation for generated ML models.

Includes metrics for:
- Regression (MSE, RMSE, MAE, R²)
- Classification (Accuracy, Precision, Recall, F1, ROC-AUC)
- Clustering (Silhouette, Davies-Bouldin, Calinski-Harabasz)
"""
from __future__ import annotations
import logging

import numpy as np

logger = logging.getLogger(__name__)

try:
    from sklearn.metrics import (
        mean_squared_error, mean_absolute_error, r2_score,
        accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
        confusion_matrix,
        silhouette_score, davies_bouldin_score, calinski_harabasz_score,
    )
except ImportError:
    logger.error("scikit-learn not installed: pip install scikit-learn")


class RegressionMetrics:
    """Calculate regression performance metrics."""

    @staticmethod
    def compute(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
        """
        Compute regression metrics.

        Parameters
        ----------
        y_true : array
            True target values
        y_pred : array
            Predicted values

        Returns
        -------
        dict with keys: mse, rmse, mae, r2
        """
        mse = mean_squared_error(y_true, y_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_true, y_pred)
        r2 = r2_score(y_true, y_pred)

        return {
            "mse": float(mse),
            "rmse": float(rmse),
            "mae": float(mae),
            "r2_score": float(r2),
        }

    @staticmethod
    def summary(metrics: dict) -> str:
        """Format metrics as readable summary."""
        return f"""\
═══════════════════════════════════════════════════════════════
REGRESSION PERFORMANCE METRICS
═══════════════════════════════════════════════════════════════
Mean Squared Error (MSE)      : {metrics['mse']:.6f}
Root Mean Squared Error (RMSE): {metrics['rmse']:.6f}
Mean Absolute Error (MAE)     : {metrics['mae']:.6f}
R² Score                       : {metrics['r2_score']:.6f}
═══════════════════════════════════════════════════════════════
"""


class ClassificationMetrics:
    """Calculate classification performance metrics."""

    @staticmethod
    def compute(y_true: np.ndarray, y_pred: np.ndarray, y_pred_proba: np.ndarray | None = None) -> dict:
        """
        Compute classification metrics.

        Parameters
        ----------
        y_true : array
            True labels
        y_pred : array
            Predicted labels
        y_pred_proba : array, optional
            Predicted probabilities (for ROC-AUC)

        Returns
        -------
        dict with classification metrics
        """
        accuracy = accuracy_score(y_true, y_pred)
        precision = precision_score(y_true, y_pred, average='weighted', zero_division=0)
        recall = recall_score(y_true, y_pred, average='weighted', zero_division=0)
        f1 = f1_score(y_true, y_pred, average='weighted', zero_division=0)

        metrics = {
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1_score": float(f1),
        }

        # ROC-AUC (for binary or multiclass with proba)
        try:
            if y_pred_proba is not None and len(np.unique(y_true)) == 2:
                roc_auc = roc_auc_score(y_true, y_pred_proba[:, 1])
                metrics["roc_auc"] = float(roc_auc)
        except Exception as e:
            logger.warning(f"ROC-AUC calculation failed: {e}")

        # Confusion matrix (for binary classification)
        try:
            if len(np.unique(y_true)) == 2:
                cm = confusion_matrix(y_true, y_pred)
                metrics["confusion_matrix"] = cm.tolist()
        except Exception as e:
            logger.warning(f"Confusion matrix calculation failed: {e}")

        return metrics

    @staticmethod
    def summary(metrics: dict) -> str:
        """Format metrics as readable summary."""
        roc_line = f"ROC-AUC Score                  : {metrics.get('roc_auc', 'N/A'):.6f}\n" if 'roc_auc' in metrics else ""
        return f"""\
═══════════════════════════════════════════════════════════════
CLASSIFICATION PERFORMANCE METRICS
═══════════════════════════════════════════════════════════════
Accuracy                       : {metrics['accuracy']:.6f}
Precision (weighted)           : {metrics['precision']:.6f}
Recall (weighted)              : {metrics['recall']:.6f}
F1 Score (weighted)            : {metrics['f1_score']:.6f}
{roc_line}═══════════════════════════════════════════════════════════════
"""


class ClusteringMetrics:
    """Calculate clustering performance metrics."""

    @staticmethod
    def compute(X: np.ndarray, labels: np.ndarray) -> dict:
        """
        Compute clustering metrics.

        Parameters
        ----------
        X : array
            Feature matrix
        labels : array
            Cluster labels

        Returns
        -------
        dict with clustering metrics
        """
        metrics = {}

        # Silhouette Score (range: -1 to 1, higher is better)
        try:
            silhouette = silhouette_score(X, labels)
            metrics["silhouette_score"] = float(silhouette)
        except Exception as e:
            logger.warning(f"Silhouette score failed: {e}")

        # Davies-Bouldin Index (lower is better)
        try:
            db_index = davies_bouldin_score(X, labels)
            metrics["davies_bouldin_index"] = float(db_index)
        except Exception as e:
            logger.warning(f"Davies-Bouldin index failed: {e}")

        # Calinski-Harabasz Index (higher is better)
        try:
            ch_index = calinski_harabasz_score(X, labels)
            metrics["calinski_harabasz_index"] = float(ch_index)
        except Exception as e:
            logger.warning(f"Calinski-Harabasz index failed: {e}")

        # Cluster sizes
        try:
            unique, counts = np.unique(labels, return_counts=True)
            metrics["cluster_sizes"] = dict(zip(map(int, unique), map(int, counts)))
            metrics["n_clusters"] = len(unique)
        except Exception as e:
            logger.warning(f"Cluster size calculation failed: {e}")

        return metrics

    @staticmethod
    def summary(metrics: dict) -> str:
        """Format metrics as readable summary."""
        lines = ["═══════════════════════════════════════════════════════════════"]
        lines.append("CLUSTERING PERFORMANCE METRICS")
        lines.append("═══════════════════════════════════════════════════════════════")

        if "silhouette_score" in metrics:
            lines.append(f"Silhouette Score               : {metrics['silhouette_score']:.6f}  (range: -1 to 1, higher is better)")
        if "davies_bouldin_index" in metrics:
            lines.append(f"Davies-Bouldin Index           : {metrics['davies_bouldin_index']:.6f}  (lower is better)")
        if "calinski_harabasz_index" in metrics:
            lines.append(f"Calinski-Harabasz Index        : {metrics['calinski_harabasz_index']:.6f}  (higher is better)")
        if "n_clusters" in metrics:
            lines.append(f"Number of Clusters             : {metrics['n_clusters']}")
        if "cluster_sizes" in metrics:
            lines.append(f"Cluster Sizes                  : {metrics['cluster_sizes']}")

        lines.append("═══════════════════════════════════════════════════════════════")
        return "\n".join(lines)


class MetricsCalculator:
    """Unified metrics calculator for all task types."""

    @staticmethod
    def compute(task_type: str, y_true: np.ndarray | None = None,
                y_pred: np.ndarray | None = None, y_pred_proba: np.ndarray | None = None,
                X: np.ndarray | None = None, labels: np.ndarray | None = None) -> dict:
        """
        Compute metrics based on task type.

        Parameters
        ----------
        task_type : str
            One of: regression, classification, clustering
        y_true : array
            True values (for regression/classification)
        y_pred : array
            Predicted values (for regression/classification)
        y_pred_proba : array
            Predicted probabilities (for classification)
        X : array
            Features (for clustering)
        labels : array
            Cluster labels (for clustering)

        Returns
        -------
        dict with appropriate metrics
        """
        if task_type == "regression":
            if y_true is None or y_pred is None:
                raise ValueError("regression requires y_true and y_pred")
            return RegressionMetrics.compute(y_true, y_pred)

        elif task_type == "classification":
            if y_true is None or y_pred is None:
                raise ValueError("classification requires y_true and y_pred")
            return ClassificationMetrics.compute(y_true, y_pred, y_pred_proba)

        elif task_type == "clustering":
            if X is None or labels is None:
                raise ValueError("clustering requires X and labels")
            return ClusteringMetrics.compute(X, labels)

        else:
            raise ValueError(f"Unknown task_type: {task_type}")

    @staticmethod
    def print_report(task_type: str, metrics: dict) -> None:
        """Print formatted metrics report."""
        if task_type == "regression":
            print(RegressionMetrics.summary(metrics))
        elif task_type == "classification":
            print(ClassificationMetrics.summary(metrics))
        elif task_type == "clustering":
            print(ClusteringMetrics.summary(metrics))
        else:
            logger.error(f"Unknown task_type: {task_type}")

    @staticmethod
    def export_json(metrics: dict) -> str:
        """Export metrics as JSON."""
        import json
        return json.dumps(metrics, indent=2, default=str)

    @staticmethod
    def get_default_metrics_for_task(task_type: str) -> dict:
        """
        Get default metrics configuration for a task type.

        Parameters
        ----------
        task_type : str
            One of: regression, classification, clustering

        Returns
        -------
        dict with metrics configuration
        """
        task_type = task_type.lower()

        if task_type == "regression":
            return {
                "task_type": "regression",
                "metrics": ["mse", "rmse", "mae", "r2_score"],
                "cv_folds": 5,
                "test_split": 0.2,
                "description": "Mean Squared Error, Root Mean Squared Error, Mean Absolute Error, R² Score"
            }
        elif task_type == "classification":
            return {
                "task_type": "classification",
                "metrics": ["accuracy", "precision", "recall", "f1_score", "roc_auc"],
                "cv_folds": 5,
                "test_split": 0.2,
                "description": "Accuracy, Precision, Recall, F1 Score, ROC-AUC"
            }
        elif task_type == "clustering":
            return {
                "task_type": "clustering",
                "metrics": ["silhouette_score", "davies_bouldin_index", "calinski_harabasz_index"],
                "cv_folds": 1,
                "test_split": 0.0,
                "description": "Silhouette Score, Davies-Bouldin Index, Calinski-Harabasz Index"
            }
        else:
            raise ValueError(f"Unknown task_type: {task_type}")
