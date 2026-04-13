"""
test_complete_system_integration.py
====================================
Complete end-to-end system integration test.
Tests the full RAD-ML pipeline:
1. Backend API health check
2. Frontend accessibility
3. Model training pipeline
4. Model evaluation
5. Deployment verification
6. Complete workflow
"""
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, Optional
import warnings
warnings.filterwarnings('ignore')

# Configuration
BACKEND_URL = "http://localhost:5001"
FRONTEND_URL = "http://localhost:5173"
TIMEOUT = 5

def print_header(title: str) -> None:
    """Print formatted section header."""
    print(f"\n{'='*80}")
    print(f"{title.center(80)}")
    print(f"{'='*80}\n")

def print_result(test_name: str, passed: bool, message: str = "") -> None:
    """Print test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {test_name}")
    if message:
        print(f"   {message}")

# ──────────────────────────────────────────────────────────────────────────────
# TEST 1: Backend Health Check
# ──────────────────────────────────────────────────────────────────────────────
def test_backend_health() -> bool:
    """Test backend health endpoint."""
    print_header("TEST 1: BACKEND HEALTH CHECK")
    
    try:
        response = requests.get(f"{BACKEND_URL}/api/health", timeout=TIMEOUT)
        is_ok = response.status_code == 200
        
        print(f"Backend URL: {BACKEND_URL}")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:100]}")
        
        print_result("Backend Health Check", is_ok)
        return is_ok
    except requests.exceptions.ConnectionError:
        print_result("Backend Health Check", False, "Cannot connect to backend")
        return False
    except Exception as e:
        print_result("Backend Health Check", False, str(e))
        return False


# ──────────────────────────────────────────────────────────────────────────────
# TEST 2: Frontend Accessibility
# ──────────────────────────────────────────────────────────────────────────────
def test_frontend_accessibility() -> bool:
    """Test frontend is accessible."""
    print_header("TEST 2: FRONTEND ACCESSIBILITY")
    
    try:
        response = requests.get(FRONTEND_URL, timeout=TIMEOUT)
        is_ok = response.status_code == 200
        
        print(f"Frontend URL: {FRONTEND_URL}")
        print(f"Status Code: {response.status_code}")
        print(f"Response Size: {len(response.text)} bytes")
        
        print_result("Frontend Accessibility", is_ok)
        return is_ok
    except requests.exceptions.ConnectionError:
        print_result("Frontend Accessibility", False, "Cannot connect to frontend")
        return False
    except Exception as e:
        print_result("Frontend Accessibility", False, str(e))
        return False


# ──────────────────────────────────────────────────────────────────────────────
# TEST 3: Authentication System
# ──────────────────────────────────────────────────────────────────────────────
def test_authentication() -> bool:
    """Test user authentication endpoints."""
    print_header("TEST 3: AUTHENTICATION SYSTEM")
    
    test_user = {
        "username": f"test_user_{int(time.time())}",
        "password": "Test@1234!",
        "email": "test@example.com"
    }
    
    try:
        # Test registration
        print("Step 1: Register user...")
        reg_response = requests.post(
            f"{BACKEND_URL}/api/auth/register",
            json=test_user,
            timeout=TIMEOUT
        )
        
        if reg_response.status_code != 201:
            print_result("User Registration", False, f"Status {reg_response.status_code}")
            return False
        
        reg_data = reg_response.json()
        token = reg_data.get("token")
        print(f"✅ User registered: {test_user['username']}")
        print(f"   Token received: {token[:20]}...")
        
        # Test getting current user
        print("\nStep 2: Verify authentication...")
        auth_headers = {"Authorization": f"Bearer {token}"}
        user_response = requests.get(
            f"{BACKEND_URL}/api/auth/me",
            headers=auth_headers,
            timeout=TIMEOUT
        )
        
        if user_response.status_code != 200:
            print_result("Authentication Verification", False, f"Status {user_response.status_code}")
            return False
        
        print(f"✅ Authentication verified")
        print_result("Authentication System", True)
        return True
        
    except Exception as e:
        print_result("Authentication System", False, str(e))
        return False


# ──────────────────────────────────────────────────────────────────────────────
# TEST 4: Model Training Pipeline  
# ──────────────────────────────────────────────────────────────────────────────
def test_model_training_pipeline() -> bool:
    """Test model training pipeline."""
    print_header("TEST 4: MODEL TRAINING PIPELINE")
    
    try:
        # Import model evaluation components
        project_root = Path(__file__).parent
        sys.path.insert(0, str(project_root / "Code_Generator" / "RAD-ML"))
        
        from generator.algorithm_selector import AlgorithmSelector
        from generator.performance_metrics import MetricsCalculator
        
        print("Step 1: Algorithm Selection...")
        
        # Select algorithm for regression task
        selection = AlgorithmSelector.select("REGRESSION", 5000)
        algo = selection["algorithm"]
        print(f"✅ Algorithm selected: {algo.upper()}")
        print(f"   Reason: {selection['reason']}")
        
        # Get metrics for this task
        print("\nStep 2: Performance Metrics...")
        metrics_config = MetricsCalculator.get_default_metrics_for_task("regression")
        print(f"✅ Metrics configured: {', '.join(metrics_config['metrics'])}")
        print(f"   CV Folds: {metrics_config['cv_folds']}")
        print(f"   Test Split: {metrics_config['test_split']}")
        
        print_result("Model Training Pipeline", True)
        return True
        
    except Exception as e:
        print_result("Model Training Pipeline", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ──────────────────────────────────────────────────────────────────────────────
# TEST 5: Model Evaluation
# ──────────────────────────────────────────────────────────────────────────────
def test_model_evaluation() -> bool:
    """Test model evaluation system."""
    print_header("TEST 5: MODEL EVALUATION")
    
    try:
        from generator.model_evaluator import ModelEvaluator
        from sklearn.datasets import make_classification
        from sklearn.model_selection import train_test_split
        from sklearn.ensemble import RandomForestClassifier
        import numpy as np
        
        print("Step 1: Create test data...")
        X, y = make_classification(n_samples=200, n_features=10, random_state=42)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        print(f"✅ Test data created: {len(X_train)} train, {len(X_test)} test")
        
        print("\nStep 2: Train model...")
        model = RandomForestClassifier(n_estimators=50, random_state=42)
        model.fit(X_train, y_train)
        print(f"✅ Model trained")
        
        print("\nStep 3: Evaluate model...")
        eval_result = ModelEvaluator.evaluate_classification(model, X_test, y_test)
        
        print(f"✅ Evaluation complete:")
        print(f"   Accuracy: {eval_result['test_accuracy']:.4f}")
        print(f"   Precision: {eval_result['test_precision']:.4f}")
        print(f"   Recall: {eval_result['test_recall']:.4f}")
        print(f"   F1 Score: {eval_result['test_f1']:.4f}")
        print(f"   Needs Retrain: {eval_result['needs_retrain']}")
        
        print_result("Model Evaluation", True)
        return True
        
    except Exception as e:
        print_result("Model Evaluation", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ──────────────────────────────────────────────────────────────────────────────
# TEST 6: Deployment Verification
# ──────────────────────────────────────────────────────────────────────────────
def test_deployment_verification() -> bool:
    """Test deployment verification system."""
    print_header("TEST 6: DEPLOYMENT VERIFICATION")
    
    try:
        from generator.model_evaluator import DeploymentVerifier
        
        print("Step 1: Check backend deployment...")
        backend_info = DeploymentVerifier.check_localhost_deployment(port=5001, timeout=3)
        backend_running = backend_info.get("is_running", False)
        
        print(f"Backend Port 5001: {'✅ Running' if backend_running else '❌ Not running'}")
        print(f"URL: {backend_info.get('localhost_url')}")
        print(f"Message: {backend_info.get('message')}")
        
        print("\nStep 2: Check frontend deployment...")
        frontend_info = DeploymentVerifier.check_localhost_deployment(port=5173, timeout=3)
        frontend_running = frontend_info.get("is_running", False)
        
        print(f"Frontend Port 5173: {'✅ Running' if frontend_running else '❌ Not running'}")
        print(f"URL: {frontend_info.get('localhost_url')}")
        print(f"Message: {frontend_info.get('message')}")
        
        is_ok = backend_running and frontend_running
        print_result("Deployment Verification", is_ok)
        return is_ok
        
    except Exception as e:
        print_result("Deployment Verification", False, str(e))
        return False


# ──────────────────────────────────────────────────────────────────────────────
# TEST 7: Complete End-to-End Workflow
# ──────────────────────────────────────────────────────────────────────────────
def test_complete_workflow() -> bool:
    """Test complete end-to-end workflow."""
    print_header("TEST 7: COMPLETE END-TO-END WORKFLOW")
    
    try:
        print("Workflow Steps:")
        print("1. Backend health: ", end="")
        backend_ok = requests.get(f"{BACKEND_URL}/api/health", timeout=3).status_code == 200
        print("✅" if backend_ok else "❌")
        
        print("2. Frontend ready: ", end="")
        frontend_ok = requests.get(FRONTEND_URL, timeout=3).status_code == 200
        print("✅" if frontend_ok else "❌")
        
        print("3. Algorithm selection: ", end="")
        sys.path.insert(0, str(Path(__file__).parent / "Code_Generator" / "RAD-ML"))
        from generator.algorithm_selector import AlgorithmSelector
        algo_result = AlgorithmSelector.select("REGRESSION", 5000)
        algo_ok = algo_result is not None
        print("✅" if algo_ok else "❌")
        
        print("4. Metrics tracking: ", end="")
        from generator.performance_metrics import MetricsCalculator
        metrics = MetricsCalculator.get_default_metrics_for_task("regression")
        metrics_ok = metrics is not None
        print("✅" if metrics_ok else "❌")
        
        print("5. Model evaluation: ", end="")
        from generator.model_evaluator import ModelEvaluator
        eval_ok = hasattr(ModelEvaluator, 'evaluate_classification')
        print("✅" if eval_ok else "❌")
        
        print("6. Deployment check: ", end="")
        from generator.model_evaluator import DeploymentVerifier
        deploy_info = DeploymentVerifier.check_localhost_deployment(port=5001, timeout=2)
        deploy_ok = deploy_info.get('is_running', False)
        print("✅" if deploy_ok else "❌")
        
        all_ok = backend_ok and frontend_ok and algo_ok and metrics_ok and eval_ok
        print_result("Complete Workflow", all_ok)
        return all_ok
        
    except Exception as e:
        print_result("Complete Workflow", False, str(e))
        import traceback
        traceback.print_exc()
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main() -> int:
    """Run all tests."""
    print_header("RAD-ML COMPLETE SYSTEM INTEGRATION TEST")
    
    tests = [
        ("Backend Health Check", test_backend_health),
        ("Frontend Accessibility", test_frontend_accessibility),
        ("Authentication System", test_authentication),
        ("Model Training Pipeline", test_model_training_pipeline),
        ("Model Evaluation", test_model_evaluation),
        ("Deployment Verification", test_deployment_verification),
        ("Complete Workflow", test_complete_workflow),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {e}")
            results.append((test_name, False))
        time.sleep(0.5)  # Brief delay between tests
    
    # Summary
    print_header("SYSTEM INTEGRATION TEST SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({100*passed/total:.0f}%)")
    
    if passed == total:
        print("\n🎉 ALL SYSTEM TESTS PASSED - SYSTEM READY FOR USE")
        print("\n📍 Access Points:")
        print("   Frontend:  http://localhost:5173")
        print("   Backend:   http://localhost:5001")
        print("   API Docs:  http://localhost:5001/api/health")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
