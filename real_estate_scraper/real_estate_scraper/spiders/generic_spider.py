import scrapy
from scrapy_playwright.page import PageMethod
from ..parsers.loader import load_config, extract_value
import time
import random

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
        'CONCURRENT_REQUESTS': 2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DOWNLOAD_DELAY': 2,
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

                if follow_link and item_data.get("link"):
                    try:
                        detail_url = response.urljoin(item_data["link"])
                        item_data["link"] = detail_url

                        meta = {
                            "item": item_data,
                            "dont_cache": True,
                            "playwright": True,
                            "playwright_page_methods": [
                                PageMethod("wait_for_load_state", "networkidle"),
                                PageMethod("wait_for_timeout", 2000),
                            ],
                            "playwright_page_init_callback": self.page_init_callback,
                        }

                        yield scrapy.Request(
                            detail_url,
                            callback=self.parse_detail,
                            meta=meta,
                            errback=self.handle_error,
                            dont_filter=True
                        )
                    except Exception as e:
                        self.logger.error(f"Error processing detail link '{item_data.get('link')}': {e}")
                        self.failed_items += 1
                        yield item_data
                else:
                    yield item_data
                    
            except Exception as e:
                self.logger.error(f"Error processing item: {e}")
                self.failed_items += 1

        self.logger.info(f"Found {items_found} items on page {self.current_page}")

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
        """Парсинг детальной страницы с проверкой типа контента"""
        item = response.meta["item"]
        
        try:
            content_type = response.headers.get('content-type', b'').decode('utf-8').lower()
            if 'text/html' not in content_type:
                self.logger.warning(f"Non-HTML content type: {content_type} for {response.url}")
                yield item
                return
            
            if not hasattr(response, 'text') or not response.text:
                self.logger.warning(f"Empty or non-text response for {response.url}")
                yield item
                return
                
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
            self.logger.debug("Page object is None in page_init_callback")
            return
            
        try:
            if page.is_closed():
                self.logger.debug("Page is already closed")
                return
                
            await page.set_default_timeout(60000)
            await page.set_default_navigation_timeout(60000)
            
            await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2}", lambda route: route.abort())
            
            page.on("pageerror", lambda err: self.logger.debug(f"Page error: {err}"))
            page.on("requestfailed", lambda request: self.logger.debug(f"Request failed: {request.url}"))
            
            await page.wait_for_timeout(random.randint(1000, 3000))
            
        except Exception as e:
            self.logger.debug(f"Error in page_init_callback: {e}")

    def handle_error(self, failure):
        """Обработчик ошибок"""
        request = failure.request
        self.logger.error(f"Request failed: {failure.value}")
        
        retries = request.meta.get('retry_times', 0)
        max_retries = 3
        
        if retries < max_retries:
            request.meta['retry_times'] = retries + 1
            
            self.logger.info(f"Retrying request {request.url} (attempt {retries + 1}/{max_retries})")
            
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
        self.logger.info(f"Spider closed: {reason}")
        self.logger.info(f"Processed items: {self.processed_items}")
        self.logger.info(f"Failed items: {self.failed_items}")
        
        time.sleep(2)
        
        if reason == 'finished':
            self.logger.info("Spider finished successfully")
        else:
            self.logger.warning(f"Spider closed with reason: {reason}")

