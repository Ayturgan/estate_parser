import scrapy
import random
from scrapy_playwright.page import PageMethod
from ..parsers.loader import load_config
from ..logger import get_scraping_logger
import logging
import os


class GenericShowMoreSimpleSpider(scrapy.Spider):
    name = "generic_show_more_simple"
    custom_settings = {
        'DOWNLOAD_HANDLERS': {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        'PLAYWRIGHT_LAUNCH_OPTIONS': {
            "headless": True,
            "args": [
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
        'PLAYWRIGHT_PAGE_METHODS': [
            PageMethod("wait_for_load_state", "networkidle"),
        ],
        'DOWNLOAD_DELAY': 1,  # Задержка между запросами
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'CONCURRENT_REQUESTS': 4,  # Один запрос за раз
        'CONCURRENT_REQUESTS_PER_DOMAIN': 4
    }

    def __init__(self, config=None, job_id=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not config:
            raise ValueError("Path to config file must be provided via -a config=...")
        self.config_path = config
        self.config = load_config(self.config_path)
        
        self.base_url = self.config.get('base_url', '')
        self.start_url = self.config.get('start_url', '/')
        self.selectors = self.config.get('selectors', {})
        self.show_more_settings = self.config.get('show_more_settings', {})
        
        # Настройки парсинга
        self.parse_all_listings = self.config.get('parse_all_listings', False)
        self.max_items_limit = self.config.get('max_items_limit', 100)
        
        # Статистика
        self.scraped_items_count = 0
        self.processed_items = 0
        self.failed_items = 0
        self.progress_update_interval = 10
        
        # Логгер
        self.job_id = job_id or os.environ.get('SCRAPY_JOB_ID', 'unknown')
        self.config_name = os.environ.get('SCRAPY_CONFIG_NAME', config or 'unknown')
        self.scraping_logger = get_scraping_logger(self.job_id, self.config_name)
        self.has_parsing_errors = False # Флаг для отслеживания ошибок парсинга
    def start_requests(self):
        """Начинает парсинг с главной страницы"""
        url = self.base_url + self.start_url
        self.logger.info(f"Starting scraping from: {url}")
        
        yield scrapy.Request(
            url,
            callback=self.parse,
            meta={
                'playwright': True,
                'playwright_include_page': True,
                'playwright_page_methods': [
                    PageMethod("wait_for_load_state", "networkidle"),
                ]
            },
            errback=self.handle_error,
            dont_filter=True
        )

    def parse(self, response):
        """Основной метод парсинга"""
        page = response.meta.get('playwright_page')
        
        if not page:
            self.logger.error("Playwright page not found")
            return

        # Получаем настройки кнопки "Показать еще"
        show_more_enabled = self.show_more_settings.get('enabled', False)
        button_selector = self.show_more_settings.get('button_selector', '')
        max_clicks = self.show_more_settings.get('max_clicks', 5)
        wait_time = self.show_more_settings.get('wait_time', 3)
        scroll_before_click = self.show_more_settings.get('scroll_before_click', True)
        
        # Кликаем кнопку "Показать еще" если включено
        if show_more_enabled and button_selector:
            self._handle_show_more(page, button_selector, max_clicks, wait_time, scroll_before_click)
        
        # Парсим объявления
        yield from self._parse_current_page(response)

    def _handle_show_more(self, page, button_selector, max_clicks, wait_time, scroll_before_click):
        """Обрабатывает клики по кнопке 'Показать еще'"""
        try:
            clicks_count = 0
            
            while clicks_count < max_clicks:
                # Проверяем наличие кнопки
                button = page.locator(button_selector)
                if not button.count():
                    self.logger.info(f"Кнопка 'Показать еще' не найдена после {clicks_count} кликов")
                    break
                
                # Прокручиваем к кнопке если нужно
                if scroll_before_click:
                    button.scroll_into_view_if_needed()
                
                # Кликаем по кнопке
                button.click()
                clicks_count += 1
                
                self.logger.info(f"Клик #{clicks_count} по кнопке 'Показать еще'")
                
                # Ждем загрузки контента
                page.wait_for_timeout(wait_time * 1000)
                
                # Ждем пока страница успокоится
                page.wait_for_load_state("networkidle")
                
        except Exception as e:
            self.logger.error(f"Ошибка при обработке кнопки 'Показать еще': {e}")


    def _parse_current_page(self, response):
        """Парсит объявления на текущей странице"""
        ads_list_selector = self.selectors.get("ads_list")
        ad_card_selector = self.selectors.get("ad_card")
        
        if not ads_list_selector or not ad_card_selector:
            self.logger.error("Required selectors (ads_list, ad_card) not found in config")
            return

        ads_container = response.css(ads_list_selector)
        if not ads_container:
            self.logger.warning(f"No ads container found with selector: {ads_list_selector}")
            return

        items_found = 0
        for element in ads_container.css(ad_card_selector):
            if not self.parse_all_listings and self.scraped_items_count >= self.max_items_limit:
                self.logger.info(f"Reached max items limit: {self.max_items_limit}")
                return
                
            items_found += 1
            self.scraped_items_count += 1
            
            # Обновляем прогресс каждые N элементов
            if self.scraped_items_count % self.progress_update_interval == 0:
                self._update_progress()
                
            try:
                # Извлекаем данные объявления
                item_data = self._extract_item_data(element)
                if item_data:
                    detail_url = item_data.get('url')
                    details_selectors = self.selectors.get('details', {})
                    
                    if detail_url and details_selectors:
                        # Переходим на детальную страницу
                        yield scrapy.Request(
                            detail_url,
                            callback=self.parse_details,
                            meta={'item_data': item_data},
                            errback=self.handle_error,
                            dont_filter=True
                        )
                    else:
                        yield item_data
            except Exception as e:
                self.logger.error(f"Error processing item: {e}")
                self.failed_items += 1

        self.logger.info(f"Found {items_found} items on page")
        if self.scraping_logger:
            self.scraping_logger.log_page_processed(1, items_found, response.url)

    def _extract_item_data(self, element):
        """Извлекает данные объявления"""
        try:
            item_data = {
                'source': self.config.get('source_name', 'unknown'),
            }
            
            # Основные поля
            basic_fields = ['title', 'url', 'price', 'location', 'description']
            for field in basic_fields:
                selector = self.selectors.get(field)
                if selector:
                    value = self._extract_field_value(element, selector)
                    item_data[field] = value
                    # Отладочная информация
                    if field in ['title', 'url']:
                        self.logger.info(f"Field '{field}': selector='{selector}', value='{value}'")
            
            # Извлекаем типы из селекторов
            property_type_selector = self.selectors.get('property_type')
            if property_type_selector:
                property_type = self._extract_field_value(element, property_type_selector)
                if property_type:
                    item_data['property_type'] = property_type
                    self.logger.info(f"Property type from selector: '{property_type}'")
            
            listing_type_selector = self.selectors.get('listing_type')
            if listing_type_selector:
                listing_type = self._extract_field_value(element, listing_type_selector)
                if listing_type:
                    item_data['listing_type'] = listing_type
                    self.logger.info(f"Listing type from selector: '{listing_type}'")
            
            # Обрабатываем URL
            if item_data.get('url') and not item_data['url'].startswith('http'):
                # Убираем двойной слеш
                base_url = self.base_url.rstrip('/')
                url = item_data['url'].lstrip('/')
                item_data['url'] = f"{base_url}/{url}"
            
            # Добавляем source_url для API
            if item_data.get('url'):
                item_data['source_url'] = item_data['url']
            
            # Фотографии будут извлекаться на детальной странице
            
            self.logger.info(f"Extracted item data: {item_data}")
            return item_data
        except Exception as e:
            self.logger.error(f"Error extracting item data: {e}")
            self.has_parsing_errors = True
            return None

    def _extract_photos(self, element):
        """Извлекает фотографии объявления"""
        try:
            photos = []
            
            # Проверяем селектор для изображений
            images_selector = self.selectors.get('images')
            self.logger.info(f"🔍 Photo extraction: images_selector from main selectors = '{images_selector}'")
            
            if not images_selector:
                # Если нет специального селектора для изображений, ищем в деталях
                details = self.selectors.get('details', {})
                images_selector = details.get('images')
                self.logger.info(f"🔍 Photo extraction: images_selector from details = '{images_selector}'")
            
            if images_selector:
                # Извлекаем все изображения
                image_elements = self._extract_field_elements(element, images_selector)
                self.logger.info(f"🔍 Photo extraction: found {len(image_elements)} image elements")
                
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
                        self.logger.info(f"🔍 Photo {i+1}: {full_url}")
            else:
                self.logger.warning("🔍 Photo extraction: no images selector found")
            
            self.logger.info(f"🔍 Photo extraction: total photos extracted = {len(photos)}")
            return photos
        except Exception as e:
            self.logger.error(f"Error extracting photos: {e}")
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
            if self.max_items_limit > 0:
                progress = min(95, int((self.scraped_items_count / self.max_items_limit) * 100))
            else:
                progress = 0
            
            # Логируем прогресс
            self.logger.info(f"Прогресс: {progress}%, спарсено: {self.scraped_items_count}")
                
        except Exception as e:
            self.logger.error(f"Ошибка обновления прогресса: {e}")

    def parse_details(self, response):
        """Парсит детальные данные на странице объявления"""
        item_data = response.meta['item_data']
        details = self.selectors.get('details', {})
        
        self.logger.info(f"🔍 Detail parsing: processing URL {response.url}")
        self.logger.info(f"🔍 Detail parsing: original item_data location = '{item_data.get('location')}'")
        
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
                self.logger.info(f"🔍 Phone extraction: selector = '{selector}'")
                phones = self._extract_phones_from_details(response, selector)
                if phones:
                    item_data['phone_numbers'] = phones
                    self.logger.info(f"🔍 Detail parsing: extracted {len(phones)} phones: {phones}")
                else:
                    self.logger.warning("🔍 Detail parsing: no phones extracted")
                    # Попробуем альтернативный селектор для an.kg
                    if 'an.kg' in response.url:
                        alt_selector = ".info_item .phone::text"
                        self.logger.info(f"🔍 Phone extraction: trying alternative selector = '{alt_selector}'")
                        alt_phones = self._extract_phones_from_details(response, alt_selector)
                        if alt_phones:
                            item_data['phone_numbers'] = alt_phones
                            self.logger.info(f"🔍 Detail parsing: extracted {len(alt_phones)} phones with alt selector: {alt_phones}")
            else:
                value = self._extract_field_value(response, selector)
                item_data[field] = value
                if field in ['rooms', 'area', 'floor']:
                    self.logger.info(f"🔍 Detail parsing: field '{field}' = '{value}'")
        
        self.logger.info(f"🔍 Detail parsing: final item_data location = '{item_data.get('location')}'")
        self.logger.info(f"🔍 Detail parsing: final item_data photos = {len(item_data.get('photos', []))} photos")
        yield item_data

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

    def _extract_photos_from_details(self, response, selector):
        """Извлекает фотографии из детальной страницы"""
        try:
            photos = []
            self.logger.info(f"🔍 Photo details extraction: selector = '{selector}'")
            self.logger.info(f"🔍 Photo details extraction: response URL = '{response.url}'")
            
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
                'reason': reason
            }
            
            self.logger.info(f"Spider closed: {stats}")
            
            if self.scraping_logger:
                self.scraping_logger.log_spider_finished(stats)
            
        except Exception as e:
            self.logger.error(f"Error in spider close: {e}") 

    def closed(self, reason):
        if self.has_parsing_errors:
            self.logger.error("Spider finished with parsing errors. Signalling failure.")
            pass


