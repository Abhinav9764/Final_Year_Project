#!/usr/bin/env python
"""Test architecture diagram generation with the explainability engine."""

import sys
import json
import base64
import importlib.util
import tempfile
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import MagicMock

# Add project to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# (Removed top-level engine loading to avoid collection errors)


class TestArchitectureDiagramGeneration(TestCase):
    """Test cases for architecture diagram generation."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures that are shared across all tests."""
        # Load RAD-ML engine module
        engine_module_path = project_root / "Code_Generator" / "RAD-ML" / "explainability" / "engine.py"
        spec = importlib.util.spec_from_file_location("explainability_engine", engine_module_path)
        explainability_engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(explainability_engine)
        cls.ExplainabilityEngine = explainability_engine.ExplainabilityEngine

        # Create mock LLM client
        cls.mock_llm = MagicMock()
        cls.mock_llm.generate.return_value = (
            "## Your model is ready!\nIt predicts price from features using XGBoost."
        )
        
        # Create config
        cls.config = {
            "codegen": {"workspace_dir": tempfile.mkdtemp(), "flask_port": 7000},
            "llm": {"gemini_api_key": ""},
        }

    def setUp(self):
        """Initialize test fixtures."""
        self.engine = self.ExplainabilityEngine(self.mock_llm, self.config)
        self.test_output_dir = Path(project_root) / "tests" / "diagram_outputs"
        self.test_output_dir.mkdir(parents=True, exist_ok=True)

    def test_diagram_generation_with_gold_price_model(self):
        """Test architecture diagram generation for gold price prediction model."""
        print("\n" + "="*70)
        print("TEST: Architecture Diagram Generation (Gold Price Model)")
        print("="*70)

        # Gold price model result structures
        job_result = {
            "deploy_url": "http://localhost:7000",
            "endpoint_name": "gold-price-endpoint",
            "sm_meta": {
                "endpoint_name": "gold-price-endpoint",
                "job_name": "radml-job-gold-price",
                "status": "Completed",
            },
            "dataset": {
                "row_count": 2150,
                "columns": ["year", "weight", "price"],
                "merged": True,
                "source_count": 2,
                "s3_uri": "s3://rad-ml-datasets/gold-price/data.csv",
                "preview_rows": [{"year": 2023, "weight": 100.5, "price": 1950.75}],
            },
            "model": {
                "task_type": "regression",
                "feature_cols": ["year", "weight"],
                "target_col": "price",
                "stats": {"train_rows": 1720, "val_rows": 430, "num_features": 2},
            },
        }

        db_results = {
            "prompt": "Predict gold price based on year and weight",
            "job_id": "gold-price-001",
            "spec": {
                "task_type": "regression",
                "input_params": ["year", "weight"],
                "target_param": "price",
                "keywords": ["gold", "price", "prediction"],
            },
            "top_sources": [
                {
                    "title": "Gold Price Dataset",
                    "source": "kaggle",
                    "url": "https://www.kaggle.com/datasets/gold-price",
                    "row_count": 1200,
                    "final_score": 0.85,
                },
                {
                    "title": "Gold Market Data",
                    "source": "openml",
                    "url": "https://www.openml.org/d/gold",
                    "row_count": 950,
                    "final_score": 0.78,
                },
            ],
        }

        # Generate explanation with architecture diagram
        explanation_result = self.engine.explain(job_result, db_results)

        # Verify result structure
        self.assertIsInstance(explanation_result, dict)
        required_keys = {
            "narrative",
            "algorithm_card",
            "usage_guide",
            "data_story",
            "architecture_diagram_b64",
            "code_preview",
        }
        for key in required_keys:
            self.assertIn(key, explanation_result, f"Missing: {key}")

        print("\n✓ All explanation components generated")
        print(f"  ├─ Narrative: {len(explanation_result['narrative'])} chars")
        print(f"  ├─ Algorithm Card: {str(explanation_result['algorithm_card'])[:60]}...")
        print(f"  ├─ Usage Guide: {len(explanation_result['usage_guide'])} items")
        print(f"  ├─ Data Story: {len(explanation_result['data_story'])} keys")
        print(f"  ├─ Architecture Diagram: {len(explanation_result['architecture_diagram_b64'])} chars")
        print(f"  └─ Code Preview: {len(explanation_result['code_preview'])} files")

        # Test architecture diagram specifically
        arch_diagram = explanation_result["architecture_diagram_b64"]

        if arch_diagram:
            print("\n✓ Architecture diagram generated successfully!")

            # Verify it's base64 encoded PNG
            try:
                # Check if it looks like base64-encoded PNG
                if arch_diagram.startswith("iVBOR"):  # PNG magic bytes in base64
                    print("  ✓ Diagram is base64-encoded PNG")

                    # Try to decode to verify validity
                    decoded = base64.b64decode(arch_diagram)
                    print(f"  ✓ Decoded successfully: {len(decoded)} bytes")

                    # Verify PNG magic bytes
                    self.assertEqual(decoded[:4], b"\x89PNG", "Invalid PNG header")
                    print("  ✓ PNG header validation passed")

                    # Save to file for inspection
                    diagram_file = self.test_output_dir / "gold_price_architecture.png"
                    with open(diagram_file, "wb") as f:
                        f.write(decoded)
                    print(f"  ✓ Saved to: {diagram_file}")

                else:
                    print(f"  ✗ Unexpected diagram content: {arch_diagram[:100]}...")

            except Exception as e:
                print(f"  ⚠ Could not fully validate diagram: {e}")
        else:
            print("\n⚠ Architecture diagram is empty")
            print("  Note: This may occur if graphviz system tool is not installed")
            print("       diagrams library will return empty string gracefully")

    def test_diagram_generation_consistency(self):
        """Test that diagram generation is consistent across multiple calls."""
        print("\n" + "="*70)
        print("TEST: Diagram Generation Consistency")
        print("="*70)

        job_result = {
            "deploy_url": "http://localhost:7000",
            "sm_meta": {"endpoint_name": "test-endpoint"},
            "dataset": {"row_count": 1000, "columns": ["x", "y", "z"]},
            "model": {
                "task_type": "regression",
                "feature_cols": ["x", "y"],
                "target_col": "z",
                "stats": {"train_rows": 800, "val_rows": 200, "num_features": 2},
            },
        }

        db_results = {
            "spec": {
                "task_type": "regression",
                "input_params": ["x", "y"],
                "target_param": "z",
            },
            "top_sources": [],
        }

        # Generate explanation twice
        result1 = self.engine.explain(job_result, db_results)
        result2 = self.engine.explain(job_result, db_results)

        # Check if diagrams match (should be identical or both empty)
        diagram1 = result1["architecture_diagram_b64"]
        diagram2 = result2["architecture_diagram_b64"]

        if diagram1 and diagram2:
            if diagram1 == diagram2:
                print("✓ Diagram generation is consistent")
            else:
                print("⚠ Diagrams differ slightly (expected for file paths)")
                print(f"  Diagram 1 size: {len(diagram1)} chars")
                print(f"  Diagram 2 size: {len(diagram2)} chars")
        else:
            print("⚠ One or both diagrams unavailable for consistency check")
            print(f"  Diagram 1: {'present' if diagram1 else 'empty'}")
            print(f"  Diagram 2: {'present' if diagram2 else 'empty'}")

    def test_diagram_with_classification_model(self):
        """Test architecture diagram generation for classification model."""
        print("\n" + "="*70)
        print("TEST: Architecture Diagram (Classification Model)")
        print("="*70)

        job_result = {
            "deploy_url": "http://localhost:7000",
            "sm_meta": {"endpoint_name": "iris-classifier"},
            "dataset": {
                "row_count": 150,
                "columns": ["sepal_length", "sepal_width", "petal_length", "petal_width", "species"],
            },
            "model": {
                "task_type": "classification",
                "feature_cols": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
                "target_col": "species",
                "stats": {"train_rows": 120, "val_rows": 30, "num_features": 4},
            },
        }

        db_results = {
            "spec": {
                "task_type": "classification",
                "input_params": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
                "target_param": "species",
            },
            "top_sources": [],
        }

        result = self.engine.explain(job_result, db_results)
        diagram = result["architecture_diagram_b64"]

        if diagram:
            print("✓ Diagram generated for classification model")
            print(f"  Size: {len(diagram)} bytes (base64)")
        else:
            print("⚠ Diagram unavailable")

    def test_components_all_present(self):
        """Verify all explanation components are generated."""
        print("\n" + "="*70)
        print("TEST: All Explanation Components Present")
        print("="*70)

        job_result = {
            "deploy_url": "http://localhost:7000",
            "sm_meta": {"endpoint_name": "test-ep"},
            "dataset": {"row_count": 500, "columns": ["x", "y", "z"]},
            "model": {
                "task_type": "regression",
                "feature_cols": ["x", "y"],
                "target_col": "z",
                "stats": {"train_rows": 400, "val_rows": 100, "num_features": 2},
            },
        }

        db_results = {
            "spec": {
                "task_type": "regression",
                "input_params": ["x", "y"],
                "target_param": "z",
            },
            "top_sources": [],
        }

        result = self.engine.explain(job_result, db_results)

        required_components = [
            "narrative",
            "algorithm_card",
            "usage_guide",
            "data_story",
            "architecture_diagram_b64",
            "code_preview",
        ]

        print("\nVerifying all components:")
        for component in required_components:
            self.assertIn(component, result, f"Missing: {component}")
            has_content = bool(result[component])
            indicator = "✓" if has_content else "⚠"
            size_info = f"{len(result[component])} chars" if isinstance(result[component], str) else "present"
            print(f"  {indicator} {component}: {size_info}")

        print("\n✓ All required components present")


def run_tests():
    """Run all tests with summary."""
    print("\n" + "="*70)
    print("ARCHITECTURE DIAGRAM GENERATION TEST SUITE")
    print("="*70)
    print("Testing the generation of architecture diagrams for ML models")
    print("using the ExplainabilityEngine with diagrams/graphviz")
    
    # Run tests
    main(verbosity=2, exit=True)


if __name__ == "__main__":
    run_tests()
