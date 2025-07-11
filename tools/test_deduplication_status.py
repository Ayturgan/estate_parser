#!/usr/bin/env python3
"""
Тестовый скрипт для проверки состояния дедупликации
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.database import SessionLocal
from app.database import db_models
from sqlalchemy import func, and_
import json

def test_deduplication_status():
    """Проверяет текущее состояние дедупликации"""
    
    db = SessionLocal()
    try:
        print("🔍 Анализ состояния дедупликации")
        print("=" * 50)
        
        # 1. Общая статистика
        total_ads = db.query(func.count(db_models.DBAd.id)).scalar() or 0
        total_unique_ads = db.query(func.count(db_models.DBUniqueAd.id)).scalar() or 0
        total_duplicates = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.is_duplicate == True
        ).scalar() or 0
        unprocessed_ads = db.query(func.count(db_models.DBAd.id)).filter(
            and_(
                db_models.DBAd.is_processed == False,
                db_models.DBAd.is_duplicate == False
            )
        ).scalar() or 0
        
        print(f"📊 Общая статистика:")
        print(f"  Всего объявлений: {total_ads}")
        print(f"  Уникальных объявлений: {total_unique_ads}")
        print(f"  Дубликатов: {total_duplicates}")
        print(f"  Необработанных: {unprocessed_ads}")
        
        if total_ads > 0:
            dedup_ratio = (total_duplicates / total_ads) * 100
            print(f"  Коэффициент дедупликации: {dedup_ratio:.1f}%")
        
        # 2. Анализ характеристик объявлений
        print(f"\n🏠 Анализ характеристик объявлений:")
        
        # Площадь
        ads_with_area = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.area_sqm.isnot(None)
        ).scalar() or 0
        print(f"  Объявления с площадью: {ads_with_area}/{total_ads} ({ads_with_area/total_ads*100:.1f}%)")
        
        # Комнаты
        ads_with_rooms = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.rooms.isnot(None)
        ).scalar() or 0
        print(f"  Объявления с комнатами: {ads_with_rooms}/{total_ads} ({ads_with_rooms/total_ads*100:.1f}%)")
        
        # Этаж
        ads_with_floor = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.floor.isnot(None)
        ).scalar() or 0
        print(f"  Объявления с этажом: {ads_with_floor}/{total_ads} ({ads_with_floor/total_ads*100:.1f}%)")
        
        # Локация
        ads_with_location = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.location_id.isnot(None)
        ).scalar() or 0
        print(f"  Объявления с локацией: {ads_with_location}/{total_ads} ({ads_with_location/total_ads*100:.1f}%)")
        
        # Фотографии
        ads_with_photos = db.query(func.count(db_models.DBAd.id)).join(
            db_models.DBPhoto
        ).scalar() or 0
        print(f"  Объявления с фото: {ads_with_photos}/{total_ads} ({ads_with_photos/total_ads*100:.1f}%)")
        
        # Обработанные фото
        processed_photos = db.query(func.count(db_models.DBPhoto.id)).filter(
            db_models.DBPhoto.hash.isnot(None)
        ).scalar() or 0
        total_photos = db.query(func.count(db_models.DBPhoto.id)).scalar() or 0
        print(f"  Обработанных фото: {processed_photos}/{total_photos} ({processed_photos/total_photos*100:.1f}%)")
        
        # 3. Анализ потенциальных дубликатов
        print(f"\n🔍 Анализ потенциальных дубликатов:")
        
        # Объявления с одинаковыми характеристиками
        similar_characteristics = db.query(
            db_models.DBAd.area_sqm,
            db_models.DBAd.rooms,
            db_models.DBAd.floor,
            func.count(db_models.DBAd.id).label('count')
        ).filter(
            and_(
                db_models.DBAd.area_sqm.isnot(None),
                db_models.DBAd.rooms.isnot(None),
                db_models.DBAd.floor.isnot(None)
            )
        ).group_by(
            db_models.DBAd.area_sqm,
            db_models.DBAd.rooms,
            db_models.DBAd.floor
        ).having(
            func.count(db_models.DBAd.id) > 1
        ).all()
        
        print(f"  Групп с одинаковыми характеристиками: {len(similar_characteristics)}")
        
        total_potential_duplicates = sum(group.count for group in similar_characteristics)
        print(f"  Потенциальных дубликатов: {total_potential_duplicates}")
        
        # 4. Примеры групп
        if similar_characteristics:
            print(f"\n📋 Примеры групп потенциальных дубликатов:")
            for i, group in enumerate(similar_characteristics[:5]):
                print(f"  Группа {i+1}: {group.rooms}к, {group.area_sqm}м², {group.floor}эт. - {group.count} объявлений")
        
        # 5. Оценка эффективности алгоритма
        print(f"\n✅ Оценка эффективности алгоритма дедупликации:")
        
        if total_ads > 0:
            # Минимальные требования для дедупликации
            min_requirements = min(ads_with_area, ads_with_rooms, ads_with_location)
            coverage = (min_requirements / total_ads) * 100
            
            print(f"  Покрытие алгоритмом: {coverage:.1f}%")
            
            if coverage > 50:
                print(f"  ✅ Хорошее покрытие - алгоритм сможет обнаружить большинство дубликатов")
            elif coverage > 20:
                print(f"  ⚠️ Среднее покрытие - алгоритм обнаружит часть дубликатов")
            else:
                print(f"  ❌ Низкое покрытие - алгоритм обнаружит мало дубликатов")
            
            if processed_photos > 0:
                photo_coverage = (processed_photos / total_photos) * 100
                print(f"  Покрытие фото: {photo_coverage:.1f}%")
                
                if photo_coverage > 80:
                    print(f"  ✅ Фото хорошо обработаны - дополнительное подтверждение дубликатов")
                else:
                    print(f"  ⚠️ Много необработанных фото - снижена точность дедупликации")
        
        # 6. Рекомендации
        print(f"\n💡 Рекомендации:")
        
        if unprocessed_ads > 0:
            print(f"  - Запустить обработку {unprocessed_ads} необработанных объявлений")
        
        if processed_photos < total_photos * 0.8:
            print(f"  - Запустить обработку фотографий ({total_photos - processed_photos} осталось)")
        
        if total_potential_duplicates > 0:
            print(f"  - Запустить дедупликацию для обработки {total_potential_duplicates} потенциальных дубликатов")
        
        if coverage < 50:
            print(f"  - Улучшить извлечение характеристик объявлений (площадь, комнаты, локация)")
        
        print(f"\n✅ Анализ завершен")
        
    except Exception as e:
        print(f"❌ Ошибка анализа: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_deduplication_status() 