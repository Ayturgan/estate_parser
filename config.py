# config.py
import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Настройки базы данных
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "real_estate_db")
DB_USER = os.getenv("DB_USER", "real_estate_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin123")


REDIS_URL = os.getenv("REDIS_URL")

# Настройки парсинга
TARGET_SITE_URL = os.getenv("TARGET_SITE_URL")
PARSING_INTERVAL = 3600  # интервал между запросами в секундах

# Настройки прокси
USE_PROXY = os.getenv("USE_PROXY", "False").lower() == "true"
PROXY_URL = os.getenv("PROXY_URL", "")

# Настройки API
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# Настройки определения дубликатов
IMAGE_HASH_THRESHOLD = int(os.getenv("IMAGE_HASH_THRESHOLD", "5"))
TEXT_SIMILARITY_THRESHOLD = float(os.getenv("TEXT_SIMILARITY_THRESHOLD", "0.8"))

# Строка подключения к базе данных для SQLAlchemy
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
