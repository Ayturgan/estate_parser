import asyncio
import aiohttp
import logging
import uuid
import redis.asyncio as aioredis
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from app.core.config import REDIS_URL, get_enable_scraping

# Импортируем event_emitter для WebSocket событий
from app.services.event_emitter import event_emitter

logger = logging.getLogger(__name__)

SCRAPY_CONFIG_TO_SPIDER = {
    'stroka': 'generic_scraper',
    'house': 'generic_scraper',  # Используем обычный HTML спайдер для house
    'lalafo': 'generic_api',
    'agency': 'generic_show_more_simple',
    'an': 'generic_show_more_simple',
}


class ScrapyJobStatus:
    PENDING = 'ожидание'
    RUNNING = 'выполняется'
    FINISHED = 'завершено'
    FINISHED_WITH_PARSING_ERRORS = 'завершено с ошибками парсинга'
    FAILED = 'ошибка'
    FAILED_WITH_PARSING_ERRORS = 'ошибка парсинга'
    STOPPED = 'остановлено'

class ScrapyManager:
    def __init__(self, redis_url: str = None):
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        self.jobs_key = 'scrapy_jobs'
        self.log_prefix = 'scrapy_log:'

    async def _save_job(self, job_id: str, data: dict):
        await self.redis.hset(self.jobs_key, job_id, json.dumps(data, ensure_ascii=False))

    async def _get_job(self, job_id: str) -> Optional[dict]:
        raw = await self.redis.hget(self.jobs_key, job_id)
        if raw:
            return json.loads(raw)
        return None

    async def _update_job(self, job_id: str, **kwargs):
        job = await self._get_job(job_id)
        if not job:
            return
        
        old_status = job.get('status')
        job.update(kwargs)
        await self._save_job(job_id, job)
        
        # Отправляем WebSocket события при изменении статуса
        new_status = job.get('status')
        if old_status != new_status:
            if new_status == ScrapyJobStatus.RUNNING:
                await event_emitter.emit_scraping_progress(job_id, 0, {"status": "started"})
            elif new_status == ScrapyJobStatus.FINISHED:
                await event_emitter.emit_scraping_completed(job_id, job.get('config', 'unknown'), {"scraped_items": 0})
            elif new_status == ScrapyJobStatus.FINISHED_WITH_PARSING_ERRORS:
                await event_emitter.emit_scraping_error(job_id, job.get('config', 'unknown'), "Задача завершена с ошибками парсинга")
            elif new_status == ScrapyJobStatus.FAILED:
                await event_emitter.emit_scraping_error(job_id, job.get('config', 'unknown'), "Задача завершена с ошибкой")
            elif new_status == ScrapyJobStatus.FAILED_WITH_PARSING_ERRORS:
                await event_emitter.emit_scraping_error(job_id, job.get('config', 'unknown'), "Задача завершена с ошибкой парсинга")

    async def _append_log(self, job_id: str, line: str):
        await self.redis.rpush(f'{self.log_prefix}{job_id}', line)

    async def get_log(self, job_id: str, limit: int = 100) -> List[str]:
        return await self.redis.lrange(f'{self.log_prefix}{job_id}', -limit, -1)

    async def start_job(self, config_name: str) -> str:
        # Проверяем, включён ли парсинг в настройках
        if not get_enable_scraping():
            logger.warning(f"❌ Парсинг отключён в настройках. Задача {config_name} не будет запущена.")
            raise ValueError('Парсинг отключён в настройках системы')
        
        if config_name not in SCRAPY_CONFIG_TO_SPIDER:
            raise ValueError('Неизвестный конфиг')
        
        spider = SCRAPY_CONFIG_TO_SPIDER[config_name]
        job_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        job_data = {
            'id': job_id,
            'config': config_name,
            'spider': spider,
            'status': ScrapyJobStatus.PENDING,
            'created_at': now,
            'started_at': None,
            'finished_at': None,
            'returncode': None,
        }
        await self._save_job(job_id, job_data)
        await self.redis.lpush("scrapy_tasks", json.dumps({"job_id": job_id, "config": config_name, "spider": spider}, ensure_ascii=False))
        
        # Отправляем событие запуска парсинга
        await event_emitter.emit_scraping_started(job_id, config_name)
        
        return job_id

    async def stop_job(self, job_id: str):
        job = await self._get_job(job_id)
        await self._update_job(job_id, status=ScrapyJobStatus.STOPPED, finished_at=datetime.utcnow().isoformat())
        
        # Отправляем событие остановки парсинга
        if job:
            await event_emitter.emit_scraping_error(job_id, job.get('config', 'unknown'), 'Остановлен пользователем')

    async def get_status(self, job_id: str) -> Optional[dict]:
        return await self._get_job(job_id)

    async def get_all_jobs(self) -> List[dict]:
        try:
            jobs = await self.redis.hgetall(self.jobs_key)
            
            result = []
            for j in jobs.values():
                try:
                    result.append(json.loads(j))
                except Exception as e:
                    print(f"❌ Ошибка парсинга задачи: {e}")
                    continue
            
            return result
        except Exception as e:
            print(f"❌ Ошибка получения задач из Redis: {e}")
            return []

    async def start_all(self) -> List[str]:
        # Проверяем, включён ли парсинг в настройках
        if not get_enable_scraping():
            logger.warning("❌ Парсинг отключён в настройках. Задачи не будут запущены.")
            return []
        
        job_ids = []
        for config in SCRAPY_CONFIG_TO_SPIDER:
            try:
                job_id = await self.start_job(config)
                job_ids.append(job_id)
            except ValueError as e:
                logger.error(f"❌ Ошибка запуска задачи {config}: {e}")
                continue
        return job_ids

    async def stop_all_jobs(self):
        """Остановка всех активных задач"""
        try:
            jobs = await self.get_all_jobs()
            stopped_count = 0
            
            for job in jobs:
                if job.get('status') == ScrapyJobStatus.RUNNING or job.get('status') == ScrapyJobStatus.PENDING:
                    await self.stop_job(job['id'])
                    stopped_count += 1
            
            logger.info(f"Остановлено {stopped_count} задач парсинга")
            return stopped_count
        except Exception as e:
            logger.error(f"Ошибка остановки всех задач: {e}")
            raise 

# Создаем экземпляр ScrapyManager для экспорта
scrapy_manager = ScrapyManager(redis_url=REDIS_URL)