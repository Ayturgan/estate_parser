#!/usr/bin/env python3
"""
Скрипт для создания первого администратора системы Estate Parser
"""

import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))

from app.services.auth_service import auth_service
from app.database.models import AdminCreate

DATABASE_URL = "postgresql://estate_user:admin123@localhost:5432/estate_db"

def create_first_admin():
    """Создает первого администратора системы"""
    print("🔐 Создание первого администратора Estate Parser")
    print("=" * 50)
    
    # Получаем данные от пользователя
    username = input("Введите имя пользователя: ").strip()
    if not username:
        print("❌ Имя пользователя не может быть пустым!")
        return False
    
    password = input("Введите пароль (минимум 6 символов): ").strip()
    if len(password) < 6:
        print("❌ Пароль должен содержать минимум 6 символов!")
        return False
    
    full_name = input("Введите полное имя (необязательно): ").strip()
    if not full_name:
        full_name = None
    
    # Создаем администратора
    try:
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        with SessionLocal() as db:
            admin_data = AdminCreate(
                username=username,
                password=password,
                full_name=full_name
            )
            
            new_admin = auth_service.create_admin(db, admin_data)
            
            print("\n✅ Администратор успешно создан!")
            print(f"   ID: {new_admin.id}")
            print(f"   Имя пользователя: {new_admin.username}")
            print(f"   Полное имя: {new_admin.full_name or 'Не указано'}")
            print(f"   Дата создания: {new_admin.created_at}")
            print("\n🌐 Теперь вы можете войти в систему:")
            print("   1. Откройте http://localhost:8000/login")
            print("   2. Введите свои учетные данные")
            print("   3. Получите доступ к панели управления")
            
            return True
            
    except ValueError as e:
        print(f"❌ Ошибка: {e}")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

def main():
    """Основная функция"""
    try:
        # Проверяем подключение к базе данных
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        with SessionLocal() as db:
            # Проверяем, есть ли уже администраторы
            from app.database.db_models import DBAdmin
            existing_admins = db.query(DBAdmin).count()
            
            if existing_admins > 0:
                print(f"ℹ️  В системе уже есть {existing_admins} администратор(ов).")
                choice = input("Создать ещё одного? (y/N): ").strip().lower()
                if choice not in ['y', 'yes', 'да', 'д']:
                    print("Отменено.")
                    return
        
        # Создаем администратора
        success = create_first_admin()
        
        if success:
            print("\n🚀 Готово! Система авторизации настроена.")
        else:
            print("\n💥 Не удалось создать администратора.")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        print("Убедитесь, что база данных запущена и доступна.")
        sys.exit(1)

if __name__ == "__main__":
    main() 