import json
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database import db_models
from app.database.database import SessionLocal

logger = logging.getLogger(__name__)

class SettingsService:
    """Сервис для управления настройками системы"""
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_updated: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=5)  # Кэш на 5 минут
        
    def _get_db(self) -> Session:
        """Получить сессию БД"""
        return SessionLocal()
    
    def _is_cache_valid(self) -> bool:
        """Проверить актуальность кэша"""
        if not self._cache_updated:
            return False
        return datetime.now() - self._cache_updated < self._cache_ttl
    
    def _load_settings_to_cache(self):
        """Загрузить все настройки в кэш"""
        try:
            db = self._get_db()
            settings = db.query(db_models.DBSettings).all()
            
            self._cache.clear()
            for setting in settings:
                # Конвертируем значение в правильный тип
                converted_value = self._convert_value(setting.value, setting.value_type)
                self._cache[setting.key] = converted_value
            
            self._cache_updated = datetime.now()
            logger.debug(f"Загружено {len(settings)} настроек в кэш")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки настроек в кэш: {e}")
        finally:
            db.close()
    
    def _convert_value(self, value: str, value_type: str) -> Any:
        """Конвертировать строковое значение в нужный тип"""
        if value is None:
            return None
            
        try:
            if value_type == 'bool':
                return value.lower() in ('true', '1', 'yes', 'on')
            elif value_type == 'int':
                return int(value)
            elif value_type == 'float':
                return float(value)
            elif value_type == 'json':
                return json.loads(value) if value else None
            else:  # string
                return value
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Ошибка конвертации значения '{value}' в тип '{value_type}': {e}")
            return None
    
    def _convert_to_string(self, value: Any, value_type: str) -> str:
        """Конвертировать значение в строку для сохранения в БД"""
        if value is None:
            return ""
        
        try:
            if value_type == 'json':
                return json.dumps(value)
            else:
                return str(value)
        except Exception as e:
            logger.error(f"Ошибка конвертации значения в строку: {e}")
            return str(value)
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Получить значение настройки"""
        if not self._is_cache_valid():
            self._load_settings_to_cache()
        
        return self._cache.get(key, default)
    
    def set_setting(self, key: str, value: Any, value_type: str = 'string', 
                   description: str = None, category: str = None) -> bool:
        """Установить значение настройки"""
        try:
            db = self._get_db()
            
            # Ищем существующую настройку
            setting = db.query(db_models.DBSettings).filter(
                db_models.DBSettings.key == key
            ).first()
            
            string_value = self._convert_to_string(value, value_type)
            
            if setting:
                # Обновляем существующую настройку
                setting.value = string_value
                setting.value_type = value_type
                if description:
                    setting.description = description
                if category:
                    setting.category = category
                setting.updated_at = datetime.now()
            else:
                # Создаем новую настройку
                setting = db_models.DBSettings(
                    key=key,
                    value=string_value,
                    value_type=value_type,
                    description=description,
                    category=category
                )
                db.add(setting)
            
            db.commit()
            
            # Обновляем кэш
            self._cache[key] = self._convert_value(string_value, value_type)
            self._cache_updated = datetime.now()
            
            logger.info(f"Настройка '{key}' обновлена: {value}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения настройки '{key}': {e}")
            if db:
                db.rollback()
            return False
        finally:
            if db:
                db.close()
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Получить все настройки"""
        if not self._is_cache_valid():
            self._load_settings_to_cache()
        return self._cache.copy()
    
    def get_settings_by_category(self, category: str) -> Dict[str, Any]:
        """Получить настройки по категории"""
        try:
            db = self._get_db()
            settings = db.query(db_models.DBSettings).filter(
                db_models.DBSettings.category == category
            ).all()
            
            result = {}
            for setting in settings:
                value = self._convert_value(setting.value, setting.value_type)
                result[setting.key] = value
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения настроек категории '{category}': {e}")
            return {}
        finally:
            db.close()
    
    def delete_setting(self, key: str) -> bool:
        """Удалить настройку"""
        try:
            db = self._get_db()
            setting = db.query(db_models.DBSettings).filter(
                db_models.DBSettings.key == key
            ).first()
            
            if setting:
                db.delete(setting)
                db.commit()
                
                # Удаляем из кэша
                if key in self._cache:
                    del self._cache[key]
                
                logger.info(f"Настройка '{key}' удалена")
                return True
            else:
                logger.warning(f"Настройка '{key}' не найдена для удаления")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка удаления настройки '{key}': {e}")
            if db:
                db.rollback()
            return False
        finally:
            if db:
                db.close()
    
    def initialize_default_settings(self):
        """Инициализировать настройки по умолчанию"""
        default_settings = [
            # Автоматизация
            {
                'key': 'auto_mode',
                'value': True,
                'value_type': 'bool',
                'description': 'Автоматический режим работы пайплайна',
                'category': 'automation'
            },
            {
                'key': 'pipeline_interval_minutes',
                'value': 180,
                'value_type': 'int',
                'description': 'Интервал автоматического запуска пайплайна (в минутах)',
                'category': 'automation'
            },
            {
                'key': 'run_immediately_on_start',
                'value': False,
                'value_type': 'bool',
                'description': 'Запускать пайплайн сразу при старте сервиса',
                'category': 'automation'
            },
            
            # Парсинг
            {
                'key': 'scraping_sources',
                'value': ['lalafo', 'stroka'],
                'value_type': 'json',
                'description': 'Список источников для парсинга',
                'category': 'scraping'
            },
            {
                'key': 'enable_scraping',
                'value': True,
                'value_type': 'bool',
                'description': 'Включить этап парсинга',
                'category': 'scraping'
            },
            
            # Обработка
            {
                'key': 'enable_photo_processing',
                'value': True,
                'value_type': 'bool',
                'description': 'Включить обработку фотографий',
                'category': 'processing'
            },
            {
                'key': 'enable_duplicate_processing',
                'value': True,
                'value_type': 'bool',
                'description': 'Включить обработку дубликатов',
                'category': 'processing'
            },
            {
                'key': 'enable_realtor_detection',
                'value': True,
                'value_type': 'bool',
                'description': 'Включить определение риэлторов',
                'category': 'processing'
            },
            {
                'key': 'enable_elasticsearch_reindex',
                'value': True,
                'value_type': 'bool',
                'description': 'Включить переиндексацию Elasticsearch',
                'category': 'processing'
            },
            {
                'key': 'enable_link_validation',
                'value': True,
                'value_type': 'bool',
                'description': 'Включить валидацию ссылок',
                'category': 'processing'
            },
            {
                'key': 'link_validation_batch_size',
                'value': 500,
                'value_type': 'int',
                'description': 'Размер батча для валидации ссылок',
                'category': 'processing'
            },
            

        ]
        
        for setting_data in default_settings:
            # Проверяем, существует ли уже настройка в БД
            try:
                db = self._get_db()
                existing_setting = db.query(db_models.DBSettings).filter(
                    db_models.DBSettings.key == setting_data['key']
                ).first()
                
                if not existing_setting:
                    # Создаем настройку только если её нет в БД
                    self.set_setting(
                        key=setting_data['key'],
                        value=setting_data['value'],
                        value_type=setting_data['value_type'],
                        description=setting_data['description'],
                        category=setting_data['category']
                    )
                    logger.info(f"Создана настройка по умолчанию: {setting_data['key']}")
                else:
                    logger.debug(f"Настройка уже существует: {setting_data['key']}")
                    
            except Exception as e:
                logger.error(f"Ошибка проверки настройки {setting_data['key']}: {e}")
            finally:
                if db:
                    db.close()
        
        logger.info("Настройки по умолчанию инициализированы")
        
        # Синхронизируем auto_mode с automation_service
        try:
            from app.services.automation_service import automation_service
            auto_mode = self.get_setting('auto_mode', True)
            automation_service.set_auto_mode(auto_mode)
            logger.info(f"Автоматический режим синхронизирован при инициализации: {auto_mode}")
        except Exception as e:
            logger.error(f"Ошибка синхронизации auto_mode с automation_service: {e}")

# Создаем глобальный экземпляр сервиса
settings_service = SettingsService() 