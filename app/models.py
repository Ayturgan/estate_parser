# models.py

from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict

class Location(BaseModel):
    """
    Модель для географических координат.
    """
    address: Optional[str] = Field(None, description="Полный адрес объявления")
    district: Optional[str] = Field(None, description="Район")
    city: Optional[str] = Field(None, description="Город")
    region: Optional[str] = Field(None, description="Регион/Область")

class Photo(BaseModel):
    """
    Модель для информации о фотографии.
    """
    url: HttpUrl = Field(..., description="URL фотографии")
    hash: Optional[str] = Field(None, description="Perceptual hash изображения для сравнения дубликатов")

class Ad(BaseModel):
    """
    Основная модель для объявления о недвижимости.
    """
    id: Optional[str] = Field(None, description="Уникальный ID объявления (будет генерироваться)")
    source_url: HttpUrl = Field(..., description="URL оригинального объявления на сайте-источнике")
    source_name: str = Field(..., description="Название сайта-источника (например, 'Avito', 'Cian')")
    title: str = Field(..., description="Заголовок объявления")
    description: str = Field(..., description="Полное описание объявления")
    price: Optional[float] = Field(None, description="Цена объявления")
    currency: Optional[str] = Field("RUB", description="Валюта цены (например, 'RUB', 'USD')")
    
    # Атрибуты недвижимости
    area_sqm: Optional[float] = Field(None, description="Площадь в квадратных метрах")
    rooms: Optional[int] = Field(None, description="Количество комнат")
    floor: Optional[int] = Field(None, description="Этаж")
    total_floors: Optional[int] = Field(None, description="Всего этажей в здании")
    
    # Контактная информация
    phone_numbers: List[str] = Field([], description="Список телефонных номеров")
    email: Optional[str] = Field(None, description="Email контактного лица")
    contact_name: Optional[str] = Field(None, description="Имя контактного лица")

    # Геоданные
    location: Optional[Location] = Field(None, description="Географические данные объявления")

    # Фотографии
    photos: List[Photo] = Field([], description="Список фотографий объявления")

    # Дополнительные атрибуты, которые могут быть специфичны для разных сайтов
    attributes: Dict[str, str] = Field({}, description="Словарь дополнительных атрибутов (например, 'тип_дома': 'кирпичный')")

    # Временные метки
    published_at: Optional[str] = Field(None, description="Дата и время публикации объявления на источнике (в формате ISO 8601)")
    parsed_at: Optional[str] = Field(None, description="Дата и время парсинга объявления (будет генерироваться)")

    # Поля для определения риэлторов
    is_realtor: bool = Field(False, description="Флаг, указывающий, является ли объявление от риэлтора")
    realtor_score: Optional[float] = Field(None, description="Оценка вероятности, что это риэлтор")

    # Поля для дубликатов (будут заполняться позже)
    is_duplicate: bool = Field(False, description="Флаг, указывающий, является ли это объявление дубликатом")
    unique_ad_id: Optional[str] = Field(None, description="ID уникального объявления, если это дубликат")
    duplicate_of_ids: List[str] = Field([], description="Список ID объявлений, которые дублируют это уникальное объявление")

