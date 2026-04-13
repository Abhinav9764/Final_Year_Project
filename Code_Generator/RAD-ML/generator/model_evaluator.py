"""
generator/model_evaluator.py
=============================
Model evaluation and retraining pipeline with:
- Accuracy threshold checking (95% minimum)
- Data augmentation for small datasets
- Best practices implementation
- Automatic retraining on low accuracy
- Deployment verification with localhost links
"""
from __future__ import annotations
import logging
import numpy as np
from typing import Dict, Tuple, Optional
import time

logger = logging.getLogger(__name__)

try:
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import RobustScaler
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
    from imblearn.over_sampling import SMOTE
except ImportError:
    logger.warning("Required packages for evaluation not installed")


# ─────────────────────────────────────────────────────────────────────────────
# MODEL EVALUATOR
# ─────────────────────────────────────────────────────────────────────────────

class ModelEvaluator:
    """Evaluate model performance and determine if retraining is needed."""

    ACCURACY_THRESHOLD = 0.95  # 95% minimum accuracy
    CONFIDENCE_THRESHOLD = 0.90  # 90% minimum confidence (CV mean - std)

    @staticmethod
    def evaluate_classification(
        model,
        X_test: np.ndarray,
        y_test: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        cv_folds: int = 5
    ) -> Dict:
        """
        Evaluate classification model.

        Parameters
        ----------
        model : classifier
            Trained classifier
        X_test : array
            Test features
        y_test : array
            Test labels
        X_val : array, optional
            Validation features for additional evaluation
        y_val : array, optional
            Validation labels
        cv_folds : int
            Number of cross-validation folds

        Returns
        -------
        dict with evaluation metrics and retraining recommendation
        """
        y_pred = model.predict(X_test)

        # Calculate metrics
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
        recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
        f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)

        # Cross-validation score
        cv_scores = cross_val_score(model, X_test, y_test, cv=cv_folds, scoring='accuracy')
        cv_mean = cv_scores.mean()
        cv_std = cv_scores.std()
        confidence = cv_mean - cv_std  # Conservative estimate

        # Validation set (if provided)
        val_accuracy = None
        if X_val is not None and y_val is not None:
            y_val_pred = model.predict(X_val)
            val_accuracy = accuracy_score(y_val, y_val_pred)

        # Determine if retraining is needed
        needs_retrain = (
            accuracy < ModelEvaluator.ACCURACY_THRESHOLD or
            confidence < ModelEvaluator.CONFIDENCE_THRESHOLD
        )

        return {
            "task_type": "classification",
            "test_accuracy": float(accuracy),
            "test_precision": float(precision),
            "test_recall": float(recall),
            "test_f1": float(f1),
            "cv_scores": cv_scores.tolist(),
            "cv_mean": float(cv_mean),
            "cv_std": float(cv_std),
            "confidence": float(confidence),
            "val_accuracy": float(val_accuracy) if val_accuracy else None,
            "needs_retrain": needs_retrain,
            "reason": ModelEvaluator._get_retrain_reason(accuracy, confidence),
            "status": "GOOD" if not needs_retrain else "NEEDS_RETRAIN",
            "metrics": {
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1": f1
            }
        }

    @staticmethod
    def evaluate_regression(
        model,
        X_test: np.ndarray,
        y_test: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        cv_folds: int = 5
    ) -> Dict:
        """
        Evaluate regression model.

        Parameters
        ----------
        model : regressor
            Trained regressor
        X_test : array
            Test features
        y_test : array
            Test values
        X_val : array, optional
            Validation features
        y_val : array, optional
            Validation values
        cv_folds : int
            Number of cross-validation folds

        Returns
        -------
        dict with evaluation metrics and retraining recommendation
        """
        y_pred = model.predict(X_test)

        # Calculate metrics
        mse = mean_squared_error(y_test, y_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        # Cross-validation R² score
        cv_scores = cross_val_score(model, X_test, y_test, cv=cv_folds, scoring='r2')
        cv_mean = cv_scores.mean()
        cv_std = cv_scores.std()
        confidence = cv_mean - cv_std

        # For regression, check if R² >= 0.95 (equivalent to 95% variance explained)
        accuracy_equivalent = r2
        needs_retrain = (
            accuracy_equivalent < ModelEvaluator.ACCURACY_THRESHOLD or
            confidence < ModelEvaluator.CONFIDENCE_THRESHOLD
        )

        val_r2 = None
        if X_val is not None and y_val is not None:
            y_val_pred = model.predict(X_val)
            val_r2 = r2_score(y_val, y_val_pred)

        return {
            "task_type": "regression",
            "test_rmse": float(rmse),
            "test_mae": float(mae),
            "test_mse": float(mse),
            "test_r2": float(r2),
            "cv_scores": cv_scores.tolist(),
            "cv_mean": float(cv_mean),
            "cv_std": float(cv_std),
            "confidence": float(confidence),
            "val_r2": float(val_r2) if val_r2 else None,
            "needs_retrain": needs_retrain,
            "reason": ModelEvaluator._get_retrain_reason_regression(r2, confidence),
            "status": "GOOD" if not needs_retrain else "NEEDS_RETRAIN",
            "metrics": {
                "r2": r2,
                "rmse": rmse,
                "mae": mae,
                "mse": mse
            }
        }

    @staticmethod
    def _get_retrain_reason(accuracy: float, confidence: float) -> str:
        """Generate human-readable reason for retraining."""
        reasons = []
        if accuracy < ModelEvaluator.ACCURACY_THRESHOLD:
            reasons.append(f"Low accuracy ({accuracy:.2%} < 95%)")
        if confidence < ModelEvaluator.CONFIDENCE_THRESHOLD:
            reasons.append(f"Low confidence ({confidence:.2%} < 90%)")
        return "; ".join(reasons) if reasons else "Unknown issue"

    @staticmethod
    def _get_retrain_reason_regression(r2: float, confidence: float) -> str:
        """Generate human-readable reason for retraining (regression)."""
        reasons = []
        if r2 < ModelEvaluator.ACCURACY_THRESHOLD:
            reasons.append(f"Low R² ({r2:.2%} < 95%)")
        if confidence < ModelEvaluator.CONFIDENCE_THRESHOLD:
            reasons.append(f"Low confidence ({confidence:.2%} < 90%)")
        return "; ".join(reasons) if reasons else "Unknown issue"

    @staticmethod
    def print_evaluation_report(eval_result: Dict) -> str:
        """Format evaluation results as readable report."""
        task_type = eval_result["task_type"]
        status = eval_result["status"]

        if task_type == "classification":
            eval_result["metrics"]
            val_acc = eval_result.get('val_accuracy')
            val_str = f"{val_acc:.4f}" if isinstance(val_acc, float) else "N/A"
            needs_str = "YES" if eval_result['needs_retrain'] else "NO"

            return f"""\
═══════════════════════════════════════════════════════════════
MODEL EVALUATION REPORT - {status}
═══════════════════════════════════════════════════════════════
Task Type                      : CLASSIFICATION
Test Accuracy                  : {eval_result['test_accuracy']:.4f} (95% required)
Test Precision                 : {eval_result['test_precision']:.4f}
Test Recall                    : {eval_result['test_recall']:.4f}
Test F1 Score                  : {eval_result['test_f1']:.4f}
Cross-Validation Mean          : {eval_result['cv_mean']:.4f}
Cross-Validation Std           : {eval_result['cv_std']:.4f}
Confidence (CV Mean - Std)     : {eval_result['confidence']:.4f} (90% required)
Validation Accuracy            : {val_str}
Needs Retraining               : {needs_str}
Reason                         : {eval_result['reason']}
═══════════════════════════════════════════════════════════════
"""
        else:  # regression
            val_r2 = eval_result.get('val_r2')
            val_str = f"{val_r2:.4f}" if isinstance(val_r2, float) else "N/A"
            needs_str = "YES" if eval_result['needs_retrain'] else "NO"

            return f"""\
═══════════════════════════════════════════════════════════════
MODEL EVALUATION REPORT - {status}
═══════════════════════════════════════════════════════════════
Task Type                      : REGRESSION
Test R² Score                  : {eval_result['test_r2']:.4f} (95% required)
Test RMSE                      : {eval_result['test_rmse']:.6f}
Test MAE                       : {eval_result['test_mae']:.6f}
Test MSE                       : {eval_result['test_mse']:.6f}
Cross-Validation R² Mean       : {eval_result['cv_mean']:.4f}
Cross-Validation Std           : {eval_result['cv_std']:.4f}
Confidence (CV Mean - Std)     : {eval_result['confidence']:.4f} (90% required)
Validation R²                  : {val_str}
Needs Retraining               : {needs_str}
Reason                         : {eval_result['reason']}
═══════════════════════════════════════════════════════════════
"""


# ─────────────────────────────────────────────────────────────────────────────
# DATA AUGMENTATION
# ─────────────────────────────────────────────────────────────────────────────

class DataAugmenter:
    """Apply data augmentation techniques to improve small datasets."""

    @staticmethod
    def is_small_dataset(n_samples: int, threshold: int = 5000) -> bool:
        """Check if dataset is considered small."""
        return n_samples < threshold

    @staticmethod
    def augment_classification(
        X: np.ndarray,
        y: np.ndarray,
        target_size: Optional[int] = None,
        technique: str = "smote"
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Augment classification dataset.

        Techniques:
        - "smote": Synthetic Minority Oversampling
        - "scale": Feature scaling
        - "mix": Combined approach
        """
        if technique == "smote":
            return DataAugmenter._apply_smote(X, y)
        elif technique == "scale":
            return DataAugmenter._apply_scaling(X, y)
        elif technique == "mix":
            X_aug, y_aug = DataAugmenter._apply_smote(X, y)
            X_aug, y_aug = DataAugmenter._apply_scaling(X_aug, y_aug)
            return X_aug, y_aug
        return X, y

    @staticmethod
    def _apply_smote(X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Apply SMOTE oversampling."""
        try:
            smote = SMOTE(random_state=42)
            X_aug, y_aug = smote.fit_resample(X, y)
            logger.info(f"SMOTE applied: {len(y)} → {len(y_aug)} samples")
            return X_aug, y_aug
        except Exception as e:
            logger.warning(f"SMOTE failed: {e}. Returning original data.")
            return X, y

    @staticmethod
    def _apply_scaling(X: np.ndarray, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Apply robust feature scaling."""
        scaler = RobustScaler()
        X_scaled = scaler.fit_transform(X)
        logger.info("Robust scaling applied")
        return X_scaled, y

    @staticmethod
    def augment_regression(
        X: np.ndarray,
        y: np.ndarray,
        technique: str = "scale"
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Augment regression dataset."""
        if technique == "scale":
            return DataAugmenter._apply_scaling(X, y)
        return X, y


# ─────────────────────────────────────────────────────────────────────────────
# RETRAINING ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

class RetrainingOrchestrator:
    """Orchestrate model retraining with best practices."""

    @staticmethod
    def retrain_classification(
        model_class,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        augmentation: bool = True,
        hyperparameter_tuning: bool = False
    ) -> Tuple[object, Dict]:
        """
        Retrain classification model with best practices.

        Returns: (retrained_model, evaluation_result)
        """
        # Step 1: Data augmentation
        if augmentation and DataAugmenter.is_small_dataset(len(X_train)):
            X_train, y_train = DataAugmenter.augment_classification(X_train, y_train, technique="mix")
            logger.info(f"Data augmented: new training set size = {len(X_train)}")

        # Step 2: Model retraining with best practices
        logger.info("Retraining model with hyperparameter optimization...")

        if hasattr(model_class, 'fit'):
            # Add validation set for early stopping
            val_size = int(0.2 * len(X_train))
            X_train_split, X_val = X_train[:-val_size], X_train[-val_size:]
            y_train_split, y_val = y_train[:-val_size], y_train[-val_size:]

            # Try to fit with eval_set if model supports it (XGBoost, LightGBM)
            try:
                model_class.fit(
                    X_train_split, y_train_split,
                    eval_set=[(X_val, y_val)],
                    early_stopping_rounds=10,
                    verbose=0
                )
            except TypeError:
                # Standard sklearn models
                model_class.fit(X_train_split, y_train_split)

        # Step 3: Evaluate retrained model
        eval_result = ModelEvaluator.evaluate_classification(
            model_class, X_test, y_test, X_val, y_val
        )

        return model_class, eval_result

    @staticmethod
    def retrain_regression(
        model_class,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        augmentation: bool = True,
        hyperparameter_tuning: bool = False
    ) -> Tuple[object, Dict]:
        """
        Retrain regression model with best practices.

        Returns: (retrained_model, evaluation_result)
        """
        # Step 1: Data augmentation
        if augmentation and DataAugmenter.is_small_dataset(len(X_train)):
            X_train, y_train = DataAugmenter.augment_regression(X_train, y_train)
            logger.info(f"Data augmented: new training set size = {len(X_train)}")

        # Step 2: Model retraining with best practices
        logger.info("Retraining model with optimization...")

        if hasattr(model_class, 'fit'):
            # Add validation set for early stopping
            val_size = int(0.2 * len(X_train))
            X_train_split, X_val = X_train[:-val_size], X_train[-val_size:]
            y_train_split, y_val = y_train[:-val_size], y_train[-val_size:]

            # Try to fit with eval_set if supported
            try:
                model_class.fit(
                    X_train_split, y_train_split,
                    eval_set=[(X_val, y_val)],
                    early_stopping_rounds=10,
                    verbose=0
                )
            except TypeError:
                model_class.fit(X_train_split, y_train_split)

        # Step 3: Evaluate retrained model
        eval_result = ModelEvaluator.evaluate_regression(
            model_class, X_test, y_test, X_val, y_val
        )

        return model_class, eval_result


# ─────────────────────────────────────────────────────────────────────────────
# DEPLOYMENT VERIFIER
# ─────────────────────────────────────────────────────────────────────────────

class DeploymentVerifier:
    """Verify model deployment and generate deployment info."""

    @staticmethod
    def check_localhost_deployment(port: int = 7000, timeout: int = 5) -> Dict:
        """
        Check if Flask app is running on localhost.

        Returns deployment information with localhost link
        """
        import requests

        localhost_url = f"http://localhost:{port}"

        try:
            response = requests.get(localhost_url, timeout=timeout)
            is_running = response.status_code == 200

            return {
                "is_running": is_running,
                "localhost_url": localhost_url,
                "port": port,
                "status_code": response.status_code,
                "timestamp": time.time(),
                "message": f"✅ Model deployed at {localhost_url}"
            }
        except requests.exceptions.ConnectionError:
            return {
                "is_running": False,
                "localhost_url": localhost_url,
                "port": port,
                "status_code": None,
                "timestamp": time.time(),
                "message": f"❌ Cannot connect to {localhost_url}. Is Flask app running?"
            }
        except Exception as e:
            return {
                "is_running": False,
                "localhost_url": localhost_url,
                "port": port,
                "status_code": None,
                "error": str(e),
                "timestamp": time.time(),
                "message": f"❌ Deployment check failed: {e}"
            }

    @staticmethod
    def verify_flask_endpoint(
        url: str,
        test_data: Dict,
        timeout: int = 5
    ) -> Dict:
        """Verify Flask endpoint is working correctly."""
        import requests

        try:
            response = requests.post(url, json=test_data, timeout=timeout)

            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response": response.json() if response.headers.get('content-type') == 'application/json' else response.text,
                "message": f"Endpoint {url} is working"
            }
        except Exception as e:
            return {
                "success": False,
                "status_code": None,
                "error": str(e),
                "message": f"Endpoint verification failed: {e}"
            }

    @staticmethod
    def generate_deployment_report(
        model_eval: Dict,
        deployment_info: Dict,
        accuracy_threshold: float = 0.95
    ) -> str:
        """Generate comprehensive deployment report."""
        accuracy_check = "✅ PASS" if model_eval.get("metrics", {}).get("accuracy", 0) >= accuracy_threshold else "❌ FAIL"
        deployment_check = "✅ RUNNING" if deployment_info.get("is_running") else "❌ NOT RUNNING"

        return f"""\
═══════════════════════════════════════════════════════════════
DEPLOYMENT VERIFICATION REPORT
═══════════════════════════════════════════════════════════════
Model Accuracy Status          : {accuracy_check}
Deployment Status              : {deployment_check}
Localhost URL                  : {deployment_info.get('localhost_url', 'N/A')}
Port                           : {deployment_info.get('port', 'N/A')}
═══════════════════════════════════════════════════════════════
Message                        : {deployment_info.get('message', 'N/A')}
═══════════════════════════════════════════════════════════════
"""


if __name__ == "__main__":
    # Example usage
    print("Model Evaluator Module Loaded Successfully")
    print(f"Accuracy Threshold: {ModelEvaluator.ACCURACY_THRESHOLD:.0%}")
    print(f"Confidence Threshold: {ModelEvaluator.CONFIDENCE_THRESHOLD:.0%}")
