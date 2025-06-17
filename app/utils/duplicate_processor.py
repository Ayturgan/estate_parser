import hashlib
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import numpy as np
from sentence_transformers import SentenceTransformer
from PIL import Image
import io
import requests
from imagehash import average_hash
import logging

from app.db_models import DBAd, DBUniqueAd, DBAdDuplicate, DBPhoto, DBUniquePhoto

logger = logging.getLogger(__name__)

class DuplicateProcessor:
    def __init__(self, db: Session):
        self.db = db
        self.text_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        
    def process_new_ads(self, batch_size: int = 100):
        """Обрабатывает новые объявления на предмет дубликатов"""
        # Получаем необработанные объявления
        unprocessed_ads = self.db.query(DBAd).filter(
            and_(
                DBAd.is_processed == False,
                DBAd.is_duplicate == False
            )
        ).limit(batch_size).all()
        
        for ad in unprocessed_ads:
            self.process_ad(ad)
            
        self.db.commit()
    
    def process_ad(self, ad: DBAd):
        """Обрабатывает одно объявление"""
        logger.info(f"Processing ad {ad.id} ({ad.title})")
        
        # 1. Получаем хэши фото
        ad_photo_hashes = [photo.hash for photo in ad.photos if photo.hash]
        logger.info(f"Got {len(ad_photo_hashes)} photo hashes")
        
        # 2. Получаем эмбеддинги текста
        text_embeddings = self._get_text_embeddings(ad)
        logger.info("Got text embeddings")
        
        # 3. Ищем похожие объявления
        similar_ads = self._find_similar_ads(ad, ad_photo_hashes, text_embeddings)
        logger.info(f"Found {len(similar_ads)} similar ads")
        
        if similar_ads:
            # Нашли дубликат
            unique_ad, similarity = similar_ads[0]
            logger.info(f"Found duplicate with similarity {similarity:.2f}")
            self._handle_duplicate(ad, unique_ad, similarity)
        else:
            # Создаем новое уникальное объявление
            logger.info("Creating new unique ad")
            self._create_unique_ad(ad, ad_photo_hashes, text_embeddings)
        
        # Отмечаем как обработанное
        ad.is_processed = True
        ad.processed_at = datetime.utcnow()
    
    def _get_text_embeddings(self, ad: DBAd) -> np.ndarray:
        """Получает эмбеддинги текста объявления"""
        text = f"{ad.title} {ad.description}"
        return self.text_model.encode(text)
    
    def _find_similar_ads(
        self,
        ad: DBAd,
        ad_photo_hashes: List[str],
        text_embeddings: np.ndarray
    ) -> List[Tuple[DBAd, float]]:
        """Ищет похожие объявления"""
        similar_ads = []
        
        # Ищем по всем объявлениям, кроме текущего
        for other_ad in self.db.query(DBAd).filter(DBAd.id != ad.id).all():
            similarity = self._calculate_similarity(
                ad, other_ad,
                ad_photo_hashes,
                text_embeddings
            )
            
            logger.info(f"Similarity with ad {other_ad.id}: {similarity:.2f}")
            
            if similarity > 0.8:  # Увеличиваем порог схожести
                similar_ads.append((other_ad, similarity))
        
        return sorted(similar_ads, key=lambda x: x[1], reverse=True)
    
    def _calculate_similarity(
        self,
        ad: DBAd,
        other_ad: DBAd,
        ad_photo_hashes: List[str],
        text_embeddings: np.ndarray
    ) -> float:
        """Вычисляет общую схожесть объявлений"""
        # Получаем хэши фотографий второго объявления
        other_photo_hashes = [photo.hash for photo in other_ad.photos if photo.hash]
        
        # Схожесть фото
        photo_sim = self._calculate_photo_similarity(
            ad_photo_hashes,
            other_photo_hashes
        )
        
        # Схожесть текста
        other_text_embeddings = self._get_text_embeddings(other_ad)
        text_sim = self._calculate_text_similarity(
            text_embeddings,
            other_text_embeddings
        )
        
        # Схожесть контактов
        contact_sim = self._calculate_contact_similarity(
            ad.phone_numbers,
            other_ad.phone_numbers
        )
        
        # Схожесть адресов
        address_sim = self._calculate_address_similarity(ad, other_ad)
        
        # Общая схожесть (взвешенная сумма)
        weights = {
            'photo': 0.5,  # Увеличиваем вес фото
            'text': 0.3,   # Увеличиваем вес текста
            'contact': 0.1,
            'address': 0.1
        }
        
        overall_sim = (
            photo_sim * weights['photo'] +
            text_sim * weights['text'] +
            contact_sim * weights['contact'] +
            address_sim * weights['address']
        )
        
        logger.info(f"Similarity scores for ad {ad.id} vs {other_ad.id}:")
        logger.info(f"  Photo: {photo_sim:.2f}")
        logger.info(f"  Text: {text_sim:.2f}")
        logger.info(f"  Contact: {contact_sim:.2f}")
        logger.info(f"  Address: {address_sim:.2f}")
        logger.info(f"  Overall: {overall_sim:.2f}")
        
        return overall_sim
    
    def _calculate_photo_similarity(
        self,
        hashes1: List[str],
        hashes2: List[str]
    ) -> float:
        """Вычисляет схожесть фотографий"""
        if not hashes1 or not hashes2:
            return 0.0
            
        # Считаем количество совпадающих хэшей
        matches = len(set(hashes1) & set(hashes2))
        total = len(set(hashes1) | set(hashes2))
        
        # Если есть хотя бы одно совпадение, считаем это значимым
        if matches > 0:
            return matches / total
            
        return 0.0
    
    def _calculate_text_similarity(
        self,
        emb1: np.ndarray,
        emb2: np.ndarray
    ) -> float:
        """Вычисляет схожесть текста"""
        if emb1 is None or emb2 is None:
            return 0.0
            
        # Косинусное сходство
        return float(np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2)))
    
    def _calculate_contact_similarity(
        self,
        phones1: List[str],
        phones2: List[str]
    ) -> float:
        """Вычисляет схожесть контактов"""
        if not phones1 or not phones2:
            return 0.0
            
        # Нормализуем номера телефонов
        def normalize_phone(phone: str) -> str:
            return ''.join(filter(str.isdigit, phone))
            
        phones1 = [normalize_phone(p) for p in phones1]
        phones2 = [normalize_phone(p) for p in phones2]
        
        # Считаем совпадения
        matches = len(set(phones1) & set(phones2))
        total = len(set(phones1) | set(phones2))
        
        return matches / total if total > 0 else 0.0
    
    def _calculate_address_similarity(
        self,
        ad: DBAd,
        other_ad: DBAd
    ) -> float:
        """Вычисляет схожесть адресов"""
        if not ad.location or not other_ad.location:
            return 0.0
            
        # Сравниваем компоненты адреса
        components1 = [
            ad.location.city,
            ad.location.district,
            ad.location.address
        ]
        components2 = [
            other_ad.location.city,
            other_ad.location.district,
            other_ad.location.address
        ]
        
        # Считаем совпадения
        matches = sum(1 for c1, c2 in zip(components1, components2) if c1 and c2 and c1 == c2)
        total = sum(1 for c1, c2 in zip(components1, components2) if c1 or c2)
        
        return matches / total if total > 0 else 0.0
    
    def _handle_duplicate(
        self,
        ad: DBAd,
        unique_ad: DBAd,
        similarity: float
    ):
        """Обрабатывает найденный дубликат"""
        # Получаем хэши фотографий из связанных фотографий
        ad_photo_hashes = [photo.hash for photo in ad.photos if photo.hash]
        unique_ad_photo_hashes = [photo.hash for photo in unique_ad.photos if photo.hash]
        
        # Создаем запись о дубликате
        duplicate = DBAdDuplicate(
            unique_ad_id=unique_ad.id,
            original_ad_id=ad.id,
            photo_similarity=self._calculate_photo_similarity(
                ad_photo_hashes,
                unique_ad_photo_hashes
            ),
            text_similarity=self._calculate_text_similarity(
                self._get_text_embeddings(ad),
                self._get_text_embeddings(unique_ad)
            ),
            contact_similarity=self._calculate_contact_similarity(
                ad.phone_numbers,
                unique_ad.phone_numbers
            ),
            address_similarity=self._calculate_address_similarity(ad, unique_ad),
            overall_similarity=similarity
        )
        
        self.db.add(duplicate)
        
        # Отмечаем объявление как дубликат
        ad.is_duplicate = True
        ad.duplicate_info = duplicate
        
        # Обновляем счетчик дубликатов
        unique_ad.duplicates_count = getattr(unique_ad, 'duplicates_count', 0) + 1
        
        # Обновляем уникальное объявление, если есть новые данные
        self._update_unique_ad(unique_ad, ad)
    
    def _create_unique_ad(
        self,
        ad: DBAd,
        ad_photo_hashes: List[str],
        text_embeddings: np.ndarray
    ):
        """Создает новое уникальное объявление"""
        # Создаем уникальное объявление
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
            repair=ad.repair,
            furniture=ad.furniture,
            heating=ad.heating,
            hot_water=ad.hot_water,
            gas=ad.gas,
            ceiling_height=ad.ceiling_height,
            location_id=ad.location_id,
            is_vip=ad.is_vip,
            is_realtor=ad.is_realtor,
            realtor_score=ad.realtor_score,
            attributes=ad.attributes,
            text_embeddings=text_embeddings.tolist(),
            confidence_score=1.0
        )
        
        self.db.add(unique_ad)
        self.db.flush()  # Чтобы получить id
        
        # Копируем фотографии
        for photo in ad.photos:
            unique_photo = DBUniquePhoto(
                url=photo.url,
                hash=photo.hash,
                unique_ad_id=unique_ad.id
            )
            self.db.add(unique_photo)
            
        # Оригинальное объявление не является дубликатом (оно является основой для уникального)
        ad.is_duplicate = False
        # ad.duplicate_info не устанавливается здесь, так как это не дубликат
    
    def _update_unique_ad(self, unique_ad: DBUniqueAd, ad: DBAd):
        """Обновляет уникальное объявление новыми данными"""
        # Обновляем уникальное объявление новыми данными
        # Логика приоритезации данных: предпочтение отдается более полным или определенным данным.

        # Заголовок: выбираем более длинный заголовок
        if ad.title and (not unique_ad.title or len(ad.title) > len(unique_ad.title)):
            unique_ad.title = ad.title

        # Описание: выбираем более длинное описание
        if ad.description and (not unique_ad.description or len(ad.description) > len(unique_ad.description)):
            unique_ad.description = ad.description

        # Цена: приоритет отдается существующей цене, но обновляем, если новая цена присутствует, а текущая отсутствует
        if ad.price is not None and unique_ad.price is None:
            unique_ad.price = ad.price
            unique_ad.price_original = ad.price_original
            unique_ad.currency = ad.currency

        # Номера телефонов: объединяем, удаляя дубликаты
        if ad.phone_numbers:
            if unique_ad.phone_numbers:
                unique_ad.phone_numbers = list(set(unique_ad.phone_numbers + ad.phone_numbers))
            else:
                unique_ad.phone_numbers = ad.phone_numbers

        # Площадь: обновляем, если новое значение есть, а текущего нет
        if ad.area_sqm is not None and unique_ad.area_sqm is None:
            unique_ad.area_sqm = ad.area_sqm

        # Комнаты: обновляем, если новое значение есть, а текущего нет
        if ad.rooms is not None and unique_ad.rooms is None:
            unique_ad.rooms = ad.rooms

        # Этаж и всего этажей: обновляем, если новые значения есть, а текущих нет
        if ad.floor is not None and unique_ad.floor is None:
            unique_ad.floor = ad.floor
        if ad.total_floors is not None and unique_ad.total_floors is None:
            unique_ad.total_floors = ad.total_floors

        # Серия, тип здания, состояние, ремонт, мебель, отопление, горячая вода, газ:
        # Обновляем, если ad имеет значение, а unique_ad - нет
        fields_to_update_if_none = [
            'series', 'building_type', 'condition', 'repair', 'furniture',
            'heating', 'hot_water', 'gas'
        ]
        for field in fields_to_update_if_none:
            ad_value = getattr(ad, field)
            unique_ad_value = getattr(unique_ad, field)
            if ad_value and not unique_ad_value:
                setattr(unique_ad, field, ad_value)

        # Высота потолка: обновляем, если новое значение есть, а текущего нет
        if ad.ceiling_height is not None and unique_ad.ceiling_height is None:
            unique_ad.ceiling_height = ad.ceiling_height

        # VIP-статус и риэлторская информация: приоритет отдается True или более высоким показателям
        if ad.is_vip and not unique_ad.is_vip:
            unique_ad.is_vip = True
        if ad.is_realtor and not unique_ad.is_realtor:
            unique_ad.is_realtor = True
        if ad.realtor_score is not None and (unique_ad.realtor_score is None or ad.realtor_score > unique_ad.realtor_score):
            unique_ad.realtor_score = ad.realtor_score

        # Атрибуты: объединяем словари
        if ad.attributes:
            if unique_ad.attributes:
                unique_ad.attributes.update(ad.attributes)
            else:
                unique_ad.attributes = ad.attributes

        # Местоположение: объединяем, предпочитая более конкретные данные
        if ad.location:
            if not unique_ad.location:
                unique_ad.location = ad.location
            else:
                # Обновляем компоненты адреса, если ad предоставляет более конкретные данные
                if ad.location.city and not unique_ad.location.city:
                    unique_ad.location.city = ad.location.city
                if ad.location.district and not unique_ad.location.district:
                    unique_ad.location.district = ad.location.district
                if ad.location.address and (not unique_ad.location.address or len(ad.location.address) > len(unique_ad.location.address)):
                    unique_ad.location.address = ad.location.address
        
        # Обновляем фотографии: добавляем новые, если их хешей еще нет
        existing_hashes = {photo.hash for photo in unique_ad.photos if photo.hash}
        for photo in ad.photos:
            if photo.hash and photo.hash not in existing_hashes:
                unique_photo = DBUniquePhoto(
                    url=photo.url,
                    hash=photo.hash,
                    unique_ad_id=unique_ad.id
                )
                self.db.add(unique_photo) 