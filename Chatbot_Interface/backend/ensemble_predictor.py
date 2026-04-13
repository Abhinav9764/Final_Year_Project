"""
Chatbot_Interface/backend/ensemble_predictor.py
================================================
Ensemble Risk Assessment for VM-ERA

- Load and run predictions from CNN, RCNN, and RF models
- Aggregate predictions using weighted averaging
- Calculate final risk score with confidence metrics
"""
from __future__ import annotations
import logging
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from PIL import Image

logger = logging.getLogger(__name__)


class EnsemblePredictor:
    """
    Ensemble predictor combining CNN, RCNN, and Random Forest models.

    Uses weighted averaging to aggregate predictions and produce
    a final risk score with confidence metrics.
    """

    def __init__(
        self,
        model_dir: Optional[str] = None,
        cnn_weight: float = 0.4,
        rcnn_weight: float = 0.35,
        rf_weight: float = 0.25,
        use_gpu: bool = True
    ):
        """
        Initialize ensemble predictor.

        Args:
            model_dir: Directory containing trained models
            cnn_weight: Weight for CNN predictions (default 0.4)
            rcnn_weight: Weight for RCNN predictions (default 0.35)
            rf_weight: Weight for RF predictions (default 0.25)
            use_gpu: Whether to use GPU acceleration if available
        """
        self.model_dir = Path(model_dir) if model_dir else None
        self.weights = {
            'cnn': cnn_weight,
            'rcnn': rcnn_weight,
            'rf': rf_weight
        }

        # Normalize weights
        total_weight = sum(self.weights.values())
        self.weights = {k: v / total_weight for k, v in self.weights.items()}

        self.use_gpu = use_gpu
        self._models_loaded = False
        self._cnn_model = None
        self._rcnn_model = None
        self._rf_model = None
        self._gpu_available = False

        # Check GPU availability
        self._check_gpu()

    def _check_gpu(self) -> None:
        """Check if GPU is available for TensorFlow."""
        try:
            import tensorflow as tf
            gpus = tf.config.list_physical_devices('GPU')
            self._gpu_available = len(gpus) > 0

            if self._gpu_available and self.use_gpu:
                logger.info("GPU available: %d device(s)", len(gpus))
                # Enable mixed precision for faster inference
                try:
                    from tensorflow.keras import mixed_precision
                    mixed_precision.set_global_policy('mixed_float16')
                    logger.info("Mixed precision enabled for faster inference")
                except Exception as e:
                    logger.warning("Could not enable mixed precision: %s", e)
            else:
                logger.info("Using CPU for inference (GPU not available or disabled)")

        except ImportError:
            logger.warning("TensorFlow not available - models will not load")
            self._gpu_available = False

    def load_models(self, model_dir: Optional[str] = None) -> bool:
        """
        Load all three models from disk.

        Args:
            model_dir: Override directory for models

        Returns:
            True if all models loaded successfully
        """
        if model_dir:
            self.model_dir = Path(model_dir)

        if self.model_dir is None:
            logger.error("No model directory specified")
            return False

        try:
            import tensorflow as tf

            # Load CNN model
            cnn_path = self.model_dir / 'cnn_model.h5'
            if cnn_path.exists():
                self._cnn_model = tf.keras.models.load_model(str(cnn_path))
                logger.info("Loaded CNN model from %s", cnn_path)
            else:
                logger.warning("CNN model not found at %s", cnn_path)

            # Load RCNN model
            rcnn_path = self.model_dir / 'rcnn_model.h5'
            if rcnn_path.exists():
                self._rcnn_model = tf.keras.models.load_model(str(rcnn_path))
                logger.info("Loaded RCNN model from %s", rcnn_path)
            else:
                logger.warning("RCNN model not found at %s", rcnn_path)

            # Load Random Forest (pickle joblib)
            rf_path = self.model_dir / 'rf_model.pkl'
            if rf_path.exists():
                import joblib
                self._rf_model = joblib.load(str(rf_path))
                logger.info("Loaded RF model from %s", rf_path)
            else:
                logger.warning("RF model not found at %s", rf_path)

            self._models_loaded = any([
                self._cnn_model is not None,
                self._rcnn_model is not None,
                self._rf_model is not None
            ])

            if self._models_loaded:
                logger.info(
                    "Loaded %d/%d models (CNN=%s, RCNN=%s, RF=%s)",
                    sum([
                        self._cnn_model is not None,
                        self._rcnn_model is not None,
                        self._rf_model is not None
                    ]),
                    3,
                    "yes" if self._cnn_model else "no",
                    "yes" if self._rcnn_model else "no",
                    "yes" if self._rf_model else "no"
                )

            return self._models_loaded

        except Exception as e:
            logger.error("Failed to load models: %s", e)
            return False

    def predict_cnn(self, fingerprint_array: np.ndarray) -> Tuple[float, float]:
        """
        Run prediction using CNN model.

        Args:
            fingerprint_array: 128x128 numpy array from APK visual fingerprint

        Returns:
            Tuple of (malware_probability, confidence)
        """
        if self._cnn_model is None:
            return 0.5, 0.0

        try:
            import tensorflow as tf

            # Preprocess for CNN
            img = fingerprint_array.astype(np.float32) / 255.0
            img = np.expand_dims(img, axis=0)  # (1, 128, 128)
            img = np.expand_dims(img, axis=-1)  # (1, 128, 128, 1) for channels_last

            prediction = self._cnn_model.predict(img, verbose=0)[0]

            # Handle different output shapes
            if len(prediction) > 1:
                # Multi-class output - assume [benign_prob, malware_prob]
                malware_prob = float(prediction[1])
            else:
                # Binary output
                malware_prob = float(prediction[0])

            # Confidence based on how far from decision boundary
            confidence = abs(malware_prob - 0.5) * 2

            return malware_prob, confidence

        except Exception as e:
            logger.error("CNN prediction failed: %s", e)
            return 0.5, 0.0

    def predict_rcnn(self, fingerprint_array: np.ndarray) -> Tuple[float, float]:
        """
        Run prediction using RCNN model.

        Args:
            fingerprint_array: 128x128 numpy array

        Returns:
            Tuple of (malware_probability, confidence)
        """
        if self._rcnn_model is None:
            return 0.5, 0.0

        try:
            import tensorflow as tf

            # Preprocess for RCNN (may need sequence format)
            img = fingerprint_array.astype(np.float32) / 255.0

            # RCNN might expect sequence input - reshape accordingly
            # Assuming RCNN treats rows as sequences
            img = img.reshape(1, 128, 128)  # (batch, seq_len, features)

            prediction = self._rcnn_model.predict(img, verbose=0)[0]

            if len(prediction) > 1:
                malware_prob = float(prediction[1])
            else:
                malware_prob = float(prediction[0])

            confidence = abs(malware_prob - 0.5) * 2

            return malware_prob, confidence

        except Exception as e:
            logger.error("RCNN prediction failed: %s", e)
            return 0.5, 0.0

    def predict_rf(self, fingerprint_array: np.ndarray) -> Tuple[float, float]:
        """
        Run prediction using Random Forest model.

        Args:
            fingerprint_array: 128x128 numpy array

        Returns:
            Tuple of (malware_probability, confidence)
        """
        if self._rf_model is None:
            return 0.5, 0.0

        try:
            # Flatten for RF
            features = fingerprint_array.flatten().astype(np.float32) / 255.0
            features = features.reshape(1, -1)  # (1, 16384)

            # Get probability
            if hasattr(self._rf_model, 'predict_proba'):
                proba = self._rf_model.predict_proba(features)[0]
                if len(proba) > 1:
                    malware_prob = float(proba[1])
                else:
                    malware_prob = float(proba[0])
            else:
                # Hard prediction only
                pred = self._rf_model.predict(features)[0]
                malware_prob = float(pred)

            confidence = abs(malware_prob - 0.5) * 2

            return malware_prob, confidence

        except Exception as e:
            logger.error("RF prediction failed: %s", e)
            return 0.5, 0.0

    def predict_ensemble(
        self,
        fingerprint_array: np.ndarray,
        permission_risk_score: float = 0.0
    ) -> Dict[str, Any]:
        """
        Run ensemble prediction combining all available models.

        Args:
            fingerprint_array: 128x128 numpy array from APK visual fingerprint
            permission_risk_score: Optional risk score from permission analysis (0-100)

        Returns:
            Dictionary containing:
            - final_risk_score: Aggregated risk score (0-100)
            - malware_probability: Final malware probability (0-1)
            - individual_predictions: Breakdown by model
            - confidence: Overall confidence metric
            - models_used: List of models that contributed
        """
        predictions = {}
        models_used = []

        # Run CNN prediction
        if self._cnn_model is not None:
            cnn_prob, cnn_conf = self.predict_cnn(fingerprint_array)
            predictions['cnn'] = {'probability': cnn_prob, 'confidence': cnn_conf}
            models_used.append('cnn')
            logger.debug("CNN prediction: prob=%.4f, conf=%.4f", cnn_prob, cnn_conf)

        # Run RCNN prediction
        if self._rcnn_model is not None:
            rcnn_prob, rcnn_conf = self.predict_rcnn(fingerprint_array)
            predictions['rcnn'] = {'probability': rcnn_prob, 'confidence': rcnn_conf}
            models_used.append('rcnn')
            logger.debug("RCNN prediction: prob=%.4f, conf=%.4f", rcnn_prob, rcnn_conf)

        # Run RF prediction
        if self._rf_model is not None:
            rf_prob, rf_conf = self.predict_rf(fingerprint_array)
            predictions['rf'] = {'probability': rf_prob, 'confidence': rf_conf}
            models_used.append('rf')
            logger.debug("RF prediction: prob=%.4f, conf=%.4f", rf_prob, rf_conf)

        # Calculate weighted average
        if not predictions:
            logger.warning("No models available for prediction")
            return {
                'final_risk_score': 50.0,
                'malware_probability': 0.5,
                'individual_predictions': {},
                'confidence': 0.0,
                'models_used': [],
                'verdict': 'unknown'
            }

        weighted_prob = 0.0
        weighted_conf = 0.0

        for model_name, pred in predictions.items():
            weight = self.weights.get(model_name, 1.0 / len(predictions))
            weighted_prob += pred['probability'] * weight
            weighted_conf += pred['confidence'] * weight

        # Incorporate permission risk score if available
        if permission_risk_score > 0:
            # Blend permission risk (20% weight) with model predictions (80%)
            perm_risk_normalized = permission_risk_score / 100.0
            weighted_prob = weighted_prob * 0.8 + perm_risk_normalized * 0.2
            logger.debug(
                "Blended with permission risk: final_prob=%.4f",
                weighted_prob
            )

        # Convert to 0-100 risk score
        final_risk_score = weighted_prob * 100

        # Determine verdict
        if final_risk_score >= 70:
            verdict = 'malware'
        elif final_risk_score >= 40:
            verdict = 'suspicious'
        else:
            verdict = 'benign'

        result = {
            'final_risk_score': round(final_risk_score, 2),
            'malware_probability': round(weighted_prob, 4),
            'individual_predictions': predictions,
            'confidence': round(weighted_conf, 4),
            'models_used': models_used,
            'verdict': verdict,
            'permission_risk_included': permission_risk_score > 0
        }

        logger.info(
            "Ensemble prediction: risk=%.2f, verdict=%s, models=%d",
            final_risk_score, verdict, len(models_used)
        )

        return result

    def predict_from_image(
        self,
        image: Image.Image,
        permission_risk_score: float = 0.0
    ) -> Dict[str, Any]:
        """
        Run ensemble prediction from PIL Image.

        Args:
            image: PIL Image of the visual fingerprint
            permission_risk_score: Optional risk score from permission analysis

        Returns:
            Same as predict_ensemble()
        """
        fingerprint_array = np.array(image)
        return self.predict_ensemble(fingerprint_array, permission_risk_score)


# Convenience function
def predict_apk_risk(
    fingerprint_array: np.ndarray,
    permission_risk_score: float = 0.0,
    model_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Quick function to get ensemble risk prediction.

    Args:
        fingerprint_array: 128x128 numpy array
        permission_risk_score: Risk score from permission analysis (0-100)
        model_dir: Directory containing models

    Returns:
        Ensemble prediction results
    """
    predictor = EnsemblePredictor(model_dir=model_dir)
    predictor.load_models()
    return predictor.predict_ensemble(fingerprint_array, permission_risk_score)
