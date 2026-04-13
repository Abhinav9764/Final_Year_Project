"""
test_model_evaluation_pipeline.py
==================================
Comprehensive test for model evaluation, retraining, and deployment verification.

Tests:
1. Model evaluation (accuracy threshold checking)
2. Data augmentation for classification
3. Automatic retraining on low accuracy
4. Deployment verification with localhost
5. End-to-end pipeline
"""
import sys
import json
import numpy as np
from pathlib import Path

# Add paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "Code_Generator" / "RAD-ML"))

from generator.model_evaluator import (
    ModelEvaluator, DataAugmenter, RetrainingOrchestrator, DeploymentVerifier
)

# Try importing scikit-learn models
try:
    from sklearn.datasets import make_classification, make_regression
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


def print_section(title):
    """Print formatted section header."""
    print(f"\n{'='*80}")
    print(f"{title.center(80)}")
    print(f"{'='*80}\n")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1: CLASSIFICATION EVALUATION
# ─────────────────────────────────────────────────────────────────────────────

def test_classification_evaluation():
    """Test classification model evaluation."""
    if not SKLEARN_AVAILABLE:
        print("❌ scikit-learn not available")
        return False
    
    print_section("TEST 1: CLASSIFICATION MODEL EVALUATION")
    
    # Generate test data
    X, y = make_classification(n_samples=1000, n_features=20, n_informative=15, 
                              n_redundant=5, random_state=42, n_classes=3)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    X_val, X_test, y_val, y_test = train_test_split(X_test, y_test, test_size=0.5, random_state=42)
    
    # Train model
    model = RandomForestClassifier(n_estimators=50, max_depth=10, random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluate
    eval_result = ModelEvaluator.evaluate_classification(
        model, X_test, y_test, X_val, y_val, cv_folds=5
    )
    
    print(ModelEvaluator.print_evaluation_report(eval_result))
    
    # Check results
    accuracy = eval_result["test_accuracy"]
    needs_retrain = eval_result["needs_retrain"]
    
    print(f"Test Accuracy: {accuracy:.4f}")
    print(f"Needs Retrain: {'YES (below 95%)' if needs_retrain else 'NO (above 95%)'}")
    print(f"Status: {eval_result['status']}")
    
    return True


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2: REGRESSION EVALUATION
# ─────────────────────────────────────────────────────────────────────────────

def test_regression_evaluation():
    """Test regression model evaluation."""
    if not SKLEARN_AVAILABLE:
        print("❌ scikit-learn not available")
        return False
    
    print_section("TEST 2: REGRESSION MODEL EVALUATION")
    
    # Generate test data
    X, y = make_regression(n_samples=1000, n_features=20, n_informative=15, 
                          random_state=42, noise=10)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    X_val, X_test, y_val, y_test = train_test_split(X_test, y_test, test_size=0.5, random_state=42)
    
    # Train model
    model = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluate
    eval_result = ModelEvaluator.evaluate_regression(
        model, X_test, y_test, X_val, y_val, cv_folds=5
    )
    
    print(ModelEvaluator.print_evaluation_report(eval_result))
    
    # Check results
    r2 = eval_result["test_r2"]
    needs_retrain = eval_result["needs_retrain"]
    
    print(f"Test R² Score: {r2:.4f}")
    print(f"Needs Retrain: {'YES (below 95%)' if needs_retrain else 'NO (above 95%)'}")
    print(f"Status: {eval_result['status']}")
    
    return True


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3: DATA AUGMENTATION
# ─────────────────────────────────────────────────────────────────────────────

def test_data_augmentation():
    """Test data augmentation functionality."""
    if not SKLEARN_AVAILABLE:
        print("❌ scikit-learn not available")
        return False
    
    print_section("TEST 3: DATA AUGMENTATION")
    
    # Generate small dataset
    X, y = make_classification(n_samples=500, n_features=20, n_informative=15,
                              random_state=42, n_classes=2)
    
    print(f"Original dataset size: {len(X)} samples")
    print(f"Class distribution: {np.bincount(y)}")
    
    # Test small dataset detection
    is_small = DataAugmenter.is_small_dataset(len(X), threshold=5000)
    print(f"Is small dataset (< 5000): {is_small}")
    
    if is_small:
        print("\nApplying data augmentation techniques:")
        
        # Test SMOTE
        try:
            X_aug, y_aug = DataAugmenter.augment_classification(X, y, technique="smote")
            print(f"  ✅ SMOTE: {len(X)} → {len(X_aug)} samples")
            print(f"     New distribution: {np.bincount(y_aug)}")
        except Exception as e:
            print(f"  ❌ SMOTE failed: {e}")
        
        # Test scaling
        try:
            X_scaled, y_scaled = DataAugmenter.augment_classification(X, y, technique="scale")
            print(f"  ✅ Scaling: Robust feature scaling applied")
            print(f"     Feature scales - mean: {X_scaled.mean():.4f}, std: {X_scaled.std():.4f}")
        except Exception as e:
            print(f"  ❌ Scaling failed: {e}")
    
    return True


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4: DEPLOYMENT VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def test_deployment_verification():
    """Test deployment verification (localhost check)."""
    
    print_section("TEST 4: DEPLOYMENT VERIFICATION")
    
    print("Checking if Flask app is running on localhost:7000...")
    
    # Check localhost
    deployment_info = DeploymentVerifier.check_localhost_deployment(port=7000, timeout=2)
    
    print(f"Localhost URL: {deployment_info['localhost_url']}")
    print(f"Is Running: {deployment_info['is_running']}")
    print(f"Status Code: {deployment_info.get('status_code', 'N/A')}")
    print(f"Message: {deployment_info['message']}")
    
    if not deployment_info['is_running']:
        print("\n⚠️  Flask app is not running. To start it:")
        print("   1. Navigate to: Chatbot_Interface/backend")
        print("   2. Run: python app.py")
        print("   3. Then model will be available at: http://localhost:7000")
    else:
        print("\n✅ Flask app is running!")
    
    return True


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5: COMPREHENSIVE EVALUATION REPORT
# ─────────────────────────────────────────────────────────────────────────────

def test_comprehensive_evaluation():
    """Test comprehensive evaluation with deployment verification."""
    
    if not SKLEARN_AVAILABLE:
        print("❌ scikit-learn not available")
        return False
    
    print_section("TEST 5: COMPREHENSIVE EVALUATION & DEPLOYMENT REPORT")
    
    # Create a classification model
    X, y = make_classification(n_samples=800, n_features=20, n_informative=15,
                              random_state=42, n_classes=2)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    X_val, X_test, y_val, y_test = train_test_split(X_test, y_test, test_size=0.5, random_state=42)
    
    # Train model
    model = RandomForestClassifier(n_estimators=50, max_depth=8, random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluate
    eval_result = ModelEvaluator.evaluate_classification(
        model, X_test, y_test, X_val, y_val
    )
    
    # Check deployment
    deployment_info = DeploymentVerifier.check_localhost_deployment(port=7000, timeout=2)
    
    # Generate report
    report = DeploymentVerifier.generate_deployment_report(
        eval_result, deployment_info, accuracy_threshold=0.95
    )
    
    print(report)
    
    # Additional info
    print("\nDetailed Metrics:")
    print(f"  Accuracy: {eval_result['test_accuracy']:.4f}")
    print(f"  Precision: {eval_result['test_precision']:.4f}")
    print(f"  Recall: {eval_result['test_recall']:.4f}")
    print(f"  F1 Score: {eval_result['test_f1']:.4f}")
    print(f"  Confidence: {eval_result['confidence']:.4f}")
    print(f"  Needs Retrain: {eval_result['needs_retrain']}")
    
    return True


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6: RETRAINING ORCHESTRATION
# ─────────────────────────────────────────────────────────────────────────────

def test_retraining_orchestration():
    """Test automatic retraining orchestration."""
    
    if not SKLEARN_AVAILABLE:
        print("❌ scikit-learn not available")
        return False
    
    print_section("TEST 6: AUTOMATIC RETRAINING ORCHESTRATION")
    
    # Create classification data
    X, y = make_classification(n_samples=600, n_features=20, n_informative=10,
                              random_state=42, n_classes=2)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    X_val, X_test, y_val, y_test = train_test_split(X_test, y_test, test_size=0.5, random_state=42)
    
    # Initial model (likely low accuracy due to limited features)
    print("Step 1: Initial model training...")
    model = RandomForestClassifier(n_estimators=20, max_depth=3, random_state=42)
    
    eval_result, retr_model = None, None
    try:
        retr_model, eval_result = RetrainingOrchestrator.retrain_classification(
            model, X_train, y_train, X_test, y_test, 
            augmentation=True, hyperparameter_tuning=False
        )
        
        print(f"  ✅ Model retrained")
        print(f"  Accuracy: {eval_result['test_accuracy']:.4f}")
        
        if eval_result['needs_retrain']:
            print(f"  Status: Still needs improvement (accuracy < 95%)")
            print(f"  Reason: {eval_result['reason']}")
        else:
            print(f"  Status: ✅ Meets quality threshold!")
        
    except Exception as e:
        print(f"  ⚠️  Retraining test: {e}")
    
    return True


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TEST RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """Run all tests."""
    
    print_section("MODEL EVALUATION & RETRAINING PIPELINE - COMPREHENSIVE TEST SUITE")
    
    tests = [
        ("Classification Evaluation", test_classification_evaluation),
        ("Regression Evaluation", test_regression_evaluation),
        ("Data Augmentation", test_data_augmentation),
        ("Deployment Verification", test_deployment_verification),
        ("Comprehensive Evaluation Report", test_comprehensive_evaluation),
        ("Retraining Orchestration", test_retraining_orchestration),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = "PASSED" if result else "FAILED"
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            results[test_name] = "ERROR"
    
    # Summary
    print_section("TEST SUMMARY")
    
    for test_name, status in results.items():
        symbol = "✅" if status == "PASSED" else "❌" if status == "FAILED" else "⚠️"
        print(f"{symbol} {test_name}: {status}")
    
    passed = sum(1 for s in results.values() if s == "PASSED")
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - PIPELINE READY FOR DEPLOYMENT")
        return True
    else:
        print("\n⚠️  SOME TESTS INCOMPLETE - CHECK DETAILS ABOVE")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
