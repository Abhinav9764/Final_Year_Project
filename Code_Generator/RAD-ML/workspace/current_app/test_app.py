import app as app_module

def test_encode_feature_numeric():
    assert app_module._encode_feature('area', ' 1500.5 ') == '1500.5'
def test_encode_feature_string():
    val = app_module._encode_feature('region', 'north')
    assert val.isdigit()
def test_prediction_dummy(monkeypatch):
    monkeypatch.setattr(app_module, 'sm_runtime', None)
    assert app_module.make_prediction(['100', '200']) == '150.0'
def test_validate_payload_missing():
    ok, msg = app_module.validate_payload({})
    assert ok is False
    assert 'Missing required fields' in msg
