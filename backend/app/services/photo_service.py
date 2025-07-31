import asyncio
import aiohttp
from PIL import Image
import io
import imagehash
import logging
from typing import Optional, Dict
from sqlalchemy.orm import Session
from app.database import db_models
import time
import numpy as np

# Импорты для CLIP модели
try:
    from transformers import CLIPProcessor, CLIPModel
    import torch
    CLIP_AVAILABLE = True
except ImportError:
    CLIP_AVAILABLE = False
    logging.warning("CLIP модель недоступна. Установите transformers и torch для полной функциональности.")

logger = logging.getLogger(__name__)

# Глобальные переменные для кэширования CLIP модели
_clip_model_photo = None
_clip_processor_photo = None
_clip_loaded_photo = False

def get_clip_model_photo():
    """Возвращает кэшированную CLIP модель для обработки фотографий"""
    global _clip_model_photo, _clip_processor_photo, _clip_loaded_photo
    
    if not CLIP_AVAILABLE:
        return None, None
    
    if not _clip_loaded_photo:
        try:
            logger.info("Загружаем CLIP модель для обработки фотографий...")
            _clip_model_photo = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            _clip_processor_photo = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            _clip_loaded_photo = True
            logger.info("CLIP модель загружена успешно")
        except Exception as e:
            logger.warning(f"Не удалось загрузить CLIP модель: {e}")
            _clip_model_photo = None
            _clip_processor_photo = None
    
    return _clip_model_photo, _clip_processor_photo

class PhotoService:
    def __init__(self, max_concurrent: int = 10, timeout: int = 30, max_retries: int = 3):
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.max_retries = max_retries
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # Инициализация CLIP модели (используем кэшированную)
        # self.clip_model, self.clip_processor = get_clip_model_photo()  # Отключаем CLIP
        self.clip_model, self.clip_processor = None, None
    
    async def process_ad_photos(self, db: Session, ad: db_models.DBAd):
        """Асинхронно и параллельно обрабатывает все фотографии объявления"""
        if not ad.photos:
            logger.info(f"No photos to process for ad {ad.id}")
            return
        
        total_photos = len(ad.photos)
        photos_without_hash = [p for p in ad.photos if not p.perceptual_hashes]
        
        if not photos_without_hash:
            logger.info(f"All {total_photos} photos for ad {ad.id} already have hashes")
            return
            
        logger.info(f"Processing {len(photos_without_hash)} photos without hashes for ad {ad.id}")
        
        tasks = []
        for photo in photos_without_hash:
            tasks.append(self._process_single_photo_with_retry(photo))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_hashes = 0
        failed_photos = 0
        not_found_photos = 0
        
        for photo, result in zip(photos_without_hash, results):
            if isinstance(result, dict) and result:
                # Успешный результат с хешами и эмбеддингами
                if 'perceptual_hashes' in result:
                    photo.perceptual_hashes = result['perceptual_hashes']
                if 'clip_embedding' in result and result['clip_embedding']:
                    photo.clip_embedding = result['clip_embedding']
                successful_hashes += 1
                logger.debug(f"Successfully computed hashes and embeddings for photo {photo.url}")
            elif isinstance(result, str) and result in ["404_NOT_FOUND", "403_FORBIDDEN"]:
                # Специальные случаи - помечаем как обработанные
                photo.perceptual_hashes = result
                failed_photos += 1
                if result == "404_NOT_FOUND":
                    not_found_photos += 1
                    logger.info(f"Marked 404 photo as processed: {photo.url}")
                else:
                    logger.info(f"Marked 403 photo as processed: {photo.url}")
            else:
                # Остальные ошибки
                failed_photos += 1
                logger.debug(f"Failed to compute hash for photo {photo.url}: {result}")
        
        try:
            db.commit()
            logger.info(f"Successfully processed {successful_hashes} photos for ad {ad.id}")
            if failed_photos > 0:
                logger.warning(f"Failed to process {failed_photos} photos for ad {ad.id} (404 not found: {not_found_photos})")
        except Exception as e:
            logger.error(f"Error committing photo hashes for ad {ad.id}: {e}")
            db.rollback()
    
    async def _process_single_photo_with_retry(self, photo: db_models.DBPhoto) -> Optional[Dict[str, str]]:
        """Обрабатывает одну фотографию с повторными попытками"""
        for attempt in range(self.max_retries):
            try:
                return await self._process_single_photo(photo)
            except Exception as e:
                error_msg = str(e)
                
                # Если это 404 ошибка, не повторяем попытки - изображение не существует
                if "404" in error_msg or "Not Found" in error_msg:
                    logger.warning(f"Photo not found (404): {photo.url} - skipping retries")
                    return "404_NOT_FOUND"  # Возвращаем специальную строку вместо None
                
                # Если это 403 ошибка, тоже не повторяем - доступ запрещен
                if "403" in error_msg or "Forbidden" in error_msg:
                    logger.warning(f"Photo access forbidden (403): {photo.url} - skipping retries")
                    return "403_FORBIDDEN"  # Возвращаем специальную строку вместо None
                
                logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed for photo {photo.url}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error(f"All {self.max_retries} attempts failed for photo {photo.url}")
                    return None
    
    async def _process_single_photo(self, photo: db_models.DBPhoto) -> Dict[str, str]:
        """Обрабатывает одну фотографию"""
        async with self.semaphore:
            start_time = time.time()
            try:
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                
                # Добавляем правильные заголовки для разных источников
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                
                # Специальные заголовки для Lalafo
                if 'lalafo.com' in photo.url:
                    headers['Referer'] = 'https://lalafo.kg/'
                    headers['Accept'] = 'image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
                    headers['Accept-Language'] = 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
                
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(photo.url, headers=headers) as response:
                        if response.status == 200:
                            content = await response.read()
                            if not content or len(content) < 100:
                                raise Exception("Image too small or empty")
                            loop = asyncio.get_running_loop()
                            photo_data = await loop.run_in_executor(
                                None,
                                self._compute_hash_sync,
                                content
                            )
                            processing_time = time.time() - start_time
                            logger.info(f"Computed hashes and embeddings for photo {photo.url} in {processing_time:.2f}s")
                            return photo_data
                        else:
                            raise Exception(f"HTTP {response.status}: {response.reason}")
            except Exception as e:
                processing_time = time.time() - start_time
                logger.error(f"Error processing photo {photo.url} after {processing_time:.2f}s: {e}")
                raise e
    
    def _compute_hash_sync(self, content: bytes) -> Dict[str, any]:
        img = Image.open(io.BytesIO(content))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Вычисляем различные перцептивные хеши
        hashes = {
            'pHash': str(imagehash.phash(img)),
            'dHash': str(imagehash.dhash(img)),
            'aHash': str(imagehash.average_hash(img)),
            'wHash': str(imagehash.whash(img))
        }
        
        # Вычисляем CLIP эмбеддинг если модель доступна (отключено)
        clip_embedding = None
        # if self.clip_model and self.clip_processor:
        #     try:
        #         inputs = self.clip_processor(images=img, return_tensors="pt")
        #         with torch.no_grad():
        #         image_features = self.clip_model.get_image_features(**inputs)
        #         clip_embedding = image_features.cpu().numpy()[0].tolist()
        #     except Exception as e:
        #         logger.warning(f"Ошибка вычисления CLIP эмбеддинга: {e}")
        
        return {
            'perceptual_hashes': hashes,
            'clip_embedding': clip_embedding
        }
    
    async def process_all_unprocessed_photos(self, db: Session, batch_size: int = 500):
        """Обрабатывает все фотографии без хешей в базе данных"""
        logger.info("Starting batch processing of all unprocessed photos...")
        
        total_processed = 0
        while True:
            unprocessed_photos = db.query(db_models.DBPhoto).filter(
                db_models.DBPhoto.perceptual_hashes.is_(None)
            ).limit(batch_size).all()
            
            if not unprocessed_photos:
                logger.info(f"Processing completed. Total processed: {total_processed}")
                break
            
            logger.info(f"Processing batch of {len(unprocessed_photos)} photos...")
            
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
            
            total_processed += len(unprocessed_photos)
            logger.info(f"Batch completed. Processed: {total_processed}")
    
    async def get_processing_status(self) -> dict:
        """Получает статус обработки фотографий"""
        try:
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                total_photos = db.query(db_models.DBPhoto).count()
                processed_photos = db.query(db_models.DBPhoto).filter(
                    db_models.DBPhoto.perceptual_hashes.isnot(None)
                ).count()
                unprocessed_photos = total_photos - processed_photos
                processing_percentage = (processed_photos / total_photos * 100) if total_photos > 0 else 0
                
                stats = {
                    'total_photos': total_photos,
                    'processed_photos': processed_photos,
                    'unprocessed_photos': unprocessed_photos,
                    'processing_percentage': processing_percentage
                }
                
                # Определяем статус: если есть необработанные фото - running, иначе completed
                if unprocessed_photos > 0:
                    status = "running"
                    message = f"Обработка фотографий: {processed_photos}/{total_photos} ({processing_percentage:.1f}%)"
                else:
                    status = "completed"
                    message = f"Обработка фотографий завершена: {processed_photos}/{total_photos} ({processing_percentage:.1f}%)"
                
                return {
                    "status": status,
                    "message": message,
                    "stats": stats
                }
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting photo processing status: {e}")
            return {
                "status": "error", 
                "message": f"Error getting photo processing status: {e}",
                "stats": {}
            }

