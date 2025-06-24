from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime


class DBLocation(Base):
    __tablename__ = 'locations'

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String, nullable=True, index=True)
    district = Column(String, nullable=True, index=True)
    address = Column(String, nullable=True, index=True)

    # Обратная связь к объявлениям с каскадным удалением
    ads = relationship("DBAd", back_populates="location", cascade="all, delete-orphan")
    unique_ads = relationship("DBUniqueAd", back_populates="location", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Location(id={self.id}, city='{self.city}', district='{self.district}', address='{self.address}')>"


class DBAd(Base):
    __tablename__ = 'ads'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    source_id = Column(String, unique=True, index=True, nullable=True)
    source_name = Column(String, nullable=True, index=True)
    source_url = Column(String, nullable=True, index=True)
    title = Column(String, nullable=True, index=True)
    description = Column(String, nullable=True)
    price = Column(Float, nullable=True, index=True)
    price_original = Column(String, nullable=True)
    currency = Column(String, nullable=True)
    rooms = Column(Integer, nullable=True, index=True)
    area_sqm = Column(Float, nullable=True, index=True)
    floor = Column(Integer, nullable=True)
    total_floors = Column(Integer, nullable=True)
    series = Column(String, nullable=True, index=True)
    building_type = Column(String, nullable=True)
    condition = Column(String, nullable=True)
    repair = Column(String, nullable=True)
    furniture = Column(String, nullable=True)
    heating = Column(String, nullable=True)
    hot_water = Column(String, nullable=True)
    gas = Column(String, nullable=True)
    ceiling_height = Column(Float, nullable=True)
    phone_numbers = Column(JSONB, nullable=True)
    location_id = Column(Integer, ForeignKey('locations.id', ondelete='CASCADE'), nullable=True, index=True)
    is_vip = Column(Boolean, default=False, index=True)
    published_at = Column(DateTime, nullable=True, index=True)
    parsed_at = Column(DateTime, nullable=True)
    attributes = Column(JSONB, nullable=True)
    is_realtor = Column(Boolean, default=False, index=True)
    realtor_score = Column(Float, nullable=True)

    # Поля для работы с дубликатами
    is_duplicate = Column(Boolean, default=False, index=True)
    is_processed = Column(Boolean, default=False, index=True)
    processed_at = Column(DateTime, nullable=True)

    # Связь с локацией
    location = relationship("DBLocation", back_populates="ads")

    # Связь с фотографиями
    photos = relationship("DBPhoto", back_populates="ad", cascade="all, delete-orphan")

    unique_ad_id = Column(Integer, ForeignKey('unique_ads.id', ondelete='SET NULL'), nullable=True, index=True)
    unique_ad = relationship("DBUniqueAd", foreign_keys=[unique_ad_id], back_populates="original_ads")

    # Связь с дубликатами
    duplicate_info = relationship("DBAdDuplicate", back_populates="original_ad", uselist=False, cascade="all, delete-orphan")
    
    # Обратная связь к уникальным объявлениям, где это объявление является базовым
    base_unique_ads = relationship("DBUniqueAd", foreign_keys="DBUniqueAd.base_ad_id", back_populates="base_ad")

    def __repr__(self):
        return f"<Ad(id={self.id}, title='{self.title}', price={self.price}, source='{self.source_name}')>"
        


class DBPhoto(Base):
    __tablename__ = 'photos'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    url = Column(String, nullable=False, index=True)
    hash = Column(String, nullable=True, index=True)
    ad_id = Column(Integer, ForeignKey('ads.id', ondelete='CASCADE'), index=True)

    # Связь с объявлением
    ad = relationship("DBAd", back_populates="photos")

    def __repr__(self):
        return f"<Photo(id={self.id}, url='{self.url}')>"


class DBUniqueAd(Base):
    """Уникальное объявление - результат объединения дублей"""
    __tablename__ = 'unique_ads'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, nullable=True, index=True)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=True, index=True)
    price_original = Column(String, nullable=True)
    currency = Column(String, nullable=True)
    phone_numbers = Column(JSONB, nullable=True)
    
    # Характеристики недвижимости
    rooms = Column(Integer, nullable=True, index=True)
    area_sqm = Column(Float, nullable=True, index=True)
    floor = Column(Integer, nullable=True)
    total_floors = Column(Integer, nullable=True)
    series = Column(String, nullable=True, index=True)
    building_type = Column(String, nullable=True)
    condition = Column(String, nullable=True)
    repair = Column(String, nullable=True)
    furniture = Column(String, nullable=True) 
    heating = Column(String, nullable=True)
    hot_water = Column(String, nullable=True)
    gas = Column(String, nullable=True)
    ceiling_height = Column(Float, nullable=True)
    
    # Локация
    location_id = Column(Integer, ForeignKey('locations.id', ondelete='CASCADE'), nullable=True, index=True)
    location = relationship("DBLocation", back_populates="unique_ads")
    
    # Новое поле: ссылка на базовое объявление
    base_ad_id = Column(Integer, ForeignKey('ads.id', ondelete='SET NULL'), nullable=True)
    
    # Метаданные
    is_vip = Column(Boolean, default=False, index=True)
    is_realtor = Column(Boolean, default=False, index=True)
    realtor_score = Column(Float, nullable=True)
    attributes = Column(JSONB, nullable=True)
    
    # Аналитические данные
    photo_hashes = Column(JSONB, nullable=True)
    text_embeddings = Column(JSONB, nullable=True)
    confidence_score = Column(Float, nullable=True)
    
    # Статистика
    duplicates_count = Column(Integer, default=0, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    photos = relationship("DBUniquePhoto", back_populates="unique_ad", cascade="all, delete-orphan")
    duplicates = relationship("DBAdDuplicate", back_populates="unique_ad", cascade="all, delete-orphan")
    base_ad = relationship("DBAd", foreign_keys=[base_ad_id], back_populates="base_unique_ads")
    original_ads = relationship("DBAd", foreign_keys="DBAd.unique_ad_id", back_populates="unique_ad")

    def __repr__(self):
        return f"<UniqueAd(id={self.id}, title='{self.title}', price={self.price})>"


class DBUniquePhoto(Base):
    """Фотографии уникальных объявлений"""
    __tablename__ = 'unique_photos'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    url = Column(String, nullable=False, index=True)
    hash = Column(String, nullable=True, index=True)
    unique_ad_id = Column(Integer, ForeignKey('unique_ads.id', ondelete='CASCADE'), index=True)
    
    # Связь с уникальным объявлением
    unique_ad = relationship("DBUniqueAd", back_populates="photos")

    def __repr__(self):
        return f"<UniquePhoto(id={self.id}, url='{self.url}')>"


class DBAdDuplicate(Base):
    """Связка: какие исходные объявления относятся к уникальному"""
    __tablename__ = 'ad_duplicates'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    unique_ad_id = Column(Integer, ForeignKey('unique_ads.id', ondelete='CASCADE'), index=True)
    original_ad_id = Column(Integer, ForeignKey('ads.id', ondelete='CASCADE'), index=True)
    
    # Метрики схожести
    photo_similarity = Column(Float, nullable=True)
    text_similarity = Column(Float, nullable=True)
    contact_similarity = Column(Float, nullable=True)
    address_similarity = Column(Float, nullable=True)
    overall_similarity = Column(Float, nullable=True)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Связи
    unique_ad = relationship("DBUniqueAd", back_populates="duplicates")
    original_ad = relationship("DBAd", back_populates="duplicate_info")

    def __repr__(self):
        return f"<AdDuplicate(id={self.id}, unique_ad_id={self.unique_ad_id}, original_ad_id={self.original_ad_id})>"
