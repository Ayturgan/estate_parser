#!/usr/bin/env python3
"""
Сервис автоматизации парсинга и обработки данных
Управляет всеми процессами из одного места с гибкой настройкой
"""

import asyncio
import aiohttp
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional
import json

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AutomationScheduler:
    def __init__(self):
        # Настройки из переменных окружения
        self.api_base_url = os.getenv('API_BASE_URL', 'http://app:8000')
        self.pipeline_interval = int(os.getenv('PIPELINE_INTERVAL_HOURS', '3')) * 3600  # в секундах
        
        # Какие источники парсить (можно настроить через переменную окружения)
        scraping_sources = os.getenv('SCRAPING_SOURCES', 'house,lalafo,stroka')
        self.scraping_sources = [s.strip() for s in scraping_sources.split(',') if s.strip()]
        
        # Включение/выключение различных процессов
        self.enable_scraping = os.getenv('ENABLE_SCRAPING', 'true').lower() == 'true'
        self.enable_photo_processing = os.getenv('ENABLE_PHOTO_PROCESSING', 'true').lower() == 'true'
        self.enable_duplicate_processing = os.getenv('ENABLE_DUPLICATE_PROCESSING', 'true').lower() == 'true'
        self.enable_realtor_detection = os.getenv('ENABLE_REALTOR_DETECTION', 'true').lower() == 'true'
        self.enable_elasticsearch_reindex = os.getenv('ENABLE_ELASTICSEARCH_REINDEX', 'true').lower() == 'true'
        
        # Запуск пайплайна сразу при старте
        self.run_immediately_on_start = os.getenv('RUN_IMMEDIATELY_ON_START', 'true').lower() == 'true'
        
        # Настройки ожидания между этапами
        self.scraping_check_interval = int(os.getenv('SCRAPING_CHECK_INTERVAL_SECONDS', '60'))  # проверка статуса парсинга
        self.processing_check_interval = int(os.getenv('PROCESSING_CHECK_INTERVAL_SECONDS', '30'))  # проверка статуса обработки
        self.max_wait_time = int(os.getenv('MAX_WAIT_TIME_MINUTES', '120')) * 60  # максимальное время ожидания
        
        # Время последнего запуска пайплайна
        self.last_pipeline_run = 0
        
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        """Запуск основного цикла автоматизации"""
        logger.info("🚀 Запуск сервиса автоматизации")
        logger.info(f"📊 Настройки:")
        logger.info(f"  - API: {self.api_base_url}")
        logger.info(f"  - Запуск пайплайна каждые {self.pipeline_interval // 3600} часов")
        logger.info(f"  - Источники парсинга: {', '.join(self.scraping_sources)}")
        logger.info(f"  - Порядок выполнения: Парсинг → Обработка фото → Обработка дубликатов → Определение риэлторов → Индексация")
        
        enabled_steps = []
        if self.enable_scraping: enabled_steps.append("Парсинг")
        if self.enable_photo_processing: enabled_steps.append("Обработка фото")
        if self.enable_duplicate_processing: enabled_steps.append("Обработка дубликатов")
        if self.enable_realtor_detection: enabled_steps.append("Определение риэлторов")
        if self.enable_elasticsearch_reindex: enabled_steps.append("Индексация")
        logger.info(f"  - Включённые этапы: {' → '.join(enabled_steps)}")
        if self.run_immediately_on_start:
            logger.info("  - Запуск при старте: ДА")
        else:
            logger.info("  - Запуск при старте: НЕТ")
        
        self.session = aiohttp.ClientSession()
        
        try:
            # Ждём готовности API перед первым запуском
            if self.run_immediately_on_start:
                await self.wait_for_api_ready()
                logger.info("🚀 Запуск первого пайплайна сразу после старта")
                success = await self.run_full_pipeline()
                if success:
                    self.last_pipeline_run = asyncio.get_event_loop().time()
                    logger.info("✅ Первый пайплайн завершён успешно")
                    logger.info(f"📅 Следующий запуск через {self.pipeline_interval // 3600} часов")
                else:
                    logger.error("❌ Ошибки в первом пайплайне")
            else:
                logger.info(f"⏳ Первый запуск пайплайна через {self.pipeline_interval // 3600} часов")
            
            while True:
                current_time = asyncio.get_event_loop().time()
                
                # Проверяем, нужно ли запускать пайплайн по расписанию
                if current_time - self.last_pipeline_run >= self.pipeline_interval:
                    logger.info("🔄 Запуск пайплайна по расписанию")
                    success = await self.run_full_pipeline()
                    if success:
                        self.last_pipeline_run = current_time
                        logger.info("✅ Пайплайн завершён успешно")
                        logger.info(f"📅 Следующий запуск через {self.pipeline_interval // 3600} часов")
                    else:
                        logger.error("❌ Ошибки в пайплайне")
                
                # Ждём 60 секунд перед следующей проверкой
                await asyncio.sleep(60)
                
        except KeyboardInterrupt:
            logger.info("🛑 Остановка сервиса автоматизации")
        finally:
            if self.session:
                await self.session.close()

    async def run_full_pipeline(self) -> bool:
        """Запуск полного последовательного пайплайна обработки данных"""
        pipeline_success = True
        
        # Этап 1: Парсинг
        if self.enable_scraping:
            logger.info("🕷️ Этап 1/5: Запуск парсинга")
            scraping_success = await self.run_scraping_step()
            if not scraping_success:
                logger.error("❌ Парсинг завершился с ошибками")
                pipeline_success = False
            else:
                logger.info("✅ Парсинг завершён успешно")
        else:
            logger.info("⏭️ Парсинг отключён, пропускаем")
        
        # Этап 2: Обработка фотографий
        if self.enable_photo_processing:
            logger.info("📸 Этап 2/5: Запуск обработки фотографий")
            photo_success = await self.run_photo_processing_step()
            if not photo_success:
                logger.error("❌ Обработка фотографий завершилась с ошибками")
                pipeline_success = False
            else:
                logger.info("✅ Обработка фотографий завершена успешно")
        else:
            logger.info("⏭️ Обработка фотографий отключена, пропускаем")
        
        # Этап 3: Обработка дубликатов
        if self.enable_duplicate_processing:
            logger.info("🔄 Этап 3/5: Запуск обработки дубликатов")
            duplicates_success = await self.run_duplicate_processing_step()
            if not duplicates_success:
                logger.error("❌ Обработка дубликатов завершилась с ошибками")
                pipeline_success = False
            else:
                logger.info("✅ Обработка дубликатов завершена успешно")
        else:
            logger.info("⏭️ Обработка дубликатов отключена, пропускаем")
        
        # Этап 4: Определение риэлторов
        if self.enable_realtor_detection:
            logger.info("🏢 Этап 4/5: Запуск определения риэлторов")
            realtor_success = await self.run_realtor_detection_step()
            if not realtor_success:
                logger.error("❌ Определение риэлторов завершилось с ошибками")
                pipeline_success = False
            else:
                logger.info("✅ Определение риэлторов завершено успешно")
        else:
            logger.info("⏭️ Определение риэлторов отключено, пропускаем")
        
        # Этап 5: Переиндексация Elasticsearch
        if self.enable_elasticsearch_reindex:
            logger.info("🔍 Этап 5/5: Запуск переиндексации Elasticsearch")
            reindex_success = await self.run_elasticsearch_reindex_step()
            if not reindex_success:
                logger.error("❌ Переиндексация Elasticsearch завершилась с ошибками")
                pipeline_success = False
            else:
                logger.info("✅ Переиндексация Elasticsearch завершена успешно")
        else:
            logger.info("⏭️ Переиндексация Elasticsearch отключена, пропускаем")
        
        return pipeline_success

    async def run_scraping_step(self) -> bool:
        """Этап 1: Запуск и ожидание завершения парсинга"""
        success_count = 0
        total_sources = len(self.scraping_sources)
        job_ids = []
        
        # Запускаем парсинг по всем источникам
        for source in self.scraping_sources:
            logger.info(f"📡 Запуск парсинга для источника: {source}")
            job_id = await self.start_scraping_job(source)
            if job_id:
                job_ids.append((source, job_id))
                success_count += 1
                logger.info(f"✅ Парсинг {source} запущен (job_id: {job_id})")
            else:
                logger.error(f"❌ Ошибка запуска парсинга {source}")
        
        if success_count == 0:
            logger.error("❌ Не удалось запустить ни одного источника парсинга")
            return False
        
        logger.info(f"📊 Запущено {success_count} из {total_sources} источников")
        
        # Ожидаем завершения всех задач парсинга
        logger.info("⏳ Ожидание завершения всех задач парсинга...")
        all_completed = await self.wait_for_scraping_completion(job_ids)
        
        if all_completed:
            logger.info("✅ Все задачи парсинга завершены")
            return True
        else:
            logger.warning("⚠️ Некоторые задачи парсинга завершились с ошибками или превысили время ожидания")
            return False

    async def run_photo_processing_step(self) -> bool:
        """Этап 2: Запуск и ожидание завершения обработки фотографий"""
        logger.info("📸 Запуск обработки фотографий...")
        success = await self.api_request('POST', '/process/photos')
        if not success:
            return False
        
        # Ожидаем завершения обработки фотографий
        logger.info("⏳ Ожидание завершения обработки фотографий...")
        completed = await self.wait_for_processing_completion('/process/photos/status')
        return completed

    async def run_duplicate_processing_step(self) -> bool:
        """Этап 3: Запуск и ожидание завершения обработки дубликатов"""
        logger.info("🔄 Запуск обработки дубликатов...")
        success = await self.api_request('POST', '/process/duplicates')
        if not success:
            return False
        
        # Ожидаем завершения обработки дубликатов
        logger.info("⏳ Ожидание завершения обработки дубликатов...")
        completed = await self.wait_for_processing_completion('/process/duplicates/status')
        return completed

    async def run_realtor_detection_step(self) -> bool:
        """Этап 4: Запуск и ожидание завершения определения риэлторов"""
        logger.info("🏢 Запуск определения риэлторов...")
        success = await self.api_request('POST', '/process/realtors/detect')
        if not success:
            return False
        
        # Ожидаем завершения определения риэлторов
        logger.info("⏳ Ожидание завершения определения риэлторов...")
        completed = await self.wait_for_processing_completion('/process/realtors/status')
        return completed

    async def run_elasticsearch_reindex_step(self) -> bool:
        """Этап 5: Запуск переиндексации Elasticsearch"""
        logger.info("🔍 Запуск переиндексации Elasticsearch...")
        success = await self.api_request('POST', '/elasticsearch/reindex')
        if success:
            logger.info("✅ Переиндексация Elasticsearch запущена (выполняется в фоне)")
            # Переиндексация обычно выполняется в фоне, поэтому не ждём её завершения
            return True
        return False

    async def start_scraping_job(self, source: str) -> Optional[str]:
        """Запуск задачи парсинга и получение job_id"""
        url = f"{self.api_base_url}/scraping/start/{source}"
        
        try:
            async with self.session.post(url) as response:
                if response.status in [200, 201, 202]:
                    data = await response.json()
                    return data.get('job_id')
                else:
                    logger.error(f"❌ Ошибка запуска парсинга {source} - статус {response.status}")
                    return None
        except Exception as e:
            logger.error(f"❌ Ошибка запроса парсинга {source}: {e}")
            return None

    async def wait_for_scraping_completion(self, job_ids: List[tuple]) -> bool:
        """Ожидание завершения всех задач парсинга"""
        start_time = asyncio.get_event_loop().time()
        
        while True:
            current_time = asyncio.get_event_loop().time()
            if current_time - start_time > self.max_wait_time:
                logger.warning(f"⏰ Превышено максимальное время ожидания ({self.max_wait_time // 60} минут)")
                return False
            
            all_completed = True
            running_jobs = []
            
            for source, job_id in job_ids:
                status = await self.get_scraping_job_status(job_id)
                if status:
                    job_status = status.get('status', 'неизвестно')
                    if job_status in ['выполняется', 'ожидание']:
                        all_completed = False
                        running_jobs.append(f"{source}({job_status})")
                    elif job_status == 'ошибка':
                        logger.warning(f"⚠️ Парсинг {source} завершился с ошибкой")
                else:
                    logger.warning(f"⚠️ Не удалось получить статус задачи {source}")
            
            if all_completed:
                return True
            
            if running_jobs:
                logger.info(f"⏳ Ожидаем завершения: {', '.join(running_jobs)}")
            
            await asyncio.sleep(self.scraping_check_interval)

    async def wait_for_processing_completion(self, status_endpoint: str) -> bool:
        """Ожидание завершения обработки"""
        start_time = asyncio.get_event_loop().time()
        
        while True:
            current_time = asyncio.get_event_loop().time()
            if current_time - start_time > self.max_wait_time:
                logger.warning(f"⏰ Превышено максимальное время ожидания ({self.max_wait_time // 60} минут)")
                return False
            
            status = await self.get_processing_status(status_endpoint)
            if status:
                process_status = status.get('status', 'неизвестно')
                if process_status == 'running':
                    logger.info("⏳ Обработка продолжается...")
                elif process_status == 'completed':
                    return True
                elif process_status == 'error':
                    logger.error("❌ Обработка завершилась с ошибкой")
                    return False
                elif process_status == 'idle':
                    # Если статус idle, значит обработка уже завершена
                    return True
            
            await asyncio.sleep(self.processing_check_interval)

    async def get_scraping_job_status(self, job_id: str) -> Optional[Dict]:
        """Получение статуса задачи парсинга"""
        url = f"{self.api_base_url}/scraping/status/{job_id}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return None
        except Exception as e:
            logger.debug(f"Ошибка получения статуса задачи {job_id}: {e}")
            return None

    async def get_processing_status(self, endpoint: str) -> Optional[Dict]:
        """Получение статуса обработки"""
        url = f"{self.api_base_url}{endpoint}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return None
        except Exception as e:
            logger.debug(f"Ошибка получения статуса обработки: {e}")
            return None

    async def api_request(self, method: str, endpoint: str, **kwargs) -> bool:
        """Выполнение HTTP-запроса к API"""
        url = f"{self.api_base_url}{endpoint}"
        
        try:
            async with self.session.request(method, url, **kwargs) as response:
                if response.status in [200, 201, 202]:
                    logger.debug(f"✅ {method} {endpoint} - успешно")
                    return True
                else:
                    logger.error(f"❌ {method} {endpoint} - статус {response.status}")
                    text = await response.text()
                    logger.error(f"Ответ: {text[:200]}...")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Ошибка запроса {method} {endpoint}: {e}")
            return False

    async def wait_for_api_ready(self):
        """Ожидание готовности FastAPI сервера"""
        logger.info("⏳ Ожидание готовности FastAPI сервера...")
        max_attempts = 60  # Максимум 5 минут ожидания
        attempt = 0
        
        while attempt < max_attempts:
            try:
                async with self.session.get(f"{self.api_base_url}/status") as response:
                    if response.status == 200:
                        logger.info("✅ FastAPI сервер готов!")
                        return
            except Exception as e:
                logger.debug(f"API ещё не готов (попытка {attempt + 1}/{max_attempts}): {e}")
            
            attempt += 1
            await asyncio.sleep(5)  # Ждём 5 секунд между попытками
        
        logger.warning("⚠️ FastAPI сервер не отвечает, но продолжаем работу...")

    async def get_system_status(self) -> Dict:
        """Получение статуса системы"""
        try:
            async with self.session.get(f"{self.api_base_url}/status") as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            logger.error(f"Ошибка получения статуса: {e}")
        return {}

async def main():
    """Главная функция"""
    scheduler = AutomationScheduler()
    await scheduler.start()

if __name__ == "__main__":
    asyncio.run(main()) 