# app/services/duplicate_service.py
import asyncio
from typing import List, Dict
from sqlalchemy.orm import Session
from app import db_models
from app.utils.duplicate_processor import DuplicateProcessor
import logging

logger = logging.getLogger(__name__)

class DuplicateService:
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
    
    async def process_pending_ads(self, db: Session) -> Dict[str, int]:
        """Обрабатывает все необработанные объявления"""
        processor = DuplicateProcessor(db)
        
        # Получаем количество необработанных объявлений
        pending_count = db.query(db_models.DBAd).filter(
            db_models.DBAd.is_processed == False
        ).count()
        
        if pending_count == 0:
            return {"processed": 0, "pending": 0}
        
        # Обрабатываем батчами
        total_processed = 0
        while True:
            # Обрабатываем один батч
            processor.process_new_ads(self.batch_size)
            
            # Проверяем, остались ли необработанные
            remaining = db.query(db_models.DBAd).filter(
                db_models.DBAd.is_processed == False
            ).count()
            
            batch_processed = min(self.batch_size, pending_count - total_processed)
            total_processed += batch_processed
            
            logger.info(f"Processed batch of {batch_processed} ads. Remaining: {remaining}")
            
            if remaining == 0:
                break
            
            # Небольшая пауза между батчами
            await asyncio.sleep(0.1)
        
        return {"processed": total_processed, "pending": 0}
    
    async def detect_all_realtors(self, db: Session) -> Dict[str, int]:
        """Обнаруживает всех риэлторов"""
        processor = DuplicateProcessor(db)
        
        # Сбрасываем предыдущие флаги
        processor.reset_realtor_flags()
        
        # Запускаем обнаружение
        processor.detect_realtors()
        
        # Получаем статистику
        stats = processor.get_realtor_statistics()
        
        return {
            "realtor_unique_ads": stats["realtor_unique_ads"],
            "realtor_original_ads": stats["realtor_original_ads"],
            "total_unique_ads": stats["total_unique_ads"],
            "total_original_ads": stats["total_original_ads"]
        }

