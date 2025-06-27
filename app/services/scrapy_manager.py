import asyncio
import uuid
import redis.asyncio as aioredis
import json
from typing import Dict, Optional, List
from datetime import datetime

SCRAPY_CONFIG_TO_SPIDER = {
    'stroka': 'generic_scraper',
    'house': 'generic_scraper',
    'lalafo': 'generic_api',
}

class ScrapyJobStatus:
    PENDING = 'ожидание'
    RUNNING = 'выполняется'
    FINISHED = 'завершено'
    FAILED = 'ошибка'
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
        job.update(kwargs)
        await self._save_job(job_id, job)

    async def _append_log(self, job_id: str, line: str):
        await self.redis.rpush(f'{self.log_prefix}{job_id}', line)

    async def get_log(self, job_id: str, limit: int = 100) -> List[str]:
        return await self.redis.lrange(f'{self.log_prefix}{job_id}', -limit, -1)

    async def start_job(self, config_name: str) -> str:
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
        return job_id

    async def stop_job(self, job_id: str):
        await self._update_job(job_id, status=ScrapyJobStatus.STOPPED, finished_at=datetime.utcnow().isoformat())

    async def get_status(self, job_id: str) -> Optional[dict]:
        return await self._get_job(job_id)

    async def get_all_jobs(self) -> List[dict]:
        jobs = await self.redis.hgetall(self.jobs_key)
        result = []
        for j in jobs.values():
            try:
                result.append(json.loads(j))
            except Exception:
                continue
        return result

    async def start_all(self) -> List[str]:
        job_ids = []
        for config in SCRAPY_CONFIG_TO_SPIDER:
            job_id = await self.start_job(config)
            job_ids.append(job_id)
        return job_ids 