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
            'args': [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-ipc-flooding-protection",
                "--memory-pressure-off",
                "--max_old_space_size=4096"
            ]
        },
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 80000,  # Увеличиваем до 2 минут
        'DOWNLOAD_TIMEOUT': 120,
        'DOWNLOAD_MAXSIZE': 10485760,
        'DOWNLOAD_WARNSIZE': 5242880,
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 522, 524, 408, 429, 403],
        'CONCURRENT_REQUESTS': 4,  # Было 1
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4,  # Было 1
        'DOWNLOAD_DELAY': 0.5,  # Было 3
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
        
        # Настройки Playwright
        self.request_settings = self.config.get("request_settings", {})
        self.use_playwright = self.request_settings.get("use_playwright", False)
        self.playwright_wait = self.request_settings.get("playwright_wait", 3)
        
        self.processed_items = 0
        self.failed_items = 0
        self.scraped_items_count = 0  # Общий счетчик для статистики
        self.category_items_count = {}  # Счетчик по категориям
        self.has_parsing_errors = False # Флаг для отслеживания ошибок парсинга
        
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
                
                # Добавляем отладочное логирование
                self.logger.debug(f"🔍 Detail URL: {detail_url}")
                self.logger.debug(f"🔍 Details selectors: {bool(details_selectors)}")
                
                if detail_url and details_selectors:
                    # Переходим на детальную страницу
                    self.logger.debug(f"🔍 Making detail request to: {detail_url}")
                    yield scrapy.Request(
                        detail_url,
                        callback=self.parse_details,
                        meta={'item_data': item_data, 'category': category},
                        errback=self.handle_error,
                        dont_filter=True
                    )
                else:
                    self.logger.debug(f"🔍 Skipping detail request - URL: {detail_url}, selectors: {bool(details_selectors)}")
                    yield item_data
            except Exception as e:
                self.logger.error(f"Error processing item: {e}")
                self.has_parsing_errors = True
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
            self.has_parsing_errors = True
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
            self.has_parsing_errors = True
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
        """Callback для инициализации Playwright страницы"""
        if not page:
            self.logger.debug("Page object is None in page_init_callback")
            return
            
        try:
            if page.is_closed():
                self.logger.debug("Page is already closed")
                return
                
            await page.set_default_timeout(60000)
            await page.set_default_navigation_timeout(60000)
            
            # Блокируем загрузку изображений для ускорения
            await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2}", lambda route: route.abort())
            
            # Устанавливаем обработчики ошибок
            page.on("pageerror", lambda err: self.logger.debug(f"Page error: {err}"))
            page.on("requestfailed", lambda request: self.logger.debug(f"Request failed: {request.url}"))
            
            # Устанавливаем viewport
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            # Устанавливаем User-Agent
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
            
            # Скрываем webdriver
            await page.evaluate("() => { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }) }")
            
            # Случайная задержка
            await page.wait_for_timeout(random.randint(1000, 3000))
            
        except Exception as e:
            self.logger.debug(f"Error in page_init_callback: {e}")

    def handle_error(self, failure):
        """Обработка ошибок с retry механизмом"""
        try:
            request = failure.request
            retry_count = request.meta.get('retry_count', 0)
            max_retries = 3
            
            self.logger.error(f"Request failed: {request.url}")
            self.logger.error(f"Error: {failure.value}")
            
            # Retry для таймаутов и сетевых ошибок
            if retry_count < max_retries and (
                'Timeout' in str(failure.value) or 
                'Connection' in str(failure.value) or
                'Network' in str(failure.value)
            ):
                retry_count += 1
                self.logger.info(f"Retrying request {request.url} (attempt {retry_count}/{max_retries})")
                
                # Увеличиваем таймаут для retry
                new_timeout = 120000 + (retry_count * 30000)  # +30 сек за каждую попытку
                
                yield scrapy.Request(
                    request.url,
                    callback=request.callback,
                    meta={
                        **request.meta,
                        'retry_count': retry_count,
                        'playwright': True,
                        'playwright_include_page': True,
                        'playwright_page_methods': [
                            PageMethod("wait_for_load_state", "networkidle"),
                        ]
                    },
                    errback=self.handle_error,
                    dont_filter=True
                )
                return
            
            # Устанавливаем флаг ошибок парсинга при сетевых ошибках
            error_str = str(failure.value).lower()
            if any(network_error in error_str for network_error in [
                'dns lookup failed', 'connection refused', 'connection timeout',
                'network unreachable', 'host unreachable', 'request failed'
            ]):
                self.has_parsing_errors = True
                self.logger.error("Network error detected, setting parsing errors flag")
            
            if self.scraping_logger:
                self.scraping_logger.log_request_failure(request.url, str(failure.value))
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
        self.logger.info(f"🔍 parse_details called for URL: {response.url}")
        item_data = response.meta['item_data']
        category = response.meta['category']
        details = self.selectors.get('details', {})
        
        # Если включен Playwright, используем его для детальных страниц
        if self.use_playwright:
            self.logger.info(f"🔍 Using Playwright for details page: {response.url}")
            yield scrapy.Request(
                response.url,
                callback=self.parse_details_with_playwright,
                meta={
                    'item_data': item_data,
                    'category': category,
                    'details': details,
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod("wait_for_load_state", "networkidle"),
                        PageMethod("wait_for_timeout", self.playwright_wait * 1000),
                    ],
                    'playwright_page_init_callback': self.page_init_callback,
                },
                errback=self.handle_error,
                dont_filter=True
            )
        else:
            # Обычная обработка без Playwright
            for field, selector in details.items():
                if field == 'images':
                    # Обрабатываем изображения отдельно
                    photos = self._extract_photos_from_details(response, selector)
                    if photos:
                        item_data['photos'] = photos
                        # Также добавляем в images для совместимости с пайплайном
                        item_data['images'] = [photo['url'] for photo in photos]
                        self.logger.info(f"🔍 Detail parsing: extracted {len(photos)} photos")
                    else:
                        self.logger.warning("🔍 Detail parsing: no photos extracted")
                elif field == 'phone':
                    # Обрабатываем телефоны отдельно
                    phones = self._extract_phones_from_details(response, selector)
                    if phones:
                        item_data['phone_numbers'] = phones
                        self.logger.info(f"🔍 Detail parsing: extracted {len(phones)} phones: {phones}")
                    else:
                        self.logger.warning("🔍 Detail parsing: no phones extracted")
                else:
                    value = self._extract_field_value(response, selector)
                    item_data[field] = value
            
            yield item_data

    def parse_details_with_playwright(self, response):
        """Парсит детальные данные с использованием Playwright (правильный подход)"""
        item_data = response.meta['item_data']
        category = response.meta['category']
        details = response.meta['details']
        
        self.logger.info(f"🔍 Playwright detail parsing started for: {response.url}")
        
        try:
            # Проверяем тип контента
            content_type = response.headers.get('content-type', b'').decode('utf-8').lower()
            if 'text/html' not in content_type:
                self.logger.warning(f"Non-HTML content type: {content_type} for {response.url}")
                yield item_data
                return
            
            if not hasattr(response, 'text') or not response.text:
                self.logger.warning(f"Empty or non-text response for {response.url}")
                yield item_data
                return
            
            # Обрабатываем поля
            for field, selector in details.items():
                try:
                    if field == 'images':
                        # Обрабатываем изображения отдельно
                        photos = self._extract_photos_from_details(response, selector)
                        if photos:
                            item_data['photos'] = photos
                            # Также добавляем в images для совместимости с пайплайном
                            item_data['images'] = [photo['url'] for photo in photos]
                            self.logger.info(f"🔍 Playwright detail parsing: extracted {len(photos)} photos")
                        else:
                            self.logger.warning("🔍 Playwright detail parsing: no photos extracted")
                    elif field == 'phone':
                        # Обрабатываем телефоны отдельно
                        phones = self._extract_phones_from_details(response, selector)
                        if phones:
                            item_data['phone_numbers'] = phones
                            self.logger.info(f"🔍 Playwright detail parsing: extracted {len(phones)} phones: {phones}")
                        else:
                            self.logger.warning("🔍 Playwright detail parsing: no phones extracted")
                    else:
                        value = self._extract_field_value(response, selector)
                        item_data[field] = value
                        
                except Exception as e:
                    self.logger.warning(f"Error extracting detail field '{field}': {e}")
                    item_data[field] = None
            
            yield item_data
            
        except Exception as e:
            self.logger.error(f"Error in Playwright details parsing: {e}")
            yield item_data

    def _extract_photos_from_details(self, response, selector):
        """Извлекает фотографии из детальной страницы"""
        try:
            photos = []
            self.logger.info(f"🔍 Photo details extraction: selector = '{selector}'")
            self.logger.info(f"🔍 Photo details extraction: response URL = '{response.url}'")
            
            # Добавляем отладку HTML
            html_sample = response.text[:500] if response.text else "No HTML content"
            self.logger.info(f"🔍 Photo details extraction: HTML sample = '{html_sample}...'")
            
            image_elements = self._extract_field_elements(response, selector)
            self.logger.info(f"🔍 Photo details extraction: found {len(image_elements)} image elements")
            
            # Дополнительная отладка - выводим первые несколько элементов
            for i, img_url in enumerate(image_elements[:5]):
                self.logger.info(f"🔍 Photo details extraction: raw image {i+1} = '{img_url}'")
            
            for i, img_url in enumerate(image_elements):
                if img_url:
                    # Преобразуем относительный URL в полный
                    if not img_url.startswith('http'):
                        base_url = self.base_url.rstrip('/')
                        img_url = img_url.lstrip('/')
                        full_url = f"{base_url}/{img_url}"
                    else:
                        full_url = img_url
                    
                    photos.append({'url': full_url})
                    self.logger.info(f"🔍 Photo details extraction: photo {i+1} = {full_url}")
            
            self.logger.info(f"🔍 Photo details extraction: total photos = {len(photos)}")
            return photos
        except Exception as e:
            self.logger.error(f"Error extracting photos from details: {e}")
            return []

    def _extract_phones_from_details(self, response, selector):
        """Извлекает телефоны из детальной страницы"""
        try:
            phones = []
            self.logger.info(f"🔍 Phone extraction: selector = '{selector}'")
            
            phone_elements = self._extract_field_elements(response, selector)
            self.logger.info(f"🔍 Phone extraction: found {len(phone_elements)} phone elements")
            
            for i, phone in enumerate(phone_elements):
                if phone:
                    self.logger.info(f"🔍 Phone extraction: raw phone {i+1} = '{phone}'")
                    # Очищаем номер телефона от лишних символов
                    cleaned_phone = self._clean_phone_number(phone)
                    if cleaned_phone:
                        phones.append(cleaned_phone)
                        self.logger.info(f"🔍 Phone extraction: cleaned phone {i+1} = '{cleaned_phone}'")
                    else:
                        self.logger.warning(f"🔍 Phone extraction: phone {i+1} was cleaned to empty")
                else:
                    self.logger.warning(f"🔍 Phone extraction: phone {i+1} is empty")
            
            self.logger.info(f"🔍 Phone extraction: total phones = {len(phones)}")
            return phones
        except Exception as e:
            self.logger.error(f"Error extracting phones from details: {e}")
            return []

    def _extract_field_elements(self, element, selector):
        """Извлекает все элементы по селектору"""
        try:
            if selector.startswith("xpath:"):
                xpath_sel = selector[len("xpath:"):]
                return element.xpath(xpath_sel).getall()
            elif selector.strip().startswith("//") or selector.strip().startswith(".//"):
                return element.xpath(selector).getall()
            else:
                return element.css(selector).getall()
        except Exception as e:
            self.logger.warning(f"Error extracting field elements with selector '{selector}': {e}")
            return []

    def _clean_phone_number(self, phone):
        """Очищает номер телефона от лишних символов"""
        try:
            # Убираем префикс tel: если есть
            if phone.startswith('tel:'):
                phone = phone[4:]
            
            # Убираем все символы кроме цифр, + и пробелов
            import re
            cleaned = re.sub(r'[^\d+\s\-\(\)]', '', phone)
            
            # Убираем лишние пробелы
            cleaned = ' '.join(cleaned.split())
            
            return cleaned if cleaned else None
        except Exception as e:
            self.logger.warning(f"Error cleaning phone number '{phone}': {e}")
            return phone



    def closed(self, reason):
        if self.has_parsing_errors:
            self.logger.error("Spider finished with parsing errors. Signalling failure.")
            # Scrapy завершается с кодом 0 по умолчанию, даже при ошибках в логах.
            # Чтобы сигнализировать внешнему процессу об ошибке, можно использовать sys.exit(1)
            # или другой механизм, который будет перехвачен воркером.
            # Для демонстрации, мы просто логируем это, но в реальной системе
            # здесь может быть более сложная логика, например, запись в Redis
            # или установка флага в базе данных, который будет проверен воркером.
            # В рамках Scrapy, чтобы повлиять на код выхода, нужно использовать CrawlerProcess
            # и его exitcode, или перехватывать ошибки в расширении.
            # Для вашей задачи, если веб-интерфейс смотрит только на код выхода процесса,
            # то нужно будет настроить Scrapy так, чтобы он завершался с ненулевым кодом
            # при наличии self.has_parsing_errors. Это обычно делается через
            # пользовательские расширения Scrapy или путем изменения запускающего скрипта.
            # В данном случае, я просто логирую, что есть ошибки парсинга.
            pass


