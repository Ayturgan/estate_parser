#!/usr/bin/env python3
"""
Тестовый скрипт для пошаговой отладки дедупликации
Проверяет каждое объявление и выясняет почему дедупликация не работает
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.database import SessionLocal
from app.database import db_models
from app.utils.duplicate_processor import DuplicateProcessor
from sqlalchemy import and_
import numpy as np

def debug_deduplication():
    """Пошаговая отладка дедупликации"""
    db = SessionLocal()
    
    try:
        # 1. Проверяем общую статистику
        print("=== ОБЩАЯ СТАТИСТИКА ===")
        total_ads = db.query(db_models.DBAd).count()
        processed_ads = db.query(db_models.DBAd).filter(db_models.DBAd.is_processed == True).count()
        unique_ads = db.query(db_models.DBUniqueAd).count()
        duplicate_ads = db.query(db_models.DBAd).filter(db_models.DBAd.is_duplicate == True).count()
        
        print(f"Всего объявлений: {total_ads}")
        print(f"Обработанных: {processed_ads}")
        print(f"Уникальных: {unique_ads}")
        print(f"Дубликатов: {duplicate_ads}")
        print(f"Пропало: {total_ads - unique_ads - duplicate_ads}")
        
        # 2. Проверяем объявления без unique_ad_id
        print("\n=== ОБЪЯВЛЕНИЯ БЕЗ UNIQUE_AD_ID ===")
        orphan_ads = db.query(db_models.DBAd).filter(
            and_(
                db_models.DBAd.is_processed == True,
                db_models.DBAd.unique_ad_id.is_(None)
            )
        ).limit(5).all()
        
        print(f"Найдено {len(orphan_ads)} объявлений без unique_ad_id (показываем первые 5):")
        for ad in orphan_ads:
            print(f"  ID: {ad.id}, Title: {ad.title[:50]}..., Price: {ad.price}, Area: {ad.area_sqm}")
        
        # 3. Проверяем несколько объявлений пошагово
        print("\n=== ПОШАГОВАЯ ПРОВЕРКА ДЕДУПЛИКАЦИИ ===")
        
        # Берем несколько объявлений для тестирования
        test_ads = db.query(db_models.DBAd).filter(
            and_(
                db_models.DBAd.is_processed == True,
                db_models.DBAd.unique_ad_id.is_(None)
            )
        ).limit(3).all()
        
        processor = DuplicateProcessor(db)
        
        for i, ad in enumerate(test_ads):
            print(f"\n--- ТЕСТ ОБЪЯВЛЕНИЯ {i+1} (ID: {ad.id}) ---")
            print(f"Title: {ad.title}")
            print(f"Price: {ad.price}, Area: {ad.area_sqm}, Rooms: {ad.rooms}")
            print(f"Phone: {ad.phone_numbers}")
            
            # Шаг 1: Получаем фото хеши
            ad_photo_hashes = [photo.hash for photo in ad.photos if photo.hash]
            print(f"Photo hashes: {len(ad_photo_hashes)}")
            
            # Шаг 2: Получаем текстовые эмбеддинги
            try:
                text_embeddings = processor._get_text_embeddings(ad)
                print(f"Text embeddings shape: {text_embeddings.shape}")
            except Exception as e:
                print(f"ERROR getting text embeddings: {e}")
                continue
            
            # Шаг 3: Ищем похожие уникальные объявления
            try:
                similar_ads = processor._find_similar_unique_ads(ad, ad_photo_hashes, text_embeddings)
                print(f"Found {len(similar_ads)} similar unique ads")
                
                if similar_ads:
                    for j, (unique_ad, similarity) in enumerate(similar_ads[:3]):  # Показываем первые 3
                        print(f"  Similar ad {j+1}: ID {unique_ad.id}, similarity: {similarity:.3f}")
                        print(f"    Title: {unique_ad.title[:50]}...")
                        print(f"    Price: {unique_ad.price}, Area: {unique_ad.area_sqm}")
                else:
                    print("  No similar ads found")
                    
            except Exception as e:
                print(f"ERROR finding similar ads: {e}")
                continue
            
            # Шаг 4: Проверяем детали схожести с первым уникальным объявлением
            if similar_ads:
                unique_ad, similarity = similar_ads[0]
                print(f"\n  ДЕТАЛИ СХОЖЕСТИ с уникальным объявлением {unique_ad.id}:")
                
                try:
                    # Проверяем схожесть по характеристикам
                    char_sim = processor._calculate_property_characteristics_similarity(ad, unique_ad)
                    print(f"    Characteristics similarity: {char_sim:.3f}")
                    
                    # Проверяем схожесть по адресу
                    addr_sim = processor._calculate_address_similarity_with_unique(ad, unique_ad)
                    print(f"    Address similarity: {addr_sim:.3f}")
                    
                    # Проверяем схожесть по фото
                    unique_photo_hashes = [photo.hash for photo in unique_ad.photos if photo.hash]
                    photo_sim = processor._calculate_photo_similarity(ad_photo_hashes, unique_photo_hashes)
                    print(f"    Photo similarity: {photo_sim:.3f}")
                    
                    # Проверяем схожесть по тексту
                    if unique_ad.text_embeddings:
                        unique_text_embeddings = np.array(unique_ad.text_embeddings)
                        text_sim = processor._calculate_text_similarity(text_embeddings, unique_text_embeddings)
                        print(f"    Text similarity: {text_sim:.3f}")
                    
                    # Проверяем порог схожести
                    overall_sim, threshold = processor._calculate_similarity_with_unique(
                        ad, unique_ad, ad_photo_hashes, text_embeddings
                    )
                    print(f"    Overall similarity: {overall_sim:.3f}")
                    print(f"    Threshold: {threshold:.3f}")
                    print(f"    Is duplicate: {overall_sim > threshold}")
                    
                except Exception as e:
                    print(f"    ERROR calculating similarity details: {e}")
        
        # 4. Проверяем пороги схожести
        print("\n=== ПРОВЕРКА ПОРОГОВ СХОЖЕСТИ ===")
        print("Текущие пороги:")
        print("  - С фото: 0.65")
        print("  - Без фото: 0.68")
        print("  - Веса: characteristics=0.5, address=0.2, photo=0.1, text=0.2")
        
        # 5. Проверяем количество кандидатов для сравнения
        print("\n=== КАНДИДАТЫ ДЛЯ СРАВНЕНИЯ ===")
        for ad in test_ads[:2]:  # Проверяем первые 2
            base_query = db.query(db_models.DBUniqueAd)
            if ad.location_id:
                base_query = base_query.filter(db_models.DBUniqueAd.location_id == ad.location_id)
            if ad.price:
                min_price = ad.price * 0.8
                max_price = ad.price * 1.2
                base_query = base_query.filter(
                    and_(
                        db_models.DBUniqueAd.price >= min_price,
                        db_models.DBUniqueAd.price <= max_price
                    )
                )
            if ad.rooms:
                base_query = base_query.filter(db_models.DBUniqueAd.rooms == ad.rooms)
            
            candidates = base_query.all()
            print(f"Ad {ad.id}: {len(candidates)} candidates after basic filtering")
            
            if candidates:
                print(f"  First candidate: ID {candidates[0].id}, Price: {candidates[0].price}, Area: {candidates[0].area_sqm}")
        
    finally:
        db.close()

if __name__ == "__main__":
    debug_deduplication() 