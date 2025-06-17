from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, JSON, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime


class DBLocation(Base):
    __tablename__ = 'locations'

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String, nullable=True)
    district = Column(String, nullable=True)
    address = Column(String, nullable=True)

    # Обратная связь к объявлениям
    ads = relationship("DBAd", back_populates="location")
    unique_ads = relationship("DBUniqueAd", back_populates="location")


class DBAd(Base):
    __tablename__ = 'ads'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    source_id = Column(String, unique=True, index=True, nullable=True)
    source_name = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    title = Column(String, nullable=True)
    description = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    price_original = Column(String, nullable=True)
    currency = Column(String, nullable=True)
    rooms = Column(Integer, nullable=True)
    area_sqm = Column(Float, nullable=True)
    floor = Column(Integer, nullable=True)
    total_floors = Column(Integer, nullable=True)
    series = Column(String, nullable=True)
    building_type = Column(String, nullable=True)
    condition = Column(String, nullable=True)
    repair = Column(String, nullable=True)
    furniture = Column(String, nullable=True)
    heating = Column(String, nullable=True)
    hot_water = Column(String, nullable=True)
    gas = Column(String, nullable=True)
    ceiling_height = Column(Float, nullable=True)
    phone_numbers = Column(JSON, nullable=True)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True)
    is_vip = Column(Boolean, default=False)
    published_at = Column(DateTime, nullable=True)
    parsed_at = Column(DateTime, nullable=True)
    attributes = Column(JSON, nullable=True)
    is_realtor = Column(Boolean, default=False)
    realtor_score = Column(Float, nullable=True)

    # Поля для работы с дубликатами
    is_duplicate = Column(Boolean, default=False)
    is_processed = Column(Boolean, default=False)
    processed_at = Column(DateTime, nullable=True)

    # Связь с локацией
    location = relationship("DBLocation", back_populates="ads")

    # Связь с фотографиями
    photos = relationship("DBPhoto", back_populates="ad", cascade="all, delete-orphan")

    # Связь с дубликатами
    duplicate_info = relationship("DBAdDuplicate", back_populates="original_ad", uselist=False)


class DBPhoto(Base):
    __tablename__ = 'photos'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    url = Column(String, nullable=False)
    hash = Column(String, nullable=True)
    ad_id = Column(Integer, ForeignKey('ads.id'))

    # Связь с объявлением
    ad = relationship("DBAd", back_populates="photos")


class DBUniqueAd(Base):
    """Уникальное объявление - результат объединения дублей"""
    __tablename__ = 'unique_ads'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=True)
    price_original = Column(String, nullable=True)
    currency = Column(String, nullable=True)
    phone_numbers = Column(JSON, nullable=True)
    
    # Характеристики недвижимости
    rooms = Column(Integer, nullable=True)
    area_sqm = Column(Float, nullable=True)
    floor = Column(Integer, nullable=True)
    total_floors = Column(Integer, nullable=True)
    series = Column(String, nullable=True)
    building_type = Column(String, nullable=True)
    condition = Column(String, nullable=True)
    repair = Column(String, nullable=True)
    furniture = Column(String, nullable=True)
    heating = Column(String, nullable=True)
    hot_water = Column(String, nullable=True)
    gas = Column(String, nullable=True)
    ceiling_height = Column(Float, nullable=True)
    
    # Локация
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=True)
    location = relationship("DBLocation", back_populates="unique_ads")
    
    # Метаданные
    is_vip = Column(Boolean, default=False)
    is_realtor = Column(Boolean, default=False)
    realtor_score = Column(Float, nullable=True)
    attributes = Column(JSON, nullable=True)
    
    # Аналитические данные
    photo_hashes = Column(JSON, nullable=True)  # Хэши всех фото
    text_embeddings = Column(JSON, nullable=True)  # Векторы для NLP сравнения
    confidence_score = Column(Float, nullable=True)  # Общая уверенность в уникальности
    
    # Статистика
    duplicates_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    photos = relationship("DBUniquePhoto", back_populates="unique_ad", cascade="all, delete-orphan")
    duplicates = relationship("DBAdDuplicate", back_populates="unique_ad", cascade="all, delete-orphan")


class DBUniquePhoto(Base):
    """Фотографии уникальных объявлений"""
    __tablename__ = 'unique_photos'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    url = Column(String, nullable=False)
    hash = Column(String, nullable=True)
    unique_ad_id = Column(Integer, ForeignKey('unique_ads.id'))
    
    # Связь с уникальным объявлением
    unique_ad = relationship("DBUniqueAd", back_populates="photos")


class DBAdDuplicate(Base):
    """Связка: какие исходные объявления относятся к уникальному"""
    __tablename__ = 'ad_duplicates'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    unique_ad_id = Column(Integer, ForeignKey('unique_ads.id'))
    original_ad_id = Column(Integer, ForeignKey('ads.id'))
    
    # Метрики схожести
    photo_similarity = Column(Float, nullable=True)  # Схожесть фото
    text_similarity = Column(Float, nullable=True)   # Схожесть текста
    contact_similarity = Column(Float, nullable=True) # Схожесть контактов
    address_similarity = Column(Float, nullable=True) # Схожесть адресов
    overall_similarity = Column(Float, nullable=True) # Общая схожесть
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    unique_ad = relationship("DBUniqueAd", back_populates="duplicates")
    original_ad = relationship("DBAd", back_populates="duplicate_info")
