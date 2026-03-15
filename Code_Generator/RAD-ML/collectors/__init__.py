# collectors — Data Acquisition Layer
from .ddg_scraper import DDGScraper
from .kaggle_client import KaggleClient

__all__ = ["DDGScraper", "KaggleClient"]
