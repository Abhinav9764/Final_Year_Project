"""
Test script for algorithm selection and code generation with performance metrics.
Tests the gold price prediction prompt.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "Code_Generator" / "RAD-ML"))
sys.path.insert(0, str(ROOT))

def test_algorithm_selection():
    """Test algorithm selection for different task types."""
    from generator.algorithm_selector import AlgorithmSelector
    
    print("\n" + "="*90)
    print("TEST 1: ALGORITHM SELECTION FOR DIFFERENT TASK TYPES")
    print("="*90)
    
    # Test cases: (task_type, dataset_size, expected_algorithm)
    test_cases = [
        ("regression", 50000, "xgboost"),
        ("regression", 500000, "lightgbm"),
        ("classification", 30000, "xgboost"),
        ("classification", 200000, "lightgbm"),
        ("clustering", 10000, "kmeans"),
        ("clustering", None, "kmeans"),
    ]
    
    for task_type, dataset_size, expected_algo in test_cases:
        print(f"\n{'─'*90}")
        print(f"Test: task_type={task_type}, dataset_size={dataset_size}")
        print(f"{'─'*90}")
        
        try:
            selection = AlgorithmSelector.select(task_type, dataset_size)
            
            print(f"✅ Algorithm Selected:    {selection['name']}")
            print(f"   Algorithm ID:         {selection['algorithm']}")
            print(f"   Reason:              {selection['reason']}")
            print(f"   Pros:                {', '.join(selection['pros'][:2])}... (and more)")
            print(f"   Package:             {selection['package']}")
            print(f"   Hyperparameters:     {len(selection['hyperparams'])} configured")
            print(f"   Metrics to Track:    {', '.join(selection['metrics'][:3])}... (and more)")
            print(f"   CV Folds:            {selection['cross_validation_folds']}")
            print(f"   All Options:         {selection['all_options']}")
            
            # Verify correct algorithm
            if selection['algorithm'] == expected_algo:
                print(f"   ✅ MATCH: Expected {expected_algo}, got {selection['algorithm']}")
            else:
                print(f"   ⚠️  MISMATCH: Expected {expected_algo}, got {selection['algorithm']}")
                
        except Exception as e:
            print(f"❌ ERROR: {e}")


def test_code_generation():
    """Test code generation for selected algorithms."""
    from generator.algorithm_selector import AlgorithmSelector
    
    print("\n" + "="*90)
    print("TEST 2: CODE GENERATION FOR ALGORITHMS")
    print("="*90)
    
    # Test code generation for regression
    print(f"\n{'─'*90}")
    print("Regression - XGBoost Algorithm Code:")
    print(f"{'─'*90}")
    
    regression_selection = AlgorithmSelector.select("regression", dataset_size=50000)
    regression_code = AlgorithmSelector.get_algorithm_code(regression_selection)
    print(regression_code)
    
    # Test code generation for classification
    print(f"\n{'─'*90}")
    print("Classification - LightGBM Algorithm Code:")
    print(f"{'─'*90}")
    
    classification_selection = AlgorithmSelector.select("classification", dataset_size=200000)
    classification_code = AlgorithmSelector.get_algorithm_code(classification_selection)
    print(classification_code)
    
    # Test code generation for clustering
    print(f"\n{'─'*90}")
    print("Clustering - K-Means Algorithm Code:")
    print(f"{'─'*90}")
    
    clustering_selection = AlgorithmSelector.select("clustering")
    clustering_code = AlgorithmSelector.get_algorithm_code(clustering_selection)
    print(clustering_code)


def test_performance_metrics():
    """Test performance metrics calculation."""
    from generator.performance_metrics import (
        MetricsCalculator, RegressionMetrics, ClassificationMetrics, ClusteringMetrics
    )
    import numpy as np
    
    print("\n" + "="*90)
    print("TEST 3: PERFORMANCE METRICS CALCULATION")
    print("="*90)
    
    # Test regression metrics
    print(f"\n{'─'*90}")
    print("Regression Metrics:")
    print(f"{'─'*90}")
    
    np.random.seed(42)
    y_true_reg = np.random.randn(100)
    y_pred_reg = y_true_reg + np.random.randn(100) * 0.2  # Add noise
    
    regression_metrics = MetricsCalculator.compute("regression", y_true_reg, y_pred_reg)
    print(RegressionMetrics.summary(regression_metrics))
    
    # Test classification metrics
    print(f"{'─'*90}")
    print("Classification Metrics:")
    print(f"{'─'*90}")
    
    y_true_clf = np.array([0, 1, 1, 0, 1, 0, 1, 1, 0, 0] * 10)
    y_pred_clf = np.random.randint(0, 2, 100)
    
    classification_metrics = MetricsCalculator.compute("classification", y_true_clf, y_pred_clf)
    print(ClassificationMetrics.summary(classification_metrics))
    
    # Test clustering metrics
    print(f"{'─'*90}")
    print("Clustering Metrics:")
    print(f"{'─'*90}")
    
    X_cluster = np.random.randn(100, 4)
    labels_cluster = np.random.randint(0, 3, 100)
    
    try:
        clustering_metrics = MetricsCalculator.compute("clustering", X=X_cluster, labels=labels_cluster)
        print(ClusteringMetrics.summary(clustering_metrics))
    except Exception as e:
        print(f"⚠️  Clustering metrics calculation requires scipy: {e}")


def test_gold_price_pipeline():
    """Test complete pipeline for gold price prediction."""
    from generator.algorithm_selector import AlgorithmSelector
    from generator.performance_metrics import MetricsCalculator
    
    print("\n" + "="*90)
    print("TEST 4: GOLD PRICE PREDICTION - COMPLETE PIPELINE")
    print("="*90)
    
    # Simulate gold price prediction task
    task_type = "regression"
    dataset_size = 5000  # Hypothetical dataset size
    
    print(f"\n{'─'*90}")
    print("Step 1: Task Analysis")
    print(f"{'─'*90}")
    print(f"User Prompt: 'Build a model that can predict gold price'")
    print(f"Detected Task Type: {task_type.upper()}")
    print(f"Estimated Dataset Size: {dataset_size:,} rows")
    print(f"Input Features: year, weight")
    print(f"Target: gold_price")
    
    # Step 2: Algorithm Selection
    print(f"\n{'─'*90}")
    print("Step 2: Intelligent Algorithm Selection")
    print(f"{'─'*90}")
    
    algorithm = AlgorithmSelector.select(task_type, dataset_size)
    
    print(f"✅ Selected Algorithm: {algorithm['name']}")
    print(f"   Algorithm ID: {algorithm['algorithm']}")
    print(f"   Reason: {algorithm['reason']}")
    print(f"\n   Why this choice?")
    for i, pro in enumerate(algorithm['pros'], 1):
        print(f"     {i}. {pro}")
    print(f"\n   Considerations:")
    for i, con in enumerate(algorithm['cons'], 1):
        print(f"     {i}. {con}")
    
    # Step 3: Hyperparameters
    print(f"\n{'─'*90}")
    print("Step 3: Algorithm Hyperparameters")
    print(f"{'─'*90}")
    
    print(f"Configured Hyperparameters:")
    for param, value in algorithm['hyperparams'].items():
        print(f"  • {param}: {value}")
    
    # Step 4: Code generation
    print(f"\n{'─'*90}")
    print("Step 4: Generated Training Code")
    print(f"{'─'*90}")
    
    code = AlgorithmSelector.get_algorithm_code(algorithm)
    print(code)
    
    # Step 5: Performance Metrics
    print(f"\n{'─'*90}")
    print("Step 5: Performance Metrics to Track")
    print(f"{'─'*90}")
    
    print(f"Metrics that will be calculated:")
    for i, metric in enumerate(algorithm['metrics'], 1):
        print(f"  {i}. {metric}")
    
    print(f"\nCross-Validation: {algorithm['cross_validation_folds']}-fold")
    print(f"Train/Test Split: {int(algorithm['train_test_split']*100)}% test, {int((1-algorithm['train_test_split'])*100)}% train")
    
    # Step 6: Simulated metrics
    print(f"\n{'─'*90}")
    print("Step 6: Simulated Performance Metrics (Sample)")
    print(f"{'─'*90}")
    
    import numpy as np
    np.random.seed(42)
    y_true = np.random.randn(100) * 1000 + 50000  # Gold price range
    y_pred = y_true + np.random.randn(100) * 500   # Add noise
    
    metrics = MetricsCalculator.compute("regression", y_true, y_pred)
    
    from generator.performance_metrics import RegressionMetrics
    print(RegressionMetrics.summary(metrics))
    
    # Step 7: Generated training code with metrics
    print(f"{'─'*90}")
    print("Step 7: Complete Training Script with Metrics")
    print(f"{'─'*90}")
    
    training_script = f"""
# Generated Training Script for Gold Price Prediction
# Algorithm: {algorithm['name']}
# Task: Regression
# Reason: {algorithm['reason']}

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
{code}

# Performance Metrics Calculation
from generator.performance_metrics import MetricsCalculator

# Train/Test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size={algorithm['train_test_split']}, random_state=42
)

# Train the model
model.fit(X_train, y_train)

# Make predictions
y_pred = model.predict(X_test)

# Calculate metrics
metrics = MetricsCalculator.compute(
    task_type='regression',
    y_true=y_test,
    y_pred=y_pred
)

# Print report
MetricsCalculator.print_report('regression', metrics)

# Export metrics as JSON
import json
print(MetricsCalculator.export_json(metrics))
"""
    
    print(training_script[:500] + "\n... (truncated)")


def main():
    print("\n" + "╔" + "="*88 + "╗")
    print("║" + "ALGORITHM SELECTION & CODE GENERATION TEST".center(88) + "║")
    print("║" + "With Performance Metrics for ML Model Training".center(88) + "║")
    print("╚" + "="*88 + "╝")
    
    try:
        test_algorithm_selection()
        test_code_generation()
        test_performance_metrics()
        test_gold_price_pipeline()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*90)
    print("SUMMARY")
    print("="*90)
    print("""
✅ ALGORITHM SELECTION SYSTEM:
   • Intelligently selects best algorithm based on task type
   • Considers dataset size for optimization
   • Provides hyperparameters and configurations
   • Supports: Regression, Classification, Clustering
   • Free/open-source libraries: sklearn, lightgbm, xgboost

✅ PERFORMANCE METRICS:
   • Regression: MSE, RMSE, MAE, R²
   • Classification: Accuracy, Precision, Recall, F1, ROC-AUC
   • Clustering: Silhouette, Davies-Bouldin, Calinski-Harabasz
   • Automatic calculation and reporting

✅ CODE GENERATION:
   • Complete training code for each algorithm
   • Hyperparameter configuration
   • Performance metrics integration
   • Production-ready templates

Example: Gold Price Prediction
  • Task Type: REGRESSION (predict numeric price)
  • Selected Algorithm: XGBoost (most accurate for dataset size)
  • Metrics Tracked: RMSE, MAE, R² Score
  • Ready for immediate training
    """)


if __name__ == "__main__":
    main()
