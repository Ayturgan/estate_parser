from fastapi import FastAPI, HTTPException, status, Depends, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional, Union
from datetime import datetime
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_, func, desc
from pydantic import BaseModel, Field, validator
import logging
import asyncio
import aiohttp
from contextlib import asynccontextmanager
import redis
import json
from cachetools import TTLCache

from app.models import Ad, Location, Photo, UniqueAd
from app.database import get_db
from app import db_models
from app.utils.transform import transform_ad, transform_unique_ad
from config import API_HOST, API_PORT, REDIS_URL
from app.utils.duplicate_processor import DuplicateProcessor
from app.services.photo_service import PhotoService
from app.services.duplicate_service import DuplicateService

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Кэш в памяти для быстрого доступа
memory_cache = TTLCache(maxsize=1000, ttl=300)  # 5 минут

# Redis для распределенного кэша
try:
    redis_client = redis.from_url(REDIS_URL) if REDIS_URL else None
except:
    redis_client = None
    logger.warning("Redis not available, using memory cache only")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    logger.info("Starting Real Estate API...")
    yield
    # Shutdown
    logger.info("Shutting down Real Estate API...")

app = FastAPI(
    title="Real Estate Aggregator API",
    description="API for aggregated real estate listings with duplicate detection and clustering.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Модели для ответов API
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

# Валидация и модели запросов
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
    floor: Optional[int] = None
    total_floors: Optional[int] = None
    series: Optional[str] = None
    building_type: Optional[str] = None
    condition: Optional[str] = None
    repair: Optional[str] = None
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

    @validator('source_url')
    def validate_source_url(cls, v):
        if not v or not v.startswith(('http://', 'https://')):
            raise ValueError('source_url must be a valid HTTP/HTTPS URL')
        return v

    @validator('phone_numbers')
    def validate_phone_numbers(cls, v):
        if v:
            for phone in v:
                if not phone or len(phone.strip()) < 7:
                    raise ValueError('Invalid phone number format')
        return v

# Сервисы
photo_service = PhotoService()
duplicate_service = DuplicateService()

# Вспомогательные функции
async def get_from_cache(key: str) -> Optional[str]:
    """Получение данных из кэша"""
    # Сначала проверяем память
    if key in memory_cache:
        return memory_cache[key]
    
    # Затем Redis
    if redis_client:
        try:
            return await redis_client.get(key)
        except:
            pass
    return None

async def set_cache(key: str, value: str, ttl: int = 300):
    """Сохранение данных в кэш"""
    # Сохраняем в память
    memory_cache[key] = value
    
    # Сохраняем в Redis
    if redis_client:
        try:
            await redis_client.setex(key, ttl, value)
        except:
            pass

def build_unique_ads_query(
    db: Session,
    filters: Dict = None,
    include_relations: bool = True
):
    """Создает оптимизированный запрос для уникальных объявлений"""
    query = db.query(db_models.DBUniqueAd)
    
    if include_relations:
        query = query.options(
            selectinload(db_models.DBUniqueAd.location),
            selectinload(db_models.DBUniqueAd.photos)
        )
    
    if not filters:
        return query
        
    # Применяем фильтры
    if filters.get('is_realtor') is not None:
        query = query.filter(db_models.DBUniqueAd.is_realtor == filters['is_realtor'])
    
    if filters.get('city'):
        query = query.join(db_models.DBUniqueAd.location).filter(
            db_models.DBLocation.city == filters['city']
        )
    
    if filters.get('district'):
        query = query.join(db_models.DBUniqueAd.location).filter(
            db_models.DBLocation.district == filters['district']
        )
    
    if filters.get('min_price') is not None:
        query = query.filter(db_models.DBUniqueAd.price >= filters['min_price'])
    
    if filters.get('max_price') is not None:
        query = query.filter(db_models.DBUniqueAd.price <= filters['max_price'])
    
    if filters.get('min_area') is not None:
        query = query.filter(db_models.DBUniqueAd.area_sqm >= filters['min_area'])
    
    if filters.get('max_area') is not None:
        query = query.filter(db_models.DBUniqueAd.area_sqm <= filters['max_area'])
    
    if filters.get('rooms') is not None:
        query = query.filter(db_models.DBUniqueAd.rooms == filters['rooms'])
    
    if filters.get('has_duplicates'):
        if filters['has_duplicates']:
            query = query.filter(db_models.DBUniqueAd.duplicates_count > 0)
        else:
            query = query.filter(db_models.DBUniqueAd.duplicates_count == 0)
    
    return query

# Основные эндпоинты согласно ТЗ

@app.get("/", response_model=Dict[str, str])
async def read_root():
    """Корневой эндпоинт"""
    return {
        "message": "Real Estate Aggregator API",
        "version": app.version,
        "docs": "/docs"
    }

@app.get("/status", response_model=Dict[str, Union[str, int]])
async def get_status(db: Session = Depends(get_db)):
    """Статус системы"""
    try:
        # Быстрая проверка БД
        total_unique = db.query(func.count(db_models.DBUniqueAd.id)).scalar()
        total_ads = db.query(func.count(db_models.DBAd.id)).scalar()
        
        return {
            "status": "healthy",
            "version": app.version,
            "total_unique_ads": total_unique,
            "total_ads": total_ads,
            "cache_status": "redis" if redis_client else "memory_only"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

# ТЗ №5: GET /ads/unique — список всех уникальных объявлений
@app.get("/ads/unique", response_model=PaginatedUniqueAdsResponse)
async def get_unique_ads(
    db: Session = Depends(get_db),
    is_realtor: Optional[bool] = Query(None, description="Фильтр по риэлторам"),
    city: Optional[str] = Query(None, description="Город"),
    district: Optional[str] = Query(None, description="Район"),
    min_price: Optional[float] = Query(None, ge=0, description="Минимальная цена"),
    max_price: Optional[float] = Query(None, ge=0, description="Максимальная цена"),
    min_area: Optional[float] = Query(None, ge=0, description="Минимальная площадь"),
    max_area: Optional[float] = Query(None, ge=0, description="Максимальная площадь"),
    rooms: Optional[int] = Query(None, ge=0, le=10, description="Количество комнат"),
    has_duplicates: Optional[bool] = Query(None, description="Есть ли дубликаты"),
    sort_by: Optional[str] = Query("created_at", description="Сортировка: price, area_sqm, created_at, duplicates_count"),
    sort_order: Optional[str] = Query("desc", description="Порядок: asc, desc"),
    limit: int = Query(50, ge=1, le=500, description="Количество записей"),
    offset: int = Query(0, ge=0, description="Смещение")
):
    """Получает список уникальных объявлений с фильтрацией"""
    
    # Создаем ключ кэша
    cache_key = f"unique_ads:{hash(str(locals()))}"
    
    # Проверяем кэш
    cached = await get_from_cache(cache_key)
    if cached:
        return json.loads(cached)
    
    filters = {
        'is_realtor': is_realtor,
        'city': city,
        'district': district,
        'min_price': min_price,
        'max_price': max_price,
        'min_area': min_area,
        'max_area': max_area,
        'rooms': rooms,
        'has_duplicates': has_duplicates
    }
    
    query = build_unique_ads_query(db, filters)
    
    # Сортировка
    if sort_by == "price":
        order_col = db_models.DBUniqueAd.price
    elif sort_by == "area_sqm":
        order_col = db_models.DBUniqueAd.area_sqm
    elif sort_by == "duplicates_count":
        order_col = db_models.DBUniqueAd.duplicates_count
    else:
        order_col = db_models.DBUniqueAd.id  # created_at по умолчанию
    
    if sort_order == "desc":
        query = query.order_by(desc(order_col))
    else:
        query = query.order_by(order_col)
    
    # Оптимизированный подсчет
    total = query.count()
    
    # Получаем данные
    db_unique_ads = query.offset(offset).limit(limit).all()
    
    result = PaginatedUniqueAdsResponse(
        total=total,
        offset=offset,
        limit=limit,
        items=[transform_unique_ad(ad) for ad in db_unique_ads]
    )
    
    # Кэшируем результат
    await set_cache(cache_key, result.json(), ttl=180)  # 3 минуты
    
    return result

# ТЗ №5: GET /ads/{id} — подробности по уникальному объявлению и его дублям
@app.get("/ads/unique/{unique_ad_id}", response_model=DuplicateInfo)
async def get_unique_ad_details(
    unique_ad_id: int,
    db: Session = Depends(get_db)
):
    """Получает детали уникального объявления и все его дубликаты"""
    
    # Проверяем кэш
    cache_key = f"unique_ad_details:{unique_ad_id}"
    cached = await get_from_cache(cache_key)
    if cached:
        return json.loads(cached)
    
    # Получаем уникальное объявление
    unique_ad = db.query(db_models.DBUniqueAd).options(
        selectinload(db_models.DBUniqueAd.location),
        selectinload(db_models.DBUniqueAd.photos)
    ).filter(db_models.DBUniqueAd.id == unique_ad_id).first()
    
    if not unique_ad:
        raise HTTPException(status_code=404, detail="Unique ad not found")
    
    # Получаем все связанные объявления через DuplicateProcessor
    processor = DuplicateProcessor(db)
    all_ads_info = processor.get_all_ads_for_unique(unique_ad_id)
    
    # Получаем базовое объявление
    base_ad = None
    if all_ads_info['base_ad']:
        base_ad = transform_ad(all_ads_info['base_ad'][0])
    
    # Получаем дубликаты
    duplicates = [transform_ad(ad) for ad in all_ads_info['duplicates']]
    
    # Формируем источники
    sources = []
    if base_ad:
        sources.append(AdSource(
            id=base_ad.id,
            source_url=base_ad.source_url,
            source_name=base_ad.source_name,
            published_at=base_ad.published_at,
            is_base=True
        ))
    
    for dup in duplicates:
        sources.append(AdSource(
            id=dup.id,
            source_url=dup.source_url,
            source_name=dup.source_name,
            published_at=dup.published_at,
            is_base=False
        ))
    
    result = DuplicateInfo(
        unique_ad_id=unique_ad_id,
        total_duplicates=unique_ad.duplicates_count,
        base_ad=base_ad,
        duplicates=duplicates,
        sources=sources
    )
    
    # Кэшируем результат
    await set_cache(cache_key, result.json(), ttl=600)  # 10 минут
    
    return result

# ТЗ №5: GET /ads/{id}/sources — список источников
@app.get("/ads/unique/{unique_ad_id}/sources", response_model=List[AdSource])
async def get_unique_ad_sources(
    unique_ad_id: int,
    db: Session = Depends(get_db)
):
    """Получает все источники для уникального объявления"""
    
    # Проверяем существование
    unique_ad = db.query(db_models.DBUniqueAd).filter(
        db_models.DBUniqueAd.id == unique_ad_id
    ).first()
    
    if not unique_ad:
        raise HTTPException(status_code=404, detail="Unique ad not found")
    
    # Получаем все связанные объявления
    processor = DuplicateProcessor(db)
    all_ads_info = processor.get_all_ads_for_unique(unique_ad_id)
    
    sources = []
    
    # Базовое объявление
    if all_ads_info['base_ad']:
        base = all_ads_info['base_ad'][0]
        sources.append(AdSource(
            id=base.id,
            source_url=base.source_url,
            source_name=base.source_name,
            published_at=base.published_at,
            is_base=True
        ))
    
    # Дубликаты
    for dup in all_ads_info['duplicates']:
        sources.append(AdSource(
            id=dup.id,
            source_url=dup.source_url,
            source_name=dup.source_name,
            published_at=dup.published_at,
            is_base=False
        ))
    
    return sources

# Создание нового объявления (для парсеров)
@app.post("/ads", response_model=Ad, status_code=status.HTTP_201_CREATED)
async def create_ad(
    ad_data: AdCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Создает новое объявление и запускает обработку дубликатов в фоне"""
    try:
        # Создаем или получаем локацию
        db_location = None
        if ad_data.location:
            db_location = db.query(db_models.DBLocation).filter(
                and_(
                    db_models.DBLocation.city == ad_data.location.city,
                    db_models.DBLocation.district == ad_data.location.district,
                    db_models.DBLocation.address == ad_data.location.address
                )
            ).first()
            
            if not db_location:
                db_location = db_models.DBLocation(
                    city=ad_data.location.city,
                    district=ad_data.location.district,
                    address=ad_data.location.address
                )
                db.add(db_location)
                db.flush()

        # Парсим дату публикации
        published_at = None
        if ad_data.published_at:
            try:
                published_at = datetime.fromisoformat(ad_data.published_at)
            except ValueError:
                logger.warning(f"Invalid published_at format: {ad_data.published_at}")

        # Создаем объявление
        db_ad = db_models.DBAd(
            source_id=ad_data.source_id,
            source_url=ad_data.source_url,
            source_name=ad_data.source_name,
            title=ad_data.title,
            description=ad_data.description,
            price=ad_data.price,
            price_original=ad_data.price_original,
            currency=ad_data.currency,
            rooms=ad_data.rooms,
            area_sqm=ad_data.area_sqm,
            floor=ad_data.floor,
            total_floors=ad_data.total_floors,
            series=ad_data.series,
            building_type=ad_data.building_type,
            condition=ad_data.condition,
            repair=ad_data.repair,
            furniture=ad_data.furniture,
            heating=ad_data.heating,
            hot_water=ad_data.hot_water,
            gas=ad_data.gas,
            ceiling_height=ad_data.ceiling_height,
            phone_numbers=ad_data.phone_numbers,
            location_id=db_location.id if db_location else None,
            attributes=ad_data.attributes,
            published_at=published_at,
            parsed_at=datetime.utcnow(),
            is_duplicate=False,
            is_processed=False
        )
        
        db.add(db_ad)
        db.flush()
        
        # Создаем записи фотографий (без обработки)
        if ad_data.photos:
            for photo in ad_data.photos:
                db_photo = db_models.DBPhoto(
                    url=str(photo.url),
                    ad_id=db_ad.id
                )
                db.add(db_photo)
        
        db.commit()
        db.refresh(db_ad)
        
        # Запускаем обработку фото и дубликатов в фоне
        background_tasks.add_task(
            process_ad_async,
            db_ad.id
        )
        
        return transform_ad(db_ad)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating ad: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_ad_async(ad_id: int):
    """Асинхронная обработка объявления"""
    try:
        # Создаем новую сессию для фоновой задачи
        from app.database import SessionLocal
        db = SessionLocal()
        
        try:
            # Получаем объявление
            db_ad = db.query(db_models.DBAd).filter(db_models.DBAd.id == ad_id).first()
            if not db_ad:
                return
            
            # Обрабатываем фотографии асинхронно
            await photo_service.process_ad_photos(db, db_ad)
            
            # Обрабатываем дубликаты
            processor = DuplicateProcessor(db)
            processor.process_ad(db_ad)
            
            db.commit()
            logger.info(f"Successfully processed ad {ad_id}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error processing ad {ad_id}: {e}")

# Статистика
@app.get("/stats", response_model=StatsResponse)
async def get_statistics(db: Session = Depends(get_db)):
    """Получает общую статистику системы"""
    
    cache_key = "system_stats"
    cached = await get_from_cache(cache_key)
    if cached:
        return json.loads(cached)
    
    # Получаем статистику через DuplicateProcessor
    processor = DuplicateProcessor(db)
    duplicate_stats = processor.get_duplicate_statistics()
    realtor_stats = processor.get_realtor_statistics()
    
    result = StatsResponse(
        total_unique_ads=duplicate_stats['total_unique_ads'],
        total_original_ads=duplicate_stats['total_original_ads'],
        total_duplicates=duplicate_stats['duplicate_ads'],
        realtor_ads=realtor_stats['realtor_unique_ads'],
        deduplication_ratio=duplicate_stats['deduplication_ratio']
    )
    
    # Кэшируем на 5 минут
    await set_cache(cache_key, result.json(), ttl=300)
    
    return result

# Управление дубликатами
@app.post("/duplicates/process", status_code=status.HTTP_202_ACCEPTED)
async def process_duplicates(
    background_tasks: BackgroundTasks,
    batch_size: int = Query(100, ge=1, le=1000)
):
    """Запускает обработку дубликатов в фоне"""
    background_tasks.add_task(process_duplicates_async, batch_size)
    return {"message": "Duplicate processing started", "batch_size": batch_size}

async def process_duplicates_async(batch_size: int):
    """Асинхронная обработка дубликатов"""
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        
        try:
            processor = DuplicateProcessor(db)
            processor.process_new_ads(batch_size)
            logger.info(f"Processed {batch_size} ads for duplicates")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error processing duplicates: {e}")

@app.post("/realtors/detect", status_code=status.HTTP_202_ACCEPTED)
async def detect_realtors(background_tasks: BackgroundTasks):
    """Запускает обнаружение риэлторов в фоне"""
    background_tasks.add_task(detect_realtors_async)
    return {"message": "Realtor detection started"}

async def detect_realtors_async():
    """Асинхронное обнаружение риэлторов"""
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        
        try:
            processor = DuplicateProcessor(db)
            processor.detect_realtors()
            logger.info("Realtor detection completed")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error detecting realtors: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
        workers=1,  # В продакшене увеличить
        log_level="info"
    )

