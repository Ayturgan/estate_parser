#!/usr/bin/env python3

import imagehash
from PIL import Image
import requests
from io import BytesIO

def download_image(url):
    """Скачивает изображение по URL"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        print(f"Ошибка загрузки {url}: {e}")
        return None

def calculate_hashes(image):
    """Вычисляет все типы хешей для изображения"""
    try:
        return {
            'aHash': str(imagehash.average_hash(image)),
            'dHash': str(imagehash.dhash(image)),
            'pHash': str(imagehash.phash(image)),
            'wHash': str(imagehash.whash(image))
        }
    except Exception as e:
        print(f"Ошибка вычисления хешей: {e}")
        return None

def hamming_distance(hash1, hash2):
    """Вычисляет расстояние Хэмминга между двумя хешами"""
    return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))

def calculate_similarity(hash1, hash2):
    """Вычисляет схожесть на основе расстояния Хэмминга"""
    distance = hamming_distance(hash1, hash2)
    max_distance = len(hash1)
    return 1.0 - (distance / max_distance)

# URL фотографий из базы данных
urls = [
    "https://img5.lalafo.com/i/posters/original/ea/7a/46/zemelnyj-ucastok-s-kartofelnym-polem-id-42789990-846728634.jpeg",  # Объявление 106
    "https://data.stroka.kg/image/big/4143377.jpg",  # Дубликат 290
    "https://data.stroka.kg/image/big/4194577.jpg",  # Дубликат 322
    "https://data.stroka.kg/image/big/4176620.jpg",  # Дубликат 357
    "https://data.stroka.kg/image/big/4194619.jpg",  # Дубликат 347
]

print("🔍 Проверка хешей фотографий...")
print("=" * 80)

hashes_list = []
for i, url in enumerate(urls):
    print(f"\n📸 Фото {i+1}: {url}")
    image = download_image(url)
    if image:
        hashes = calculate_hashes(image)
        if hashes:
            hashes_list.append(hashes)
            print(f"   Хеши: {hashes}")
        else:
            print("   ❌ Не удалось вычислить хеши")
    else:
        print("   ❌ Не удалось загрузить изображение")

print("\n" + "=" * 80)
print("🔍 Сравнение хешей...")

if len(hashes_list) >= 2:
    base_hashes = hashes_list[0]  # Хеши первого фото (объявление 106)
    
    for i, compare_hashes in enumerate(hashes_list[1:], 1):
        print(f"\n📊 Сравнение фото 1 vs фото {i+1}:")
        
        best_similarity = 0.0
        for hash_type in ['aHash', 'dHash', 'pHash', 'wHash']:
            if hash_type in base_hashes and hash_type in compare_hashes:
                hash1 = base_hashes[hash_type]
                hash2 = compare_hashes[hash_type]
                
                similarity = calculate_similarity(hash1, hash2)
                distance = hamming_distance(hash1, hash2)
                
                print(f"   {hash_type}: схожесть={similarity:.3f}, расстояние={distance}")
                
                if similarity > best_similarity:
                    best_similarity = similarity
        
        print(f"   🎯 Лучшая схожесть: {best_similarity:.3f}")
        
        if best_similarity >= 0.3:
            print(f"   ✅ Проходит порог 0.3")
        else:
            print(f"   ❌ НЕ проходит порог 0.3") 