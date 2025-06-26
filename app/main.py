from fastapi import FastAPI, HTTPException, status, Depends, Query, BackgroundTasks, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional, Union
from datetime import datetime
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_, func, desc
import logging
from contextlib import asynccontextmanager
import redis
import json
from cachetools import TTLCache
import asyncio

from app.models import Ad, AdCreateRequest, PaginatedUniqueAdsResponse, AdSource, DuplicateInfo, StatsResponse
from app.database import get_db, SessionLocal
from app import db_models
from app.utils.transform import transform_ad, transform_unique_ad
from config import API_HOST, API_PORT, REDIS_URL, ELASTICSEARCH_HOSTS, ELASTICSEARCH_INDEX
from app.utils.duplicate_processor import DuplicateProcessor
from app.services.photo_service import PhotoService
from app.services.duplicate_service import DuplicateService
from app.services.elasticsearch_service import ElasticsearchService
from app.services.scrapy_manager import ScrapyManager, SCRAPY_CONFIG_TO_SPIDER

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

memory_cache = TTLCache(maxsize=1000, ttl=300)  

try:
    redis_client = redis.from_url(REDIS_URL) if REDIS_URL else None
except:
    redis_client = None
    logger.warning("Redis not available, using memory cache only")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""

        
    # Автоматическое создание таблиц при первом запуске
    try:
        from app.database import engine
        from app import db_models
        logger.info("Creating database tables if they don't exist...")
        db_models.Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created/verified successfully!")
    except Exception as e:
        logger.error(f"❌ Error creating database tables: {e}")
        raise e
    
    logger.info("Starting Real Estate API...")
    yield
    logger.info("Shutting down Real Estate API...")

app = FastAPI(
    title="Real Estate Aggregator API",
    description="API for aggregated real estate listings with duplicate detection and clustering.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Сервисы
photo_service = PhotoService()
duplicate_service = DuplicateService()
es_service = ElasticsearchService(hosts=ELASTICSEARCH_HOSTS, index_name=ELASTICSEARCH_INDEX)

scrapy_manager = ScrapyManager(redis_url="redis://redis:6379/0")

# Роутеры
ads_router = APIRouter(prefix="/ads", tags=["ads"])
process_router = APIRouter(prefix="/process", tags=["process"])
elasticsearch_router = APIRouter(prefix="/elasticsearch", tags=["elasticsearch"])
scraping_router = APIRouter(prefix="/scraping", tags=["scraping"])

# Вспомогательные функции
async def get_from_cache(key: str) -> Optional[str]:
    """Получение данных из кэша"""
    if key in memory_cache:
        return memory_cache[key]
    
    if redis_client:
        try:
            return await redis_client.get(key)
        except:
            pass
    return None

async def set_cache(key: str, value: str, ttl: int = 300):
    """Сохранение данных в кэш"""
    memory_cache[key] = value
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

# Основные эндпоинты (корневые)

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

@app.get("/stats", response_model=StatsResponse)
async def get_statistics(db: Session = Depends(get_db)):
    """Получает общую статистику системы"""
    
    cache_key = "system_stats"
    cached = await get_from_cache(cache_key)
    if cached:
        return json.loads(cached)
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
    await set_cache(cache_key, result.json(), ttl=300)
    
    return result

# Роутер для работы с объявлениями
@ads_router.get("/unique", response_model=PaginatedUniqueAdsResponse)
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
    cache_key = f"unique_ads:{hash(str(locals()))}"
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
    
    if sort_by == "price":
        order_col = db_models.DBUniqueAd.price
    elif sort_by == "area_sqm":
        order_col = db_models.DBUniqueAd.area_sqm
    elif sort_by == "duplicates_count":
        order_col = db_models.DBUniqueAd.duplicates_count
    else:
        order_col = db_models.DBUniqueAd.id 
    
    if sort_order == "desc":
        query = query.order_by(desc(order_col))
    else:
        query = query.order_by(order_col)
    total = query.count()
    db_unique_ads = query.offset(offset).limit(limit).all()
    
    result = PaginatedUniqueAdsResponse(
        total=total,
        offset=offset,
        limit=limit,
        items=[transform_unique_ad(ad) for ad in db_unique_ads]
    )
    await set_cache(cache_key, result.json(), ttl=180)
    return result

@ads_router.get("/unique/{unique_ad_id}", response_model=DuplicateInfo)
async def get_unique_ad_details(
    unique_ad_id: int,
    db: Session = Depends(get_db)
):
    """Получает детали уникального объявления и все его дубликаты"""
    
    cache_key = f"unique_ad_details:{unique_ad_id}"
    cached = await get_from_cache(cache_key)
    if cached:
        return json.loads(cached)
    
    unique_ad = db.query(db_models.DBUniqueAd).options(
        selectinload(db_models.DBUniqueAd.location),
        selectinload(db_models.DBUniqueAd.photos)
    ).filter(db_models.DBUniqueAd.id == unique_ad_id).first()
    
    if not unique_ad:
        raise HTTPException(status_code=404, detail="Unique ad not found")
    
    processor = DuplicateProcessor(db)
    all_ads_info = processor.get_all_ads_for_unique(unique_ad_id)
    
    base_ad = None
    if all_ads_info['base_ad']:
        base_ad = transform_ad(all_ads_info['base_ad'][0])
    duplicates = [transform_ad(ad) for ad in all_ads_info['duplicates']]
    
    sources = []
    if base_ad:
        sources.append(AdSource(
            id=base_ad.id,
            source_name=base_ad.source_name,
            source_url=str(base_ad.source_url) if base_ad.source_url is not None else None,
            published_at=base_ad.published_at,
            is_base=True
        ))
    for ad in duplicates:
        sources.append(AdSource(
            id=ad.id,
            source_name=ad.source_name,
            source_url=str(ad.source_url) if ad.source_url is not None else None,
            published_at=ad.published_at,
            is_base=False
        ))
    
    result = DuplicateInfo(
        unique_ad_id=unique_ad_id,
        total_duplicates=unique_ad.duplicates_count,
        base_ad=base_ad,
        duplicates=duplicates,
        sources=sources
    )
    
    await set_cache(cache_key, result.json(), ttl=600)
    
    return result

@ads_router.get("/unique/{unique_ad_id}/sources", response_model=List[AdSource])
async def get_unique_ad_sources(
    unique_ad_id: int,
    db: Session = Depends(get_db)
):
    """Получает все источники для уникального объявления"""
    unique_ad = db.query(db_models.DBUniqueAd).filter(
        db_models.DBUniqueAd.id == unique_ad_id
    ).first()
    
    if not unique_ad:
        raise HTTPException(status_code=404, detail="Unique ad not found")
    processor = DuplicateProcessor(db)
    all_ads_info = processor.get_all_ads_for_unique(unique_ad_id)
    
    sources = []
    if all_ads_info['base_ad']:
        base = all_ads_info['base_ad'][0]
        sources.append(AdSource(
            id=base.id,
            source_url=base.source_url,
            source_name=base.source_name,
            published_at=base.published_at,
            is_base=True
        ))
    for dup in all_ads_info['duplicates']:
        sources.append(AdSource(
            id=dup.id,
            source_url=dup.source_url,
            source_name=dup.source_name,
            published_at=dup.published_at,
            is_base=False
        ))
    
    return sources

@ads_router.post("/", response_model=Ad, status_code=status.HTTP_201_CREATED)
async def create_ad(
    ad_data: AdCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Создает новое объявление"""
    existing_ad = db.query(db_models.DBAd).filter(
        db_models.DBAd.source_url == ad_data.source_url
    ).first()
    
    if existing_ad:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ad with this source_url already exists"
        )
    
    try:
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

        published_at = None
        if ad_data.published_at:
            try:
                published_at = datetime.fromisoformat(ad_data.published_at)
            except ValueError:
                logger.warning(f"Invalid published_at format: {ad_data.published_at}")

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
        
        if ad_data.photos:
            for photo in ad_data.photos:
                db_photo = db_models.DBPhoto(
                    url=str(photo.url),
                    ad_id=db_ad.id
                )
                db.add(db_photo)
        
        db.commit()
        db.refresh(db_ad)
        background_tasks.add_task(index_ad_in_elasticsearch, db_ad.id)
        
        logger.info(f"Ad created successfully: {db_ad.id}")
        return transform_ad(db_ad)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating ad: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Роутер для обработки
@process_router.post("/duplicates", status_code=status.HTTP_202_ACCEPTED)
async def process_duplicates(
    background_tasks: BackgroundTasks,
    batch_size: int = Query(100, ge=1, le=1000)
):
    """Запускает обработку дубликатов в фоне"""
    if duplicates_processing_status['status'] == 'running':
        return {"message": "Duplicate processing already running"}
    background_tasks.add_task(process_duplicates_async, batch_size)
    return {"message": "Duplicate processing started", "batch_size": batch_size}

@process_router.post("/realtors/detect", status_code=status.HTTP_202_ACCEPTED)
async def detect_realtors(background_tasks: BackgroundTasks):
    """Запускает обнаружение риэлторов в фоне"""
    if realtors_detection_status['status'] == 'running':
        return {"message": "Realtor detection already running"}
    background_tasks.add_task(detect_realtors_async)
    return {"message": "Realtor detection started"}

@process_router.post("/photos", status_code=status.HTTP_202_ACCEPTED)
async def process_photos(background_tasks: BackgroundTasks):
    """Запускает обработку всех необработанных фотографий в фоне"""
    if photo_processing_status['status'] == 'running':
        return {"message": "Photo processing already running"}
    background_tasks.add_task(process_photos_async)
    return {"message": "Photo processing started"}

@process_router.get("/duplicates/status")
async def get_duplicates_process_status():
    """Проверка статуса процесса обработки дубликатов"""
    return duplicates_processing_status

@process_router.get("/realtors/status")
async def get_realtors_detection_status():
    """Проверка статуса процесса обнаружения риэлторов"""
    return realtors_detection_status

@process_router.get("/photos/status")
async def get_photos_process_status():
    """Проверка статуса процесса обработки фото"""
    return photo_processing_status

# Роутер для Elasticsearch
@elasticsearch_router.get("/search", response_model=Dict)
async def search_ads(
    q: Optional[str] = Query(None, description="Поисковый запрос"),
    city: Optional[str] = Query(None, description="Город"),
    district: Optional[str] = Query(None, description="Район"),
    min_price: Optional[float] = Query(None, ge=0, description="Минимальная цена"),
    max_price: Optional[float] = Query(None, ge=0, description="Максимальная цена"),
    min_area: Optional[float] = Query(None, ge=0, description="Минимальная площадь"),
    max_area: Optional[float] = Query(None, ge=0, description="Максимальная площадь"),
    rooms: Optional[int] = Query(None, ge=0, description="Количество комнат"),
    is_realtor: Optional[bool] = Query(None, description="Фильтр по риэлторам"),
    is_vip: Optional[bool] = Query(None, description="Фильтр по VIP"),
    source_name: Optional[str] = Query(None, description="Источник объявления"),
    sort_by: Optional[str] = Query("relevance", description="Сортировка: relevance, price, area_sqm, created_at, published_at, duplicates_count"),
    sort_order: Optional[str] = Query("desc", description="Порядок сортировки: asc, desc"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    size: int = Query(20, ge=1, le=100, description="Размер страницы")
):
    """Полнотекстовый поиск объявлений через Elasticsearch"""
    
    filters = {
        'city': city,
        'district': district,
        'min_price': min_price,
        'max_price': max_price,
        'min_area': min_area,
        'max_area': max_area,
        'rooms': rooms,
        'is_realtor': is_realtor,
        'is_vip': is_vip,
        'source_name': source_name
    }
    filters = {k: v for k, v in filters.items() if v is not None}
    try:
        result = es_service.search_ads(q, filters, sort_by, sort_order, page, size)
        return result
    except Exception as e:
        logger.error(f"Error in search: {e}")
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@elasticsearch_router.get("/health")
async def elasticsearch_health():
    """Проверка здоровья Elasticsearch"""
    try:
        health = es_service.health_check()
        return health
    except Exception as e:
        logger.error(f"Error checking Elasticsearch health: {e}")
        raise HTTPException(status_code=500, detail=f"Health check error: {str(e)}")

@elasticsearch_router.get("/stats")
async def elasticsearch_stats():
    """Статистика Elasticsearch индекса"""
    try:
        stats = es_service.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting Elasticsearch stats: {e}")
        raise HTTPException(status_code=500, detail=f"Stats error: {str(e)}")

@elasticsearch_router.post("/reindex", status_code=status.HTTP_202_ACCEPTED)
async def reindex_elasticsearch(background_tasks: BackgroundTasks):
    """Переиндексация всех объявлений в Elasticsearch"""
    background_tasks.add_task(reindex_elasticsearch_async)
    return {"message": "Reindexing started in background"}

# Вспомогательные функции
async def index_ad_in_elasticsearch(ad_id: int):
    """Фоновая задача для индексации объявления в Elasticsearch"""
    try:
        db = SessionLocal()
        db_ad = db.query(db_models.DBAd).filter(db_models.DBAd.id == ad_id).first()
        
        if db_ad:
            ad_data = transform_ad(db_ad).dict()
            es_service.index_ad(ad_data)
            logger.info(f"Ad {ad_id} indexed in Elasticsearch")
        
        db.close()
    except Exception as e:
        logger.error(f"Error indexing ad {ad_id} in Elasticsearch: {e}")

async def process_ad_async(ad_id: int):
    """Асинхронная обработка объявления"""
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        
        try:
            db_ad = db.query(db_models.DBAd).filter(db_models.DBAd.id == ad_id).first()
            if not db_ad:
                return
            await photo_service.process_ad_photos(db, db_ad)
            processor = DuplicateProcessor(db)
            processor.process_ad(db_ad)
            
            db.commit()
            logger.info(f"Successfully processed ad {ad_id}")
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error processing ad {ad_id}: {e}")

photo_processing_status = {
    'status': 'idle', 
    'last_started': None,
    'last_completed': None,
    'last_error': None
}

duplicates_processing_status = {
    'status': 'idle',
    'last_started': None,
    'last_completed': None,
    'last_error': None,
    'batch_size': None
}

realtors_detection_status = {
    'status': 'idle',
    'last_started': None,
    'last_completed': None,
    'last_error': None
}

async def process_duplicates_async(batch_size: int):
    """Асинхронная обработка дубликатов"""
    try:
        duplicates_processing_status['status'] = 'running'
        duplicates_processing_status['last_started'] = datetime.utcnow().isoformat()
        duplicates_processing_status['batch_size'] = batch_size
        
        from app.database import SessionLocal
        db = SessionLocal()
        
        try:
            processor = DuplicateProcessor(db)
            processor.process_new_ads(batch_size)
            logger.info(f"Processed {batch_size} ads for duplicates")
            duplicates_processing_status['status'] = 'completed'
            duplicates_processing_status['last_completed'] = datetime.utcnow().isoformat()
        finally:
            db.close()
            
    except Exception as e:
        duplicates_processing_status['status'] = 'error'
        duplicates_processing_status['last_error'] = str(e)
        logger.error(f"Error processing duplicates: {e}")

async def detect_realtors_async():
    """Фоновая задача для определения риэлторов"""
    try:
        realtors_detection_status['status'] = 'running'
        realtors_detection_status['last_started'] = datetime.utcnow().isoformat()
        
        db = SessionLocal()
        duplicate_service = DuplicateService()
        await duplicate_service.detect_all_realtors(db)
        db.close()
        
        realtors_detection_status['status'] = 'completed'
        realtors_detection_status['last_completed'] = datetime.utcnow().isoformat()
        logger.info("Realtor detection completed")
    except Exception as e:
        realtors_detection_status['status'] = 'error'
        realtors_detection_status['last_error'] = str(e)
        logger.error(f"Error in realtor detection: {e}")

async def reindex_elasticsearch_async():
    """Фоновая задача для переиндексации Elasticsearch"""
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        
        try:
            unique_ads = db.query(db_models.DBUniqueAd).all()
            ads_data = []
            for unique_ad in unique_ads:
                ad_dict = transform_unique_ad(unique_ad).dict()
                ads_data.append(ad_dict)
            
            logger.info(f"Starting reindex of {len(ads_data)} ads")
            success = es_service.reindex_all(ads_data)
            
            if success:
                logger.info("✅ Elasticsearch reindexing completed successfully!")
            else:
                logger.error("❌ Some errors occurred during reindexing")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error during Elasticsearch reindexing: {e}")

async def process_photos_async():
    """Фоновая задача для обработки фотографий"""
    try:
        photo_processing_status['status'] = 'running'
        photo_processing_status['last_started'] = datetime.utcnow().isoformat()
        db = SessionLocal()
        try:
            await photo_service.process_all_unprocessed_photos(db)
            photo_processing_status['status'] = 'completed'
            photo_processing_status['last_completed'] = datetime.utcnow().isoformat()
        finally:
            db.close()
    except Exception as e:
        photo_processing_status['status'] = 'error'
        photo_processing_status['last_error'] = str(e)
        logger.error(f"Error processing photos: {e}")

# Роутер для скрапинга
@scraping_router.post("/start/{config_name}")
async def start_scraping(config_name: str, background_tasks: BackgroundTasks):
    if config_name not in SCRAPY_CONFIG_TO_SPIDER:
        raise HTTPException(status_code=400, detail="Неизвестный конфиг")
    job_id = await scrapy_manager.start_job(config_name)
    return {"message": "Задача запущена", "job_id": job_id}

@scraping_router.get("/status/{job_id}")
async def get_status(job_id: str):
    job = await scrapy_manager.get_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return job

@scraping_router.get("/jobs")
async def get_jobs():
    jobs = await scrapy_manager.get_all_jobs()
    return jobs

@scraping_router.post("/stop/{job_id}")
async def stop_job(job_id: str):
    job = await scrapy_manager.get_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    await scrapy_manager.stop_job(job_id)
    return {"message": "Задача остановлена"}

@scraping_router.post("/start-all")
async def start_all(background_tasks: BackgroundTasks):
    job_ids = await scrapy_manager.start_all()
    return {"message": "Все задачи запущены", "job_ids": job_ids}

@scraping_router.get("/log/{job_id}")
async def get_log(job_id: str, limit: int = 100):
    job = await scrapy_manager.get_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    log = await scrapy_manager.get_log(job_id, limit=limit)
    return {"log": log}

# Подключение роутеров
app.include_router(ads_router)
app.include_router(process_router)
app.include_router(elasticsearch_router)
app.include_router(scraping_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
        workers=1,
        log_level="info"
    )

