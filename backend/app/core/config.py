import os

# API Configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# Database Configuration
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "estate_db")
DB_USER = os.getenv("DB_USER", "estate_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin123")

# Redis Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Elasticsearch Configuration
ELASTICSEARCH_HOSTS = os.getenv("ELASTICSEARCH_HOSTS", "http://elasticsearch:9200")
ELASTICSEARCH_INDEX = os.getenv("ELASTICSEARCH_INDEX", "real_estate_ads")
ELASTICSEARCH_USERNAME = os.getenv("ELASTICSEARCH_USERNAME", "")
ELASTICSEARCH_PASSWORD = os.getenv("ELASTICSEARCH_PASSWORD", "")

# Scrapy Configuration
SCRAPY_API_URL = os.getenv("SCRAPY_API_URL", "http://api:8000/api/ads")

# Timing Settings (жестко заданные)
SCRAPING_CHECK_INTERVAL_SECONDS = int(os.getenv("SCRAPING_CHECK_INTERVAL_SECONDS", "60"))
PROCESSING_CHECK_INTERVAL_SECONDS = int(os.getenv("PROCESSING_CHECK_INTERVAL_SECONDS", "30"))
MAX_WAIT_TIME_MINUTES = int(os.getenv("MAX_WAIT_TIME_MINUTES", "120"))

def get_setting_from_db(key: str, default_value=None, value_type=str):
    """Получить настройку из БД с fallback на .env"""
    try:
        from app.services.settings_service import settings_service
        value = settings_service.get_setting(key, default_value)
        if value is not None:
            return value
    except Exception:
        pass
    
    # Fallback на .env
    env_value = os.getenv(key.upper(), default_value)
    if env_value is not None:
        if value_type == bool:
            return str(env_value).lower() == "true"
        elif value_type == int:
            return int(env_value)
        elif value_type == list:
            return [s.strip() for s in str(env_value).split(',') if s.strip()]
        else:
            return str(env_value)
    
    return default_value

# Динамические настройки из БД
def get_auto_mode():
    return get_setting_from_db('auto_mode', True, bool)

def get_pipeline_interval_minutes():
    return get_setting_from_db('pipeline_interval_minutes', 180, int)

def get_run_immediately_on_start():
    return get_setting_from_db('run_immediately_on_start', False, bool)

def get_scraping_sources():
    return get_setting_from_db('scraping_sources', ['lalafo', 'stroka'], list)

def get_enable_scraping():
    return get_setting_from_db('enable_scraping', True, bool)

def get_enable_photo_processing():
    return get_setting_from_db('enable_photo_processing', True, bool)

def get_enable_duplicate_processing():
    return get_setting_from_db('enable_duplicate_processing', True, bool)

def get_enable_realtor_detection():
    return get_setting_from_db('enable_realtor_detection', True, bool)

def get_enable_elasticsearch_reindex():
    return get_setting_from_db('enable_elasticsearch_reindex', True, bool)

def get_enable_link_validation():
    return get_setting_from_db('enable_link_validation', True, bool)

def get_link_validation_batch_size():
    return get_setting_from_db('link_validation_batch_size', 500, int)

# PgAdmin Configuration
PGADMIN_DEFAULT_EMAIL = os.getenv("PGADMIN_DEFAULT_EMAIL", "admin@admin.com")
PGADMIN_DEFAULT_PASSWORD = os.getenv("PGADMIN_DEFAULT_PASSWORD", "admin123")
PGADMIN_PORT = int(os.getenv("PGADMIN_PORT", "5050"))

# Elasticsearch Cluster Settings
ES_CLUSTER_NAME = os.getenv("ES_CLUSTER_NAME", "real-estate-cluster")
ES_NODE_NAME = os.getenv("ES_NODE_NAME", "real-estate-node")
ES_JAVA_OPTS = os.getenv("ES_JAVA_OPTS", "-Xms512m -Xmx512m")

# Docker Ports (for external access)
REDIS_EXTERNAL_PORT = int(os.getenv("REDIS_EXTERNAL_PORT", "6379"))
ELASTICSEARCH_EXTERNAL_PORT = int(os.getenv("ELASTICSEARCH_EXTERNAL_PORT", "9200"))
ELASTICSEARCH_TRANSPORT_PORT = int(os.getenv("ELASTICSEARCH_TRANSPORT_PORT", "9300"))

# Proxy Configuration (optional)
USE_PROXY = os.getenv("USE_PROXY", "false").lower() == "true"
PROXY_URL = os.getenv("PROXY_URL", "")

# Default Admin Configuration
DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "Adminn")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin2025")
DEFAULT_ADMIN_FULL_NAME = os.getenv("DEFAULT_ADMIN_FULL_NAME", "Administrator")
CREATE_DEFAULT_ADMIN = os.getenv("CREATE_DEFAULT_ADMIN", "true").lower() == "true" 