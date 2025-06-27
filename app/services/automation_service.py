import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import aiohttp
from enum import Enum
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)

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

class AutomationService:
    """Сервис автоматизации с управлением через веб-интерфейс"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Состояние пайплайна
        self.pipeline_status = PipelineStatus.IDLE
        self.current_stage: Optional[PipelineStage] = None
        self.last_run_start: Optional[datetime] = None
        self.last_run_end: Optional[datetime] = None
        self.next_run_scheduled: Optional[datetime] = None
        self.is_auto_mode = os.getenv('RUN_IMMEDIATELY_ON_START', 'false').lower() == 'true'
        self.interval_hours = int(os.getenv('PIPELINE_INTERVAL_HOURS', '3'))
        
        # Детали выполнения
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
        
        # Настройки из переменных окружения
        self.enabled_stages = {
            PipelineStage.SCRAPING: os.getenv('ENABLE_SCRAPING', 'true').lower() == 'true',
            PipelineStage.PHOTO_PROCESSING: os.getenv('ENABLE_PHOTO_PROCESSING', 'true').lower() == 'true', 
            PipelineStage.DUPLICATE_PROCESSING: os.getenv('ENABLE_DUPLICATE_PROCESSING', 'true').lower() == 'true',
            PipelineStage.REALTOR_DETECTION: os.getenv('ENABLE_REALTOR_DETECTION', 'true').lower() == 'true',
            PipelineStage.ELASTICSEARCH_REINDEX: os.getenv('ENABLE_ELASTICSEARCH_REINDEX', 'true').lower() == 'true'
        }
        
        # Источники парсинга из переменных окружения
        sources_str = os.getenv('SCRAPING_SOURCES', 'house,lalafo,stroka')
        self.scraping_sources = [s.strip() for s in sources_str.split(',') if s.strip()]
        
        # Фоновая задача
        self._background_task: Optional[asyncio.Task] = None
        
        # Исходная статистика для отслеживания новых объявлений
        self.initial_stats = None
        
    async def start_service(self):
        """Запуск сервиса автоматизации"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        if not self._background_task:
            self._background_task = asyncio.create_task(self._background_scheduler())
            
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
    
    async def _background_scheduler(self):
        """Фоновый планировщик для автоматического режима"""
        while True:
            try:
                if (self.is_auto_mode and 
                    self.pipeline_status == PipelineStatus.IDLE and
                    self.next_run_scheduled and
                    datetime.now() >= self.next_run_scheduled):
                    
                    logger.info("⏰ Запуск автоматического пайплайна по расписанию")
                    await self.start_pipeline()
                
                await asyncio.sleep(60)  # Проверяем каждую минуту
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в планировщике: {e}")
                await asyncio.sleep(60)
    
    async def start_pipeline(self, manual: bool = False) -> bool:
        """Запуск полного пайплайна"""
        if self.pipeline_status == PipelineStatus.RUNNING:
            return False
            
        self.pipeline_status = PipelineStatus.RUNNING
        self.last_run_start = datetime.now()
        self.last_run_end = None
        
        if not manual:
            # Планируем следующий запуск
            self.next_run_scheduled = datetime.now() + timedelta(hours=self.interval_hours)
        
        logger.info(f"🚀 Запуск пайплайна ({'ручной' if manual else 'автоматический'})")
        
        try:
            success = True
            
            # Выполняем все этапы последовательно
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
            
            logger.info(f"✅ Пайплайн завершен {'успешно' if success else 'с ошибками'}")
            return success
            
        except Exception as e:
            self.pipeline_status = PipelineStatus.ERROR
            self.current_stage = None
            self.last_run_end = datetime.now()
            logger.error(f"❌ Ошибка выполнения пайплайна: {e}")
            return False
    
    async def _execute_stage(self, stage: PipelineStage) -> bool:
        """Выполнение конкретного этапа пайплайна"""
        stage_info = self.stage_details[stage]
        stage_info["status"] = "running"
        stage_info["started_at"] = datetime.now()
        stage_info["error"] = None
        
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
            return success
            
        except Exception as e:
            stage_info["status"] = "error"
            stage_info["error"] = str(e)
            stage_info["completed_at"] = datetime.now()
            logger.error(f"❌ Ошибка этапа {stage.value}: {e}")
            return False
    
    async def _execute_scraping(self) -> bool:
        """Выполнение этапа парсинга"""
        # Сохраняем исходную статистику
        await self._update_stats()
        
        job_ids = []
        progress = self.stage_details[PipelineStage.SCRAPING]["progress"]
        progress["total"] = len(self.scraping_sources)
        progress["completed"] = 0
        progress["failed"] = 0
        progress["sources_active"] = 0
        progress["sources_completed"] = 0
        progress["new_ads"] = 0
        progress["processed_ads"] = 0
        
        # Запускаем парсинг по всем источникам
        for source in self.scraping_sources:
            try:
                async with self.session.post(f"{self.api_base_url}/api/scraping/start/{source}") as response:
                    if response.status in [200, 201, 202]:
                        data = await response.json()
                        job_id = data.get('job_id')
                        if job_id:
                            job_ids.append((source, job_id))
                            progress["sources_active"] += 1
                            logger.info(f"✅ Парсинг {source} запущен (job_id: {job_id})")
                    else:
                        progress["failed"] += 1
                        logger.error(f"❌ Ошибка запуска парсинга {source}")
            except Exception as e:
                progress["failed"] += 1
                logger.error(f"❌ Ошибка запроса парсинга {source}: {e}")
        
        if not job_ids:
            return False
            
        # Ждем завершения всех задач
        return await self._wait_for_scraping_completion(job_ids)
    
    async def _wait_for_scraping_completion(self, job_ids: list) -> bool:
        """Ожидание завершения парсинга"""
        progress = self.stage_details[PipelineStage.SCRAPING]["progress"]
        completed_jobs = set()
        
        while len(completed_jobs) < len(job_ids):
            # Обновляем статистику на каждой итерации
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
                                    logger.info(f"✅ Парсинг {source}: завершен успешно")
                                else:
                                    progress["failed"] += 1
                                    logger.info(f"❌ Парсинг {source}: завершен с ошибкой ({status})")
                            elif status == 'выполняется':
                                logger.info(f"⏳ Парсинг {source}: выполняется...")
                                
                except Exception as e:
                    logger.error(f"❌ Ошибка проверки статуса {source}: {e}")
            
            if len(completed_jobs) < len(job_ids):
                await asyncio.sleep(30)  # Проверяем каждые 30 секунд
        
        # Финальное обновление статистики
        await self._update_stats()
        return progress["failed"] == 0
    
    async def _wait_for_process_completion(self, process_type: str) -> bool:
        """Ожидание завершения фоновых процессов"""
        max_wait_time = 3600  # Максимум 1 час ожидания
        check_interval = 30   # Проверяем каждые 30 секунд
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
                    logger.error(f"❌ Неизвестный тип процесса: {process_type}")
                    return False
                
                async with self.session.get(f"{self.api_base_url}{endpoint}") as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Проверяем статус в зависимости от типа процесса
                        if process_type == "photos":
                            status = data.get('status', 'unknown')
                            if status in ['completed', 'idle']:
                                logger.info(f"✅ Обработка фотографий завершена")
                                return True
                            elif status == 'error':
                                logger.error(f"❌ Ошибка обработки фотографий")
                                return False
                                
                        elif process_type == "duplicates":
                            status = data.get('status', 'unknown')
                            if status in ['completed', 'idle']:
                                logger.info(f"✅ Обработка дубликатов завершена")
                                return True
                            elif status == 'error':
                                logger.error(f"❌ Ошибка обработки дубликатов")
                                return False
                                
                        elif process_type == "realtors":
                            status = data.get('status', 'unknown')
                            if status in ['completed', 'idle']:
                                logger.info(f"✅ Определение риэлторов завершено")
                                return True
                            elif status == 'error':
                                logger.error(f"❌ Ошибка определения риэлторов")
                                return False
                                
                        elif process_type == "elasticsearch":
                            # Для elasticsearch просто проверяем доступность
                            logger.info(f"✅ Переиндексация завершена")
                            return True
                            
                        # Если процесс еще выполняется, ждем
                        logger.info(f"⏳ {process_type} еще выполняется, ожидание...")
                        
                    else:
                        logger.warning(f"⚠️ Не удалось проверить статус {process_type}")
                        
            except Exception as e:
                logger.error(f"❌ Ошибка проверки статуса {process_type}: {e}")
            
            await asyncio.sleep(check_interval)
            elapsed_time += check_interval
        
        logger.warning(f"⏰ Превышено время ожидания для {process_type}")
        return False
    
    async def _execute_photo_processing(self) -> bool:
        """Выполнение обработки фотографий"""
        try:
            # Запускаем обработку фотографий
            async with self.session.post(f"{self.api_base_url}/api/process/photos") as response:
                if response.status not in [200, 201, 202]:
                    return False
                    
            # Ждем завершения обработки фотографий
            logger.info("📸 Обработка фотографий запущена, ожидание завершения...")
            return await self._wait_for_process_completion("photos")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска обработки фото: {e}")
            return False
    
    async def _execute_duplicate_processing(self) -> bool:
        """Выполнение обработки дубликатов"""
        try:
            # Запускаем обработку дубликатов
            async with self.session.post(f"{self.api_base_url}/api/process/duplicates") as response:
                if response.status not in [200, 201, 202]:
                    return False
                    
            # Ждем завершения обработки дубликатов
            logger.info("🔍 Обработка дубликатов запущена, ожидание завершения...")
            return await self._wait_for_process_completion("duplicates")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска обработки дубликатов: {e}")
            return False
    
    async def _execute_realtor_detection(self) -> bool:
        """Выполнение определения риэлторов"""
        try:
            # Запускаем определение риэлторов
            async with self.session.post(f"{self.api_base_url}/api/process/realtors/detect") as response:
                if response.status not in [200, 201, 202]:
                    return False
                    
            # Ждем завершения определения риэлторов
            logger.info("👤 Определение риэлторов запущено, ожидание завершения...")
            return await self._wait_for_process_completion("realtors")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска определения риэлторов: {e}")
            return False
    
    async def _execute_elasticsearch_reindex(self) -> bool:
        """Выполнение переиндексации"""
        try:
            # Запускаем переиндексацию
            async with self.session.post(f"{self.api_base_url}/api/elasticsearch/reindex") as response:
                if response.status not in [200, 201, 202]:
                    return False
                    
            # Ждем завершения переиндексации
            logger.info("🔍 Переиндексация запущена, ожидание завершения...")
            return await self._wait_for_process_completion("elasticsearch")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска переиндексации: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Получение полного статуса автоматизации"""
        return {
            "pipeline_status": self.pipeline_status.value,
            "current_stage": self.current_stage.value if self.current_stage else None,
            "is_auto_mode": self.is_auto_mode,
            "interval_hours": self.interval_hours,
            "scraping_sources": self.scraping_sources,
            "last_run_start": self.last_run_start.isoformat() if self.last_run_start else None,
            "last_run_end": self.last_run_end.isoformat() if self.last_run_end else None,
            "next_run_scheduled": self.next_run_scheduled.isoformat() if self.next_run_scheduled else None,
            "enabled_stages": {stage.value: enabled for stage, enabled in self.enabled_stages.items()},
            "stage_details": {
                stage.value: {
                    **details,
                    "started_at": details["started_at"].isoformat() if details["started_at"] else None,
                    "completed_at": details["completed_at"].isoformat() if details["completed_at"] else None
                }
                for stage, details in self.stage_details.items()
            }
        }
    
    # Методы управления автоматическим режимом удалены - настройки только через .env файл
    
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
    
    def stop_pipeline(self):
        """Остановка пайплайна"""
        if self.pipeline_status in [PipelineStatus.RUNNING, PipelineStatus.PAUSED]:
            self.pipeline_status = PipelineStatus.IDLE
            self.current_stage = None
            self.last_run_end = datetime.now()
            logger.info("🛑 Пайплайн остановлен")

    async def _update_stats(self):
        """Обновление статистики системы"""
        try:
            async with self.session.get(f"{self.api_base_url}/api/stats") as response:
                if response.status == 200:
                    current_stats = await response.json()
                    
                    if self.initial_stats is None:
                        self.initial_stats = current_stats.copy()
                    
                    # Обновляем прогресс парсинга
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
            # Обновляем статус обработки дубликатов
            await self._update_duplicates_status()
            
            # Обновляем статус обработки фотографий
            await self._update_photos_status()
            
            # Обновляем статус определения риэлторов
            await self._update_realtors_status()
            
            # Обновляем статус парсинга
            await self._update_scraping_status()
            
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
                        
                        # Обновляем прогресс если есть данные
                        progress = data.get('progress', {})
                        if progress:
                            stage["progress"].update(progress)
                            
                    elif status == 'completed':
                        stage["status"] = "completed"
                        if not stage["completed_at"]:
                            stage["completed_at"] = datetime.now()
                        
                        # Сбрасываем статус на idle через 10 секунд после завершения
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
            logger.debug(f"Не удалось обновить статус дубликатов: {e}")
    
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
                        
                        # Обновляем прогресс если есть данные
                        progress = data.get('progress', {})
                        if progress:
                            stage["progress"].update(progress)
                            
                    elif status == 'completed':
                        stage["status"] = "completed"
                        if not stage["completed_at"]:
                            stage["completed_at"] = datetime.now()
                        
                        # Сбрасываем статус на idle через 10 секунд после завершения
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
            logger.debug(f"Не удалось обновить статус фотографий: {e}")
    
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
                        
                        # Обновляем прогресс если есть данные
                        progress = data.get('progress', {})
                        if progress:
                            stage["progress"].update(progress)
                            
                    elif status == 'completed':
                        stage["status"] = "completed"
                        if not stage["completed_at"]:
                            stage["completed_at"] = datetime.now()
                        
                        # Сбрасываем статус на idle через 10 секунд после завершения
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
            logger.debug(f"Не удалось обновить статус риэлторов: {e}")
    
    async def _update_scraping_status(self):
        """Обновление статуса парсинга"""
        try:
            async with self.session.get(f"{self.api_base_url}/api/scraping/jobs") as response:
                if response.status == 200:
                    jobs = await response.json()
                    stage = self.stage_details[PipelineStage.SCRAPING]
                    
                    # Проверяем есть ли активные задачи парсинга
                    running_jobs = [job for job in jobs if job.get('status') == 'выполняется']
                    
                    if running_jobs:
                        stage["status"] = "running"
                        if not stage["started_at"]:
                            stage["started_at"] = datetime.now()
                        
                        # Обновляем прогресс парсинга
                        progress = stage["progress"]
                        progress["sources_active"] = len(running_jobs)
                        progress["total"] = len(self.scraping_sources)
                        
                        # Считаем завершенные источники
                        completed_sources = 0
                        for source in self.scraping_sources:
                            source_jobs = [j for j in jobs if j.get('config') == source]
                            if source_jobs:
                                latest_job = max(source_jobs, key=lambda x: x.get('created_at', ''))
                                if latest_job.get('status') == 'завершено':
                                    completed_sources += 1
                        
                        progress["sources_completed"] = completed_sources
                        
                    else:
                        # Проверяем были ли недавние завершенные задачи
                        recent_completed = [job for job in jobs if job.get('status') == 'завершено']
                        if recent_completed and stage["status"] == "running":
                            stage["status"] = "completed"
                            stage["completed_at"] = datetime.now()
                        elif stage["status"] not in ["completed"]:
                            stage["status"] = "idle"
                            
        except Exception as e:
            logger.debug(f"Не удалось обновить статус парсинга: {e}")

# Глобальный экземпляр сервиса
automation_service = AutomationService() 