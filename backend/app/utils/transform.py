from app.database.db_models import DBAd, DBPhoto, DBLocation, DBUniqueAd, DBAdDuplicate, DBUniquePhoto, DBRealtor
from app.database.models import Ad, Photo, Location, UniqueAd, UniquePhoto
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
        if hasattr(v, 'url') and hasattr(v, '__str__'):
            return str(v)
        if isinstance(v, (pydantic.BaseModel,)):
            return clean_value(v.dict())
        if hasattr(v, 'isoformat'):
            return v.isoformat()
        if isinstance(v, (int, float, bool, str)):
            return v
        return str(v)
    if hasattr(ad, 'dict'):
        ad = ad.dict()
    return {k: clean_value(v) for k, v in ad.items()}


def transform_unique_ad(db_unique_ad: DBUniqueAd) -> UniqueAd:
    photos = []
    for photo in db_unique_ad.photos:
        photos.append({
            'url': str(photo.url),
            'hash': photo.hash
        })
    created_at = db_unique_ad.created_at.isoformat() if db_unique_ad.created_at else None
    updated_at = db_unique_ad.updated_at.isoformat() if db_unique_ad.updated_at else None
    location_data = None
    if db_unique_ad.location:
        location_data = {
            'address': db_unique_ad.location.address,
            'district': db_unique_ad.location.district,
            'city': db_unique_ad.location.city
        }
    
    # Преобразование данных риэлтора
    realtor_data = None
    if db_unique_ad.realtor:
        realtor_data = {
            'id': db_unique_ad.realtor.id,
            'phone_number': db_unique_ad.realtor.phone_number,
            'name': db_unique_ad.realtor.name,
            'company_name': db_unique_ad.realtor.company_name,
            'total_ads_count': db_unique_ad.realtor.total_ads_count,
            'active_ads_count': db_unique_ad.realtor.active_ads_count,
            'confidence_score': db_unique_ad.realtor.confidence_score,
            'average_price': db_unique_ad.realtor.average_price,
            'favorite_districts': db_unique_ad.realtor.favorite_districts,
            'property_types': db_unique_ad.realtor.property_types,
            'first_seen': db_unique_ad.realtor.first_seen.isoformat() if db_unique_ad.realtor.first_seen else None,
            'last_activity': db_unique_ad.realtor.last_activity.isoformat() if db_unique_ad.realtor.last_activity else None,
            'created_at': db_unique_ad.realtor.created_at.isoformat() if db_unique_ad.realtor.created_at else None,
            'updated_at': db_unique_ad.realtor.updated_at.isoformat() if db_unique_ad.realtor.updated_at else None
        }
    
    return UniqueAd(
        id=db_unique_ad.id,
        title=db_unique_ad.title,
        description=db_unique_ad.description,
        price=db_unique_ad.price,
        price_original=db_unique_ad.price_original,
        currency=db_unique_ad.currency,
        area_sqm=db_unique_ad.area_sqm,
        land_area_sotka=db_unique_ad.land_area_sotka,
        rooms=db_unique_ad.rooms,
        floor=db_unique_ad.floor,
        total_floors=db_unique_ad.total_floors,
        series=db_unique_ad.series,
        building_type=db_unique_ad.building_type,
        condition=db_unique_ad.condition,
        furniture=db_unique_ad.furniture,
        heating=db_unique_ad.heating,
        hot_water=db_unique_ad.hot_water,
        gas=db_unique_ad.gas,
        ceiling_height=db_unique_ad.ceiling_height,
        phone_numbers=db_unique_ad.phone_numbers,
        location=location_data,
        photos=photos,
        attributes=db_unique_ad.attributes,

        realtor=realtor_data,
        realtor_id=db_unique_ad.realtor_id,
        property_type=db_unique_ad.property_type,
        property_origin=db_unique_ad.property_origin,
        listing_type=db_unique_ad.listing_type,
        photo_hashes=db_unique_ad.photo_hashes or [],
        confidence_score=db_unique_ad.confidence_score,
        duplicates_count=db_unique_ad.duplicates_count,
        created_at=created_at,
        updated_at=updated_at
    )


def transform_ad(db_ad: DBAd) -> Ad:
    """Преобразует DBAd в Ad"""
    attributes = {}
    if db_ad.attributes:
        try:
            if isinstance(db_ad.attributes, str):
                attributes = json.loads(db_ad.attributes)
            elif isinstance(db_ad.attributes, dict):
                attributes = db_ad.attributes
        except json.JSONDecodeError:
            pass
    photos = []
    for photo in db_ad.photos:
        photos.append({
            'url': str(photo.url),
            'hash': photo.hash
        })
    published_at = db_ad.published_at.isoformat() if db_ad.published_at else None
    parsed_at = db_ad.parsed_at.isoformat() if db_ad.parsed_at else None
    processed_at = db_ad.processed_at.isoformat() if db_ad.processed_at else None
    location_data = None
    if db_ad.location:
        location_data = {
            'address': db_ad.location.address,
            'district': db_ad.location.district,
            'city': db_ad.location.city
        }
    duplicate_info_data = None
    if db_ad.duplicate_info:
        duplicate_info_data = {
            'id': db_ad.duplicate_info.id,
            'unique_ad_id': db_ad.duplicate_info.unique_ad_id,
            'photo_similarity': db_ad.duplicate_info.photo_similarity,
            'text_similarity': db_ad.duplicate_info.text_similarity,
            'contact_similarity': db_ad.duplicate_info.contact_similarity,
            'address_similarity': db_ad.duplicate_info.address_similarity,
            'characteristics_similarity': db_ad.duplicate_info.characteristics_similarity,  # НОВОЕ ПОЛЕ
            'overall_similarity': db_ad.duplicate_info.overall_similarity,
            'created_at': db_ad.duplicate_info.created_at.isoformat() if db_ad.duplicate_info.created_at else None
        }

    # Преобразование данных риэлтора
    realtor_data = None
    if db_ad.realtor:
        realtor_data = {
            'id': db_ad.realtor.id,
            'phone_number': db_ad.realtor.phone_number,
            'name': db_ad.realtor.name,
            'company_name': db_ad.realtor.company_name,
            'total_ads_count': db_ad.realtor.total_ads_count,
            'active_ads_count': db_ad.realtor.active_ads_count,
            'confidence_score': db_ad.realtor.confidence_score,
            'average_price': db_ad.realtor.average_price,
            'favorite_districts': db_ad.realtor.favorite_districts,
            'property_types': db_ad.realtor.property_types,
            'first_seen': db_ad.realtor.first_seen.isoformat() if db_ad.realtor.first_seen else None,
            'last_activity': db_ad.realtor.last_activity.isoformat() if db_ad.realtor.last_activity else None,
            'created_at': db_ad.realtor.created_at.isoformat() if db_ad.realtor.created_at else None,
            'updated_at': db_ad.realtor.updated_at.isoformat() if db_ad.realtor.updated_at else None
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
        land_area_sotka=db_ad.land_area_sotka,
        floor=db_ad.floor,
        total_floors=db_ad.total_floors,
        series=db_ad.series,
        building_type=db_ad.building_type,
        condition=db_ad.condition,
        furniture=db_ad.furniture,
        heating=db_ad.heating,
        hot_water=db_ad.hot_water,
        gas=db_ad.gas,
        ceiling_height=db_ad.ceiling_height,
        phone_numbers=db_ad.phone_numbers,
        location=location_data,
        photos=photos,
        published_at=published_at,
        parsed_at=parsed_at,
        attributes=attributes,

        realtor=realtor_data,
        realtor_id=db_ad.realtor_id,
        property_type=db_ad.property_type,
        property_origin=db_ad.property_origin,
        listing_type=db_ad.listing_type,
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
        'characteristics_similarity': db_duplicate.characteristics_similarity,  # НОВОЕ ПОЛЕ
        'overall_similarity': db_duplicate.overall_similarity,
        'created_at': db_duplicate.created_at.isoformat() if db_duplicate.created_at else None
    }


def transform_realtor(db_realtor: DBRealtor) -> dict:
    """Преобразует DBRealtor в словарь для API"""
    return {
        'id': db_realtor.id,
        'phone_number': db_realtor.phone_number,
        'name': db_realtor.name,
        'company_name': db_realtor.company_name,
        'total_ads_count': db_realtor.total_ads_count,
        'active_ads_count': db_realtor.active_ads_count,
        'confidence_score': db_realtor.confidence_score,
        'average_price': db_realtor.average_price,
        'favorite_districts': db_realtor.favorite_districts,
        'property_types': db_realtor.property_types,
        'first_seen': db_realtor.first_seen.isoformat() if db_realtor.first_seen else None,
        'last_activity': db_realtor.last_activity.isoformat() if db_realtor.last_activity else None,
        'created_at': db_realtor.created_at.isoformat() if db_realtor.created_at else None,
        'updated_at': db_realtor.updated_at.isoformat() if db_realtor.updated_at else None
    }
