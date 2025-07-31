#!/usr/bin/env python3
"""
Тестовый скрипт для проверки валидации ссылок
"""

import asyncio
import aiohttp
import sys
import os

# Добавляем путь к backend
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

async def test_link_validation():
    """Тест валидации ссылок"""
    print("🧪 Тестирование валидации ссылок...")
    
    try:
        # Импортируем сервис
        from app.services.link_validation_service import link_validation_service
        
        # Проверяем статус
        status = link_validation_service.get_status()
        print(f"📊 Начальный статус: {status['status']}")
        
        # Запускаем валидацию
        print("🚀 Запуск валидации...")
        success = await link_validation_service.start_validation()
        
        if success:
            print("✅ Валидация запущена успешно")
            
            # Ждем немного и проверяем прогресс
            await asyncio.sleep(5)
            
            status = link_validation_service.get_status()
            print(f"📊 Статус через 5 секунд: {status}")
            
            # Ждем завершения
            while status['status'] == 'running':
                await asyncio.sleep(10)
                status = link_validation_service.get_status()
                print(f"📊 Прогресс: {status['progress']}")
            
            print(f"✅ Валидация завершена: {status}")
            
        else:
            print("❌ Ошибка запуска валидации")
            
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_link_validation()) 