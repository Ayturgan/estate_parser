# create_db_tables.py

from app.database import Base, engine
from app.db_models import (
    DBLocation, DBAd, DBPhoto,
    DBUniqueAd, DBUniquePhoto, DBAdDuplicate
)

def create_tables():
    print("Connecting to DB:", engine.url)
    Base.metadata.drop_all(bind=engine) 
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    create_tables()
    print("Таблицы успешно созданы!")

