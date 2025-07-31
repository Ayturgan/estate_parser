#!/usr/bin/env python3
"""
Скрипт для анализа состояния базы данных и выяснения причин "исчезновения" объявлений
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import create_engine, func, and_, or_, case
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import json

# Прямое подключение к базе данных
DATABASE_URL = "postgresql://estate_user:admin123@localhost:5432/estate_db"

# Импорты из проекта
from app.database import db_models

def analyze_database_state():
    """Анализирует состояние базы данных"""
    
    # Подключение к базе данных
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        print("🔍 АНАЛИЗ СОСТОЯНИЯ БАЗЫ ДАННЫХ")
        print("=" * 50)
        
        # 1. Общая статистика
        print("\n📊 ОБЩАЯ СТАТИСТИКА:")
        total_ads = db.query(func.count(db_models.DBAd.id)).scalar()
        total_unique_ads = db.query(func.count(db_models.DBUniqueAd.id)).scalar()
        total_duplicates = db.query(func.count(db_models.DBAd.id)).filter(db_models.DBAd.is_duplicate == True).scalar()
        total_base_ads = db.query(func.count(db_models.DBAd.id)).filter(db_models.DBAd.is_duplicate == False).scalar()
        
        print(f"Всего объявлений в DBAd: {total_ads}")
        print(f"Уникальных объявлений в DBUniqueAd: {total_unique_ads}")
        print(f"Дубликатов: {total_duplicates}")
        print(f"Базовых объявлений: {total_base_ads}")
        
        # 2. Анализ необработанных объявлений
        print("\n🔍 АНАЛИЗ НЕОБРАБОТАННЫХ ОБЪЯВЛЕНИЙ:")
        unprocessed_ads = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.is_processed == False
        ).scalar()
        print(f"Необработанных объявлений: {unprocessed_ads}")
        
        # 3. Анализ по источникам
        print("\n📈 СТАТИСТИКА ПО ИСТОЧНИКАМ:")
        sources_stats = db.query(
            db_models.DBAd.source_name,
            func.count(db_models.DBAd.id).label('total'),
            func.sum(case((db_models.DBAd.is_duplicate == True, 1), else_=0)).label('duplicates'),
            func.sum(case((db_models.DBAd.is_processed == False, 1), else_=0)).label('unprocessed')
        ).group_by(db_models.DBAd.source_name).all()
        
        for source_name, total, duplicates, unprocessed in sources_stats:
            print(f"  {source_name}: всего={total}, дубликатов={duplicates}, необработанных={unprocessed}")
        
        # 4. Анализ по датам
        print("\n📅 АНАЛИЗ ПО ДАТАМ (последние 7 дней):")
        week_ago = datetime.now() - timedelta(days=7)
        daily_stats = db.query(
            func.date(db_models.DBAd.parsed_at).label('date'),
            func.count(db_models.DBAd.id).label('total'),
            func.sum(case((db_models.DBAd.is_duplicate == True, 1), else_=0)).label('duplicates'),
            func.sum(case((db_models.DBAd.is_processed == False, 1), else_=0)).label('unprocessed')
        ).filter(
            db_models.DBAd.parsed_at >= week_ago
        ).group_by(func.date(db_models.DBAd.parsed_at)).order_by(func.date(db_models.DBAd.parsed_at)).all()
        
        for date, total, duplicates, unprocessed in daily_stats:
            print(f"  {date}: всего={total}, дубликатов={duplicates}, необработанных={unprocessed}")
        
        # 5. Анализ ошибок парсинга
        print("\n❌ АНАЛИЗ ОШИБОК:")
        error_ads = db.query(func.count(db_models.DBAd.id)).filter(
            or_(
                db_models.DBAd.title.is_(None),
                db_models.DBAd.title == '',
                db_models.DBAd.price.is_(None),
                db_models.DBAd.price == 0
            )
        ).scalar()
        print(f"Объявлений с ошибками (пустые title/price): {error_ads}")
        
        # 6. Анализ связей с уникальными объявлениями
        print("\n🔗 АНАЛИЗ СВЯЗЕЙ:")
        ads_with_unique = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.unique_ad_id.isnot(None)
        ).scalar()
        ads_without_unique = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.unique_ad_id.is_(None)
        ).scalar()
        print(f"Объявлений связанных с уникальными: {ads_with_unique}")
        print(f"Объявлений НЕ связанных с уникальными: {ads_without_unique}")
        
        # 7. Детальный анализ "исчезнувших" объявлений
        print("\n🔍 ДЕТАЛЬНЫЙ АНАЛИЗ 'ИСЧЕЗНУВШИХ' ОБЪЯВЛЕНИЙ:")
        
        # Объявления без уникальных связей и не дубликаты
        orphan_ads = db.query(func.count(db_models.DBAd.id)).filter(
            and_(
                db_models.DBAd.unique_ad_id.is_(None),
                db_models.DBAd.is_duplicate == False
            )
        ).scalar()
        print(f"Осиротевших объявлений (не дубликаты, без связи): {orphan_ads}")
        
        # Необработанные объявления
        unprocessed_count = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.is_processed == False
        ).scalar()
        print(f"Необработанных объявлений: {unprocessed_count}")
        
        # 8. Рекомендации
        print("\n💡 РЕКОМЕНДАЦИИ:")
        
        if unprocessed_count > 0:
            print(f"  ⚠️  Есть {unprocessed_count} необработанных объявлений")
            print("     Запустите обработку дубликатов для их обработки")
        
        if orphan_ads > 0:
            print(f"  ⚠️  Есть {orphan_ads} объявлений без связи с уникальными")
            print("     Это может быть причиной 'исчезновения' объявлений")
        
        if error_ads > 0:
            print(f"  ⚠️  Есть {error_ads} объявлений с ошибками")
            print("     Проверьте качество данных")
        
        # 9. Расчет реальной статистики
        print("\n📊 РЕАЛЬНАЯ СТАТИСТИКА:")
        real_total = total_ads
        real_unique = total_unique_ads + orphan_ads  # Добавляем осиротевшие
        real_duplicates = total_duplicates
        
        print(f"Всего собрано: {real_total}")
        print(f"Уникальных: {real_unique}")
        print(f"Дубликатов: {real_duplicates}")
        print(f"Разница: {real_total - real_unique}")
        
        if real_total - real_unique != real_duplicates:
            print(f"  ⚠️  Несоответствие! Разница должна быть равна количеству дубликатов")
            print(f"  Возможные причины: необработанные объявления или ошибки в данных")
        
    except Exception as e:
        print(f"❌ Ошибка при анализе: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    analyze_database_state() 