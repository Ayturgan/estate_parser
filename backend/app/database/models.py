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
    characteristics_similarity: Optional[float] = Field(None, description="Схожесть по характеристикам недвижимости")
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
    land_area_sotka: Optional[float] = Field(None, description="Площадь участка в сотках")
    rooms: Optional[int] = Field(None, description="Количество комнат")
    floor: Optional[int] = Field(None, description="Этаж")
    total_floors: Optional[int] = Field(None, description="Всего этажей в здании")
    series: Optional[str] = Field(None, description="Тип дома")
    building_type: Optional[str] = Field(None, description="Тип здания")
    condition: Optional[str] = Field(None, description="Состояние квартиры")
    furniture: Optional[str] = Field(None, description="Наличие мебели")
    heating: Optional[str] = Field(None, description="Тип отопления")
    hot_water: Optional[str] = Field(None, description="Горячая вода")
    gas: Optional[str] = Field(None, description="Газ")
    ceiling_height: Optional[float] = Field(None, description="Высота потолков")
    
    phone_numbers: List[str] = Field(default_factory=list, description="Список телефонных номеров")
    location: Optional[Location] = Field(None, description="Географические данные объявления")
    photos: List[UniquePhoto] = Field(default_factory=list, description="Список фотографий объявления")
    
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Словарь дополнительных атрибутов")


    realtor: Optional["Realtor"] = Field(None, description="Данные риэлтора")
    
    # Новые поля для классификации (заполняются ИИ)
    property_type: Optional[str] = Field(None, description="Тип недвижимости (квартира, дом, участок, другое)")
    property_origin: Optional[str] = Field(None, description="Происхождение недвижимости (новостройка, вторичка, неизвестно)")
    listing_type: Optional[str] = Field(None, description="Тип объявления (продажа, аренда)")
    realtor_id: Optional[int] = Field(None, description="ID риэлтора")
    
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
    land_area_sotka: Optional[float] = Field(None, description="Площадь участка в сотках")
    rooms: Optional[int] = Field(None, description="Количество комнат")
    floor: Optional[int] = Field(None, description="Этаж")
    total_floors: Optional[int] = Field(None, description="Всего этажей в здании")
    series: Optional[str] = Field(None, description="Тип дома (элитка, хрущевка и т.д.)")
    building_type: Optional[str] = Field(None, description="Тип здания (монолитный, кирпичный и т.д.)")
    building_year: Optional[int] = Field(None, description="Год постройки здания")

    condition: Optional[str] = Field(None, description="Состояние квартиры")
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



    realtor: Optional["Realtor"] = Field(None, description="Данные риэлтора")
    
    # Новые поля для классификации (заполняются ИИ)
    property_type: Optional[str] = Field(None, description="Тип недвижимости (квартира, дом, участок, другое)")
    property_origin: Optional[str] = Field(None, description="Происхождение недвижимости (новостройка, вторичка, неизвестно)")
    listing_type: Optional[str] = Field(None, description="Тип объявления (продажа, аренда)")
    realtor_id: Optional[int] = Field(None, description="ID риэлтора")

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
    land_area_sotka: Optional[float] = None
    floor: Optional[int] = None
    total_floors: Optional[int] = None
    series: Optional[str] = None
    building_type: Optional[str] = None
    condition: Optional[str] = None
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
    
    # Новые поля для классификации (заполняются ИИ)
    property_type: Optional[str] = Field(None, description="Тип недвижимости (квартира, дом, участок, другое)")
    property_origin: Optional[str] = Field(None, description="Происхождение недвижимости (новостройка, вторичка, неизвестно)")
    listing_type: Optional[str] = Field(None, description="Тип объявления (продажа, аренда)")
    realtor_id: Optional[int] = Field(None, description="ID риэлтора")


class Realtor(BaseModel):
    id: Optional[int] = Field(None, description="ID риэлтора")
    phone_number: str = Field(..., description="Номер телефона риэлтора")
    name: Optional[str] = Field(None, description="Имя риэлтора")
    company_name: Optional[str] = Field(None, description="Название компании")
    total_ads_count: int = Field(0, description="Общее количество объявлений")
    active_ads_count: int = Field(0, description="Количество активных объявлений")
    first_seen: Optional[datetime] = Field(None, description="Дата первого появления")
    last_activity: Optional[datetime] = Field(None, description="Дата последней активности")
    confidence_score: float = Field(0.0, description="Уверенность что это риэлтор (0-1)")
    
    # Статистика
    average_price: Optional[float] = Field(None, description="Средняя цена объявлений")
    favorite_districts: Optional[Dict[str, int]] = Field(None, description="Любимые районы с количеством")
    property_types: Optional[Dict[str, int]] = Field(None, description="Статистика по типам недвижимости")
    
    created_at: Optional[datetime] = Field(None, description="Дата создания записи")
    updated_at: Optional[datetime] = Field(None, description="Дата обновления записи")


class RealtorCreateRequest(BaseModel):
    phone_number: str = Field(..., description="Номер телефона риэлтора")
    name: Optional[str] = Field(None, description="Имя риэлтора")
    company_name: Optional[str] = Field(None, description="Название компании")


class RealtorStatsResponse(BaseModel):
    total_realtors: int = Field(..., description="Общее количество риэлторов")
    active_realtors: int = Field(..., description="Количество активных риэлторов")
    avg_ads_per_realtor: float = Field(..., description="Среднее количество объявлений на риэлтора")


class RealtorWithAds(BaseModel):
    realtor: Realtor
    recent_ads: List[Ad] = Field(default_factory=list, description="Последние объявления риэлтора")


class DuplicateStatistics(BaseModel):
    total_unique_ads: int = Field(..., description="Общее количество уникальных объявлений")
    total_original_ads: int = Field(..., description="Общее количество исходных объявлений")
    base_ads: int = Field(..., description="Количество базовых объявлений")
    duplicate_ads: int = Field(..., description="Количество дубликатов")
    unique_ads_with_duplicates: int = Field(..., description="Количество уникальных объявлений с дубликатами")
    avg_duplicates_per_unique: float = Field(..., description="Среднее количество дубликатов на уникальное объявление")
    deduplication_ratio: float = Field(..., description="Процент дедупликации")


# === МОДЕЛИ ДЛЯ АВТОРИЗАЦИИ ===

class AdminLogin(BaseModel):
    """Модель для входа администратора"""
    username: str = Field(..., description="Имя пользователя")
    password: str = Field(..., description="Пароль")

class AdminCreate(BaseModel):
    """Модель для создания нового администратора"""
    username: str = Field(..., min_length=3, max_length=50, description="Имя пользователя")
    password: str = Field(..., min_length=6, description="Пароль")
    full_name: Optional[str] = Field(None, max_length=100, description="Полное имя")

class AdminResponse(BaseModel):
    """Модель ответа с данными администратора"""
    id: int = Field(..., description="ID администратора")
    username: str = Field(..., description="Имя пользователя")
    full_name: Optional[str] = Field(None, description="Полное имя")
    created_at: datetime = Field(..., description="Дата создания")
    last_login_at: Optional[datetime] = Field(None, description="Последний вход")
    is_active: bool = Field(..., description="Активность аккаунта")

class Token(BaseModel):
    """Модель токена авторизации"""
    access_token: str = Field(..., description="JWT токен")
    token_type: str = Field(default="bearer", description="Тип токена")
    expires_in: int = Field(..., description="Время жизни токена в секундах")

class AdminChangePassword(BaseModel):
    """Модель для смены пароля администратора"""
    current_password: str = Field(..., description="Текущий пароль")
    new_password: str = Field(..., min_length=6, description="Новый пароль")