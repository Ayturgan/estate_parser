# main.py

from fastapi import FastAPI, HTTPException, status
from typing import List, Dict
from datetime import datetime
import uuid # Для генерации уникальных ID

from models import Ad


# Создаем экземпляр приложения FastAPI
app = FastAPI(
    title="Parser API",
    description="API for parsing real estate listings and detecting duplicates.",
    version="0.1.0"
)

# Временное хранилище для объявлений (пока без БД)
# В реальном приложении здесь будет взаимодействие с PostgreSQL
fake_db: Dict[str, Ad] = {}

@app.post("/ads/", response_model=Ad, status_code=status.HTTP_201_CREATED)
async def create_ad(ad: Ad):
    """
    Создает новое объявление.
    Временно сохраняет объявление в памяти.
    """
    if ad.id is None:
        ad.id = str(uuid.uuid4()) # Генерируем уникальный ID, если его нет
    
    ad.parsed_at = datetime.now().isoformat() # Устанавливаем время парсинга

    if ad.id in fake_db:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ad with this ID already exists")
    
    fake_db[ad.id] = ad
    return ad

@app.get("/ads/{ad_id}", response_model=Ad)
async def get_ad(ad_id: str):
    """
    Возвращает объявление по его ID.
    """
    ad = fake_db.get(ad_id)
    if ad is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad not found")
    return ad

@app.get("/ads/", response_model=List[Ad])
async def get_all_ads():
    """
    Возвращает список всех объявлений.
    """
    return list(fake_db.values())

