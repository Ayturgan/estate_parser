#!/bin/bash

# Скрипт для быстрого тестирования изменений
# Запускает только необходимые компоненты локально

echo "⚡ Быстрое тестирование изменений..."

# Устанавливаем переменные окружения
export PYTHONPATH=/home/aetheriw/Downloads/estate_parser/backend:/home/aetheriw/Downloads/estate_parser/scraper
export REDIS_HOST=localhost
export REDIS_PORT=6379
export SCRAPY_API_URL=http://localhost:8000/api/ads

# Функция для тестирования backend
test_backend() {
    echo "🧪 Тестируем backend..."
    cd backend
    
    # Проверяем импорты
    echo "🔍 Проверяем импорты backend..."
    python3 -c "
try:
    from app.main import app
    from app.services.ai_data_extractor import AIDataExtractor
    print('✅ Backend импорты работают')
except Exception as e:
    print(f'❌ Ошибка импорта backend: {e}')
"
    
    cd ..
}

# Функция для тестирования scraper
test_scraper() {
    echo "🧪 Тестируем scraper..."
    cd scraper/estate_scraper
    
    # Проверяем импорты
    echo "🔍 Проверяем импорты scraper..."
    python3 -c "
import sys
sys.path.append('/home/aetheriw/Downloads/estate_parser/backend')
try:
    from app.services.ai_data_extractor import AIDataExtractor
    from real_estate_scraper.spiders.generic_spider import GenericSpider
    from real_estate_scraper.pipelines import DatabasePipeline
    print('✅ Scraper импорты работают')
    print('✅ AI модуль доступен')
except Exception as e:
    print(f'❌ Ошибка импорта scraper: {e}')
"
    
    cd ../..
}

# Функция для тестирования AI модуля
test_ai_module() {
    echo "🤖 Тестируем AI модуль..."
    cd backend
    
    python3 -c "
from app.services.ai_data_extractor import AIDataExtractor
import asyncio

async def test_ai():
    try:
        extractor = AIDataExtractor()
        print('✅ AI Data Extractor создан')
        
        # Тестируем извлечение данных
        result = extractor.extract_and_classify(
            title='Продается 2-комнатная квартира в центре',
            description='Красивая квартира с ремонтом, мебелью, 50м²',
            existing_data={}
        )
        print(f'✅ AI обработка работает: {result}')
        
    except Exception as e:
        print(f'❌ Ошибка AI модуля: {e}')

asyncio.run(test_ai())
"
    
    cd ..
}

# Основная логика
case "${1:-all}" in
    "backend")
        test_backend
        ;;
    "scraper")
        test_scraper
        ;;
    "ai")
        test_ai_module
        ;;
    "all"|*)
        test_backend
        echo ""
        test_scraper
        echo ""
        test_ai_module
        echo ""
        echo "🎉 Все тесты завершены!"
        ;;
esac 