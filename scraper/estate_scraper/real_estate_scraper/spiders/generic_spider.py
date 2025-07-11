import scrapy
from scrapy_playwright.page import PageMethod
from ..parsers.loader import load_config, extract_value
import time
import random
import os
from ..logger import get_scraping_logger

class GenericSpider(scrapy.Spider):
    name = "generic_scraper"
    custom_settings = {
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            'headless': True,
            'timeout': 60000,
        },
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 60000,
        'DOWNLOAD_TIMEOUT': 60,
        'DOWNLOAD_MAXSIZE': 10485760,
        'DOWNLOAD_WARNSIZE': 5242880,
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 522, 524, 408, 429, 403],
        'CONCURRENT_REQUESTS': 8,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
        'DOWNLOAD_DELAY': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
    }

    def __init__(self, config=None, job_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not config:
            raise ValueError("Path to config file must be provided via -a config=...")
        self.config_path = config
        self.config = load_config(self.config_path)

        # Мультикатегорийная структура
        self.base_url = self.config.get("base_url", "")
        self.categories = self.config.get("categories", [])
        self.selectors = self.config.get("selectors", {})
        self.pagination = self.config.get("pagination", {})
        self.data_processing = self.config.get("data_processing", {})
        
        # Генерируем start_urls для всех категорий
        self.start_urls = []
        for category in self.categories:
            start_page = self.pagination.get("start_page", 1)
            page_url_format = self.pagination.get("page_url_format", "{base_url}{category_url}?page={page}")
            
            start_url = page_url_format.format(
                base_url=self.base_url,
                category_url=category["url"],
                page=start_page
            )
            self.start_urls.append(start_url)

        # Настройки парсинга
        self.parse_all_listings = self.config.get("parse_all_listings", True)
        self.max_items_limit = int(self.config.get("max_items_limit", 100))
        
        self.processed_items = 0
        self.failed_items = 0
        self.scraped_items_count = 0  # Общий счетчик для статистики
        self.category_items_count = {}  # Счетчик по категориям
        
        # Инициализируем детальное логирование
        self.job_id = job_id or os.environ.get('SCRAPY_JOB_ID', 'unknown')
        self.config_name = os.environ.get('SCRAPY_CONFIG_NAME', config or 'unknown')
        self.scraping_logger = get_scraping_logger(self.job_id, self.config_name)
        
        # Счетчики для прогресса
        self.total_items_expected = 0
        self.progress_update_interval = 10  # Обновляем прогресс каждые 10 элементов

    def start_requests(self):
        """Генерируем запросы для всех категорий"""
        for url in self.start_urls:
            # Определяем категорию по URL
            category = self._get_category_from_url(url)
            if category:
                yield scrapy.Request(
                    url,
                    callback=self.parse,
                    meta={
                        'category': category,
                        'page': self.pagination.get("start_page", 1)
                    },
                    errback=self.handle_error,
                    dont_filter=True
                )

    def _get_category_from_url(self, url):
        """Определяет категорию по URL"""
        for category in self.categories:
            if category["url"] in url:
                return category
        return None

    def parse(self, response):
        category = response.meta.get('category')
        current_page = response.meta.get('page', 1)
        
        if not category:
            self.logger.error("Category not found in response meta")
            return

        ads_list_selector = self.selectors.get("ads_list")
        ad_card_selector = self.selectors.get("ad_card")
        
        if not ads_list_selector or not ad_card_selector:
            self.logger.error("Required selectors (ads_list, ad_card) not found in config")
            return

        ads_container = response.css(ads_list_selector)
        if not ads_container:
            self.logger.warning(f"No ads container found with selector: {ads_list_selector}")
            return

        category_name = category['name']
        if category_name not in self.category_items_count:
            self.category_items_count[category_name] = 0

        items_found = 0
        for element in ads_container.css(ad_card_selector):
            if not self.parse_all_listings and self.category_items_count[category_name] >= self.max_items_limit:
                self.logger.info(f"Reached max items limit for category '{category_name}': {self.max_items_limit}")
                return
                
            items_found += 1
            self.scraped_items_count += 1
            self.category_items_count[category_name] += 1
            
            # Обновляем прогресс каждые N элементов
            if self.scraped_items_count % self.progress_update_interval == 0:
                self._update_progress()
                
            try:
                # Собираем только основные поля (без details)
                item_data = self._extract_item_data(element, category, only_main=True)
                detail_url = item_data.get('url')
                details_selectors = self.selectors.get('details', {})
                if detail_url and details_selectors:
                    # Переходим на детальную страницу
                    yield scrapy.Request(
                        detail_url,
                        callback=self.parse_details,
                        meta={'item_data': item_data, 'category': category},
                        errback=self.handle_error,
                        dont_filter=True
                    )
                else:
                    yield item_data
            except Exception as e:
                self.logger.error(f"Error processing item: {e}")
                self.failed_items += 1

        self.logger.info(f"Found {items_found} items on page {current_page} for category {category['name']}")
        self.scraping_logger.log_page_processed(current_page, items_found, response.url)

        # Если не найдено ни одного объявления — прекращаем пагинацию для этой категории
        if items_found == 0:
            self.logger.info(f"На странице {current_page} для категории {category['name']} не найдено объявлений, прекращаем пагинацию.")
            return

        if self._should_continue_pagination(category):
            yield from self._handle_pagination(response, category, current_page)

    def _extract_item_data(self, element, category, only_main=False):
        """Извлекает данные объявления. only_main=True — только основные поля, без details."""
        try:
            item_data = {
                'property_type': category['property_type'],
                'listing_type': category['listing_type'],
                'source': self.config.get('source_name', 'unknown'),
                'category_name': category['name']
            }
            basic_fields = ['title', 'url', 'price', 'location', 'description', 'image']
            for field in basic_fields:
                selector = self.selectors.get(field)
                if selector:
                    value = self._extract_field_value(element, selector)
                    item_data[field] = value
            if not only_main:
                details = self.selectors.get('details', {})
                for field, selector in details.items():
                    value = self._extract_field_value(element, selector)
                    item_data[field] = value
            if item_data.get('url') and not item_data['url'].startswith('http'):
                item_data['url'] = self.base_url + item_data['url']
            return item_data
        except Exception as e:
            self.logger.error(f"Error extracting item data: {e}")
            return None

    def _extract_field_value(self, element, selector):
        """Извлекает значение поля по селектору"""
        try:
            if selector.startswith("xpath:"):
                xpath_sel = selector[len("xpath:"):]
                return element.xpath(xpath_sel).get(default="").strip()
            elif selector.strip().startswith("//") or selector.strip().startswith(".//"):
                return element.xpath(selector).get(default="").strip()
            else:
                return element.css(selector).get(default="").strip()
        except Exception as e:
            self.logger.warning(f"Error extracting field with selector '{selector}': {e}")
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

    def _should_continue_pagination(self, category):
        """Проверяет нужно ли продолжать пагинацию для конкретной категории"""
        category_name = category['name']
        if not self.parse_all_listings and self.category_items_count.get(category_name, 0) >= self.max_items_limit:
            return False
        return True

    def _handle_pagination(self, response, category, current_page):
        """Обрабатывает пагинацию"""
        try:
            next_page = current_page + 1
            page_url_format = self.pagination.get("page_url_format", "{base_url}{category_url}?page={page}")
            
            next_url = page_url_format.format(
                base_url=self.base_url,
                category_url=category["url"],
                page=next_page
            )
            
            self.logger.info(f"Following to page {next_page} for category {category['name']}: {next_url}")
            
            yield scrapy.Request(
                next_url,
                callback=self.parse,
                meta={
                    'category': category,
                    'page': next_page
                },
                errback=self.handle_error,
                dont_filter=True
            )
            
        except Exception as e:
            self.logger.error(f"Error in pagination: {e}")

    async def page_init_callback(self, page, request):
        """Инициализация страницы для Playwright"""
        try:
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            ]
            
            await page.set_extra_http_headers({
                "User-Agent": random.choice(user_agents),
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            })
            
            await page.evaluate("() => { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }) }")
            
        except Exception as e:
            self.logger.warning(f"Error in page initialization: {e}")

    def handle_error(self, failure):
        """Обработка ошибок"""
        try:
            self.logger.error(f"Request failed: {failure.request.url}")
            self.logger.error(f"Error: {failure.value}")
            self.scraping_logger.log_request_failure(failure.request.url, str(failure.value))
            self.failed_items += 1
        except Exception as e:
            self.logger.error(f"Error in error handler: {e}")

    def closed(self, reason):
        """Завершение работы спайдера"""
        try:
            # Финальное обновление прогресса
            self._update_progress()
            
            total_processed = self.processed_items + self.failed_items
            success_rate = (self.processed_items / total_processed * 100) if total_processed > 0 else 0
            
            stats = {
                'scraped_items': self.scraped_items_count,
                'processed_items': self.processed_items,
                'failed_items': self.failed_items,
                'success_rate': f"{success_rate:.1f}%",
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

    def parse_details(self, response):
        """Парсит детальные данные на странице объявления и объединяет с item_data из meta."""
        item_data = response.meta['item_data']
        category = response.meta['category']
        details = self.selectors.get('details', {})
        for field, selector in details.items():
            value = self._extract_field_value(response, selector)
            item_data[field] = value
        yield item_data

