#!/usr/bin/env python3
"""
Быстрый запуск тестового парсинга для создания логов
"""

import requests
import json
import time
from datetime import datetime

def start_test_scraping():
    """Запуск тестового парсинга для создания логов"""
    api_url = "http://localhost:8000"
    
    print("🚀 Запуск тестового парсинга...")
    print("📊 Это создаст логи в папке logs/scraping/")
    print("-" * 50)
    
    # Конфигурация для тестирования
    test_configs = [
        "house",       # Дома на house.kg
        "lalafo",      # Lalafo.kg
        "stroka"       # Stroka.kg
    ]
    
    try:
        for config in test_configs:
            print(f"📋 Запуск парсинга: {config}")
            
            response = requests.post(
                f"{api_url}/api/scraping/start/{config}",
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()

                job_id = result.get('job_id')
                if job_id:
                    print(f"✅ Парсинг запущен")
                    print(f"   🆔 Job ID: {job_id}")
                else:
                    print(f"✅ Парсинг запущен: {result.get('message', 'OK')}")
                    
            else:
                print(f"❌ Ошибка запуска {config}: {response.status_code}")
                print(f"   💥 {response.text}")
            
            # Небольшая пауза между запусками
            time.sleep(2)
    
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("💡 Убедитесь что API контейнер запущен: docker ps | grep api")
    
    print("\n📡 Теперь можете запустить мониторинг логов:")
    print("   python monitor_logs.py")
    print("   python monitor_logs.py --errors-only  # только ошибки")

if __name__ == "__main__":
    start_test_scraping() 