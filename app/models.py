from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime


class Location(BaseModel):
    address: Optional[str] = Field(None, description="Полный адрес объявления")
    district: Optional[str] = Field(None, description="Район")
    city: Optional[str] = Field(None, description="Город")


class Photo(BaseModel):
    url: HttpUrl = Field(..., description="URL фотографии")
    hash: Optional[str] = Field(None, description="Perceptual hash изображения для сравнения дубликатов")


class UniquePhoto(BaseModel):
    url: HttpUrl = Field(..., description="URL фотографии")
    hash: Optional[str] = Field(None, description="Perceptual hash изображения для сравнения дубликатов")


class DuplicateInfo(BaseModel):
    id: int = Field(..., description="ID записи о дубликате")
    unique_ad_id: int = Field(..., description="ID уникального объявления")
    photo_similarity: Optional[float] = Field(None, description="Схожесть фотографий")
    text_similarity: Optional[float] = Field(None, description="Схожесть текста")
    contact_similarity: Optional[float] = Field(None, description="Схожесть контактов")
    address_similarity: Optional[float] = Field(None, description="Схожесть адресов")
    overall_similarity: Optional[float] = Field(None, description="Общая схожесть")
    created_at: Optional[datetime] = Field(None, description="Дата создания записи о дубликате")


class UniqueAd(BaseModel):
    id: Optional[int] = Field(None, description="Уникальный ID объявления")
    title: str = Field(..., description="Заголовок объявления")
    description: Optional[str] = Field(None, description="Полное описание объявления")
    price: Optional[float] = Field(None, description="Цена объявления")
    price_original: Optional[str] = Field(None, description="Оригинальная строка с ценой")
    currency: Optional[str] = Field("USD", description="Валюта цены")
    
    area_sqm: Optional[float] = Field(None, description="Площадь в квадратных метрах")
    rooms: Optional[int] = Field(None, description="Количество комнат")
    floor: Optional[int] = Field(None, description="Этаж")
    total_floors: Optional[int] = Field(None, description="Всего этажей в здании")
    series: Optional[str] = Field(None, description="Тип дома")
    building_type: Optional[str] = Field(None, description="Тип здания")
    condition: Optional[str] = Field(None, description="Состояние квартиры")
    repair: Optional[str] = Field(None, description="Тип ремонта")
    furniture: Optional[str] = Field(None, description="Наличие мебели")
    heating: Optional[str] = Field(None, description="Тип отопления")
    hot_water: Optional[str] = Field(None, description="Горячая вода")
    gas: Optional[str] = Field(None, description="Газ")
    ceiling_height: Optional[float] = Field(None, description="Высота потолков")
    
    phone_numbers: List[str] = Field(default_factory=list, description="Список телефонных номеров")
    location: Optional[Location] = Field(None, description="Географические данные объявления")
    photos: List[UniquePhoto] = Field(default_factory=list, description="Список фотографий объявления")
    
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Словарь дополнительных атрибутов")
    is_vip: bool = Field(False, description="Флаг VIP-объявления")
    is_realtor: bool = Field(False, description="Флаг, указывающий, является ли объявление от риэлтора")
    realtor_score: Optional[float] = Field(None, description="Оценка вероятности, что это риэлтор")
    
    photo_hashes: List[str] = Field(default_factory=list, description="Список хэшей фотографий")
    confidence_score: Optional[float] = Field(None, description="Общая уверенность в уникальности")
    duplicates_count: int = Field(0, description="Количество найденных дубликатов")
    
    base_ad_id: Optional[int] = None
    
    created_at: Optional[datetime] = Field(None, description="Дата создания уникального объявления")
    updated_at: Optional[datetime] = Field(None, description="Дата последнего обновления")


class Ad(BaseModel):
    id: Optional[int] = Field(None, description="Уникальный ID объявления (из базы)")
    source_id: Optional[str] = None
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

    location: Optional[Location] = Field(None, description="Географические данные объявления")
    photos: List[Photo] = Field(default_factory=list, description="Список фотографий объявления")

    attributes: Dict[str, Any] = Field(default_factory=dict, description="Словарь дополнительных атрибутов")

    published_at: Optional[datetime] = Field(None, description="Дата и время публикации объявления на источнике (ISO 8601)")
    parsed_at: Optional[datetime] = Field(None, description="Дата и время парсинга объявления")

    is_vip: bool = Field(default=False, description="Флаг VIP-объявления")
    is_realtor: bool = Field(default=False, description="Флаг, указывающий, является ли объявление от риэлтора")
    realtor_score: Optional[float] = Field(None, description="Оценка вероятности, что это риэлтор")

    is_duplicate: bool = Field(default=False, description="Флаг, указывающий, является ли это объявление дубликатом")
    is_processed: bool = Field(default=False, description="Флаг, указывающий, было ли обработано объявление на дубликаты")
    processed_at: Optional[datetime] = Field(None, description="Дата и время обработки объявления на дубликаты")
    duplicate_info: Optional[DuplicateInfo] = Field(None, description="Информация о дубликате, если объявление является дубликатом")

class PaginatedUniqueAdsResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: List[UniqueAd]

class PaginatedAdsResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: List[Ad]

class AdSource(BaseModel):
    id: int
    source_url: str
    source_name: str
    published_at: Optional[datetime]
    is_base: bool = False

class DuplicateInfo(BaseModel):
    unique_ad_id: int
    total_duplicates: int
    base_ad: Optional[Ad]
    duplicates: List[Ad]
    sources: List[AdSource]

class StatsResponse(BaseModel):
    total_unique_ads: int
    total_original_ads: int
    total_duplicates: int
    realtor_ads: int
    deduplication_ratio: float

class AdCreateRequest(BaseModel):
    source_id: Optional[str] = None
    source_url: str
    source_name: str
    title: str
    description: Optional[str] = None
    price: Optional[float] = None
    price_original: Optional[str] = None
    currency: Optional[str] = "USD"
    rooms: Optional[int] = None
    area_sqm: Optional[float] = None
    floor: Optional[int] = None
    total_floors: Optional[int] = None
    series: Optional[str] = None
    building_type: Optional[str] = None
    condition: Optional[str] = None
    repair: Optional[str] = None
    furniture: Optional[str] = None
    heating: Optional[str] = None
    hot_water: Optional[str] = None
    gas: Optional[str] = None
    ceiling_height: Optional[float] = None
    phone_numbers: Optional[List[str]] = None
    location: Optional[Location] = None
    photos: Optional[List[Photo]] = None
    attributes: Optional[Dict] = {}
    published_at: Optional[str] = None