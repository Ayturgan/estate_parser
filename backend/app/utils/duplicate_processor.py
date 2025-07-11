import logging
logger = logging.getLogger(__name__)

from typing import List, Dict, Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import numpy as np
from sentence_transformers import SentenceTransformer
import asyncio
from sqlalchemy import and_, or_, func
from app.database.db_models import DBAd, DBUniqueAd, DBAdDuplicate, DBUniquePhoto
from app.services.ai_data_extractor import get_cached_gliner_model

# Импорт event_emitter для отправки событий
try:
    from app.services.event_emitter import event_emitter
except ImportError:
    event_emitter = None

_text_model = None

def get_text_model():
    """Возвращает кэшированную модель для эмбеддингов (SentenceTransformer)"""
    global _text_model
    if _text_model is None:
        logger.info("Loading SentenceTransformer model...")
        from sentence_transformers import SentenceTransformer
        _text_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        logger.info("SentenceTransformer model loaded successfully")
    return _text_model

_gliner_model = None

def get_gliner_model():
    """Возвращает кэшированную модель GLiNER"""
    global _gliner_model
    if _gliner_model is None:
        _gliner_model = get_cached_gliner_model()
    return _gliner_model

class DuplicateProcessor:
    def __init__(self, db: Session, realtor_threshold: int = 5):
        self.db = db
        self.text_model = get_text_model()
        self.gliner_model = get_gliner_model()
        self.realtor_threshold = realtor_threshold
        
    def process_new_ads(self, batch_size: int = 100):
        """Обрабатывает новые объявления на предмет дубликатов (старый метод)"""
        unprocessed_ads = self.db.query(DBAd).filter(
            and_(
                DBAd.is_processed == False,
                DBAd.is_duplicate == False
            )
        ).limit(batch_size).all()
        
        for ad in unprocessed_ads:
            self.process_ad(ad)

        self.detect_realtors()
            
        self.db.commit()
    
    def process_new_ads_batch(self, batch_size: int = 100) -> int:
        """Обрабатывает батч необработанных объявлений"""
        unprocessed_ads = self.db.query(DBAd).filter(
            and_(
                DBAd.is_processed == False,
                DBAd.is_duplicate == False
            )
        ).limit(batch_size).all()
        
        total_ads = len(unprocessed_ads)
        processed_count = 0
        
        # Отправляем событие начала обработки (только если есть объявления)
        if total_ads > 0:
            logger.info(f"Starting batch processing of {total_ads} ads")
        
        for i, ad in enumerate(unprocessed_ads):
            try:
                self.process_ad(ad)
                processed_count += 1
                
                # Отправляем прогресс только каждые 10 объявлений или в конце
                if processed_count % 10 == 0 or processed_count == total_ads:
                    progress = int((processed_count / total_ads) * 100)
                    logger.info(f"Processed {processed_count}/{total_ads} ads ({progress}%)")
                    
            except Exception as e:
                logger.error(f"Error processing ad {ad.id}: {e}")
                # Помечаем объявление как обработанное даже при ошибке, чтобы не зацикливаться
                ad.is_processed = True
                ad.processed_at = datetime.utcnow()
                processed_count += 1
        
        # Отправляем событие завершения
        if total_ads > 0:
            logger.info(f"Completed batch processing: {processed_count}/{total_ads} ads")
        
        return processed_count
    
    def process_ad(self, ad: DBAd):
        """Обрабатывает одно объявление"""
        logger.info(f"Processing ad {ad.id} ({ad.title})")
        ad_photo_hashes = [photo.hash for photo in ad.photos if photo.hash]
        logger.info(f"Got {len(ad_photo_hashes)} photo hashes")
        text_embeddings = self._get_text_embeddings(ad)
        logger.info("Got text embeddings")
        similar_unique_ads = self._find_similar_unique_ads(ad, ad_photo_hashes, text_embeddings)
        logger.info(f"Found {len(similar_unique_ads)} similar unique ads")
        
        if similar_unique_ads:
            unique_ad, similarity = similar_unique_ads[0]
            logger.info(f"Found duplicate with similarity {similarity:.2f}")
            self._handle_duplicate(ad, unique_ad, similarity)
            
            # Отправляем событие об обнаружении дубликата (синхронно)
            try:
                if event_emitter:
                    pass  # Убираем асинхронный вызов, так как мы в синхронном контексте
            except Exception as e:
                logger.warning(f"Could not emit duplicate detected event: {e}")
        else:
            logger.info("Creating new unique ad")
            unique_ad = self._create_unique_ad(ad, ad_photo_hashes, text_embeddings)
            
            # Отправляем событие о новом объявлении (синхронно)
            try:
                if event_emitter:
                    pass  # Убираем асинхронный вызов, так как мы в синхронном контексте
            except Exception as e:
                logger.warning(f"Could not emit new ad event: {e}")
                
                # Отправляем обновление статистики (синхронно)
                try:
                    if event_emitter:
                        pass  # Убираем асинхронный вызов
                except Exception as e:
                    logger.warning(f"Could not emit stats update event: {e}")
        ad.is_processed = True
        ad.processed_at = datetime.utcnow()
    
    def _get_text_embeddings(self, ad: DBAd) -> np.ndarray:
        """Получает эмбеддинги текста объявления через SentenceTransformer"""
        text = f"{ad.title} {ad.description}"
        # Используем только SentenceTransformer для избежания проблем с GLiNER
        return self.text_model.encode(text)
    
    def _find_similar_unique_ads(
        self,
        ad: DBAd,
        ad_photo_hashes: List[str],
        text_embeddings: np.ndarray
    ) -> List[Tuple[DBUniqueAd, float]]:
        """
        Ищет похожие уникальные объявления
        """
        similar_ads = []
        base_query = self.db.query(DBUniqueAd)
        if ad.location_id:
            base_query = base_query.filter(DBUniqueAd.location_id == ad.location_id)
        if ad.price:
            min_price = ad.price * 0.8
            max_price = ad.price * 1.2
            base_query = base_query.filter(
                and_(
                    DBUniqueAd.price >= min_price,
                    DBUniqueAd.price <= max_price
                )
            )
        if ad.rooms:
            base_query = base_query.filter(DBUniqueAd.rooms == ad.rooms)
        candidate_ads = base_query.all()
        logger.info(f"Found {len(candidate_ads)} candidate unique ads after basic filtering")
        for unique_ad in candidate_ads:
            sim, threshold = self._calculate_similarity_with_unique(
                ad, unique_ad,
                ad_photo_hashes,
                text_embeddings
            )
            logger.info(f"Similarity with unique ad {unique_ad.id}: {sim:.2f} (threshold: {threshold})")
            if sim > threshold:
                similar_ads.append((unique_ad, sim))
        return sorted(similar_ads, key=lambda x: x[1], reverse=True)
    
    def _get_property_type(self, ad: DBAd) -> str:
        """Определяет тип недвижимости из поля property_type"""
        if getattr(ad, 'property_type', None):
            return ad.property_type.lower().strip()
        return ""

    def _calculate_similarity_with_unique(
        self,
        ad: DBAd,
        unique_ad: DBUniqueAd,
        ad_photo_hashes: List[str],
        text_embeddings: np.ndarray
    ) -> float:
        """
        Вычисляет схожесть объявления с уникальным объявлением
        Теперь: если типы недвижимости не совпадают — схожесть 0
        """
        # --- ФИЛЬТРАЦИЯ ПО ТИПУ НЕДВИЖИМОСТИ ---
        ad_type = self._get_property_type(ad)
        unique_type = getattr(unique_ad, 'property_type', None)
        if unique_type:
            unique_type = unique_type.lower().strip()
        
        # Если оба типа определены и не совпадают — сразу схожесть 0
        if ad_type and unique_type and ad_type != unique_type:
            logger.info(f"Типы недвижимости не совпадают: '{ad_type}' vs '{unique_type}'. Считаем схожесть 0.")
            return 0.0, 1.0
        
        # Дополнительная проверка: если один тип определен, а другой нет - снижаем схожесть
        if (ad_type and not unique_type) or (unique_type and not ad_type):
            logger.info(f"Один тип недвижимости не определен: '{ad_type}' vs '{unique_type}'. Снижаем схожесть.")
            # Не возвращаем 0, но будем более строгими в других критериях
        # --- Дальше обычная логика ---
        # Вычисляем схожесть по характеристикам недвижимости (основной критерий)
        characteristics_sim = self._calculate_property_characteristics_similarity(ad, unique_ad)
        
        # Вычисляем схожесть по адресу
        address_sim = self._calculate_address_similarity_with_unique(ad, unique_ad)
        
        # Вычисляем схожесть по фотографиям
        unique_photo_hashes = [photo.hash for photo in unique_ad.photos if photo.hash]
        photo_sim = self._calculate_photo_similarity(ad_photo_hashes, unique_photo_hashes)
        
        # Вычисляем схожесть по тексту (вторичный критерий)
        if unique_ad.text_embeddings:
            unique_text_embeddings = np.array(unique_ad.text_embeddings)
            text_sim = self._calculate_text_similarity(text_embeddings, unique_text_embeddings)
        else:
            unique_text_embeddings = self._get_text_embeddings_from_unique(unique_ad)
            text_sim = self._calculate_text_similarity(text_embeddings, unique_text_embeddings)
        
        # НОВЫЕ ВЕСА: теперь текст учитывается в итоговой метрике!
        # Если есть фотографии - фото как подтверждение, текст важен
        if photo_sim > 0:
            weights = {
                'characteristics': 0.6,  # Увеличиваем вес характеристик
                'address': 0.2,          # Важный критерий
                'photo': 0.1,            # Дополнительное подтверждение
                'text': 0.1              # Уменьшаем вес текста
            }
            similarity_threshold = 0.75  # Повышаем порог для избежания ложных дубликатов
        else:
            # Нет фотографий - текст становится ещё важнее
            weights = {
                'characteristics': 0.6,  # Увеличиваем вес характеристик
                'address': 0.2,          # Важный критерий
                'photo': 0.0,            # Нет фотографий
                'text': 0.2              # Семантическое сравнение текста
            }
            similarity_threshold = 0.78  # Повышаем порог для избежания ложных дубликатов
        
        # Вычисляем общую схожесть
        overall_sim = (
            characteristics_sim * weights['characteristics'] +
            address_sim * weights['address'] +
            photo_sim * weights['photo'] +
            text_sim * weights['text']
        )
        
        # Логируем детали для отладки
        logger.info(f"NEW Similarity scores for ad {ad.id} vs unique ad {unique_ad.id}:")
        logger.info(f"  Characteristics: {characteristics_sim:.2f} (weight: {weights['characteristics']})")
        logger.info(f"  Address: {address_sim:.2f} (weight: {weights['address']})")
        logger.info(f"  Photo: {photo_sim:.2f} (weight: {weights['photo']})")
        logger.info(f"  Text: {text_sim:.2f} (weight: {weights['text']})")
        logger.info(f"  Overall: {overall_sim:.2f} (threshold: {similarity_threshold})")
        
        return overall_sim, similarity_threshold
    
    def _get_text_embeddings_from_unique(self, unique_ad: DBUniqueAd) -> np.ndarray:
        """Получает эмбеддинги текста уникального объявления"""
        text = f"{unique_ad.title} {unique_ad.description}"
        return self.text_model.encode(text)
    
    def _calculate_photo_similarity(
        self,
        hashes1: List[str],
        hashes2: List[str]
    ) -> float:
        """Вычисляет схожесть фотографий"""
        if not hashes1 or not hashes2:
            return 0.0
            
        matches = len(set(hashes1) & set(hashes2))
        total = len(set(hashes1) | set(hashes2))
        
        if matches > 0:
            return matches / total
            
        return 0.0
    
    def _calculate_text_similarity(self, emb1, emb2) -> float:
        """Вычисляет семантическую схожесть текста через SentenceTransformer"""
        if emb1 is None or emb2 is None:
            return 0.0
        
        # Проверяем, что эмбеддинги - это numpy массивы
        if not isinstance(emb1, np.ndarray):
            emb1 = np.array(emb1, dtype=np.float32)
        if not isinstance(emb2, np.ndarray):
            emb2 = np.array(emb2, dtype=np.float32)
        
        # Приводим к одной длине если нужно
        if emb1.shape != emb2.shape:
            min_len = min(len(emb1), len(emb2))
            emb1 = emb1[:min_len]
            emb2 = emb2[:min_len]
        
        # Проверяем на нулевые векторы
        if np.linalg.norm(emb1) == 0 or np.linalg.norm(emb2) == 0:
            return 0.0
        
        # Вычисляем косинусное сходство
        return float(np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2)))
    
    def _calculate_contact_similarity(
        self,
        phones1: List[str],
        phones2: List[str]
    ) -> float:
        """Вычисляет схожесть контактов"""
        if not phones1 or not phones2:
            return 0.0
            
        def normalize_phone(phone: str) -> str:
            return ''.join(filter(str.isdigit, phone))
            
        phones1 = [normalize_phone(p) for p in phones1]
        phones2 = [normalize_phone(p) for p in phones2]
        
        matches = len(set(phones1) & set(phones2))
        total = len(set(phones1) | set(phones2))
        
        return matches / total if total > 0 else 0.0
    
    def _calculate_address_similarity_with_unique(
        self,
        ad: DBAd,
        unique_ad: DBUniqueAd
    ) -> float:
        """Вычисляет схожесть адресов между DBAd и DBUniqueAd"""
        if not ad.location or not unique_ad.location:
            return 0.0
            
        components1 = [
            ad.location.city,
            ad.location.district,
            ad.location.address
        ]
        components2 = [
            unique_ad.location.city,
            unique_ad.location.district,
            unique_ad.location.address
        ]
        
        matches = sum(1 for c1, c2 in zip(components1, components2) if c1 and c2 and c1 == c2)
        total = sum(1 for c1, c2 in zip(components1, components2) if c1 or c2)
        
        return matches / total if total > 0 else 0.0
    
    def _calculate_property_characteristics_similarity(
        self,
        ad: DBAd,
        unique_ad: DBUniqueAd
    ) -> float:
        """
        Вычисляет схожесть по неизменяемым характеристикам недвижимости
        Фокусируется на характеристиках, которые не могут измениться у одного объекта
        """
        characteristics = []
        
        # 1. Площадь (с небольшой погрешностью)
        if ad.area_sqm and unique_ad.area_sqm:
            try:
                area_diff = abs(float(ad.area_sqm) - float(unique_ad.area_sqm))
                # Увеличиваем допуск для площади - разница до 5 кв.м считается одинаковой
                area_sim = 1.0 if area_diff < 5.0 else 0.0
                characteristics.append(('area_sqm', area_sim, 1.0))
            except (ValueError, TypeError):
                characteristics.append(('area_sqm', 0.0, 1.0))
        elif not ad.area_sqm and not unique_ad.area_sqm:
            characteristics.append(('area_sqm', 1.0, 1.0))
        else:
            characteristics.append(('area_sqm', 0.0, 1.0))
        
        # 2. Количество комнат
        if ad.rooms and unique_ad.rooms:
            try:
                rooms_sim = 1.0 if int(ad.rooms) == int(unique_ad.rooms) else 0.0
                characteristics.append(('rooms', rooms_sim, 1.0))
            except (ValueError, TypeError):
                characteristics.append(('rooms', 0.0, 1.0))
        elif not ad.rooms and not unique_ad.rooms:
            characteristics.append(('rooms', 1.0, 1.0))
        else:
            characteristics.append(('rooms', 0.0, 1.0))
        
        # 3. Этаж
        if ad.floor and unique_ad.floor:
            try:
                floor_sim = 1.0 if int(ad.floor) == int(unique_ad.floor) else 0.0
                characteristics.append(('floor', floor_sim, 0.8))
            except (ValueError, TypeError):
                characteristics.append(('floor', 0.0, 0.8))
        elif not ad.floor and not unique_ad.floor:
            characteristics.append(('floor', 1.0, 0.8))
        else:
            characteristics.append(('floor', 0.0, 0.8))
        
        # 4. Общая этажность
        if ad.total_floors and unique_ad.total_floors:
            try:
                total_floors_sim = 1.0 if int(ad.total_floors) == int(unique_ad.total_floors) else 0.0
                characteristics.append(('total_floors', total_floors_sim, 0.7))
            except (ValueError, TypeError):
                characteristics.append(('total_floors', 0.0, 0.7))
        elif not ad.total_floors and not unique_ad.total_floors:
            characteristics.append(('total_floors', 1.0, 0.7))
        else:
            characteristics.append(('total_floors', 0.0, 0.7))
        
        # 5. Тип здания
        if ad.building_type and unique_ad.building_type:
            building_sim = 1.0 if str(ad.building_type) == str(unique_ad.building_type) else 0.0
            characteristics.append(('building_type', building_sim, 0.6))
        elif not ad.building_type and not unique_ad.building_type:
            characteristics.append(('building_type', 1.0, 0.6))
        else:
            characteristics.append(('building_type', 0.0, 0.6))
        
        # 6. Серия дома
        if ad.series and unique_ad.series:
            series_sim = 1.0 if str(ad.series) == str(unique_ad.series) else 0.0
            characteristics.append(('series', series_sim, 0.5))
        elif not ad.series and not unique_ad.series:
            characteristics.append(('series', 1.0, 0.5))
        else:
            characteristics.append(('series', 0.0, 0.5))
        
        # 7. Тип недвижимости (квартира/дом/участок)
        if ad.property_type and unique_ad.property_type:
            property_sim = 1.0 if str(ad.property_type) == str(unique_ad.property_type) else 0.0
            characteristics.append(('property_type', property_sim, 0.9))
        elif not ad.property_type and not unique_ad.property_type:
            characteristics.append(('property_type', 1.0, 0.9))
        else:
            characteristics.append(('property_type', 0.0, 0.9))
        
        # 8. Тип сделки (продажа/аренда)
        if ad.listing_type and unique_ad.listing_type:
            listing_sim = 1.0 if str(ad.listing_type) == str(unique_ad.listing_type) else 0.0
            characteristics.append(('listing_type', listing_sim, 0.8))
        elif not ad.listing_type and not unique_ad.listing_type:
            characteristics.append(('listing_type', 1.0, 0.8))
        else:
            characteristics.append(('listing_type', 0.0, 0.8))
        
        # 9. Площадь участка (для домов)
        if ad.land_area_sotka and unique_ad.land_area_sotka:
            try:
                land_diff = abs(float(ad.land_area_sotka) - float(unique_ad.land_area_sotka))
                land_sim = 1.0 if land_diff < 0.1 else 0.0
                characteristics.append(('land_area_sotka', land_sim, 0.8))
            except (ValueError, TypeError):
                characteristics.append(('land_area_sotka', 0.0, 0.8))
        elif not ad.land_area_sotka and not unique_ad.land_area_sotka:
            characteristics.append(('land_area_sotka', 1.0, 0.8))
        else:
            characteristics.append(('land_area_sotka', 0.0, 0.8))
        
        # Вычисляем общую схожесть по характеристикам
        total_weight = sum(weight for _, _, weight in characteristics)
        weighted_sum = sum(sim * weight for _, sim, weight in characteristics)
        
        overall_sim = weighted_sum / total_weight if total_weight > 0 else 0.0
        
        # Логируем детали для отладки
        logger.info(f"Property characteristics similarity for ad {ad.id} vs unique ad {unique_ad.id}:")
        for char_name, sim, weight in characteristics:
            logger.info(f"  {char_name}: {sim:.2f} (weight: {weight})")
        logger.info(f"  Overall characteristics similarity: {overall_sim:.2f}")
        
        return overall_sim
    
    def _handle_duplicate(
        self,
        ad: DBAd,
        unique_ad: DBUniqueAd,
        similarity: float
    ):
        """Обрабатывает найденный дубликат"""
        ad_photo_hashes = [photo.hash for photo in ad.photos if photo.hash]
        unique_ad_photo_hashes = [photo.hash for photo in unique_ad.photos if photo.hash]
        
        # Вычисляем схожесть по характеристикам для записи в дубликат
        characteristics_sim = self._calculate_property_characteristics_similarity(ad, unique_ad)
        
        duplicate = DBAdDuplicate(
            unique_ad_id=unique_ad.id,
            original_ad_id=ad.id,
            photo_similarity=self._calculate_photo_similarity(
                ad_photo_hashes,
                unique_ad_photo_hashes
            ),
            text_similarity=self._calculate_text_similarity(
                self._get_text_embeddings(ad),
                np.array(unique_ad.text_embeddings) if unique_ad.text_embeddings else self._get_text_embeddings_from_unique(unique_ad)
            ),
            contact_similarity=self._calculate_contact_similarity(
                ad.phone_numbers,
                unique_ad.phone_numbers
            ),
            address_similarity=self._calculate_address_similarity_with_unique(ad, unique_ad),
            characteristics_similarity=characteristics_sim,  # НОВОЕ ПОЛЕ
            overall_similarity=similarity
        )
        
        self.db.add(duplicate)
        
        ad.is_duplicate = True
        ad.duplicate_info = duplicate
        ad.unique_ad_id = unique_ad.id
        unique_ad.duplicates_count = (unique_ad.duplicates_count or 0) + 1
        self._update_unique_ad(unique_ad, ad)
        
        logger.info(f"Ad {ad.id} marked as duplicate of unique ad {unique_ad.id}. Duplicates count: {unique_ad.duplicates_count}")
    
    def _create_unique_ad(
        self,
        ad: DBAd,
        ad_photo_hashes: List[str],
        text_embeddings: np.ndarray
    ) -> DBUniqueAd:
        """Создает новое уникальное объявление"""
        unique_ad = DBUniqueAd(
            title=ad.title,
            description=ad.description,
            price=ad.price,
            price_original=ad.price_original,
            currency=ad.currency,
            phone_numbers=ad.phone_numbers,
            rooms=ad.rooms,
            area_sqm=ad.area_sqm,
            floor=ad.floor,
            total_floors=ad.total_floors,
            series=ad.series,
            building_type=ad.building_type,
                            condition=ad.condition,
            furniture=ad.furniture,
            heating=ad.heating,
            hot_water=ad.hot_water,
            gas=ad.gas,
            ceiling_height=ad.ceiling_height,
            location_id=ad.location_id,
            attributes=ad.attributes,
            text_embeddings=text_embeddings.tolist(),
            confidence_score=1.0,
            duplicates_count=0,
            base_ad_id=ad.id,
            property_type=ad.property_type,
            listing_type=ad.listing_type
        )
        self.db.add(unique_ad)
        self.db.flush()  
        self.db.refresh(unique_ad)
        for photo in ad.photos:
            unique_photo = DBUniquePhoto(
                url=photo.url,
                hash=photo.hash,
                unique_ad_id=unique_ad.id
            )
            self.db.add(unique_photo)
        ad.is_duplicate = False
        ad.unique_ad_id = unique_ad.id
        logger.info(f"Created new unique ad {unique_ad.id} from base ad {ad.id}. Duplicates count: {unique_ad.duplicates_count}")
        
        return unique_ad
    
    def _update_unique_ad(self, unique_ad: DBUniqueAd, ad: DBAd):
        """Обновляет уникальное объявление новыми данными"""
        if ad.title and (not unique_ad.title or len(ad.title) > len(unique_ad.title)):
            unique_ad.title = ad.title
        if ad.description and (not unique_ad.description or len(ad.description) > len(unique_ad.description)):
            unique_ad.description = ad.description
        if ad.price is not None and unique_ad.price is None:
            unique_ad.price = ad.price
            unique_ad.price_original = ad.price_original
            unique_ad.currency = ad.currency
        if ad.phone_numbers:
            if unique_ad.phone_numbers:
                unique_ad.phone_numbers = list(set(unique_ad.phone_numbers + ad.phone_numbers))
            else:
                unique_ad.phone_numbers = ad.phone_numbers
        if ad.area_sqm is not None and unique_ad.area_sqm is None:
            unique_ad.area_sqm = ad.area_sqm
        if ad.land_area_sotka is not None and unique_ad.land_area_sotka is None:
            unique_ad.land_area_sotka = ad.land_area_sotka
        if ad.rooms is not None and unique_ad.rooms is None:
            unique_ad.rooms = ad.rooms
        if ad.floor is not None and unique_ad.floor is None:
            unique_ad.floor = ad.floor
        if ad.total_floors is not None and unique_ad.total_floors is None:
            unique_ad.total_floors = ad.total_floors
        fields_to_update_if_none = [
            'series', 'building_type', 'condition', 'furniture',
            'heating', 'hot_water', 'gas'
        ]
        for field in fields_to_update_if_none:
            ad_value = getattr(ad, field)
            unique_ad_value = getattr(unique_ad, field)
            if ad_value and not unique_ad_value:
                setattr(unique_ad, field, ad_value)
        if ad.ceiling_height is not None and unique_ad.ceiling_height is None:
            unique_ad.ceiling_height = ad.ceiling_height

        if ad.attributes:
            if unique_ad.attributes:
                unique_ad.attributes.update(ad.attributes)
            else:
                unique_ad.attributes = ad.attributes
        if ad.location:
            if not unique_ad.location:
                unique_ad.location = ad.location
            else:
                if ad.location.city and not unique_ad.location.city:
                    unique_ad.location.city = ad.location.city
                if ad.location.district and not unique_ad.location.district:
                    unique_ad.location.district = ad.location.district
                if ad.location.address and (not unique_ad.location.address or len(ad.location.address) > len(unique_ad.location.address)):
                    unique_ad.location.address = ad.location.address
        existing_hashes = {photo.hash for photo in unique_ad.photos if photo.hash}
        for photo in ad.photos:
            if photo.hash and photo.hash not in existing_hashes:
                unique_photo = DBUniquePhoto(
                    url=photo.url,
                    hash=photo.hash,
                    unique_ad_id=unique_ad.id
                )
                self.db.add(unique_photo)
        if ad.title or ad.description:
            new_text_embeddings = self._get_text_embeddings_from_unique(unique_ad)
            unique_ad.text_embeddings = new_text_embeddings.tolist()

        if ad.property_type and not unique_ad.property_type:
            unique_ad.property_type = ad.property_type
        if ad.listing_type and not unique_ad.listing_type:
            unique_ad.listing_type = ad.listing_type

    def get_base_ad_for_unique(self, unique_ad_id: int) -> Optional[DBAd]:
        """Получает базовое объявление для уникального объявления"""
        unique_ad = self.db.query(DBUniqueAd).filter(DBUniqueAd.id == unique_ad_id).first()
        if not unique_ad:
            return None
        if hasattr(unique_ad, 'base_ad_id') and unique_ad.base_ad_id:
            return self.db.query(DBAd).filter(DBAd.id == unique_ad.base_ad_id).first()
        base_ad = self.db.query(DBAd).filter(
            and_(
                DBAd.is_duplicate == False,
                DBAd.is_processed == True,
                DBAd.location_id == unique_ad.location_id
            )
        ).first()
        
        return base_ad

    def get_all_ads_for_unique(self, unique_ad_id: int) -> Dict[str, List[DBAd]]:
        """Получает все объявления (базовое + дубликаты) для уникального объявления"""
        base_ad = self.get_base_ad_for_unique(unique_ad_id)
        duplicates = self.db.query(DBAdDuplicate).filter(
            DBAdDuplicate.unique_ad_id == unique_ad_id
        ).all()
        
        duplicate_ads = []
        for dup in duplicates:
            ad = self.db.query(DBAd).filter(DBAd.id == dup.original_ad_id).first()
            if ad:
                duplicate_ads.append(ad)
        
        return {
            'base_ad': [base_ad] if base_ad else [],
            'duplicates': duplicate_ads,
            'total_count': (1 if base_ad else 0) + len(duplicate_ads)
        }

    def detect_realtors(self):
        """Обнаруживает риэлторов на основе количества объявлений и создает их профили"""
        from app.database.db_models import DBRealtor
        
        # 1. Ищем телефоны с большим количеством объявлений
        phone_groups = self.db.query(
            func.jsonb_array_elements_text(DBAd.phone_numbers).label("phone_number"),
            func.count(DBAd.id).label("ad_count")
        ) \
            .filter(DBAd.phone_numbers.isnot(None)) \
            .group_by(func.jsonb_array_elements_text(DBAd.phone_numbers)) \
            .having(func.count(DBAd.id) > self.realtor_threshold) \
            .all()

        current_realtor_phones = {pg.phone_number: pg.ad_count for pg in phone_groups}

        # 2. Убираем realtor_id у объявлений тех, кто больше не риэлтор
        existing_realtors = self.db.query(DBRealtor).all()
        for realtor in existing_realtors:
            if realtor.phone_number not in current_realtor_phones:
                # У этого номера стало меньше 5 объявлений
                self.db.query(DBUniqueAd).filter(
                    DBUniqueAd.realtor_id == realtor.id
                ).update({DBUniqueAd.realtor_id: None})
                
                # Удаляем профиль риэлтора
                self.db.delete(realtor)
                logger.info(f"Removed realtor status from phone: {realtor.phone_number}")

        if not current_realtor_phones:
            logger.info("No realtors detected based on phone number threshold.")
            self.db.commit()
            return

        logger.info(f"Detected {len(current_realtor_phones)} potential realtor phone numbers.")
        
        # 3. Обрабатываем каждый номер риэлтора
        for phone_number, total_ads_count in current_realtor_phones.items():
            try:
                self._process_realtor_phone(phone_number, total_ads_count)
            except Exception as e:
                logger.error(f"Error processing realtor phone {phone_number}: {e}")
                continue

        self.db.commit()
        logger.info("Realtor detection complete.")

    def _process_realtor_phone(self, phone_number: str, total_ads_count: int):
        """Обрабатывает номер телефона риэлтора: создает профиль и связывает объявления"""
        from app.database.db_models import DBRealtor
        
        # 1. Находим или создаем запись риэлтора
        realtor = self.db.query(DBRealtor).filter(
            DBRealtor.phone_number == phone_number
        ).first()
        
        if not realtor:
            realtor = DBRealtor(
                phone_number=phone_number,
                total_ads_count=total_ads_count,
                created_at=datetime.utcnow()
            )
            self.db.add(realtor)
            self.db.flush()  # Получаем ID
            logger.info(f"Created new realtor profile for phone: {phone_number}")
            
            # Отправляем событие об обнаружении риэлтора (синхронно)
            try:
                if event_emitter:
                    # Используем синхронный вызов или игнорируем ошибку event loop
                    pass  # Убираем асинхронный вызов, так как мы в синхронном контексте
            except Exception as e:
                logger.warning(f"Could not emit realtor detected event: {e}")
        else:
            # Обновляем количество объявлений
            realtor.total_ads_count = total_ads_count
            realtor.updated_at = datetime.utcnow()
        
        # 2. Находим и связываем уникальные объявления с риэлтором
        unique_ads_to_update = (
            self.db.query(DBUniqueAd)
            .join(DBAd, DBAd.unique_ad_id == DBUniqueAd.id)
            .filter(DBAd.phone_numbers.op("@>")(f'["{phone_number}"]'))
            .distinct()
            .all()
        )

        for unique_ad in unique_ads_to_update:
            unique_ad.realtor_id = realtor.id
        
        logger.info(f"Linked {len(unique_ads_to_update)} unique ads to realtor: {phone_number}")

    def get_duplicate_statistics(self) -> Dict[str, int]:
        """Возвращает статистику по дубликатам"""
        total_unique_ads = self.db.query(DBUniqueAd).count()
        total_original_ads = self.db.query(DBAd).count()
        duplicate_ads = self.db.query(DBAd).filter(DBAd.is_duplicate == True).count()
        base_ads = self.db.query(DBAd).filter(DBAd.is_duplicate == False).count()
        unique_ads_with_duplicates = self.db.query(DBUniqueAd).filter(
            DBUniqueAd.duplicates_count > 0
        ).count()

        avg_duplicates = self.db.query(func.avg(DBUniqueAd.duplicates_count)).scalar() or 0
        
        return {
            'total_unique_ads': total_unique_ads,
            'total_original_ads': total_original_ads,
            'base_ads': base_ads,
            'duplicate_ads': duplicate_ads,
            'unique_ads_with_duplicates': unique_ads_with_duplicates,
            'avg_duplicates_per_unique': float(avg_duplicates),
            'deduplication_ratio': (duplicate_ads / total_original_ads * 100) if total_original_ads > 0 else 0
        }

    def get_realtor_statistics(self) -> Dict[str, int]:
        """Возвращает статистику по риэлторам и объявлениям"""
        from app.database.db_models import DBRealtor
        
        total_realtors = self.db.query(DBRealtor).count()
        realtor_unique_ads = self.db.query(DBUniqueAd).filter(
            DBUniqueAd.realtor_id.isnot(None)
        ).count()
        realtor_original_ads = self.db.query(DBAd).filter(
            DBAd.realtor_id.isnot(None)
        ).count()
        total_unique_ads = self.db.query(DBUniqueAd).count()
        total_original_ads = self.db.query(DBAd).count()
        # Средний процент объявлений от риэлторов
        realtor_percentage = (realtor_unique_ads / total_unique_ads * 100) if total_unique_ads > 0 else 0
        return {
            'total_realtors': total_realtors,
            'realtor_unique_ads': realtor_unique_ads,
            'realtor_original_ads': realtor_original_ads,
            'total_unique_ads': total_unique_ads,
            'total_original_ads': total_original_ads,
            'realtor_percentage': float(realtor_percentage)
        }

