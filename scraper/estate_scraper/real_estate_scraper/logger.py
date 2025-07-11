import logging
import os
from datetime import datetime
from typing import Optional
import json

class ScrapingLogger:
    """Централизованная система логирования для задач парсинга"""
    
    def __init__(self, job_id: str, config_name: str):
        self.job_id = job_id
        self.config_name = config_name
        self.log_dir = "/app/logs/scraping"
        self.ensure_log_directory()
        
        # Создаем отдельный логгер для этой задачи
        self.logger = logging.getLogger(f"scraping_{job_id}")
        self.logger.setLevel(logging.DEBUG)
        
        # Предотвращаем дублирование обработчиков
        if not self.logger.handlers:
            self.setup_handlers()
        
        # Метрики задачи
        self.stats = {
            'job_id': job_id,
            'config_name': config_name,
            'started_at': datetime.now().isoformat(),
            'items_total': 0,
            'items_processed': 0,
            'items_failed': 0,
            'pages_processed': 0,
            'api_calls_success': 0,
            'api_calls_failed': 0,
            'errors': [],
            'warnings': []
        }
    
    def ensure_log_directory(self):
        """Создает директорию для логов если она не существует"""
        os.makedirs(self.log_dir, exist_ok=True)
    
    def setup_handlers(self):
        """Настраивает обработчики логов"""
        # Файл детальных логов для задачи
        detail_log_file = f"{self.log_dir}/scraping_{self.job_id}_{self.config_name}.log"
        detail_handler = logging.FileHandler(detail_log_file, encoding='utf-8')
        detail_handler.setLevel(logging.DEBUG)
        
        # Файл только ошибок
        error_log_file = f"{self.log_dir}/scraping_{self.job_id}_{self.config_name}_errors.log"
        error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        
        # Общий файл статистики всех задач
        stats_log_file = f"{self.log_dir}/scraping_stats.log"
        stats_handler = logging.FileHandler(stats_log_file, encoding='utf-8')
        stats_handler.setLevel(logging.INFO)
        
        # Форматирование
        detail_formatter = logging.Formatter(
            '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        error_formatter = logging.Formatter(
            '%(asctime)s [JOB:%(job_id)s|%(config)s] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        detail_handler.setFormatter(detail_formatter)
        error_handler.setFormatter(detail_formatter)
        stats_handler.setFormatter(detail_formatter)
        
        self.logger.addHandler(detail_handler)
        self.logger.addHandler(error_handler)
        self.logger.addHandler(stats_handler)
        
        # Также выводим в консоль с префиксом
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            f'[JOB:{self.job_id[:8]}|{self.config_name}] %(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
    
    def log_job_start(self):
        """Логирует начало задачи"""
        self.logger.info("=" * 60)
        self.logger.info(f"🚀 ЗАПУСК ЗАДАЧИ ПАРСИНГА")
        self.logger.info(f"📋 Job ID: {self.job_id}")
        self.logger.info(f"⚙️ Конфиг: {self.config_name}")
        self.logger.info(f"🕐 Время старта: {self.stats['started_at']}")
        self.logger.info("=" * 60)
    
    def log_job_end(self, status: str = "completed", error: Optional[str] = None):
        """Логирует завершение задачи"""
        self.stats['finished_at'] = datetime.now().isoformat()
        self.stats['status'] = status
        if error:
            self.stats['final_error'] = error
            
        duration = self._calculate_duration()
        
        self.logger.info("=" * 60)
        self.logger.info(f"🏁 ЗАВЕРШЕНИЕ ЗАДАЧИ ПАРСИНГА")
        self.logger.info(f"📊 ИТОГОВАЯ СТАТИСТИКА:")
        self.logger.info(f"   ⏱️ Длительность: {duration}")
        self.logger.info(f"   📄 Страниц обработано: {self.stats['pages_processed']}")
        self.logger.info(f"   🏠 Объявлений найдено: {self.stats['items_total']}")
        self.logger.info(f"   ✅ Успешно обработано: {self.stats['items_processed']}")
        self.logger.info(f"   ❌ Ошибок обработки: {self.stats['items_failed']}")
        self.logger.info(f"   📡 API вызовов успешных: {self.stats['api_calls_success']}")
        self.logger.info(f"   🚫 API вызовов неуспешных: {self.stats['api_calls_failed']}")
        self.logger.info(f"   ⚠️ Предупреждений: {len(self.stats['warnings'])}")
        self.logger.info(f"   💥 Ошибок: {len(self.stats['errors'])}")
        self.logger.info(f"   🎯 Статус: {status.upper()}")
        if error:
            self.logger.error(f"   🔥 Финальная ошибка: {error}")
        self.logger.info("=" * 60)
        
        # Сохраняем финальную статистику в отдельный файл
        self._save_stats()
    
    def log_page_processed(self, page_num: int, items_found: int, url: str = ""):
        """Логирует обработку страницы"""
        self.stats['pages_processed'] += 1
        self.stats['items_total'] += items_found
        
        self.logger.info(f"📄 Страница {page_num} обработана: найдено {items_found} объявлений")
        if url:
            self.logger.debug(f"   🔗 URL: {url}")
    
    def log_item_processing(self, item_title: str, item_url: str = ""):
        """Логирует начало обработки объявления"""
        self.logger.debug(f"🏠 Обрабатываем объявление: {item_title}")
        if item_url:
            self.logger.debug(f"   🔗 URL: {item_url}")
    
    def log_item_success(self, item_title: str, extracted_data: dict = None):
        """Логирует успешную обработку объявления"""
        self.stats['items_processed'] += 1
        
        self.logger.info(f"✅ Объявление успешно обработано: {item_title}")
        if extracted_data:
            property_type = extracted_data.get('property_type', 'N/A')
            listing_type = extracted_data.get('listing_type', 'N/A')
            rooms = extracted_data.get('rooms', 'N/A')
            area = extracted_data.get('area_sqm', 'N/A')
            self.logger.debug(f"   📊 Данные: {property_type}, {listing_type}, {rooms} комн., {area} м²")
    
    def log_item_failure(self, item_title: str, error: str):
        """Логирует ошибку обработки объявления"""
        self.stats['items_failed'] += 1
        self.stats['errors'].append({
            'timestamp': datetime.now().isoformat(),
            'type': 'item_processing',
            'item': item_title,
            'error': error
        })
        
        self.logger.error(f"❌ Ошибка обработки объявления: {item_title}")
        self.logger.error(f"   💥 Ошибка: {error}")
    
    def log_api_call_success(self, item_title: str, endpoint: str = ""):
        """Логирует успешный вызов API"""
        self.stats['api_calls_success'] += 1
        
        self.logger.info(f"📡 API: успешно отправлено - {item_title}")
        if endpoint:
            self.logger.debug(f"   🎯 Endpoint: {endpoint}")
    
    def log_api_call_failure(self, item_title: str, error: str, endpoint: str = ""):
        """Логирует ошибку вызова API"""
        self.stats['api_calls_failed'] += 1
        self.stats['errors'].append({
            'timestamp': datetime.now().isoformat(),
            'type': 'api_call',
            'item': item_title,
            'endpoint': endpoint,
            'error': error
        })
        
        self.logger.error(f"🚫 API: ошибка отправки - {item_title}")
        self.logger.error(f"   💥 Ошибка: {error}")
        if endpoint:
            self.logger.debug(f"   🎯 Endpoint: {endpoint}")
    
    def log_warning(self, message: str, context: str = ""):
        """Логирует предупреждение"""
        self.stats['warnings'].append({
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'context': context
        })
        
        self.logger.warning(f"⚠️ {message}")
        if context:
            self.logger.debug(f"   📝 Контекст: {context}")
    
    def log_error(self, message: str, context: str = "", exception: Exception = None):
        """Логирует ошибку"""
        error_data = {
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'context': context
        }
        if exception:
            error_data['exception'] = str(exception)
            error_data['exception_type'] = type(exception).__name__
        
        self.stats['errors'].append(error_data)
        
        self.logger.error(f"💥 {message}")
        if context:
            self.logger.debug(f"   📝 Контекст: {context}")
        if exception:
            self.logger.debug(f"   🐛 Исключение: {exception}")
    
    def log_ai_processing(self, title: str, description: str, result: dict = None):
        """Логирует AI обработку"""
        text_len = len(f"{title} {description}".strip())
        self.logger.debug(f"🤖 AI обработка: '{title}' (текст: {text_len} символов)")
        
        if result:
            property_type = result.get('property_type', 'N/A')
            property_confidence = result.get('property_type_confidence', 0)
            listing_type = result.get('listing_type', 'N/A')
            listing_confidence = result.get('listing_type_confidence', 0)
            quality = result.get('extraction_quality', 0)
            
            self.logger.debug(f"   🏠 Тип недвижимости: {property_type} (уверенность: {property_confidence:.2f})")
            self.logger.debug(f"   📋 Тип объявления: {listing_type} (уверенность: {listing_confidence:.2f})")
            self.logger.debug(f"   🎯 Качество извлечения: {quality:.2f}")
    
    def log_request_failure(self, url: str, error: str):
        """Логирует ошибку HTTP запроса"""
        self.stats['api_calls_failed'] += 1
        self.stats['errors'].append({
            'timestamp': datetime.now().isoformat(),
            'type': 'http_request',
            'url': url,
            'error': error
        })
        
        self.logger.error(f"🚫 HTTP запрос неуспешен: {url}")
        self.logger.error(f"   💥 Ошибка: {error}")
    
    def log_spider_finished(self, stats: dict):
        """Логирует завершение работы спайдера"""
        self.logger.info("🕷️ Спайдер завершил работу")
        self.logger.info(f"   📊 Статистика: {stats}")
        
        # Обновляем общую статистику
        if 'scraped_items' in stats:
            self.stats['items_total'] = stats['scraped_items']
        if 'category_breakdown' in stats:
            self.logger.info("   📂 Разбивка по категориям:")
            for category, count in stats['category_breakdown'].items():
                self.logger.info(f"      {category}: {count} объявлений")
    
    def get_stats(self) -> dict:
        """Возвращает текущую статистику"""
        return self.stats.copy()
    
    def _calculate_duration(self) -> str:
        """Вычисляет длительность выполнения"""
        if 'finished_at' not in self.stats:
            return "N/A"
        
        try:
            start = datetime.fromisoformat(self.stats['started_at'])
            end = datetime.fromisoformat(self.stats['finished_at'])
            duration = end - start
            
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                return f"{hours}ч {minutes}м {seconds}с"
            elif minutes > 0:
                return f"{minutes}м {seconds}с"
            else:
                return f"{seconds}с"
        except:
            return "N/A"
    
    def _save_stats(self):
        """Сохраняет финальную статистику в JSON файл"""
        stats_file = f"{self.log_dir}/scraping_{self.job_id}_{self.config_name}_stats.json"
        try:
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения статистики: {e}")

# Глобальный реестр логгеров
_loggers_registry = {}

def get_scraping_logger(job_id: str, config_name: str) -> ScrapingLogger:
    """Получает или создает логгер для задачи"""
    key = f"{job_id}_{config_name}"
    if key not in _loggers_registry:
        _loggers_registry[key] = ScrapingLogger(job_id, config_name)
    return _loggers_registry[key]

def remove_scraping_logger(job_id: str, config_name: str):
    """Удаляет логгер из реестра после завершения задачи"""
    key = f"{job_id}_{config_name}"
    if key in _loggers_registry:
        del _loggers_registry[key] 