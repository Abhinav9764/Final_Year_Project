import unittest
from unittest.mock import MagicMock, patch

def _mock_streamlit_module():
    st = MagicMock()
    st.sidebar.__enter__.return_value = st
    st.sidebar.__exit__.return_value = False
    tab_a = MagicMock()
    tab_b = MagicMock()
    tab_a.__enter__.return_value = st
    tab_a.__exit__.return_value = False
    tab_b.__enter__.return_value = st
    tab_b.__exit__.return_value = False
    st.tabs.return_value = [tab_a, tab_b]
    col_a = MagicMock()
    col_b = MagicMock()
    col_a.__enter__.return_value = st
    col_a.__exit__.return_value = False
    col_b.__enter__.return_value = st
    col_b.__exit__.return_value = False
    st.columns.return_value = [col_a, col_b]
    form_ctx = MagicMock()
    form_ctx.__enter__.return_value = st
    form_ctx.__exit__.return_value = False
    st.form.return_value = form_ctx
    spinner_ctx = MagicMock()
    spinner_ctx.__enter__.return_value = st
    spinner_ctx.__exit__.return_value = False
    st.spinner.return_value = spinner_ctx
    progress_bar = MagicMock()
    progress_bar.progress.return_value = None
    st.progress.return_value = progress_bar
    st.file_uploader.return_value = None
    st.form_submit_button.return_value = False
    st.button.return_value = False
    return st

class TestMLApp(unittest.TestCase):
    def setUp(self):
        import sys
        self._st_patcher = patch.dict(sys.modules, {'streamlit': _mock_streamlit_module()})
        self._st_patcher.start()
        import importlib
        import app as app_module
        importlib.reload(app_module)
        self.app = app_module

    def tearDown(self):
        self._st_patcher.stop()

    def test_encode_feature_numeric(self):
        self.assertEqual(self.app._encode_feature('area', ' 1500.5 '), '1500.5')

    def test_encode_feature_strips_units(self):
        self.assertEqual(self.app._encode_feature('area', '200sq.ft'), '200.0')

    def test_encode_feature_region(self):
        val = self.app._encode_feature('region', 'north')
        self.assertTrue(val.isdigit())

    def test_validate_payload_missing(self):
        ok, msg = self.app.validate_payload({})
        self.assertFalse(ok)
        self.assertIn('Missing required fields', msg)

    def test_make_prediction_local_fallback(self):
        with patch.object(self.app, 'get_sm_runtime', return_value=None):
            result = self.app.make_prediction(['100.0', '200.0'])
            self.assertIsInstance(result, str)

if __name__ == '__main__':
    unittest.main()
