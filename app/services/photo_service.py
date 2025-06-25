import asyncio
import aiohttp
from PIL import Image
import io
from imagehash import average_hash
import logging
from typing import Optional
from sqlalchemy.orm import Session
from app import db_models
import time

logger = logging.getLogger(__name__)

class PhotoService:
    def __init__(self, max_concurrent: int = 5, timeout: int = 30, max_retries: int = 3):
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.max_retries = max_retries
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_ad_photos(self, db: Session, ad: db_models.DBAd):
        """Асинхронно обрабатывает все фотографии объявления"""
        if not ad.photos:
            logger.info(f"No photos to process for ad {ad.id}")
            return
        
        logger.info(f"Processing {len(ad.photos)} photos for ad {ad.id}")
        tasks = []
        for photo in ad.photos:
            if not photo.hash:
                task = self._process_single_photo_with_retry(photo)
                tasks.append((photo, task))
        
        if not tasks:
            logger.info(f"All photos for ad {ad.id} already have hashes")
            return
        
        logger.info(f"Processing {len(tasks)} photos without hashes for ad {ad.id}")
        for photo, task in tasks:
            try:
                photo_hash = await task
                if photo_hash:
                    photo.hash = photo_hash
                    logger.info(f"Successfully computed hash for photo {photo.url}: {photo_hash[:10]}...")
                else:
                    logger.error(f"Failed to compute hash for photo {photo.url}")
            except Exception as e:
                logger.error(f"Error processing photo {photo.url}: {e}")
        try:
            db.commit()
            logger.info(f"Successfully processed {len([t for t in tasks if t[0].hash])} photos for ad {ad.id}")
        except Exception as e:
            logger.error(f"Error committing photo hashes for ad {ad.id}: {e}")
            db.rollback()
    
    async def _process_single_photo_with_retry(self, photo: db_models.DBPhoto) -> Optional[str]:
        """Обрабатывает одну фотографию с повторными попытками"""
        for attempt in range(self.max_retries):
            try:
                return await self._process_single_photo(photo)
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed for photo {photo.url}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error(f"All {self.max_retries} attempts failed for photo {photo.url}")
                    return None
    
    async def _process_single_photo(self, photo: db_models.DBPhoto) -> str:
        """Обрабатывает одну фотографию"""
        async with self.semaphore:
            start_time = time.time()
            try:
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(photo.url) as response:
                        if response.status == 200:
                            content = await response.read()
                            if not content or len(content) < 100:
                                raise Exception("Image too small or empty")
                            img = Image.open(io.BytesIO(content))
                            if img.mode != 'RGB':
                                img = img.convert('RGB')
                            
                            photo_hash = str(average_hash(img))
                            processing_time = time.time() - start_time
                            
                            logger.info(f"Computed hash for photo {photo.url} in {processing_time:.2f}s: {photo_hash[:10]}...")
                            return photo_hash
                        else:
                            raise Exception(f"HTTP {response.status}: {response.reason}")
            except Exception as e:
                processing_time = time.time() - start_time
                logger.error(f"Error processing photo {photo.url} after {processing_time:.2f}s: {e}")
                raise e
    
    async def process_all_unprocessed_photos(self, db: Session, batch_size: int = 50):
        """Обрабатывает все фотографии без хешей в базе данных"""
        logger.info("Starting batch processing of all unprocessed photos...")
        
        unprocessed_photos = db.query(db_models.DBPhoto).filter(
            db_models.DBPhoto.hash.is_(None)
        ).limit(batch_size).all()
        
        if not unprocessed_photos:
            logger.info("No unprocessed photos found")
            return
        
        logger.info(f"Found {len(unprocessed_photos)} unprocessed photos")
        
        photos_by_ad = {}
        for photo in unprocessed_photos:
            if photo.ad_id not in photos_by_ad:
                photos_by_ad[photo.ad_id] = []
            photos_by_ad[photo.ad_id].append(photo)
        for ad_id, photos in photos_by_ad.items():
            try:
                ad = db.query(db_models.DBAd).filter(db_models.DBAd.id == ad_id).first()
                if ad:
                    await self.process_ad_photos(db, ad)
                else:
                    logger.warning(f"Ad {ad_id} not found for photos")
            except Exception as e:
                logger.error(f"Error processing photos for ad {ad_id}: {e}")
        
        logger.info("Batch processing completed")
    
    def get_processing_stats(self, db: Session) -> dict:
        """Получает статистику обработки фотографий"""
        total_photos = db.query(db_models.DBPhoto).count()
        processed_photos = db.query(db_models.DBPhoto).filter(
            db_models.DBPhoto.hash.isnot(None)
        ).count()
        unprocessed_photos = total_photos - processed_photos
        
        return {
            'total_photos': total_photos,
            'processed_photos': processed_photos,
            'unprocessed_photos': unprocessed_photos,
            'processing_percentage': (processed_photos / total_photos * 100) if total_photos > 0 else 0
        }

