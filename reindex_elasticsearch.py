#!/usr/bin/env python3
"""
Скрипт для переиндексации всех объявлений в Elasticsearch
Использование: python reindex_elasticsearch.py
"""

import sys
import os
import logging
from datetime import datetime
from sqlalchemy.orm import Session

# Добавляем корневую папку в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app import db_models
from app.utils.transform import transform_unique_ad, to_elasticsearch_dict
from app.services.elasticsearch_service import ElasticsearchService
from config import ELASTICSEARCH_HOSTS, ELASTICSEARCH_INDEX

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('reindex_elasticsearch.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Основная функция переиндексации"""
    logger.info("🚀 Starting Elasticsearch reindexing...")
    
    # Инициализация сервиса
    es_service = ElasticsearchService(
        hosts=ELASTICSEARCH_HOSTS,
        index_name=ELASTICSEARCH_INDEX
    )
    
    # Проверка здоровья Elasticsearch
    logger.info("🔍 Checking Elasticsearch health...")
    health = es_service.health_check()
    if health.get('status') == 'error':
        logger.error(f"❌ Elasticsearch is not available: {health.get('error')}")
        return False
    
    logger.info(f"✅ Elasticsearch is healthy: {health}")
    
    # Получение данных из базы
    logger.info("📊 Fetching data from database...")
    db = SessionLocal()
    
    try:
        # Получаем все уникальные объявления с их дубликатами
        unique_ads = db.query(db_models.DBUniqueAd).all()
        
        logger.info(f"📈 Found {len(unique_ads)} unique ads to reindex")
        
        if not unique_ads:
            logger.warning("⚠️ No ads found in database")
            return True
        
        # Преобразуем в формат для Elasticsearch
        ads_data = []
        for unique_ad in unique_ads:
            try:
                ad_dict = to_elasticsearch_dict(transform_unique_ad(unique_ad))
                ads_data.append(ad_dict)
            except Exception as e:
                logger.error(f"Error transforming ad {unique_ad.id}: {e}")
                continue
        
        logger.info(f"🔄 Transformed {len(ads_data)} ads for indexing")
        
        # Переиндексация
        logger.info("🔄 Starting reindexing...")
        start_time = datetime.now()
        
        success = es_service.reindex_all(ads_data)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        if success:
            logger.info(f"✅ Reindexing completed successfully in {duration:.2f} seconds!")
            
            # Получаем статистику
            stats = es_service.get_stats()
            logger.info(f"📊 Index stats: {stats}")
            
        else:
            logger.error("❌ Some errors occurred during reindexing")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error during reindexing: {e}")
        return False
        
    finally:
        db.close()
    
    logger.info("🎉 Reindexing process completed!")
    return True

def test_search():
    """Тестирование поиска после переиндексации"""
    logger.info("🧪 Testing search functionality...")
    
    es_service = ElasticsearchService(
        hosts=ELASTICSEARCH_HOSTS,
        index_name=ELASTICSEARCH_INDEX
    )
    
    try:
        # Тест 1: Поиск всех объявлений
        result = es_service.search_ads(size=5)
        logger.info(f"✅ Search test 1 - Found {result.get('total', 0)} total ads")
        
        # Тест 2: Поиск с фильтрами
        result = es_service.search_ads(
            query="квартира",
            filters={'is_realtor': False},
            size=3
        )
        logger.info(f"✅ Search test 2 - Found {len(result.get('hits', []))} ads with filters")
        
        # Тест 3: Агрегации
        aggregations = es_service.get_aggregations()
        logger.info(f"✅ Aggregations test - Got {len(aggregations)} aggregation types")
        
        # Тест 4: Автодополнение
        suggestions = es_service.suggest_addresses("Бишкек", 3)
        logger.info(f"✅ Suggestions test - Got {len(suggestions)} suggestions")
        
        logger.info("🎉 All search tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Search test failed: {e}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Elasticsearch reindexing script')
    parser.add_argument('--test-only', action='store_true', 
                       help='Only test search functionality without reindexing')
    parser.add_argument('--reindex-only', action='store_true',
                       help='Only reindex without testing')
    
    args = parser.parse_args()
    
    if args.test_only:
        success = test_search()
    elif args.reindex_only:
        success = main()
    else:
        # Полный процесс: переиндексация + тестирование
        success = main()
        if success:
            success = test_search()
    
    sys.exit(0 if success else 1) 