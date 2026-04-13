"""
verify_fixes.py — Quick deterministic smoke-tests for all four Streamlit pipeline fixes.
Run from:  Code_Generator/RAD-ML/
"""
import sys  # noqa: E402

sys.path.insert(0, ".")

PASS = "[OK]"
FAIL = "[FAIL]"


def check(cond: bool, desc: str) -> bool:
    tag = PASS if cond else FAIL
    print(f"{tag} {desc}")
    return cond


all_passed = True

# ── Fix 1: base_streamlit.py - safe config loading + AWS EC2 metadata fix ──────
from generator.base_streamlit import STREAMLIT_APP_ML, STREAMLIT_APP_CHATBOT  # noqa: E402

all_passed &= check(
    "if _cfg_path.exists():" in STREAMLIT_APP_ML,
    "ML template: safe config.yaml loading present"
)
all_passed &= check(
    "AWS_EC2_METADATA_DISABLED" in STREAMLIT_APP_ML,
    "ML template: AWS EC2 metadata disabled"
)
all_passed &= check(
    "if _cfg_path.exists():" in STREAMLIT_APP_CHATBOT,
    "Chatbot template: safe config.yaml loading present"
)

# ── Fix 2a: FEATURES placeholder still present for injection ────────────────────
placeholder = 'FEATURES: List[str] = list(CFG.get("ml_features", []))'
all_passed &= check(
    placeholder in STREAMLIT_APP_ML,
    "ML template: FEATURES placeholder present (literal injection target)"
)

# ── Fix 2b: literal FEATURES injection works ────────────────────────────────────
old_placeholder = (
    'FEATURES: List[str] = list(CFG.get("ml_features", [])) or [\n'
    '    "region",\n'
    '    "area",\n'
    '    "bedrooms",\n'
    '    "bathrooms",\n'
    '    "age_of_property",\n'
    ']'
)
features = ["tenure", "monthly_charges", "age"]
feat_lines = ",\n".join(f'    "{f}"' for f in features)
new_decl = f"FEATURES: List[str] = [\n{feat_lines}\n]"

simulated_result = STREAMLIT_APP_ML.replace(old_placeholder, new_decl)
all_passed &= check("tenure" in simulated_result, "Literal replacement injects 'tenure'")
all_passed &= check("monthly_charges" in simulated_result, "Literal replacement injects 'monthly_charges'")
all_passed &= check("age_of_property" not in simulated_result, "Old placeholder removed after replacement")

# ── Fix 2c: _derive_app_name_from_prompt ────────────────────────────────────────
from generator.code_gen_factory import CodeGenFactory  # noqa: E402

cases = [
    ("predict customer churn based on tenure", "Customer Churn Predictor"),
    ("house price prediction model", "House Price Predictor"),
    ("news topic classification model", "News Topic Classifier"),
    ("loan default risk prediction", "Loan Default Predictor"),
    ("fraud detection model using transactions", "Fraud Detection"),
]
for prompt, expected in cases:
    got = CodeGenFactory._derive_app_name_from_prompt(prompt)
    all_passed &= check(got == expected, f"_derive_app_name: '{prompt[:40]}' -> '{got}'")

# ── Fix 2d: _validate_prompt_alignment ─────────────────────────────────────────
aligned_code = 'FEATURES = ["tenure", "monthly_charges", "age"]'
wrong_code = 'FEATURES = ["region", "area", "bedrooms"]'

all_passed &= check(
    CodeGenFactory._validate_prompt_alignment(aligned_code, "churn", ["tenure", "monthly_charges", "age"]),
    "_validate_prompt_alignment: passes when features are present"
)
# When generated code has only wrong placeholder features and none from the dataset list
all_passed &= check(
    not CodeGenFactory._validate_prompt_alignment(wrong_code, "churn", ["tenure", "monthly_charges", "age"]),
    "_validate_prompt_alignment: fails when dataset features absent from code"
)

# ── Fix 2e: end-to-end stub with prompt-context injection ───────────────────────
import json  # noqa: E402

factory = CodeGenFactory({})
factory._current_engine_meta = {
    "features": ["tenure", "monthly_charges", "age"],
    "endpoint": "test-churn-endpoint",
}
raw = factory._stub_bundle_json("ml", "predict customer churn based on tenure")
stub = json.loads(raw)
py = stub["python"]

all_passed &= check("tenure" in py, "Stub: 'tenure' is in the generated app.py")
all_passed &= check("monthly_charges" in py, "Stub: 'monthly_charges' in the generated app.py")
all_passed &= check("Customer Churn Predictor" in py, "Stub: App name injected as 'Customer Churn Predictor'")
all_passed &= check("age_of_property" not in py, "Stub: Default placeholder 'age_of_property' NOT in output")
all_passed &= check("test-churn-endpoint" in py, "Stub: ENDPOINT_NAME correctly injected")

# ── Fix 3: main.py Streamlit timeout ────────────────────────────────────────────
import os  # noqa: E402
main_path = os.path.join(os.path.dirname(__file__), "main.py")
with open(main_path, encoding="utf-8") as f:
    main_src = f.read()
all_passed &= check("per_candidate_timeout = 60" in main_src, "main.py: Streamlit launch timeout is 60s")
all_passed &= check("spawn failed:" in main_src, "main.py: Spawn failure is captured gracefully")

# ── Summary ─────────────────────────────────────────────────────────────────────
print()
if all_passed:
    print("=== ALL VERIFICATION CHECKS PASSED ===")
else:
    print("=== SOME CHECKS FAILED - review above ===")
    sys.exit(1)
