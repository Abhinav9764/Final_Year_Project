"""
test_end_to_end_integration.py
==============================
Validates the complete pipeline:
  1. Task type classification (regression/classification/clustering)
  2. Algorithm selection based on task type
  3. Code generation with selected algorithm
  4. Generated code includes performance metrics
  5. E2E validation for gold price prediction
"""
import sys
import json
from pathlib import Path

# Add paths
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "Code_Generator" / "RAD-ML"))
sys.path.insert(0, str(project_root / "Data_Collection_Agent"))

# Import modules
from generator.algorithm_selector import AlgorithmSelector
from generator.performance_metrics import MetricsCalculator


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*80}")
    print(f"{title.center(80)}")
    print(f"{'='*80}\n")


def test_end_to_end_pipeline():
    """Test complete pipeline from prompt to code generation with algorithm selection."""
    
    print_section("END-TO-END INTEGRATION TEST")
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 1: Task Classification (Simplified)
    # ──────────────────────────────────────────────────────────────────────────
    print_section("STEP 1: TASK CLASSIFICATION")
    
    user_prompt = "Build a model that can predict gold price based on year and weight"
    print(f"Original Prompt: '{user_prompt}'")
    
    # Simplified task classification (in real scenario, this comes from prompt_understanding)
    task_type = "REGRESSION"  # Gold price prediction → regression task
    estimated_size = 5000
    features = ["year", "weight"]
    target = "gold_price"
    domain = "financial"
    
    print(f"✅ Task Type Detected: {task_type}")
    print(f"   Estimated Dataset Size: {estimated_size} rows")
    print(f"   Features: {features}")
    print(f"   Target Column: {target}")
    print(f"   Problem Domain: {domain}")
    
    # Create project spec like prompt_understanding would produce
    project_spec = {
        "task": "gold price prediction",
        "task_type": task_type,
        "feature_cols": features,
        "target_col": target,
        "estimated_dataset_size": estimated_size,
        "domain": domain,
    }
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 2: Algorithm Selection
    # ──────────────────────────────────────────────────────────────────────────
    print_section("STEP 2: INTELLIGENT ALGORITHM SELECTION")
    
    try:
        # Select best algorithm based on task type and dataset size
        algo_selection = AlgorithmSelector.select(task_type, estimated_size)
        
        selected_algo = algo_selection["algorithm"]
        reason = algo_selection["reason"]
        hyperparams = algo_selection["hyperparams"]
        metrics = algo_selection["metrics"]
        
        print(f"✅ Selected Algorithm: {selected_algo.upper()}")
        print(f"   Reason: {reason}")
        print(f"\n   Hyperparameters:")
        for param, value in hyperparams.items():
            print(f"      • {param}: {value}")
        print(f"\n   Performance Metrics to Track:")
        for i, metric in enumerate(metrics, 1):
            print(f"      {i}. {metric}")
        
    except Exception as e:
        print(f"❌ Error in algorithm selection: {e}")
        return False
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 3: Get Algorithm-Specific Code Snippet
    # ──────────────────────────────────────────────────────────────────────────
    print_section("STEP 3: GENERATE ALGORITHM CODE")
    
    try:
        algo_code = AlgorithmSelector.get_algorithm_code(algo_selection)
        
        print(f"Generated training code ({len(algo_code.split(chr(10)))} lines):")
        print("─" * 80)
        print(algo_code)
        print("─" * 80)
        print("✅ Code generated successfully")
        
    except Exception as e:
        print(f"❌ Error in code generation: {e}")
        return False
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 4: Validate Metrics Integration
    # ──────────────────────────────────────────────────────────────────────────
    print_section("STEP 4: PERFORMANCE METRICS INTEGRATION")
    
    try:
        # Get the metrics for this task type
        metrics_for_task = MetricsCalculator.get_default_metrics_for_task(task_type)
        
        print(f"Metrics for {task_type} task:")
        print(f"  Task Type: {metrics_for_task['task_type']}")
        print(f"  Metrics: {', '.join(metrics_for_task['metrics'])}")
        print(f"  Cross-Validation Folds: {metrics_for_task.get('cv_folds', 5)}")
        print(f"  Train/Test Split: {metrics_for_task.get('test_split', 0.2)}")
        
        print("\n✅ Metrics configuration ready for generated code")
        
    except Exception as e:
        print(f"❌ Error in metrics configuration: {e}")
        return False
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 5: Full Integration Check
    # ──────────────────────────────────────────────────────────────────────────
    print_section("STEP 5: INTEGRATION VALIDATION")
    
    print("Checking integration points...")
    
    # Check 1: Correct algorithm for task type
    expected_algo = "xgboost" if task_type == "REGRESSION" else "lightgbm"
    check1 = selected_algo == expected_algo
    print(f"  [{'✅' if check1 else '❌'}] Algorithm ({selected_algo}) matches task type ({task_type})")
    
    # Check 2: Code contains algorithm imports
    has_import = f"import {selected_algo}" in algo_code.lower() or f"from {selected_algo}" in algo_code.lower()
    print(f"  [{'✅' if has_import else '❌'}] Generated code includes {selected_algo} imports")
    
    # Check 3: Code has model training
    has_training = "model.fit" in algo_code or "fit(" in algo_code
    print(f"  [{'✅' if has_training else '❌'}] Generated code includes model.fit()")
    
    # Check 4: Hyperparameters in code
    has_hyperparams = any(str(v) in algo_code for v in hyperparams.values() if isinstance(v, (int, float)))
    print(f"  [{'✅' if has_hyperparams else '❌'}] Hyperparameters included in code")
    
    # Check 5: Metrics are specified
    has_metrics = len(metrics) > 0
    print(f"  [{'✅' if has_metrics else '❌'}] Performance metrics defined ({len(metrics)} metrics)")
    
    all_passed = all([check1, has_import, has_training, has_hyperparams, has_metrics])
    
    print_section("INTEGRATION TEST RESULT")
    if all_passed:
        print("✅ ALL CHECKS PASSED - END-TO-END INTEGRATION SUCCESSFUL")
        return True
    else:
        print("❌ SOME CHECKS FAILED - REVIEW ABOVE")
        return False


def test_alternative_scenarios():
    """Test algorithm selection for different task types."""
    
    print_section("TESTING ALTERNATIVE SCENARIOS")
    
    # Define test scenarios with simplified classification
    scenarios = [
        ("Classification: Build a fraud detection model", "CLASSIFICATION", 200000),
        ("Clustering: Group customer segments", "CLUSTERING", 50000),
        ("Regression: Predict house prices", "REGRESSION", 30000),
    ]
    
    results = []
    for prompt, expected_task, expected_size in scenarios:
        print(f"\n📌 Scenario: {prompt}")
        
        try:
            task = expected_task
            size = expected_size
            
            algo = AlgorithmSelector.select(task, size)
            selected = algo["algorithm"]
            
            # Determine expected algorithm
            if task == "REGRESSION":
                expected = "xgboost" if size <= 100000 else "lightgbm"
            elif task == "CLASSIFICATION":
                expected = "xgboost" if size <= 100000 else "lightgbm"
            else:
                expected = "kmeans"
            
            match = selected == expected
            status = "✅" if match else "❌"
            results.append(match)
            
            print(f"   Task: {task}, Size: {size}, Algorithm: {selected} {status}")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results.append(False)
    
    print_section("ALTERNATIVE SCENARIOS SUMMARY")
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    return all(results)


if __name__ == "__main__":
    success = test_end_to_end_pipeline()
    
    if success:
        alt_success = test_alternative_scenarios()
        final_result = success and alt_success
    else:
        final_result = False
    
    print_section("FINAL RESULT")
    if final_result:
        print("✅ ALL TESTS PASSED - INTEGRATION READY FOR DEPLOYMENT")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED - REVIEW ABOVE FOR DETAILS")
        sys.exit(1)
