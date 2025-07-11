#!/usr/bin/env python3
"""
Скрипт для быстрого тестирования нового сайта-источника
Использование: python test_new_site.py config_name [spider_type]
"""

import sys
import os
import subprocess
import json
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Использование: python test_new_site.py config_name [spider_type]")
        print("Примеры:")
        print("  python test_new_site.py my_site")
        print("  python test_new_site.py my_api_site api")
        print("  python test_new_site.py my_show_more_site show_more")
        sys.exit(1)
    
    config_name = sys.argv[1]
    spider_type = sys.argv[2] if len(sys.argv) > 2 else "html"
    
    # Определяем тип спайдера
    spider_map = {
        "html": "generic_scraper",
        "api": "generic_api", 
        "show_more": "generic_show_more",
        "show_more_simple": "generic_show_more_simple"
    }
    
    if spider_type not in spider_map:
        print(f"Неизвестный тип спайдера: {spider_type}")
        print(f"Доступные типы: {', '.join(spider_map.keys())}")
        sys.exit(1)
    
    spider_name = spider_map[spider_type]
    
    # Проверяем существование конфига
    config_path = Path(f"scraper/estate_scraper/real_estate_scraper/configs/{config_name}.yml")
    if not config_path.exists():
        print(f"❌ Конфигурация {config_name}.yml не найдена!")
        print(f"Создайте файл: {config_path}")
        sys.exit(1)
    
    print(f"🔍 Тестируем конфигурацию: {config_name}")
    print(f"🕷️  Используем спайдер: {spider_name}")
    print(f"📁 Конфиг: {config_path}")
    print("-" * 50)
    
    # Переходим в директорию scraper
    os.chdir("scraper/estate_scraper")
    
    # Запускаем тестовый парсинг
    cmd = [
        "scrapy", "crawl", spider_name,
        "-a", f"config={config_name}",
        "-s", "LOG_LEVEL=INFO",
        "-s", "CLOSESPIDER_ITEMCOUNT=5",  # Ограничиваем до 5 элементов для теста
        "-o", f"test_output_{config_name}.json"
    ]
    
    print(f"🚀 Запускаем команду: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        print("📊 Результаты:")
        print(f"Код выхода: {result.returncode}")
        
        if result.stdout:
            print("✅ Вывод:")
            print(result.stdout)
        
        if result.stderr:
            print("⚠️  Ошибки:")
            print(result.stderr)
        
        # Проверяем результат
        output_file = f"test_output_{config_name}.json"
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"📈 Спарсено объявлений: {len(data)}")
            
            if data:
                print("📋 Пример первого объявления:")
                first_item = data[0]
                for key, value in first_item.items():
                    if value:
                        print(f"  {key}: {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
        
        if result.returncode == 0:
            print("✅ Тест прошел успешно!")
        else:
            print("❌ Тест завершился с ошибками")
            
    except subprocess.TimeoutExpired:
        print("⏰ Тест превысил лимит времени (5 минут)")
    except Exception as e:
        print(f"💥 Ошибка при запуске: {e}")

if __name__ == "__main__":
    main() 