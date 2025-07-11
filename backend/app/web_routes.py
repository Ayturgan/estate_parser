from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, distinct, or_
from typing import Optional
import json
from datetime import datetime, timedelta

from app.database import get_db
from app.database import db_models
from app.services.auth_service import auth_service

# Инициализация
web_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Вспомогательная функция для получения текущего пользователя
def get_current_admin(request: Request, db: Session):
    """Получает текущего авторизованного администратора"""
    token = request.cookies.get("access_token")
    if not token or not token.startswith("Bearer "):
        return None
    
    token_value = token.split(" ")[1]
    return auth_service.get_admin_by_token(db, token_value)

@web_router.get("/", response_class=HTMLResponse)
async def home_page(
    request: Request,
    db: Session = Depends(get_db),
    query: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    min_area: Optional[float] = Query(None),
    max_area: Optional[float] = Query(None),
    rooms: Optional[int] = Query(None),
    has_duplicates: Optional[bool] = Query(None),
    is_realtor: Optional[bool] = Query(None),
    property_type: Optional[str] = Query(None, description="Тип недвижимости"),
    listing_type: Optional[str] = Query(None, description="Тип сделки"),
    source_name: Optional[str] = Query(None, description="Источник объявления"),
    sort_by: Optional[str] = Query("created_at"),
    sort_order: Optional[str] = Query("desc"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Главная страница - объявления"""
    try:
        # Получаем текущего пользователя для навигации
        current_admin = get_current_admin(request, db)
        
        db_query = db.query(db_models.DBUniqueAd)
        
        # DEBUG: Вывести все property_type и listing_type из базы до фильтрации
        all_property_types = db.query(db_models.DBUniqueAd.property_type).all()
        all_listing_types = db.query(db_models.DBUniqueAd.listing_type).all()
        print(f"[DEBUG] all_property_types (raw): {all_property_types}")
        print(f"[DEBUG] all_listing_types (raw): {all_listing_types}")
        
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
        
        # Получаем уникальные типы недвижимости и типы сделок (чистим, сортируем, убираем дубликаты)
        property_types = db.query(db_models.DBUniqueAd.property_type).filter(db_models.DBUniqueAd.property_type.isnot(None)).all()
        property_types = sorted(set(pt[0].strip() for pt in property_types if pt[0] and pt[0].strip()))
        listing_types = db.query(db_models.DBUniqueAd.listing_type).filter(db_models.DBUniqueAd.listing_type.isnot(None)).all()
        listing_types = sorted(set(lt[0].strip() for lt in listing_types if lt[0] and lt[0].strip()))
        print(f"[DEBUG] property_types: {property_types}")
        print(f"[DEBUG] listing_types: {listing_types}")
        print(f"[DEBUG] selected property_type: {property_type}")
        print(f"[DEBUG] selected listing_type: {listing_type}")

        # Если в базе нет данных, используем фиксированные значения из конфигов парсинга
        if not property_types:
            property_types = ["Квартира", "Дом", "Коммерческая недвижимость", "Комната", "Земельный участок", "Дача", "Гараж"]
        if not listing_types:
            listing_types = ["Продажа", "Аренда"]

        # Фильтрация по типу недвижимости
        if property_type:
            property_type_clean = property_type.strip()
            if property_type_clean in property_types:
                db_query = db_query.filter(db_models.DBUniqueAd.property_type == property_type_clean)
        # Фильтрация по типу сделки
        if listing_type:
            listing_type_clean = listing_type.strip()
            if listing_type_clean in listing_types:
                db_query = db_query.filter(db_models.DBUniqueAd.listing_type == listing_type_clean)
        
        # Фильтрация по источнику
        if source_name:
            db_query = db_query.join(db_models.DBAd, db_models.DBUniqueAd.base_ad_id == db_models.DBAd.id).filter(
                db_models.DBAd.source_name == source_name
            )
        
        if is_realtor is not None:
            print(f"DEBUG: is_realtor = {is_realtor}, type = {type(is_realtor)}")
            # Преобразуем строку в булево значение
            is_realtor_bool = str(is_realtor).lower() in ['true', '1', 'yes']
            print(f"DEBUG: is_realtor_bool = {is_realtor_bool}")
            if is_realtor_bool:
                db_query = db_query.filter(db_models.DBUniqueAd.realtor_id.isnot(None))
                print("DEBUG: Applied filter for realtors")
            else:
                db_query = db_query.filter(db_models.DBUniqueAd.realtor_id.is_(None))
                print("DEBUG: Applied filter for non-realtors")
        
        # Сортировка
        sort_column = getattr(db_models.DBUniqueAd, sort_by, db_models.DBUniqueAd.created_at)
        if sort_order == "desc":
            db_query = db_query.order_by(desc(sort_column))
        else:
            db_query = db_query.order_by(sort_column)
        
        # Пагинация
        total = db_query.count()
        ads = db_query.offset(offset).limit(limit).all()
        print(f"[DEBUG] total ads after filter: {total}")
        
        cities = db.query(distinct(db_models.DBLocation.city)).filter(
            db_models.DBLocation.city.isnot(None)
        ).all()
        cities = [c[0] for c in cities if c[0]]
        
        districts = db.query(distinct(db_models.DBLocation.district)).filter(
            db_models.DBLocation.district.isnot(None)
        ).all()
        districts = [d[0] for d in districts if d[0]]
        
        # Получаем список источников
        sources = db.query(distinct(db_models.DBAd.source_name)).filter(
            db_models.DBAd.source_name.isnot(None)
        ).all()
        sources = [s[0] for s in sources if s[0]]
        
        return templates.TemplateResponse("ads.html", {
            "request": request,
            "ads": ads,
            "total": total,
            "offset": offset,
            "limit": limit,
            "cities": sorted(cities),
            "districts": sorted(districts),
            "sources": sorted(sources),
            "property_types": sorted(property_types),
            "listing_types": sorted(listing_types),
            "current_filters": {
                "query": query,
                "city": city,
                "district": district,
                "min_price": min_price,
                "max_price": max_price,
                "min_area": min_area,
                "max_area": max_area,
                "rooms": rooms,
                "has_duplicates": has_duplicates,
                "is_realtor": is_realtor,
                "property_type": property_type,
                "listing_type": listing_type,
                "source_name": source_name,
                "sort_by": sort_by,
                "sort_order": sort_order
            },
            "current_admin": current_admin
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
            "current_filters": {},
            "current_admin": get_current_admin(request, db)
                 })

@web_router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Дашборд для администраторов"""
    # Проверка авторизации
    current_admin = get_current_admin(request, db)
    if not current_admin:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Необходима авторизация для доступа к дашборду"
        })
    
    try:
        # Основная статистика
        total_unique = db.query(func.count(db_models.DBUniqueAd.id)).scalar() or 0
        total_ads = db.query(func.count(db_models.DBAd.id)).scalar() or 0
        total_duplicates = db.query(func.count(db_models.DBAd.id)).filter(
            db_models.DBAd.is_duplicate == True
        ).scalar() or 0
        realtor_ads = db.query(func.count(db_models.DBUniqueAd.id)).filter(
            db_models.DBUniqueAd.realtor_id.isnot(None)
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
        
        # Последние объявления
        recent_ads_query = db.query(db_models.DBUniqueAd).order_by(
            desc(db_models.DBUniqueAd.created_at)
        ).limit(5).all()
        
        recent_ads = []
        for ad in recent_ads_query:
            recent_ads.append({
                'id': ad.id,
                'title': ad.title or 'Без названия',
                'price': ad.price,
                'currency': ad.currency,
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
            "stats": stats,
            "current_admin": current_admin
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
            },
            "current_admin": current_admin
        })

@web_router.get("/ads", response_class=HTMLResponse)
async def ads_page(
    request: Request,
    db: Session = Depends(get_db),
    query: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    min_area: Optional[float] = Query(None),
    max_area: Optional[float] = Query(None),
    rooms: Optional[int] = Query(None),
    has_duplicates: Optional[bool] = Query(None),
    is_realtor: Optional[bool] = Query(None),
    property_type: Optional[str] = Query(None, description="Тип недвижимости"),
    listing_type: Optional[str] = Query(None, description="Тип сделки"),
    source_name: Optional[str] = Query(None, description="Источник объявления"),
    sort_by: Optional[str] = Query("created_at"),
    sort_order: Optional[str] = Query("desc"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Страница просмотра объявлений"""
    try:
        # Получаем текущего пользователя для навигации
        current_admin = get_current_admin(request, db)
        
        db_query = db.query(db_models.DBUniqueAd)
        
        # Приведение параметра is_realtor к булеву типу (важно для корректной фильтрации)
        if isinstance(is_realtor, str):
            is_realtor_bool = is_realtor.lower() in ['true', '1', 'yes']
        else:
            is_realtor_bool = bool(is_realtor) if is_realtor is not None else None
        
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
        
        # Получаем уникальные типы недвижимости и типы сделок (чистим, сортируем, убираем дубликаты)
        property_types = db.query(db_models.DBUniqueAd.property_type).filter(db_models.DBUniqueAd.property_type.isnot(None)).all()
        property_types = sorted(set(pt[0].strip() for pt in property_types if pt[0] and pt[0].strip()))
        listing_types = db.query(db_models.DBUniqueAd.listing_type).filter(db_models.DBUniqueAd.listing_type.isnot(None)).all()
        listing_types = sorted(set(lt[0].strip() for lt in listing_types if lt[0] and lt[0].strip()))
        print(f"[DEBUG] property_types: {property_types}")
        print(f"[DEBUG] listing_types: {listing_types}")
        print(f"[DEBUG] selected property_type: {property_type}")
        print(f"[DEBUG] selected listing_type: {listing_type}")

        # Если в базе нет данных, используем фиксированные значения из конфигов парсинга
        if not property_types:
            property_types = ["Квартира", "Дом", "Коммерческая недвижимость", "Комната", "Земельный участок", "Дача", "Гараж"]
        if not listing_types:
            listing_types = ["Продажа", "Аренда"]

        # Фильтрация по типу недвижимости
        if property_type:
            property_type_clean = property_type.strip()
            if property_type_clean in property_types:
                db_query = db_query.filter(db_models.DBUniqueAd.property_type == property_type_clean)
        # Фильтрация по типу сделки
        if listing_type:
            listing_type_clean = listing_type.strip()
            if listing_type_clean in listing_types:
                db_query = db_query.filter(db_models.DBUniqueAd.listing_type == listing_type_clean)
        
        # Фильтрация по источнику
        if source_name:
            db_query = db_query.join(db_models.DBAd, db_models.DBUniqueAd.base_ad_id == db_models.DBAd.id).filter(
                db_models.DBAd.source_name == source_name
            )
        
        # Фильтрация по риэлторам
        if is_realtor_bool is not None:
            if is_realtor_bool:
                db_query = db_query.filter(db_models.DBUniqueAd.realtor_id.isnot(None))
            else:
                db_query = db_query.filter(db_models.DBUniqueAd.realtor_id.is_(None))
        
        # Сортировка
        sort_column = getattr(db_models.DBUniqueAd, sort_by, db_models.DBUniqueAd.created_at)
        if sort_order == "desc":
            db_query = db_query.order_by(desc(sort_column))
        else:
            db_query = db_query.order_by(sort_column)
        
        # Пагинация
        total = db_query.count()
        ads = db_query.offset(offset).limit(limit).all()
        print(f"[DEBUG] total ads after filter: {total}")
        
        cities = db.query(distinct(db_models.DBLocation.city)).filter(
            db_models.DBLocation.city.isnot(None)
        ).all()
        cities = [c[0] for c in cities if c[0]]
        
        districts = db.query(distinct(db_models.DBLocation.district)).filter(
            db_models.DBLocation.district.isnot(None)
        ).all()
        districts = [d[0] for d in districts if d[0]]
        
        # Получаем список источников
        sources = db.query(distinct(db_models.DBAd.source_name)).filter(
            db_models.DBAd.source_name.isnot(None)
        ).all()
        sources = [s[0] for s in sources if s[0]]
        
        return templates.TemplateResponse("ads.html", {
            "request": request,
            "ads": ads,
            "total": total,
            "offset": offset,
            "limit": limit,
            "cities": sorted(cities),
            "districts": sorted(districts),
            "sources": sorted(sources),
            "property_types": sorted(property_types),
            "listing_types": sorted(listing_types),
            "current_filters": {
                "query": query,
                "city": city,
                "district": district,
                "min_price": min_price,
                "max_price": max_price,
                "min_area": min_area,
                "max_area": max_area,
                "rooms": rooms,
                "has_duplicates": has_duplicates,
                "is_realtor": is_realtor,
                "property_type": property_type,
                "listing_type": listing_type,
                "source_name": source_name,
                "sort_by": sort_by,
                "sort_order": sort_order
            },
            "current_admin": current_admin
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
            "current_filters": {},
            "current_admin": get_current_admin(request, db)
        })

@web_router.get("/automation", response_class=HTMLResponse)
async def automation_page(request: Request, db: Session = Depends(get_db)):
    """Страница автоматизации"""
    # Проверка авторизации
    current_admin = get_current_admin(request, db)
    if not current_admin:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Необходима авторизация для доступа к автоматизации"
        })
    
    # Получаем данные конфигурации из настроек БД
    from app.services.settings_service import settings_service
    
    # Конфигурация автоматизации
    is_auto_mode = settings_service.get_setting('auto_mode', True)
    
    interval_minutes = settings_service.get_setting('pipeline_interval_minutes', 180)
    interval_hours = interval_minutes / 60.0
    
    scraping_sources = settings_service.get_setting('scraping_sources', ['lalafo', 'stroka'])
    
    enabled_stages = {
        'scraping': settings_service.get_setting('enable_scraping', True),
        'photo_processing': settings_service.get_setting('enable_photo_processing', True),
        'duplicate_processing': settings_service.get_setting('enable_duplicate_processing', True),
        'realtor_detection': settings_service.get_setting('enable_realtor_detection', True),
        'elasticsearch_reindex': settings_service.get_setting('enable_elasticsearch_reindex', True)
    }
    
    return templates.TemplateResponse("automation.html", {
        "request": request,
        "current_admin": current_admin,
        "automation_config": {
            "is_auto_mode": is_auto_mode,
            "interval_hours": interval_hours,
            "interval_minutes": interval_minutes,
            "scraping_sources": scraping_sources,
            "enabled_stages": enabled_stages
        }
    })

@web_router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    """Страница настроек системы"""
    # Проверка авторизации
    current_admin = get_current_admin(request, db)
    if not current_admin:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Необходима авторизация для доступа к настройкам"
        })
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "current_admin": current_admin
    })

# === АВТОРИЗАЦИЯ ===

@web_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница входа"""
    return templates.TemplateResponse("login.html", {
        "request": request
    })

@web_router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Обработка входа"""
    from app.services.auth_service import auth_service
    from app.database.models import AdminLogin
    
    try:
        login_data = AdminLogin(username=username, password=password)
        token = auth_service.authenticate_admin(db, login_data)
        
        if token:
            from fastapi.responses import RedirectResponse
            response = RedirectResponse(url="/", status_code=302)
            
            # Устанавливаем JWT токен в cookie (httponly для безопасности)
            response.set_cookie(
                key="access_token",
                value=f"Bearer {token.access_token}",
                max_age=token.expires_in,
                httponly=True,
                secure=False,  # В продакшене должно быть True для HTTPS
                path="/",
                samesite="lax"
            )
            
            # Дополнительный cookie для WebSocket (НЕ httponly)
            response.set_cookie(
                key="ws_token",
                value=token.access_token,  # Без "Bearer "
                max_age=token.expires_in,
                httponly=False,  # Доступен для JavaScript
                secure=False,
                path="/",
                samesite="lax"
            )
            
            return response
        else:
            return templates.TemplateResponse("login.html", {
                "request": request,
                "error": "Неверное имя пользователя или пароль"
            })
    except Exception as e:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": f"Ошибка входа: {str(e)}"
        })

@web_router.get("/logout")
async def logout(request: Request):
    """Выход из системы"""
    from fastapi.responses import RedirectResponse
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    response.delete_cookie("ws_token")
    return response

@web_router.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(
    request: Request, 
    db: Session = Depends(get_db),
    success: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    error: Optional[str] = Query(None)
):
    """Страница управления пользователями"""
    # Проверка авitorизации
    current_admin = get_current_admin(request, db)
    if not current_admin:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Необходима авторизация"
        })
    
    # Получаем список всех админов
    admins = auth_service.get_all_admins(db)
    
    # Подготавливаем сообщения на основе параметров
    success_message = None
    error_message = None
    
    if success == "created" and username:
        success_message = f"Администратор {username} успешно создан"
    elif error:
        error_message = error
    
    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "admins": admins,
        "current_admin": current_admin,
        "success": success_message,
        "error": error_message
    })

@web_router.post("/admin/users/create")
async def create_admin(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(""),
    db: Session = Depends(get_db)
):
    """Создание нового администратора"""
    from app.database.models import AdminCreate
    from fastapi.responses import RedirectResponse
    
    # Проверка авторизации
    current_admin = get_current_admin(request, db)
    if not current_admin:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Необходима авторизации"
        })
    
    try:
        admin_data = AdminCreate(
            username=username,
            password=password,
            full_name=full_name if full_name else None
        )
        new_admin = auth_service.create_admin(db, admin_data)
        
        # Успешное создание - делаем redirect с параметром успеха
        return RedirectResponse(
            url=f"/admin/users?success=created&username={username}",
            status_code=302
        )
        
    except ValueError as e:
        # Ошибка валидации - делаем redirect с параметром ошибки
        import urllib.parse
        error_msg = urllib.parse.quote(str(e))
        return RedirectResponse(
            url=f"/admin/users?error={error_msg}",
            status_code=302
        )
        
    except Exception as e:
        # Другие ошибки - делаем redirect с параметром ошибки
        import urllib.parse
        error_msg = urllib.parse.quote(f"Ошибка создания: {str(e)}")
        return RedirectResponse(
            url=f"/admin/users?error={error_msg}",
            status_code=302
        )

# === НОВЫЕ РОУТЫ ДЛЯ ДЕТАЛЬНЫХ СТРАНИЦ ===

@web_router.get("/ad/{ad_id}", response_class=HTMLResponse)
async def ad_detail_page(
    request: Request,
    ad_id: int,
    db: Session = Depends(get_db)
):
    """Детальная страница объявления"""
    try:
        # Получаем текущего пользователя для навигации
        current_admin = get_current_admin(request, db)
        
        # Получаем уникальное объявление
        unique_ad = db.query(db_models.DBUniqueAd).filter(
            db_models.DBUniqueAd.id == ad_id
        ).first()
        
        if not unique_ad:
            return templates.TemplateResponse("ads.html", {
                "request": request,
                "error": "Объявление не найдено",
                "current_admin": current_admin,
                "ads": [],
                "total": 0,
                "offset": 0,
                "limit": 20,
                "cities": [],
                "districts": [],
                "property_types": [],
                "listing_types": [],
                "current_filters": {}
            })
        
        # Получаем все связанные объявления (базовое + дубликаты)
        from app.utils.duplicate_processor import DuplicateProcessor
        processor = DuplicateProcessor(db)
        all_ads_info = processor.get_all_ads_for_unique(ad_id)
        
        # Получаем базовое объявление
        base_ad = None
        if all_ads_info['base_ad']:
            base_ad = all_ads_info['base_ad'][0]
        
        # Получаем дубликаты
        duplicates = all_ads_info['duplicates']
        
        # Получаем информацию о риэлторе если есть
        realtor = None
        if unique_ad.realtor_id:
            realtor = db.query(db_models.DBRealtor).filter(
                db_models.DBRealtor.id == unique_ad.realtor_id
            ).first()
        
        return templates.TemplateResponse("ad_detail.html", {
            "request": request,
            "unique_ad": unique_ad,
            "base_ad": base_ad,
            "duplicates": duplicates,
            "realtor": realtor,
            "current_admin": current_admin
        })
        
    except Exception as e:
        return templates.TemplateResponse("ads.html", {
            "request": request,
            "error": f"Ошибка загрузки объявления: {str(e)}",
            "current_admin": current_admin,
            "ads": [],
            "total": 0,
            "offset": 0,
            "limit": 20,
            "cities": [],
            "districts": [],
            "property_types": [],
            "listing_types": [],
            "current_filters": {}
        })

@web_router.get("/realtor/{realtor_id}", response_class=HTMLResponse)
async def realtor_profile_page(
    request: Request,
    realtor_id: int,
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Страница профиля риэлтора"""
    try:
        # Получаем текущего пользователя для навигации
        current_admin = get_current_admin(request, db)
        
        # Получаем информацию о риэлторе
        realtor = db.query(db_models.DBRealtor).filter(
            db_models.DBRealtor.id == realtor_id
        ).first()
        
        if not realtor:
            return templates.TemplateResponse("ads.html", {
                "request": request,
                "error": "Риэлтор не найден",
                "current_admin": current_admin,
                "ads": [],
                "total": 0,
                "offset": 0,
                "limit": 20,
                "cities": [],
                "districts": [],
                "property_types": [],
                "listing_types": [],
                "current_filters": {}
            })
        
        # Получаем объявления риэлтора
        ads_query = db.query(db_models.DBUniqueAd).filter(
            db_models.DBUniqueAd.realtor_id == realtor_id
        ).order_by(desc(db_models.DBUniqueAd.created_at))
        
        total_ads = ads_query.count()
        ads = ads_query.offset(offset).limit(limit).all()
        
        return templates.TemplateResponse("realtor_profile.html", {
            "request": request,
            "realtor": realtor,
            "ads": ads,
            "total_ads": total_ads,
            "offset": offset,
            "limit": limit,
            "current_admin": current_admin
        })
        
    except Exception as e:
        return templates.TemplateResponse("ads.html", {
            "request": request,
            "error": f"Ошибка загрузки профиля риэлтора: {str(e)}",
            "current_admin": current_admin,
            "ads": [],
            "total": 0,
            "offset": 0,
            "limit": 20,
            "cities": [],
            "districts": [],
            "property_types": [],
            "listing_types": [],
            "current_filters": {}
        })

 