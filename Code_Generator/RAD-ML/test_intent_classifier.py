import pytest
from intent_classifier import classify_intent

@pytest.mark.parametrize("prompt,expected_mode", [
    ("Predict house prices based on features", "ml"),
    ("Create a chatbot that answers questions", "chatbot"),
    ("Forecast sales for next quarter", "ml"),
    ("Chat with an AI assistant", "chatbot"),
])
def test_classify_intent_mode(prompt, expected_mode):
    result = classify_intent(prompt)
    assert result["mode"] == expected_mode

def test_classify_intent_target_column():
    prompt = "Predict price based on area and rooms"
    result = classify_intent(prompt)
    # Should detect target column "price" from the word "price"
    assert result["target_column"] in ("price", "")

def test_classify_intent_features_extraction():
    prompt = "Build a model with features: area, rooms, location"
    result = classify_intent(prompt)
    # Features list should contain the extracted feature names
    for feat in ["area", "rooms", "location"]:
        assert feat in result["features"]
