from app.db_models import DBAd, DBPhoto, DBLocation, DBUniqueAd, DBAdDuplicate, DBUniquePhoto
from app.models import Ad, Photo, Location, UniqueAd, UniquePhoto
from typing import List
import json
import pydantic


def transform_location(db_location: DBLocation) -> Location:
    return Location(
        address=db_location.address,
        district=db_location.district,
        city=db_location.city,
    )


def transform_photos(db_photos: List[DBPhoto]) -> List[Photo]:
    return [Photo(url=photo.url, hash=photo.hash) for photo in db_photos]


def transform_unique_photos(db_photos: List[DBUniquePhoto]) -> List[UniquePhoto]:
    return [UniquePhoto(url=photo.url, hash=photo.hash) for photo in db_photos]


def to_elasticsearch_dict(ad: UniqueAd) -> dict:
    """Преобразует объект UniqueAd или словарь в JSON-совместимый словарь для Elasticsearch"""
    def clean_value(v):
        if v is None:
            return None
        if isinstance(v, str) and v == 'None':
            return None
        if isinstance(v, list):
            return [clean_value(x) for x in v]
        if isinstance(v, dict):
            return {kk: clean_value(vv) for kk, vv in v.items()}
        # HttpUrl и другие pydantic-типы
        if hasattr(v, 'url') and hasattr(v, '__str__'):
            return str(v)
        if isinstance(v, (pydantic.BaseModel,)):
            return clean_value(v.dict())
        if hasattr(v, 'isoformat'):
            return v.isoformat()
        # Оставляем числа, bool, str
        if isinstance(v, (int, float, bool, str)):
            return v
        # Всё остальное — строкой
        return str(v)
    if hasattr(ad, 'dict'):
        ad = ad.dict()
    return {k: clean_value(v) for k, v in ad.items()}


def transform_unique_ad(db_unique_ad: DBUniqueAd) -> UniqueAd:
    # Преобразуем фотографии в строки URL
    photos = []
    for photo in db_unique_ad.photos:
        photos.append({
            'url': str(photo.url),
            'hash': photo.hash
        })
    
    # Преобразуем даты в строки ISO
    created_at = db_unique_ad.created_at.isoformat() if db_unique_ad.created_at else None
    updated_at = db_unique_ad.updated_at.isoformat() if db_unique_ad.updated_at else None
    
    # Преобразуем location
    location_data = None
    if db_unique_ad.location:
        location_data = {
            'address': db_unique_ad.location.address,
            'district': db_unique_ad.location.district,
            'city': db_unique_ad.location.city
        }
    
    return UniqueAd(
        id=db_unique_ad.id,
        title=db_unique_ad.title,
        description=db_unique_ad.description,
        price=db_unique_ad.price,
        price_original=db_unique_ad.price_original,
        currency=db_unique_ad.currency,
        area_sqm=db_unique_ad.area_sqm,
        rooms=db_unique_ad.rooms,
        floor=db_unique_ad.floor,
        total_floors=db_unique_ad.total_floors,
        series=db_unique_ad.series,
        building_type=db_unique_ad.building_type,
        condition=db_unique_ad.condition,
        repair=db_unique_ad.repair,
        furniture=db_unique_ad.furniture,
        heating=db_unique_ad.heating,
        hot_water=db_unique_ad.hot_water,
        gas=db_unique_ad.gas,
        ceiling_height=db_unique_ad.ceiling_height,
        phone_numbers=db_unique_ad.phone_numbers,
        location=location_data,
        photos=photos,
        attributes=db_unique_ad.attributes,
        is_vip=db_unique_ad.is_vip,
        is_realtor=db_unique_ad.is_realtor,
        realtor_score=db_unique_ad.realtor_score,
        photo_hashes=db_unique_ad.photo_hashes or [],
        confidence_score=db_unique_ad.confidence_score,
        duplicates_count=db_unique_ad.duplicates_count,
        created_at=created_at,
        updated_at=updated_at
    )


def transform_ad(db_ad: DBAd) -> Ad:
    """Преобразует DBAd в Ad"""
    # Преобразуем атрибуты из JSON в словарь
    attributes = {}
    if db_ad.attributes:
        try:
            if isinstance(db_ad.attributes, str):
                attributes = json.loads(db_ad.attributes)
            elif isinstance(db_ad.attributes, dict):
                attributes = db_ad.attributes
        except json.JSONDecodeError:
            pass

    # Преобразуем фотографии в строки URL
    photos = []
    for photo in db_ad.photos:
        photos.append({
            'url': str(photo.url),
            'hash': photo.hash
        })
    
    # Преобразуем даты в строки ISO
    published_at = db_ad.published_at.isoformat() if db_ad.published_at else None
    parsed_at = db_ad.parsed_at.isoformat() if db_ad.parsed_at else None
    processed_at = db_ad.processed_at.isoformat() if db_ad.processed_at else None
    
    # Преобразуем location
    location_data = None
    if db_ad.location:
        location_data = {
            'address': db_ad.location.address,
            'district': db_ad.location.district,
            'city': db_ad.location.city
        }
    
    # Преобразуем duplicate_info
    duplicate_info_data = None
    if db_ad.duplicate_info:
        duplicate_info_data = {
            'id': db_ad.duplicate_info.id,
            'unique_ad_id': db_ad.duplicate_info.unique_ad_id,
            'photo_similarity': db_ad.duplicate_info.photo_similarity,
            'text_similarity': db_ad.duplicate_info.text_similarity,
            'contact_similarity': db_ad.duplicate_info.contact_similarity,
            'address_similarity': db_ad.duplicate_info.address_similarity,
            'overall_similarity': db_ad.duplicate_info.overall_similarity,
            'created_at': db_ad.duplicate_info.created_at.isoformat() if db_ad.duplicate_info.created_at else None
        }

    return Ad(
        id=db_ad.id,
        source_id=db_ad.source_id,
        source_name=db_ad.source_name,
        source_url=str(db_ad.source_url),
        title=db_ad.title,
        description=db_ad.description,
        price=db_ad.price,
        price_original=db_ad.price_original,
        currency=db_ad.currency,
        rooms=db_ad.rooms,
        area_sqm=db_ad.area_sqm,
        floor=db_ad.floor,
        total_floors=db_ad.total_floors,
        series=db_ad.series,
        building_type=db_ad.building_type,
        condition=db_ad.condition,
        repair=db_ad.repair,
        furniture=db_ad.furniture,
        heating=db_ad.heating,
        hot_water=db_ad.hot_water,
        gas=db_ad.gas,
        ceiling_height=db_ad.ceiling_height,
        phone_numbers=db_ad.phone_numbers,
        location=location_data,
        photos=photos,
        is_vip=db_ad.is_vip,
        published_at=published_at,
        parsed_at=parsed_at,
        attributes=attributes,
        is_realtor=db_ad.is_realtor,
        realtor_score=db_ad.realtor_score,
        is_duplicate=db_ad.is_duplicate,
        is_processed=db_ad.is_processed,
        processed_at=processed_at,
        duplicate_info=duplicate_info_data
    )


def transform_duplicate_info(db_duplicate: DBAdDuplicate) -> dict:
    return {
        'id': db_duplicate.id,
        'unique_ad_id': db_duplicate.unique_ad_id,
        'photo_similarity': db_duplicate.photo_similarity,
        'text_similarity': db_duplicate.text_similarity,
        'contact_similarity': db_duplicate.contact_similarity,
        'address_similarity': db_duplicate.address_similarity,
        'overall_similarity': db_duplicate.overall_similarity,
        'created_at': db_duplicate.created_at.isoformat() if db_duplicate.created_at else None
    }
