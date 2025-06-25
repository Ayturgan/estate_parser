from app.database import Base, engine
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from app.db_models import (
    DBLocation, DBAd, DBPhoto,
    DBUniqueAd, DBUniquePhoto, DBAdDuplicate
)

def drop_fk_constraints():
    with engine.connect() as conn:
        try:
            conn.execute(text('ALTER TABLE ads DROP CONSTRAINT IF EXISTS ads_unique_ad_id_fkey;'))
        except ProgrammingError:
            pass
        try:
            conn.execute(text('ALTER TABLE unique_ads DROP CONSTRAINT IF EXISTS unique_ads_base_ad_id_fkey;'))
        except ProgrammingError:
            pass
        conn.commit()

def drop_tables():
    with engine.connect() as conn:
        for table in ["ad_duplicates", "unique_photos", "photos", "ads", "unique_ads", "locations"]:
            try:
                conn.execute(text(f'DROP TABLE IF EXISTS {table} CASCADE;'))
            except ProgrammingError:
                pass
        conn.commit()

def create_tables():
    print("Connecting to DB:", engine.url)
    drop_fk_constraints()
    drop_tables()
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    create_tables()
    print("Таблицы успешно созданы!")

