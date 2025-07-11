#!/usr/bin/env python3
"""
Тестовый скрипт для проверки AI извлечения данных с локальным подключением к БД
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
from sqlalchemy import func, and_
import json

def test_ai_extraction():
    """Тестирует AI извлечение данных из объявлений (без типа, сделки и телефонов)"""
    
    print("🔍 Тестирование AI извлечения данных (без типа, сделки и телефонов)")
    print("=" * 50)
    
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
        # Получаем несколько объявлений для тестирования
        test_ads = db.query(db_models.DBAd).filter(
            db_models.DBAd.description.isnot(None)
        ).limit(5).all()
        
        print(f"📊 Найдено {len(test_ads)} объявлений для тестирования")
        
        if not test_ads:
            print("❌ Нет объявлений с описанием для тестирования")
            return
        
        # Тестируем каждое объявление
        for i, ad in enumerate(test_ads, 1):
            print(f"\n🔍 Тест {i}/{len(test_ads)}")
            print(f"📝 Заголовок: {ad.title[:100] if ad.title else 'Без заголовка'}...")
            print(f"📄 Описание: {ad.description[:200] if ad.description else 'Без описания'}...")
            
            # Объединяем заголовок и описание
            full_text = f"{ad.title or ''} {ad.description or ''}".strip()
            
            # Тестируем AI извлечение
            try:
                extracted_data = ai_extractor.extract_and_classify(
                    title=ad.title or "",
                    description=ad.description or "",
                    existing_data={}
                )
                
                print(f"✅ AI извлечение завершено")
                print(f"  🏠 Комнаты: {extracted_data.get('rooms')}")
                print(f"  📐 Площадь: {extracted_data.get('area_sqm')} м²")
                print(f"  🏢 Этаж: {extracted_data.get('floor')}/{extracted_data.get('total_floors')}")
                print(f"  📍 Локация: {extracted_data.get('location')}")
                print(f"  🔥 Отопление: {extracted_data.get('heating')}")
                print(f"  🪑 Мебель: {extracted_data.get('furniture')}")
                print(f"  🔧 Состояние: {extracted_data.get('condition')}")
                print(f"  🛠️ Удобства: {extracted_data.get('amenities')}")
                print(f"  📊 Качество извлечения: {extracted_data.get('extraction_quality', 0):.2f}")
                
                # Сохраняем только нужные поля
                if extracted_data.get('area_sqm'):
                    ad.area_sqm = extracted_data['area_sqm']
                    print(f"  💾 Площадь сохранена в БД: {ad.area_sqm}")
                if extracted_data.get('rooms'):
                    ad.rooms = extracted_data['rooms']
                    print(f"  💾 Комнаты сохранены в БД: {ad.rooms}")
                if extracted_data.get('floor'):
                    ad.floor = extracted_data['floor']
                    print(f"  💾 Этаж сохранен в БД: {ad.floor}")
                if extracted_data.get('total_floors'):
                    ad.total_floors = extracted_data['total_floors']
                    print(f"  💾 Общая этажность сохранена в БД: {ad.total_floors}")
                if extracted_data.get('location'):
                    ad.location = extracted_data['location']
                    print(f"  💾 Локация сохранена в БД: {ad.location}")
                if extracted_data.get('heating'):
                    ad.heating = extracted_data['heating']
                    print(f"  💾 Отопление сохранено в БД: {ad.heating}")
                if extracted_data.get('furniture'):
                    ad.furniture = extracted_data['furniture']
                    print(f"  💾 Мебель сохранена в БД: {ad.furniture}")
                if extracted_data.get('condition'):
                    ad.condition = extracted_data['condition']
                    print(f"  💾 Состояние сохранено в БД: {ad.condition}")
                if extracted_data.get('amenities'):
                    ad.amenities = json.dumps(extracted_data['amenities'])
                    print(f"  💾 Удобства сохранены в БД: {ad.amenities}")
            except Exception as e:
                print(f"❌ Ошибка AI извлечения: {e}")
        
        # Сохраняем изменения в БД
        try:
            db.commit()
            print(f"\n✅ Изменения сохранены в базе данных")
        except Exception as e:
            print(f"❌ Ошибка сохранения в БД: {e}")
            db.rollback()
        
        # Проверяем статистику после обработки
        print(f"\n📊 Статистика после AI обработки:")
        ads_with_area = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.area_sqm.isnot(None)
        ).scalar() or 0
        total_ads = db.query(func.count(db_models.DBAd.id)).scalar() or 0
        print(f"  Объявления с площадью: {ads_with_area}/{total_ads} ({ads_with_area/total_ads*100:.1f}%)")
        ads_with_rooms = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.rooms.isnot(None)
        ).scalar() or 0
        print(f"  Объявления с комнатами: {ads_with_rooms}/{total_ads} ({ads_with_rooms/total_ads*100:.1f}%)")
        print(f"\n✅ Тестирование AI извлечения завершено")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_ai_extraction() 