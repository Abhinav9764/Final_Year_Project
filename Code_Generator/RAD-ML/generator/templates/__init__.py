# generator/templates — Base offline fallback templates
from .base_flask import FLASK_APP_CHATBOT, FLASK_APP_ML
from .base_streamlit import STREAMLIT_APP_CHATBOT, STREAMLIT_APP_ML
from .base_html  import HTML_CHATBOT, HTML_ML
from .base_css   import BASE_CSS

__all__ = [
    "FLASK_APP_CHATBOT", "FLASK_APP_ML",
    "STREAMLIT_APP_CHATBOT", "STREAMLIT_APP_ML",
    "HTML_CHATBOT", "HTML_ML",
    "BASE_CSS",
]
