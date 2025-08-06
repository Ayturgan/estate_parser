import logging
import re
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import numpy as np
from sentence_transformers import SentenceTransformer
import asyncio
from app.database.db_models import DBAd, DBUniqueAd, DBAdDuplicate, DBUniquePhoto
from app.services.ai_data_extractor import get_cached_gliner_model

# Импорты для CLIP модели
try:
    from transformers import CLIPProcessor, CLIPModel
    import torch
    CLIP_AVAILABLE = True
except ImportError:
    CLIP_AVAILABLE = False
    logging.warning("CLIP модель недоступна. Установите transformers и torch для полной функциональности.")

logger = logging.getLogger(__name__)

# Глобальные переменные для кэширования моделей
_clip_model = None
_clip_processor = None
_clip_loaded = False

def get_clip_model():
    """Возвращает кэшированную CLIP модель"""
    global _clip_model, _clip_processor, _clip_loaded
    
    if not CLIP_AVAILABLE:
        return None, None
    
    if not _clip_loaded:
        try:
            logger.info("Загружаем CLIP модель для дедупликации...")
            _clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            _clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            _clip_loaded = True
            logger.info("CLIP модель загружена успешно")
        except Exception as e:
            logger.warning(f"Не удалось загрузить CLIP модель: {e}")
            _clip_model = None
            _clip_processor = None
    
    return _clip_model, _clip_processor

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
        logger.info("Loading improved SentenceTransformer model...")
        from sentence_transformers import SentenceTransformer
        try:
            _text_model = SentenceTransformer("BAAI/bge-m3")
            logger.info("BGE-M3 model loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load BGE-M3 model: {e}")
            try:
                _text_model = SentenceTransformer("BAAI/bge-large-zh-v1.5")
                logger.info("BGE-large-zh-v1.5 model loaded successfully")
            except Exception as e2:
                logger.warning(f"Failed to load BGE-large-zh-v1.5 model: {e2}")
                _text_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
                logger.info("Fallback to paraphrase-multilingual-MiniLM-L12-v2 model")
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
        
        # Инициализация CLIP модели (используем кэшированную)
        # self.clip_model, self.clip_processor = get_clip_model()  # Отключаем CLIP
        self.clip_model, self.clip_processor = None, None
        
        # Конфигурация для сбалансированной дедупликации с правильными весами
        self.config = {
            'semantic_top_k': 10,         # Кандидаты для анализа
            'semantic_threshold': 0.7,    # Порог семантики
            'weights': {
                'characteristics': 0.55,  # Основные характеристики (площадь, комнаты, этаж)
                'perceptual_photos': 0.3, # Перцептивные хеши фотографий
                'clip_photos': 0.0,       # CLIP эмбеддинги фотографий (отключено)
                'text': 0.1,              # Текстовое описание - умеренное увеличение
                'address': 0.05,          # Адрес (минимальный вес)
            },
            'similarity_threshold': 0.8,  # Общий порог для дубликата
            'photo_similarity_threshold': 0.7,  # Порог схожести фотографий
            'characteristics_similarity_threshold': 0.8,  # Порог схожести характеристик
            'area_tolerance_percent': 5,  # Допуск по площади в процентах (±5%)
            'floor_tolerance_abs': 1,     # Допуск по этажу (±1 этаж)
            'photo_early_stop_threshold': 0.8,  # Порог для ранней остановки поиска совпадений
            'photo_required_threshold': 0.6,  # МИНИМАЛЬНЫЙ порог для обязательного совпадения фотографий
        }
    
    def process_new_ads_batch(self, batch_size: int = 1000) -> int:
        """Обрабатывает батч необработанных объявлений"""
        unprocessed_ads = self.db.query(DBAd).filter(
            and_(
                DBAd.is_processed == False,
                DBAd.is_duplicate == False
            )
        ).limit(batch_size).all()
        
        total_ads = len(unprocessed_ads)
        processed_count = 0
        
        if total_ads > 0:
            logger.info(f"Starting batch processing of {total_ads} ads")
        
        for i, ad in enumerate(unprocessed_ads):
            try:
                self.process_ad(ad)
                processed_count += 1
                if processed_count % 10 == 0 or processed_count == total_ads:
                    progress = int((processed_count / total_ads) * 100)
                    logger.info(f"Processed {processed_count}/{total_ads} ads ({progress}%)")
            except Exception as e:
                logger.error(f"Error processing ad {ad.id}: {e}")
                ad.is_processed = True
                ad.processed_at = datetime.utcnow()
                processed_count += 1
        
        if total_ads > 0:
            logger.info(f"Completed batch processing: {processed_count}/{total_ads} ads")
        
        return processed_count
    
    def process_ad(self, ad: DBAd):
        """Обрабатывает одно объявление"""
        logger.info(f"Processing ad {ad.id} ({ad.title})")
        
        # Шаг 1: Создаем унифицированный профиль для нового объявления
        ad_characteristics = self._get_unified_characteristics(ad)
        
        ad_photo_hashes = [photo.perceptual_hashes for photo in ad.photos 
                          if photo.perceptual_hashes and isinstance(photo.perceptual_hashes, dict)]
        text_embeddings = self._get_text_embeddings(ad, ad_characteristics)
        
        # Шаг 2: Ищем похожие объявления
        similar_unique_ads = self._find_similar_unique_ads(ad, ad_characteristics, ad_photo_hashes, text_embeddings)
        
        if similar_unique_ads:
            unique_ad, similarity = similar_unique_ads[0]
            logger.info(f"Found duplicate with similarity {similarity:.2f}")
            self._handle_duplicate(ad, unique_ad, similarity)
        else:
            logger.info("Creating new unique ad")
            self._create_unique_ad(ad, ad_photo_hashes, text_embeddings)
            
        ad.is_processed = True
        ad.processed_at = datetime.utcnow()
    
    def _get_unified_characteristics(self, ad_object: DBAd or DBUniqueAd) -> Dict:
        """
        Создает унифицированный профиль характеристик, извлекая данные из полей и текста.
        Приоритет у данных из полей БД.
        """
        text = f"{ad_object.title or ''} {ad_object.description or ''}".lower()
        
        # Функция для извлечения числа из текста
        def extract_float(pattern, text):
            match = re.search(pattern, text)
            if match:
                try:
                    # Удаляем все, кроме цифр и точки/запятой, затем заменяем запятую на точку
                    val_str = re.sub(r'[^\d.,]', '', match.group(1)).replace(',', '.')
                    return float(val_str)
                except (ValueError, IndexError):
                    return None
            return None

        def extract_int(pattern, text):
            val = extract_float(pattern, text)
            return int(val) if val is not None else None

        # Извлекаем данные, отдавая приоритет полям БД
        characteristics = {
            'area_sqm': ad_object.area_sqm or extract_float(r'(\d+[.,]?\d*)\s*(?:м2|кв\. ?м|квадрат)', text),
            'rooms': ad_object.rooms or extract_int(r'(\d+)\s*-?\s*(?:комн|комнат|к\.)', text),
            'floor': ad_object.floor or extract_int(r'этаж\s*[:\-]?\s*(\d+)', text),
            'total_floors': ad_object.total_floors or extract_int(r'(\d+)\s*этажн|из\s*(\d+)', text),
            'land_area_sotka': ad_object.land_area_sotka or extract_float(r'(\d+[.,]?\d*)\s*(?:сот|соток|сотка)', text),
            'property_type': getattr(ad_object, 'property_type', None),
            'listing_type': getattr(ad_object, 'listing_type', None),
            'attributes': getattr(ad_object, 'attributes', {}),  # Добавляем атрибуты для дедупликации
        }
        return characteristics

    def _get_text_embeddings(self, ad: DBAd, characteristics: Dict) -> np.ndarray:
        """Создает эмбеддинги, обогащая текст извлеченными характеристиками."""
        if self.text_model is None:
            logger.warning("Text model not available, returning empty embedding")
            return np.array([])
            
        text_parts = [
            ad.title.strip() if ad.title else "",
            ad.description.strip() if ad.description else ""
        ]
        
        # Добавляем только извлеченные и подтвержденные характеристики
        char_text = []
        if characteristics.get('rooms') is not None: char_text.append(f"{characteristics['rooms']} комн")
        if characteristics.get('area_sqm') is not None: char_text.append(f"{characteristics['area_sqm']} кв.м")
        if characteristics.get('floor') is not None: char_text.append(f"этаж {characteristics['floor']}")
        
        if char_text:
            text_parts.append(" ".join(char_text))
        
        # Фильтруем None значения и пустые строки
        filtered_parts = [part for part in text_parts if part is not None and part.strip()]
        full_text = ' '.join(filtered_parts)
        full_text = ' '.join(full_text.split())
        
        if not full_text.strip():
            logger.warning("Empty text for embedding, returning empty array")
            return np.array([])
            
        try:
            return self.text_model.encode(full_text)
        except Exception as e:
            logger.error(f"Error encoding text: {e}")
            return np.array([])
    
    def _find_similar_unique_ads(
        self,
        ad: DBAd,
        ad_characteristics: Dict,
        ad_photo_hashes: List[Dict[str, str]],
        text_embeddings: np.ndarray
    ) -> List[Tuple[DBUniqueAd, float]]:
        
        # Шаг 1: Предварительная фильтрация по полям БД (быстрая)
        base_query = self.db.query(DBUniqueAd)
        if ad.location_id:
            base_query = base_query.filter(DBUniqueAd.location_id == ad.location_id)
        # Убираем строгую фильтрацию по комнатам - сравниваем со всеми кандидатами
        
        candidate_ads = base_query.all()
        logger.info(f"Found {len(candidate_ads)} candidates after initial DB filtering.")
        if not candidate_ads:
            return []

        # Шаг 2: Семантический поиск для отбора лучших кандидатов
        semantic_candidates = self._find_semantic_candidates(
            candidate_ads, text_embeddings, top_k=self.config['semantic_top_k']
        )
        logger.info(f"Found {len(semantic_candidates)} semantic candidates.")
        
        # Шаг 3: Детальный анализ с гибридной проверкой
        similar_ads = []
        for unique_ad, semantic_sim in semantic_candidates:
            # Создаем унифицированный профиль для кандидата
            unique_ad_characteristics = self._get_unified_characteristics(unique_ad)
            
            # НОВЫЙ ЭТАП: Критическая проверка фактов. Если они не совпадают - пропускаем.
            if not self._check_critical_match(ad_characteristics, unique_ad_characteristics):
                logger.warning(f"Critical characteristics mismatch for ad {ad.id} vs unique {unique_ad.id}. Skipping.")
                continue
            
            # Если прошли критическую проверку, считаем детальную схожесть
            characteristics_sim = self._calculate_property_characteristics_similarity(
                ad_characteristics, unique_ad_characteristics
            )
            
            # Получаем перцептивные хеши для unique_ad
            unique_ad_photo_hashes = [photo.perceptual_hashes for photo in unique_ad.photos if photo.perceptual_hashes]
            
            # Перцептивные хеши фотографий
            perceptual_photo_sim = self._calculate_photo_similarity(ad_photo_hashes, unique_ad_photo_hashes)
            
            # Получаем CLIP эмбеддинги для обоих объявлений (отключено)
            # ad_clip_embeddings = [photo.clip_embedding for photo in ad.photos if photo.clip_embedding]
            # unique_ad_clip_embeddings = [photo.clip_embedding for photo in unique_ad.photos if photo.clip_embedding]
            
            # CLIP эмбеддинги фотографий (отключено)
            clip_photo_sim = 0.0
            # if self.clip_model and ad_clip_embeddings and unique_ad_clip_embeddings:
            #     clip_photo_sim = self._calculate_clip_embedding_similarity(
            #         ad_clip_embeddings, unique_ad_clip_embeddings
            #     )
            
            text_sim = self._calculate_text_similarity(
                text_embeddings,
                np.array(unique_ad.text_embeddings) if unique_ad.text_embeddings else np.array([])
            )
            address_sim = self._calculate_address_similarity_with_unique(ad, unique_ad)
            
            weights = self.config['weights']
            overall_sim = (
                characteristics_sim * weights['characteristics'] + 
                perceptual_photo_sim * weights['perceptual_photos'] + 
                clip_photo_sim * weights['clip_photos'] + 
                text_sim * weights['text'] + 
                address_sim * weights['address']
            )
            
            logger.info(f"Detailed analysis for ad {ad.id} vs unique {unique_ad.id}: "
                       f"Characteristics: {characteristics_sim:.2f}, "
                       f"Perceptual Photos: {perceptual_photo_sim:.2f}, "
                       f"CLIP Photos: {clip_photo_sim:.2f}, "
                       f"Text: {text_sim:.2f}, Address: {address_sim:.2f}, "
                       f"Overall: {overall_sim:.2f}")
            
            # НОВАЯ ЛОГИКА: ОБЯЗАТЕЛЬНОЕ условие - хотя бы одно совпадение фотографий
            photo_sim_combined = perceptual_photo_sim  # Только перцептивные хеши
            
            logger.info(f"🔍 Проверка фото для ad {ad.id} vs unique {unique_ad.id}: "
                       f"photo_sim={photo_sim_combined:.3f}, required_threshold={self.config['photo_required_threshold']}")
            
            # Проверяем обязательное условие: должно быть хотя бы одно совпадение фотографий
            if photo_sim_combined >= self.config['photo_required_threshold']:  # Есть хотя бы одно совпадение фотографий
                if (characteristics_sim >= self.config['characteristics_similarity_threshold'] and 
                    photo_sim_combined >= self.config['photo_similarity_threshold'] and 
                    overall_sim > self.config['similarity_threshold']):
                    similar_ads.append((unique_ad, overall_sim))
                    logger.info(f"✅ Найден дубликат с обязательным совпадением фото: {photo_sim_combined:.3f}")
                else:
                    logger.info(f"❌ Не прошли дополнительные проверки: characteristics={characteristics_sim:.3f}, "
                              f"photo_threshold={self.config['photo_similarity_threshold']}, overall={overall_sim:.3f}")
            else:
                # Нет совпадений фотографий - НЕ дубликат
                logger.info(f"❌ Нет совпадений фотографий для ad {ad.id} vs unique {unique_ad.id} - НЕ дубликат")
        
        return sorted(similar_ads, key=lambda x: x[1], reverse=True)
    
    def _find_semantic_candidates(
        self,
        candidate_ads: List[DBUniqueAd],
        text_embeddings: np.ndarray,
        top_k: int
    ) -> List[Tuple[DBUniqueAd, float]]:
        """Находит топ-K семантически похожих кандидатов"""
        semantic_scores = []
        for unique_ad in candidate_ads:
            if unique_ad.text_embeddings is not None and len(unique_ad.text_embeddings) > 0:
                unique_text_embeddings = np.array(unique_ad.text_embeddings)
                semantic_sim = self._calculate_text_similarity(text_embeddings, unique_text_embeddings)
                if semantic_sim >= self.config['semantic_threshold']:
                    semantic_scores.append((unique_ad, semantic_sim))
        
        semantic_scores.sort(key=lambda x: x[1], reverse=True)
        return semantic_scores[:top_k]

    def _check_critical_match(self, char1: Dict, char2: Dict) -> bool:
        """Проверяет совпадение критически важных характеристик из унифицированных профилей."""
        # 1. Площадь - более мягкая проверка
        area1, area2 = char1.get('area_sqm'), char2.get('area_sqm')
        if area1 is not None and area2 is not None:
            try:
                area1_float = float(area1)
                area2_float = float(area2)
                tolerance = area1_float * (self.config['area_tolerance_percent'] / 100.0)
                if abs(area1_float - area2_float) > tolerance:
                    logger.debug(f"Critical mismatch: area {area1_float} vs {area2_float}")
                    return False # Площадь не совпадает
            except (TypeError, ValueError) as e:
                logger.warning(f"Error comparing areas {area1} vs {area2}: {e}")
                # Если не можем сравнить площади, продолжаем
        # Убираем строгую проверку - если у одного есть площадь, а у другого нет, все равно сравниваем

        # 2. Комнаты - более мягкая проверка
        rooms1, rooms2 = char1.get('rooms'), char2.get('rooms')
        if rooms1 is not None and rooms2 is not None:
            if rooms1 != rooms2:
                logger.debug(f"Critical mismatch: rooms {rooms1} vs {rooms2}")
                return False # Комнаты не совпадают
        # Убираем строгую проверку - если у одного есть комнаты, а у другого нет, все равно сравниваем

        # 3. Этаж - более мягкая проверка
        floor1, floor2 = char1.get('floor'), char2.get('floor')
        if floor1 is not None and floor2 is not None:
            if abs(floor1 - floor2) > self.config['floor_tolerance_abs']:
                logger.debug(f"Critical mismatch: floor {floor1} vs {floor2}")
                return False # Этажи не совпадают
        # Убираем строгую проверку - если у одного есть этаж, а у другого нет, все равно сравниваем
            
        # 4. Тип недвижимости (если оба определены и не совпадают)
        type1, type2 = char1.get('property_type'), char2.get('property_type')
        if type1 is not None and type2 is not None and type1 != type2:
            logger.debug(f"Critical mismatch: property_type {type1} vs {type2}")
            return False

        # 5. ДОПОЛНИТЕЛЬНЫЕ ПРОВЕРКИ ДЛЯ ГАРАЖЕЙ
        if type1 == 'Гараж' or type2 == 'Гараж':
            # Для гаражей проверяем building_type (материал) и condition
            attrs1, attrs2 = char1.get('attributes', {}), char2.get('attributes', {})
            
            # Проверяем building_type (материал)
            building_type1 = attrs1.get('building_type') or attrs1.get('material')
            building_type2 = attrs2.get('building_type') or attrs2.get('material')
            if building_type1 and building_type2 and building_type1 != building_type2:
                logger.debug(f"Critical mismatch for garage: building_type {building_type1} vs {building_type2}")
                return False
            
            # Проверяем condition (состояние)
            condition1 = attrs1.get('condition')
            condition2 = attrs2.get('condition')
            if condition1 and condition2 and condition1 != condition2:
                logger.debug(f"Critical mismatch for garage: condition {condition1} vs {condition2}")
                return False

        # 6. ОБЩИЕ ПРОВЕРКИ ДЛЯ ВСЕХ ТИПОВ НЕДВИЖИМОСТИ
        attrs1, attrs2 = char1.get('attributes', {}), char2.get('attributes', {})
        
        # Проверяем building_type (если есть в атрибутах)
        building_type1 = attrs1.get('building_type')
        building_type2 = attrs2.get('building_type')
        if building_type1 and building_type2 and building_type1 != building_type2:
            logger.debug(f"Critical mismatch: building_type {building_type1} vs {building_type2}")
            return False
        
        # Проверяем condition (если есть в атрибутах)
        condition1 = attrs1.get('condition')
        condition2 = attrs2.get('condition')
        if condition1 and condition2 and condition1 != condition2:
            logger.debug(f"Critical mismatch: condition {condition1} vs {condition2}")
            return False

        return True # Все критические проверки пройдены
    
    def _calculate_photo_similarity(self, hashes1: List[Dict[str, str]], hashes2: List[Dict[str, str]]) -> float:
        """Вычисляет схожесть на основе перцептивных хешей - НОВАЯ ЛОГИКА: хотя бы одно совпадение"""
        if not hashes1 or not hashes2: 
            logger.debug("Пустые списки хешей для сравнения")
            return 0.0
        
        # НОВАЯ ЛОГИКА: Ищем хотя бы одно совпадение среди всех фотографий
        best_similarity = 0.0
        found_match = False
        
        for hash_dict1 in hashes1:
            for hash_dict2 in hashes2:
                # Проверяем тип и валидность хешей
                if not isinstance(hash_dict1, dict) or not isinstance(hash_dict2, dict):
                    logger.debug(f"Пропускаем невалидные хеши: {type(hash_dict1)} vs {type(hash_dict2)}")
                    continue
                    
                # Сравниваем только точные хеши (pHash и dHash более надежны)
                for hash_type in ['pHash', 'dHash']:
                    if hash_type in hash_dict1 and hash_type in hash_dict2:
                        hash1 = hash_dict1[hash_type]
                        hash2 = hash_dict2[hash_type]
                        
                        # Проверяем валидность хешей
                        if hash1 and hash2 and isinstance(hash1, str) and isinstance(hash2, str):
                            try:
                                # Вычисляем расстояние Хэмминга
                                distance = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
                                max_distance = len(hash1)
                                similarity = 1.0 - (distance / max_distance)
                                
                                logger.info(f"🔍 {hash_type}: hash1={hash1[:8]}..., hash2={hash2[:8]}..., "
                                          f"distance={distance}, similarity={similarity:.3f}")
                                
                                # НОВАЯ ЛОГИКА: Запоминаем лучшее совпадение
                                if similarity > best_similarity:
                                    best_similarity = similarity
                                    found_match = True
                                    logger.info(f"🎯 Новое лучшее совпадение {hash_type}: {similarity:.3f}")
                                    
                                # Если нашли очень хорошее совпадение, можно остановиться
                                if similarity >= self.config['photo_early_stop_threshold']:
                                    logger.info(f"🏆 Найдено отличное совпадение {hash_type}: {similarity:.3f}")
                                    return similarity
                                    
                            except Exception as e:
                                logger.warning(f"Ошибка вычисления расстояния Хэмминга для {hash_type}: {e}")
                                continue
                        else:
                            logger.debug(f"Пропускаем невалидные хеши {hash_type}: {hash1} vs {hash2}")
        
        # Возвращаем лучшее найденное совпадение
        result = best_similarity if found_match else 0.0
        logger.info(f"📸 Схожесть фото: {result:.3f} (найдено совпадений: {found_match})")
        return result
    
    def _calculate_clip_embedding_similarity(self, embeddings1: List[np.ndarray], embeddings2: List[np.ndarray]) -> float:
        """
        Вычисляет схожесть на основе CLIP эмбеддингов
        
        Args:
            embeddings1: CLIP эмбеддинги первого объявления
            embeddings2: CLIP эмбеддинги второго объявления
            
        Returns:
            Средняя схожесть по всем парам изображений
        """
        if not embeddings1 or not embeddings2:
            logger.debug("Пустые списки эмбеддингов для сравнения")
            return 0.0
        
        if self.clip_model is None:
            logger.warning("CLIP модель недоступна для вычисления схожести")
            return 0.0
        
        total_similarity = 0.0
        total_comparisons = 0
        
        for emb1 in embeddings1:
            for emb2 in embeddings2:
                # Проверяем валидность эмбеддингов
                if emb1 is not None and emb2 is not None:
                    try:
                        # Проверяем размерности
                        if len(emb1) == 0 or len(emb2) == 0:
                            logger.debug("Пропускаем пустые эмбеддинги")
                            continue
                        
                        # Конвертируем в numpy массивы если нужно
                        if not isinstance(emb1, np.ndarray):
                            emb1 = np.array(emb1, dtype=np.float32)
                        if not isinstance(emb2, np.ndarray):
                            emb2 = np.array(emb2, dtype=np.float32)
                        
                        # Проверяем, что это векторы
                        if emb1.ndim != 1 or emb2.ndim != 1:
                            logger.warning(f"Неверная размерность эмбеддингов: {emb1.shape} vs {emb2.shape}")
                            continue
                        
                        # Нормализуем эмбеддинги
                        norm1 = np.linalg.norm(emb1)
                        norm2 = np.linalg.norm(emb2)
                        
                        if norm1 == 0 or norm2 == 0:
                            logger.debug("Пропускаем нулевые эмбеддинги")
                            continue
                        
                        emb1_norm = emb1 / norm1
                        emb2_norm = emb2 / norm2
                        
                        # Вычисляем косинусное сходство
                        similarity = np.dot(emb1_norm, emb2_norm)
                        total_similarity += similarity
                        total_comparisons += 1
                    except Exception as e:
                        logger.warning(f"Ошибка вычисления CLIP схожести: {e}")
                        continue
                else:
                    logger.debug("Пропускаем None эмбеддинги")
        
        result = total_similarity / total_comparisons if total_comparisons > 0 else 0.0
        logger.debug(f"Схожесть по CLIP эмбеддингам: {result:.3f} (сравнений: {total_comparisons})")
        return result
    
    def _calculate_text_similarity(self, emb1, emb2) -> float:
        if emb1 is None or emb2 is None or len(emb1) == 0 or len(emb2) == 0: return 0.0
        if not isinstance(emb1, np.ndarray): emb1 = np.array(emb1, dtype=np.float32)
        if not isinstance(emb2, np.ndarray): emb2 = np.array(emb2, dtype=np.float32)
        if emb1.shape != emb2.shape:
            min_len = min(len(emb1), len(emb2))
            emb1, emb2 = emb1[:min_len], emb2[:min_len]
        norm1, norm2 = np.linalg.norm(emb1), np.linalg.norm(emb2)
        if norm1 == 0 or norm2 == 0: return 0.0
        return float(np.dot(emb1, emb2) / (norm1 * norm2))
    
    def _calculate_contact_similarity(self, phones1: List[str], phones2: List[str]) -> float:
        if not phones1 or not phones2: return 0.0
        normalize = lambda p: ''.join(filter(str.isdigit, p))
        s1, s2 = set(map(normalize, phones1)), set(map(normalize, phones2))
        return len(s1 & s2) / len(s1 | s2) if s1 | s2 else 0.0

    def _calculate_address_similarity_with_unique(self, ad: DBAd, unique_ad: DBUniqueAd) -> float:
        if not ad.location or not unique_ad.location: return 0.0
        c1 = [ad.location.city, ad.location.district, ad.location.address]
        c2 = [unique_ad.location.city, unique_ad.location.district, unique_ad.location.address]
        matches = sum(1 for v1, v2 in zip(c1, c2) if v1 and v2 and v1 == v2)
        total = sum(1 for v1, v2 in zip(c1, c2) if v1 or v2) # Учитываем только заполненные поля
        return matches / total if total > 0 else 0.0
    
    def _calculate_property_characteristics_similarity(self, char1: Dict, char2: Dict) -> float:
        """Сравнивает два унифицированных профиля характеристик."""
        scores = []
        weights_sum = 0.0
        
        def compare(key, weight, tolerance=0):
            nonlocal weights_sum
            val1, val2 = char1.get(key), char2.get(key)
            
            if val1 is not None and val2 is not None:
                weights_sum += weight
                try:
                    is_match = abs(float(val1) - float(val2)) <= tolerance
                except (TypeError, ValueError):
                    is_match = str(val1) == str(val2)
                scores.append(1.0 * weight if is_match else 0.0)
            # Если поля нет в обоих, не учитываем в весе и не добавляем в scores
            # Если только в одном, то это уже отловлено в _check_critical_match

        # Основные характеристики (поля БД)
        area1_val = char1.get('area_sqm')
        if area1_val is not None:
            try:
                area1_float = float(area1_val)
                tolerance = area1_float * (self.config['area_tolerance_percent'] / 100.0)
                compare('area_sqm', 1.0, tolerance)
            except (TypeError, ValueError):
                compare('area_sqm', 1.0, 0)  # Если не можем вычислить tolerance, используем 0
        else:
            compare('area_sqm', 1.0, 0)  # Если нет площади, используем tolerance 0
        compare('rooms', 1.0)
        compare('floor', 0.8, self.config['floor_tolerance_abs'])
        compare('total_floors', 0.7)
        compare('property_type', 0.9)
        compare('land_area_sotka', 1.0)  # Площадь участка в сотках - критически важно для участков
        
        # Дополнительные характеристики из атрибутов
        attributes_score = self._calculate_attributes_similarity(char1.get('attributes', {}), char2.get('attributes', {}))
        if attributes_score > 0:
            weights_sum += 0.5  # Вес для атрибутов
            scores.append(attributes_score * 0.5)
        
        return sum(scores) / weights_sum if weights_sum > 0 else 0.0

    def _calculate_attributes_similarity(self, attrs1: Dict, attrs2: Dict) -> float:
        """Сравнивает атрибуты из JSONB поля для более точной дедупликации"""
        if not attrs1 or not attrs2:
            return 0.0
        
        # Важные атрибуты для сравнения (с весами)
        important_attrs = {
            'utilities': 1.0,           # Коммуникации
            'heating': 0.8,             # Отопление
            'condition': 0.8,           # Ремонт
            'furniture': 0.7,           # Мебель
            'building_type': 0.9,       # Тип здания
            'offer_type': 0.6,          # Тип предложения
            'purpose': 0.8,             # Назначение (для участков)
            'material': 0.7,            # Материал (для гаражей)
            'height': 0.6,              # Высота (для гаражей)
            'capacity': 0.7,            # Вместимость (для квартир)
            'amenities': 0.6,           # Удобства (для квартир)
            'housing_class': 0.5,       # Класс жилья (для квартир)
            'additional_features': 0.5,  # Дополнительные особенности
            'subletting': 0.4,          # Подселение
            'pets': 0.3,                # Животные
            'parking': 0.5,             # Паркинг
            'documents': 0.6,           # Документы
        }
        total_score = 0.0
        total_weight = 0.0
        for attr_name, weight in important_attrs.items():
            val1 = attrs1.get(attr_name)
            val2 = attrs2.get(attr_name)
            
            if val1 is not None and val2 is not None:
                # Сравниваем значения атрибутов
                if isinstance(val1, str) and isinstance(val2, str):
                    val1_lower = val1.lower()
                    val2_lower = val2.lower()

                    if val1_lower == val2_lower:
                        score = 1.0
                    elif val1_lower in val2_lower or val2_lower in val1_lower:
                        score = 0.7
                    else:
                        # Проверяем общие слова
                        words1 = set(val1_lower.split())
                        words2 = set(val2_lower.split())
                        if words1 and words2:
                            common_words = words1.intersection(words2)
                            score = len(common_words) / max(len(words1), len(words2))
                        else:
                            score = 0.0
                else:
                    # Для нестроковых значений точное совпадение
                    score = 1.0 if val1 == val2 else 0.0
                
                total_score += score * weight
                total_weight += weight
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    def _handle_duplicate(
        self,
        ad: DBAd,
        unique_ad: DBUniqueAd,
        similarity: float
    ):
        """Обрабатывает найденный дубликат БЕЗ ОБНОВЛЕНИЯ УНИКАЛЬНОГО ОБЪЯВЛЕНИЯ"""
        ad_photo_hashes = [photo.perceptual_hashes for photo in ad.photos 
                          if photo.perceptual_hashes and isinstance(photo.perceptual_hashes, dict)]
        unique_ad_photo_hashes = [photo.perceptual_hashes for photo in unique_ad.photos 
                                 if photo.perceptual_hashes and isinstance(photo.perceptual_hashes, dict)]
        
        # Получаем унифицированные характеристики для детального логирования
        ad_characteristics = self._get_unified_characteristics(ad)
        unique_ad_characteristics = self._get_unified_characteristics(unique_ad)

        characteristics_sim = self._calculate_property_characteristics_similarity(
            ad_characteristics, unique_ad_characteristics
        )
        
        # Вычисляем все схожести для записи в БД
        perceptual_photo_sim = self._calculate_photo_similarity(ad_photo_hashes, unique_ad_photo_hashes)
        
        # Получаем CLIP эмбеддинги для обоих объявлений (отключено)
        # ad_clip_embeddings = [photo.clip_embedding for photo in ad.photos 
        #                      if photo.clip_embedding and isinstance(photo.clip_embedding, list)]
        # unique_ad_clip_embeddings = [photo.clip_embedding for photo in unique_ad.photos 
        #                             if photo.clip_embedding and isinstance(photo.clip_embedding, list)]
        
        # CLIP эмбеддинги фотографий (отключено)
        clip_photo_sim = 0.0
        # if self.clip_model and ad_clip_embeddings and unique_ad_clip_embeddings:
        #     clip_photo_sim = self._calculate_clip_embedding_similarity(
        #         ad_clip_embeddings, unique_ad_clip_embeddings
        #     )
        
        # Общая схожесть фотографий (только перцептивные хеши)
        photo_sim_combined = perceptual_photo_sim
        
        text_sim = self._calculate_text_similarity(
            self._get_text_embeddings(ad, ad_characteristics),
            np.array(unique_ad.text_embeddings) if unique_ad.text_embeddings else np.array([])
        )
        contact_sim = self._calculate_contact_similarity(ad.phone_numbers, unique_ad.phone_numbers)
        address_sim = self._calculate_address_similarity_with_unique(ad, unique_ad)
        
        # Конвертируем numpy типы в обычные float для PostgreSQL
        duplicate = DBAdDuplicate(
            unique_ad_id=unique_ad.id,
            original_ad_id=ad.id,
            photo_similarity=float(photo_sim_combined),
            text_similarity=float(text_sim),
            contact_similarity=float(contact_sim),
            address_similarity=float(address_sim),
            characteristics_similarity=float(characteristics_sim),
            overall_similarity=float(similarity)
        )
        self.db.add(duplicate)
        
        ad.is_duplicate = True
        ad.duplicate_info = duplicate
        ad.unique_ad_id = unique_ad.id
        unique_ad.duplicates_count = (unique_ad.duplicates_count or 0) + 1
        
        logger.info(f"Ad {ad.id} marked as duplicate of unique ad {unique_ad.id}. "
                   f"Similarities: Perceptual={perceptual_photo_sim:.2f}, CLIP={clip_photo_sim:.2f}, "
                   f"Text={text_sim:.2f}, Characteristics={characteristics_sim:.2f}, "
                   f"Overall={similarity:.2f}. Duplicates count: {unique_ad.duplicates_count}")
        if event_emitter:
            try:
                # Используем правильный асинхронный вызов
                import asyncio
                from app.services.event_emitter import EventType
                # Создаем задачу в текущем event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(event_emitter.emit(EventType.DUPLICATE_DETECTED, {'ad_id': ad.id, 'unique_ad_id': unique_ad.id}))
                else:
                    # Если loop не запущен, просто логируем
                    logger.info(f"Event loop not running, skipping event emission")
            except Exception as e:
                logger.warning(f"Failed to emit event: {e}")
    
    def _create_unique_ad(
        self,
        ad: DBAd,
        ad_photo_hashes: List[Dict[str, str]],
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
            land_area_sotka=ad.land_area_sotka,  # Добавляем площадь участка
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
            unique_photo = DBUniquePhoto(url=photo.url, perceptual_hashes=photo.perceptual_hashes, clip_embedding=photo.clip_embedding, unique_ad_id=unique_ad.id)
            self.db.add(unique_photo)
            
        ad.is_duplicate = False
        ad.unique_ad_id = unique_ad.id
        logger.info(f"Created new unique ad {unique_ad.id} from base ad {ad.id}.")
        if event_emitter:
            try:
                # Используем правильный асинхронный вызов
                import asyncio
                from app.services.event_emitter import EventType
                # Создаем задачу в текущем event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(event_emitter.emit(EventType.NEW_AD_CREATED, {'unique_ad_id': unique_ad.id, 'base_ad_id': ad.id}))
                else:
                    # Если loop не запущен, просто логируем
                    logger.info(f"Event loop not running, skipping event emission")
            except Exception as e:
                logger.warning(f"Failed to emit event: {e}")
        
        return unique_ad

    def get_base_ad_for_unique(self, unique_ad_id: int) -> Optional[DBAd]:
        unique_ad = self.db.query(DBUniqueAd).filter(DBUniqueAd.id == unique_ad_id).first()
        if not unique_ad: return None
        if hasattr(unique_ad, 'base_ad_id') and unique_ad.base_ad_id:
            return self.db.query(DBAd).filter(DBAd.id == unique_ad.base_ad_id).first()
        return self.db.query(DBAd).filter(DBAd.unique_ad_id == unique_ad.id, DBAd.is_duplicate == False).first()

    def get_all_ads_for_unique(self, unique_ad_id: int) -> Dict[str, List[DBAd]]:
        base_ad = self.get_base_ad_for_unique(unique_ad_id)
        duplicates = self.db.query(DBAdDuplicate).filter(DBAdDuplicate.unique_ad_id == unique_ad_id).all()
        duplicate_ads = [self.db.query(DBAd).get(dup.original_ad_id) for dup in duplicates if self.db.query(DBAd).get(dup.original_ad_id)]
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



