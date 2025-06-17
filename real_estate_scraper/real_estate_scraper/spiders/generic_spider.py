# generic_spider.py - ПРАВИЛЬНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ

import scrapy
from scrapy_playwright.page import PageMethod
from ..parsers.loader import load_config, extract_value
import asyncio
import logging
import time
import random

class GenericSpider(scrapy.Spider):
    name = "generic_scraper"
    custom_settings = {
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            'headless': True,
            'timeout': 60000,  # Увеличиваем таймаут запуска браузера
        },
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 60000,  # Увеличиваем таймаут навигации
        'DOWNLOAD_TIMEOUT': 60,  # Увеличиваем общий таймаут загрузки
        'DOWNLOAD_MAXSIZE': 10485760,  # 10MB
        'DOWNLOAD_WARNSIZE': 5242880,  # 5MB
        'RETRY_TIMES': 3,  # Количество повторных попыток
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 522, 524, 408, 429, 403],
        'CONCURRENT_REQUESTS': 2,  # Уменьшаем количество одновременных запросов
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DOWNLOAD_DELAY': 2,  # Задержка между запросами
        'RANDOMIZE_DOWNLOAD_DELAY': True,
    }

    def __init__(self, config=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not config:
            raise ValueError("Path to config file must be provided via -a config=...")
        self.config_path = config
        self.config = load_config(self.config_path)

        self.start_urls = self.config.get("start_urls", [])
        self.selectors = self.config.get("selectors", {})
        self.pagination = self.config.get("pagination", {})
        self.detail_config = self.config.get("detail", {})

        self.max_pages = int(self.config.get("max_pages", 50))
        self.current_page = 1
        
        # Счетчики для отслеживания
        self.processed_items = 0
        self.failed_items = 0

    def parse(self, response):
        item_selector = self.selectors.get("item")
        if not item_selector:
            self.logger.error("Item selector not found in config")
            return

        items_found = 0
        for element in response.css(item_selector):
            items_found += 1
            try:
                item_data = {}
                for key, sel in self.selectors.items():
                    if key == "item":
                        continue

                    # Обработка ошибок для селекторов
                    try:
                        value = None
                        if sel.startswith("xpath:"):
                            xpath_sel = sel[len("xpath:"):]
                            value = element.xpath(xpath_sel).get(default="")
                        elif sel.strip().startswith("//") or sel.strip().startswith(".//"):
                            value = element.xpath(sel).get(default="")
                        else:
                            value = element.css(sel).get(default="")

                        item_data[key] = value.strip() if value else None
                    except Exception as e:
                        self.logger.warning(f"Error extracting field '{key}' with selector '{sel}': {e}")
                        item_data[key] = None

                follow_link = self.detail_config.get("follow_link", False)
                use_playwright = self.detail_config.get("use_playwright", False)

                if follow_link and item_data.get("link"):
                    # Проверка корректности ссылки
                    try:
                        detail_url = response.urljoin(item_data["link"])
                        item_data["link"] = detail_url

                        meta = {
                            "item": item_data,
                            "dont_cache": True,
                            "playwright": True,
                            "playwright_page_methods": [
                                PageMethod("wait_for_load_state", "networkidle"),
                                PageMethod("wait_for_timeout", 2000),  # Ждем загрузки
                            ],
                            "playwright_page_init_callback": self.page_init_callback,
                            "max_retries": 3,  # Максимальное количество попыток
                            "retry_delay": 5000,  # Задержка между попытками
                        }

                        yield scrapy.Request(
                            detail_url,
                            callback=self.parse_detail,
                            meta=meta,
                            errback=self.handle_error,
                            dont_filter=True  # Разрешаем повторные запросы
                        )
                    except Exception as e:
                        self.logger.error(f"Error processing detail link '{item_data.get('link')}': {e}")
                        self.failed_items += 1
                        # Возвращаем элемент без детальной информации
                        yield item_data
                else:
                    yield item_data
                    
            except Exception as e:
                self.logger.error(f"Error processing item: {e}")
                self.failed_items += 1

        self.logger.info(f"Found {items_found} items on page {self.current_page}")

        # Пагинация
        next_page_selector = self.pagination.get("next_page_selector")
        if next_page_selector and self.current_page < self.max_pages:
            try:
                next_page = None
                if next_page_selector.startswith("xpath:"):
                    xpath_next_page_sel = next_page_selector[len("xpath:"):]
                    next_page = response.xpath(xpath_next_page_sel).get()
                elif next_page_selector.strip().startswith("//") or next_page_selector.strip().startswith(".//"):
                    next_page = response.xpath(next_page_selector).get()
                else:
                    next_page = response.css(next_page_selector).get()

                if next_page and not next_page.startswith("javascript:"):
                    self.current_page += 1
                    self.logger.info(f"Following to page {self.current_page}: {next_page}")
                    yield response.follow(
                        next_page, 
                        callback=self.parse,
                        errback=self.handle_error,
                        dont_filter=True
                    )
                else:
                    self.logger.info("No more pages to process")
            except Exception as e:
                self.logger.error(f"Error in pagination: {e}")

    def parse_detail(self, response):
        """Парсинг детальной страницы без return в генераторе"""
        item = response.meta["item"]
        
        try:
            detail_fields = self.detail_config.get("fields", {})
            for key, selector in detail_fields.items():
                try:
                    all_text = (key == "description")
                    multiple_results = (key == "images")

                    item[key] = extract_value(
                        response,
                        selector,
                        all_text=all_text,
                        multiple=multiple_results
                    )
                except Exception as e:
                    self.logger.warning(f"Error extracting detail field '{key}': {e}")
                    item[key] = None

            self.processed_items += 1
            
        except Exception as e:
            self.logger.error(f"Error parsing detail page {response.url}: {e}")
            self.failed_items += 1

        yield item

    async def page_init_callback(self, page, request):
        """Callback для инициализации Playwright страницы"""
        if not page:
            self.logger.warning("Page object is None in page_init_callback")
            return
            
        try:
            # Устанавливаем таймауты
            await page.set_default_timeout(60000)  # 60 секунд
            await page.set_default_navigation_timeout(60000)
            
            # Отключаем загрузку ненужных ресурсов для ускорения
            await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2}", lambda route: route.abort())
            
            # Добавляем обработку ошибок
            page.on("pageerror", lambda err: self.logger.error(f"Page error: {err}"))
            page.on("requestfailed", lambda request: self.logger.warning(f"Request failed: {request.url}"))
            
            # Добавляем случайные задержки
            await page.wait_for_timeout(random.randint(1000, 3000))
            
        except Exception as e:
            self.logger.warning(f"Error in page_init_callback: {e}")

    def handle_error(self, failure):
        """Обработчик ошибок"""
        request = failure.request
        self.logger.error(f"Request failed: {failure.value}")
        
        # Проверяем количество попыток
        retries = request.meta.get('retry_times', 0)
        max_retries = request.meta.get('max_retries', 3)
        
        if retries < max_retries:
            # Увеличиваем счетчик попыток
            request.meta['retry_times'] = retries + 1
            
            # Добавляем задержку перед повторной попыткой
            delay = request.meta.get('retry_delay', 5000)
            self.logger.info(f"Retrying request {request.url} (attempt {retries + 1}/{max_retries}) after {delay}ms")
            
            return scrapy.Request(
                url=request.url,
                callback=request.callback,
                errback=request.errback,
                meta=request.meta,
                dont_filter=True
            )
        else:
            self.logger.error(f"Max retries ({max_retries}) exceeded for {request.url}")
            self.failed_items += 1

    def closed(self, reason):
        """Корректное закрытие спайдера с обработкой асинхронных задач"""
        self.logger.info(f"Spider closed: {reason}")
        self.logger.info(f"Processed items: {self.processed_items}")
        self.logger.info(f"Failed items: {self.failed_items}")
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Получаем все незавершенные задачи
                pending_tasks = [task for task in asyncio.all_tasks(loop) 
                                 if not task.done() and not task.cancelled()]
                
                if pending_tasks:
                    self.logger.info(f"Found {len(pending_tasks)} pending tasks")
                    
                    async def cancel_tasks():
                        for task in pending_tasks:
                            if not task.done() and not task.cancelled():
                                task.cancel()
                                try:
                                    await asyncio.wait_for(task, timeout=1.0)
                                except (asyncio.CancelledError, asyncio.TimeoutError):
                                    pass
                                except Exception as e:
                                    self.logger.warning(f"Error cancelling task: {e}")
                    
                    future = asyncio.run_coroutine_threadsafe(cancel_tasks(), loop)
                    try:
                        future.result(timeout=5)  # Ждем завершения отмены задач
                    except Exception as e:
                        if isinstance(e, asyncio.CancelledError):
                            self.logger.info("Spider tasks were cancelled safely")
                        else:
                            self.logger.warning(f"Error waiting for tasks cancellation: {e}")
                    
        except Exception as e:
            self.logger.warning(f"Error in cleanup: {e}")
            
        # Даем время на завершение всех операций
        time.sleep(1)
        
        try:
            if reason == 'finished':
                self.logger.info("Spider finished successfully")
            else:
                self.logger.warning(f"Spider closed with reason: {reason}")
        except Exception as e:
            self.logger.warning(f"Unhandled exception during spider closure: {e}")
