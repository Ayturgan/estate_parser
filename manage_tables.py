import sys
from sqlalchemy import create_engine, text
from app.database import Base
import app.db_models 

# ЯВНО УКАЗЫВАЕМ ССЫЛКУ НА БД ЗДЕСЬ:
DATABASE_URL = "postgresql://estate_user:admin123@localhost:5432/estate_db" 
engine = create_engine(DATABASE_URL)

def main():
    confirm = input("ВНИМАНИЕ: Все таблицы будут удалены и созданы заново! Продолжить? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Операция отменена.")
        sys.exit(0)

    print("Удаление всех таблиц через SQL...")
    with engine.connect() as conn:
        # Удаляем всю схему public целиком (это удалит все таблицы, ограничения, индексы)
        conn.execute(text("DROP SCHEMA public CASCADE;"))
        # Создаем пустую схему public заново
        conn.execute(text("CREATE SCHEMA public;"))
        conn.commit()
    
    print("Создание всех таблиц...")
    Base.metadata.create_all(bind=engine)
    print("✅ Все таблицы успешно пересозданы!")

if __name__ == "__main__":
    main() 