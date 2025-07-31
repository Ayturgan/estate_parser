from fastapi import FastAPI, HTTPException, status, Depends, Query, BackgroundTasks, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import List, Dict, Optional, Union, Any
from datetime import datetime
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_, func, desc
import logging
from contextlib import asynccontextmanager
import redis
import json
from cachetools import TTLCache
import asyncio
import os


from app.database.models import Ad, AdCreateRequest, PaginatedUniqueAdsResponse, AdSource, DuplicateInfo, StatsResponse
from app.database import get_db, SessionLocal
from app.database import db_models
from app.utils.transform import transform_ad, transform_unique_ad, transform_realtor
from app.core.config import API_HOST, API_PORT, REDIS_URL, ELASTICSEARCH_HOSTS, ELASTICSEARCH_INDEX
from app.utils.duplicate_processor import DuplicateProcessor
from app.services.photo_service import PhotoService
from app.services.duplicate_service import DuplicateService
from app.services.elasticsearch_service import ElasticsearchService
from app.services.scrapy_manager import ScrapyManager, SCRAPY_CONFIG_TO_SPIDER
from app.services.automation_service import automation_service
from app.web_routes import web_router
from app.websocket import websocket_router
from app.services.event_emitter import event_emitter


# Импортируем API роутеры
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

def create_default_admin():
    """Создает админа по умолчанию при первом запуске"""
    try:
        from app.services.auth_service import AuthService
        from app.database.models import AdminCreate
        from app.core.config import DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD, DEFAULT_ADMIN_FULL_NAME, CREATE_DEFAULT_ADMIN
        
        # Проверяем, нужно ли создавать админа по умолчанию
        if not CREATE_DEFAULT_ADMIN:
            logger.info("Default admin creation disabled via environment variable")
            return
        
        # Создаем сессию БД
        db = SessionLocal()
        auth_service = AuthService()
        
        # Проверяем, существует ли админ с указанным username
        existing_admin = db.query(db_models.DBAdmin).filter(
            db_models.DBAdmin.username == DEFAULT_ADMIN_USERNAME
        ).first()
        
        if existing_admin:
            logger.info(f"Default admin '{DEFAULT_ADMIN_USERNAME}' already exists, skipping creation")
            return
        
        # Создаем админа по умолчанию
        admin_data = AdminCreate(
            username=DEFAULT_ADMIN_USERNAME,
            password=DEFAULT_ADMIN_PASSWORD,
            full_name=DEFAULT_ADMIN_FULL_NAME
        )
        
        auth_service.create_admin(db, admin_data)
        logger.info(f"✅ Default admin created: username={DEFAULT_ADMIN_USERNAME}, password={DEFAULT_ADMIN_PASSWORD}")
        
    except Exception as e:
        logger.error(f"❌ Error creating default admin: {e}")
        raise e
    finally:
        if 'db' in locals():
            db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    
    # Автоматическое создание таблиц при первом запуске
    try:
        from app.database import engine
        from app.database import db_models
        logger.info("Creating database tables if they don't exist...")
        db_models.Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created/verified successfully!")
        
        # Инициализация настроек по умолчанию
        logger.info("Initializing default settings...")
        from app.services.settings_service import settings_service
        settings_service.initialize_default_settings()
        logger.info("✅ Default settings initialized successfully!")
        
        
        # Создание админа по умолчанию
        logger.info("Creating default admin...")
        create_default_admin()
        logger.info("✅ Default admin created/verified successfully!")
    except Exception as e:
        logger.error(f"❌ Error creating database tables: {e}")
        raise e
    
    # Предзагрузка ML-моделей
    try:
        logger.info("🔄 Preloading SentenceTransformer model for duplicates...")
        from app.utils.duplicate_processor import get_text_model
        model = get_text_model()
        logger.info("✅ SentenceTransformer model for duplicates preloaded successfully!")
    except Exception as e:
        logger.error(f"❌ Error preloading SentenceTransformer model for duplicates: {e}")
        # Не прерываем запуск приложения, модель загрузится при первом использовании

    # Запуск сервиса автоматизации
    await automation_service.start_service()
    
    logger.info("Starting Real Estate API...")
    yield
    
    # Остановка сервиса автоматизации
    await automation_service.stop_service()
    logger.info("Shutting down Real Estate API...")

app = FastAPI(
    title="Real Estate Aggregator API",
    description="API for aggregated real estate listings with duplicate detection and clustering.",
    version="1.0.0",
    lifespan=lifespan
)

# Настройки CORS для продакшена
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
if ALLOWED_ORIGINS == ["*"]:
    # Для разработки - разрешаем все
    origins = ["*"]
else:
    # Для продакшена - только указанные домены
    origins = [origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение статических файлов
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Подключение веб-интерфейса
app.include_router(web_router)

# Подключение WebSocket
app.include_router(websocket_router)

# Подключение API роутеров


# Сервисы
photo_service = PhotoService()
duplicate_service = DuplicateService()
es_service = ElasticsearchService(hosts=ELASTICSEARCH_HOSTS, index_name=ELASTICSEARCH_INDEX)

scrapy_manager = ScrapyManager(redis_url=f"{REDIS_URL}/0")

# Единый API роутер
api_router = APIRouter(prefix="/api", tags=["api"])

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
            selectinload(db_models.DBUniqueAd.photos),
            selectinload(db_models.DBUniqueAd.realtor)
        )
    
    if not filters:
        return query
        

    
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
    
    if filters.get('is_realtor') is not None:
        if filters['is_realtor']:
            query = query.filter(db_models.DBUniqueAd.realtor_id.isnot(None))
        else:
            query = query.filter(db_models.DBUniqueAd.realtor_id.is_(None))
    
    # Поиск по номеру телефона
    if filters.get('phone_number'):
        query = query.filter(db_models.DBUniqueAd.phone_numbers.contains([filters['phone_number'].strip()]))
    
    return query

# === ОСНОВНЫЕ ЭНДПОИНТЫ ===
@api_router.get("/", response_model=Dict[str, str])
async def read_root():
    """Корневой эндпоинт API"""
    return {
        "message": "Real Estate Aggregator API",
        "version": "2.0.0",
        "docs": "/docs"
    }

@api_router.get("/status", response_model=Dict[str, Union[str, int]])
async def get_status(db: Session = Depends(get_db)):
    """Статус системы"""
    try:
        total_unique = db.query(func.count(db_models.DBUniqueAd.id)).scalar()
        total_ads = db.query(func.count(db_models.DBAd.id)).scalar()
        
        # Проверка Redis
        redis_status = "connected" if redis_client else "disconnected"
        
        # Проверка Elasticsearch
        es_health = es_service.health_check()
        es_status = es_health.get('status', 'unknown')
        
        return {
            "status": "healthy",
            "total_unique_ads": total_unique,
            "total_ads": total_ads,
            "redis": redis_status,
            "elasticsearch": es_status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@api_router.get("/stats", response_model=StatsResponse)
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

# === ОБЪЯВЛЕНИЯ ===
@api_router.get("/ads/unique", response_model=PaginatedUniqueAdsResponse)
async def get_unique_ads(
    db: Session = Depends(get_db),
    city: Optional[str] = Query(None, description="Город"),
    district: Optional[str] = Query(None, description="Район"),
    min_price: Optional[float] = Query(None, ge=0, description="Минимальная цена"),
    max_price: Optional[float] = Query(None, ge=0, description="Максимальная цена"),
    min_area: Optional[float] = Query(None, ge=0, description="Минимальная площадь"),
    max_area: Optional[float] = Query(None, ge=0, description="Максимальная площадь"),
    min_land_area: Optional[float] = Query(None, ge=0, description="Минимальная площадь участка"),
    max_land_area: Optional[float] = Query(None, ge=0, description="Максимальная площадь участка"),
    rooms: Optional[int] = Query(None, ge=0, le=10, description="Количество комнат"),
    has_duplicates: Optional[bool] = Query(None, description="Есть ли дубликаты"),
    is_realtor: Optional[bool] = Query(None, description="Фильтр по риэлторам"),
    phone_number: Optional[str] = Query(None, description="Номер телефона"),
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
        'city': city,
        'district': district,
        'min_price': min_price,
        'max_price': max_price,
        'min_area': min_area,
        'max_area': max_area,
        'min_land_area': min_land_area,
        'max_land_area': max_land_area,
        'rooms': rooms,
        'has_duplicates': has_duplicates,
        'is_realtor': is_realtor,
        'phone_number': phone_number
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

@api_router.get("/ads/unique/{unique_ad_id}", response_model=DuplicateInfo)
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
        selectinload(db_models.DBUniqueAd.photos),
        selectinload(db_models.DBUniqueAd.realtor)
    ).filter(db_models.DBUniqueAd.id == unique_ad_id).first()
    
    if not unique_ad:
        raise HTTPException(status_code=404, detail="Unique ad not found")
    
    processor = DuplicateProcessor(db)
    all_ads_info = processor.get_all_ads_for_unique(unique_ad_id)
    
    base_ad = None
    if all_ads_info['base_ad']:
        base_ad = transform_ad(all_ads_info['base_ad'][0])
        # Добавляем информацию о риэлторе из уникального объявления
        if unique_ad.realtor_id:
            base_ad.realtor_id = unique_ad.realtor_id
            if unique_ad.realtor:
                base_ad.realtor = transform_realtor(unique_ad.realtor)
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

@api_router.get("/ads/unique/{unique_ad_id}/sources", response_model=List[AdSource])
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

@api_router.get("/ads/{ad_id}/duplicates")
async def get_ad_duplicates(ad_id: int, db: Session = Depends(get_db)):
    """Получить дубликаты конкретного объявления"""
    try:
        main_ad = db.query(db_models.DBUniqueAd).filter(
            db_models.DBUniqueAd.id == ad_id
        ).first()
        
        if not main_ad:
            raise HTTPException(status_code=404, detail="Объявление не найдено")
        
        if main_ad.duplicates_count == 0:
            return {
                "main_ad": {
                    "id": main_ad.id,
                    "title": main_ad.title,
                    "duplicates_count": 0
                },
                "duplicates": []
            }
        
        duplicates = db.query(db_models.DBAd).options(
            selectinload(db_models.DBAd.location),
            selectinload(db_models.DBAd.photos)
        ).filter(
            db_models.DBAd.unique_ad_id == ad_id
        ).all()
        
        duplicates_data = []
        for dup in duplicates:
            dup_data = {
                "id": dup.id,
                "title": dup.title,
                "price": float(dup.price) if dup.price else None,
                "currency": dup.currency,
                "area_sqm": float(dup.area_sqm) if dup.area_sqm else None,
                "rooms": dup.rooms,
                "source_name": dup.source_name,
                "source_url": dup.source_url,
                "created_at": dup.parsed_at.isoformat() if dup.parsed_at else None,
                "location": None,
                "photos": []
            }
            
            if dup.location:
                dup_data["location"] = {
                    "city": dup.location.city,
                    "district": dup.location.district,
                    "address": dup.location.address
                }
            
            if dup.photos:
                dup_data["photos"] = [
                    {
                        "url": photo.url,
                        "is_main": False 
                    } for photo in dup.photos[:5] 
                ]
            
            duplicates_data.append(dup_data)
        
        return {
            "main_ad": {
                "id": main_ad.id,
                "title": main_ad.title,
                "duplicates_count": main_ad.duplicates_count
            },
            "duplicates": duplicates_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ НОРМАЛИЗАЦИИ ТИПА СДЕЛКИ ===
def normalize_listing_type(listing_type: str) -> str:
    if not listing_type:
        return None
    value = listing_type.strip().lower()
    if value in ["продажа", "продаётся", "продается", "sell", "sale"]:
        return "продажа"
    if value in ["аренда", "сдача", "сдается", "сдаётся", "rent", "lease"]:
        return "аренда"
    return value  # fallback: сохранить как есть, но в нижнем регистре

@api_router.post("/ads", response_model=Ad, status_code=status.HTTP_200_OK)
async def create_ad(
    ad_data: AdCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Создает новое объявление или обновляет существующее по source_url"""
    # 🔍 Подробное логирование входящих данных
    logger.info(f"🔍 API received ad data: title='{ad_data.title[:50] if ad_data.title else 'None'}...'")
    logger.info(f"🔍 AI fields received: property_type={ad_data.property_type}, property_origin={ad_data.property_origin}, listing_type={ad_data.listing_type}")
    logger.info(f"🔍 Extracted data: rooms={ad_data.rooms}, area_sqm={ad_data.area_sqm}, floor={ad_data.floor}, total_floors={ad_data.total_floors}")
    logger.info(f"🔍 Realtor ID: {ad_data.realtor_id}")
    logger.info(f"🔍 Source URL: {ad_data.source_url}")
    
    existing_ad = db.query(db_models.DBAd).filter(
        db_models.DBAd.source_url == ad_data.source_url
    ).first()
    
    if existing_ad:
        # 🔍 ПРОВЕРКА НА ИЗМЕНЕНИЯ
        logger.info(f"🔍 Checking for changes in existing ad ID={existing_ad.id} from {ad_data.source_url}")
        
        # Сохраняем старые значения для сравнения
        old_price = existing_ad.price
        old_title = existing_ad.title
        old_description = existing_ad.description
        old_phone_numbers = existing_ad.phone_numbers
        
        # Проверяем основные изменения
        has_changes = False
        changes = []
        # Безопасное сравнение с обработкой None
        if old_price != ad_data.price:
            has_changes = True
            changes.append(f"price: {old_price} → {ad_data.price}")
        
        if old_title != ad_data.title:
            has_changes = True
            title_old = old_title[:30] + "..." if old_title and len(old_title) > 30 else old_title or "None"
            title_new = ad_data.title[:30] + "..." if ad_data.title and len(ad_data.title) > 30 else ad_data.title or "None"
            changes.append(f"title: '{title_old}' → '{title_new}'")
        
        if old_description != ad_data.description:
            has_changes = True
            changes.append("description updated")
        
        if old_phone_numbers != ad_data.phone_numbers:
            has_changes = True
            changes.append("phone_numbers updated")
        
        # Если изменений нет - пропускаем
        if not has_changes:
            logger.info(f"⏭️ No changes detected for ad ID={existing_ad.id}, skipping update")
            return transform_ad(existing_ad)
        # 🔄 ОБНОВЛЕНИЕ СУЩЕСТВУЮЩЕГО ОБЪЯВЛЕНИЯ
        logger.info(f"🔄 Updating existing ad ID={existing_ad.id} with changes: {', '.join(changes)}")
        # Обновляем основные поля
        existing_ad.title = ad_data.title
        existing_ad.description = ad_data.description
        existing_ad.price = ad_data.price
        existing_ad.price_original = ad_data.price_original
        existing_ad.currency = ad_data.currency
        existing_ad.rooms = ad_data.rooms
        existing_ad.area_sqm = ad_data.area_sqm
        existing_ad.land_area_sotka = ad_data.land_area_sotka
        existing_ad.floor = ad_data.floor
        existing_ad.total_floors = ad_data.total_floors
        existing_ad.series = ad_data.series
        existing_ad.building_type = ad_data.building_type
        existing_ad.condition = ad_data.condition
        existing_ad.furniture = ad_data.furniture
        existing_ad.heating = ad_data.heating
        existing_ad.hot_water = ad_data.hot_water
        existing_ad.gas = ad_data.gas
        existing_ad.ceiling_height = ad_data.ceiling_height
        existing_ad.phone_numbers = ad_data.phone_numbers
        existing_ad.attributes = ad_data.attributes
        existing_ad.parsed_at = datetime.utcnow()
        
        # Обновляем AI поля
        existing_ad.property_type = ad_data.property_type
        existing_ad.property_origin = ad_data.property_origin
        existing_ad.listing_type = normalize_listing_type(ad_data.listing_type) if ad_data.listing_type else None
        existing_ad.realtor_id = ad_data.realtor_id
        
        # Обновляем published_at если есть новые данные
        if ad_data.published_at:
            try:
                existing_ad.published_at = datetime.fromisoformat(ad_data.published_at)
            except ValueError:
                logger.warning(f"Invalid published_at format: {ad_data.published_at}")
        
        # Обновляем локацию если есть новые данные
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
            
            existing_ad.location_id = db_location.id
        
        # Удаляем старые фотографии и добавляем новые
        if ad_data.photos:
            # Удаляем старые фотографии
            db.query(db_models.DBPhoto).filter(db_models.DBPhoto.ad_id == existing_ad.id).delete()
            
            # Добавляем новые фотографии
            for photo in ad_data.photos:
                db_photo = db_models.DBPhoto(
                    url=str(photo.url),
                    ad_id=existing_ad.id
                )
                db.add(db_photo)
        
        # Сбрасываем флаги обработки для повторной обработки дубликатов
        existing_ad.is_processed = False
        existing_ad.is_duplicate = False
        
        db.commit()
        db.refresh(existing_ad)
        
        logger.info(f"✅ Ad updated successfully: ID={existing_ad.id}")
        logger.info(f"📝 Changes applied: {', '.join(changes) if changes else 'none'}")
        
        # Отправляем событие об обновлении объявления
        try:
            from app.services.event_emitter import event_emitter
            await event_emitter.emit_new_ad(
                ad_id=existing_ad.id,
                title=existing_ad.title or "Без названия",
                source=existing_ad.source_name
            )
        except Exception as e:
            logger.warning(f"Failed to emit events for updated ad: {e}")
        
        return transform_ad(existing_ad)
    
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

        # --- НОРМАЛИЗАЦИЯ ТИПА СДЕЛКИ ---
        normalized_listing_type = normalize_listing_type(ad_data.listing_type) if ad_data.listing_type else None

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
            land_area_sotka=ad_data.land_area_sotka,  # Добавляем поле площади участка
            floor=ad_data.floor,
            total_floors=ad_data.total_floors,
            series=ad_data.series,
            building_type=ad_data.building_type,
                            condition=ad_data.condition,
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
            is_processed=False,
            # Новые поля для AI классификации
            property_type=ad_data.property_type,
            property_origin=ad_data.property_origin,
            listing_type=normalized_listing_type,
            realtor_id=ad_data.realtor_id
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
        
        # 🔍 Логирование сохраненных данных
        logger.info(f"✅ New ad created successfully: ID={db_ad.id}")
        logger.info(f"✅ Saved AI fields: property_type='{db_ad.property_type}', property_origin='{db_ad.property_origin}', listing_type='{db_ad.listing_type}'")
        logger.info(f"✅ Saved extracted data: rooms={db_ad.rooms}, area_sqm={db_ad.area_sqm}, land_area_sotka={db_ad.land_area_sotka}, floor={db_ad.floor}, total_floors={db_ad.total_floors}")
        logger.info(f"✅ Saved realtor_id: {db_ad.realtor_id}")
        
        # Отправляем событие о новом объявлении
        try:
            from app.services.event_emitter import event_emitter
            await event_emitter.emit_new_ad(
                ad_id=db_ad.id,
                title=db_ad.title or "Без названия",
                source=db_ad.source_name
            )
            
            # Отправляем обновление статистики
            total_original_ads = db.query(db_models.DBAd).count()
            total_unique_ads = db.query(db_models.DBUniqueAd).count()
            await event_emitter.emit_stats_update({
                "total_original_ads": total_original_ads,
                "total_unique_ads": total_unique_ads,
                "new_ads": 1  # Увеличиваем счетчик новых объявлений
            })
        except Exception as e:
            logger.warning(f"Failed to emit events for new ad: {e}")
        
        return transform_ad(db_ad)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating ad: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# === ОБРАБОТКА ===
@api_router.post("/process/duplicates", status_code=status.HTTP_202_ACCEPTED)
async def process_duplicates(
    background_tasks: BackgroundTasks,
    batch_size: int = Query(100, ge=1, le=1000)
):
    """Запускает обработку всех дубликатов в фоне"""
    if duplicates_processing_status['status'] == 'running':
        return {"message": "Duplicate processing already running"}
    background_tasks.add_task(process_all_duplicates_async, batch_size)
    return {"message": "Processing all duplicates started", "batch_size": batch_size}

@api_router.post("/process/realtors/detect", status_code=status.HTTP_202_ACCEPTED)
async def detect_realtors(background_tasks: BackgroundTasks):
    """Запускает обнаружение риэлторов в фоне"""
    if realtors_detection_status['status'] == 'running':
        return {"message": "Realtor detection already running"}
    background_tasks.add_task(detect_realtors_async)
    return {"message": "Realtor detection started"}

@api_router.post("/process/photos", status_code=status.HTTP_202_ACCEPTED)
async def process_photos(background_tasks: BackgroundTasks):
    """Запускает обработку всех необработанных фотографий в фоне"""
    if photo_processing_status['status'] == 'running':
        return {"message": "Photo processing already running"}
    background_tasks.add_task(process_photos_async)
    return {"message": "Photo processing started"}

@api_router.get("/process/duplicates/status")
async def get_duplicates_process_status():
    """Проверка статуса процесса обработки дубликатов"""
    return duplicates_processing_status

@api_router.get("/process/realtors/status")
async def get_realtors_detection_status():
    """Проверка статуса процесса обнаружения риэлторов"""
    return realtors_detection_status

@api_router.get("/process/photos/status")
async def get_photos_process_status():
    """Проверка статуса процесса обработки фото"""
    return await photo_service.get_processing_status()

# === ELASTICSEARCH ===
@api_router.get("/elasticsearch/search", response_model=Dict)
async def search_ads(
    q: Optional[str] = Query(None, description="Поисковый запрос"),
    city: Optional[str] = Query(None, description="Город"),
    district: Optional[str] = Query(None, description="Район"),
    min_price: Optional[float] = Query(None, ge=0, description="Минимальная цена"),
    max_price: Optional[float] = Query(None, ge=0, description="Максимальная цена"),
    min_area: Optional[float] = Query(None, ge=0, description="Минимальная площадь"),
    max_area: Optional[float] = Query(None, ge=0, description="Максимальная площадь"),
    rooms: Optional[int] = Query(None, ge=0, description="Количество комнат"),
    phone_number: Optional[str] = Query(None, description="Номер телефона"),
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
        'phone_number': phone_number,
        'source_name': source_name
    }
    filters = {k: v for k, v in filters.items() if v is not None}
    try:
        result = es_service.search_ads(q, filters, sort_by, sort_order, page, size)
        return result
    except Exception as e:
        logger.error(f"Error in search: {e}")
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@api_router.get("/elasticsearch/health")
async def elasticsearch_health():
    """Проверка здоровья Elasticsearch"""
    try:
        health = es_service.health_check()
        return health
    except Exception as e:
        logger.error(f"Error checking Elasticsearch health: {e}")
        raise HTTPException(status_code=500, detail=f"Health check error: {str(e)}")


@api_router.get("/elasticsearch/stats")
async def elasticsearch_stats():
    """Статистика Elasticsearch индекса"""
    try:
        stats = es_service.get_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting Elasticsearch stats: {e}")
        raise HTTPException(status_code=500, detail=f"Stats error: {str(e)}")

@api_router.post("/elasticsearch/reindex", status_code=status.HTTP_202_ACCEPTED)
async def reindex_elasticsearch(background_tasks: BackgroundTasks):
    """Переиндексация всех объявлений в Elasticsearch"""
    background_tasks.add_task(reindex_elasticsearch_async)
    return {"message": "Reindexing started in background"}

# Вспомогательные функции
async def index_ad_in_elasticsearch(ad_id: int):
    """Фоновая задача для индексации объявления в Elasticsearch"""
    try:
        from app.utils.transform import to_elasticsearch_dict
        
        db = SessionLocal()
        db_ad = db.query(db_models.DBAd).filter(db_models.DBAd.id == ad_id).first()
        
        if db_ad:
            ad_data = to_elasticsearch_dict(transform_ad(db_ad))
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
    'batch_size': None,
    'total_processed': 0,
    'remaining': 0
}

realtors_detection_status = {
    'status': 'idle',
    'last_started': None,
    'last_completed': None,
    'last_error': None
}

async def process_all_duplicates_async(batch_size: int):
    """Асинхронная обработка всех дубликатов"""
    try:
        # Отправляем событие начала обработки
        await event_emitter.emit_notification("info", "Обработка дубликатов", "Начинаем обработку дубликатов", {
            "batch_size": batch_size
        })
        
        duplicates_processing_status['status'] = 'running'
        duplicates_processing_status['last_started'] = datetime.utcnow().isoformat()
        duplicates_processing_status['batch_size'] = batch_size
        
        from app.database import SessionLocal
        db = SessionLocal()
        
        try:
            processor = DuplicateProcessor(db)
            
            total_unprocessed = db.query(db_models.DBAd).filter(
                and_(
                    db_models.DBAd.is_processed == False,
                    db_models.DBAd.is_duplicate == False
                )
            ).count()
            
            if total_unprocessed == 0:
                logger.info("No unprocessed ads found for duplicate detection")
                duplicates_processing_status['status'] = 'completed'
                duplicates_processing_status['last_completed'] = datetime.utcnow().isoformat()
                await event_emitter.emit_notification("info", "Обработка завершена", "Нет необработанных объявлений")
                return
            
            logger.info(f"Starting duplicate processing for {total_unprocessed} unprocessed ads...")
            total_processed = 0
            duplicates_processing_status['total_processed'] = 0
            duplicates_processing_status['remaining'] = total_unprocessed
            
            await event_emitter.emit_automation_status({
                "stage": "duplicate_processing",
                "status": "started",
                "total_unprocessed": total_unprocessed,
                "batch_size": batch_size
            })
            
            while True:
                remaining = db.query(db_models.DBAd).filter(
                    and_(
                        db_models.DBAd.is_processed == False,
                        db_models.DBAd.is_duplicate == False
                    )
                ).count()
                
                if remaining == 0:
                    logger.info(f"✅ All duplicates processed! Total processed: {total_processed}")
                    break
                
                batch_processed = processor.process_new_ads_batch(batch_size)
                total_processed += batch_processed
                
                duplicates_processing_status['total_processed'] = total_processed
                duplicates_processing_status['remaining'] = remaining - batch_processed
                
                logger.info(f"📊 Processed batch of {batch_processed} ads. Total: {total_processed}, Remaining: {remaining - batch_processed}")
                
                db.commit()
                
                await asyncio.sleep(0.1)
            
            logger.info("✅ Duplicate processing completed, ready for next automation stage")
            
            logger.info(f"🎉 Duplicate processing completed! Total processed: {total_processed} ads")
            duplicates_processing_status['status'] = 'completed'
            duplicates_processing_status['last_completed'] = datetime.utcnow().isoformat()
            
            # Отправляем событие завершения
            await event_emitter.emit_notification("success", "Обработка завершена", 
                f"Обработано {total_processed} объявлений", {
                    "total_processed": total_processed
                })
            
        finally:
            db.close()
            
    except Exception as e:
        duplicates_processing_status['status'] = 'error'
        duplicates_processing_status['last_error'] = str(e)
        logger.error(f"❌ Error processing duplicates: {e}")
        await event_emitter.emit_notification("error", "Ошибка обработки", str(e))

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
        from app.utils.transform import to_elasticsearch_dict
        
        db = SessionLocal()
        
        try:
            unique_ads = db.query(db_models.DBUniqueAd).all()
            ads_data = []
            for unique_ad in unique_ads:
                ad_dict = to_elasticsearch_dict(transform_unique_ad(unique_ad))
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

async def process_photos_async(batch_size: int = 200):
    """Фоновая задача для обработки фотографий"""
    try:
        photo_processing_status['status'] = 'running'
        photo_processing_status['last_started'] = datetime.utcnow().isoformat()
        db = SessionLocal()
        try:
            await photo_service.process_all_unprocessed_photos(db, batch_size)
            photo_processing_status['status'] = 'completed'
            photo_processing_status['last_completed'] = datetime.utcnow().isoformat()
        finally:
            db.close()
    except Exception as e:
        photo_processing_status['status'] = 'error'
        photo_processing_status['last_error'] = str(e)
        logger.error(f"Error processing photos: {e}")

# === СКРАПИНГ ===
@api_router.post("/scraping/start/{config_name}")
async def start_scraping(config_name: str, background_tasks: BackgroundTasks):
    if config_name not in SCRAPY_CONFIG_TO_SPIDER:
        raise HTTPException(status_code=400, detail="Неизвестный конфиг")
    
    try:
        job_id = await scrapy_manager.start_job(config_name)
        return {"message": "Задача запущена", "job_id": job_id}
    except ValueError as e:
        if "отключён" in str(e):
            raise HTTPException(status_code=400, detail="Парсинг отключён в настройках системы")
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Ошибка запуска парсинга {config_name}: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@api_router.get("/scraping/status/{job_id}")
async def get_status(job_id: str):
    job = await scrapy_manager.get_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return job

@api_router.get("/scraping/jobs")
async def get_jobs():
    jobs = await scrapy_manager.get_all_jobs()
    return jobs

@api_router.post("/scraping/stop/{job_id}")
async def stop_job(job_id: str):
    job = await scrapy_manager.get_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    await scrapy_manager.stop_job(job_id)
    return {"message": "Задача остановлена"}

@api_router.post("/scraping/start-all")
async def start_all(background_tasks: BackgroundTasks):
    try:
        job_ids = await scrapy_manager.start_all()
        if not job_ids:
            return {"message": "Парсинг отключён в настройках системы", "job_ids": []}
        return {"message": "Все задачи запущены", "job_ids": job_ids}
    except Exception as e:
        logger.error(f"Ошибка запуска всех задач парсинга: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@api_router.post("/scraping/stop-all")
async def stop_all():
    """Остановка всех задач парсинга"""
    try:
        await scrapy_manager.stop_all_jobs()
        return {"message": "Все задачи остановлены"}
    except Exception as e:
        logger.error(f"Error stopping all jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/scraping/log/{job_id}")
async def get_log(job_id: str, limit: int = 100):
    job = await scrapy_manager.get_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    log = await scrapy_manager.get_log(job_id, limit=limit)
    return {"log": log}


@api_router.get("/scraping/sources")
async def get_scraping_sources():
    """Получить список источников парсинга и их статус"""
    try:
        # Получаем все задачи
        jobs = await scrapy_manager.get_all_jobs()
        
        # Получаем список источников из настроек БД
        from app.services.settings_service import settings_service
        sources = settings_service.get_setting('scraping_sources', ['house'])
        
        result = {
            "sources": sources,
            "jobs": jobs
        }
        
        return result
    except Exception as e:
        logger.error(f"❌ Ошибка получения источников парсинга: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# === АВТОМАТИЗАЦИЯ ===
@api_router.get("/automation/status")
async def get_automation_status():
    """Получение статуса автоматизации"""
    await automation_service.update_stage_status()
    status = automation_service.get_status()
    from app.services.settings_service import settings_service
    
    status['is_auto_mode'] = settings_service.get_setting('auto_mode', True)
    
    interval_minutes = settings_service.get_setting('pipeline_interval_minutes', 180)
    status['interval_minutes'] = interval_minutes
    status['interval_hours'] = interval_minutes / 60.0
    
    status['scraping_sources'] = settings_service.get_setting('scraping_sources', ['lalafo', 'stroka'])
    
    status['enabled_stages'] = {
        'scraping': settings_service.get_setting('enable_scraping', True),
        'photo_processing': settings_service.get_setting('enable_photo_processing', True),
        'duplicate_processing': settings_service.get_setting('enable_duplicate_processing', True),
        'realtor_detection': settings_service.get_setting('enable_realtor_detection', True),
        'elasticsearch_reindex': settings_service.get_setting('enable_elasticsearch_reindex', True)
    }
    
    return status

@api_router.get("/users/online")
async def get_online_users():
    """Получение статуса онлайн пользователей"""
    from app.services.websocket_manager import websocket_manager
    return {
        "online": websocket_manager.is_anyone_online(),
        "connection_count": websocket_manager.get_connection_count(),
        "connected_users": websocket_manager.get_connected_users()
    }

@api_router.post("/automation/start")
async def start_automation_pipeline(manual: bool = True):
    """Запуск пайплайна автоматизации"""
    success = await automation_service.start_pipeline(manual=manual)
    return {
        "success": success,
        "message": "Пайплайн запущен" if success else "Пайплайн уже выполняется"
    }

@api_router.post("/automation/stop")
async def stop_automation_pipeline():
    """Остановка пайплайна автоматизации"""
    await automation_service.stop_pipeline()
    return {"message": "Пайплайн остановлен"}

@api_router.post("/automation/pause")
async def pause_automation_pipeline():
    """Приостановка пайплайна автоматизации"""
    automation_service.pause_pipeline()
    return {"message": "Пайплайн приостановлен"}

@api_router.post("/automation/resume")
async def resume_automation_pipeline():
    """Возобновление пайплайна автоматизации"""
    automation_service.resume_pipeline()
    return {"message": "Пайплайн возобновлен"}



# === НАСТРОЙКИ СИСТЕМЫ ===
@api_router.get("/settings")
async def get_all_settings():
    """Получить все настройки системы"""
    from app.services.settings_service import settings_service
    return settings_service.get_all_settings()

@api_router.get("/settings/{category}")
async def get_settings_by_category(category: str):
    """Получить настройки по категории"""
    from app.services.settings_service import settings_service
    return settings_service.get_settings_by_category(category)

from pydantic import BaseModel

class SettingUpdateRequest(BaseModel):
    value: Any
    value_type: str = 'string'
    description: str = None
    category: str = None

@api_router.post("/settings/{key}")
async def update_setting(
    key: str,
    request: SettingUpdateRequest
):
    """Обновить настройку"""
    from app.services.settings_service import settings_service
    success = settings_service.set_setting(key, request.value, request.value_type, request.description, request.category)
    
    automation_keys = [
        'auto_mode', 'pipeline_interval_minutes', 'scraping_sources',
        'enable_scraping', 'enable_photo_processing', 'enable_duplicate_processing',
        'enable_realtor_detection', 'enable_elasticsearch_reindex', 'run_immediately_on_start'
    ]
    if key in automation_keys and success:
        automation_service.reload_settings()
        logger.info(f"Настройки автоматизации синхронизированы с БД: {key}={request.value}")
    
    return {
        "success": success,
        "message": f"Настройка '{key}' {'обновлена' if success else 'не обновлена'}"
    }

@api_router.delete("/settings/{key}")
async def delete_setting(key: str):
    """Удалить настройку"""
    from app.services.settings_service import settings_service
    success = settings_service.delete_setting(key)
    return {
        "success": success,
        "message": f"Настройка '{key}' {'удалена' if success else 'не удалена'}"
    }

# === ЭНДПОИНТЫ ДЛЯ РАБОТЫ С РИЭЛТОРАМИ ===
@api_router.get("/realtors", response_model=Dict)
async def get_realtors(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200, description="Количество записей"),
    offset: int = Query(0, ge=0, description="Смещение"),
    min_ads_count: Optional[int] = Query(None, ge=1, description="Минимальное количество объявлений"),
    sort_by: Optional[str] = Query("total_ads_count", description="Сортировка: total_ads_count, confidence_score, last_activity")
):
    """Получить список риэлторов с их статистикой"""
    try:
        # Получаем всех риэлторов с динамическим подсчетом объявлений
        all_realtors = db.query(db_models.DBRealtor).all()
        realtors_with_counts = []
        
        for realtor in all_realtors:
            realtor_ads_count = db.query(db_models.DBUniqueAd).filter(
                db_models.DBUniqueAd.realtor_id == realtor.id
            ).count()
            realtors_with_counts.append((realtor, realtor_ads_count))
        
        # Применяем фильтр по минимальному количеству объявлений
        if min_ads_count is not None:
            realtors_with_counts = [(r, c) for r, c in realtors_with_counts if c >= min_ads_count]
        
        # Применяем сортировку
        if sort_by == "confidence_score":
            realtors_with_counts.sort(key=lambda x: x[0].confidence_score or 0, reverse=True)
        elif sort_by == "last_activity":
            realtors_with_counts.sort(key=lambda x: x[0].last_activity or datetime.min, reverse=True)
        else:  # sort_by == "total_ads_count"
            realtors_with_counts.sort(key=lambda x: x[1], reverse=True)
        
        total = len(realtors_with_counts)
        # Применяем пагинацию
        start_idx = offset
        end_idx = offset + limit
        realtors_with_counts = realtors_with_counts[start_idx:end_idx]
        
        realtors = [realtor for realtor, _ in realtors_with_counts]
        
        result = []
        for realtor in realtors:
            # Вычисляем актуальное количество объявлений риэлтора
            realtor_ads_count = db.query(db_models.DBUniqueAd).filter(
                db_models.DBUniqueAd.realtor_id == realtor.id
            ).count()
            
            result.append({
                "id": realtor.id,
                "phone_number": realtor.phone_number,
                "name": realtor.name,
                "company_name": realtor.company_name,
                "total_ads_count": realtor_ads_count,
                "active_ads_count": realtor.active_ads_count,
                "confidence_score": realtor.confidence_score,
                "average_price": realtor.average_price,
                "favorite_districts": realtor.favorite_districts,
                "property_types": realtor.property_types,
                "first_seen": realtor.first_seen.isoformat() if realtor.first_seen else None,
                "last_activity": realtor.last_activity.isoformat() if realtor.last_activity else None
            })
        
        return {
            "items": result,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error getting realtors: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/realtors/{realtor_id}", response_model=Dict)
async def get_realtor_details(
    realtor_id: int,
    db: Session = Depends(get_db),
    include_ads: bool = Query(False, description="Включить последние объявления")
):
    """Получить детали риэлтора"""
    try:
        realtor = db.query(db_models.DBRealtor).filter(
            db_models.DBRealtor.id == realtor_id
        ).first()
        
        if not realtor:
            raise HTTPException(status_code=404, detail="Риэлтор не найден")
        
        # Вычисляем актуальное количество объявлений риэлтора
        realtor_ads_count = db.query(db_models.DBUniqueAd).filter(
            db_models.DBUniqueAd.realtor_id == realtor.id
        ).count()
        
        result = {
            "id": realtor.id,
            "phone_number": realtor.phone_number,
            "name": realtor.name,
            "company_name": realtor.company_name,
            "total_ads_count": realtor_ads_count,
            "active_ads_count": realtor.active_ads_count,
            "confidence_score": realtor.confidence_score,
            "average_price": realtor.average_price,
            "favorite_districts": realtor.favorite_districts,
            "property_types": realtor.property_types,
            "first_seen": realtor.first_seen.isoformat() if realtor.first_seen else None,
            "last_activity": realtor.last_activity.isoformat() if realtor.last_activity else None
        }
        
        if include_ads:
            recent_ads = db.query(db_models.DBUniqueAd).options(
                selectinload(db_models.DBUniqueAd.location),
                selectinload(db_models.DBUniqueAd.photos),
                selectinload(db_models.DBUniqueAd.realtor)
            ).filter(
                db_models.DBUniqueAd.realtor_id == realtor_id
            ).order_by(desc(db_models.DBUniqueAd.created_at)).limit(10).all()
            
            result["recent_ads"] = [transform_unique_ad(ad) for ad in recent_ads]
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting realtor details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/realtors/stats", response_model=Dict)
async def get_realtors_stats(db: Session = Depends(get_db)):
    """Статистика по риэлторам"""
    try:
        total_realtors = db.query(func.count(db_models.DBRealtor.id)).scalar() or 0
        active_realtors = db.query(func.count(db_models.DBRealtor.id)).filter(
            db_models.DBRealtor.active_ads_count > 0
        ).scalar() or 0
        
        # Вычисляем актуальную статистику по риэлторам
        realtors_with_counts = []
        all_realtors = db.query(db_models.DBRealtor).all()
        
        for realtor in all_realtors:
            realtor_ads_count = db.query(db_models.DBUniqueAd).filter(
                db_models.DBUniqueAd.realtor_id == realtor.id
            ).count()
            realtors_with_counts.append((realtor, realtor_ads_count))
        
        # Сортируем по количеству объявлений для получения топ-5
        realtors_with_counts.sort(key=lambda x: x[1], reverse=True)
        top_realtors = realtors_with_counts[:5]
        
        # Вычисляем среднее количество объявлений
        total_ads_count = sum(count for _, count in realtors_with_counts)
        avg_ads = total_ads_count / len(realtors_with_counts) if realtors_with_counts else 0
        
        top_realtors_data = []
        for realtor, ads_count in top_realtors:
            top_realtors_data.append({
                "id": realtor.id,
                "name": realtor.name or f"Риэлтор {realtor.phone_number}",
                "phone_number": realtor.phone_number,
                "total_ads_count": ads_count,
                "confidence_score": realtor.confidence_score
            })
        
        return {
            "total_realtors": total_realtors,
            "active_realtors": active_realtors,
            "avg_ads_per_realtor": round(float(avg_ads), 2),
            "top_realtors": top_realtors_data
        }
    except Exception as e:
        logger.error(f"Error getting realtors stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/realtors/rebuild", status_code=status.HTTP_202_ACCEPTED)
async def rebuild_realtors(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Полностью пересчитывает всех риэлторов и их статистику"""
    try:
        db.query(db_models.DBRealtor).delete()
        db.commit()
        
        background_tasks.add_task(detect_realtors_async)
        
        return {"message": "Realtor rebuild started. All existing realtor profiles will be recreated."}
    except Exception as e:
        logger.error(f"Error starting realtor rebuild: {e}")
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
        workers=6,
        log_level="info"
    )

