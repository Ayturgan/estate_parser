from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict
from datetime import datetime


class Location(BaseModel):
    address: Optional[str] = Field(None, description="Полный адрес объявления")
    district: Optional[str] = Field(None, description="Район")
    city: Optional[str] = Field(None, description="Город")


class Photo(BaseModel):
    url: HttpUrl = Field(..., description="URL фотографии")
    hash: Optional[str] = Field(None, description="Perceptual hash изображения для сравнения дубликатов")


class Ad(BaseModel):
    id: Optional[int] = Field(None, description="Уникальный ID объявления (из базы)")

    source_url: HttpUrl = Field(..., description="URL оригинального объявления на сайте-источнике")
    source_name: str = Field(..., description="Название сайта-источника (например, 'house.kg', 'lalafo.kg', 'stroka.kg')")
    title: str = Field(..., description="Заголовок объявления")
    description: Optional[str] = Field(None, description="Полное описание объявления")
    price: Optional[float] = Field(None, description="Цена объявления")
    price_original: Optional[str] = Field(None, description="Оригинальная строка с ценой")
    currency: Optional[str] = Field("USD", description="Валюта цены (например, 'USD', 'KGS')")

    area_sqm: Optional[float] = Field(None, description="Площадь в квадратных метрах")
    rooms: Optional[int] = Field(None, description="Количество комнат")
    floor: Optional[int] = Field(None, description="Этаж")
    total_floors: Optional[int] = Field(None, description="Всего этажей в здании")
    series: Optional[str] = Field(None, description="Тип дома (элитка, хрущевка и т.д.)")
    building_type: Optional[str] = Field(None, description="Тип здания (монолитный, кирпичный и т.д.)")
    building_year: Optional[int] = Field(None, description="Год постройки здания")

    condition: Optional[str] = Field(None, description="Состояние квартиры")
    repair: Optional[str] = Field(None, description="Тип ремонта")
    furniture: Optional[str] = Field(None, description="Наличие мебели")

    heating: Optional[str] = Field(None, description="Тип отопления")
    hot_water: Optional[str] = Field(None, description="Горячая вода")
    gas: Optional[str] = Field(None, description="Газ")
    ceiling_height: Optional[float] = Field(None, description="Высота потолков")

    phone_numbers: List[str] = Field(default_factory=list, description="Список телефонных номеров")
    # У тебя в базе нет поля email, contact_name, их можно убрать или оставить необязательными без связи с БД

    location: Optional[Location] = Field(None, description="Географические данные объявления")
    photos: List[Photo] = Field(default_factory=list, description="Список фотографий объявления")

    attributes: Dict[str, Optional[str]] = Field(default_factory=dict, description="Словарь дополнительных атрибутов")

    published_at: Optional[datetime] = Field(None, description="Дата и время публикации объявления на источнике (ISO 8601)")
    parsed_at: Optional[datetime] = Field(None, description="Дата и время парсинга объявления")

    is_vip: bool = Field(False, description="Флаг VIP-объявления")
    is_realtor: bool = Field(False, description="Флаг, указывающий, является ли объявление от риэлтора")
    realtor_score: Optional[float] = Field(None, description="Оценка вероятности, что это риэлтор")

    is_duplicate: bool = Field(False, description="Флаг, указывающий, является ли это объявление дубликатом")
    unique_ad_id: Optional[int] = Field(None, description="ID уникального объявления, если это дубликат")
    duplicate_of_ids: List[int] = Field(default_factory=list, description="Список ID объявлений, которые дублируют это уникальное объявление")
