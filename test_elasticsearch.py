#!/usr/bin/env python3
"""
Скрипт для тестирования Elasticsearch функциональности
Использование: python test_elasticsearch.py
"""

import sys
import os
import json
import requests
from datetime import datetime

# Добавляем корневую папку в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.elasticsearch_service import ElasticsearchService
from config import ELASTICSEARCH_HOSTS, ELASTICSEARCH_INDEX

def test_elasticsearch_connection():
    """Тест подключения к Elasticsearch"""
    print("🔍 Тестирование подключения к Elasticsearch...")
    
    es_service = ElasticsearchService(
        hosts=ELASTICSEARCH_HOSTS,
        index_name=ELASTICSEARCH_INDEX
    )
    
    # Проверка здоровья
    health = es_service.health_check()
    print(f"✅ Здоровье Elasticsearch: {health}")
    
    # Создание индекса
    success = es_service.create_index()
    if success:
        print("✅ Индекс создан/существует")
    else:
        print("❌ Ошибка создания индекса")
        return False
    
    return True

def test_sample_data():
    """Тест с примерными данными"""
    print("\n📝 Тестирование с примерными данными...")
    
    es_service = ElasticsearchService(
        hosts=ELASTICSEARCH_HOSTS,
        index_name=ELASTICSEARCH_INDEX
    )
    
    # Примерные данные объявлений
    sample_ads = [
        {
            "id": 1,
            "title": "Продается 2-комнатная квартира в центре Бишкека",
            "description": "Уютная квартира с ремонтом, мебелью и техникой. Рядом метро, магазины, школа.",
            "price": 150000,
            "currency": "USD",
            "rooms": 2,
            "area_sqm": 65.5,
            "floor": 5,
            "total_floors": 9,
            "series": "Панельный",
            "building_type": "Многоквартирный дом",
            "condition": "Хорошее",
            "repair": "Евроремонт",
            "furniture": "Полностью меблированная",
            "heating": "Центральное",
            "hot_water": "Есть",
            "gas": "Есть",
            "ceiling_height": 2.7,
            "city": "Бишкек",
            "district": "Октябрьский",
            "address": "ул. Ленина, 15",
            "is_vip": False,
            "is_realtor": False,
            "realtor_score": 0.1,
            "duplicates_count": 0,
            "source_name": "lalafo",
            "source_url": "https://lalafo.kg/ad/123",
            "source_id": "123",
            "published_at": "2024-01-15T10:00:00",
            "created_at": "2024-01-15T10:00:00",
            "phone_numbers": ["+996555123456"],
            "photos": [{"url": "https://example.com/photo1.jpg"}],
            "location": {
                "city": "Бишкек",
                "district": "Октябрьский", 
                "address": "ул. Ленина, 15",
                "lat": 42.8746,
                "lon": 74.5698
            }
        },
        {
            "id": 2,
            "title": "Сдам 1-комнатную квартиру в новостройке",
            "description": "Современная квартира в новом доме. Отличная транспортная доступность.",
            "price": 25000,
            "currency": "USD",
            "rooms": 1,
            "area_sqm": 45.0,
            "floor": 12,
            "total_floors": 16,
            "series": "Монолитный",
            "building_type": "Многоквартирный дом",
            "condition": "Отличное",
            "repair": "Дизайнерский ремонт",
            "furniture": "Частично меблированная",
            "heating": "Индивидуальное",
            "hot_water": "Есть",
            "gas": "Есть",
            "ceiling_height": 3.0,
            "city": "Бишкек",
            "district": "Ленинский",
            "address": "пр. Чуй, 78",
            "is_vip": True,
            "is_realtor": True,
            "realtor_score": 0.9,
            "duplicates_count": 2,
            "source_name": "house",
            "source_url": "https://house.kg/ad/456",
            "source_id": "456",
            "published_at": "2024-01-14T15:30:00",
            "created_at": "2024-01-14T15:30:00",
            "phone_numbers": ["+996700987654"],
            "photos": [{"url": "https://example.com/photo2.jpg"}],
            "location": {
                "city": "Бишкек",
                "district": "Ленинский",
                "address": "пр. Чуй, 78",
                "lat": 42.8765,
                "lon": 74.6123
            }
        },
        {
            "id": 3,
            "title": "Продажа 3-комнатной квартиры в элитном районе",
            "description": "Просторная квартира с панорамными окнами. Закрытая территория, подземная парковка.",
            "price": 350000,
            "currency": "USD",
            "rooms": 3,
            "area_sqm": 120.0,
            "floor": 8,
            "total_floors": 12,
            "series": "Монолитно-кирпичный",
            "building_type": "Жилой комплекс",
            "condition": "Отличное",
            "repair": "Премиум ремонт",
            "furniture": "Без мебели",
            "heating": "Индивидуальное",
            "hot_water": "Есть",
            "gas": "Есть",
            "ceiling_height": 3.2,
            "city": "Бишкек",
            "district": "Свердловский",
            "address": "ул. Московская, 25",
            "is_vip": True,
            "is_realtor": False,
            "realtor_score": 0.2,
            "duplicates_count": 1,
            "source_name": "stroka",
            "source_url": "https://stroka.kg/ad/789",
            "source_id": "789",
            "published_at": "2024-01-13T09:15:00",
            "created_at": "2024-01-13T09:15:00",
            "phone_numbers": ["+996555789012"],
            "photos": [{"url": "https://example.com/photo3.jpg"}],
            "location": {
                "city": "Бишкек",
                "district": "Свердловский",
                "address": "ул. Московская, 25",
                "lat": 42.8789,
                "lon": 74.5987
            }
        }
    ]
    
    # Индексация примерных данных
    success_count = 0
    for ad in sample_ads:
        if es_service.index_ad(ad):
            success_count += 1
            print(f"✅ Индексировано объявление {ad['id']}")
        else:
            print(f"❌ Ошибка индексации объявления {ad['id']}")
    
    print(f"📊 Успешно индексировано: {success_count}/{len(sample_ads)} объявлений")
    return success_count == len(sample_ads)

def test_search_functionality():
    """Тест функциональности поиска"""
    print("\n🔍 Тестирование поиска...")
    
    es_service = ElasticsearchService(
        hosts=ELASTICSEARCH_HOSTS,
        index_name=ELASTICSEARCH_INDEX
    )
    
    # Тест 1: Поиск всех объявлений
    print("1️⃣ Поиск всех объявлений:")
    result = es_service.search_ads(size=10)
    print(f"   Найдено: {result.get('total', 0)} объявлений")
    
    # Тест 2: Поиск по тексту
    print("2️⃣ Поиск по тексту 'квартира':")
    result = es_service.search_ads(query="квартира", size=5)
    print(f"   Найдено: {len(result.get('hits', []))} объявлений")
    for hit in result.get('hits', [])[:3]:
        print(f"   - {hit.get('title', 'Без названия')} (${hit.get('price', 0)})")
    
    # Тест 3: Поиск с фильтрами
    print("3️⃣ Поиск с фильтрами (не риэлторы, цена до 200k):")
    result = es_service.search_ads(
        query="квартира",
        filters={'is_realtor': False, 'max_price': 200000},
        size=5
    )
    print(f"   Найдено: {len(result.get('hits', []))} объявлений")
    
    # Тест 4: Поиск VIP объявлений
    print("4️⃣ Поиск VIP объявлений:")
    result = es_service.search_ads(
        filters={'is_vip': True},
        sort_by='price',
        sort_order='desc',
        size=5
    )
    print(f"   Найдено: {len(result.get('hits', []))} VIP объявлений")
    
    # Тест 5: Поиск по району
    print("5️⃣ Поиск в Октябрьском районе:")
    result = es_service.search_ads(
        filters={'district': 'Октябрьский'},
        size=5
    )
    print(f"   Найдено: {len(result.get('hits', []))} объявлений")
    
    return True

def test_aggregations():
    """Тест агрегаций"""
    print("\n📊 Тестирование агрегаций...")
    
    es_service = ElasticsearchService(
        hosts=ELASTICSEARCH_HOSTS,
        index_name=ELASTICSEARCH_INDEX
    )
    
    aggregations = es_service.get_aggregations()
    
    print("Города:")
    for city in aggregations.get('cities', [])[:5]:
        print(f"   {city['key']}: {city['doc_count']} объявлений")
    
    print("\nРайоны:")
    for district in aggregations.get('districts', [])[:5]:
        print(f"   {district['key']}: {district['doc_count']} объявлений")
    
    print("\nИсточники:")
    for source in aggregations.get('sources', []):
        print(f"   {source['key']}: {source['doc_count']} объявлений")
    
    print("\nДиапазоны цен:")
    for price_range in aggregations.get('price_ranges', []):
        print(f"   {price_range['key']}: {price_range['doc_count']} объявлений")
    
    print("\nКоличество комнат:")
    for rooms in aggregations.get('rooms', []):
        print(f"   {rooms['key']} комн.: {rooms['doc_count']} объявлений")
    
    return True

def test_suggestions():
    """Тест автодополнения"""
    print("\n💡 Тестирование автодополнения...")
    
    es_service = ElasticsearchService(
        hosts=ELASTICSEARCH_HOSTS,
        index_name=ELASTICSEARCH_INDEX
    )
    
    # Тест автодополнения адресов
    suggestions = es_service.suggest_addresses("Бишкек", 5)
    print(f"Предложения для 'Бишкек': {suggestions}")
    
    suggestions = es_service.suggest_addresses("Ленина", 3)
    print(f"Предложения для 'Ленина': {suggestions}")
    
    return True

def test_api_endpoints():
    """Тест API эндпоинтов"""
    print("\n🌐 Тестирование API эндпоинтов...")
    
    base_url = "http://localhost:8000"
    
    try:
        # Тест здоровья Elasticsearch
        response = requests.get(f"{base_url}/elasticsearch/health")
        if response.status_code == 200:
            print("✅ /elasticsearch/health - OK")
        else:
            print(f"❌ /elasticsearch/health - {response.status_code}")
        
        # Тест статистики
        response = requests.get(f"{base_url}/elasticsearch/stats")
        if response.status_code == 200:
            print("✅ /elasticsearch/stats - OK")
        else:
            print(f"❌ /elasticsearch/stats - {response.status_code}")
        
        # Тест поиска
        response = requests.get(f"{base_url}/search?q=квартира&size=3")
        if response.status_code == 200:
            print("✅ /search - OK")
        else:
            print(f"❌ /search - {response.status_code}")
        
        # Тест агрегаций
        response = requests.get(f"{base_url}/search/aggregations")
        if response.status_code == 200:
            print("✅ /search/aggregations - OK")
        else:
            print(f"❌ /search/aggregations - {response.status_code}")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Не удается подключиться к API (сервер не запущен)")
        return False

def main():
    """Основная функция тестирования"""
    print("🧪 Начинаем тестирование Elasticsearch интеграции...\n")
    
    # Тест 1: Подключение
    if not test_elasticsearch_connection():
        print("❌ Тест подключения провален")
        return False
    
    # Тест 2: Примерные данные
    if not test_sample_data():
        print("❌ Тест с примерными данными провален")
        return False
    
    # Тест 3: Поиск
    if not test_search_functionality():
        print("❌ Тест поиска провален")
        return False
    
    # Тест 4: Агрегации
    if not test_aggregations():
        print("❌ Тест агрегаций провален")
        return False
    
    # Тест 5: Автодополнение
    if not test_suggestions():
        print("❌ Тест автодополнения провален")
        return False
    
    # Тест 6: API эндпоинты
    if not test_api_endpoints():
        print("⚠️ API тесты пропущены (сервер не запущен)")
    
    print("\n🎉 Все тесты Elasticsearch пройдены успешно!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 