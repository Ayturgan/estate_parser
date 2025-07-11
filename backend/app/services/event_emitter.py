import asyncio
import logging
from typing import Dict, Any, Callable, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from app.services.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Типы событий"""
    # Системные события
    SYSTEM_STATUS = "system_status"
    SYSTEM_ERROR = "system_error"
    SYSTEM_WARNING = "system_warning"
    
    # Статистика
    STATS_UPDATE = "stats_update"
    REALTIME_STATS = "realtime_stats"
    
    # Парсинг
    SCRAPING_STARTED = "scraping_started"
    SCRAPING_PROGRESS = "scraping_progress"
    SCRAPING_COMPLETED = "scraping_completed"
    SCRAPING_ERROR = "scraping_error"
    SCRAPING_SOURCES_UPDATE = "scraping_sources_update"
    
    # Обработка дубликатов
    DUPLICATE_PROCESSING_STARTED = "duplicate_processing_started"
    DUPLICATE_PROCESSING_PROGRESS = "duplicate_processing_progress"
    DUPLICATE_PROCESSING_COMPLETED = "duplicate_processing_completed"
    
    # Автоматизация
    AUTOMATION_STATUS = "automation_status"
    AUTOMATION_PROGRESS = "automation_progress"
    AUTOMATION_COMPLETED = "automation_completed"
    AUTOMATION_ERROR = "automation_error"
    
    # Объявления
    NEW_AD_CREATED = "new_ad_created"
    AD_PROCESSED = "ad_processed"
    DUPLICATE_DETECTED = "duplicate_detected"
    
    # Риэлторы
    REALTOR_DETECTED = "realtor_detected"
    REALTOR_UPDATED = "realtor_updated"
    
    # Elasticsearch
    ELASTICSEARCH_INDEXED = "elasticsearch_indexed"
    ELASTICSEARCH_ERROR = "elasticsearch_error"
    
    # Уведомления
    NOTIFICATION = "notification"
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

@dataclass
class Event:
    """Структура события"""
    type: EventType
    data: Dict[str, Any]
    timestamp: datetime = None
    source: str = "system"
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class EventEmitter:
    """Эмиттер событий для real-time обновлений"""
    
    def __init__(self):
        self.listeners: Dict[EventType, List[Callable]] = {}
        self.event_history: List[Event] = []
        self.max_history = 1000
    
    def on(self, event_type: EventType, callback: Callable):
        """Подписывается на событие"""
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(callback)
    
    def off(self, event_type: EventType, callback: Callable):
        """Отписывается от события"""
        if event_type in self.listeners:
            self.listeners[event_type].remove(callback)
    
    async def emit(self, event_type: EventType, data: Dict[str, Any], source: str = "system"):
        """Генерирует событие"""
        event = Event(type=event_type, data=data, source=source)
        
        # Добавляем в историю
        self.event_history.append(event)
        if len(self.event_history) > self.max_history:
            self.event_history.pop(0)
        
        logger.info(f"Event emitted: {event_type.value} from {source}")
        
        # Вызываем локальные слушатели
        if event_type in self.listeners:
            for callback in self.listeners[event_type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    logger.error(f"Error in event listener: {e}")
        
        # Отправляем через WebSocket
        await self.broadcast_event(event)
    
    async def broadcast_event(self, event: Event):
        """Отправляет событие через WebSocket"""
        message = {
            "type": "event",
            "event_type": event.type.value,
            "data": event.data,
            "timestamp": event.timestamp.isoformat(),
            "source": event.source
        }
        
        await websocket_manager.broadcast_to_admins(message)
    
    def get_recent_events(self, limit: int = 50) -> List[Event]:
        """Возвращает последние события"""
        return self.event_history[-limit:]
    
    def get_events_by_type(self, event_type: EventType, limit: int = 50) -> List[Event]:
        """Возвращает события определенного типа"""
        filtered = [e for e in self.event_history if e.type == event_type]
        return filtered[-limit:]
    
    # Методы для удобной отправки различных типов событий
    
    async def emit_system_status(self, status: str, details: Dict[str, Any] = None):
        """Отправляет статус системы"""
        await self.emit(EventType.SYSTEM_STATUS, {
            "status": status,
            "details": details or {}
        })
    
    async def emit_stats_update(self, stats: Dict[str, Any]):
        """Отправляет обновление статистики"""
        await self.emit(EventType.STATS_UPDATE, stats)
    
    async def emit_scraping_progress(self, job_id: str, progress: int, details: Dict[str, Any] = None):
        """Отправляет прогресс парсинга"""
        await self.emit(EventType.SCRAPING_PROGRESS, {
            "job_id": job_id,
            "progress": progress,
            "details": details or {}
        })
    
    async def emit_scraping_started(self, job_id: str, config: str):
        """Отправляет событие запуска парсинга"""
        await self.emit(EventType.SCRAPING_STARTED, {
            "job_id": job_id,
            "config": config
        })
    
    async def emit_scraping_completed(self, job_id: str, config: str, stats: Dict[str, Any] = None):
        """Отправляет событие завершения парсинга"""
        await self.emit(EventType.SCRAPING_COMPLETED, {
            "job_id": job_id,
            "config": config,
            "stats": stats or {}
        })
    
    async def emit_scraping_error(self, job_id: str, config: str, error: str):
        """Отправляет событие ошибки парсинга"""
        await self.emit(EventType.SCRAPING_ERROR, {
            "job_id": job_id,
            "config": config,
            "error": error
        })
    
    async def emit_scraping_sources_update(self, data: Dict[str, Any]):
        """Отправляет обновление источников парсинга"""
        await self.emit(EventType.SCRAPING_SOURCES_UPDATE, data)
    
    async def emit_duplicate_progress(self, progress: int, processed: int, total: int, current_ad: str = None):
        """Отправляет прогресс обработки дубликатов"""
        await self.emit(EventType.DUPLICATE_PROCESSING_PROGRESS, {
            "progress": progress,
            "processed": processed,
            "total": total,
            "current_ad": current_ad
        })
    
    async def emit_duplicate_completed(self, stats: Dict[str, Any]):
        """Отправляет событие завершения обработки дубликатов"""
        await self.emit(EventType.DUPLICATE_PROCESSING_COMPLETED, stats)
    
    async def emit_automation_status(self, status: Dict[str, Any]):
        """Отправляет статус автоматизации"""
        await self.emit(EventType.AUTOMATION_STATUS, status)
    
    async def emit_automation_progress(self, stage: str, progress: int, details: Dict[str, Any] = None):
        """Отправляет прогресс автоматизации"""
        await self.emit(EventType.AUTOMATION_PROGRESS, {
            "stage": stage,
            "progress": progress,
            "details": details or {}
        })
    
    async def emit_automation_completed(self):
        """Отправляет событие завершения пайплайна автоматизации"""
        await self.emit(EventType.AUTOMATION_COMPLETED, {})

    async def emit_automation_error(self, error: str):
        """Отправляет событие ошибки пайплайна автоматизации"""
        await self.emit(EventType.AUTOMATION_ERROR, {"error": error})
    
    async def emit_new_ad(self, ad_id: int, title: str, source: str):
        """Отправляет уведомление о новом объявлении"""
        await self.emit(EventType.NEW_AD_CREATED, {
            "ad_id": ad_id,
            "title": title,
            "source": source
        })
    
    async def emit_duplicate_detected(self, ad_id: int, unique_ad_id: int, similarity: float):
        """Отправляет уведомление об обнаружении дубликата"""
        await self.emit(EventType.DUPLICATE_DETECTED, {
            "ad_id": ad_id,
            "unique_ad_id": unique_ad_id,
            "similarity": similarity
        })
    
    async def emit_realtor_detected(self, phone: str, ads_count: int):
        """Отправляет уведомление об обнаружении риэлтора"""
        await self.emit(EventType.REALTOR_DETECTED, {
            "phone": phone,
            "ads_count": ads_count
        })
    
    async def emit_notification(self, level: str, title: str, message: str, details: Dict[str, Any] = None):
        """Отправляет уведомление"""
        event_type = {
            "success": EventType.SUCCESS,
            "error": EventType.ERROR,
            "warning": EventType.WARNING,
            "info": EventType.INFO
        }.get(level, EventType.NOTIFICATION)
        
        await self.emit(event_type, {
            "level": level,
            "title": title,
            "message": message,
            "details": details or {}
        })
    
    async def emit_elasticsearch_indexed(self, indexed_count: int, total_count: int):
        """Отправляет событие индексации Elasticsearch"""
        await self.emit(EventType.ELASTICSEARCH_INDEXED, {
            "indexed_count": indexed_count,
            "total_count": total_count
        })
    
    async def emit_elasticsearch_error(self, error: str):
        """Отправляет событие ошибки Elasticsearch"""
        await self.emit(EventType.ELASTICSEARCH_ERROR, {
            "error": error
        })

# Глобальный экземпляр эмиттера
event_emitter = EventEmitter() 