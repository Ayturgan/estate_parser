# generic_spider.py - ПРАВИЛЬНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ

import scrapy
from scrapy_playwright.page import PageMethod
from ..parsers.loader import load_config, extract_value
import asyncio
import logging

class GenericSpider(scrapy.Spider):
    name = "generic_scraper"

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

                    # ИСПРАВЛЕНИЕ: Добавляем обработку ошибок для селекторов
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
                    # ИСПРАВЛЕНИЕ: Проверяем корректность ссылки
                    try:
                        detail_url = response.urljoin(item_data["link"])
                        item_data["link"] = detail_url

                        meta = {
                            "item": item_data,
                            "dont_cache": True,
                        }
                        
                        if use_playwright:
                            # ИСПРАВЛЕНИЕ: Улучшенная конфигурация Playwright
                            playwright_methods = [
                                PageMethod("wait_for_load_state", "networkidle"),
                            ]
                            
                            # Добавляем селектор ожидания если есть
                            wait_selector = self.detail_config.get("wait_selector", "img.fotorama__img")
                            if wait_selector:
                                playwright_methods.append(
                                    PageMethod("wait_for_selector", wait_selector, timeout=10000)
                                )
                            
                            meta.update({
                                "playwright": True,
                                "playwright_page_methods": playwright_methods,
                                "playwright_page_init_callback": self.page_init_callback,
                            })

                        yield response.follow(
                            detail_url,
                            callback=self.parse_detail,
                            meta=meta,
                            errback=self.handle_error
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
                        errback=self.handle_error
                    )
                else:
                    self.logger.info("No more pages to process")
            except Exception as e:
                self.logger.error(f"Error in pagination: {e}")

    def parse_detail(self, response):
        """ИСПРАВЛЕННАЯ ВЕРСИЯ: Парсинг детальной страницы без return в генераторе"""
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

        # ИСПРАВЛЕНИЕ: Убираем return, только yield
        yield item

    def page_init_callback(self, page, request):
        """Callback для инициализации Playwright страницы"""
        try:
            # Устанавливаем таймауты
            page.set_default_timeout(30000)  # 30 секунд
            page.set_default_navigation_timeout(30000)
            
            # Отключаем загрузку ненужных ресурсов для ускорения
            page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2}", lambda route: route.abort())
            
        except Exception as e:
            self.logger.warning(f"Error in page_init_callback: {e}")

    def handle_error(self, failure):
        """Обработчик ошибок для запросов"""
        self.logger.error(f"Request failed: {failure.value}")
        self.failed_items += 1
        
        # Если это ошибка Playwright, логируем дополнительную информацию
        if hasattr(failure.value, '__class__'):
            error_type = failure.value.__class__.__name__
            if 'playwright' in error_type.lower() or 'timeout' in error_type.lower():
                self.logger.error(f"Playwright/Timeout error: {error_type}")

    def closed(self, reason):
        """ИСПРАВЛЕНИЕ: Более мягкое закрытие спайдера"""
        self.logger.info(f"Spider closed: {reason}")
        self.logger.info(f"Processed items: {self.processed_items}")
        self.logger.info(f"Failed items: {self.failed_items}")
        
        # ИСПРАВЛЕНИЕ: Более осторожная очистка asyncio задач
        try:
            # Не пытаемся принудительно отменять задачи - это может вызвать CancelledError
            # Просто логируем информацию
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    pending_tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
                    if pending_tasks:
                        self.logger.info(f"Found {len(pending_tasks)} pending tasks (will be handled by Scrapy)")
            except Exception:
                pass  # Игнорируем ошибки получения loop
        except Exception as e:
            self.logger.warning(f"Error in cleanup: {e}")

