# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy
from datetime import datetime


class ParserItem(scrapy.Item):
    # Основная информация
    source_id = scrapy.Field()  # ID объявления на сайте-источнике
    source_name = scrapy.Field()  # Название сайта-источника
    source_url = scrapy.Field()  # URL объявления
    title = scrapy.Field()  # Заголовок объявления
    description = scrapy.Field()  # Описание объявления
    
    # Цена
    price = scrapy.Field()  # Цена в числовом формате
    price_original = scrapy.Field()  # Оригинальная строка с ценой
    currency = scrapy.Field()  # Валюта (USD, KGS, EUR)
    
    # Характеристики недвижимости
    rooms = scrapy.Field()  # Количество комнат
    area_sqm = scrapy.Field()  # Площадь в м²
    land_area_sotka = scrapy.Field()  # Площадь участка в сотках
    floor = scrapy.Field()  # Этаж
    total_floors = scrapy.Field()  # Всего этажей
    series = scrapy.Field()  # Серия дома
    building_type = scrapy.Field()  # Тип здания
    condition = scrapy.Field()  # Состояние/Ремонт
    furniture = scrapy.Field()  # Мебель
    heating = scrapy.Field()  # Отопление
    hot_water = scrapy.Field()  # Горячая вода
    gas = scrapy.Field()  # Газ
    ceiling_height = scrapy.Field()  # Высота потолков
    
    # Контакты
    phone_numbers = scrapy.Field()  # Список телефонных номеров
    
    # Локация
    city = scrapy.Field()  # Город
    district = scrapy.Field()  # Район
    address = scrapy.Field()  # Адрес
    
    # Метаданные

    published_at = scrapy.Field()  # Дата публикации
    parsed_at = scrapy.Field()  # Дата парсинга
    attributes = scrapy.Field()  # Дополнительные атрибуты

    
    # Фотографии
    images = scrapy.Field()  # Список URL фотографий
