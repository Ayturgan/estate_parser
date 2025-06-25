import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.db_models import DBUniqueAd, DBAd

def reset_duplicates():
    session = SessionLocal()
    try:
        # Удаляем все уникальные объявления
        deleted = session.query(DBUniqueAd).delete()
        print(f"Удалено уникальных объявлений: {deleted}")
        # Сбрасываем is_processed у всех сырых объявлений
        updated = session.query(DBAd).update({DBAd.is_processed: False, DBAd.is_duplicate: False, DBAd.unique_ad_id: None})
        print(f"Сброшено is_processed у объявлений: {updated}")
        session.commit()
        print("Готово!")
    except Exception as e:
        session.rollback()
        print(f"Ошибка: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    reset_duplicates() 