from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
import logging
from datetime import datetime

from app.database import get_db
from app.services.websocket_manager import websocket_manager
from app.services.event_emitter import event_emitter, EventType

logger = logging.getLogger(__name__)

websocket_router = APIRouter()

@websocket_router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """WebSocket endpoint для real-time соединений"""
    connection_id = None
    
    try:
        # Подключаем клиента с аутентификацией
        connection_id = await websocket_manager.connect(websocket, token, db)
        
        if not connection_id:
            return
        
        # Отправляем начальную статистику
        await send_initial_data(connection_id, db)
        
        # Слушаем входящие сообщения
        while True:
            try:
                data = await websocket.receive_text()
                await handle_websocket_message(connection_id, data, db)
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if connection_id:
            websocket_manager.disconnect(connection_id)

async def send_initial_data(connection_id: str, db: Session):
    """Отправляет начальные данные при подключении"""
    try:
        from app.utils.duplicate_processor import DuplicateProcessor
        
        # Получаем текущую статистику
        processor = DuplicateProcessor(db)
        duplicate_stats = processor.get_duplicate_statistics()
        realtor_stats = processor.get_realtor_statistics()
        
        # Статистика системы
        await websocket_manager.send_to_connection(connection_id, {
            "type": "initial_stats",
            "data": {
                "duplicate_stats": duplicate_stats,
                "realtor_stats": realtor_stats,
                "websocket_connections": websocket_manager.get_connection_count()
            }
        })
        
        # Последние события
        recent_events = event_emitter.get_recent_events(20)
        for event in recent_events:
            await websocket_manager.send_to_connection(connection_id, {
                "type": "event",
                "event_type": event.type.value,
                "data": event.data,
                "timestamp": event.timestamp.isoformat(),
                "source": event.source
            })
        
    except Exception as e:
        logger.error(f"Error sending initial data: {e}")

async def send_automation_status(connection_id: str, db: Session):
    """Отправляет текущий статус автоматизации"""
    try:
        from app.services.automation_service import automation_service
        
        # Получаем текущий статус автоматизации
        status = automation_service.get_status()
        logger.info(f"Отправляем статус автоматизации: {status}")
        
        await websocket_manager.send_to_connection(connection_id, {
            "type": "event",
            "event_type": "automation_status",
            "data": status,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error sending automation status: {e}")

async def send_scraping_sources(connection_id: str, db: Session):
    """Отправляет источники парсинга"""
    try:
        from app.services.automation_service import automation_service
        
        # Получаем источники парсинга
        sources = automation_service.scraping_sources
        
        # Получаем задачи парсинга через прямой вызов функции
        try:
            from app.services.scrapy_manager import scrapy_manager
            jobs = await scrapy_manager.get_all_jobs()
        except Exception as e:
            logger.error(f"Ошибка получения задач парсинга: {e}")
            jobs = []
        
        await websocket_manager.send_to_connection(connection_id, {
            "type": "event",
            "event_type": "scraping_sources_update",
            "data": {
                "sources": sources,
                "jobs": jobs
            },
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error sending scraping sources: {e}")

async def handle_websocket_message(connection_id: str, message: str, db: Session):
    """Обрабатывает входящие WebSocket сообщения"""
    try:
        import json
        data = json.loads(message)
        message_type = data.get("type")
        
        if message_type == "ping":
            # Pong ответ для проверки соединения
            await websocket_manager.send_to_connection(connection_id, {
                "type": "pong",
                "timestamp": datetime.now().isoformat()
            })
            
        elif message_type == "request_stats":
            # Запрос текущей статистики
            await send_initial_data(connection_id, db)
            
        elif message_type == "request_recent_events":
            # Запрос последних событий
            limit = data.get("limit", 50)
            recent_events = event_emitter.get_recent_events(limit)
            
            await websocket_manager.send_to_connection(connection_id, {
                "type": "recent_events",
                "data": [
                    {
                        "event_type": event.type.value,
                        "data": event.data,
                        "timestamp": event.timestamp.isoformat(),
                        "source": event.source
                    }
                    for event in recent_events
                ]
            })
            
        elif message_type == "request_automation_status":
            # Запрос статуса автоматизации
            logger.info(f"Запрос статуса автоматизации от соединения {connection_id}")
            await send_automation_status(connection_id, db)
            
        elif message_type == "request_scraping_sources":
            # Запрос источников парсинга
            logger.info(f"Запрос источников парсинга от соединения {connection_id}")
            await send_scraping_sources(connection_id, db)
            
        else:
            logger.warning(f"Unknown WebSocket message type: {message_type}")
            
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in WebSocket message: {message}")
    except Exception as e:
        logger.error(f"Error handling WebSocket message: {e}")

# API endpoints для WebSocket информации
@websocket_router.get("/ws/status")
async def websocket_status():
    """Возвращает статус WebSocket соединений"""
    return {
        "active_connections": websocket_manager.get_connection_count(),
        "connected_users": websocket_manager.get_connected_users()
    }

@websocket_router.get("/ws/events/recent")
async def get_recent_events(limit: int = 50):
    """Возвращает последние события"""
    events = event_emitter.get_recent_events(limit)
    return [
        {
            "event_type": event.type.value,
            "data": event.data,
            "timestamp": event.timestamp.isoformat(),
            "source": event.source
        }
        for event in events
    ]

@websocket_router.post("/ws/broadcast")
async def broadcast_message(message: dict):
    """Отправляет сообщение всем подключенным клиентам (для тестирования)"""
    await websocket_manager.broadcast(message)
    return {"status": "broadcasted", "connections": websocket_manager.get_connection_count()} 