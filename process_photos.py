#!/usr/bin/env python3
"""
Скрипт для массовой обработки всех фотографий без хешей
Использование: python process_photos.py
"""

import sys
import os
import asyncio
import logging
from datetime import datetime

# Добавляем корневую папку в путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.services.photo_service import PhotoService
from app import db_models

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('process_photos.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def main():
    """Основная функция обработки фотографий"""
    logger.info("🖼️ Starting mass photo processing...")
    
    db = SessionLocal()
    photo_service = PhotoService()
    
    try:
        # Получаем статистику до обработки
        stats_before = photo_service.get_processing_stats(db)
        logger.info(f"📊 Statistics before processing:")
        logger.info(f"   Total photos: {stats_before['total_photos']}")
        logger.info(f"   Processed photos: {stats_before['processed_photos']}")
        logger.info(f"   Unprocessed photos: {stats_before['unprocessed_photos']}")
        logger.info(f"   Processing percentage: {stats_before['processing_percentage']:.1f}%")
        
        if stats_before['unprocessed_photos'] == 0:
            logger.info("✅ All photos are already processed!")
            return
        
        # Начинаем обработку
        start_time = datetime.now()
        logger.info(f"🔄 Starting processing of {stats_before['unprocessed_photos']} photos...")
        
        # Обрабатываем фотографии батчами
        batch_size = 50
        total_processed = 0
        
        while True:
            # Получаем статистику текущего батча
            current_stats = photo_service.get_processing_stats(db)
            unprocessed = current_stats['unprocessed_photos']
            
            if unprocessed == 0:
                break
            
            logger.info(f"📦 Processing batch: {min(batch_size, unprocessed)} photos remaining...")
            
            # Обрабатываем батч
            await photo_service.process_all_unprocessed_photos(db, batch_size)
            
            # Обновляем счетчик
            new_stats = photo_service.get_processing_stats(db)
            processed_in_batch = current_stats['processed_photos'] - new_stats['processed_photos']
            total_processed += processed_in_batch
            
            logger.info(f"✅ Batch completed. Processed: {processed_in_batch}, Total: {total_processed}")
            
            # Небольшая пауза между батчами
            await asyncio.sleep(1)
        
        # Финальная статистика
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        stats_after = photo_service.get_processing_stats(db)
        
        logger.info(f"🎉 Photo processing completed!")
        logger.info(f"📊 Final statistics:")
        logger.info(f"   Total photos: {stats_after['total_photos']}")
        logger.info(f"   Processed photos: {stats_after['processed_photos']}")
        logger.info(f"   Unprocessed photos: {stats_after['unprocessed_photos']}")
        logger.info(f"   Processing percentage: {stats_after['processing_percentage']:.1f}%")
        logger.info(f"⏱️ Total processing time: {duration:.2f} seconds")
        logger.info(f"🚀 Processing speed: {total_processed/duration:.2f} photos/second")
        
        if stats_after['unprocessed_photos'] > 0:
            logger.warning(f"⚠️ {stats_after['unprocessed_photos']} photos could not be processed")
        else:
            logger.info("✅ All photos successfully processed!")
            
    except Exception as e:
        logger.error(f"❌ Error during photo processing: {e}")
        raise
    finally:
        db.close()

def get_photo_stats():
    """Получает статистику фотографий без асинхронной обработки"""
    logger.info("📊 Getting photo statistics...")
    
    db = SessionLocal()
    photo_service = PhotoService()
    
    try:
        stats = photo_service.get_processing_stats(db)
        
        logger.info(f"📊 Photo Statistics:")
        logger.info(f"   Total photos: {stats['total_photos']}")
        logger.info(f"   Processed photos: {stats['processed_photos']}")
        logger.info(f"   Unprocessed photos: {stats['unprocessed_photos']}")
        logger.info(f"   Processing percentage: {stats['processing_percentage']:.1f}%")
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Error getting photo stats: {e}")
        return None
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Mass photo processing script')
    parser.add_argument('--stats-only', action='store_true', 
                       help='Only show statistics without processing')
    parser.add_argument('--batch-size', type=int, default=50,
                       help='Batch size for processing (default: 50)')
    
    args = parser.parse_args()
    
    if args.stats_only:
        get_photo_stats()
    else:
        # Запускаем асинхронную обработку
        asyncio.run(main()) 