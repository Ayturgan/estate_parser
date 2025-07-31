import re
import os
from datetime import datetime
from itemadapter import ItemAdapter
import requests
import sys
import os
from .logger import get_scraping_logger

# Импорт валидатора фотографий
try:
    from .services.photo_validator_service import PhotoValidatorService
    PHOTO_VALIDATION_ENABLED = True
    print("✅ Photo validator service loaded successfully!")
except ImportError as e:
    print(f"⚠️ Photo validator service not available: {e}")
    PHOTO_VALIDATION_ENABLED = False

# Добавляем корневую папку проекта в путь
# Определяем корневую папку в зависимости от среды
if '/app/' in __file__:
    # Docker среда
    project_root = "/app"
else:
    # Локальная среда - ищем estate_parser директорию
    current_dir = os.path.dirname(__file__)
    while current_dir != '/' and os.path.basename(current_dir) != 'estate_parser':
        current_dir = os.path.dirname(current_dir)
    
    if os.path.basename(current_dir) == 'estate_parser':
        project_root = current_dir
    else:
        # Fallback - используем старый метод
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

# Добавляем backend в путь для локальной разработки
backend_path = os.path.join(project_root, 'backend')
if os.path.exists(backend_path):
    sys.path.insert(0, backend_path)

sys.path.append(project_root)

# Импортируем AI сервис с обработкой ошибок
try:
    # Импортируем новый модульный AI extractor
    from backend.app.services.ai_data_extractor import AIDataExtractor
    ai_extractor = AIDataExtractor()
    AI_ENABLED = True
    print(f"✅ AI Data Extractor loaded successfully with modular architecture!")
except ImportError as e:
    print(f"⚠️ AI Data Extractor not available: {e}")
    AI_ENABLED = False
    ai_extractor = None
    # Дополнительная отладка
    ai_module_path = os.path.join(project_root, 'backend', 'app', 'services', 'ai_data_extractor.py')
    print(f"🔍 Expected AI module path: {ai_module_path}")
    print(f"🔍 AI module exists: {os.path.exists(ai_module_path)}")
    
    # Дополнительная диагностика структуры папок
    print(f"🔍 Contents of project_root ({project_root}): {os.listdir(project_root) if os.path.exists(project_root) else 'N/A'}")
    backend_path = os.path.join(project_root, 'backend')
    if os.path.exists(backend_path):
        print(f"🔍 Contents of backend folder: {os.listdir(backend_path)}")
        app_path = os.path.join(backend_path, 'app')
        if os.path.exists(app_path):
            print(f"🔍 Contents of app folder: {os.listdir(app_path)}")
            services_path = os.path.join(app_path, 'services')
            if os.path.exists(services_path):
                print(f"🔍 Contents of services folder: {os.listdir(services_path)}")
    
    import traceback
    print(f"🔍 Full traceback: {traceback.format_exc()}")


class ParserPipeline:
    def process_item(self, item, spider):
        return item


class DataCleaningPipeline:
    """
    Пайплайн для очистки всех числовых полей: цены, площади, этажей и т.д.
    """
    
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
        price_original = adapter.get("price")
        if price_original is not None:
            adapter["price_original"] = str(price_original)
            cleaned_price, currency = self.clean_price_and_currency(str(price_original))
            adapter["price"] = cleaned_price
            adapter["currency"] = currency
            spider.logger.debug(f"Price cleaned: '{price_original}' -> {cleaned_price} {currency}")
        
        area_original = adapter.get("area") or adapter.get("area_sqm")
        if area_original is not None:
            cleaned_area = self.extract_number(str(area_original))
            adapter["area_sqm"] = cleaned_area
            spider.logger.debug(f"Area cleaned: '{area_original}' -> {cleaned_area}")
        
        floor_original = adapter.get("floor")
        if floor_original is not None:
            cleaned_floor = self.extract_floor_number(str(floor_original))
            adapter["floor"] = cleaned_floor
            spider.logger.debug(f"Floor cleaned: '{floor_original}' -> {cleaned_floor}")
        
        total_floors_original = adapter.get("total_floors")
        if total_floors_original is not None:
            cleaned_total_floors = self.extract_total_floors(str(total_floors_original))
            adapter["total_floors"] = cleaned_total_floors
            spider.logger.debug(f"Total floors cleaned: '{total_floors_original}' -> {cleaned_total_floors}")
        elif floor_original and "из" in str(floor_original):
            total_floors = self.extract_total_floors_from_floor_string(str(floor_original))
            if total_floors:
                adapter["total_floors"] = total_floors
        
        rooms_original = adapter.get("rooms")
        if rooms_original is not None:
            cleaned_rooms = self.extract_rooms_number(str(rooms_original))
            adapter["rooms"] = cleaned_rooms
            spider.logger.debug(f"Rooms cleaned: '{rooms_original}' -> {cleaned_rooms}")
        
        ceiling_height_original = adapter.get("ceiling_height")
        if ceiling_height_original is not None:
            cleaned_ceiling_height = self.extract_number(str(ceiling_height_original))
            adapter["ceiling_height"] = cleaned_ceiling_height
            spider.logger.debug(f"Ceiling height cleaned: '{ceiling_height_original}' -> {cleaned_ceiling_height}")

        images_original = adapter.get("images")
        if images_original is not None:
            cleaned_images = self.extract_images_universal(images_original)
            adapter["images"] = cleaned_images
            spider.logger.debug(f"Images cleaned: found {len(cleaned_images)} images")

        return item
    
    def clean_price_and_currency(self, price_str):
        """
        Очищает строку цены и определяет валюту
        """
        if not price_str:
            return None, "SOM"
        
        price_str = str(price_str).strip()
        
        currency = "SOM"  
        
        if any(keyword in price_str.lower() for keyword in ['сом', 'som', 'kgs', 'кгс']):
            currency = "SOM"
        elif any(keyword in price_str.lower() for keyword in ['usd', '$', 'долл', 'dollar']):
            currency = "USD"
        elif any(keyword in price_str.lower() for keyword in ['eur', '€', 'евро', 'euro']):
            currency = "EUR"
        
        cleaned = re.sub(r'[^\d.,]', '', price_str)
        cleaned = re.sub(r'\s+', '', cleaned)
        
        if '.' in cleaned and ',' in cleaned:
            last_dot = cleaned.rfind('.')
            last_comma = cleaned.rfind(',')
            
            if last_dot > last_comma:
                cleaned = cleaned.replace(',', '')
            else:
                cleaned = cleaned.replace('.', '').replace(',', '.')
        elif ',' in cleaned:
            comma_parts = cleaned.split(',')
            if len(comma_parts) == 2 and len(comma_parts[1]) <= 2:
                cleaned = cleaned.replace(',', '.')
            else:
                cleaned = cleaned.replace(',', '')
        
        try:
            if '.' in cleaned:
                price_value = float(cleaned)
            else:
                price_value = int(cleaned)
            
            if price_value <= 0:
                return None, currency
                
            return price_value, currency
            
        except (ValueError, TypeError):
            return None, currency
        

    def extract_images_universal(self, images_data):
        """
        Извлекает URL изображений, обрабатывая как прямые URL, так и URL из background-image стилей,
        а также структуры API (например, Lalafo).
        """
        if not images_data:
            return []
        
        image_urls = []
        
        # Если images_data - это строка, попробуем извлечь из стиля или считать как прямой URL
        if isinstance(images_data, str):
            # Попытка извлечь из стиля
            urls_from_style = re.findall(r"url\([\\'\"]?([^\\'\"]+)[\\'\"]?\)", images_data)
            if urls_from_style:
                image_urls.extend(urls_from_style)
            else:
                # Если не стиль, считаем, что это прямой URL
                image_urls.append(images_data)
        # Если images_data - это список, итерируемся по элементам
        elif isinstance(images_data, list):
            for item in images_data:
                if item:
                    # Если элемент - это словарь (API структура, например Lalafo)
                    if isinstance(item, dict):
                        # Ищем URL в различных полях
                        url = (item.get('original_url') or 
                               item.get('url') or 
                               item.get('src') or 
                               item.get('image_url'))
                        if url:
                            image_urls.append(str(url))
                    else:
                        # Попытка извлечь из стиля
                        urls_from_style = re.findall(r"url\([\\'\"]?([^\\'\"]+)[\\'\"]?\)", str(item))
                        if urls_from_style:
                            image_urls.extend(urls_from_style)
                        else:
                            # Если не стиль, считаем, что это прямой URL
                            image_urls.append(str(item))
        
        return list(filter(None, list(set(image_urls))))
    
    def extract_number(self, text):
        """
        Извлекает первое число из строки
        """
        if not text:
            return None
        
        match = re.search(r'(\d+(?:[.,]\d+)?)', str(text))
        if match:
            number_str = match.group(1).replace(',', '.')
            try:
                if '.' in number_str:
                    return float(number_str)
                else:
                    return int(number_str)
            except (ValueError, TypeError):
                return None
        return None
    
    def extract_floor_number(self, floor_str):
        """
        Извлекает номер этажа из строки типа "3 этаж из 10"
        """
        if not floor_str:
            return None
        
        match = re.search(r'(\d+)\s*(?:этаж|эт\.?)', str(floor_str), re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, TypeError):
                return None
        
        return self.extract_number(floor_str)
    
    def extract_total_floors(self, total_floors_str):
        """
        Извлекает общее количество этажей
        """
        if not total_floors_str:
            return None
        
        match = re.search(r'из\s*(\d+)', str(total_floors_str), re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, TypeError):
                return None
        
        return self.extract_number(total_floors_str)
    
    def extract_total_floors_from_floor_string(self, floor_str):
        """
        Извлекает общее количество этажей из строки этажа типа "3 этаж из 10"
        """
        if not floor_str:
            return None
        
        match = re.search(r'из\s*(\d+)', str(floor_str), re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, TypeError):
                return None
        return None
    
    def extract_rooms_number(self, rooms_str):
        """
        Извлекает количество комнат из строки типа "1-комн. кв."
        """
        if not rooms_str:
            return None
        
        match = re.search(r'(\d+)[-\s]*комн', str(rooms_str), re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, TypeError):
                return None
        return self.extract_number(rooms_str)


class DatabasePipeline:
    """
    Пайплайн для отправки объявлений через API FastAPI (POST /ads)
    """
    def __init__(self):
        try:
            from backend.app.core.config import SCRAPY_API_URL
            self.API_URL = SCRAPY_API_URL
        except ImportError:
            self.API_URL = os.getenv("SCRAPY_API_URL", "http://api:8000/api/ads")
        
        # Убираем инициализацию валидатора фото
        self.photo_validator = None
        # Универсальный список паттернов для фильтрации рекламных фото
        self.photo_filter_patterns = [
            '/banners/',
            # В будущем можно добавить другие паттерны, например:
            # '/ads/', '/promo/', '/watermark/'
        ]

    def filter_photos(self, images):
        """
        Фильтрует список ссылок на фото по паттернам из self.photo_filter_patterns
        Оставляет только валидные фото
        """
        if not images:
            return []
        filtered = []
        for url in images:
            if not any(pattern in url for pattern in self.photo_filter_patterns):
                filtered.append(url)
        return filtered

    def process_phone_numbers(self, phone_data):
        """
        Обрабатывает номера телефонов: разделяет сгруппированные номера и нормализует их в нужные форматы
        Поддерживает форматы: +996700121212, 996700121212, 0700121212, 700121212
        """
        if not phone_data:
            return []
        
        processed_phones = []
        
        # Если это список, обрабатываем каждый элемент
        if isinstance(phone_data, list):
            for phone_item in phone_data:
                processed_phones.extend(self._split_and_normalize_phone(phone_item))
        else:
            # Если это строка, обрабатываем её
            processed_phones.extend(self._split_and_normalize_phone(phone_data))
        
        # Убираем дубликаты и пустые значения
        unique_phones = list(set(filter(None, processed_phones)))
        
        return unique_phones

    def _split_and_normalize_phone(self, phone_str):
        """
        Разделяет сгруппированные номера и нормализует их
        """
        if not phone_str:
            return []
        
        phone_str = str(phone_str).strip()
        normalized_phones = []
        
        # Разделяем по различным разделителям
        # Поддерживаем разделители: пробел, запятая, точка с запятой, дефис
        phone_parts = re.split(r'[\s,;\-]+', phone_str)
        
        for part in phone_parts:
            part = part.strip()
            if not part:
                continue
            
            # Убираем лишние символы (скобки, кавычки и т.д.)
            part = re.sub(r'[()"\']', '', part)
            
            # Нормализуем номер
            normalized = self._normalize_phone_number(part)
            if normalized:
                normalized_phones.append(normalized)
        
        return normalized_phones

    def _normalize_phone_number(self, phone):
        """
        Нормализует номер телефона в один из поддерживаемых форматов
        Поддерживаемые форматы: +996700121212, 996700121212, 0700121212, 700121212
        """
        if not phone:
            return None
        
        # Убираем все нецифровые символы кроме +
        clean_phone = re.sub(r'[^\d+]', '', phone)
        
        # Если номер начинается с +996
        if clean_phone.startswith('+996'):
            if len(clean_phone) == 13:  # +996700121212
                return clean_phone
            elif len(clean_phone) == 12:  # +99670121212 (без 0 после +996)
                return clean_phone
        
        # Если номер начинается с 996 (без +)
        elif clean_phone.startswith('996'):
            if len(clean_phone) == 12:  # 996700121212
                return f"+{clean_phone}"
            elif len(clean_phone) == 11:  # 99670121212 (без 0 после 996)
                return f"+{clean_phone}"
        
        # Если номер начинается с 0 (кыргызский формат)
        elif clean_phone.startswith('0'):
            if len(clean_phone) == 10:  # 0700121212
                return f"+996{clean_phone[1:]}"
            elif len(clean_phone) == 9:  # 070757554 (9 цифр с 0)
                return f"+996{clean_phone[1:]}"
        
        # Если номер начинается с 7 (без 0)
        elif clean_phone.startswith('7'):
            if len(clean_phone) == 9:  # 700121212
                return f"+996{clean_phone}"
        
        # Если номер начинается с 5, 6, 7 (мобильные коды)
        elif clean_phone.startswith(('5', '6', '7')):
            if len(clean_phone) == 9:  # 700121212
                return f"+996{clean_phone}"
        
        return None

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
        # Получаем логгер для этой задачи
        job_id = getattr(spider, 'job_id', 'unknown')
        config_name = getattr(spider, 'config_name', 'unknown')
        scraping_logger = get_scraping_logger(job_id, config_name)
        
        title = adapter.get("title", "Unknown")
        item_url = adapter.get("link") or adapter.get("url", "")
        
        scraping_logger.log_item_processing(title, item_url)
        
        source_name = None
        if hasattr(spider, "config"):
            source_name = spider.config.get("source_name", None)
        if not source_name:
            url = adapter.get('link') or adapter.get('url', '')
            if 'house.kg' in url:
                source_name = "house.kg"
            elif 'lalafo.kg' in url:
                source_name = "lalafo.kg"
            elif 'stroka.kg' in url:
                source_name = "stroka.kg"
            elif 'an.kg' in url:
                source_name = "an.kg"
            elif 'agency.kg' in url:
                source_name = "agency.kg"
            else:
                source_name = "unknown"

        city = adapter.get('city')
        district = adapter.get('district')
        address_line = adapter.get('address')
        
        # Обрабатываем локацию из поля location (для agency.kg)
        location_str = adapter.get('location')
        spider.logger.info(f"🔍 Pipeline location processing: location_str = '{location_str}'")
        if location_str and not city and not district:
            # Если есть строка локации, используем её как district
            district = location_str
            address_line = location_str
            spider.logger.info(f"🔍 Pipeline location processing: set district = '{district}'")
        
        if not city and not district and address_line:
            parts = [p.strip() for p in address_line.split(',')]
            if len(parts) >= 3:
                city = parts[0]
                district = parts[1]
                address_line = ', '.join(parts[2:])
            elif len(parts) == 2:
                city = parts[0]
                address_line = parts[1]
        location = None
        if city or district or address_line:
            location = {
                "city": city,
                "district": district,
                "address": address_line
            }
            spider.logger.info(f"🔍 Pipeline location: created location object = {location}")
        else:
            spider.logger.warning("🔍 Pipeline location: no location data found")

        images = adapter.get('images') or ([adapter.get('main_image_url')] if adapter.get('main_image_url') else [])
        
        # Фильтрация рекламных фото по паттернам
        filtered_images = self.filter_photos(images)
        photos = [{"url": url} for url in filtered_images if url]

        # 🔧 УЛУЧШЕННАЯ ОБРАБОТКА НОМЕРОВ ТЕЛЕФОНОВ
        phone_numbers = []
        
        # Обрабатываем поле phone_numbers (из спайдера)
        phones_from_spider = adapter.get('phone_numbers')
        if phones_from_spider:
            processed_phones = self.process_phone_numbers(phones_from_spider)
            phone_numbers.extend(processed_phones)
            spider.logger.info(f"🔧 Phone processing: processed {len(processed_phones)} phones from spider: {processed_phones}")
        
        # Также проверяем старые поля для совместимости
        phone = adapter.get('phone')
        if phone:
            processed_phone = self.process_phone_numbers(phone)
            for p in processed_phone:
                if p not in phone_numbers:
                    phone_numbers.append(p)
        
        mobile = adapter.get('mobile')
        if mobile:
            processed_mobile = self.process_phone_numbers(mobile)
            for p in processed_mobile:
                if p not in phone_numbers:
                    phone_numbers.append(p)
        
        spider.logger.info(f"🔧 Final phone processing: {len(phone_numbers)} unique phones: {phone_numbers}")

        published_at = None
        created_time = adapter.get('created_at')
        if created_time:
            if isinstance(created_time, (int, float)):
                try:
                    published_at = datetime.fromtimestamp(created_time).isoformat()
                except Exception:
                    published_at = None
            elif isinstance(created_time, str):
                date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', created_time)
                if date_match:
                    day, month, year = map(int, date_match.groups())
                    try:
                        published_at = datetime(year, month, day).isoformat()
                    except Exception:
                        published_at = None

        payload = {
            "source_id": adapter.get("source_id"),
            "source_url": adapter.get("link") or adapter.get("url"),
            "source_name": source_name,
            "title": adapter.get("title"),
            "description": adapter.get("description"),
            "price": adapter.get("price"), 
            "currency": adapter.get("currency") or "USD",
            "rooms": adapter.get("rooms"),  
            "area_sqm": adapter.get("area_sqm"), 
            "land_area_sotka": adapter.get("land_area_sotka"),
            "floor": adapter.get("floor"), 
            "total_floors": adapter.get("total_floors"),  
            "series": adapter.get("series"),
            "building_type": adapter.get("building_type") or adapter.get("building"),
                                "condition": adapter.get("condition") or adapter.get("repair"),
            "furniture": adapter.get("furniture"),
            "heating": adapter.get("heating"),
            "hot_water": adapter.get("hot_water"),
            "gas": adapter.get("gas"),
            "ceiling_height": adapter.get("ceiling_height"),
            "phone_numbers": phone_numbers,
            "location": location,
            "photos": photos,
            "attributes": adapter.get("attributes") or {},
            "published_at": published_at,
            # Добавляем данные классификации из конфигов
            "property_type": adapter.get("property_type"),
            "listing_type": adapter.get("listing_type"),

        }
        
        # 🔍 ДИАГНОСТИКА: Логируем property_type и listing_type из adapter
        spider.logger.info(f"🔍 DIAGNOSTIC: adapter.get('property_type') = {adapter.get('property_type')}")
        spider.logger.info(f"🔍 DIAGNOSTIC: adapter.get('listing_type') = {adapter.get('listing_type')}")
        spider.logger.info(f"🔍 DIAGNOSTIC: payload property_type = {payload.get('property_type')}")
        spider.logger.info(f"🔍 DIAGNOSTIC: payload listing_type = {payload.get('listing_type')}")
        
        payload = {k: v for k, v in payload.items() if v not in [None, ""]}
        
        # 🔍 ДИАГНОСТИКА: Логируем после фильтрации
        spider.logger.info(f"🔍 DIAGNOSTIC: После фильтрации - payload property_type = {payload.get('property_type')}")
        spider.logger.info(f"🔍 DIAGNOSTIC: После фильтрации - payload listing_type = {payload.get('listing_type')}")

        # 🤖 AI обработка и извлечение данных
        spider.logger.info(f"🔍 AI Debug: AI_ENABLED={AI_ENABLED}, ai_extractor={ai_extractor is not None if ai_extractor else 'None'}")
        
        if AI_ENABLED and ai_extractor:
            try:
                ai_title = adapter.get("title") or ""
                description = adapter.get("description") or ""
                
                spider.logger.info(f"🤖 Starting AI processing for title: {ai_title[:50]}...")
                spider.logger.debug(f"🤖 Description: {description[:100]}...")
                
                # Подготавливаем item_data с данными из конфигов (если есть)
                item_data = payload.copy()  # Начинаем с парсенных данных
                
                # Добавляем точную классификацию из конфигов спайдера (если доступна)
                if hasattr(spider, 'config') and spider.config:
                    # Для мультикатегорийных спайдеров данные могут быть в item
                    config_data = {}
                    
                    # Проверяем есть ли данные классификации в самом item
                    if adapter.get('property_type'):
                        config_data['property_type'] = adapter.get('property_type')
                    if adapter.get('listing_type'):
                        config_data['listing_type'] = adapter.get('listing_type')
                    if adapter.get('source'):
                        config_data['source'] = adapter.get('source')
                    if adapter.get('category_name'):
                        config_data['category_name'] = adapter.get('category_name')
                    if adapter.get('category_id'):
                        config_data['category_id'] = adapter.get('category_id')
                    
                    if config_data:
                        item_data.update(config_data)
                        spider.logger.info(f"🎯 Используем точную классификацию из конфига: {config_data}")
                
                # Применяем AI для извлечения недостающих данных и классификации
                enhanced_data = ai_extractor.extract_and_classify(
                    title=ai_title,
                    description=description, 
                    existing_data=item_data  # Передаем данные с классификацией из конфигов
                )
                
                # Логируем AI обработку
                scraping_logger.log_ai_processing(ai_title, description, enhanced_data)
                
                spider.logger.debug(f"🤖 AI extracted data: {enhanced_data}")
                
                # Обновляем payload с данными от AI
                payload.update(enhanced_data)
                spider.logger.info(f"✅ AI enhancement completed for: {ai_title[:50]}... | Updated payload keys: {list(enhanced_data.keys())}")
                
                # 🔍 ДИАГНОСТИКА: Логируем после AI обработки
                spider.logger.info(f"🔍 DIAGNOSTIC: После AI - payload property_type = {payload.get('property_type')}")
                spider.logger.info(f"🔍 DIAGNOSTIC: После AI - payload listing_type = {payload.get('listing_type')}")
                
            except Exception as e:
                spider.logger.error(f"❌ AI enhancement failed: {e}")
                scraping_logger.log_error(f"AI enhancement failed", f"Title: {title}", e)
                import traceback
                spider.logger.error(f"❌ AI traceback: {traceback.format_exc()}")
        else:
            spider.logger.warning(f"⚠️ AI enhancement skipped - AI_ENABLED={AI_ENABLED}, ai_extractor available={ai_extractor is not None if ai_extractor else 'None'}")
            scraping_logger.log_warning("AI enhancement skipped", f"AI_ENABLED={AI_ENABLED}, ai_extractor available={ai_extractor is not None}")

        # 🔍 Логирование финального payload перед отправкой
        spider.logger.info(f"🔍 Final payload being sent to API:")
        spider.logger.info(f"  📝 Title: {payload.get('title', 'N/A')}")
        spider.logger.info(f"🔍 DIAGNOSTIC: ФИНАЛЬНЫЙ - payload property_type = {payload.get('property_type')}")
        spider.logger.info(f"🔍 DIAGNOSTIC: ФИНАЛЬНЫЙ - payload listing_type = {payload.get('listing_type')}")
        spider.logger.info(f"  🤖 AI Classification: property_type={payload.get('property_type')}, property_origin={payload.get('property_origin')}, listing_type={payload.get('listing_type')}")
        spider.logger.info(f"  🏠 Property Data: rooms={payload.get('rooms')}, area_sqm={payload.get('area_sqm')}, floor={payload.get('floor')}, total_floors={payload.get('total_floors')}")
        spider.logger.info(f"  🏡 Characteristics: heating={payload.get('heating')}, furniture={payload.get('furniture')}, condition={payload.get('condition')}")
        spider.logger.info(f"  📍 Location: {payload.get('location', 'N/A')}")
        spider.logger.info(f"  👤 Realtor: {payload.get('realtor_id')}")
        spider.logger.info(f"  📞 Phones: {payload.get('phone_numbers')}")
        
        try:
            response = requests.post(self.API_URL, json=payload, timeout=30)
            response.raise_for_status()
            
            # Определяем тип операции по статус коду
            if response.status_code == 200:
                spider.logger.info(f"✅ Ad processed successfully (created or updated): {payload.get('title')}")
                scraping_logger.log_api_call_success(title, self.API_URL)
                scraping_logger.log_item_success(title, payload)
            else:
                spider.logger.info(f"✅ Ad sent to API with status {response.status_code}: {payload.get('title')}")
                scraping_logger.log_api_call_success(title, self.API_URL)
                scraping_logger.log_item_success(title, payload)
                
        except requests.exceptions.HTTPError as e:
            error_text = ""
            try:
                error_text = response.text
            except Exception:
                pass
            error_msg = f"HTTP Error {e}: {error_text}"
            spider.logger.error(f"Error sending ad to API: {e} | Data: {payload} | Response: {error_text}")
            scraping_logger.log_api_call_failure(title, error_msg, self.API_URL)
        except Exception as e:
            spider.logger.error(f"Error sending ad to API: {e} | Data: {payload}")
            scraping_logger.log_api_call_failure(title, str(e), self.API_URL)
        
        return item

