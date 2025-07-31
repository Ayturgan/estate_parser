import asyncio
import aiohttp
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database.database import SessionLocal
from app.database import db_models
from datetime import datetime
import time
from collections import defaultdict
from app.core.config import get_link_validation_batch_size

logger = logging.getLogger(__name__)

class LinkValidationService:
    """Сервис для валидации ссылок объявлений"""
    
    def __init__(self):
        self.status = "idle"
        self.progress = {
            "total": 0,
            "valid": 0,
            "invalid": 0,
            "deleted": 0,
            "processed": 0
        }
        self.started_at = None
        self.completed_at = None
        self.error = None
        
        # Список доменов, которые НЕ будут проверяться (agency.kg исключен)
        self.excluded_domains = ['agency.kg']
        
    def _get_db(self) -> Session:
        """Получить сессию БД"""
        return SessionLocal()
    
    async def check_url_status_async(self, session: aiohttp.ClientSession, url: str) -> tuple:
        """Асинхронная проверка статуса URL"""
        try:
            async with session.head(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=15)) as response:
                code = response.status
                if code == 200:
                    return url, "valid"
                elif code == 404:
                    return url, "invalid"
                elif code == 410:
                    return url, "invalid"
                elif code == 302:
                    return url, "valid"  # Редирект считаем валидным
                elif code in [403, 429, 500, 502, 503, 504]:
                    # Временные ошибки - считаем валидными
                    logger.debug(f"Временная ошибка {code} для {url}")
                    return url, "valid"
                else:
                    return url, "valid"  # Другие коды считаем валидными
        except asyncio.TimeoutError:
            logger.debug(f"Таймаут для {url}")
            return url, "valid"  # Таймаут считаем валидным
        except Exception as e:
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ['timeout', 'connection', 'dns', 'ssl']):
                logger.debug(f"Сетевая ошибка для {url}: {str(e)}")
                return url, "valid"  # Сетевые ошибки считаем валидными
            else:
                logger.debug(f"Ошибка проверки {url}: {str(e)}")
                return url, "invalid"
    
    def should_skip_domain(self, url: str) -> bool:
        """Проверяет, нужно ли пропустить домен"""
        try:
            domain = url.split('/')[2]
            return domain in self.excluded_domains
        except:
            return False
    
    async def validate_links_batch(self, urls: List[str], batch_size: int = None) -> List[tuple]:
        """Валидация ссылок батчами"""
        if batch_size is None:
            batch_size = get_link_validation_batch_size()
        results = []
        
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=50)) as session:
            # Разбиваем на батчи для контроля нагрузки
            for i in range(0, len(urls), batch_size):
                batch_urls = urls[i:i + batch_size]
                tasks = [self.check_url_status_async(session, url) for url in batch_urls]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                results.extend(batch_results)
                
                # Небольшая задержка между батчами
                if i + batch_size < len(urls):
                    await asyncio.sleep(1)
        
        return results
    
    async def start_validation(self) -> bool:
        """Запуск валидации ссылок"""
        if self.status == "running":
            logger.warning("Валидация ссылок уже выполняется")
            return False
        
        self.status = "running"
        self.started_at = datetime.now()
        self.error = None
        self.progress = {
            "total": 0,
            "valid": 0,
            "invalid": 0,
            "deleted": 0,
            "processed": 0
        }
        
        try:
            # Запускаем валидацию в фоновом режиме
            asyncio.create_task(self._run_validation())
            logger.info("🚀 Валидация ссылок запущена")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка запуска валидации ссылок: {e}")
            self.status = "error"
            self.error = str(e)
            self.completed_at = datetime.now()
            return False
    
    async def _run_validation(self):
        """Выполнение валидации ссылок"""
        db = None
        try:
            db = self._get_db()
            
            # Получаем все source_url из уникальных объявлений и их дубликатов
            query = text("""
                SELECT DISTINCT a.source_url 
                FROM ads a
                JOIN unique_ads ua ON a.id = ua.base_ad_id
                WHERE a.source_url IS NOT NULL
                UNION
                SELECT DISTINCT a.source_url 
                FROM ads a
                JOIN ad_duplicates ad ON a.id = ad.original_ad_id
                WHERE a.source_url IS NOT NULL
            """)
            
            result = db.execute(query)
            urls = [row[0] for row in result.fetchall()]
            
            # Фильтруем исключенные домены
            filtered_urls = [url for url in urls if not self.should_skip_domain(url)]
            
            self.progress["total"] = len(filtered_urls)
            logger.info(f"🔍 Найдено {len(filtered_urls)} ссылок для проверки (исключено {len(urls) - len(filtered_urls)} из agency.kg)")
            
            if not filtered_urls:
                self.status = "completed"
                self.completed_at = datetime.now()
                logger.info("✅ Нет ссылок для проверки")
                return
            
            # Проверяем ссылки батчами
            batch_size = get_link_validation_batch_size()
            invalid_urls = []
            
            for i in range(0, len(filtered_urls), batch_size):
                batch_urls = filtered_urls[i:i + batch_size]
                batch_results = await self.validate_links_batch(batch_urls, batch_size)
                
                for url, status in batch_results:
                    self.progress["processed"] += 1
                    
                    if status == "valid":
                        self.progress["valid"] += 1
                    else:
                        self.progress["invalid"] += 1
                        invalid_urls.append(url)
                
                # Логируем прогресс
                if self.progress["processed"] % 500 == 0:
                    logger.info(f"📊 Прогресс: {self.progress['processed']}/{self.progress['total']} "
                              f"(валидных: {self.progress['valid']}, невалидных: {self.progress['invalid']})")
            
            # Удаляем объявления с невалидными ссылками
            if invalid_urls:
                logger.info(f"🗑️ Удаляем {len(invalid_urls)} объявлений с невалидными ссылками...")
                deleted_count = await self._delete_invalid_ads(db, invalid_urls)
                self.progress["deleted"] = deleted_count
                logger.info(f"✅ Удалено {deleted_count} объявлений")
            
            self.status = "completed"
            self.completed_at = datetime.now()
            
            logger.info(f"✅ Валидация завершена. "
                       f"Всего: {self.progress['total']}, "
                       f"Валидных: {self.progress['valid']}, "
                       f"Невалидных: {self.progress['invalid']}, "
                       f"Удалено: {self.progress['deleted']}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка валидации ссылок: {e}")
            self.status = "error"
            self.error = str(e)
            self.completed_at = datetime.now()
        finally:
            if db:
                db.close()
    
    async def _delete_invalid_ads(self, db: Session, invalid_urls: List[str]) -> int:
        """Удаление объявлений с невалидными ссылками"""
        try:
            # Находим объявления с невалидными ссылками
            invalid_ads = db.query(db_models.DBAd).filter(
                db_models.DBAd.source_url.in_(invalid_urls)
            ).all()
            
            deleted_count = 0
            
            for ad in invalid_ads:
                try:
                    # Просто удаляем объявление - каскадное удаление в БД удалит связанные записи
                    db.delete(ad)
                    deleted_count += 1
                        
                except Exception as e:
                    logger.error(f"Ошибка удаления объявления {ad.id}: {e}")
                    continue
            
            db.commit()
            return deleted_count
            
        except Exception as e:
            logger.error(f"Ошибка удаления невалидных объявлений: {e}")
            db.rollback()
            return 0
    
    def get_status(self) -> Dict[str, Any]:
        """Получение статуса валидации"""
        return {
            "status": self.status,
            "progress": self.progress,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error
        }
    
    def stop_validation(self):
        """Остановка валидации"""
        if self.status == "running":
            self.status = "stopped"
            self.completed_at = datetime.now()
            logger.info("🛑 Валидация ссылок остановлена")

# Создаем глобальный экземпляр сервиса
link_validation_service = LinkValidationService() 