import scrapy
from playwright.async_api import async_playwright
import asyncio
import yaml
import os
from urllib.parse import urljoin
from ..parsers.loader import load_config


class UniversalSpider(scrapy.Spider):
    name = "generic_api"
    
    def __init__(self, config=None, *args, **kwargs):
        super(UniversalSpider, self).__init__(*args, **kwargs)
        if not config:
            raise ValueError("Config name must be provided via -a config=...")
        
        # Если передан путь с расширением - используем как есть
        if config.endswith('.yml') or config.endswith('.yaml'):
            self.config_path = config
        else:
            # Иначе строим путь к конфигу по имени
            current_dir = os.path.dirname(os.path.abspath(__file__))
            configs_dir = os.path.join(os.path.dirname(current_dir), "configs")
            self.config_path = os.path.join(configs_dir, f"{config}.yml")
        
        self.config = load_config(self.config_path)
        self.validate_config()



    def validate_config(self):
        """Проверяет обязательные поля в конфиге"""
        required_fields = ['api_url', 'main_url', 'headers']
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"Missing required field '{field}' in config")

    async def start(self):
        """Точка входа для асинхронного запуска"""
        if self.config.get('use_playwright', True):
            cookies, headers = await self.get_cookies_and_headers()
            cookie_header = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            headers_to_use = {**headers, "cookie": cookie_header}
        else:
            headers_to_use = self.config['headers']
        
        yield scrapy.Request(
            url=self.config['api_url'],
            headers=headers_to_use,
            callback=self.parse_api,
            meta={'config': self.config}
        )

    async def get_cookies_and_headers(self):
        """Получает куки и заголовки через Playwright"""
        main_url = self.config['main_url']
        headers = self.config['headers']
        
        playwright_config = self.config.get('playwright', {})
        headless = playwright_config.get('headless', True)
        sleep_time = playwright_config.get('sleep_time', 3)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(main_url)
            await asyncio.sleep(sleep_time)

            cookies = await context.cookies()
            await browser.close()
            return cookies, headers

    def parse_api(self, response):
        """Парсит API ответ согласно конфигурации"""
        config = response.meta['config']
        
        try:
            data = response.json()
        except ValueError:
            self.logger.error("Invalid JSON in response: %s", response.text)
            return

        # Получаем путь к данным (например, "items" или "data.results")
        items_path = config.get('items_path', 'items')
        items = self.get_nested_value(data, items_path)
        
        if not isinstance(items, list):
            self.logger.warning("Expected items to be a list, got: %s", type(items))
            return

        # Маппинг полей из конфига
        field_mapping = config.get('field_mapping', {})
        
        for item in items:
            result = {}
            
            # Обрабатываем простые поля
            for output_field, input_path in field_mapping.items():
                if isinstance(input_path, str):
                    result[output_field] = self.get_nested_value(item, input_path)
                elif isinstance(input_path, dict):
                    # Сложная обработка полей
                    result[output_field] = self.process_complex_field(item, input_path)
            
            # Добавляем URL если нужно
            if 'url' in result and config.get('make_absolute_url', True):
                result['url'] = urljoin(config['main_url'], result['url'])
            
            yield result

    def get_nested_value(self, data, path):
        """Получает значение по вложенному пути (например, 'data.items.0.title')"""
        if not path:
            return data
            
        keys = path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list) and key.isdigit():
                idx = int(key)
                current = current[idx] if idx < len(current) else None
            else:
                return None
                
            if current is None:
                return None
                
        return current

    def process_complex_field(self, item, field_config):
        """Обрабатывает сложные поля согласно конфигурации"""
        field_type = field_config.get('type')
        
        if field_type == 'main_image':
            images = self.get_nested_value(item, field_config['source_path'])
            if not images:
                return None
            main_image = next((img for img in images if img.get(field_config.get('main_field', 'is_main'))), None)
            if main_image:
                return main_image.get(field_config.get('url_field', 'original_url'))
            return None
            
        elif field_type == 'param_search':
            params = self.get_nested_value(item, field_config['source_path'])
            if not params:
                return None
            target_id = field_config['target_id']
            for param in params:
                if param.get('id') == target_id:
                    return param.get('value')
            return None
            
        elif field_type == 'custom':
            # Для кастомной обработки
            return self.custom_field_processor(item, field_config)
            
        return None
    

    def custom_field_processor(self, item, field_config):
        """Переопределяй этот метод для кастомной обработки полей"""
        return None