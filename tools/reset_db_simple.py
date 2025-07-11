#!/usr/bin/env python3
"""
Простой скрипт для сброса базы данных
Удаляет схему public и создает таблицы заново
"""

import psycopg2
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Прямая ссылка на БД
DATABASE_URL = "postgresql://estate_user:admin123@localhost:5432/estate_db"

def reset_database():
    """Удаляет схему public и создает таблицы заново"""
    try:
        print("🔄 Подключаемся к базе данных...")
        
        # Подключаемся к БД
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("🗑️ Удаляем только таблицы приложения...")
        
        # Список таблиц приложения (без pgAdmin)
        app_tables = [
            'ads', 
            'unique_ads',
            'photos',
            'unique_photos',
            'locations',
            'realtors',
            'ad_duplicates'
        ]
        
        # Удаляем только таблицы приложения
        for table in app_tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
            print(f"  ✅ Удалена таблица: {table}")
        
        print("✅ Таблицы приложения удалены!")
        
        cursor.close()
        conn.close()
        
        print("🔨 Создаем таблицы...")
        
        # Импортируем и создаем таблицы
        from app.database import db_models
        
        # Создаем engine с правильным URL
        from sqlalchemy import create_engine
        engine = create_engine("postgresql://estate_user:admin123@localhost:5432/estate_db")
        
        # Создаем все таблицы
        db_models.Base.metadata.create_all(bind=engine)
        print("✅ Все таблицы созданы!")
        
        print("🎉 База данных успешно сброшена и пересоздана!")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def reset_processing_flags():
    """Сбрасывает флаги is_processed у сырых объявлений для перезапуска дедупликации"""
    try:
        print("🔄 Сбрасываем флаги обработки...")
        
        # Подключаемся к БД
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Проверяем количество объявлений
        cursor.execute("SELECT COUNT(*) FROM ads;")
        total_ads = cursor.fetchone()[0]
        
        if total_ads == 0:
            print("📊 Нет объявлений для обработки")
            cursor.close()
            conn.close()
            return True
        
        # Сбрасываем флаги is_processed и is_duplicate
        cursor.execute("""
            UPDATE ads 
            SET is_processed = false, 
                is_duplicate = false,
                processed_at = NULL
            WHERE is_processed = true;
        """)
        
        updated_count = cursor.rowcount
        print(f"✅ Сброшены флаги у {updated_count} объявлений")
        
        # Очищаем таблицу unique_ads
        cursor.execute("DELETE FROM unique_ads;")
        unique_deleted = cursor.rowcount
        print(f"✅ Удалено {unique_deleted} уникальных объявлений")
        
        # Очищаем таблицу ad_duplicates
        cursor.execute("DELETE FROM ad_duplicates;")
        duplicates_deleted = cursor.rowcount
        print(f"✅ Удалено {duplicates_deleted} записей о дубликатах")
        
        # Очищаем таблицу realtors
        cursor.execute("DELETE FROM realtors;")
        realtors_deleted = cursor.rowcount
        print(f"✅ Удалено {realtors_deleted} риэлторов")
        
        # Сбрасываем realtor_id у объявлений
        cursor.execute("UPDATE ads SET realtor_id = NULL;")
        realtor_reset = cursor.rowcount
        print(f"✅ Сброшены realtor_id у {realtor_reset} объявлений")
        
        cursor.close()
        conn.close()
        
        print("🎉 Флаги обработки успешно сброшены!")
        print(f"📊 Готово к перезапуску дедупликации для {total_ads} объявлений")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == "__main__":
    print("🗄️ Простой сброс базы данных")
    print("=" * 40)
    
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1 and sys.argv[1] == "reset_flags":
        print("🔄 Режим: сброс флагов обработки")
        success = reset_processing_flags()
    else:
        print("🔄 Режим: полный сброс базы данных")
        success = reset_database()
    
    if success:
        print("\n✅ Готово!")
    else:
        print("\n❌ Ошибка!")
        sys.exit(1) 