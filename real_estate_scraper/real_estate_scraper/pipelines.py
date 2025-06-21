# pipelines.py - ИСПРАВЛЕННАЯ ВЕРСИЯ для работы с API спайдером

import re
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from itemadapter import ItemAdapter
from app.database import SessionLocal
from app.db_models import DBAd, DBLocation, DBPhoto
import requests
import io
from PIL import Image
from imagehash import average_hash
from app.utils.duplicate_processor import DuplicateProcessor


class ParserPipeline:
    def process_item(self, item, spider):
        # Просто передаёт item дальше
        return item


class DatabasePipeline:
    """
    Новый пайплайн: отправляет объявления через API FastAPI (POST /ads), а не напрямую в базу.
    """
    API_URL = "http://localhost:8000/ads"  # Замените на нужный адрес, если работаете в Docker

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        # Определяем source_name, если не задан в конфиге
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

        # Формируем location
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

        # Формируем список фото
        images = adapter.get('images') or ([adapter.get('main_image_url')] if adapter.get('main_image_url') else [])
        photos = [{"url": url} for url in images if url]

        # Формируем номера телефонов
        phone_numbers = []
        phone = adapter.get('phone')
        mobile = adapter.get('mobile')
        if phone:
            phone_numbers.append(phone)
        elif mobile:
            phone_numbers.append(mobile)

        # Формируем published_at
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

        # Формируем payload для API
        payload = {
            "source_id": adapter.get("source_id"),
            "source_url": adapter.get("link") or adapter.get("url"),
            "source_name": source_name,
            "title": adapter.get("title"),
            "description": adapter.get("description"),
            "price": adapter.get("price"),
            "price_original": str(adapter.get("price")) if adapter.get("price") is not None else None,
            "currency": adapter.get("currency") or "USD",
            "rooms": adapter.get("rooms"),
            "area_sqm": adapter.get("area"),
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
        # Удаляем поля, если их значение None или пустая строка
        payload = {k: v for k, v in payload.items() if v not in [None, ""]}

        try:
            response = requests.post(self.API_URL, json=payload, timeout=30)
            response.raise_for_status()
            spider.logger.info(f"Ad sent to API: {payload.get('title')}")
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

