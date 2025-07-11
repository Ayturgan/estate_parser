#!/usr/bin/env python3
"""
Тестовый скрипт для проверки извлечения телефонов
"""

import re

def clean_phone_number(phone):
    """Очищает номер телефона от лишних символов"""
    try:
        # Убираем префикс tel: если есть
        if phone.startswith('tel:'):
            phone = phone[4:]
        
        # Убираем все символы кроме цифр, + и пробелов
        cleaned = re.sub(r'[^\d+\s\-\(\)]', '', phone)
        
        # Убираем лишние пробелы
        cleaned = ' '.join(cleaned.split())
        
        return cleaned if cleaned else None
    except Exception as e:
        print(f"Error cleaning phone number '{phone}': {e}")
        return phone

# Тестовые данные
test_phones = [
    "tel:+996556201701",
    "+996556201701",
    "0770 986400, 0700 986400, 0555 188 664",
    "0312986400",
    "+996 (555) 123-456",
    "0555 123 456"
]

print("Тестирование очистки номеров телефонов:")
print("=" * 50)

for phone in test_phones:
    cleaned = clean_phone_number(phone)
    print(f"Исходный: '{phone}'")
    print(f"Очищенный: '{cleaned}'")
    print("-" * 30) 