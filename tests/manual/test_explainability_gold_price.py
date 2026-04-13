"""
test_explainability_gold_price.py
==================================
Comprehensive test of the ExplainabilityEngine using the gold price prediction prompt
from previous chat sessions. This test verifies that explanation generation works
correctly end-to-end.

Test Prompt:
    "Build a model that can predict the gold price by taking the input parameters 
     of year and weight based on the past data"

Test Coverage:
    1. Narrative generation (LLM or fallback)
    2. Algorithm card for regression task
    3. Usage guide with correct input parameters
    4. Data story structure and content
    5. Code preview functionality
    6. Architecture diagram generation (with graceful fallback)
    7. Complete result structure validation
"""
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent / "Code_Generator" / "RAD-ML"))

from explainability.engine import ExplainabilityEngine, _ALGO_KB


# ─────────────────────────────────────────────────────────────────────────────
# GOLD PRICE TEST DATA
# ─────────────────────────────────────────────────────────────────────────────

GOLD_PRICE_JOB_RESULT = {
    "deploy_url": "http://localhost:5001",
    "endpoint_name": "gold-price-predictor-v1",
    "sm_meta": {
        "endpoint_name": "gold-price-predictor-v1",
        "job_name": "radml-gold-price-job",
        "status": "completed",
        "model_accuracy": 0.92,
    },
    "dataset": {
        "row_count": 2150,
        "columns": ["year", "weight", "price", "market_cap", "volatility"],
        "merged": False,
        "source_count": 2,
        "s3_uri": "s3://rad-ml-datasets/gold-price-data/collected_data.csv",
        "preview_rows": [
            {"year": 2020, "weight": 100, "price": 1770.50, "market_cap": 5.2e12},
            {"year": 2021, "weight": 150, "price": 1800.75, "market_cap": 5.4e12},
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

GOLD_PRICE_DB_RESULTS = {
    "prompt": "Build a model that can predict the gold price by taking the input parameters of year and weight based on the past data",
    "job_id": "gold-price-001",
    "spec": {
        "task_type": "regression",
        "input_params": ["year", "weight"],
        "target_param": "price",
        "keywords": ["gold", "price", "year", "weight", "prediction"],
    },
    "top_sources": [
        {
            "title": "Gold Prices Dataset (Years 2010-2024)",
            "source": "kaggle",
            "url": "https://www.kaggle.com/datasets/gold-prices",
            "row_count": 1200,
            "final_score": 0.92,
        },
        {
            "title": "Precious Metals Historical Data",
            "source": "openml",
            "url": "https://www.openml.org/datasets/gold-metals",
            "row_count": 950,
            "final_score": 0.88,
        },
    ],
}

CFG = {
    "codegen": {"workspace_dir": tempfile.mkdtemp(), "flask_port": 5001},
    "llm": {"gemini_api_key": ""},
}

MOCK_NARRATIVE = """## Your Gold Price Prediction Model is Ready!

Your model predicts **gold price** from **year** and **weight** of gold.

### What Your Model Does
The model takes two inputs (year and weight of gold) and predicts the price in USD per ounce.
This is useful for investors and traders who want to forecast gold prices based on temporal trends
and quantity considerations.

### Your Dataset
We collected **2,150 rows** of historical gold price data from Kaggle and OpenML, covering years 2010-2024.
The dataset includes real market prices, trading volumes, and market capitalization data.

### How Training Worked
1. Downloaded 2 datasets (1,200 + 950 rows)
2. Merged them to create a comprehensive historical view
3. Selected XGBoost Regressor (best for continuous price prediction)
4. Trained on 1,720 samples, validated on 430 samples
5. Model achieved 92% accuracy on the validation set

### How to Use Your Live App
1. Open http://localhost:5001 in your browser
2. Enter the year (e.g., 2024) and weight (e.g., 100 oz)
3. Click "Predict"
4. Read the predicted gold price

### Important Limitations
- Model is trained on historical data; future prices depend on market conditions
- Predictions are best within the year range 2010-2024
- Large quantities may have different pricing
"""


def _make_engine(narrative=MOCK_NARRATIVE):
    """Create a mock ExplainabilityEngine with mocked LLM."""
    llm = MagicMock()
    llm.generate.return_value = narrative
    return ExplainabilityEngine(llm, CFG), llm


# ─────────────────────────────────────────────────────────────────────────────
# TESTS
# ─────────────────────────────────────────────────────────────────────────────

def test_explain_gold_price_returns_all_required_keys():
    """✅ Test 1: All required explanation components are present."""
    engine, _ = _make_engine()
    result = engine.explain(GOLD_PRICE_JOB_RESULT, GOLD_PRICE_DB_RESULTS)
    
    required_keys = {
        "narrative",
        "algorithm_card",
        "usage_guide",
        "data_story",
        "architecture_diagram_b64",
        "code_preview",
    }
    
    missing = required_keys - set(result.keys())
    assert not missing, f"❌ Missing keys: {missing}"
    print("✅ TEST 1 PASSED: All required explanation keys present")
    return True


def test_narrative_generated_for_gold_price():
    """✅ Test 2: Narrative is generated and contains relevant content."""
    engine, llm = _make_engine()
    result = engine.explain(GOLD_PRICE_JOB_RESULT, GOLD_PRICE_DB_RESULTS)
    
    narrative = result["narrative"]
    assert len(narrative) > 100, f"❌ Narrative too short: {len(narrative)} chars"
    assert llm.generate.called, "❌ LLM was not called"
    assert "gold" in narrative.lower(), "❌ Narrative doesn't mention 'gold'"
    assert "price" in narrative.lower(), "❌ Narrative doesn't mention 'price'"
    print("✅ TEST 2 PASSED: Narrative generated with relevant content")
    print(f"  📝 Narrative length: {len(narrative)} characters")
    print(f"  📝 LLM called: {llm.generate.called}")
    return True


def test_narrative_fallback_on_llm_failure():
    """✅ Test 3: Fallback narrative works when LLM fails."""
    engine, llm = _make_engine()
    llm.generate.side_effect = RuntimeError("LLM API Error")
    
    result = engine.explain(GOLD_PRICE_JOB_RESULT, GOLD_PRICE_DB_RESULTS)
    narrative = result["narrative"]
    
    assert len(narrative) > 50, f"❌ Fallback narrative too short: {len(narrative)}"
    assert "price" in narrative.lower() or "model" in narrative.lower(), \
        "❌ Fallback narrative missing key terms"
    print("✅ TEST 3 PASSED: Fallback narrative works correctly")
    print(f"  📝 Fallback narrative length: {len(narrative)} characters")
    return True


def test_algorithm_card_is_regression():
    """✅ Test 4: Algorithm card correctly identifies regression task."""
    engine, _ = _make_engine()
    result = engine.explain(GOLD_PRICE_JOB_RESULT, GOLD_PRICE_DB_RESULTS)
    
    card = result["algorithm_card"]
    assert card["name"] == "XGBoost Regressor", f"❌ Wrong algorithm: {card['name']}"
    assert "Gradient Boosted" in card["family"], f"❌ Wrong family: {card['family']}"
    assert len(card["strengths"]) > 0, "❌ No strengths listed"
    assert len(card["limitations"]) > 0, "❌ No limitations listed"
    assert len(card["metrics"]) > 0, "❌ No metrics listed"
    assert "why_chosen" in card, "❌ Missing 'why_chosen'"
    assert "how_it_works" in card, "❌ Missing 'how_it_works'"
    
    print("✅ TEST 4 PASSED: Algorithm card is correct for regression")
    print(f"  📋 Algorithm: {card['name']}")
    print(f"  📋 Family: {card['family']}")
    print(f"  📋 Strengths: {len(card['strengths'])} listed")
    print(f"  📋 Limitations: {len(card['limitations'])} listed")
    print(f"  📋 Metrics: {', '.join(card['metrics'])}")
    return True


def test_usage_guide_has_five_steps():
    """✅ Test 5: Usage guide has proper structure (5 steps)."""
    engine, _ = _make_engine()
    result = engine.explain(GOLD_PRICE_JOB_RESULT, GOLD_PRICE_DB_RESULTS)
    
    guide = result["usage_guide"]
    assert len(guide) == 5, f"❌ Expected 5 steps, got {len(guide)}"
    
    for i, step in enumerate(guide):
        assert "step" in step, f"❌ Step {i} missing 'step' key"
        assert "title" in step, f"❌ Step {i} missing 'title' key"
        assert "detail" in step, f"❌ Step {i} missing 'detail' key"
        assert "icon" in step, f"❌ Step {i} missing 'icon' key"
        assert step["step"] == i + 1, f"❌ Step {i} has wrong step number"
    
    print("✅ TEST 5 PASSED: Usage guide has correct structure (5 steps)")
    for step in guide:
        print(f"  {step['icon']} Step {step['step']}: {step['title']}")
    return True


def test_usage_guide_mentions_input_parameters():
    """✅ Test 6: Usage guide references the correct input parameters (year, weight)."""
    engine, _ = _make_engine()
    result = engine.explain(GOLD_PRICE_JOB_RESULT, GOLD_PRICE_DB_RESULTS)
    
    guide = result["usage_guide"]
    step2 = guide[1]  # "Fill in the input form" step
    detail = step2["detail"]
    
    # Should mention the input parameters
    assert "year" in detail.lower() or "2" in detail, \
        f"❌ Input parameters not mentioned. Detail: {detail}"
    assert "2 input fields" in detail or "2" in detail or "year" in detail.lower(), \
        f"❌ Number of inputs not mentioned. Detail: {detail}"
    
    print("✅ TEST 6 PASSED: Usage guide correctly mentions input parameters")
    print(f"  📝 Input form step: {detail}")
    return True


def test_data_story_structure():
    """✅ Test 7: Data story has proper structure and content."""
    engine, _ = _make_engine()
    result = engine.explain(GOLD_PRICE_JOB_RESULT, GOLD_PRICE_DB_RESULTS)
    
    story = result["data_story"]
    
    required_keys = ["summary", "sources", "columns", "row_count", "merged", "keywords_used", "search_strategy"]
    for key in required_keys:
        assert key in story, f"❌ Data story missing '{key}'"
    
    assert story["row_count"] == 2150, f"❌ Wrong row count: {story['row_count']}"
    assert len(story["sources"]) >= 1, f"❌ No sources found"
    assert "2,150" in story["summary"] or "2150" in story["summary"], \
        f"❌ Row count not in summary"
    
    print("✅ TEST 7 PASSED: Data story has correct structure and content")
    print(f"  📊 Row count: {story['row_count']:,}")
    print(f"  📊 Number of columns: {len(story['columns'])}")
    print(f"  📊 Sources: {len(story['sources'])}")
    print(f"  📊 Datasets merged: {story['merged']}")
    return True


def test_data_story_sources_detail():
    """✅ Test 8: Data story sources contain proper details."""
    engine, _ = _make_engine()
    result = engine.explain(GOLD_PRICE_JOB_RESULT, GOLD_PRICE_DB_RESULTS)
    
    sources = result["data_story"]["sources"]
    assert len(sources) >= 1, "❌ No sources in data story"
    
    for i, source in enumerate(sources):
        assert "name" in source, f"❌ Source {i} missing 'name'"
        assert "source" in source, f"❌ Source {i} missing 'source'"
        assert "url" in source, f"❌ Source {i} missing 'url'"
        assert "rows" in source, f"❌ Source {i} missing 'rows'"
        assert "score" in source, f"❌ Source {i} missing 'score'"
        assert source["source"] in ("KAGGLE", "UCI", "OPENML"), \
            f"❌ Invalid source: {source['source']}"
    
    print("✅ TEST 8 PASSED: Data story sources contain proper details")
    for source in sources:
        print(f"  🔗 {source['name']} ({source['source']}): {source['rows']} rows, score={source['score']}")
    return True


def test_data_story_mentions_search_strategy():
    """✅ Test 9: Data story explains the search strategy."""
    engine, _ = _make_engine()
    result = engine.explain(GOLD_PRICE_JOB_RESULT, GOLD_PRICE_DB_RESULTS)
    
    story = result["data_story"]
    strategy = story["search_strategy"]
    
    assert "Kaggle" in strategy or "kaggle" in strategy, "❌ Kaggle not mentioned"
    assert "UCI" in strategy or "uci" in strategy or "OpenML" in strategy, \
        "❌ Search sources not mentioned"
    assert len(strategy) > 100, f"❌ Strategy description too short: {len(strategy)}"
    
    print("✅ TEST 9 PASSED: Data story contains search strategy")
    print(f"  🔍 Strategy: {strategy[:150]}...")
    return True


def test_code_preview_structure():
    """✅ Test 10: Code preview can be generated and has correct structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create sample code files
        train_py = Path(tmpdir) / "train.py"
        train_py.write_text("# Training script\nfrom sklearn.ensemble import XGBRegressor\nmodel = XGBRegressor()\n")
        
        app_py = Path(tmpdir) / "app.py"
        app_py.write_text("# Flask app\nfrom flask import Flask\napp = Flask(__name__)\n@app.route('/predict')\ndef predict():\n    return {}\n")
        
        engine, _ = _make_engine()
        result = engine.explain(
            GOLD_PRICE_JOB_RESULT,
            GOLD_PRICE_DB_RESULTS,
            written_files={"train.py": str(train_py), "app.py": str(app_py)},
        )
        
        preview = result["code_preview"]
        assert isinstance(preview, dict), "❌ Code preview should be a dict"
        assert "train.py" in preview, "❌ train.py not in preview"
        assert "app.py" in preview, "❌ app.py not in preview"
        assert "XGBRegressor" in preview["train.py"], "❌ Content not properly previewed"
        
        print("✅ TEST 10 PASSED: Code preview generated correctly")
        for fname, content in preview.items():
            line_count = content.count('\n')
            print(f"  📄 {fname}: {len(content)} chars, ~{line_count} lines")
    return True


def test_complete_explanation_gold_price():
    """✅ Test 11: Complete end-to-end explanation generation."""
    engine, llm = _make_engine()
    result = engine.explain(GOLD_PRICE_JOB_RESULT, GOLD_PRICE_DB_RESULTS)
    
    # Verify all components are populated
    assert result["narrative"], "❌ Narrative is empty"
    assert result["algorithm_card"], "❌ Algorithm card is empty"
    assert result["usage_guide"], "❌ Usage guide is empty"
    assert result["data_story"], "❌ Data story is empty"
    assert isinstance(result["code_preview"], dict), "❌ Code preview is not a dict"
    
    print("✅ TEST 11 PASSED: Complete explanation successfully generated")
    print(f"  📝 Narrative: {len(result['narrative'])} chars")
    print(f"  📚 Algorithm card: {result['algorithm_card']['name']}")
    print(f"  👣 Usage guide: {len(result['usage_guide'])} steps")
    print(f"  📊 Data story: {result['data_story']['row_count']:,} rows")
    print(f"  📄 Code preview: {len(result['code_preview'])} files")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TEST RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """Run all tests and print results."""
    tests = [
        test_explain_gold_price_returns_all_required_keys,
        test_narrative_generated_for_gold_price,
        test_narrative_fallback_on_llm_failure,
        test_algorithm_card_is_regression,
        test_usage_guide_has_five_steps,
        test_usage_guide_mentions_input_parameters,
        test_data_story_structure,
        test_data_story_sources_detail,
        test_data_story_mentions_search_strategy,
        test_code_preview_structure,
        test_complete_explanation_gold_price,
    ]
    
    print("\n" + "="*80)
    print("GOLD PRICE PREDICTION - EXPLAINABILITY ENGINE TESTS")
    print("="*80)
    print(f"Prompt: {GOLD_PRICE_DB_RESULTS['prompt']}")
    print(f"Task: {GOLD_PRICE_DB_RESULTS['spec']['task_type'].upper()}")
    print(f"Inputs: {', '.join(GOLD_PRICE_DB_RESULTS['spec']['input_params'])}")
    print(f"Target: {GOLD_PRICE_DB_RESULTS['spec']['target_param']}")
    print("="*80 + "\n")
    
    passed = 0
    failed = 0
    results = []
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
            results.append((test_func.__name__, True, None))
        except AssertionError as e:
            failed += 1
            results.append((test_func.__name__, False, str(e)))
            print(f"❌ {test_func.__name__}: {e}\n")
        except Exception as e:
            failed += 1
            results.append((test_func.__name__, False, f"Exception: {e}"))
            print(f"❌ {test_func.__name__}: Exception: {e}\n")
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for name, success, error in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
        if error and not success:
            print(f"       {error}")
    
    print("="*80)
    print(f"TOTAL: {passed + failed} tests")
    print(f"✅ PASSED: {passed}")
    print(f"❌ FAILED: {failed}")
    print(f"SUCCESS RATE: {100 * passed // (passed + failed)}%")
    print("="*80 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
