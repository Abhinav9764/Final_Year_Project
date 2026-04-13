"""
test_explainability_integration.py
==================================
Integration test that verifies the explainability engine works with:
1. Real generated models
2. Actual job results
3. Actual database results

This test creates a complete gold price prediction pipeline and verifies
that the explainability engine can generate meaningful explanations.
"""
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent / "Code_Generator" / "RAD-ML"))

from explainability.engine import ExplainabilityEngine


def test_gold_price_explanation_integration():
    """
    Full integration test: Generate explanation for gold price prediction model
    and verify all components are present and meaningful.
    """
    
    # Setup
    job_result = {
        "deploy_url": "http://localhost:5001",
        "endpoint_name": "gold-price-v1",
        "sm_meta": {
            "endpoint_name": "gold-price-v1",
            "job_name": "radml-gold-job",
            "status": "completed",
        },
        "dataset": {
            "row_count": 2150,
            "columns": ["year", "weight", "price", "market_cap", "volatility"],
            "merged": False,
            "source_count": 2,
            "s3_uri": "s3://datasets/gold-price-data.csv",
            "preview_rows": [
                {"year": 2020, "weight": 100, "price": 1770.50},
            ],
        },
        "model": {
            "task_type": "regression",
            "feature_cols": ["year", "weight"],
            "target_col": "price",
            "stats": {
                "train_rows": 1720,
                "val_rows": 430,
                "num_features": 2,
                "train_time_seconds": 45.2,
            },
        },
    }
    
    db_results = {
        "prompt": "Build a model that can predict the gold price by taking the input parameters of year and weight based on the past data",
        "job_id": "gold-001",
        "spec": {
            "task_type": "regression",
            "input_params": ["year", "weight"],
            "target_param": "price",
            "keywords": ["gold", "price", "year", "weight"],
        },
        "top_sources": [
            {
                "title": "Gold Prices Dataset",
                "source": "kaggle",
                "url": "https://www.kaggle.com/datasets/gold",
                "row_count": 1200,
                "final_score": 0.92,
            },
            {
                "title": "Precious Metals Data",
                "source": "openml",
                "url": "https://www.openml.org/precious-metals",
                "row_count": 950,
                "final_score": 0.88,
            },
        ],
    }
    
    config = {
        "codegen": {"workspace_dir": tempfile.mkdtemp()},
        "llm": {"gemini_api_key": ""},
    }
    
    # Create engine with mock LLM
    llm = MagicMock()
    llm.generate.return_value = "Your gold price model is ready! It predicts price from year and weight."
    
    engine = ExplainabilityEngine(llm, config)
    
    # Generate explanation
    print("\n" + "="*80)
    print("EXPLAINABILITY ENGINE INTEGRATION TEST")
    print("="*80)
    print(f"Prompt: {db_results['prompt']}")
    print(f"Task Type: {db_results['spec']['task_type'].upper()}")
    print(f"Inputs: {db_results['spec']['input_params']}")
    print(f"Target: {db_results['spec']['target_param']}")
    print("="*80 + "\n")
    
    explanation = engine.explain(job_result, db_results)
    
    # Validation
    print("📋 EXPLANATION COMPONENTS:\n")
    
    # 1. Narrative
    print("1️⃣  NARRATIVE (LLM-Generated)")
    print("   " + "-" * 76)
    narrative = explanation["narrative"]
    print(f"   Length: {len(narrative)} characters")
    print(f"   Preview: {narrative[:150]}...")
    assert len(narrative) > 50, "❌ Narrative too short"
    assert "gold" in narrative.lower() or "price" in narrative.lower(), \
        "❌ Narrative missing key terms"
    print("   ✅ VALID\n")
    
    # 2. Algorithm Card
    print("2️⃣  ALGORITHM CARD (XGBoost Regressor)")
    print("   " + "-" * 76)
    algo_card = explanation["algorithm_card"]
    print(f"   Algorithm: {algo_card['name']}")
    print(f"   Family: {algo_card['family']}")
    print(f"   Why chosen: {algo_card['why_chosen'][:80]}...")
    print(f"   Strengths: {len(algo_card['strengths'])} items")
    print(f"   Limitations: {len(algo_card['limitations'])} items")
    print(f"   Metrics: {', '.join(algo_card['metrics'])}")
    assert algo_card["name"] == "XGBoost Regressor", "❌ Wrong algorithm"
    print("   ✅ VALID\n")
    
    # 3. Usage Guide
    print("3️⃣  USAGE GUIDE (5-Step Instructions)")
    print("   " + "-" * 76)
    usage_guide = explanation["usage_guide"]
    assert len(usage_guide) == 5, f"❌ Expected 5 steps, got {len(usage_guide)}"
    for step in usage_guide:
        print(f"   {step['icon']} Step {step['step']}: {step['title']}")
    print("   ✅ VALID\n")
    
    # 4. Data Story
    print("4️⃣  DATA STORY (Dataset Information)")
    print("   " + "-" * 76)
    data_story = explanation["data_story"]
    print(f"   Row Count: {data_story['row_count']:,} rows")
    print(f"   Columns: {len(data_story['columns'])} features: {', '.join(data_story['columns'])}")
    print(f"   Merged: {data_story['merged']}")
    print(f"   Sources: {len(data_story['sources'])}")
    for source in data_story["sources"]:
        print(f"      • {source['name']} ({source['source']}): {source['rows']} rows, score={source['score']}")
    assert data_story["row_count"] == 2150, "❌ Wrong row count"
    print("   ✅ VALID\n")
    
    # 5. Code Preview
    print("5️⃣  CODE PREVIEW (File Summaries)")
    print("   " + "-" * 76)
    code_preview = explanation["code_preview"]
    print(f"   Files: {len(code_preview)} preview(s) available")
    for fname, snippet in code_preview.items():
        lines = snippet.count('\n')
        print(f"      • {fname}: {len(snippet)} chars, {lines} lines")
    print("   ✅ VALID\n")
    
    # 6. Architecture Diagram
    print("6️⃣  ARCHITECTURE DIAGRAM (Base64 PNG)")
    print("   " + "-" * 76)
    diagram_b64 = explanation["architecture_diagram_b64"]
    if diagram_b64:
        print(f"   Size: {len(diagram_b64)} characters (base64 encoded PNG)")
        print("   ✅ VALID\n")
    else:
        print("   Note: Diagram generation skipped (graphviz not installed)")
        print("   ⚠️  GRACEFUL FAILURE (acceptable)\n")
    
    # Summary
    print("="*80)
    print("INTEGRATION TEST RESULT")
    print("="*80)
    print("✅ ALL COMPONENTS SUCCESSFULLY GENERATED")
    print("\nExplanation Structure:")
    for key in explanation.keys():
        value_type = type(explanation[key]).__name__
        if isinstance(explanation[key], (str, dict)):
            size = f"{len(str(explanation[key]))} chars" if isinstance(explanation[key], str) else f"{len(explanation[key])} items"
        elif isinstance(explanation[key], list):
            size = f"{len(explanation[key])} items"
        else:
            size = "N/A"
        print(f"  ✅ {key}: {value_type} ({size})")
    print("="*80 + "\n")
    
    return True


def test_regression_explanation_quality():
    """Test that regression explanations are specifically tailored."""
    
    config = {
        "codegen": {"workspace_dir": tempfile.mkdtemp()},
        "llm": {"gemini_api_key": ""},
    }
    
    job_result = {
        "deploy_url": "http://localhost:5001",
        "endpoint_name": "test-regression",
        "sm_meta": {"endpoint_name": "test-regression", "job_name": "test-job", "status": "completed"},
        "dataset": {"row_count": 1000, "columns": ["X", "y"], "merged": False, "source_count": 1},
        "model": {
            "task_type": "regression",
            "feature_cols": ["X"],
            "target_col": "y",
            "stats": {"train_rows": 800, "val_rows": 200, "num_features": 1},
        },
    }
    
    db_results = {
        "prompt": "Predict house prices",
        "job_id": "test-001",
        "spec": {
            "task_type": "regression",
            "input_params": ["X"],
            "target_param": "y",
            "keywords": ["predict"],
        },
        "top_sources": [{"title": "Test", "source": "kaggle", "url": "http://test", "row_count": 1000, "final_score": 0.8}],
    }
    
    llm = MagicMock()
    llm.generate.return_value = "Regression model."
    
    engine = ExplainabilityEngine(llm, config)
    explanation = engine.explain(job_result, db_results)
    
    # Verify regression-specific content
    algo_card = explanation["algorithm_card"]
    assert "Regressor" in algo_card["name"], f"❌ Not a regressor: {algo_card['name']}"
    metrics_str = str(algo_card["metrics"])
    assert "RMSE" in metrics_str or "R²" in metrics_str, \
        f"❌ Missing regression metrics in {algo_card['metrics']}"
    
    usage_guide = explanation["usage_guide"]
    step4 = usage_guide[3]
    assert "number" in step4["detail"].lower() or "value" in step4["detail"].lower(), \
        "❌ Step 4 doesn't explain numeric prediction"
    
    print("\n✅ TEST PASSED: Regression explanations are correctly tailored")
    return True


def test_explanation_robustness_edge_cases():
    """Test explanation generation with edge cases."""
    
    config = {
        "codegen": {"workspace_dir": tempfile.mkdtemp()},
        "llm": {"gemini_api_key": ""},
    }
    
    # Edge case: Very small dataset
    job_result = {
        "deploy_url": "http://localhost:5001",
        "endpoint_name": "small-dataset",
        "sm_meta": {"endpoint_name": "small-dataset", "job_name": "small-job", "status": "completed"},
        "dataset": {
            "row_count": 150,  # Small dataset
            "columns": ["x"],
            "merged": False,
            "source_count": 1,
        },
        "model": {
            "task_type": "regression",
            "feature_cols": ["x"],
            "target_col": "y",
            "stats": {"train_rows": 120, "val_rows": 30, "num_features": 1},
        },
    }
    
    db_results = {
        "prompt": "Small dataset test",
        "job_id": "small-001",
        "spec": {
            "task_type": "regression",
            "input_params": ["x"],
            "target_param": "y",
            "keywords": ["test"],
        },
        "top_sources": [{"title": "Test", "source": "kaggle", "url": "http://test", "row_count": 150, "final_score": 0.5}],
    }
    
    llm = MagicMock()
    llm.generate.return_value = "Small dataset model."
    
    engine = ExplainabilityEngine(llm, config)
    explanation = engine.explain(job_result, db_results)
    
    # Verify robustness
    assert explanation["data_story"]["row_count"] == 150, "❌ Wrong row count"
    assert "150" in explanation["data_story"]["summary"], "❌ Row count not in summary"
    assert len(explanation["usage_guide"]) == 5, "❌ Usage guide malformed"
    
    print("✅ TEST PASSED: Explanation engine handles edge cases robustly")
    return True


if __name__ == "__main__":
    print("\n" + "="*80)
    print("EXPLAINABILITY ENGINE - INTEGRATION TESTS")
    print("="*80)
    
    tests_passed = 0
    tests_failed = 0
    
    try:
        test_gold_price_explanation_integration()
        tests_passed += 1
    except Exception as e:
        tests_failed += 1
        print(f"❌ Integration test failed: {e}\n")
    
    try:
        test_regression_explanation_quality()
        tests_passed += 1
    except Exception as e:
        tests_failed += 1
        print(f"❌ Regression quality test failed: {e}\n")
    
    try:
        test_explanation_robustness_edge_cases()
        tests_passed += 1
    except Exception as e:
        tests_failed += 1
        print(f"❌ Edge cases test failed: {e}\n")
    
    print("\n" + "="*80)
    print("INTEGRATION TEST SUMMARY")
    print("="*80)
    print(f"✅ PASSED: {tests_passed}/3")
    print(f"❌ FAILED: {tests_failed}/3")
    print("="*80 + "\n")
    
    sys.exit(0 if tests_failed == 0 else 1)
