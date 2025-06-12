# db_models.py

from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY # Для списков строк
from sqlalchemy.ext.mutable import MutableDict # Для изменяемых JSON-полей

from app.database import Base # Импортируем базовый класс для моделей

# Модель для таблицы 'locations'
class DBLocation(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    address = Column(String, index=True, nullable=True)
    district = Column(String, index=True, nullable=True)
    city = Column(String, index=True, nullable=True)
    region = Column(String, index=True, nullable=True)

    # Связь с объявлениями
    ads = relationship("DBAd", back_populates="location_obj")

# Модель для таблицы 'photos'
class DBPhoto(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False)
    hash = Column(String, nullable=True) # Perceptual hash

    ad_id = Column(String, ForeignKey("ads.id"))
    ad = relationship("DBAd", back_populates="photos_obj")

# Модель для таблицы 'ads'
class DBAd(Base):
    __tablename__ = "ads"

    id = Column(String, primary_key=True, index=True, unique=True)
    source_url = Column(String, nullable=False)
    source_name = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    price = Column(Float, nullable=True)
    currency = Column(String, default="RUB")

    area_sqm = Column(Float, nullable=True)
    rooms = Column(Integer, nullable=True)
    floor = Column(Integer, nullable=True)
    total_floors = Column(Integer, nullable=True)

    phone_numbers = Column(ARRAY(String), default=[])
    email = Column(String, nullable=True)
    contact_name = Column(String, nullable=True)

    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    location_obj = relationship("DBLocation", back_populates="ads")

    photos_obj = relationship("DBPhoto", back_populates="ad")

    attributes = Column(MutableDict.as_mutable(JSON), default={})

    published_at = Column(DateTime, nullable=True)
    parsed_at = Column(DateTime, nullable=True)

    is_realtor = Column(Boolean, default=False)
    realtor_score = Column(Float, nullable=True)

    is_duplicate = Column(Boolean, default=False)

    # Изменяем unique_ad_id на внешний ключ, ссылающийся на id этой же таблицы
    unique_ad_id = Column(String, ForeignKey('ads.id'), nullable=True) 

    # Отношение для получения "родительского" уникального объявления, если текущее - дубликат
    unique_parent_ad = relationship(
    'DBAd', 
    remote_side=[id], # Указываем, что id - это удаленная сторона отношения
    back_populates='duplicates_list', # Обратное отношение
    uselist=False # Одно объявление может иметь только одного уникального родителя
    )

    # Отношение для получения списка дубликатов, если текущее - уникальное объявление
    duplicates_list = relationship(
    'DBAd', 
    back_populates='unique_parent_ad', # Обратное отношение
    foreign_keys=[unique_ad_id] # Указываем, какой столбец является внешним ключом
    )

    # duplicate_of_ids - это поле теперь не нужно для ORM-связи, но может остаться для хранения
    # списка ID, если это требуется для какой-то специфической логики.
    # Для ORM-связи мы используем duplicates_list.
    # Если это поле не будет использоваться, его можно удалить.
    # Пока оставим, но в дальнейшем, возможно, уберем.
    duplicate_of_ids = Column(ARRAY(String), default=[]) 
