import asyncio
from typing import Dict
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
        pending_count = db.query(db_models.DBAd).filter(
            db_models.DBAd.is_processed == False
        ).count()
        
        if pending_count == 0:
            return {"processed": 0, "pending": 0}
        total_processed = 0
        loop = asyncio.get_running_loop()
        while True:
            await loop.run_in_executor(None, processor.process_new_ads, self.batch_size)
            remaining = db.query(db_models.DBAd).filter(
                db_models.DBAd.is_processed == False
            ).count()
            
            batch_processed = min(self.batch_size, pending_count - total_processed)
            total_processed += batch_processed
            
            logger.info(f"Processed batch of {batch_processed} ads. Remaining: {remaining}")
            
            if remaining == 0:
                break

            await asyncio.sleep(0.1)
        
        return {"processed": total_processed, "pending": 0}
    
    async def detect_all_realtors(self, db: Session) -> Dict[str, int]:
        """Обнаруживает всех риэлторов"""
        processor = DuplicateProcessor(db)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, processor.reset_realtor_flags)
        await loop.run_in_executor(None, processor.detect_realtors)
        stats = await loop.run_in_executor(None, processor.get_realtor_statistics)
        
        return {
            "realtor_unique_ads": stats["realtor_unique_ads"],
            "realtor_original_ads": stats["realtor_original_ads"],
            "total_unique_ads": stats["total_unique_ads"],
            "total_original_ads": stats["total_original_ads"]
        }

