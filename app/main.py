from fastapi import FastAPI, HTTPException, status, Depends, Query
from typing import List, Dict, Optional
from datetime import datetime
import uuid
from sqlalchemy.orm import Session, joinedload, subqueryload
from sqlalchemy import and_, or_
from pydantic import BaseModel
import logging
import requests
import io
from PIL import Image
from imagehash import average_hash

from app.models import Ad, Location, Photo
from app.database import get_db
from app import db_models
from app.utils.transform import transform_ad
from config import API_HOST, API_PORT
from app.utils.duplicate_processor import DuplicateProcessor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Real Estate Parser API",
    description="API for parsing real estate listings and detecting duplicates.",
    version="0.1.0"
)

# Модели для ответов API
class PaginatedResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: List[Ad]

# Базовые эндпоинты
@app.get("/", response_model=Dict[str, str])
async def read_root():
    return {"message": "Welcome to the Real Estate Parser API!"}

@app.get("/status", response_model=Dict[str, str])
async def get_status():
    return {"status": "running", "version": app.version}

# Вспомогательные функции
def get_location_query(location: Optional[Location] = None):
    """Создает запрос для поиска локации"""
    if not location:
        return None
    
    return and_(
        db_models.DBLocation.city == location.city if location.city else True,
        db_models.DBLocation.district == location.district if location.district else True,
        db_models.DBLocation.address == location.address if location.address else True
    )

def build_ads_query(
    db: Session,
    filters: Dict = None,
    include_relations: bool = True
):
    """Создает базовый запрос для объявлений с фильтрами"""
    query = db.query(db_models.DBAd)
    
    if include_relations:
        query = query.options(
            joinedload(db_models.DBAd.location),
            joinedload(db_models.DBAd.photos),
            subqueryload(db_models.DBAd.duplicate_info)
        )
    
    if not filters:
        return query
        
    # Применяем фильтры
    if filters.get('is_realtor') is not None:
        query = query.filter(db_models.DBAd.is_realtor == filters['is_realtor'])
    
    if filters.get('city'):
        query = query.join(db_models.DBAd.location).filter(db_models.DBLocation.city == filters['city'])
    
    if filters.get('district'):
        query = query.join(db_models.DBAd.location).filter(db_models.DBLocation.district == filters['district'])
    
    if filters.get('min_price') is not None:
        query = query.filter(db_models.DBAd.price >= filters['min_price'])
    
    if filters.get('max_price') is not None:
        query = query.filter(db_models.DBAd.price <= filters['max_price'])
    
    if filters.get('min_area') is not None:
        query = query.filter(db_models.DBAd.area_sqm >= filters['min_area'])
    
    if filters.get('max_area') is not None:
        query = query.filter(db_models.DBAd.area_sqm <= filters['max_area'])
    
    if filters.get('rooms') is not None:
        query = query.filter(db_models.DBAd.rooms == filters['rooms'])
    
    if filters.get('source_name'):
        query = query.filter(db_models.DBAd.source_name == filters['source_name'])
    
    if filters.get('series'):
        query = query.filter(db_models.DBAd.series == filters['series'])
    
    if filters.get('repair'):
        query = query.filter(db_models.DBAd.repair == filters['repair'])
    
    if filters.get('heating'):
        query = query.filter(db_models.DBAd.heating == filters['heating'])
    
    if filters.get('furniture'):
        query = query.filter(db_models.DBAd.furniture == filters['furniture'])
    
    return query

# Основные эндпоинты
@app.post("/ads", response_model=Ad, status_code=status.HTTP_201_CREATED)
async def create_ad(ad: Ad, db: Session = Depends(get_db)):
    """Создает новое объявление"""
    try:
        if not ad.id:
            ad.id = str(uuid.uuid4())

        if db.query(db_models.DBAd).filter_by(id=ad.id).first():
            raise HTTPException(status_code=409, detail="Ad with this ID already exists")

        ad.parsed_at = datetime.now().isoformat()

        # Создаем или получаем локацию
        db_location = None
        if ad.location:
            location_query = get_location_query(ad.location)
            if location_query:
                db_location = db.query(db_models.DBLocation).filter(location_query).first()
            if not db_location:
                db_location = db_models.DBLocation(
                    city=ad.location.city,
                    district=ad.location.district,
                    address=ad.location.address
                )
                db.add(db_location)
                db.flush()

        # Создаем объявление
        db_ad = db_models.DBAd(
            id=ad.id,
            source_id=ad.source_id,
            source_url=str(ad.source_url),
            source_name=ad.source_name,
            title=ad.title,
            description=ad.description,
            price=ad.price,
            price_original=ad.price_original,
            currency=ad.currency,
            rooms=ad.rooms,
            area_sqm=ad.area_sqm,
            floor=ad.floor,
            total_floors=ad.total_floors,
            series=ad.series,
            building_type=ad.building_type,
            condition=ad.condition,
            repair=ad.repair,
            furniture=ad.furniture,
            heating=ad.heating,
            hot_water=ad.hot_water,
            gas=ad.gas,
            ceiling_height=ad.ceiling_height,
            phone_numbers=ad.phone_numbers,
            location_id=db_location.id if db_location else None,
            is_vip=ad.is_vip,
            is_realtor=ad.is_realtor,
            realtor_score=ad.realtor_score,
            attributes=ad.attributes,
            published_at=datetime.fromisoformat(ad.published_at) if ad.published_at else None,
            parsed_at=datetime.fromisoformat(ad.parsed_at),
            is_duplicate=False,
            is_processed=False
        )
        
        db.add(db_ad)
        db.flush()  # Чтобы получить id
        
        # Создаем фотографии и вычисляем их хэши
        if ad.photos:
            for photo in ad.photos:
                try:
                    # Скачиваем фото
                    response = requests.get(photo.url, timeout=10)
                    img = Image.open(io.BytesIO(response.content))
                    
                    # Вычисляем хэш
                    photo_hash = str(average_hash(img))
                    
                    # Создаем запись в базе
                    db_photo = db_models.DBPhoto(
                        url=str(photo.url),
                        hash=photo_hash,
                        ad_id=db_ad.id
                    )
                    db.add(db_photo)
                    logger.info(f"Computed hash for photo {photo.url}: {photo_hash}")
                except Exception as e:
                    logger.error(f"Error processing photo {photo.url}: {e}")
                    # Создаем запись без хэша
                    db_photo = db_models.DBPhoto(
                        url=str(photo.url),
                        ad_id=db_ad.id
                    )
                    db.add(db_photo)
        
        # Сохраняем изменения
        db.commit()
        db.refresh(db_ad)
        
        # Проверяем на дубликаты
        processor = DuplicateProcessor(db)
        processor.process_ad(db_ad)
        db.commit()
        
        return transform_ad(db_ad)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ads/{ad_id}", response_model=Ad)
async def get_ad(ad_id: str, db: Session = Depends(get_db)):
    db_ad = build_ads_query(db, include_relations=True).filter(db_models.DBAd.id == ad_id).first()
    
    if not db_ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    
    return transform_ad(db_ad)

@app.get("/ads/", response_model=PaginatedResponse)
async def get_all_ads(
    db: Session = Depends(get_db),
    is_realtor: Optional[bool] = None,
    city: Optional[str] = None,
    district: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_area: Optional[float] = None,
    max_area: Optional[float] = None,
    rooms: Optional[int] = None,
    source_name: Optional[str] = None,
    series: Optional[str] = None,
    repair: Optional[str] = None,
    heating: Optional[str] = None,
    furniture: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    filters = {
        'is_realtor': is_realtor,
        'city': city,
        'district': district,
        'min_price': min_price,
        'max_price': max_price,
        'min_area': min_area,
        'max_area': max_area,
        'rooms': rooms,
        'source_name': source_name,
        'series': series,
        'repair': repair,
        'heating': heating,
        'furniture': furniture
    }
    
    query = build_ads_query(db, filters)
    total = query.count()
    
    db_ads = query.offset(offset).limit(limit).all()
    
    return PaginatedResponse(
        total=total,
        offset=offset,
        limit=limit,
        items=[transform_ad(ad) for ad in db_ads]
    )

@app.get("/ads/{ad_id}/sources", response_model=List[Dict[str, str]])
async def get_ad_sources(ad_id: str, db: Session = Depends(get_db)):
    db_ad = build_ads_query(db, include_relations=True).filter(db_models.DBAd.id == ad_id).first()
    
    if not db_ad:
        raise HTTPException(status_code=404, detail="Ad not found")
    
    sources = []
    
    if not db_ad.is_duplicate:
        sources.append({
            "id": db_ad.id,
            "source_url": db_ad.source_url,
            "source_name": db_ad.source_name,
            "published_at": db_ad.published_at.isoformat() if db_ad.published_at else None
        })
        for dup in db_ad.duplicates_list:
            sources.append({
                "id": dup.id,
                "source_url": dup.source_url,
                "source_name": dup.source_name,
                "published_at": dup.published_at.isoformat() if dup.published_at else None
            })
    elif db_ad.unique_parent_ad:
        sources.append({
            "id": db_ad.unique_parent_ad.id,
            "source_url": db_ad.unique_parent_ad.source_url,
            "source_name": db_ad.unique_parent_ad.source_name,
            "published_at": db_ad.unique_parent_ad.published_at.isoformat() if db_ad.unique_parent_ad.published_at else None
        })
        for dup in db_ad.unique_parent_ad.duplicates_list:
            sources.append({
                "id": dup.id,
                "source_url": dup.source_url,
                "source_name": dup.source_name,
                "published_at": dup.published_at.isoformat() if dup.published_at else None
            })
    else:
        sources.append({
            "id": db_ad.id,
            "source_url": db_ad.source_url,
            "source_name": db_ad.source_name,
            "published_at": db_ad.published_at.isoformat() if db_ad.published_at else None
        })
    
    return sources

@app.delete("/ads/{ad_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ad(ad_id: int, db: Session = Depends(get_db)):
    """Удаляет объявление по ID"""
    try:
        # Проверяем существование объявления
        db_ad = db.query(db_models.DBAd).filter(db_models.DBAd.id == ad_id).first()
        if not db_ad:
            raise HTTPException(status_code=404, detail="Ad not found")
        
        # Если это дубликат, уменьшаем счетчик у уникального объявления
        if db_ad.is_duplicate and db_ad.duplicate_info:
            unique_ad = db.query(db_models.DBUniqueAd).filter(
                db_models.DBUniqueAd.id == db_ad.duplicate_info.unique_ad_id
            ).first()
            if unique_ad:
                unique_ad.duplicates_count = max(0, unique_ad.duplicates_count - 1)
        
        # Удаляем объявление (каскадное удаление удалит связанные записи)
        db.delete(db_ad)
        db.commit()
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/ads/{ad_id}", response_model=Ad)
async def update_ad(ad_id: int, ad: Ad, db: Session = Depends(get_db)):
    """Обновляет объявление по ID"""
    try:
        # Проверяем существование объявления
        db_ad = db.query(db_models.DBAd).filter(db_models.DBAd.id == ad_id).first()
        if not db_ad:
            raise HTTPException(status_code=404, detail="Ad not found")
        
        # Обновляем локацию
        if ad.location:
            location_query = get_location_query(ad.location)
            if location_query:
                db_location = db.query(db_models.DBLocation).filter(location_query).first()
            if not db_location:
                db_location = db_models.DBLocation(**ad.location.dict())
                db.add(db_location)
                db.flush()
            db_ad.location_id = db_location.id
        
        # Обновляем основные поля
        db_ad.source_id = ad.source_id
        db_ad.source_url = str(ad.source_url)
        db_ad.source_name = ad.source_name
        db_ad.title = ad.title
        db_ad.description = ad.description
        db_ad.price = ad.price
        db_ad.price_original = ad.price_original
        db_ad.currency = ad.currency
        db_ad.rooms = ad.rooms
        db_ad.area_sqm = ad.area_sqm
        db_ad.floor = ad.floor
        db_ad.total_floors = ad.total_floors
        db_ad.series = ad.series
        db_ad.building_type = ad.building_type
        db_ad.condition = ad.condition
        db_ad.repair = ad.repair
        db_ad.furniture = ad.furniture
        db_ad.heating = ad.heating
        db_ad.hot_water = ad.hot_water
        db_ad.gas = ad.gas
        db_ad.ceiling_height = ad.ceiling_height
        db_ad.phone_numbers = ad.phone_numbers
        db_ad.is_vip = ad.is_vip
        db_ad.published_at = datetime.fromisoformat(ad.published_at) if ad.published_at else None
        db_ad.parsed_at = datetime.fromisoformat(ad.parsed_at)
        db_ad.attributes = ad.attributes
        db_ad.is_realtor = ad.is_realtor
        db_ad.realtor_score = ad.realtor_score
        
        # Обновляем фотографии
        if ad.photos:
            # Удаляем старые фотографии
            db.query(db_models.DBPhoto).filter(db_models.DBPhoto.ad_id == ad_id).delete()
            # Добавляем новые
            for photo in ad.photos:
                db_photo = db_models.DBPhoto(url=str(photo.url), hash=photo.hash, ad_id=ad_id)
                db.add(db_photo)
        
        # Если объявление было дубликатом, но теперь не является
        if db_ad.is_duplicate and not ad.is_duplicate:
            # Удаляем информацию о дубликате
            if db_ad.duplicate_info:
                db.delete(db_ad.duplicate_info)
            # Уменьшаем счетчик у уникального объявления
            if db_ad.duplicate_info and db_ad.duplicate_info.unique_ad:
                unique_ad = db_ad.duplicate_info.unique_ad
                unique_ad.duplicates_count = max(0, unique_ad.duplicates_count - 1)
        
        # Если объявление не было дубликатом, но теперь является
        elif not db_ad.is_duplicate and ad.is_duplicate and ad.duplicate_info:
            # Создаем новую запись о дубликате
            db_duplicate = db_models.DBAdDuplicate(
                unique_ad_id=ad.duplicate_info.unique_ad_id,
                original_ad_id=ad_id,
                photo_similarity=ad.duplicate_info.photo_similarity,
                text_similarity=ad.duplicate_info.text_similarity,
                contact_similarity=ad.duplicate_info.contact_similarity,
                address_similarity=ad.duplicate_info.address_similarity,
                overall_similarity=ad.duplicate_info.overall_similarity
            )
            db.add(db_duplicate)
            # Увеличиваем счетчик у уникального объявления
            unique_ad = db.query(db_models.DBUniqueAd).filter(
                db_models.DBUniqueAd.id == ad.duplicate_info.unique_ad_id
            ).first()
            if unique_ad:
                unique_ad.duplicates_count += 1
        
        db.commit()
        db.refresh(db_ad)
        return transform_ad(db_ad)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
