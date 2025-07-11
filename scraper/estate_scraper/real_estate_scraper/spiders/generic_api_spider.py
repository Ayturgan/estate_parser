import scrapy
import asyncio
import os
import json
from urllib.parse import urljoin, urlencode, urlparse, parse_qs
from ..parsers.loader import load_config
from ..logger import get_scraping_logger


class UniversalSpider(scrapy.Spider):
    name = "generic_api"
    handle_httpstatus_list = [200, 400, 401, 403, 404, 429, 500, 502, 503]  # Обрабатываем все статус коды
    
    def __init__(self, config=None, job_id=None, *args, **kwargs):
        super(UniversalSpider, self).__init__(*args, **kwargs)
        if not config:
            raise ValueError("Config parameter is required")
            
        # Если передан путь с расширением - используем как есть
        if config.endswith('.yml') or config.endswith('.yaml'):
            self.config_path = config
        else:
            # Иначе строим путь к конфигу по имени
            current_dir = os.path.dirname(os.path.abspath(__file__))
            configs_dir = os.path.join(os.path.dirname(current_dir), "configs")
            self.config_path = os.path.join(configs_dir, f"{config}.yml")
        
        self.config = load_config(self.config_path)
        
        # Мультикатегорийная структура - ИНИЦИАЛИЗИРУЕМ ПЕРЕД validate_config()
        self.base_url = self.config.get("base_url", "")
        self.categories = self.config.get("categories", [])
        self.api_settings = self.config.get("api_settings", {})
        
        # Валидируем конфиг ПОСЛЕ инициализации атрибутов  
        self.validate_config()
        self.api_fields = self.config.get("api_fields", {})
        self.data_processing = self.config.get("data_processing", {})
        
        # Инициализируем детальное логирование
        self.job_id = job_id or os.environ.get('SCRAPY_JOB_ID', 'unknown')
        self.config_name = os.environ.get('SCRAPY_CONFIG_NAME', config or 'unknown')
        self.scraping_logger = get_scraping_logger(self.job_id, self.config_name)
        
        # Настройки парсинга
        self.parse_all_listings = self.config.get("parse_all_listings", True)
        self.max_items_limit = int(self.config.get("max_items_limit", 100))
        self.scraped_items_count = 0
        self.category_items_count = {}  # Счетчик по категориям
        
        # Счетчики для прогресса
        self.total_items_expected = 0
        self.progress_update_interval = 10  # Обновляем прогресс каждые 10 элементов

    def validate_config(self):
        """Проверяет обязательные поля в конфиге"""
        required_fields = ['base_url', 'categories', 'api_settings']
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"Missing required field '{field}' in config")

        if not self.categories:
            raise ValueError("No categories defined in config")

    def start_requests(self):
        """Главный метод запуска с рабочей логикой"""
        # Определяем главную страницу для получения кук
        main_url = self.base_url.replace('/api/search/v3/feed/search', '')
        if not main_url.endswith('/'):
            main_url += '/'
            
        # Получаем куки через Playwright (РАБОЧАЯ ЛОГИКА!)
        if self.config.get('use_playwright', True):
            try:
                # Используем существующий event loop Scrapy
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Если цикл уже запущен, используем создание задачи
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(self._run_playwright_sync, main_url)
                            cookies, headers = future.result(timeout=30)
                    else:
                        cookies, headers = loop.run_until_complete(self.get_cookies_and_headers(main_url))
                except RuntimeError:
                    # Если проблемы с циклом, запускаем синхронно
                    cookies, headers = self._run_playwright_sync(main_url)
                
                cookie_header = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                
                base_headers = {
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Cookie': cookie_header,
                    'X-Requested-With': 'XMLHttpRequest',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'device': 'pc',
                    'country-id': '12',
                    'language': 'ru_RU'
                }
                
                self.logger.info(f"🍪 Получены куки авторизации: {len(cookies)} cookies")
                self.logger.info(f"🍪 Cookie header: {cookie_header[:100]}...")
                
            except Exception as e:
                self.logger.error(f"Error getting cookies and headers: {e}")
                base_headers = {
                    'Accept': 'application/json, text/plain, */*',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'device': 'pc',
                    'country-id': '12',
                    'language': 'ru_RU'
                }
        else:
            base_headers = {
                'Accept': 'application/json, text/plain, */*',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'device': 'pc',
                'country-id': '12',
                'language': 'ru_RU'
            }

        # Генерируем запросы для всех категорий
        for category in self.categories:
            start_page = self.api_settings.get("start_page", 1)
            category_id = category.get("category_id")
            
            if not category_id:
                self.logger.error(f"Missing category_id for category: {category}")
                continue
            
            api_url = self._build_api_url(category_id, start_page)
            
            # Создаем заголовки с правильным рефераром для каждой категории
            headers_to_use = base_headers.copy()
            headers_to_use['Referer'] = category.get('referer', main_url)
            
            # Логируем заголовки перед отправкой
            self.logger.info(f"🚀 Отправляем запрос для категории {category['name']} (ID: {category_id})")
            self.logger.info(f"🚀 URL: {api_url}")
            self.logger.info(f"🚀 Referer: {headers_to_use['Referer']}")
            
            yield scrapy.Request(
                url=api_url,
                headers=headers_to_use,
                callback=self.parse_api,
                meta={
                    'category': category,
                    'page': start_page,
                    'headers': headers_to_use  # Передаем заголовки в meta
                },
                errback=self.handle_error,
                dont_filter=True
            )

    def _run_playwright_sync(self, main_url):
        """Синхронный метод для запуска Playwright в отдельном потоке"""
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.get_cookies_and_headers(main_url))
            finally:
                loop.close()
        
        return run_async()
    
    async def get_cookies_and_headers(self, main_url):
        """Получает куки и заголовки через Playwright (РАБОЧАЯ ЛОГИКА!)"""
        playwright_config = self.config.get('playwright', {})
        headless = playwright_config.get('headless', True)
        sleep_time = playwright_config.get('sleep_time', 3)
        
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=headless)
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                
                page = await context.new_page()
                await page.goto(main_url)
                await asyncio.sleep(sleep_time)
                
                cookies = await context.cookies()
                await browser.close()
                
                # Детальное логирование кук
                self.logger.info(f"🍪 Получено {len(cookies)} кук через Playwright:")
                for cookie in cookies:
                    self.logger.info(f"🍪   - {cookie['name']}: {cookie['value'][:50]}{'...' if len(cookie['value']) > 50 else ''}")
                
                headers = {
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                return cookies, headers
        except Exception as e:
            self.logger.error(f"Error getting cookies and headers: {e}")
            return [], {}

    def _build_api_url(self, category_id, page):
        """Строит URL для API запроса"""
        url_format = self.api_settings.get("url_format", "{base_url}?category_id={category_id}&page={page}")
        per_page = self.api_settings.get("per_page", 20)
        
        # Для первой страницы не добавляем параметр page
        if page <= 1:
            # Убираем &page={page} из URL для первой страницы
            url_format = url_format.replace("&page={page}", "").replace("?page={page}&", "?").replace("?page={page}", "")
            return url_format.format(
                base_url=self.base_url,
                category_id=category_id,
                per_page=per_page
            )
        else:
            return url_format.format(
                base_url=self.base_url,
                category_id=category_id,
                per_page=per_page,
                page=page
            )

    def parse_api(self, response):
        """Парсит API ответ согласно конфигурации (АДАПТИРОВАННАЯ ЛОГИКА)"""
        category = response.meta.get('category')
        current_page = response.meta.get('page', 1)
        headers = response.meta.get('headers', {})
        
        # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ СТАТУС КОДА И ОТВЕТА
        self.logger.info(f"📡 API Response: {response.status} for {response.url}")
        self.logger.info(f"📡 Response headers: {dict(response.headers)}")
        
        if response.status != 200:
            self.logger.error(f"🚫 API вернул статус {response.status} для {response.url}")
            self.logger.error(f"🚫 Response text (first 1000 chars): {response.text[:1000]}")
            return
        
        if not category:
            self.logger.error("Category not found in response meta")
            return
        
        try:
            data = response.json()
            self.logger.info(f"✅ Успешно получены JSON данные, ключи: {list(data.keys()) if isinstance(data, dict) else type(data)}")
        except ValueError as e:
            self.logger.error(f"Invalid JSON in response from {response.url}: {e}")
            self.logger.debug(f"Response text: {response.text[:500]}...")
            return

        # Получаем список объявлений
        items_key = self.api_fields.get('items_key', 'items')
        items = self._get_nested_value(data, items_key)
        
        if not isinstance(items, list):
            self.logger.warning(f"Expected items to be a list, got: {type(items)} for key '{items_key}'")
            self.logger.debug(f"Data structure: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            return

        # Инициализируем счетчик для категории если нужно
        category_name = category['name']
        if category_name not in self.category_items_count:
            self.category_items_count[category_name] = 0
        
        items_processed = 0
        for item in items:
            # Проверяем лимит объявлений ПО КАТЕГОРИЯМ если parse_all_listings = False
            if not self.parse_all_listings and self.category_items_count[category_name] >= self.max_items_limit:
                self.logger.info(f"Reached max items limit for category '{category_name}': {self.max_items_limit}")
                break
                
            try:
                processed_item = self._process_api_item(item, category)
                if processed_item:
                    items_processed += 1
                    self.scraped_items_count += 1  # Общий счетчик для статистики
                    self.category_items_count[category_name] += 1  # Счетчик по категории
                    
                    # Обновляем прогресс каждые N элементов
                    if self.scraped_items_count % self.progress_update_interval == 0:
                        self._update_progress()
                    
                    yield processed_item
                    
            except Exception as e:
                self.logger.error(f"Error processing item: {e}")
                continue
        
        self.logger.info(f"Processed {items_processed} items from page {current_page} for category {category['name']}")
        self.scraping_logger.log_page_processed(current_page, items_processed, response.url)
        
        # Проверяем пагинацию
        if self._should_continue_pagination(items_processed, category):
            yield from self._handle_pagination(response, category, current_page, headers)

    def _process_api_item(self, item, category):
        """Обрабатывает один элемент из API"""
        try:
            result = {
                # Точная классификация из category_id
                'property_type': category['property_type'],
                'listing_type': category['listing_type'],
                'source': self.config.get('source_name', 'unknown'),
                'category_name': category['name'],
                'category_id': category.get('category_id')
            }
            
            # Обрабатываем поля API
            item_fields = self.api_fields.get('item_fields', {})
            for output_field, input_path in item_fields.items():
                try:
                    value = self._get_nested_value(item, input_path)
                    result[output_field] = value
                except Exception as e:
                    self.logger.warning(f"Error processing field '{output_field}': {e}")
                    result[output_field] = None
            
            # Построение полного URL объявления
            url_building = self.config.get('url_building', {})
            if url_building and result.get('url'):
                pattern = url_building.get('pattern', '')
                if pattern:
                    result['url'] = pattern.format(**result)
            
            # Валидация и очистка
            validated_result = self._validate_and_clean_item(result)
            return validated_result
            
        except Exception as e:
            self.logger.error(f"Error processing API item: {e}")
            return None

    def _get_nested_value(self, data, path):
        """Получает значение по вложенному пути (например, 'data.items.0.title')"""
        if not path or not data:
            return None
            
        try:
            keys = str(path).split('.')
            value = data
            
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                elif isinstance(value, list) and key.isdigit():
                    index = int(key)
                    value = value[index] if 0 <= index < len(value) else None
                else:
                    return None
                    
                if value is None:
                    return None
                    
            return value
            
        except Exception as e:
            self.logger.warning(f"Error getting nested value for path '{path}': {e}")
            return None

    def _update_progress(self):
        """Отправляет обновление прогресса"""
        try:
            # Вычисляем примерный прогресс
            total_categories = len(self.categories)
            processed_categories = len([cat for cat in self.categories if self.category_items_count.get(cat['name'], 0) > 0])
            
            if total_categories > 0:
                progress = min(95, int((processed_categories / total_categories) * 100))
            else:
                progress = 0
            
            # Логируем прогресс (WebSocket прогресс обрабатывается автоматически)
            self.logger.info(f"Прогресс: {progress}%, спарсено: {self.scraped_items_count}")
                
        except Exception as e:
            self.logger.error(f"Ошибка обновления прогресса: {e}")

    def _validate_and_clean_item(self, item):
        """Валидация и базовая очистка данных"""
        try:
            # Проверка обязательных полей
            required_fields = self.data_processing.get('validate_required_fields', [])
            for field in required_fields:
                if not item.get(field):
                    self.logger.warning(f"Missing required field '{field}' in item")
                    return None
            
            # Очистка строковых полей
            string_fields = ['title', 'description', 'city', 'district', 'address']
            for field in string_fields:
                if field in item and item[field]:
                    if isinstance(item[field], str):
                        item[field] = item[field].strip()
                        if not item[field]:  # Если после очистки пустая строка
                            item[field] = None
            
            # Обработка булевых полей (убрали is_realtor, так как это поле больше не используется)
            bool_fields = []
            for field in bool_fields:
                if field in item and item[field] is not None:
                    item[field] = bool(item[field])
            
            return item
            
        except Exception as e:
            self.logger.error(f"Error validating item: {e}")
            return None

    def _should_continue_pagination(self, items_on_current_page, category):
        """Проверяет нужно ли продолжать пагинацию для конкретной категории"""
        category_name = category['name']
        
        # Прекращаем если достигли лимита по категории
        if not self.parse_all_listings and self.category_items_count.get(category_name, 0) >= self.max_items_limit:
            return False
        
        # Прекращаем если на текущей странице нет объявлений
        if items_on_current_page == 0:
            return False
        
        # Прекращаем если получили меньше объявлений чем ожидали на страницу
        per_page = self.api_settings.get("per_page", 20)
        if items_on_current_page < per_page:
            return False
                
        return True

    def _handle_pagination(self, response, category, current_page, headers):
        """Обрабатывает пагинацию для API"""
        try:
            next_page = current_page + 1
            next_url = self._build_api_url(category.get('category_id'), next_page)
            
            self.logger.info(f"Following to page {next_page} for category {category['name']}: {next_url}")
            
            yield scrapy.Request(
                url=next_url,
                headers=headers,  # Передаем те же заголовки с куками
                callback=self.parse_api,
                meta={
                    'category': category,
                    'page': next_page,
                    'headers': headers
                },
                errback=self.handle_error,
                dont_filter=True
            )
                
        except Exception as e:
            self.logger.error(f"Error in pagination: {e}")

    def handle_error(self, failure):
        """Обработка ошибок"""
        try:
            self.logger.error(f"Request failed: {failure.request.url}")
            self.logger.error(f"Error: {failure.value}")
            self.scraping_logger.log_request_failure(failure.request.url, str(failure.value))
        except Exception as e:
            self.logger.error(f"Error in error handler: {e}")

    def closed(self, reason):
        """Завершение работы спайдера"""
        try:
            # Финальное обновление прогресса
            self._update_progress()
            
            stats = {
                'scraped_items': self.scraped_items_count,
                'reason': reason,
                'category_breakdown': self.category_items_count
            }
            
            self.logger.info(f"Spider closed: {stats}")
            
            # Детальная статистика по категориям
            self.logger.info(f"📊 Статистика по категориям:")
            for category_name, count in self.category_items_count.items():
                self.logger.info(f"  📂 {category_name}: {count} объявлений")
            
            self.scraping_logger.log_spider_finished(stats)
            
        except Exception as e:
            self.logger.error(f"Error in spider close: {e}")
