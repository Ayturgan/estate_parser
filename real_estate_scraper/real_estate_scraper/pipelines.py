# pipelines.py - ИСПРАВЛЕННАЯ ВЕРСИЯ для работы с API спайдером

import re
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from itemadapter import ItemAdapter
from app.database import SessionLocal
from app.db_models import DBAd, DBLocation, DBPhoto


class ParserPipeline:
    def process_item(self, item, spider):
        # Просто передаёт item дальше
        return item


class DatabasePipeline:
    """
    Исправленная версия пайплайна, которая корректно обрабатывает
    данные как от HTML парсера (строки), так и от API парсера (числа)
    """
    
    def __init__(self):
        pass

    def extract_price(self, price_data):
        """
        ИСПРАВЛЕННАЯ ВЕРСИЯ: Извлекает числовую цену и валюту из строки или числа.
        Возвращает кортеж (price: float|None, currency: str|None)
        """
        if not price_data:
            return None, None
        
        # ИСПРАВЛЕНИЕ: Проверяем тип данных
        if isinstance(price_data, (int, float)):
            # Если получили число - возвращаем как есть
            return float(price_data), None  # Валюта будет определена из отдельного поля
        
        # Если получили строку - обрабатываем как раньше
        if not isinstance(price_data, str):
            # Если получили что-то другое - пытаемся конвертировать в строку
            try:
                price_data = str(price_data)
            except:
                return None, None
        
        # Определяем валюту по наличию ключевых слов в строке
        currency = None
        price_str_lower = price_data.lower()
        if "сом" in price_str_lower or "kgs" in price_str_lower:
            currency = "KGS"
        elif "$" in price_data or "usd" in price_str_lower:
            currency = "USD"
        elif "€" in price_data or "eur" in price_str_lower:
            currency = "EUR"
        else:
            currency = None  # Будет определена из отдельного поля или по умолчанию

        # Ищем цифры, включая пробелы, точки и запятые
        price_match = re.search(r'[\d\s.,]+', price_data)
        if not price_match:
            return None, currency
        
        price_num_str = price_match.group().replace(' ', '').replace(',', '.')
        try:
            price = float(price_num_str)
            return price, currency
        except ValueError:
            return None, currency

    def extract_area(self, area_data):
        """ИСПРАВЛЕННАЯ ВЕРСИЯ: Извлекает площадь из строки или числа."""
        if not area_data:
            return None

        # Если получили число
        if isinstance(area_data, (int, float)):
            return float(area_data)

        # Если получили строку
        if isinstance(area_data, str):
            area_match = re.search(r'[\d\s.,]+', area_data)
            if not area_match:
                return None

            try:
                area_val = float(area_match.group().replace(' ', '').replace(',', '.'))
                return area_val
            except ValueError:
                return None

        # Пытаемся конвертировать другие типы
        try:
            return float(area_data)
        except (ValueError, TypeError):
            return None

    def extract_floor(self, floor_data):
        """
        ИСПРАВЛЕННАЯ ВЕРСИЯ: Извлекает этаж и общее количество этажей 
        из строки формата "X этаж из Y" или из числа
        """
        if not floor_data:
            return None, None

        # Если получили число - это просто этаж
        if isinstance(floor_data, (int, float)):
            return int(floor_data), None

        # Если получили строку
        if isinstance(floor_data, str):
            floor_match = re.search(r'(\d+)\s*этаж\s*из\s*(\d+)', floor_data)
            if floor_match:
                try:
                    floor = int(floor_match.group(1))
                    total = int(floor_match.group(2))
                    return floor, total
                except ValueError:
                    return None, None
            
            # Пытаемся извлечь просто число
            floor_match = re.search(r'\d+', floor_data)
            if floor_match:
                try:
                    return int(floor_match.group()), None
                except ValueError:
                    return None, None

        return None, None

    def normalize_currency(self, currency_data):
        """Нормализует валюту к стандартному формату"""
        if not currency_data:
            return "USD"  # По умолчанию
        
        currency_str = str(currency_data).upper()
        
        # Маппинг различных вариантов валют
        currency_mapping = {
            'USD': 'USD',
            'ДОЛЛАР': 'USD',
            'DOLLAR': 'USD',
            '$': 'USD',
            'KGS': 'KGS',
            'СОМ': 'KGS',
            'СОМЫ': 'KGS',
            'EUR': 'EUR',
            'ЕВРО': 'EUR',
            '€': 'EUR',
            'RUB': 'RUB',
            'РУБЛЬ': 'RUB',
            'РУБЛИ': 'RUB'
        }
        
        for key, value in currency_mapping.items():
            if key in currency_str:
                return value
        
        return "USD"  # По умолчанию

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
        # Используем контекстный менеджер для автоматического управления сессией
        with SessionLocal() as session:
            try:
                # Определяем source_name, если не задан в конфиге
                source_name = spider.config.get("source_name", None) if hasattr(spider, "config") else None
                if not source_name:
                    url = adapter.get('link') or adapter.get('url', '')
                    if 'house.kg' in url:
                        source_name = "house.kg"
                    elif 'lalafo.kg' in url:
                        source_name = "lalafo.kg"
                    elif 'stroka.kg' in url:
                        source_name = "stroka.kg"
                    else:
                        source_name = "unknown"

                # ИСПРАВЛЕННАЯ ОБРАБОТКА ЦЕНЫ
                price, price_currency = self.extract_price(adapter.get('price'))
                
                # Обрабатываем валюту из отдельного поля если есть
                currency_field = adapter.get('currency')
                if currency_field:
                    currency = self.normalize_currency(currency_field)
                elif price_currency:
                    currency = price_currency
                else:
                    currency = "USD"  # По умолчанию

                # ИСПРАВЛЕННАЯ ОБРАБОТКА ДРУГИХ ПОЛЕЙ
                area = self.extract_area(adapter.get('area'))
                floor, total_floors = self.extract_floor(adapter.get('floor'))

                # Создаем объект локации, если есть данные
                location = None
                if any([adapter.get('city'), adapter.get('district'), adapter.get('address')]):
                    location = DBLocation(
                        city=adapter.get('city'),
                        district=adapter.get('district'),
                        address=adapter.get('address')
                    )
                    session.add(location)
                    session.flush()  # Чтобы получить location.id

                # Получаем source_id из ссылки
                link = adapter.get('link') or adapter.get('url')
                source_id = None
                if link:
                    if 'stroka.kg' in link:
                        # Для stroka.kg извлекаем ID из параметра topic_id
                        match = re.search(r'topic_id=(\d+)', link)
                        if match:
                            source_id = match.group(1)
                    else:
                        source_id = link.rstrip('/').split('/')[-1].split('?')[0]

                # ИСПРАВЛЕННАЯ ОБРАБОТКА КОМНАТ
                rooms_raw = adapter.get('rooms')
                rooms = None
                if rooms_raw is not None:
                    if isinstance(rooms_raw, (int, float)):
                        rooms = int(rooms_raw)
                    else:
                        try:
                            rooms = int(str(rooms_raw).strip())
                        except (ValueError, TypeError):
                            rooms = None

                # ИСПРАВЛЕННАЯ ОБРАБОТКА ВЫСОТЫ ПОТОЛКА
                ceiling_height_raw = adapter.get('ceiling_height')
                ceiling_height = None
                if ceiling_height_raw is not None:
                    if isinstance(ceiling_height_raw, (int, float)):
                        ceiling_height = float(ceiling_height_raw)
                    else:
                        try:
                            ceiling_height = float(str(ceiling_height_raw).replace('м.', '').strip())
                        except (ValueError, TypeError):
                            ceiling_height = None

                # Номера телефонов — список из одного номера, если есть
                phone_numbers = []
                phone = adapter.get('phone')
                mobile = adapter.get('mobile')
                if phone:
                    phone_numbers.append(phone)
                elif mobile:
                    phone_numbers.append(mobile)

                # ИСПРАВЛЕННАЯ ОБРАБОТКА ВРЕМЕНИ
                published_at = None
                created_time = adapter.get('created_at')
                spider.logger.info(f"DEBUG: created_time = {created_time}, type = {type(created_time)}")
                
                if created_time:
                    if isinstance(created_time, (int, float)):
                        published_at = datetime.fromtimestamp(created_time).date()
                        spider.logger.info(f"DEBUG: parsed timestamp = {published_at}")
                    elif isinstance(created_time, str):
                        # Для stroka.kg формат "Дата создания: DD.MM.YYYY"
                        date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', created_time)
                        if date_match:
                            day, month, year = map(int, date_match.groups())
                            published_at = datetime(year, month, day).date()
                            spider.logger.info(f"DEBUG: parsed date string = {published_at}")
                        else:
                            spider.logger.warning(f"DEBUG: no date match found in string: {created_time}")

                spider.logger.info(f"DEBUG: final published_at = {published_at}")

                ad = DBAd(
                    source_id=source_id,
                    title=adapter.get('title'),
                    description=adapter.get('description'),
                    source_url=link,
                    source_name=source_name,
                    price=price,
                    price_original=str(adapter.get('price')) if adapter.get('price') is not None else None,
                    currency=currency,
                    rooms=rooms,
                    area_sqm=area,
                    floor=floor,
                    total_floors=total_floors,
                    series=adapter.get('series'),
                    building_type=adapter.get('building'),
                    condition=adapter.get('condition'),
                    repair=adapter.get('repair'),
                    furniture=adapter.get('furniture'),
                    heating=adapter.get('heating'),
                    hot_water=adapter.get('hot_water'),
                    gas=adapter.get('gas'),
                    ceiling_height=ceiling_height,
                    phone_numbers=phone_numbers,
                    location_id=location.id if location else None,
                    is_vip=adapter.get('is_vip', False),
                    published_at=published_at,
                    parsed_at=datetime.utcnow(),
                    attributes={
                        'offer_type': adapter.get('offer_type'),
                        'building_year': adapter.get('building_year'),
                        'ceiling_height': adapter.get('ceiling_height')
                    }
                )
                session.add(ad)
                session.commit()

                # Сохраняем фото, если есть
                images = adapter.get('images') or ([adapter.get('main_image_url')] if adapter.get('main_image_url') else [])
                for image_url in images:
                    if image_url:
                        photo = DBPhoto(url=image_url, ad_id=ad.id)
                        session.add(photo)
                if images:
                    session.commit()

                spider.logger.info(f"Successfully saved item: {adapter.get('title', 'Unknown title')} - Price: {price} {currency}")

            except IntegrityError as e:
                # Дубликат source_id — откат и игнорирование
                session.rollback()
                spider.logger.info(f"Duplicate entry ignored: {adapter.get('link') or adapter.get('url')} - {str(e)}")
            except Exception as e:
                session.rollback()
                spider.logger.error(f"Error saving item: {e}", exc_info=True)
                spider.logger.error(f"Item data: {dict(adapter)}")  # Логируем данные для отладки

        return item

    def close_spider(self, spider):
        spider.logger.info("DatabasePipelineFixed closed")

