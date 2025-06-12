# app/main.py

from fastapi import FastAPI, HTTPException, status, Depends
from typing import List, Dict, Optional
from datetime import datetime
import uuid

from sqlalchemy.orm import Session, joinedload, subqueryload

from app.models import Ad, Location, Photo # Наши Pydantic-модели
from app.database import engine, Base, get_db # Настройки БД и функция get_db
from app import db_models # Наши SQLAlchemy-модели (импортируем, чтобы они были известны Base)

# Создаем экземпляр приложения FastAPI
app = FastAPI(
    title="Real Estate Parser API",
    description="API for parsing real estate listings and detecting duplicates.",
    version="0.1.0"
)

# Определяем первый эндпоинт (маршрут)
@app.get("/")
async def read_root():
    """
    Root endpoint to check if the API is running.
    """
    return {"message": "Welcome to the Real Estate Parser API!"}

@app.get("/status")
async def get_status():
    """
    Returns the current status of the API.
    """
    return {"status": "running", "version": app.version}

# --- Эндпоинты для работы с объявлениями ---

@app.post("/ads/", response_model=Ad, status_code=status.HTTP_201_CREATED)
async def create_ad(ad: Ad, db: Session = Depends(get_db)):
    """
    Создает новое объявление в базе данных.
    """
    # Генерируем ID, если его нет
    if ad.id is None:
        ad.id = str(uuid.uuid4())
    
    # Проверяем, существует ли объявление с таким ID
    if db.query(db_models.DBAd).filter(db_models.DBAd.id == ad.id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ad with this ID already exists")

    # Устанавливаем время парсинга
    ad.parsed_at = datetime.now().isoformat()

    # Создаем объект SQLAlchemy-модели для Location
    db_location: Optional[db_models.DBLocation] = None
    if ad.location:
        # Проверяем, существует ли уже такое местоположение
        existing_location = db.query(db_models.DBLocation).filter(
            db_models.DBLocation.address == ad.location.address,
            db_models.DBLocation.district == ad.location.district,
            db_models.DBLocation.city == ad.location.city,
            db_models.DBLocation.region == ad.location.region
        ).first()
        if existing_location:
            db_location = existing_location
        else:
            db_location = db_models.DBLocation(
                address=ad.location.address,
                district=ad.location.district,
                city=ad.location.city,
                region=ad.location.region
            )
            db.add(db_location)
            db.flush() # Получаем ID для db_location перед созданием DBAd

    # Создаем объект SQLAlchemy-модели для Ad
    db_ad = db_models.DBAd(
        id=ad.id,
        source_url=str(ad.source_url), # Преобразуем HttpUrl в str
        source_name=ad.source_name,
        title=ad.title,
        description=ad.description,
        price=ad.price,
        currency=ad.currency,
        area_sqm=ad.area_sqm,
        rooms=ad.rooms,
        floor=ad.floor,
        total_floors=ad.total_floors,
        phone_numbers=ad.phone_numbers,
        email=ad.email,
        contact_name=ad.contact_name,
        location_id=db_location.id if db_location else None, # Привязываем location_id
        attributes=ad.attributes,
        published_at=datetime.fromisoformat(ad.published_at) if ad.published_at else None,
        parsed_at=datetime.fromisoformat(ad.parsed_at) if ad.parsed_at else None,
        is_realtor=ad.is_realtor,
        realtor_score=ad.realtor_score,
        is_duplicate=ad.is_duplicate,
        unique_ad_id=ad.unique_ad_id,
        duplicate_of_ids=ad.duplicate_of_ids
    )
    db.add(db_ad)

    # Создаем объекты SQLAlchemy-модели для Photo
    for photo in ad.photos:
        db_photo = db_models.DBPhoto(
            url=str(photo.url), # Преобразуем HttpUrl в str
            hash=photo.hash,
            ad_id=db_ad.id # Привязываем к ID объявления
        )
        db.add(db_photo)

    db.commit() # Сохраняем все изменения в БД
    db.refresh(db_ad) # Обновляем объект db_ad, чтобы получить все связанные данные (например, ID фото)

    # Преобразуем SQLAlchemy-модель обратно в Pydantic-модель для ответа
    # Здесь нужно вручную собрать Pydantic-модель, так как SQLAlchemy-модель не знает о Pydantic
    response_ad = Ad(
        id=db_ad.id,
        source_url=db_ad.source_url,
        source_name=db_ad.source_name,
        title=db_ad.title,
        description=db_ad.description,
        price=db_ad.price,
        currency=db_ad.currency,
        area_sqm=db_ad.area_sqm,
        rooms=db_ad.rooms,
        floor=db_ad.floor,
        total_floors=db_ad.total_floors,
        phone_numbers=db_ad.phone_numbers,
        email=db_ad.email,
        contact_name=db_ad.contact_name,
        location=Location(
            address=db_ad.location_obj.address,
            district=db_ad.location_obj.district,
            city=db_ad.location_obj.city,
            region=db_ad.location_obj.region
        ) if db_ad.location_obj else None,
        photos=[Photo(url=p.url, hash=p.hash) for p in db_ad.photos_obj],
        attributes=db_ad.attributes,
        published_at=db_ad.published_at.isoformat() if db_ad.published_at else None,
        parsed_at=db_ad.parsed_at.isoformat() if db_ad.parsed_at else None,
        is_realtor=db_ad.is_realtor,
        realtor_score=db_ad.realtor_score,
        is_duplicate=db_ad.is_duplicate,
        unique_ad_id=db_ad.unique_ad_id,
        duplicate_of_ids=db_ad.duplicate_of_ids
    )
    return response_ad


@app.get("/ads/{ad_id}", response_model=Ad)
async def get_ad(ad_id: str, db: Session = Depends(get_db)):
    """
    Возвращает объявление по его ID, включая информацию о дубликатах, если применимо.
    """
    # Загружаем объявление, его местоположение, фото, а также связанные дубликаты или уникального родителя
    db_ad = db.query(db_models.DBAd).options(
        joinedload(db_models.DBAd.location_obj),
        joinedload(db_models.DBAd.photos_obj),
        subqueryload(db_models.DBAd.duplicates_list), # Загружаем список дубликатов, если это уникальное объявление
        joinedload(db_models.DBAd.unique_parent_ad) # Загружаем уникального родителя, если это дубликат
    ).filter(db_models.DBAd.id == ad_id).first()

    if db_ad is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad not found")
    
    # Преобразуем SQLAlchemy-модель в Pydantic-модель для ответа
    response_ad = Ad(
        id=db_ad.id,
        source_url=db_ad.source_url,
        source_name=db_ad.source_name,
        title=db_ad.title,
        description=db_ad.description,
        price=db_ad.price,
        currency=db_ad.currency,
        area_sqm=db_ad.area_sqm,
        rooms=db_ad.rooms,
        floor=db_ad.floor,
        total_floors=db_ad.total_floors,
        phone_numbers=db_ad.phone_numbers,
        email=db_ad.email,
        contact_name=db_ad.contact_name,
        location=Location(
            address=db_ad.location_obj.address,
            district=db_ad.location_obj.district,
            city=db_ad.location_obj.city,
            region=db_ad.location_obj.region
        ) if db_ad.location_obj else None,
        photos=[Photo(url=p.url, hash=p.hash) for p in db_ad.photos_obj],
        attributes=db_ad.attributes,
        published_at=db_ad.published_at.isoformat() if db_ad.published_at else None,
        parsed_at=db_ad.parsed_at.isoformat() if db_ad.parsed_at else None,
        is_realtor=db_ad.is_realtor,
        realtor_score=db_ad.realtor_score,
        is_duplicate=db_ad.is_duplicate,
        unique_ad_id=db_ad.unique_ad_id,
        # Если это уникальное объявление, заполняем duplicate_of_ids из duplicates_list
        duplicate_of_ids=[dup.id for dup in db_ad.duplicates_list] if not db_ad.is_duplicate else [],
    )
    return response_ad


@app.get("/ads/", response_model=List[Ad])
async def get_all_ads(
    db: Session = Depends(get_db),
    is_realtor: Optional[bool] = None, # Фильтр по риэлтору
    city: Optional[str] = None,        # Фильтр по городу
    district: Optional[str] = None,    # Фильтр по району
    min_price: Optional[float] = None, # Фильтр по минимальной цене
    max_price: Optional[float] = None, # Фильтр по максимальной цене
    min_area: Optional[float] = None,  # Фильтр по минимальной площади
    max_area: Optional[float] = None,  # Фильтр по максимальной площади
    rooms: Optional[int] = None,       # Фильтр по количеству комнат
    source_name: Optional[str] = None, # Фильтр по источнику
    limit: int = 100,                  # Ограничение количества результатов
    offset: int = 0                    # Смещение для пагинации
):
    """
    Возвращает список всех объявлений из базы данных с возможностью фильтрации.
    """
    query = db.query(db_models.DBAd).options(
        joinedload(db_models.DBAd.location_obj), # Загружаем location_obj одним запросом
        joinedload(db_models.DBAd.photos_obj)    # Загружаем photos_obj одним запросом
    )

    if is_realtor is not None:
        query = query.filter(db_models.DBAd.is_realtor == is_realtor)
    
    if city:
        # Фильтруем по городу в связанной таблице locations
        query = query.join(db_models.DBAd.location_obj).filter(db_models.DBLocation.city == city)
    
    if district:
        query = query.join(db_models.DBAd.location_obj).filter(db_models.DBLocation.district == district)

    if min_price:
        query = query.filter(db_models.DBAd.price >= min_price)
    if max_price:
        query = query.filter(db_models.DBAd.price <= max_price)
    
    if min_area:
        query = query.filter(db_models.DBAd.area_sqm >= min_area)
    if max_area:
        query = query.filter(db_models.DBAd.area_sqm <= max_area)

    if rooms:
        query = query.filter(db_models.DBAd.rooms == rooms)

    if source_name:
        query = query.filter(db_models.DBAd.source_name == source_name)

    # Применяем пагинацию
    db_ads = query.offset(offset).limit(limit).all()
    
    # Преобразуем список SQLAlchemy-моделей в список Pydantic-моделей
    response_ads = []
    for db_ad in db_ads:
        response_ads.append(Ad(
            id=db_ad.id,
            source_url=db_ad.source_url,
            source_name=db_ad.source_name,
            title=db_ad.title,
            description=db_ad.description,
            price=db_ad.price,
            currency=db_ad.currency,
            area_sqm=db_ad.area_sqm,
            rooms=db_ad.rooms,
            floor=db_ad.floor,
            total_floors=db_ad.total_floors,
            phone_numbers=db_ad.phone_numbers,
            email=db_ad.email,
            contact_name=db_ad.contact_name,
            location=Location(
                address=db_ad.location_obj.address,
                district=db_ad.location_obj.district,
                city=db_ad.location_obj.city,
                region=db_ad.location_obj.region
            ) if db_ad.location_obj else None,
            photos=[Photo(url=p.url, hash=p.hash) for p in db_ad.photos_obj],
            attributes=db_ad.attributes,
            published_at=db_ad.published_at.isoformat() if db_ad.published_at else None,
            parsed_at=db_ad.parsed_at.isoformat() if db_ad.parsed_at else None,
            is_realtor=db_ad.is_realtor,
            realtor_score=db_ad.realtor_score,
            is_duplicate=db_ad.is_duplicate,
            unique_ad_id=db_ad.unique_ad_id,
            duplicate_of_ids=db_ad.duplicate_of_ids
        ))
    return response_ads

@app.get("/ads/{ad_id}/sources", response_model=List[Dict[str, str]])
async def get_ad_sources(ad_id: str, db: Session = Depends(get_db)):
    """
    Возвращает список источников (URL и название) для данного объявления и всех его дубликатов.
    """
    db_ad = db.query(db_models.DBAd).options(
        subqueryload(db_models.DBAd.duplicates_list),
        joinedload(db_models.DBAd.unique_parent_ad)
    ).filter(db_models.DBAd.id == ad_id).first()

    if db_ad is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad not found")

    sources = []
    
    # Если это уникальное объявление, добавляем его источник и источники всех его дубликатов
    if not db_ad.is_duplicate:
        sources.append({"id": db_ad.id, "source_url": db_ad.source_url, "source_name": db_ad.source_name})
        for duplicate in db_ad.duplicates_list:
            sources.append({"id": duplicate.id, "source_url": duplicate.source_url, "source_name": duplicate.source_name})
    # Если это дубликат, находим его уникального родителя и добавляем источники всей группы
    else:
        if db_ad.unique_parent_ad:
            sources.append({"id": db_ad.unique_parent_ad.id, "source_url": db_ad.unique_parent_ad.source_url, "source_name": db_ad.unique_parent_ad.source_name})
            for duplicate in db_ad.unique_parent_ad.duplicates_list:
                sources.append({"id": duplicate.id, "source_url": duplicate.source_url, "source_name": duplicate.source_name})
        else:
            # Если дубликат, но уникальный родитель не найден (возможно, ошибка данных),
            # то просто возвращаем источник самого дубликата.
            sources.append({"id": db_ad.id, "source_url": db_ad.source_url, "source_name": db_ad.source_name})

    return sources