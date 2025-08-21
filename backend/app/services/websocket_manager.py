import json
import asyncio
import logging
from typing import Dict, List, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import jwt
from sqlalchemy.orm import Session

from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Менеджер WebSocket соединений"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.auth_service = AuthService()
        
    async def connect(self, websocket: WebSocket, token: str, db: Session) -> Optional[str]:
        """Подключает клиента с проверкой аутентификации"""
        try:
            # Проверяем токен - принимаем как Bearer формат, так и напрямую
            if not token:
                await websocket.close(code=4001, reason="No token provided")
                return None
            
            # Если токен передан с префиксом Bearer, извлекаем его
            if token.startswith("Bearer "):
                token_value = token.split(" ")[1]
            else:
                # Токен передан напрямую (как в URL параметре)
                token_value = token
            admin = self.auth_service.get_admin_by_token(db, token_value)
            
            if not admin:
                await websocket.close(code=4001, reason="Invalid or expired token")
                return None
            
            await websocket.accept()
            connection_id = f"admin_{admin.id}_{datetime.now().timestamp()}"
            self.active_connections[connection_id] = websocket
            
            logger.info(f"WebSocket connected: {admin.username} ({connection_id})")
            
            # Логируем общее количество соединений
            total_connections = len(self.active_connections)
            if total_connections == 1:
                logger.info("🟢 Первый пользователь онлайн - включаем проверку статуса всех процессов")
            else:
                logger.info(f"👥 Всего активных соединений: {total_connections}")
            
            # Отправляем приветственное сообщение
            await self.send_to_connection(connection_id, {
                "type": "connection_established",
                "data": {
                    "connection_id": connection_id,
                    "user": admin.username,
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            return connection_id
            
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
            await websocket.close(code=4000, reason="Connection failed")
            return None
    
    def disconnect(self, connection_id: str):
        """Отключает клиента"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
            logger.info(f"WebSocket disconnected: {connection_id}")
            
            # Логируем количество оставшихся соединений
            remaining_connections = len(self.active_connections)
            if remaining_connections == 0:
                logger.info("🔴 Все пользователи офлайн - отключаем проверку статуса всех процессов")
            else:
                logger.info(f"👥 Осталось активных соединений: {remaining_connections}")
    
    async def send_to_connection(self, connection_id: str, message: Dict[str, Any]):
        """Отправляет сообщение конкретному соединению"""
        if connection_id in self.active_connections:
            try:
                websocket = self.active_connections[connection_id]
                await websocket.send_text(json.dumps(message, default=str))
            except Exception as e:
                logger.error(f"Error sending to {connection_id}: {e}")
                self.disconnect(connection_id)
    
    async def broadcast(self, message: Dict[str, Any]):
        """Отправляет сообщение всем подключенным клиентам"""
        if not self.active_connections:
            return
        
        message_text = json.dumps(message, default=str)
        disconnected = []
        
        for connection_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message_text)
            except Exception as e:
                logger.error(f"Error broadcasting to {connection_id}: {e}")
                disconnected.append(connection_id)
        
        # Удаляем отключенные соединения
        for connection_id in disconnected:
            self.disconnect(connection_id)
    
    async def broadcast_to_admins(self, message: Dict[str, Any]):
        """Отправляет сообщение только администраторам"""
        await self.broadcast(message)
    
    def get_connection_count(self) -> int:
        """Возвращает количество активных соединений"""
        return len(self.active_connections)
    
    def get_connected_users(self) -> List[str]:
        """Возвращает список ID подключенных соединений"""
        return list(self.active_connections.keys())
    
    def is_anyone_online(self) -> bool:
        """Проверяет, есть ли активные соединения"""
        return len(self.active_connections) > 0

# Глобальный экземпляр менеджера
websocket_manager = WebSocketManager() 