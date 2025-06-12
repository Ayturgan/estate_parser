# database.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Строка подключения к базе данных
# Замени 'your_strong_password' на тот пароль, который ты задала для real_estate_user
SQLALCHEMY_DATABASE_URL = "postgresql://real_estate_user:admin123@localhost:5432/real_estate_db"

# Создаем движок SQLAlchemy
# echo=True будет выводить все SQL-запросы в консоль, полезно для отладки
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True)

# Создаем класс SessionLocal. Каждый экземпляр этого класса будет сессией базы данных.
# autocommit=False означает, что изменения не будут автоматически сохраняться в БД.
# autoflush=False означает, что объекты не будут автоматически синхронизироваться с БД.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для наших декларативных моделей SQLAlchemy
Base = declarative_base()

# Функция для получения сессии базы данных
# Это будет использоваться в FastAPI для Dependency Injection
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

