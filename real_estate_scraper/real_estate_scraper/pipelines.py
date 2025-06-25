import re
from datetime import datetime
from itemadapter import ItemAdapter
import requests


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
            return None, "USD"
        
        price_str = str(price_str).strip()
        
        currency = "USD"  
        
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
        Извлекает URL изображений, обрабатывая как прямые URL, так и URL из background-image стилей.
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
    API_URL = "http://api:8000/ads"
    # API_URL = "http://localhost:8000/ads"

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        
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
            else:
                source_name = "unknown"

        city = adapter.get('city')
        district = adapter.get('district')
        address_line = adapter.get('address')
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

        images = adapter.get('images') or ([adapter.get('main_image_url')] if adapter.get('main_image_url') else [])
        photos = [{"url": url} for url in images if url]

        phone_numbers = []
        phone = adapter.get('phone')
        mobile = adapter.get('mobile')
        if phone:
            phone_numbers.append(phone)
        elif mobile:
            phone_numbers.append(mobile)

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
            "floor": adapter.get("floor"), 
            "total_floors": adapter.get("total_floors"),  
            "series": adapter.get("series"),
            "building_type": adapter.get("building_type") or adapter.get("building"),
            "condition": adapter.get("condition"),
            "repair": adapter.get("repair"),
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
            "is_vip": adapter.get("is_vip"),
        }
        
        payload = {k: v for k, v in payload.items() if v not in [None, ""]}

        try:
            response = requests.post(self.API_URL, json=payload, timeout=30)
            response.raise_for_status()
            spider.logger.info(f"Ad sent to API successfully: {payload.get('title')}")
        except requests.exceptions.HTTPError as e:
            error_text = ""
            try:
                error_text = response.text
            except Exception:
                pass
            spider.logger.error(f"Error sending ad to API: {e} | Data: {payload} | Response: {error_text}")
        except Exception as e:
            spider.logger.error(f"Error sending ad to API: {e} | Data: {payload}")
        
        return item

