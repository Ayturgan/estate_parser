#!/usr/bin/env python3
"""
Тестовый скрипт для проверки исправлений:
1. Обработка ошибок GLiNER
2. Поэтапность пайплайна
3. Уменьшение спама событий
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime

# Конфигурация
API_BASE_URL = "http://localhost:8000"
TEST_TIMEOUT = 300  # 5 минут

async def test_api_endpoint(session, endpoint, method="GET", data=None):
    """Тестирует API endpoint"""
    url = f"{API_BASE_URL}{endpoint}"
    try:
        if method == "GET":
            async with session.get(url) as response:
                return await response.json(), response.status
        elif method == "POST":
            async with session.post(url, json=data) as response:
                return await response.json(), response.status
    except Exception as e:
        return {"error": str(e)}, 500

async def check_photo_processing_status(session):
    """Проверяет статус обработки фото"""
    print("🔍 Проверяем статус обработки фото...")
    result, status = await test_api_endpoint(session, "/api/process/photos/status")
    
    if status == 200:
        print(f"✅ Статус обработки фото: {result.get('status', 'unknown')}")
        print(f"   Сообщение: {result.get('message', 'N/A')}")
        if 'stats' in result:
            stats = result['stats']
            print(f"   Обработано: {stats.get('processed_photos', 0)}/{stats.get('total_photos', 0)}")
        return result.get('status') == 'completed'
    else:
        print(f"❌ Ошибка получения статуса фото: {result}")
        return False

async def check_duplicate_processing_status(session):
    """Проверяет статус обработки дубликатов"""
    print("🔍 Проверяем статус обработки дубликатов...")
    result, status = await test_api_endpoint(session, "/api/process/duplicates/status")
    
    if status == 200:
        print(f"✅ Статус обработки дубликатов: {result.get('status', 'unknown')}")
        print(f"   Сообщение: {result.get('message', 'N/A')}")
        return result.get('status') == 'completed'
    else:
        print(f"❌ Ошибка получения статуса дубликатов: {result}")
        return False

async def check_automation_status(session):
    """Проверяет статус автоматизации"""
    print("🔍 Проверяем статус автоматизации...")
    result, status = await test_api_endpoint(session, "/api/automation/status")
    
    if status == 200:
        print(f"✅ Статус автоматизации: {result.get('status', 'unknown')}")
        print(f"   Текущий этап: {result.get('current_stage', 'N/A')}")
        return result
    else:
        print(f"❌ Ошибка получения статуса автоматизации: {result}")
        return None

async def test_photo_processing(session):
    """Тестирует обработку фото"""
    print("\n📸 Тестируем обработку фото...")
    
    # Запускаем обработку фото
    result, status = await test_api_endpoint(session, "/api/process/photos", "POST")
    
    if status == 202:
        print("✅ Обработка фото запущена")
        
        # Ждем завершения
        start_time = time.time()
        while time.time() - start_time < TEST_TIMEOUT:
            if await check_photo_processing_status(session):
                print("✅ Обработка фото завершена успешно")
                return True
            await asyncio.sleep(5)
        
        print("⏰ Превышено время ожидания обработки фото")
        return False
    else:
        print(f"❌ Ошибка запуска обработки фото: {result}")
        return False

async def test_duplicate_processing(session):
    """Тестирует обработку дубликатов"""
    print("\n🔄 Тестируем обработку дубликатов...")
    
    # Запускаем обработку дубликатов
    result, status = await test_api_endpoint(session, "/api/process/duplicates", "POST")
    
    if status == 202:
        print("✅ Обработка дубликатов запущена")
        
        # Ждем завершения
        start_time = time.time()
        while time.time() - start_time < TEST_TIMEOUT:
            if await check_duplicate_processing_status(session):
                print("✅ Обработка дубликатов завершена успешно")
                return True
            await asyncio.sleep(5)
        
        print("⏰ Превышено время ожидания обработки дубликатов")
        return False
    else:
        print(f"❌ Ошибка запуска обработки дубликатов: {result}")
        return False

async def test_automation_pipeline(session):
    """Тестирует полный пайплайн автоматизации"""
    print("\n🚀 Тестируем полный пайплайн автоматизации...")
    
    # Запускаем автоматизацию
    result, status = await test_api_endpoint(session, "/api/automation/start", "POST")
    
    if status == 200:
        print("✅ Автоматизация запущена")
        
        # Мониторим прогресс
        start_time = time.time()
        last_stage = None
        
        while time.time() - start_time < TEST_TIMEOUT:
            automation_status = await check_automation_status(session)
            
            if automation_status:
                current_stage = automation_status.get('current_stage', 'unknown')
                status = automation_status.get('status', 'unknown')
                
                if current_stage != last_stage:
                    print(f"📊 Этап: {current_stage}, Статус: {status}")
                    last_stage = current_stage
                
                if status == 'completed':
                    print("✅ Автоматизация завершена успешно")
                    return True
                elif status == 'error':
                    print("❌ Автоматизация завершилась с ошибкой")
                    return False
            
            await asyncio.sleep(10)
        
        print("⏰ Превышено время ожидания автоматизации")
        return False
    else:
        print(f"❌ Ошибка запуска автоматизации: {result}")
        return False

async def check_logs_for_errors():
    """Проверяет логи на наличие ошибок"""
    print("\n🔍 Проверяем логи на ошибки...")
    
    try:
        with open('logs/api_container_logs.txt', 'r', encoding='utf-8') as f:
            logs = f.read()
        
        # Ищем критические ошибки
        error_patterns = [
            "can't multiply sequence by non-int of type 'float'",
            "asyncio.create_task",
            "Event emitted: duplicate_processing_progress",
            "Error processing ad"
        ]
        
        found_errors = []
        for pattern in error_patterns:
            if pattern in logs:
                count = logs.count(pattern)
                found_errors.append(f"{pattern}: {count} раз")
        
        if found_errors:
            print("⚠️ Найдены потенциальные проблемы:")
            for error in found_errors:
                print(f"   - {error}")
        else:
            print("✅ Критических ошибок не найдено")
            
    except FileNotFoundError:
        print("⚠️ Файл логов не найден")

async def main():
    """Основная функция тестирования"""
    print("🧪 Запуск тестирования исправлений...")
    print(f"📅 Время начала: {datetime.now()}")
    
    async with aiohttp.ClientSession() as session:
        # Проверяем доступность API
        result, status = await test_api_endpoint(session, "/api/status")
        if status != 200:
            print(f"❌ API недоступен: {result}")
            return
        
        print("✅ API доступен")
        
        # Тестируем обработку фото
        photo_success = await test_photo_processing(session)
        
        # Тестируем обработку дубликатов
        duplicate_success = await test_duplicate_processing(session)
        
        # Тестируем полный пайплайн
        automation_success = await test_automation_pipeline(session)
        
        # Проверяем логи
        await check_logs_for_errors()
        
        # Итоговый отчет
        print("\n" + "="*50)
        print("📊 ИТОГОВЫЙ ОТЧЕТ")
        print("="*50)
        print(f"Обработка фото: {'✅' if photo_success else '❌'}")
        print(f"Обработка дубликатов: {'✅' if duplicate_success else '❌'}")
        print(f"Полный пайплайн: {'✅' if automation_success else '❌'}")
        print(f"📅 Время завершения: {datetime.now()}")
        
        if photo_success and duplicate_success and automation_success:
            print("\n🎉 Все тесты прошли успешно!")
        else:
            print("\n⚠️ Некоторые тесты не прошли")

if __name__ == "__main__":
    asyncio.run(main()) 