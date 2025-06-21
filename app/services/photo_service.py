# app/services/photo_service.py
import asyncio
import aiohttp
from PIL import Image
import io
from imagehash import average_hash
import logging
from typing import List
from sqlalchemy.orm import Session
from app import db_models

logger = logging.getLogger(__name__)

class PhotoService:
    def __init__(self, max_concurrent: int = 10, timeout: int = 10):
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_ad_photos(self, db: Session, ad: db_models.DBAd):
        """Асинхронно обрабатывает все фотографии объявления"""
        if not ad.photos:
            return
        
        # Создаем задачи для обработки фотографий
        tasks = []
        for photo in ad.photos:
            if not photo.hash:  # Обрабатываем только если хэш еще не вычислен
                task = self._process_single_photo(photo)
                tasks.append(task)
        
        if tasks:
            # Выполняем все задачи параллельно
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Обновляем хэши в базе
            for i, result in enumerate(results):
                if isinstance(result, str):  # Успешно вычислен хэш
                    ad.photos[i].hash = result
                elif isinstance(result, Exception):
                    logger.error(f"Error processing photo {ad.photos[i].url}: {result}")
            
            # Сохраняем изменения
            db.commit()
    
    async def _process_single_photo(self, photo: db_models.DBPhoto) -> str:
        """Обрабатывает одну фотографию"""
        async with self.semaphore:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                    async with session.get(photo.url) as response:
                        if response.status == 200:
                            content = await response.read()
                            img = Image.open(io.BytesIO(content))
                            photo_hash = str(average_hash(img))
                            logger.info(f"Computed hash for photo {photo.url}: {photo_hash}")
                            return photo_hash
                        else:
                            raise Exception(f"HTTP {response.status}")
            except Exception as e:
                logger.error(f"Error processing photo {photo.url}: {e}")
                raise e

