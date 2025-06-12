# create_db_tables.py

from app.database import engine, Base
from app import db_models # Импортируем, чтобы SQLAlchemy знал о моделях

def create_tables():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")

if __name__ == "__main__":
    create_tables()

