#!/usr/bin/env python3
"""
Тестовый скрипт для проверки интеграции AI извлечения в пайплайн автоматизации
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Настраиваем подключение к БД
os.environ['DATABASE_URL'] = "postgresql://estate_user:admin123@localhost:5432/estate_db"
os.environ['DB_HOST'] = "localhost"
os.environ['DB_PORT'] = "5432"
os.environ['DB_NAME'] = "estate_db"
os.environ['DB_USER'] = "estate_user"
os.environ['DB_PASSWORD'] = "admin123"

from app.database import SessionLocal
from app.database import db_models
from app.services.ai_data_extractor import AIDataExtractor
from app.utils.duplicate_processor import DuplicateProcessor
from app.services.photo_service import PhotoService
from sqlalchemy import func
import json

async def test_ai_pipeline_integration():
    """Тестирует интеграцию AI извлечения в пайплайн автоматизации"""
    
    print("🔍 Тестирование интеграции AI извлечения в пайплайн автоматизации")
    print("=" * 70)
    
    # Инициализируем AI экстрактор
    try:
        ai_extractor = AIDataExtractor()
        print("✅ AI экстрактор инициализирован")
    except Exception as e:
        print(f"❌ Ошибка инициализации AI экстрактора: {e}")
        return
    
    # Подключаемся к базе данных
    db = SessionLocal()
    try:
        # 1. Проверяем статистику до обработки
        print("\n📊 Статистика до обработки:")
        total_ads = db.query(func.count(db_models.DBAd.id)).scalar() or 0
        ads_with_area = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.area_sqm.isnot(None)
        ).scalar() or 0
        ads_with_rooms = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.rooms.isnot(None)
        ).scalar() or 0
        ads_with_heating = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.heating.isnot(None)
        ).scalar() or 0
        ads_with_furniture = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.furniture.isnot(None)
        ).scalar() or 0
        
        print(f"  Всего объявлений: {total_ads}")
        print(f"  С площадью: {ads_with_area}/{total_ads} ({ads_with_area/total_ads*100:.1f}%)")
        print(f"  С комнатами: {ads_with_rooms}/{total_ads} ({ads_with_rooms/total_ads*100:.1f}%)")
        print(f"  С отоплением: {ads_with_heating}/{total_ads} ({ads_with_heating/total_ads*100:.1f}%)")
        print(f"  С мебелью: {ads_with_furniture}/{total_ads} ({ads_with_furniture/total_ads*100:.1f}%)")
        
        # 2. Тестируем AI извлечение на нескольких объявлениях
        print(f"\n🔍 Тестирование AI извлечения:")
        test_ads = db.query(db_models.DBAd).filter(
            db_models.DBAd.description.isnot(None)
        ).limit(3).all()
        
        for i, ad in enumerate(test_ads, 1):
            print(f"\n  Тест {i}/{len(test_ads)} - ID: {ad.id}")
            print(f"    Заголовок: {ad.title[:50] if ad.title else 'Без заголовка'}...")
            
            # Тестируем AI извлечение
            try:
                extracted_data = ai_extractor.extract_and_classify(
                    title=ad.title or "",
                    description=ad.description or "",
                    existing_data={}
                )
                
                print(f"    ✅ AI извлечение завершено")
                print(f"      Площадь: {extracted_data.get('area_sqm')} м²")
                print(f"      Комнаты: {extracted_data.get('rooms')}")
                print(f"      Этаж: {extracted_data.get('floor')}/{extracted_data.get('total_floors')}")
                print(f"      Отопление: {extracted_data.get('heating')}")
                print(f"      Мебель: {extracted_data.get('furniture')}")
                print(f"      Состояние: {extracted_data.get('condition')}")
                print(f"      Качество: {extracted_data.get('extraction_quality', 0):.2f}")
                
                # Сохраняем извлеченные данные
                if extracted_data.get('area_sqm'):
                    ad.area_sqm = extracted_data['area_sqm']
                if extracted_data.get('rooms'):
                    ad.rooms = extracted_data['rooms']
                if extracted_data.get('floor'):
                    ad.floor = extracted_data['floor']
                if extracted_data.get('total_floors'):
                    ad.total_floors = extracted_data['total_floors']
                if extracted_data.get('heating'):
                    ad.heating = extracted_data['heating']
                if extracted_data.get('furniture'):
                    ad.furniture = extracted_data['furniture']
                if extracted_data.get('condition'):
                    ad.condition = extracted_data['condition']
                if extracted_data.get('amenities'):
                    ad.amenities = json.dumps(extracted_data['amenities'])
                
            except Exception as e:
                print(f"    ❌ Ошибка AI извлечения: {e}")
        
        # Сохраняем изменения
        try:
            db.commit()
            print(f"\n✅ Изменения сохранены в базе данных")
        except Exception as e:
            print(f"❌ Ошибка сохранения в БД: {e}")
            db.rollback()
        
        # 3. Тестируем обработку дубликатов
        print(f"\n🔍 Тестирование обработки дубликатов:")
        try:
            processor = DuplicateProcessor(db)
            processed_count = processor.process_new_ads_batch(batch_size=5)
            print(f"  ✅ Обработано {processed_count} объявлений")
        except Exception as e:
            print(f"  ❌ Ошибка обработки дубликатов: {e}")
        
        # 4. Тестируем обработку фотографий
        print(f"\n🔍 Тестирование обработки фотографий:")
        try:
            photo_service = PhotoService()
            # Обрабатываем фотографии для тестовых объявлений
            for ad in test_ads:
                if ad.photos:
                    await photo_service.process_ad_photos(db, ad)
                    print(f"  ✅ Обработаны фотографии для объявления {ad.id}")
        except Exception as e:
            print(f"  ❌ Ошибка обработки фотографий: {e}")
        
        # 5. Проверяем статистику после обработки
        print(f"\n📊 Статистика после обработки:")
        ads_with_area_after = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.area_sqm.isnot(None)
        ).scalar() or 0
        ads_with_rooms_after = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.rooms.isnot(None)
        ).scalar() or 0
        ads_with_heating_after = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.heating.isnot(None)
        ).scalar() or 0
        ads_with_furniture_after = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.furniture.isnot(None)
        ).scalar() or 0
        
        print(f"  С площадью: {ads_with_area_after}/{total_ads} ({ads_with_area_after/total_ads*100:.1f}%)")
        print(f"  С комнатами: {ads_with_rooms_after}/{total_ads} ({ads_with_rooms_after/total_ads*100:.1f}%)")
        print(f"  С отоплением: {ads_with_heating_after}/{total_ads} ({ads_with_heating_after/total_ads*100:.1f}%)")
        print(f"  С мебелью: {ads_with_furniture_after}/{total_ads} ({ads_with_furniture_after/total_ads*100:.1f}%)")
        
        # 6. Проверяем уникальные объявления
        unique_ads_count = db.query(func.count(db_models.DBUniqueAd.id)).scalar() or 0
        print(f"\n📊 Уникальные объявления: {unique_ads_count}")
        
        print(f"\n✅ Тестирование интеграции AI извлечения завершено")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_ai_pipeline_integration()) 