from app.db_models import DBAd, DBPhoto, DBLocation, DBUniqueAd, DBAdDuplicate, DBUniquePhoto
from app.models import Ad, Photo, Location, UniqueAd, UniquePhoto
from typing import List
import json


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


def transform_unique_ad(db_unique_ad: DBUniqueAd) -> UniqueAd:
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
        location=transform_location(db_unique_ad.location) if db_unique_ad.location else None,
        photos=transform_unique_photos(db_unique_ad.photos),
        attributes=db_unique_ad.attributes,
        is_vip=db_unique_ad.is_vip,
        is_realtor=db_unique_ad.is_realtor,
        realtor_score=db_unique_ad.realtor_score,
        photo_hashes=db_unique_ad.photo_hashes,
        text_embeddings=db_unique_ad.text_embeddings,
        confidence_score=db_unique_ad.confidence_score,
        duplicates_count=db_unique_ad.duplicates_count,
        created_at=db_unique_ad.created_at.isoformat() if db_unique_ad.created_at else None,
        updated_at=db_unique_ad.updated_at.isoformat() if db_unique_ad.updated_at else None
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

    return Ad(
        id=db_ad.id,
        source_id=db_ad.source_id,
        source_name=db_ad.source_name,
        source_url=db_ad.source_url,
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
        location=transform_location(db_ad.location) if db_ad.location else None,
        photos=transform_photos(db_ad.photos) if db_ad.photos else [],
        is_vip=db_ad.is_vip,
        published_at=db_ad.published_at,
        parsed_at=db_ad.parsed_at,
        attributes=attributes,
        is_realtor=db_ad.is_realtor,
        realtor_score=db_ad.realtor_score,
        is_duplicate=db_ad.is_duplicate,
        is_processed=db_ad.is_processed,
        processed_at=db_ad.processed_at,
        duplicate_info=transform_duplicate_info(db_ad.duplicate_info) if db_ad.duplicate_info else None
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
