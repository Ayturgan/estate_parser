import sys
import os
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root)) 

BOT_NAME = "real_estate_scraper"

SPIDER_MODULES = ["real_estate_scraper.spiders"]
NEWSPIDER_MODULE = "real_estate_scraper.spiders"

# Настройки User-Agent
USER_AGENT = None

# Соблюдаем robots.txt
ROBOTSTXT_OBEY = True

# Настройки задержек между запросами
DOWNLOAD_DELAY = 3
RANDOMIZE_DOWNLOAD_DELAY = True

# Настройки повторных попыток
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429]

# Настройки прокси (закомментировано)
# PROXY_POOL = [
#     'http://proxy1.example.com:8080',
#     'http://proxy2.example.com:8080',
#     'http://proxy3.example.com:8080',
# ]

ADDONS = {}

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

DOWNLOADER_MIDDLEWARES = {
    # 'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 110,
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': 90,
    'real_estate_scraper.middlewares.RandomUserAgentMiddleware': 400,
    # 'real_estate_scraper.middlewares.ProxyMiddleware': 350,
    'real_estate_scraper.middlewares.RetryMiddleware': 550,
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_BROWSER_TYPE = "chromium"

# Настройки логирования
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
LOG_DATEFORMAT = '%Y-%m-%d %H:%M:%S'

FEED_EXPORT_ENCODING = "utf-8"

# Настройки для базы данных
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "estate_db")
DB_USER = os.getenv("DB_USER", "estate_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin123")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

ITEM_PIPELINES = {
    'real_estate_scraper.pipelines.DataCleaningPipeline': 200,  # Сначала очищаем цену
    'real_estate_scraper.pipelines.DatabasePipeline': 300,       # Потом отправляем в API
}






