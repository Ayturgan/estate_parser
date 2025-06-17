from app.db_models import DBAd, DBPhoto, DBLocation
from app.models import Ad, Photo, Location
from typing import List


def transform_location(db_location: DBLocation) -> Location:
    return Location(
        address=db_location.address,
        district=db_location.district,
        city=db_location.city,
    )


def transform_photos(db_photos: List[DBPhoto]) -> List[Photo]:
    return [Photo(url=photo.url, hash=photo.hash) for photo in db_photos]


def transform_ad(db_ad: DBAd) -> Ad:
    return Ad(
        id=db_ad.id,
        source_id=db_ad.source_id,
        source_url=db_ad.source_url,
        source_name=db_ad.source_name,
        title=db_ad.title,
        description=db_ad.description,
        price=db_ad.price,
        price_original=db_ad.price_original,
        currency=db_ad.currency,
        area_sqm=db_ad.area_sqm,
        rooms=db_ad.rooms,
        floor=db_ad.floor,
        total_floors=db_ad.total_floors,
        series=db_ad.series,
        building_type=db_ad.building_type,
        building_year=db_ad.attributes.get('building_year') if db_ad.attributes else None,
        condition=db_ad.condition,
        repair=db_ad.repair,
        furniture=db_ad.furniture,
        heating=db_ad.heating,
        hot_water=db_ad.hot_water,
        gas=db_ad.gas,
        ceiling_height=db_ad.ceiling_height,
        phone_numbers=db_ad.phone_numbers,
        location=transform_location(db_ad.location) if db_ad.location else None,
        photos=transform_photos(db_ad.photos),
        attributes=db_ad.attributes,
        published_at=db_ad.published_at.isoformat() if db_ad.published_at else None,
        parsed_at=db_ad.parsed_at.isoformat() if db_ad.parsed_at else None,
        is_vip=db_ad.is_vip,
        is_realtor=db_ad.is_realtor,
        realtor_score=db_ad.realtor_score,
        is_duplicate=db_ad.is_duplicate,
        unique_ad_id=db_ad.unique_ad_id,
        duplicate_of_ids=[dup.id for dup in db_ad.duplicates_list] if not db_ad.is_duplicate else []
    )
