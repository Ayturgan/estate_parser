from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, JSON, ForeignKey
)
from sqlalchemy.orm import relationship
from app.database import Base


class DBLocation(Base):
    __tablename__ = 'locations'

    id = Column(Integer, primary_key=True, index=True)
    city = Column(String, nullable=True)
    district = Column(String, nullable=True)
    address = Column(String, nullable=True)

    # Обратная связь к объявлениям
    ads = relationship("DBAd", back_populates="location")


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
    unique_ad_id = Column(Integer, ForeignKey('ads.id'), nullable=True)
    duplicate_of_ids = Column(JSON, nullable=True)  # можно хранить список ID дубликатов

    # Связь с локацией
    location = relationship("DBLocation", back_populates="ads")

    # Связь с фотографиями
    photos = relationship("DBPhoto", back_populates="ad", cascade="all, delete-orphan")

    # Self-referential связи для дубликатов
    duplicates_list = relationship(
        "DBAd",
        back_populates="unique_parent_ad",
        cascade="all, delete-orphan",
        foreign_keys="[DBAd.unique_ad_id]"
    )
    unique_parent_ad = relationship(
        "DBAd",
        remote_side=[id],
        back_populates="duplicates_list",
        foreign_keys=[unique_ad_id]
    )


class DBPhoto(Base):
    __tablename__ = 'photos'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    url = Column(String, nullable=False)
    hash = Column(String, nullable=True)
    ad_id = Column(Integer, ForeignKey('ads.id'))

    # Связь с объявлением
    ad = relationship("DBAd", back_populates="photos")
