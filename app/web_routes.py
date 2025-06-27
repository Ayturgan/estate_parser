from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, distinct, or_
from typing import Optional
import json
from datetime import datetime, timedelta

from app.database import get_db
from app import db_models
# Инициализация
web_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@web_router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Главная страница - дашборд"""
    try:
        # Основная статистика
        total_unique = db.query(func.count(db_models.DBUniqueAd.id)).scalar() or 0
        total_ads = db.query(func.count(db_models.DBAd.id)).scalar() or 0
        total_duplicates = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.is_duplicate == True
        ).scalar() or 0
        realtor_ads = db.query(func.count(db_models.DBUniqueAd.id)).filter(
            db_models.DBUniqueAd.is_realtor == True
        ).scalar() or 0
        

        
        deduplication_ratio = (total_duplicates / total_ads) if total_ads > 0 else 0
        
        # Статистика по источникам
        sources_stats = db.query(
            db_models.DBAd.source_name,
            func.count(db_models.DBAd.id).label('count')
        ).group_by(db_models.DBAd.source_name).all()
        
        # Активность за последние 7 дней
        week_ago = datetime.now() - timedelta(days=7)
        activity_stats = []
        for i in range(7):
            date = week_ago + timedelta(days=i)
            count = db.query(func.count(db_models.DBAd.id)).filter(
                func.date(db_models.DBAd.parsed_at) == date.date()
            ).scalar() or 0
            activity_stats.append({
                'date': date.strftime('%d.%m'),
                'new_ads': count
            })
        
        # Последние объявления (преобразуем в словари)
        recent_ads_query = db.query(db_models.DBUniqueAd).order_by(
            desc(db_models.DBUniqueAd.created_at)
        ).limit(5).all()
        
        recent_ads = []
        for ad in recent_ads_query:
            recent_ads.append({
                'id': ad.id,
                'title': ad.title or 'Без названия',
                'price': ad.price,
                'duplicates_count': ad.duplicates_count,
                'created_at': ad.created_at.isoformat() if ad.created_at and hasattr(ad.created_at, 'isoformat') else str(ad.created_at) if ad.created_at else None,
                'location': {
                    'city': ad.location.city if ad.location else None,
                    'district': ad.location.district if ad.location else None
                } if ad.location else None
            })
        
        stats = {
            'total_unique_ads': total_unique,
            'total_original_ads': total_ads,
            'total_duplicates': total_duplicates,
            'realtor_ads': realtor_ads,
            'deduplication_ratio': deduplication_ratio,
            'sources_stats': [{'source_name': s[0], 'count': s[1]} for s in sources_stats],
            'activity_stats': activity_stats,
            'recent_ads': recent_ads
        }
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "stats": stats
        })
    except Exception as e:
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "error": str(e),
            "stats": {
                'total_unique_ads': 0,
                'total_original_ads': 0,
                'total_duplicates': 0,
                'realtor_ads': 0,
                'deduplication_ratio': 0,
                'sources_stats': [],
                'activity_stats': [],
                'recent_ads': []
            }
        })



@web_router.get("/ads", response_class=HTMLResponse)
async def ads_page(
    request: Request,
    db: Session = Depends(get_db),
    query: Optional[str] = Query(None),
    is_realtor: Optional[bool] = Query(None),
    city: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    min_area: Optional[float] = Query(None),
    max_area: Optional[float] = Query(None),
    rooms: Optional[int] = Query(None),
    has_duplicates: Optional[bool] = Query(None),
    sort_by: Optional[str] = Query("created_at"),
    sort_order: Optional[str] = Query("desc"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Страница просмотра объявлений"""
    try:
        # Строим запрос
        db_query = db.query(db_models.DBUniqueAd)
        
        # Применяем поиск по тексту
        if query and query.strip():
            search_term = f"%{query.strip()}%"
            db_query = db_query.filter(
                or_(
                    db_models.DBUniqueAd.title.ilike(search_term),
                    db_models.DBUniqueAd.description.ilike(search_term),
                    db_models.DBUniqueAd.location.has(
                        or_(
                            db_models.DBLocation.address.ilike(search_term),
                            db_models.DBLocation.city.ilike(search_term),
                            db_models.DBLocation.district.ilike(search_term)
                        )
                    )
                )
            )
        
        # Применяем фильтры
        if is_realtor is not None:
            db_query = db_query.filter(db_models.DBUniqueAd.is_realtor == is_realtor)
        
        if city:
            db_query = db_query.join(db_models.DBUniqueAd.location).filter(
                db_models.DBLocation.city.ilike(f"%{city}%")
            )
        
        if district:
            db_query = db_query.join(db_models.DBUniqueAd.location).filter(
                db_models.DBLocation.district.ilike(f"%{district}%")
            )
        
        if min_price is not None:
            db_query = db_query.filter(db_models.DBUniqueAd.price >= min_price)
        
        if max_price is not None:
            db_query = db_query.filter(db_models.DBUniqueAd.price <= max_price)
        
        if min_area is not None:
            db_query = db_query.filter(db_models.DBUniqueAd.area_sqm >= min_area)
        
        if max_area is not None:
            db_query = db_query.filter(db_models.DBUniqueAd.area_sqm <= max_area)
        
        if rooms is not None:
            db_query = db_query.filter(db_models.DBUniqueAd.rooms == rooms)
        
        if has_duplicates is not None:
            if has_duplicates:
                db_query = db_query.filter(db_models.DBUniqueAd.duplicates_count > 0)
            else:
                db_query = db_query.filter(db_models.DBUniqueAd.duplicates_count == 0)
        
        # Сортировка
        sort_column = getattr(db_models.DBUniqueAd, sort_by, db_models.DBUniqueAd.created_at)
        if sort_order == "desc":
            db_query = db_query.order_by(desc(sort_column))
        else:
            db_query = db_query.order_by(sort_column)
        
        # Пагинация
        total = db_query.count()
        ads = db_query.offset(offset).limit(limit).all()
        
        # Получаем уникальные города и районы для фильтров
        cities = db.query(distinct(db_models.DBLocation.city)).filter(
            db_models.DBLocation.city.isnot(None)
        ).all()
        cities = [c[0] for c in cities if c[0]]
        
        districts = db.query(distinct(db_models.DBLocation.district)).filter(
            db_models.DBLocation.district.isnot(None)
        ).all()
        districts = [d[0] for d in districts if d[0]]
        
        return templates.TemplateResponse("ads.html", {
            "request": request,
            "ads": ads,
            "total": total,
            "offset": offset,
            "limit": limit,
            "cities": sorted(cities),
            "districts": sorted(districts),
            "current_filters": {
                "query": query,
                "is_realtor": is_realtor,
                "city": city,
                "district": district,
                "min_price": min_price,
                "max_price": max_price,
                "min_area": min_area,
                "max_area": max_area,
                "rooms": rooms,
                "has_duplicates": has_duplicates,
                "sort_by": sort_by,
                "sort_order": sort_order
            }
        })
    except Exception as e:
        return templates.TemplateResponse("ads.html", {
            "request": request,
            "error": str(e),
            "ads": [],
            "total": 0,
            "offset": 0,
            "limit": limit,
            "cities": [],
            "districts": [],
            "current_filters": {}
        })



@web_router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Страница просмотра логов"""
    return templates.TemplateResponse("logs.html", {
        "request": request
    })

@web_router.get("/automation", response_class=HTMLResponse)
async def automation_page(request: Request):
    """Страница автоматизации"""
    return templates.TemplateResponse("automation.html", {
        "request": request
    })

 