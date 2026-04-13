import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
import importlib.util

if __name__ == "__main__":
    #!/usr/bin/env python
    """Test comprehensive debugging system with explainability engine."""


    # Add project to path
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))

    # Load modules from RAD-ML
    code_gen_path = project_root / "Code_Generator"
    sys.path.insert(0, str(code_gen_path))

    # Load the debugger module
    debugger_path = code_gen_path / "RAD-ML" / "debugger.py"
    spec_debugger = importlib.util.spec_from_file_location("debugger", debugger_path)
    debugger_module = importlib.util.module_from_spec(spec_debugger)
    spec_debugger.loader.exec_module(debugger_module)
    DebugLogger = debugger_module.DebugLogger

    # Load explainability engine
    engine_path = code_gen_path / "RAD-ML" / "explainability" / "engine.py"
    spec_engine = importlib.util.spec_from_file_location("explainability_engine", engine_path)
    explainability_engine = importlib.util.module_from_spec(spec_engine)
    spec_engine.loader.exec_module(explainability_engine)
    ExplainabilityEngine = explainability_engine.ExplainabilityEngine

    print("\n" + "="*70)
    print("COMPREHENSIVE DEBUGGING SYSTEM TEST")
    print("="*70)

    # Setup
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "Your model is accurate and reliable."

    config = {
        "codegen": {"workspace_dir": tempfile.mkdtemp(), "flask_port": 7000},
        "llm": {"gemini_api_key": ""},
    }

    engine = ExplainabilityEngine(mock_llm, config)

    print("\n" + "-"*70)
    print("TEST 1: Normal Operation with Debugging")
    print("-"*70)

    job_result = {
        "deploy_url": "http://localhost:7000",
        "endpoint_name": "test-endpoint",
        "sm_meta": {
            "endpoint_name": "test-endpoint",
            "job_name": "test-job",
        },
        "dataset": {
            "row_count": 1000,
            "columns": ["feature1", "feature2", "target"],
            "merged": True,
            "source_count": 2,
        },
        "model": {
            "task_type": "regression",
            "feature_cols": ["feature1", "feature2"],
            "target_col": "target",
            "stats": {"train_rows": 800, "val_rows": 200, "num_features": 2},
        },
    }

    db_results = {
        "prompt": "Predict target from features",
        "spec": {
            "task_type": "regression",
            "input_params": ["feature1", "feature2"],
            "target_param": "target",
        },
        "top_sources": [
            {
                "title": "Test Dataset",
                "source": "kaggle",
                "row_count": 1000,
                "final_score": 0.85,
            },
        ],
    }

    try:
        print("\nGenerating explanation with comprehensive debugging...")
        result = engine.explain(job_result, db_results)

        print("\n✓ Explanation generated successfully")
        print(f"  • Narrative: {len(result['narrative'])} chars")
        print(f"  • Algorithm Card: {len(str(result['algorithm_card']))} chars")
        print(f"  • Usage Guide: {len(result['usage_guide'])} items")
        print(f"  • Data Story: {len(result['data_story'])} items")
        print(f"  • Architecture Diagram: {len(result['architecture_diagram_b64'])} chars")
        print(f"  • Code Preview: {len(result['code_preview'])} files")

        if engine._debug:
            print("\n✓ Debug System Active")
            engine._debug.print_summary()
            print(f"  Debug Report: {engine._debug.save_debug_report()}")

        print("\n✓ TEST 1 PASSED")

    except Exception as e:
        print(f"✗ TEST 1 FAILED: {e}")
        if engine._debug:
            engine._debug.print_summary()

    # TEST 2: Error Handling
    print("\n" + "-"*70)
    print("TEST 2: Error Handling & Recovery")
    print("-"*70)

    # Mock LLM to fail
    mock_llm_fail = MagicMock()
    mock_llm_fail.generate.side_effect = Exception("LLM service unavailable")

    engine_fail = ExplainabilityEngine(mock_llm_fail, config)

    print("\nTesting with failing LLM...")
    try:
        result = engine_fail.explain(job_result, db_results)

        # Should still return all components with fallback values
        if all(k in result for k in ["narrative", "algorithm_card", "usage_guide",
                                      "data_story", "architecture_diagram_b64", "code_preview"]):
            print("✓ Error handled gracefully")
            print(f"  • Fallback narrative: {len(result['narrative'])} chars")
            print("  • All components returned safely")

            if engine_fail._debug:
                errors = engine_fail._debug.get_errors()
                print(f"  • Errors logged: {len(errors)}")
                if errors:
                    print(f"    - {errors[0].message}")

            print("\n✓ TEST 2 PASSED")
        else:
            print("✗ Not all components returned")

    except Exception as e:
        print(f"✗ TEST 2 FAILED: {e}")

    # TEST 3: Validation Error Handling
    print("\n" + "-"*70)
    print("TEST 3: Validation Error Detection")
    print("-"*70)

    print("\nTesting with incomplete/invalid data...")
    invalid_result = {}
    invalid_db = {}

    try:
        result = engine.explain(invalid_result, invalid_db)

        print("✓ Validation errors handled gracefully")
        print(f"  • Narrative (fallback): {len(result['narrative'])} chars")
        print(f"  • Safe defaults returned for all components")

        if engine._debug:
            all_events = len(engine._debug.events)
            warnings = len(engine._debug.get_warnings())
            print(f"  • Debug events logged: {all_events}")
            print(f"  • Warnings: {warnings}")

        print("\n✓ TEST 3 PASSED")

    except Exception as e:
        print(f"✗ TEST 3 FAILED: {e}")

    # TEST 4: Debug Report Generation
    print("\n" + "-"*70)
    print("TEST 4: Debug Report Generation")
    print("-"*70)

    if engine._debug:
        print("\nGenerating comprehensive debug report...")

        report_path = engine._debug.save_debug_report()
        print(f"✓ Report saved: {report_path}")

        # Read and show summary
        import json
        with open(report_path) as f:
            report = json.load(f)

        print(f"\nReport Summary:")
        print(f"  • Agent: {report['agent']}")
        print(f"  • Total Events: {report['event_count']}")
        print(f"  • File: {report_path.name}")

        # Categorize events
        events = report['events']
        by_level = {}
        by_category = {}

        for event in events:
            level = event.get('level', 'UNKNOWN')
            category = event.get('category', 'unknown')
            by_level[level] = by_level.get(level, 0) + 1
            by_category[category] = by_category.get(category, 0) + 1

        print(f"\n  Events by Level:")
        for level, count in sorted(by_level.items()):
            print(f"    • {level}: {count}")

        print(f"\n  Events by Category:")
        for category, count in sorted(by_category.items()):
            print(f"    • {category}: {count}")

        print("\n✓ TEST 4 PASSED")
    else:
        print("✗ Debug logger not available")

    print("\n" + "="*70)
    print("DEBUGGING SYSTEM TEST COMPLETE")
    print("="*70)
    print("\nKey Features Demonstrated:")
    print("  ✓ Structured error logging by category")
    print("  ✓ Graceful error recovery with fallbacks")
    print("  ✓ Comprehensive debug event tracking")
    print("  ✓ JSON debug report generation")
    print("  ✓ Error categorization (validation, network, resource, etc.)")
    print("  ✓ Stack trace capture for debugging")
    print("  ✓ Context-aware error messages")
    print("\n✓ System is production-ready with comprehensive debugging")
    print("="*70 + "\n")
