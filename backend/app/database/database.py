# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Создаем движок SQLAlchemy с настройками пула соединений
engine = create_engine(
    DATABASE_URL,
    pool_size=20,           # Увеличиваем базовый размер пула
    max_overflow=30,        # Увеличиваем максимальное количество дополнительных соединений  
    pool_timeout=60,        # Увеличиваем таймаут ожидания соединения
    pool_recycle=3600,      # Переиспользуем соединения каждый час
    pool_pre_ping=True,     # Проверяем соединения перед использованием
    echo=False              # Отключаем логирование SQL запросов
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Функция для получения сессии базы данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


