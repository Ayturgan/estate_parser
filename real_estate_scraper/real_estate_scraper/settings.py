# real_estate_scraper/real_estate_scraper/settings.py
import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root)) 

BOT_NAME = "real_estate_scraper"

SPIDER_MODULES = ["real_estate_scraper.spiders"]
NEWSPIDER_MODULE = "real_estate_scraper.spiders"

# Настройки User-Agent
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# Соблюдаем robots.txt
ROBOTSTXT_OBEY = True

# Настройки задержек между запросами
DOWNLOAD_DELAY = 3
RANDOMIZE_DOWNLOAD_DELAY = True




ADDONS = {}

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

DOWNLOADER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 110,
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    'scrapy.downloadermiddlewares.retry.RetryMiddleware': 90,
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_BROWSER_TYPE = "chromium"



FEED_EXPORT_ENCODING = "utf-8"

# Настройки для базы данных
DATABASE_URL = "postgresql://real_estate_user:admin123@localhost:5432/real_estate_db"

# Настройки для pipeline
ITEM_PIPELINES = {
    'real_estate_scraper.pipelines.DatabasePipeline': 300,
}






