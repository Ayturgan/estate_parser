import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import aiohttp
from enum import Enum
from dotenv import load_dotenv
from app.core.config import (
    get_auto_mode, get_pipeline_interval_minutes, get_run_immediately_on_start,
    get_scraping_sources, get_enable_scraping, get_enable_photo_processing,
    get_enable_duplicate_processing, get_enable_realtor_detection,
    get_enable_elasticsearch_reindex
)
from app.services.scrapy_manager import ScrapyManager
from app.services.event_emitter import event_emitter
from app.services.websocket_manager import websocket_manager

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)

# Импортируем event_emitter для WebSocket событий
from app.services.event_emitter import event_emitter
from app.services.scrapy_manager import scrapy_manager
from app.services.websocket_manager import websocket_manager

class PipelineStatus(Enum):
    IDLE = "idle"
    RUNNING = "running" 
    COMPLETED = "completed"
    ERROR = "error"
    PAUSED = "paused"

class PipelineStage(Enum):
    SCRAPING = "scraping"
    PHOTO_PROCESSING = "photo_processing"
    DUPLICATE_PROCESSING = "duplicate_processing"
    REALTOR_DETECTION = "realtor_detection"
    ELASTICSEARCH_REINDEX = "elasticsearch_reindex"

def to_iso(dt):
    if isinstance(dt, str):
        return dt
    if dt is not None:
        return dt.isoformat()
    return None

class AutomationService:
    """Сервис автоматизации с управлением через веб-интерфейс"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.pipeline_status = PipelineStatus.IDLE
        self.current_stage: Optional[PipelineStage] = None
        self.last_run_start: Optional[datetime] = None
        self.last_run_end: Optional[datetime] = None
        self.next_run_scheduled: Optional[datetime] = None
        # is_auto_mode определяет автоматический режим (независимо от RUN_IMMEDIATELY_ON_START)
        # RUN_IMMEDIATELY_ON_START определяет только запуск при старте сервиса
        self.is_auto_mode = get_auto_mode()  # Получаем из БД
        self.scrapy_manager = scrapy_manager
        
        # Получаем интервал из БД
        self.interval_minutes = get_pipeline_interval_minutes()
        self.interval_hours = self.interval_minutes / 60.0
        
        self.stage_details = {
            PipelineStage.SCRAPING: {
                "name": "Парсинг сайтов",
                "status": "idle",
                "started_at": None,
                "completed_at": None,
                "error": None,
                "progress": {
                    "total": 0, 
                    "completed": 0, 
                    "failed": 0,
                    "new_ads": 0,
                    "processed_ads": 0,
                    "sources_active": 0,
                    "sources_completed": 0
                }
            },
            PipelineStage.PHOTO_PROCESSING: {
                "name": "Обработка фотографий", 
                "status": "idle",
                "started_at": None,
                "completed_at": None,
                "error": None,
                "progress": {
                    "processed": 0, 
                    "total": 0, 
                    "photos_downloaded": 0,
                    "photos_optimized": 0
                }
            },
            PipelineStage.DUPLICATE_PROCESSING: {
                "name": "Обработка дубликатов",
                "status": "idle", 
                "started_at": None,
                "completed_at": None,
                "error": None,
                "progress": {
                    "processed": 0, 
                    "remaining": 0, 
                    "duplicates_found": 0,
                    "groups_created": 0
                }
            },
            PipelineStage.REALTOR_DETECTION: {
                "name": "Определение риэлторов",
                "status": "idle",
                "started_at": None, 
                "completed_at": None,
                "error": None,
                "progress": {
                    "detected": 0, 
                    "processed": 0,
                    "total": 0
                }
            },
            PipelineStage.ELASTICSEARCH_REINDEX: {
                "name": "Переиндексация поиска",
                "status": "idle",
                "started_at": None,
                "completed_at": None, 
                "error": None,
                "progress": {
                    "indexed": 0, 
                    "total": 0
                }
            }
        }
        
        self.enabled_stages = {
            PipelineStage.SCRAPING: get_enable_scraping(),
            PipelineStage.PHOTO_PROCESSING: get_enable_photo_processing(), 
            PipelineStage.DUPLICATE_PROCESSING: get_enable_duplicate_processing(),
            PipelineStage.REALTOR_DETECTION: get_enable_realtor_detection(),
            PipelineStage.ELASTICSEARCH_REINDEX: get_enable_elasticsearch_reindex()
        }
        
        self.scraping_sources = get_scraping_sources()
        self._background_task: Optional[asyncio.Task] = None
        self.initial_stats = None
        self._last_new_ads = 0
        self._last_processed_ads = 0
        self._last_duplicates_found = 0
        self._last_realtors_found = 0
        
    async def start_service(self):
        """Запуск сервиса автоматизации"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        if not self._background_task:
            self._background_task = asyncio.create_task(self._background_scheduler())
            
        if self.is_auto_mode and self.pipeline_status == PipelineStatus.IDLE:
            run_immediately = get_run_immediately_on_start()
            if run_immediately:
                logger.info("🚀 Запуск пайплайна при старте сервиса (RUN_IMMEDIATELY_ON_START=true)")
                asyncio.create_task(self._delayed_start())
            
        logger.info("🚀 Сервис автоматизации запущен")
    
    async def stop_service(self):
        """Остановка сервиса автоматизации"""
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            self._background_task = None
            
        if self.session:
            await self.session.close()
            self.session = None
            
        logger.info("🛑 Сервис автоматизации остановлен")
    
    async def _delayed_start(self):
        """Отложенный запуск пайплайна при старте сервиса"""
        try:
            await asyncio.sleep(10)
            if self.pipeline_status == PipelineStatus.IDLE:
                logger.info("⚡ Запуск немедленного пайплайна (RUN_IMMEDIATELY_ON_START)")
                await self.start_pipeline(manual=False)
                
        except Exception as e:
            logger.error(f"Ошибка отложенного запуска: {e}")

    async def _background_scheduler(self):
        """Фоновый планировщик для автоматического режима"""
        while True:
            try:
                if (self.is_auto_mode and 
                    self.pipeline_status in [PipelineStatus.IDLE, PipelineStatus.COMPLETED] and
                    self.next_run_scheduled and
                    datetime.now() >= self.next_run_scheduled):
                    
                    logger.info("⏰ Запуск автоматического пайплайна по расписанию")
                    await self.start_pipeline(manual=False)
                
                # Если автоматический режим включен, но нет запланированного запуска, планируем его
                elif (self.is_auto_mode and 
                      self.pipeline_status in [PipelineStatus.IDLE, PipelineStatus.COMPLETED] and
                      not self.next_run_scheduled):
                    
                    self.next_run_scheduled = datetime.now() + timedelta(minutes=self.interval_minutes)
                    logger.info(f"⏰ Планируем следующий автоматический запуск на {self.next_run_scheduled.strftime('%H:%M:%S')}")
                
                # Обновляем статистику каждые 30 секунд для получения актуальных данных
                if websocket_manager.is_anyone_online():
                    await self._update_stats()
                    await event_emitter.emit_automation_status(self.get_status())
                
                await asyncio.sleep(30)  # Уменьшаем интервал для более частого обновления
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в планировщике: {e}")
                await asyncio.sleep(30)
    
    async def start_pipeline(self, manual: bool = False) -> bool:
        """Запуск полного пайплайна"""
        if self.pipeline_status == PipelineStatus.RUNNING:
            return False
        
        # Отправляем событие запуска пайплайна
        await event_emitter.emit_automation_status(self.get_status())
        self.pipeline_status = PipelineStatus.RUNNING
        self.last_run_start = datetime.now()
        self.last_run_end = None
        
        
        logger.info(f"🚀 Запуск пайплайна ({'ручной' if manual else 'автоматический'})")
        
        try:
            success = True
            for stage in PipelineStage:
                if not self.enabled_stages.get(stage, False):
                    continue
                    
                self.current_stage = stage
                stage_success = await self._execute_stage(stage)
                
                if not stage_success:
                    success = False
                    break
            
            self.pipeline_status = PipelineStatus.COMPLETED if success else PipelineStatus.ERROR
            self.current_stage = None
            self.last_run_end = datetime.now()
            
            # Отправляем событие завершения пайплайна
            await event_emitter.emit_automation_status(self.get_status())
            
            # Отправляем специальное событие завершения пайплайна
            if success:
                await event_emitter.emit_automation_completed()
            else:
                await event_emitter.emit_automation_error("Пайплайн завершился с ошибками")
            
            scraping_progress = self.stage_details[PipelineStage.SCRAPING]["progress"]
            duplicate_progress = self.stage_details[PipelineStage.DUPLICATE_PROCESSING]["progress"]
            realtor_progress = self.stage_details[PipelineStage.REALTOR_DETECTION]["progress"]
            
            self._last_new_ads = scraping_progress.get("new_ads", 0)
            self._last_processed_ads = scraping_progress.get("processed_ads", 0)  
            self._last_duplicates_found = duplicate_progress.get("duplicates_found", 0)
            self._last_realtors_found = realtor_progress.get("detected", 0)
            if not manual and self.is_auto_mode:
                self.next_run_scheduled = datetime.now() + timedelta(minutes=self.interval_minutes)
                logger.info(f"⏰ Следующий автоматический запуск запланирован на {self.next_run_scheduled.strftime('%H:%M:%S')}")
            
            logger.info(f"✅ Пайплайн завершен {'успешно' if success else 'с ошибками'}")
            return success
            
        except Exception as e:
            logger.error(f"Ошибка выполнения пайплайна: {e}")
            self.pipeline_status = PipelineStatus.ERROR
            self.current_stage = None
            return False
    
    async def _execute_stage(self, stage: PipelineStage) -> bool:
        """Выполнение конкретного этапа пайплайна"""
        stage_info = self.stage_details[stage]
        stage_info["status"] = "running"
        stage_info["started_at"] = datetime.now()
        stage_info["error"] = None
        
        # Отправляем событие начала этапа
        await event_emitter.emit_automation_progress(stage.value, 0, {"stage": stage.value, "status": "started"})
        
        try:
            if stage == PipelineStage.SCRAPING:
                success = await self._execute_scraping()
            elif stage == PipelineStage.PHOTO_PROCESSING:
                success = await self._execute_photo_processing()
            elif stage == PipelineStage.DUPLICATE_PROCESSING:
                success = await self._execute_duplicate_processing()
            elif stage == PipelineStage.REALTOR_DETECTION:
                success = await self._execute_realtor_detection()
            elif stage == PipelineStage.ELASTICSEARCH_REINDEX:
                success = await self._execute_elasticsearch_reindex()
            else:
                success = False
                
            stage_info["status"] = "completed" if success else "error"
            stage_info["completed_at"] = datetime.now()
            
            # Отправляем событие завершения этапа
            progress = 100 if success else 0
            await event_emitter.emit_automation_progress(stage.value, progress, {"stage": stage.value, "status": "completed" if success else "error"})
            
            return success
            
        except Exception as e:
            logger.error(f"Ошибка этапа {stage.value}: {e}")
            self.stage_details[stage]["status"] = "error"
            self.stage_details[stage]["error"] = str(e)
            self.stage_details[stage]["completed_at"] = datetime.now()
            return False
    
    async def _execute_scraping(self) -> bool:
        """Выполнение парсинга всех источников"""
        # Проверяем, включён ли парсинг в настройках
        if not self.enabled_stages[PipelineStage.SCRAPING]:
            logger.info("🚫 Парсинг отключён в настройках, пропускаем этап")
            self.stage_details[PipelineStage.SCRAPING]["status"] = "skipped"
            self.stage_details[PipelineStage.SCRAPING]["started_at"] = datetime.now().isoformat()
            self.stage_details[PipelineStage.SCRAPING]["completed_at"] = datetime.now().isoformat()
            return True
        
        logger.info("🚀 Запуск парсинга всех источников...")
        
        # Обновляем статус
        self.stage_details[PipelineStage.SCRAPING]["status"] = "running"
        self.stage_details[PipelineStage.SCRAPING]["started_at"] = datetime.now().isoformat()
        
        progress = self.stage_details[PipelineStage.SCRAPING]["progress"]
        progress["total"] = len(self.scraping_sources)
        progress["completed"] = 0
        progress["failed"] = 0
        progress["sources_active"] = 0
        progress["sources_completed"] = 0
        progress["new_ads"] = 0
        progress["processed_ads"] = 0
        
        job_ids = []
        
        for source in self.scraping_sources:
            try:
                async with self.session.post(f"{self.api_base_url}/api/scraping/start/{source}") as response:
                    if response.status in [200, 201, 202]:
                        data = await response.json()
                        job_id = data.get('job_id')
                        if job_id:
                            job_ids.append((source, job_id))
                            progress["sources_active"] += 1
                            logger.info(f"Парсинг {source} запущен (job_id: {job_id})")
                            # Убираем дублирующее уведомление - ScrapyManager уже отправляет событие
                    else:
                        progress["failed"] += 1
                        error_text = await response.text()
                        logger.error(f"Ошибка запуска парсинга {source}: {response.status} - {error_text}")
            except Exception as e:
                progress["failed"] += 1
                logger.error(f"Ошибка запроса парсинга {source}: {e}")
        
        if not job_ids:
            return False
        return await self._wait_for_scraping_completion(job_ids)
    
    async def _wait_for_scraping_completion(self, job_ids: list) -> bool:
        """Ожидание завершения парсинга"""
        progress = self.stage_details[PipelineStage.SCRAPING]["progress"]
        completed_jobs = set()
        
        while len(completed_jobs) < len(job_ids):
            await self._update_stats()
            
            for source, job_id in job_ids:
                if job_id in completed_jobs:
                    continue
                    
                try:
                    async with self.session.get(f"{self.api_base_url}/api/scraping/status/{job_id}") as response:
                        if response.status == 200:
                            data = await response.json()
                            status = data.get('status', 'unknown')
                            
                            if status in ['завершено', 'ошибка', 'остановлено']:
                                completed_jobs.add(job_id)
                                progress["sources_active"] -= 1
                                progress["sources_completed"] += 1
                                
                                if status == 'завершено':
                                    progress["completed"] += 1
                                    logger.info(f"Парсинг {source}: завершен успешно")
                                else:
                                    progress["failed"] += 1
                                    logger.info(f"Парсинг {source}: завершен с ошибкой ({status})")
                            elif status == 'выполняется':
                                logger.info(f"Парсинг {source}: выполняется...")
                                
                except Exception as e:
                    logger.error(f"Ошибка проверки статуса {source}: {e}")
            
            if len(completed_jobs) < len(job_ids):
                await asyncio.sleep(30)
        await self._update_stats()
        return progress["failed"] == 0
    
    async def _wait_for_process_completion(self, process_type: str) -> bool:
        """Ожидание завершения фоновых процессов"""
        max_wait_time = 3600  
        check_interval = 30  
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            try:
                endpoint_map = {
                    "photos": "/api/process/photos/status",
                    "duplicates": "/api/process/duplicates/status", 
                    "realtors": "/api/process/realtors/status",
                    "elasticsearch": "/api/elasticsearch/health"
                }
                
                endpoint = endpoint_map.get(process_type)
                if not endpoint:
                    logger.error(f"Неизвестный тип процесса: {process_type}")
                    return False
                
                async with self.session.get(f"{self.api_base_url}{endpoint}") as response:
                    if response.status == 200:
                        data = await response.json()
                        if process_type == "photos":
                            status = data.get('status', 'unknown')
                            if status == 'completed':
                                logger.info(f"Обработка фотографий завершена")
                                return True
                            elif status == 'running':
                                logger.info(f"Обработка фотографий выполняется...")
                            elif status == 'idle':
                                # Если статус idle, значит процесс завершен
                                logger.info(f"Обработка фотографий завершена (статус: idle)")
                                return True
                            elif status == 'error':
                                logger.error(f"Ошибка обработки фотографий")
                                return False
                                
                        elif process_type == "duplicates":
                            status = data.get('status', 'unknown')
                            if status == 'completed':
                                logger.info(f"Обработка дубликатов завершена")
                                return True
                            elif status == 'running':
                                logger.info(f"Обработка дубликатов выполняется...")
                            elif status == 'idle':
                                # Если статус idle, значит процесс завершен
                                logger.info(f"Обработка дубликатов завершена (статус: idle)")
                                return True
                            elif status == 'error':
                                logger.error(f"Ошибка обработки дубликатов")
                                return False
                                
                        elif process_type == "realtors":
                            status = data.get('status', 'unknown')
                            if status == 'completed':
                                logger.info(f"Определение риэлторов завершено")
                                return True
                            elif status == 'running':
                                logger.info(f"Определение риэлторов выполняется...")
                            elif status == 'idle':
                                # Если статус idle, значит процесс завершен
                                logger.info(f"Определение риэлторов завершено (статус: idle)")
                                return True
                            elif status == 'error':
                                logger.error(f"Ошибка определения риэлторов")
                                return False
                                
                        elif process_type == "elasticsearch":
                            logger.info(f"Переиндексация завершена")
                            return True
                            
                        logger.info(f"{process_type} еще выполняется, ожидание...")
                        
                    else:
                        logger.warning(f"Не удалось проверить статус {process_type}")
                        
            except Exception as e:
                logger.error(f"Ошибка проверки статуса {process_type}: {e}")
            
            await asyncio.sleep(check_interval)
            elapsed_time += check_interval
        
        logger.warning(f"Превышено время ожидания для {process_type}")
        return False
    
    async def _execute_photo_processing(self) -> bool:
        """Выполнение обработки фотографий"""
        try:
            async with self.session.post(f"{self.api_base_url}/api/process/photos") as response:
                if response.status not in [200, 201, 202]:
                    return False
                    
            logger.info("Обработка фотографий запущена, ожидание завершения...")
            return await self._wait_for_process_completion("photos")
        except Exception as e:
            logger.error(f"Ошибка запуска обработки фото: {e}")
            return False
    
    async def _execute_duplicate_processing(self) -> bool:
        """Выполнение обработки дубликатов"""
        try:
            async with self.session.post(f"{self.api_base_url}/api/process/duplicates") as response:
                if response.status not in [200, 201, 202]:
                    return False
                    
            logger.info("Обработка дубликатов запущена, ожидание завершения...")
            return await self._wait_for_process_completion("duplicates")
        except Exception as e:
            logger.error(f"Ошибка запуска обработки дубликатов: {e}")
            return False
    
    async def _execute_realtor_detection(self) -> bool:
        """Выполнение определения риэлторов"""
        try:
            async with self.session.post(f"{self.api_base_url}/api/process/realtors/detect") as response:
                if response.status not in [200, 201, 202]:
                    return False
                    
            logger.info("Определение риэлторов запущено, ожидание завершения...")
            return await self._wait_for_process_completion("realtors")
        except Exception as e:
            logger.error(f"Ошибка запуска определения риэлторов: {e}")
            return False
    
    async def _execute_elasticsearch_reindex(self) -> bool:
        """Выполнение переиндексации"""
        try:
            async with self.session.post(f"{self.api_base_url}/api/elasticsearch/reindex") as response:
                if response.status not in [200, 201, 202]:
                    return False
                    
            logger.info("Переиндексация запущена, ожидание завершения...")
            return await self._wait_for_process_completion("elasticsearch")
        except Exception as e:
            logger.error(f"Ошибка запуска переиндексации: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Получение полного статуса автоматизации"""
        scraping_progress = self.stage_details[PipelineStage.SCRAPING]["progress"]
        duplicate_progress = self.stage_details[PipelineStage.DUPLICATE_PROCESSING]["progress"]
        realtor_progress = self.stage_details[PipelineStage.REALTOR_DETECTION]["progress"]
        
        # Всегда используем актуальные данные о новых объявлениях
        stats = {
            "new_ads": scraping_progress.get("new_ads", 0),
            "processed_ads": scraping_progress.get("processed_ads", 0),
            "duplicates_found": duplicate_progress.get("duplicates_found", 0),
            "realtors_found": realtor_progress.get("detected", 0)
        }
        
        return {
            "pipeline_status": self.pipeline_status.value,
            "current_stage": self.current_stage.value if self.current_stage else None,
            "is_auto_mode": self.is_auto_mode,
            "interval_hours": self.interval_hours,
            "interval_minutes": self.interval_minutes,
            "scraping_sources": self.scraping_sources,
            "last_run_start": self.last_run_start.isoformat() if self.last_run_start else None,
            "last_run_end": self.last_run_end.isoformat() if self.last_run_end else None,
            "next_run_scheduled": self.next_run_scheduled.isoformat() if self.next_run_scheduled else None,
            "stats": stats,
            "enabled_stages": {stage.value: enabled for stage, enabled in self.enabled_stages.items()},
            "stage_details": {
                stage.value: {
                    "name": details["name"],
                    "status": details["status"],
                    "started_at": to_iso(details["started_at"]),
                    "completed_at": to_iso(details["completed_at"]),
                    "error": details["error"],
                    "progress": details["progress"],
                }
                for stage, details in self.stage_details.items()
            }
        }
    
    def set_auto_mode(self, enabled: bool):
        """Включение/выключение автоматического режима"""
        self.is_auto_mode = enabled
        if enabled and self.pipeline_status in [PipelineStatus.IDLE, PipelineStatus.COMPLETED]:
            # Если включаем автоматический режим и пайплайн не запущен, планируем следующий запуск
            self.next_run_scheduled = datetime.now() + timedelta(minutes=self.interval_minutes)
            logger.info(f"🔄 Автоматический режим включен. Следующий запуск: {self.next_run_scheduled.strftime('%H:%M:%S')}")
        elif not enabled:
            # Если выключаем автоматический режим, отменяем планирование
            self.next_run_scheduled = None
            logger.info("🔄 Автоматический режим отключен")
    
    def get_auto_mode(self) -> bool:
        """Получение текущего состояния автоматического режима"""
        return self.is_auto_mode
    
    def reload_settings(self):
        """Принудительно перечитать настройки из БД"""
        self.is_auto_mode = get_auto_mode()
        self.interval_minutes = get_pipeline_interval_minutes()
        self.interval_hours = self.interval_minutes / 60.0
        self.enabled_stages = {
            PipelineStage.SCRAPING: get_enable_scraping(),
            PipelineStage.PHOTO_PROCESSING: get_enable_photo_processing(),
            PipelineStage.DUPLICATE_PROCESSING: get_enable_duplicate_processing(),
            PipelineStage.REALTOR_DETECTION: get_enable_realtor_detection(),
            PipelineStage.ELASTICSEARCH_REINDEX: get_enable_elasticsearch_reindex()
        }
        self.scraping_sources = get_scraping_sources()
        
        # Если автоматический режим включен и пайплайн не запущен, планируем следующий запуск
        if (self.is_auto_mode and 
            self.pipeline_status in [PipelineStatus.IDLE, PipelineStatus.COMPLETED] and
            not self.next_run_scheduled):
            self.next_run_scheduled = datetime.now() + timedelta(minutes=self.interval_minutes)
            logger.info(f"🔄 Настройки перезагружены. Следующий запуск запланирован на {self.next_run_scheduled.strftime('%H:%M:%S')}")
        elif not self.is_auto_mode:
            # Если автоматический режим отключен, отменяем планирование
            self.next_run_scheduled = None
            logger.info("🔄 Автоматический режим отключен при перезагрузке настроек")
        
        # Отправляем обновление статуса через WebSocket
        try:
            asyncio.create_task(event_emitter.emit_automation_status(self.get_status()))
        except Exception as e:
            logger.error(f"Ошибка отправки обновления статуса после перезагрузки настроек: {e}")
    
    
    def pause_pipeline(self):
        """Приостановка пайплайна"""
        if self.pipeline_status == PipelineStatus.RUNNING:
            self.pipeline_status = PipelineStatus.PAUSED
            logger.info("⏸️ Пайплайн приостановлен")
    
    def resume_pipeline(self):
        """Возобновление пайплайна"""
        if self.pipeline_status == PipelineStatus.PAUSED:
            self.pipeline_status = PipelineStatus.RUNNING
            logger.info("▶️ Пайплайн возобновлен")
            # Перезапускаем фоновую задачу, если ее нет
            if not self._background_task or self._background_task.done():
                self._background_task = asyncio.create_task(self._run_pipeline_stages())

    async def stop_pipeline(self):
        """Остановка пайплайна и всех активных задач парсинга"""
        if self.pipeline_status != PipelineStatus.RUNNING:
            logger.warning("Пайплайн не запущен, нечего останавливать.")
            return

        logger.info("🛑 Остановка пайплайна...")
        
        # 1. Отменяем основную фоновую задачу пайплайна
        if self._background_task and not self._background_task.done():
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                logger.info("Фоновая задача пайплайна успешно отменена.")
            self._background_task = None

        # 2. Останавливаем все активные задачи парсинга через ScrapyManager
        try:
            active_jobs = await self.scrapy_manager.get_all_jobs()
            running_jobs = [job for job in active_jobs if job.get('status') == 'выполняется']
            
            if running_jobs:
                logger.info(f"Найдено {len(running_jobs)} активных задач парсинга. Отправка команды на остановку...")
                for job in running_jobs:
                    job_id = job.get('id')
                    if job_id:
                        await self.scrapy_manager.stop_job(job_id)
                        logger.info(f"  - Команда на остановку отправлена для задачи {job_id} ({job.get('config')})")
            else:
                logger.info("Активных задач парсинга не найдено.")

        except Exception as e:
            logger.error(f"Ошибка при остановке задач парсинга: {e}")

        # 3. Обновляем статус пайплайна и сбрасываем этапы
        self.pipeline_status = PipelineStatus.IDLE
        self.current_stage = None
        
        for stage in self.stage_details:
            self.stage_details[stage]["status"] = "idle"
            self.stage_details[stage]["error"] = None
            
        logger.info("✅ Пайплайн и все связанные задачи успешно остановлены.")

        # 4. Планируем следующий запуск, если включен автоматический режим
        if self.is_auto_mode:
            self.next_run_scheduled = datetime.now() + timedelta(minutes=self.interval_minutes)
            logger.info(f"Следующий запуск запланирован на {self.next_run_scheduled.strftime('%Y-%m-%d %H:%M:%S')}")

        # 5. Отправляем финальное обновление статуса через WebSocket
        await self.update_stage_status()
    
    async def _update_stats(self):
        """Обновление статистики системы"""
        try:
            async with self.session.get(f"{self.api_base_url}/api/stats") as response:
                if response.status == 200:
                    current_stats = await response.json()
                    
                    if self.initial_stats is None:
                        self.initial_stats = current_stats.copy()
                    
                    if self.current_stage == PipelineStage.SCRAPING:
                        progress = self.stage_details[PipelineStage.SCRAPING]["progress"]
                        progress["new_ads"] = current_stats.get("total_original_ads", 0) - self.initial_stats.get("total_original_ads", 0)
                        progress["processed_ads"] = current_stats.get("total_unique_ads", 0) - self.initial_stats.get("total_unique_ads", 0)
                        
                    return current_stats
        except Exception as e:
            logger.error(f"Ошибка обновления статистики: {e}")
        return None

    async def update_stage_status(self):
        """Обновление статуса всех этапов в реальном времени"""
        if not self.session:
            return
            
        try:
            # Проверяем все статусы только если есть активные WebSocket соединения
            if websocket_manager.is_anyone_online():
                await self._update_duplicates_status()
                await self._update_photos_status()
                await self._update_realtors_status()
                await self._update_scraping_status()
                
                # Обновляем статистику более часто для получения актуальных данных
                await self._update_stats()
            else:
                # Если пользователи офлайн, сбрасываем все статусы в idle
                for stage_enum in [PipelineStage.DUPLICATE_PROCESSING, PipelineStage.PHOTO_PROCESSING, PipelineStage.REALTOR_DETECTION]:
                    stage = self.stage_details[stage_enum]
                    if stage["status"] == "running":
                        stage["status"] = "idle"
                        stage["started_at"] = None
                        stage["completed_at"] = None
                        stage["error"] = None
                
                # Для scraping оставляем как есть, так как это может быть фоновый процесс
            
            # Отправляем обновленный статус через WebSocket
            await event_emitter.emit_automation_status(self.get_status())
            
        except Exception as e:
            logger.error(f"Ошибка обновления статуса этапов: {e}")
    
    async def _update_duplicates_status(self):
        """Обновление статуса обработки дубликатов"""
        try:
            async with self.session.get(f"{self.api_base_url}/api/process/duplicates/status") as response:
                if response.status == 200:
                    data = await response.json()
                    stage = self.stage_details[PipelineStage.DUPLICATE_PROCESSING]
                    status = data.get('status', 'idle')
                    
                    if status == 'running':
                        stage["status"] = "running"
                        if not stage["started_at"]:
                            stage["started_at"] = datetime.now()
                        progress = data.get('progress', {})
                        if progress:
                            stage["progress"].update(progress)
                            
                    elif status == 'completed':
                        stage["status"] = "completed"
                        if not stage["completed_at"]:
                            stage["completed_at"] = datetime.now()
                        last_completed = data.get('last_completed')
                        if last_completed:
                            try:
                                from dateutil import parser
                                completed_time = parser.parse(last_completed)
                                if (datetime.now(completed_time.tzinfo) - completed_time).total_seconds() > 10:
                                    stage["status"] = "idle"
                                    stage["started_at"] = None
                                    stage["completed_at"] = None
                            except:
                                pass
                                
                    elif status == 'idle':
                        stage["status"] = "idle"
                        stage["started_at"] = None
                        stage["completed_at"] = None
                        
                    elif status == 'error':
                        stage["status"] = "error"
                        stage["error"] = data.get('error', 'Произошла ошибка')
                        stage["completed_at"] = datetime.now()
        except Exception as e:
            # Логируем ошибку только если есть активные соединения
            if websocket_manager.is_anyone_online():
                logger.error(f"❌ Ошибка проверки статуса дубликатов: {e}")
            else:
                logger.debug(f"Не удалось обновить статус дубликатов (пользователи офлайн): {e}")
    
    async def _update_photos_status(self):
        """Обновление статуса обработки фотографий"""
        try:
            async with self.session.get(f"{self.api_base_url}/api/process/photos/status") as response:
                if response.status == 200:
                    data = await response.json()
                    stage = self.stage_details[PipelineStage.PHOTO_PROCESSING]
                    status = data.get('status', 'idle')
                    
                    if status == 'running':
                        stage["status"] = "running"
                        if not stage["started_at"]:
                            stage["started_at"] = datetime.now()
                        progress = data.get('progress', {})
                        if progress:
                            stage["progress"].update(progress)
                            
                    elif status == 'completed':
                        stage["status"] = "completed"
                        if not stage["completed_at"]:
                            stage["completed_at"] = datetime.now()
                        last_completed = data.get('last_completed')
                        if last_completed:
                            try:
                                from dateutil import parser
                                completed_time = parser.parse(last_completed)
                                if (datetime.now(completed_time.tzinfo) - completed_time).total_seconds() > 10:
                                    stage["status"] = "idle"
                                    stage["started_at"] = None
                                    stage["completed_at"] = None
                            except:
                                pass
                                
                    elif status == 'idle':
                        stage["status"] = "idle"
                        stage["started_at"] = None
                        stage["completed_at"] = None
                        
                    elif status == 'error':
                        stage["status"] = "error"
                        stage["error"] = data.get('error', 'Произошла ошибка')
                        stage["completed_at"] = datetime.now()
        except Exception as e:
            # Логируем ошибку только если есть активные соединения
            if websocket_manager.is_anyone_online():
                logger.error(f"❌ Ошибка проверки статуса фотографий: {e}")
            else:
                logger.debug(f"Не удалось обновить статус фотографий (пользователи офлайн): {e}")
    
    async def _update_realtors_status(self):
        """Обновление статуса определения риэлторов"""
        try:
            async with self.session.get(f"{self.api_base_url}/api/process/realtors/status") as response:
                if response.status == 200:
                    data = await response.json()
                    stage = self.stage_details[PipelineStage.REALTOR_DETECTION]
                    status = data.get('status', 'idle')
                    
                    if status == 'running':
                        stage["status"] = "running"
                        if not stage["started_at"]:
                            stage["started_at"] = datetime.now()
                        progress = data.get('progress', {})
                        if progress:
                            stage["progress"].update(progress)
                            
                    elif status == 'completed':
                        stage["status"] = "completed"
                        if not stage["completed_at"]:
                            stage["completed_at"] = datetime.now()
                        last_completed = data.get('last_completed')
                        if last_completed:
                            try:
                                from dateutil import parser
                                completed_time = parser.parse(last_completed)
                                if (datetime.now(completed_time.tzinfo) - completed_time).total_seconds() > 10:
                                    stage["status"] = "idle"
                                    stage["started_at"] = None
                                    stage["completed_at"] = None
                            except:
                                pass
                                
                    elif status == 'idle':
                        stage["status"] = "idle"
                        stage["started_at"] = None
                        stage["completed_at"] = None
                        
                    elif status == 'error':
                        stage["status"] = "error"
                        stage["error"] = data.get('error', 'Произошла ошибка')
                        stage["completed_at"] = datetime.now()
        except Exception as e:
            # Логируем ошибку только если есть активные соединения
            if websocket_manager.is_anyone_online():
                logger.error(f"❌ Ошибка проверки статуса realtors: {e}")
            else:
                logger.debug(f"Не удалось обновить статус риэлторов (пользователи офлайн): {e}")
    
    async def _update_scraping_status(self):
        """Обновление статуса парсинга"""
        try:
            async with self.session.get(f"{self.api_base_url}/api/scraping/jobs") as response:
                if response.status == 200:
                    jobs = await response.json()
                    stage = self.stage_details[PipelineStage.SCRAPING]
                    running_jobs = [job for job in jobs if job.get('status') == 'выполняется']
                    
                    if running_jobs:
                        stage["status"] = "running"
                        if not stage["started_at"]:
                            stage["started_at"] = datetime.now()
                        progress = stage["progress"]
                        progress["sources_active"] = len(running_jobs)
                        progress["total"] = len(self.scraping_sources)
                        completed_sources = 0
                        for source in self.scraping_sources:
                            source_jobs = [j for j in jobs if j.get('config') == source]
                            if source_jobs:
                                latest_job = max(source_jobs, key=lambda x: x.get('created_at', ''))
                                if latest_job.get('status') == 'завершено':
                                    completed_sources += 1
                        
                        progress["sources_completed"] = completed_sources
                        
                    else:
                        recent_completed = [job for job in jobs if job.get('status') == 'завершено']
                        if recent_completed and stage["status"] == "running":
                            stage["status"] = "completed"
                            stage["completed_at"] = datetime.now()
                        elif stage["status"] not in ["completed"]:
                            stage["status"] = "idle"
                    
                    # Отправляем обновление источников парсинга через WebSocket
                    await event_emitter.emit_scraping_sources_update({
                        "sources": self.scraping_sources,
                        "jobs": jobs
                    })
                            
        except Exception as e:
            # Логируем ошибку только если есть активные соединения
            if websocket_manager.is_anyone_online():
                logger.error(f"❌ Ошибка проверки статуса парсинга: {e}")
            else:
                logger.debug(f"Не удалось обновить статус парсинга (пользователи офлайн): {e}")

automation_service = AutomationService() 