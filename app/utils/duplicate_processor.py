from typing import List, Dict, Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import numpy as np
from sentence_transformers import SentenceTransformer
import logging
from sqlalchemy import and_, or_, func
from app.db_models import DBAd, DBUniqueAd, DBAdDuplicate, DBUniquePhoto

logger = logging.getLogger(__name__)

_text_model = None

def get_text_model():
    """Возвращает кэшированную модель для эмбеддингов"""
    global _text_model
    if _text_model is None:
        logger.info("Loading SentenceTransformer model...")
        _text_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        logger.info("SentenceTransformer model loaded successfully")
    return _text_model

class DuplicateProcessor:
    def __init__(self, db: Session, realtor_threshold: int = 5):
        self.db = db
        self.text_model = get_text_model()
        self.realtor_threshold = realtor_threshold
        
    def process_new_ads(self, batch_size: int = 100):
        """Обрабатывает новые объявления на предмет дубликатов"""
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
        else:
            logger.info("Creating new unique ad")
            self._create_unique_ad(ad, ad_photo_hashes, text_embeddings)
        ad.is_processed = True
        ad.processed_at = datetime.utcnow()
    
    def _get_text_embeddings(self, ad: DBAd) -> np.ndarray:
        """Получает эмбеддинги текста объявления"""
        text = f"{ad.title} {ad.description}"
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
    
    def _calculate_similarity_with_unique(
        self,
        ad: DBAd,
        unique_ad: DBUniqueAd,
        ad_photo_hashes: List[str],
        text_embeddings: np.ndarray
    ) -> float:
        """
        Вычисляет схожесть объявления с уникальным объявлением
        """
        unique_photo_hashes = [photo.hash for photo in unique_ad.photos if photo.hash]
        photo_sim = self._calculate_photo_similarity(ad_photo_hashes, unique_photo_hashes)

        if unique_ad.text_embeddings:
            unique_text_embeddings = np.array(unique_ad.text_embeddings)
            text_sim = self._calculate_text_similarity(text_embeddings, unique_text_embeddings)
        else:
            unique_text_embeddings = self._get_text_embeddings_from_unique(unique_ad)
            text_sim = self._calculate_text_similarity(text_embeddings, unique_text_embeddings)

        address_sim = self._calculate_address_similarity_with_unique(ad, unique_ad)

        if not ad_photo_hashes and not unique_photo_hashes:
            similarity_threshold = 0.95
            address_match = False
            if ad.location_id and unique_ad.location_id and ad.location and unique_ad.location:
                if (ad.location.city and unique_ad.location.city and ad.location.city == unique_ad.location.city):
                    if (ad.location.address and unique_ad.location.address and ad.location.address == unique_ad.location.address):
                        address_match = True
                    elif not ad.location.address and not unique_ad.location.address:
                        address_match = True
            area_match = (ad.area_sqm and unique_ad.area_sqm and abs(ad.area_sqm - unique_ad.area_sqm) < 0.1) or (not ad.area_sqm and not unique_ad.area_sqm)
            floor_match = (ad.floor and unique_ad.floor and ad.floor == unique_ad.floor) or (not ad.floor and not unique_ad.floor)
            if not address_match and not area_match and not floor_match:
                return 0.0, similarity_threshold
            weights = {
                'photo': 0.0,
                'text': 1.0,
                'address': 0.0
            }
        elif not ad_photo_hashes and not unique_photo_hashes:
            weights = {
                'photo': 0.0,
                'text': 0.8,
                'address': 0.2
            }
            similarity_threshold = 0.9
        elif not ad.location_id or not unique_ad.location_id:
            weights = {
                'photo': 0.5,
                'text': 0.5,
                'address': 0.0
            }
            similarity_threshold = 0.95
        else:
            weights = {
                'photo': 0.5,
                'text': 0.3,
                'address': 0.2
            }
            similarity_threshold = 0.95

        overall_sim = (
            photo_sim * weights['photo'] +
            text_sim * weights['text'] +
            address_sim * weights['address']
        )

        logger.info(f"Similarity scores for ad {ad.id} vs unique ad {unique_ad.id}:")
        logger.info(f"  Photo: {photo_sim:.2f}")
        logger.info(f"  Text: {text_sim:.2f}")
        logger.info(f"  Address: {address_sim:.2f}")
        logger.info(f"  Overall: {overall_sim:.2f}")

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
    
    def _calculate_text_similarity(
        self,
        emb1: np.ndarray,
        emb2: np.ndarray
    ) -> float:
        """Вычисляет схожесть текста"""
        if emb1 is None or emb2 is None:
            return 0.0
            
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
    
    def _handle_duplicate(
        self,
        ad: DBAd,
        unique_ad: DBUniqueAd,
        similarity: float
    ):
        """Обрабатывает найденный дубликат"""
        ad_photo_hashes = [photo.hash for photo in ad.photos if photo.hash]
        unique_ad_photo_hashes = [photo.hash for photo in unique_ad.photos if photo.hash]
        
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
    ):
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
            confidence_score=1.0,
            duplicates_count=0,
            base_ad_id=ad.id
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
        if ad.rooms is not None and unique_ad.rooms is None:
            unique_ad.rooms = ad.rooms
        if ad.floor is not None and unique_ad.floor is None:
            unique_ad.floor = ad.floor
        if ad.total_floors is not None and unique_ad.total_floors is None:
            unique_ad.total_floors = ad.total_floors
        fields_to_update_if_none = [
            'series', 'building_type', 'condition', 'repair', 'furniture',
            'heating', 'hot_water', 'gas'
        ]
        for field in fields_to_update_if_none:
            ad_value = getattr(ad, field)
            unique_ad_value = getattr(unique_ad, field)
            if ad_value and not unique_ad_value:
                setattr(unique_ad, field, ad_value)
        if ad.ceiling_height is not None and unique_ad.ceiling_height is None:
            unique_ad.ceiling_height = ad.ceiling_height
        if ad.is_vip and not unique_ad.is_vip:
            unique_ad.is_vip = True
        if ad.is_realtor and not unique_ad.is_realtor:
            unique_ad.is_realtor = True
        if ad.realtor_score is not None and (unique_ad.realtor_score is None or ad.realtor_score > unique_ad.realtor_score):
            unique_ad.realtor_score = ad.realtor_score
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
        """Обнаруживает риэлторов на основе количества уникальных объявлений"""
        self.db.query(DBUniqueAd).update({DBUniqueAd.is_realtor: False, DBUniqueAd.realtor_score: None})
        self.db.commit()
        phone_groups = self.db.query(
            func.jsonb_array_elements_text(DBAd.phone_numbers).label("phone_number"),
            func.count(DBAd.id).label("ad_count")
        ) \
            .filter(DBAd.phone_numbers.isnot(None)) \
            .group_by(func.jsonb_array_elements_text(DBAd.phone_numbers)) \
            .having(func.count(DBAd.id) > self.realtor_threshold) \
            .all()

        realtor_phone_numbers = {pg.phone_number for pg in phone_groups}

        if not realtor_phone_numbers:
            logger.info("No realtors detected based on phone number threshold.")
            return

        logger.info(f"Detected {len(realtor_phone_numbers)} potential realtor phone numbers.")
        for phone_number in realtor_phone_numbers:
            original_ads = self.db.query(DBAd).filter(
                DBAd.phone_numbers.op("@>")(f'["{phone_number}"]')
            ).all()

            for ad in original_ads:
                ad.is_realtor = True
                ad.realtor_score = 1.0
                self.db.add(ad)
        phone_conditions = []
        for phone in realtor_phone_numbers:
            phone_conditions.append(DBAd.phone_numbers.op("?")(phone))
        
        unique_ads_to_update = (
            self.db.query(DBUniqueAd)
            .join(DBAd, DBAd.unique_ad_id == DBUniqueAd.id)
            .filter(or_(*phone_conditions))
            .distinct()
            .all()
        )

        for unique_ad in unique_ads_to_update:
            unique_ad.is_realtor = True
            unique_ad.realtor_score = 1.0

        self.db.commit()
        logger.info("Realtor detection complete. Flags updated for original and unique ads.")

    def reset_realtor_flags(self):
        """Сбрасывает флаги риэлторов для всех объявлений"""
        self.db.query(DBAd).update({DBAd.is_realtor: False, DBAd.realtor_score: None})
        self.db.query(DBUniqueAd).update({DBUniqueAd.is_realtor: False, DBUniqueAd.realtor_score: None})
        self.db.commit()
        logger.info("All realtor flags reset.")

    def get_realtor_statistics(self) -> Dict[str, int]:
        """Получает статистику по риэлторам"""
        realtor_unique_ads = self.db.query(func.count(DBUniqueAd.id)).filter(DBUniqueAd.is_realtor == True).scalar()
        realtor_original_ads = self.db.query(func.count(DBAd.id)).filter(DBAd.is_realtor == True).scalar()
        total_unique_ads = self.db.query(func.count(DBUniqueAd.id)).scalar()
        total_original_ads = self.db.query(func.count(DBAd.id)).scalar()

        return {
            "realtor_unique_ads": realtor_unique_ads,
            "realtor_original_ads": realtor_original_ads,
            "total_unique_ads": total_unique_ads,
            "total_original_ads": total_original_ads
        }
    def _get_phone_statistics(self) -> Dict[str, List[int]]:
        """Получает статистику по номерам телефонов"""
        phone_stats = {}
        
        unique_ads = self.db.query(DBUniqueAd).filter(
            DBUniqueAd.phone_numbers.isnot(None)
        ).all()
        
        for unique_ad in unique_ads:
            if unique_ad.phone_numbers:
                for phone in unique_ad.phone_numbers:
                    normalized_phone = self._normalize_phone(phone)
                    if normalized_phone:
                        if normalized_phone not in phone_stats:
                            phone_stats[normalized_phone] = []
                        phone_stats[normalized_phone].append(unique_ad.id)
        for phone in phone_stats:
            phone_stats[phone] = list(set(phone_stats[phone]))
        
        return phone_stats
    
    def _get_photo_statistics(self) -> Dict[str, List[int]]:
        """Получает статистику по хэшам фотографий"""
        photo_stats = {}
        unique_photos = self.db.query(DBUniquePhoto).filter(
            DBUniquePhoto.hash.isnot(None)
        ).all()
        
        for photo in unique_photos:
            if photo.hash:
                if photo.hash not in photo_stats:
                    photo_stats[photo.hash] = []
                photo_stats[photo.hash].append(photo.unique_ad_id)
        for photo_hash in photo_stats:
            photo_stats[photo_hash] = list(set(photo_stats[photo_hash]))
        
        return photo_stats
    
    def _normalize_phone(self, phone: str) -> str:
        """Нормализует номер телефона"""
        if not phone:
            return ""
        normalized = ''.join(filter(str.isdigit, phone))
        if len(normalized) < 7:
            return ""
        if len(normalized) >= 10:
            return normalized[-10:] if len(normalized) >= 10 else normalized[-7:]
        
        return normalized
    
    def _mark_phone_as_realtor(self, phone: str, unique_ad_ids: List[int], count: int):
        """Помечает объявления с определенным номером телефона как риэлторские"""
        unique_ads = self.db.query(DBUniqueAd).filter(
            DBUniqueAd.id.in_(unique_ad_ids)
        ).all()
        
        for unique_ad in unique_ads:
            unique_ad.is_realtor = True
            unique_ad.realtor_score = max(unique_ad.realtor_score or 0, count)
            
            logger.info(f"Marked unique ad {unique_ad.id} as realtor (phone: {phone}, count: {count})")
        for unique_ad_id in unique_ad_ids:
            all_ads = self.get_all_ads_for_unique(unique_ad_id)
            for base_ad in all_ads['base_ad']:
                base_ad.is_realtor = True
                base_ad.realtor_score = max(base_ad.realtor_score or 0, count)
            for duplicate_ad in all_ads['duplicates']:
                duplicate_ad.is_realtor = True
                duplicate_ad.realtor_score = max(duplicate_ad.realtor_score or 0, count)
    
    def _mark_photo_hash_as_realtor(self, photo_hash: str, unique_ad_ids: List[int], count: int):
        """Помечает объявления с определенным хэшем фотографии как риэлторские"""
        unique_ads = self.db.query(DBUniqueAd).filter(
            DBUniqueAd.id.in_(unique_ad_ids)
        ).all()
        
        for unique_ad in unique_ads:
            unique_ad.is_realtor = True
            unique_ad.realtor_score = max(unique_ad.realtor_score or 0, count)
            
            logger.info(f"Marked unique ad {unique_ad.id} as realtor (photo hash: {photo_hash}, count: {count})")
        for unique_ad_id in unique_ad_ids:
            all_ads = self.get_all_ads_for_unique(unique_ad_id)
            for base_ad in all_ads['base_ad']:
                base_ad.is_realtor = True
                base_ad.realtor_score = max(base_ad.realtor_score or 0, count)
            for duplicate_ad in all_ads['duplicates']:
                duplicate_ad.is_realtor = True
                duplicate_ad.realtor_score = max(duplicate_ad.realtor_score or 0, count)

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

