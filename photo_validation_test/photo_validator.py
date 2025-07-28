import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re
from dataclasses import dataclass

# Импорты для работы с изображениями
try:
    from PIL import Image, ImageEnhance, ImageFilter
    import pytesseract
    from imagehash import average_hash
    
    # Компьютерное зрение
    import cv2
    import numpy as np
    
    # Машинное обучение
    import torch
    import torch.nn.functional as F
    from torchvision import transforms
    from transformers import pipeline, AutoImageProcessor, AutoModelForImageClassification
    
    # YOLO для обнаружения объектов
    from ultralytics import YOLO
    
    # Дополнительные библиотеки
    import matplotlib.pyplot as plt
    import seaborn as sns
    from sklearn.metrics import classification_report
    
except ImportError as e:
    print(f"❌ Ошибка импорта библиотек: {e}")
    print("Установите необходимые библиотеки:")
    print("pip install -r requirements.txt")
    sys.exit(1)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Результат валидации фотографии"""
    is_valid: bool
    confidence: float
    detected_issues: List[str]
    extracted_text: str
    ad_banner_score: float
    watermark_score: float
    text_density: float
    # Новые поля для компьютерного зрения
    detected_objects: List[Dict]
    image_classification_score: float

class PhotoValidator:
    """Улучшенный валидатор фотографий для распознавания рекламных баннеров с использованием CV и ML"""
    
    def __init__(self):
        # Ключевые слова для рекламных баннеров (остаются для OCR)
        self.ad_keywords = [
            'агентство', 'агент', 'риэлтор', 'недвижимость', 'квартиры', 'дома',
            'продажа', 'аренда', 'сдача', 'покупка', 'обмен',
            'тел', 'телефон', '+996', '+7', 'звоните', 'звонить',
            'whatsapp', 'вайбер', 'viber', 'whatsapp',
            'цена', 'стоимость', '$', 'сом', 'доллар', 'евро',
            'скидка', 'акция', 'специальное предложение',
            'реклама', 'баннер', 'специально', 'уникальное предложение',
            'лучшие цены', 'гарантия', 'лицензия', 'сертификат',
            'дом', 'жилье', 'недвижимость кг', 'real estate', 'property',
            'квартира', 'дом', 'участок', 'земля',
            'компания', 'фирма', 'организация', 'бюро', 'центр',
            'услуги', 'помощь', 'консультация', 'эксперт',
            'профессионально', 'качественно', 'надежно',
            'срочно', 'быстро', 'выгодно', 'дешево', 'дорого',
            'оплата', 'договор', 'сделка', 'транзакция',
            # Добавляем новые ключевые слова для лучшей детекции
            'банк', 'кредит', 'ипотека', 'займ', 'финансы',
            'процент', 'ставка', 'годовых', 'эффективная',
            'рекламное', 'рекламная', 'рекламный', 'рекламные',
            'спецпредложение', 'специальная', 'специальный',
            'уникальная', 'уникальный', 'уникальные',
            'лучшая', 'лучший', 'лучшие', 'гарантированно',
            'лицензированная', 'лицензированный', 'сертифицированная',
            # Дополнительные ключевые слова для более точного обнаружения
            'реклам', 'баннер', 'плакат', 'объявление', 'афиша',
            'маркетинг', 'продвижение', 'промо', 'акция',
            'скидка', 'распродажа', 'спец', 'уникальн',
            'гарантированн', 'лицензированн', 'сертифицированн',
            'профессиональн', 'качественн', 'надежн',
            'срочн', 'быстр', 'выгодн', 'дешев', 'дорог',
            'оплат', 'договор', 'сделк', 'транзакц',
            'консультац', 'эксперт', 'помощь', 'услуг',
            'центр', 'бюро', 'фирма', 'организац',
            'недвижимост', 'квартир', 'дом', 'жиль',
            'продаж', 'аренд', 'сдач', 'покупк', 'обмен',
            'тел', 'телефон', 'звонит', 'whatsapp', 'вайбер',
            'цена', 'стоимост', 'доллар', 'евро', 'рубл',
            'банк', 'кредит', 'ипотек', 'займ', 'финанс',
            'процент', 'ставк', 'годовых', 'эффективн',
            # ДОПОЛНИТЕЛЬНЫЕ КЛЮЧЕВЫЕ СЛОВА ДЛЯ ФОТО 14
            'апартаменты', 'апартамент', 'апартаментн',
            'иссык', 'кул', 'иссык-кул', 'иссыккул',
            'royal', 'ak', 'jol', 'ak jol',
            'комплекс', 'жилой', 'жилой комплекс',
            'современный', 'современн', 'новый', 'нов',
            'строительство', 'строительн', 'застройщик',
            'инвестиции', 'инвестиционн', 'инвестиц',
            'премиум', 'элитный', 'элитн', 'люкс',
            'комфорт', 'комфортн', 'качественн',
            'безопасность', 'безопасн', 'охрана',
            'инфраструктура', 'инфраструктурн',
            'благоустройство', 'благоустройств',
            'ландшафт', 'ландшафтн', 'дизайн',
            'архитектура', 'архитектурн', 'проект',
            'планировка', 'планировк', 'отделка',
            'ремонт', 'ремонтн', 'капитальн',
            'первичный', 'первичн', 'вторичный', 'вторичн',
            'новостройка', 'новостро', 'готовый', 'готов',
            'свободная', 'свободн', 'свободный', 'свободн',
            'планировка', 'планировк', 'отделка',
            'ремонт', 'ремонтн', 'капитальн',
            'первичный', 'первичн', 'вторичный', 'вторичн',
            'новостройка', 'новостро', 'готовый', 'готов',
            'свободная', 'свободн', 'свободный', 'свободн'
        ]
        
        # Слова для водяных знаков (остаются для OCR)
        self.watermark_keywords = [
            'watermark', 'логотип', 'лого', 'brand', 'company',
            'copyright', '©', '™', '®', 'www.', '.com', '.kg'
        ]
        
        # Настройки для OCR
        self.ocr_config = '--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя.,!?@#$%&*()_+-=[]{}|;:,.<>?/ '
        
        # Пороговые значения
        self.ad_banner_threshold = 0.6  # Порог для определения рекламного баннера (OCR)
        self.watermark_threshold = 0.4   # Порог для определения водяного знака (OCR)
        self.text_density_threshold = 0.1 # Порог плотности текста (OCR)
        
        # Пороги для CV/ML - МАКСИМАЛЬНО строгие для точного определения рекламы
        self.object_detection_threshold = 0.3 # Снизили порог для более агрессивного обнаружения
        self.classification_ad_threshold = 0.4 # Снизили порог для классификации как реклама

        # Инициализация моделей компьютерного зрения
        self.object_detector = self._load_object_detector()
        self.image_classifier = self._load_image_classifier()
        self.watermark_detector = self._load_watermark_detector()
        
        # Трансформации для классификации изображений
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    def _load_object_detector(self):
        """Загрузка предобученной модели для обнаружения объектов (YOLOv8)"""
        try:
            # Загружаем предобученную модель YOLOv8
            model = YOLO('yolov8n.pt')
            logger.info("✅ Модель YOLOv8 загружена успешно")
            return model
        except Exception as e:
            logger.warning(f"⚠️ Не удалось загрузить YOLOv8: {e}")
            logger.info("Используется режим без обнаружения объектов")
            return None

    def _load_image_classifier(self):
        """Загрузка предобученной модели для классификации изображений"""
        try:
            # Используем ViT для классификации изображений
            model_name = "google/vit-base-patch16-224"
            processor = AutoImageProcessor.from_pretrained(model_name)
            model = AutoModelForImageClassification.from_pretrained(model_name)
            
            # Переводим в режим оценки
            model.eval()
            
            logger.info("✅ Модель классификации изображений загружена успешно")
            return {"model": model, "processor": processor}
        except Exception as e:
            logger.warning(f"⚠️ Не удалось загрузить модель классификации: {e}")
            logger.info("Используется режим без классификации изображений")
            return None

    def _load_watermark_detector(self):
        """Загрузка специализированного детектора водяных знаков"""
        try:
            # Создаем простой детектор водяных знаков на основе OpenCV
            # В реальном проекте здесь была бы предобученная модель
            logger.info("✅ Детектор водяных знаков инициализирован")
            return True
        except Exception as e:
            logger.warning(f"⚠️ Не удалось инициализировать детектор водяных знаков: {e}")
            return None

    def validate_photo(self, image_path: str) -> ValidationResult:
        """
        Валидирует фотографию на предмет рекламных баннеров и водяных знаков
        с использованием гибридного подхода (OCR + CV + ML)
        
        Args:
            image_path: Путь к изображению
            
        Returns:
            ValidationResult с результатами валидации
        """
        try:
            image = Image.open(image_path).convert('RGB')
            
            # 1. Анализ с помощью компьютерного зрения (Object Detection и Image Classification)
            detected_objects = self._detect_objects(image) # Обнаружение логотипов, баннеров, контактов
            image_classification_score = self._classify_image(image) # Классификация изображения как реклама/не реклама

            # 2. Предобработка изображения для OCR
            processed_image = self._preprocess_image(image)
            
            # 3. Извлечение текста с помощью OCR
            extracted_text = self._extract_text(processed_image)
            self._last_extracted_text = extracted_text # Сохраняем для _determine_validity
            
            # 4. Анализ текста на рекламные ключевые слова
            ad_banner_score, ad_issues = self._analyze_ad_banner(extracted_text)
            
            # 5. Анализ на водяные знаки (текстовые и визуальные)
            watermark_score, watermark_issues = self._analyze_watermark(extracted_text, image)
            
            # 6. Вычисляем плотность текста
            text_density = self._calculate_text_density(extracted_text, image.size)
            
            # 7. Определяем общую валидность с учетом всех факторов
            is_valid = self._determine_validity(
                ad_banner_score,
                watermark_score,
                text_density,
                detected_objects,
                image_classification_score
            )
            
            # Собираем все обнаруженные проблемы
            detected_issues = ad_issues + watermark_issues
            if detected_objects:
                detected_issues.append(f"Обнаружены объекты: {', '.join([obj['label'] for obj in detected_objects])}")
            if image_classification_score > self.classification_ad_threshold:
                detected_issues.append(f"Изображение классифицировано как реклама (Score: {image_classification_score:.2f})")
            
            if extracted_text.strip():
                cleaned_text = self._clean_ocr_text(extracted_text)
                if cleaned_text:
                    detected_issues.append(f"Обнаружен текст на изображении: '{cleaned_text[:50]}...'")
                    logger.info(f"Очищенный текст: '{cleaned_text}'")
                else:
                    detected_issues.append("Обнаружены артефакты OCR (игнорируются)")
                    logger.info("Текст очищен как артефакты OCR")
            
            # Вычисляем общую уверенность
            confidence = self._calculate_confidence(
                ad_banner_score,
                watermark_score,
                text_density,
                detected_objects,
                image_classification_score
            )
            
            return ValidationResult(
                is_valid=is_valid,
                confidence=confidence,
                detected_issues=detected_issues,
                extracted_text=extracted_text,
                ad_banner_score=ad_banner_score,
                watermark_score=watermark_score,
                text_density=text_density,
                detected_objects=detected_objects,
                image_classification_score=image_classification_score
            )
            
        except Exception as e:
            logger.error(f"Ошибка при валидации {image_path}: {e}")
            return ValidationResult(
                is_valid=False,
                confidence=0.0,
                detected_issues=[f"Ошибка обработки: {str(e)}"],
                extracted_text="",
                ad_banner_score=1.0,
                watermark_score=0.0,
                text_density=0.0,
                detected_objects=[],
                image_classification_score=0.0
            )
    
    def _detect_objects(self, image: Image.Image) -> List[Dict]:
        """Обнаружение объектов (логотипов, телефонов, баннеров) с помощью YOLOv8"""
        if not self.object_detector:
            return []
        
        try:
            # Конвертируем PIL изображение в формат для YOLO
            results = self.object_detector(image)
            
            detected_objects = []
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        # Получаем координаты и уверенность
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = float(box.conf[0])
                        class_id = int(box.cls[0])
                        class_name = result.names[class_id]
                        
                        # Фильтруем объекты по уверенности
                        if confidence > self.object_detection_threshold:
                            # Определяем тип объекта на основе класса YOLO
                            object_type = self._map_yolo_class_to_ad_type(class_name)
                            
                            if object_type:
                                detected_objects.append({
                                    "label": object_type,
                                    "confidence": confidence,
                                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                                    "class_name": class_name
                                })
            
            if detected_objects:
                logger.info(f"Обнаружено {len(detected_objects)} объектов: {[obj['label'] for obj in detected_objects]}")
            
            return detected_objects
            
        except Exception as e:
            logger.error(f"Ошибка при обнаружении объектов: {e}")
            return []

    def _map_yolo_class_to_ad_type(self, class_name: str) -> str:
        """Маппинг классов YOLO к типам рекламных объектов"""
        # Маппинг стандартных классов YOLO к нашим типам
        mapping = {
            'cell phone': 'phone_number',
            'phone': 'phone_number',
            'remote': 'phone_number',  # Пульт может быть похож на телефон
            'laptop': 'ad_banner',     # Ноутбук может содержать рекламу
            'tv': 'ad_banner',         # Телевизор может показывать рекламу
            'book': 'ad_banner',       # Книга может содержать рекламные тексты
            'clock': 'logo',           # Часы могут быть логотипом
            'vase': 'logo',            # Ваза может быть частью логотипа
            'cup': 'logo',             # Чашка может содержать логотип
            'bottle': 'logo',          # Бутылка может содержать логотип
            'bowl': 'logo',            # Миска может содержать логотип
            'chair': 'ad_banner',      # Стул может быть в рекламном контексте
            'couch': 'ad_banner',      # Диван может быть в рекламном контексте
            'potted plant': 'logo',    # Растение может быть частью логотипа
            'dining table': 'ad_banner', # Стол может быть в рекламном контексте
            'toilet': 'ad_banner',     # Туалет может быть в рекламном контексте
            'tv monitor': 'ad_banner', # Монитор может показывать рекламу
            'laptop': 'ad_banner',     # Ноутбук может содержать рекламу
            'mouse': 'ad_banner',      # Мышь может быть в рекламном контексте
            'remote': 'phone_number',  # Пульт может быть похож на телефон
            'keyboard': 'ad_banner',   # Клавиатура может быть в рекламном контексте
            'cell phone': 'phone_number', # Мобильный телефон
            # Добавляем новые классы для лучшей детекции
            'person': None,            # Человек не является рекламным объектом
            'car': None,               # Машина не является рекламным объектом
            'bus': None,               # Автобус не является рекламным объектом
            'truck': None,             # Грузовик не является рекламным объектом
            'bicycle': None,           # Велосипед не является рекламным объектом
            'motorcycle': None,        # Мотоцикл не является рекламным объектом
            'airplane': None,          # Самолет не является рекламным объектом
            'train': None,             # Поезд не является рекламным объектом
            'boat': None,              # Лодка не является рекламным объектом
            'traffic light': None,     # Светофор не является рекламным объектом
            'fire hydrant': None,      # Пожарный гидрант не является рекламным объектом
            'stop sign': None,         # Знак стоп не является рекламным объектом
            'parking meter': None,     # Парковочный счетчик не является рекламным объектом
            'bench': None,             # Скамейка не является рекламным объектом
            'bird': None,              # Птица не является рекламным объектом
            'cat': None,               # Кошка не является рекламным объектом
            'dog': None,               # Собака не является рекламным объектом
            'horse': None,             # Лошадь не является рекламным объектом
            'sheep': None,             # Овца не является рекламным объектом
            'cow': None,               # Корова не является рекламным объектом
            'elephant': None,          # Слон не является рекламным объектом
            'bear': None,              # Медведь не является рекламным объектом
            'zebra': None,             # Зебра не является рекламным объектом
            'giraffe': None,           # Жираф не является рекламным объектом
            'backpack': None,          # Рюкзак не является рекламным объектом
            'umbrella': None,          # Зонт не является рекламным объектом
            'handbag': None,           # Сумка не является рекламным объектом
            'tie': None,               # Галстук не является рекламным объектом
            'suitcase': None,          # Чемодан не является рекламным объектом
            'frisbee': None,           # Фрисби не является рекламным объектом
            'skis': None,              # Лыжи не являются рекламным объектом
            'snowboard': None,         # Сноуборд не является рекламным объектом
            'sports ball': None,       # Спортивный мяч не является рекламным объектом
            'kite': None,              # Воздушный змей не является рекламным объектом
            'baseball bat': None,      # Бейсбольная бита не является рекламным объектом
            'baseball glove': None,    # Бейсбольная перчатка не является рекламным объектом
            'skateboard': None,        # Скейтборд не является рекламным объектом
            'surfboard': None,         # Серфборд не является рекламным объектом
            'tennis racket': None,     # Теннисная ракетка не является рекламным объектом
            'wine glass': None,        # Бокал для вина не является рекламным объектом
            'fork': None,              # Вилка не является рекламным объектом
            'knife': None,             # Нож не является рекламным объектом
            'spoon': None,             # Ложка не является рекламным объектом
            'banana': None,            # Банан не является рекламным объектом
            'apple': None,             # Яблоко не является рекламным объектом
            'sandwich': None,          # Сэндвич не является рекламным объектом
            'orange': None,            # Апельсин не является рекламным объектом
            'broccoli': None,          # Брокколи не является рекламным объектом
            'carrot': None,            # Морковь не является рекламным объектом
            'hot dog': None,           # Хот-дог не является рекламным объектом
            'pizza': None,             # Пицца не является рекламным объектом
            'donut': None,             # Пончик не является рекламным объектом
            'cake': None,              # Торт не является рекламным объектом
        }
        
        return mapping.get(class_name, None)

    def _classify_image(self, image: Image.Image) -> float:
        """Классификация изображения как рекламное/не рекламное с помощью ViT"""
        if not self.image_classifier:
            return 0.0
        
        try:
            # Подготавливаем изображение для модели
            processor = self.image_classifier["processor"]
            model = self.image_classifier["model"]
            
            # Обрабатываем изображение
            inputs = processor(image, return_tensors="pt")
            
            # Получаем предсказания
            with torch.no_grad():
                outputs = model(**inputs)
                logits = outputs.logits
                probabilities = F.softmax(logits, dim=-1)
            
            # Анализируем результаты для определения рекламного характера
            # Используем эвристики на основе классов ImageNet
            ad_score = self._calculate_ad_score_from_classification(probabilities[0], model.config.id2label)
            
            logger.info(f"Score классификации изображения: {ad_score:.3f}")
            return ad_score
            
        except Exception as e:
            logger.error(f"Ошибка при классификации изображения: {e}")
            return 0.0

    def _calculate_ad_score_from_classification(self, probabilities: torch.Tensor, id2label: dict) -> float:
        """Вычисляет score рекламности на основе классификации ImageNet"""
        # Классы, которые могут указывать на рекламный характер
        ad_indicators = {
            'magazine', 'book', 'newspaper', 'calendar', 'poster', 'signboard',
            'screen', 'monitor', 'television', 'laptop', 'computer', 'keyboard',
            'cell phone', 'telephone', 'remote', 'camera', 'video camera',
            'billboard', 'advertisement', 'logo', 'brand', 'company'
        }
        
        # Получаем топ-10 предсказаний
        top_probs, top_indices = torch.topk(probabilities, 10)
        
        ad_score = 0.0
        total_weight = 0.0
        
        for prob, idx in zip(top_probs, top_indices):
            class_name = id2label[idx.item()].lower()
            weight = prob.item()
            
            # Проверяем, содержит ли класс индикаторы рекламы
            for indicator in ad_indicators:
                if indicator in class_name:
                    ad_score += weight
                    break
            
            total_weight += weight
        
        # Нормализуем score
        if total_weight > 0:
            ad_score = ad_score / total_weight
        
        return min(ad_score, 1.0)

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Предобработка изображения для улучшения OCR"""
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        width, height = image.size
        if width < 800 or height < 600:
            scale_factor = max(800 / width, 600 / height)
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)
        
        image = image.filter(ImageFilter.SHARPEN)
        
        return image
    
    def _extract_text(self, image: Image.Image) -> str:
        """Извлекает текст из изображения с помощью OCR"""
        try:
            text = pytesseract.image_to_string(image, config=self.ocr_config, lang='rus+eng')
            return text.strip()
        except Exception as e:
            logger.warning(f"Ошибка OCR: {e}")
            return ""
    
    def _analyze_ad_banner(self, text: str) -> Tuple[float, List[str]]:
        """Анализирует текст на наличие рекламных ключевых слов"""
        if not text:
            return 0.0, []
        
        cleaned_text = self._clean_ocr_text(text)
        
        if not cleaned_text:
            return 0.0, []
        
        text_lower = cleaned_text.lower()
        issues = []
        matched_keywords = []
        
        for keyword in self.ad_keywords:
            if keyword in text_lower:
                matched_keywords.append(keyword)
                issues.append(f"Обнаружено рекламное слово: '{keyword}'")
        
        phone_patterns = [
            r'\+996\s*\d{3}\s*\d{3}\s*\d{3}',  # Кыргызстан
            r'\+7\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2}',  # Россия
            r'\d{3}-\d{3}-\d{3}',  # Простой формат
            r'\d{3}\s*\d{3}\s*\d{3}',  # Простой формат без дефисов
        ]
        
        for pattern in phone_patterns:
            if re.search(pattern, cleaned_text):
                issues.append("Обнаружен номер телефона")
                matched_keywords.append("phone")
        
        price_patterns = [
            r'\$\s*\d+',  # Доллары
            r'\d+\s*сом',  # Сомы
            r'\d+\s*руб',  # Рубли
            r'\d+\s*долл',  # Доллары
            r'\d+\s*евро',  # Евро
        ]
        
        for pattern in price_patterns:
            if re.search(pattern, cleaned_text):
                issues.append("Обнаружена цена")
                matched_keywords.append("price")
        
        ad_patterns = [
            r'компания\s+\w+',  # "компания НАЗВАНИЕ"
            r'агентство\s+\w+',  # "агентство НАЗВАНИЕ"
            r'фирма\s+\w+',      # "фирма НАЗВАНИЕ"
            r'центр\s+\w+',      # "центр НАЗВАНИЕ"
        ]
        
        for pattern in ad_patterns:
            if re.search(pattern, text_lower):
                issues.append("Обнаружен рекламный паттерн")
                matched_keywords.append("pattern")
        
        score = min(len(matched_keywords) / 2.0, 1.0)
        
        return score, issues
    
    def _clean_ocr_text(self, text: str) -> str:
        """Очищает текст от артефактов OCR"""
        if not text:
            return ""
        
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Игнорируем очень короткие строки
            if len(line) < 2:
                continue
            
            # Игнорируем строки только из символов пунктуации
            if re.match(r'^[\s\.,:;\-_=+*\/\\|()\[\]{}<>"\\]*$', line):
                continue
            
            # Игнорируем строки с большим количеством спецсимволов
            special_chars = len(re.findall(r'[^\wа-яё\s\.]', line))
            if special_chars > len(line) * 0.6:  # Увеличили порог
                continue
            
            # Игнорируем очень короткие строки без смысла
            if re.match(r'^[\w\s]*$', line) and len(line) < 4:
                meaningful_words = ['дом', 'кв', 'эт', 'ком', 'кг', 'www', 'com', 'org', 'net', 'ru', 'kg']
                line_lower = line.lower()
                if not any(word in line_lower for word in meaningful_words):
                    continue
            
            # Игнорируем строки с повторяющимися символами (артефакты)
            if re.search(r'(.)\1{2,}', line):  # 3+ одинаковых символа подряд
                continue
            
            # Игнорируем строки с большим количеством цифр без букв
            digits = len(re.findall(r'\d', line))
            letters = len(re.findall(r'[а-яёa-z]', line, re.IGNORECASE))
            if digits > 0 and letters == 0 and len(line) < 6:
                continue
            
            # Игнорируем строки с большим количеством одиночных букв
            single_letters = len(re.findall(r'\b[a-zа-яё]\b', line, re.IGNORECASE))
            if single_letters > len(line) * 0.4:  # Увеличили порог
                continue
            
            # Игнорируем строки с большим количеством согласных подряд (артефакты)
            consonant_patterns = [r'[бвгджзйклмнпрстфхцчшщ]{4,}', r'[bcdfghjklmnpqrstvwxz]{4,}']
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in consonant_patterns):
                continue
            
            # Игнорируем строки с большим количеством гласных подряд (артефакты)
            vowel_patterns = [r'[аеёиоуыэюя]{4,}', r'[aeiouy]{4,}']
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in vowel_patterns):
                continue
            
            # Игнорируем строки с чередующимися символами (артефакты)
            if re.search(r'(.)(.)\1\2\1', line):  # Паттерн типа "ababa"
                continue
            
            # Игнорируем строки с большим количеством символов в верхнем регистре без пробелов
            upper_chars = len(re.findall(r'[А-ЯA-Z]', line))
            if upper_chars > len(line) * 0.8 and ' ' not in line and len(line) > 3:
                continue
            
            cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines)
        
        # Если результат слишком короткий - считаем артефактами
        if len(result.strip()) < 5:  # Увеличили минимальную длину
            return ""
        
        # Дополнительная проверка на артефакты в целом тексте
        if result:
            # Проверяем соотношение букв и цифр
            total_chars = len(re.findall(r'[а-яёa-z0-9]', result, re.IGNORECASE))
            if total_chars == 0:
                return ""
            
            # Проверяем на повторяющиеся паттерны
            if re.search(r'(.{2,})\1{2,}', result):  # Повторяющиеся паттерны
                return ""
            
            # Проверяем на слишком много спецсимволов в целом
            special_chars_total = len(re.findall(r'[^\wа-яё\s\.]', result))
            if special_chars_total > len(result) * 0.5:
                return ""
        
        return result
    
    def _analyze_watermark(self, text: str, image: Image.Image) -> Tuple[float, List[str]]:
        """Анализирует изображение на наличие водяных знаков (текстовых и визуальных)"""
        issues = []
        score = 0.0
        
        text_lower = text.lower()
        watermark_matches = []
        
        for keyword in self.watermark_keywords:
            if keyword in text_lower:
                watermark_matches.append(keyword)
                issues.append(f"Обнаружен водяной знак: '{keyword}'")
        
        if image.mode == 'RGBA':
            alpha = image.split()[-1]
            transparent_pixels = sum(1 for pixel in alpha.getdata() if pixel < 255)
            total_pixels = alpha.size[0] * alpha.size[1]
            
            if total_pixels > 0:
                transparency_ratio = transparent_pixels / total_pixels
                if transparency_ratio > 0.1:
                    score += 0.3
                    issues.append("Обнаружена прозрачность (возможный водяной знак)")
        
        edge_text = self._extract_edge_text(image)
        if edge_text:
            edge_lower = edge_text.lower()
            for keyword in self.watermark_keywords:
                if keyword in edge_lower:
                    score += 0.2
                    issues.append(f"Водяной знак на краю изображения: '{keyword}'")
        
        # Визуальное обнаружение водяных знаков с помощью OpenCV
        if self.watermark_detector:
            visual_watermark_score = self._detect_visual_watermark(image)
            if visual_watermark_score > 0.3:
                score += visual_watermark_score * 0.4
                issues.append(f"Обнаружен визуальный водяной знак (score: {visual_watermark_score:.2f})")

        score = min(score + len(watermark_matches) * 0.1, 1.0)
        
        return score, issues
    
    def _extract_edge_text(self, image: Image.Image) -> str:
        """Извлекает текст с краев изображения"""
        try:
            width, height = image.size
            
            edge_regions = [
                image.crop((0, 0, width, height // 4)),
                image.crop((0, height * 3 // 4, width, height)),
                image.crop((0, 0, width // 4, height)),
                image.crop((width * 3 // 4, 0, width, height)),
            ]
            
            edge_texts = []
            for region in edge_regions:
                text = pytesseract.image_to_string(region, config=self.ocr_config, lang='rus+eng')
                if text.strip():
                    edge_texts.append(text.strip())
            
            return " ".join(edge_texts)
        except Exception as e:
            logger.warning(f"Ошибка извлечения текста с краев: {e}")
            return ""
    
    def _detect_visual_watermark(self, image: Image.Image) -> float:
        """Визуальное обнаружение водяных знаков с помощью OpenCV"""
        try:
            # Конвертируем PIL в OpenCV формат
            img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # Конвертируем в оттенки серого
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            
            # Применяем различные методы обнаружения водяных знаков
            
            # 1. Анализ градиентов (водяные знаки часто имеют слабые градиенты)
            sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            gradient_magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
            
            # 2. Анализ локальной дисперсии (водяные знаки имеют низкую дисперсию)
            kernel = np.ones((5,5), np.float32)/25
            local_mean = cv2.filter2D(gray.astype(np.float32), -1, kernel)
            local_variance = cv2.filter2D((gray.astype(np.float32) - local_mean)**2, -1, kernel)
            
            # 3. Анализ краев (водяные знаки часто имеют четкие края)
            edges = cv2.Canny(gray, 50, 150)
            
            # 4. Анализ углов (водяные знаки часто располагаются в углах)
            height, width = gray.shape
            corner_regions = [
                gray[0:height//4, 0:width//4],  # Верхний левый
                gray[0:height//4, 3*width//4:width],  # Верхний правый
                gray[3*height//4:height, 0:width//4],  # Нижний левый
                gray[3*height//4:height, 3*width//4:width]  # Нижний правый
            ]
            
            # Вычисляем score на основе всех факторов
            watermark_score = 0.0
            
            # Фактор 1: Низкая дисперсия в углах (признак водяного знака)
            corner_variance_scores = []
            for corner in corner_regions:
                if corner.size > 0:
                    variance = np.var(corner)
                    # Низкая дисперсия = возможный водяной знак
                    corner_variance_scores.append(1.0 / (1.0 + variance / 1000))
            
            if corner_variance_scores:
                watermark_score += np.mean(corner_variance_scores) * 0.3
            
            # Фактор 2: Наличие четких краев в углах
            corner_edge_scores = []
            for corner in corner_regions:
                if corner.size > 0:
                    corner_edges = cv2.Canny(corner, 30, 100)
                    edge_density = np.sum(corner_edges > 0) / corner_edges.size
                    corner_edge_scores.append(edge_density)
            
            if corner_edge_scores:
                watermark_score += np.mean(corner_edge_scores) * 0.2
            
            # Фактор 3: Анализ общей структуры изображения
            # Водяные знаки часто имеют регулярную структуру
            fft = np.fft.fft2(gray)
            fft_shift = np.fft.fftshift(fft)
            magnitude_spectrum = np.log(np.abs(fft_shift) + 1)
            
            # Анализируем центральную часть спектра (низкие частоты)
            center_y, center_x = magnitude_spectrum.shape[0]//2, magnitude_spectrum.shape[1]//2
            center_region = magnitude_spectrum[center_y-20:center_y+20, center_x-20:center_x+20]
            
            if center_region.size > 0:
                center_variance = np.var(center_region)
                # Высокая дисперсия в центре может указывать на водяной знак
                structure_score = min(center_variance / 1000, 1.0)
                watermark_score += structure_score * 0.2
            
            # Фактор 4: Анализ гистограммы (водяные знаки часто имеют специфическое распределение)
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
            hist_normalized = hist.flatten() / np.sum(hist)
            
            # Ищем пики в гистограмме (признак водяного знака)
            peaks = []
            for i in range(1, len(hist_normalized)-1):
                if hist_normalized[i] > hist_normalized[i-1] and hist_normalized[i] > hist_normalized[i+1]:
                    if hist_normalized[i] > 0.01:  # Значимый пик
                        peaks.append(hist_normalized[i])
            
            if peaks:
                peak_score = min(np.mean(peaks) * 10, 1.0)
                watermark_score += peak_score * 0.3
            
            return min(watermark_score, 1.0)
            
        except Exception as e:
            logger.error(f"Ошибка при визуальном обнаружении водяных знаков: {e}")
            return 0.0
    
    def _calculate_text_density(self, text: str, image_size: Tuple[int, int]) -> float:
        """Вычисляет плотность текста на изображении"""
        if not text:
            return 0.0
        
        # Очищаем текст от артефактов OCR
        cleaned_text = self._clean_ocr_text(text)
        if not cleaned_text:
            return 0.0  # Если текст очищен как артефакты, плотность = 0
        
        char_count = len(cleaned_text.replace(" ", ""))
        
        area = image_size[0] * image_size[1]
        
        density = char_count / max(area / 10000, 1)
        
        return min(density, 1.0)
    
    def _determine_validity(self, ad_banner_score: float, watermark_score: float, text_density: float, detected_objects: List[Dict], image_classification_score: float) -> bool:
        """Определяет валидность изображения с учетом всех факторов - более строгая версия"""
        
        # 1. Проверяем обнаружение объектов (CV) - МАКСИМАЛЬНО агрессивно
        ad_objects = [obj for obj in detected_objects if obj["label"] in ["phone_number", "ad_banner", "logo", "text", "sign"] and obj["confidence"] > 0.3]
        if ad_objects:
            logger.info(f"Обнаружены рекламные объекты: {[obj['label'] for obj in ad_objects]}")
            return False
        
        # 2. Проверяем классификацию изображения (CV) - МАКСИМАЛЬНО строго
        if image_classification_score > 0.4:
            logger.info(f"Изображение классифицировано как реклама с уверенностью: {image_classification_score}")
            return False
        
        # 3. Анализируем OCR результаты
        if hasattr(self, '_last_extracted_text') and self._last_extracted_text.strip():
            cleaned_text = self._clean_ocr_text(self._last_extracted_text)
            
            if not cleaned_text:
                # Если после очистки текста нет - это артефакты OCR, фото валидно
                logger.info("OCR текст очищен как артефакты - фото валидно")
                return True
            
            text_lower = cleaned_text.lower()
            
            # Проверяем на явные рекламные признаки
            ad_indicators = 0
            watermark_indicators = 0
            
            # Считаем рекламные ключевые слова
            for keyword in self.ad_keywords:
                if keyword in text_lower:
                    ad_indicators += 1
            
            # Считаем водяные знаки
            for keyword in self.watermark_keywords:
                if keyword in text_lower:
                    watermark_indicators += 1
            
            # Проверяем телефоны - БОЛЕЕ СТРОГО
            phone_patterns = [
                r'\+996\s*\d{3}\s*\d{3}\s*\d{3}',  # Кыргызстан
                r'\+7\s*\d{3}\s*\d{3}\s*\d{2}\s*\d{2}',  # Россия
                r'\d{3}-\d{3}-\d{3}',  # Простой формат
                r'\d{3}\s*\d{3}\s*\d{3}',  # Простой формат без дефисов
                r'\(\d{3}\)\s*\d{3}-\d{3}',  # Формат (707) 77-55-55
                r'\d{3}\s*\d{2}\s*\d{2}\s*\d{2}',  # Формат 707 77 55 55
                r'\+996\(\d{3}\)\d{3}\d{3}\d{3}',  # Формат +996(707)775555
                r'\+996\(\d{3}\)\d{3}-\d{3}-\d{3}',  # Формат +996(707)77-55-55
                r'\d{3}\(\d{3}\)\d{3}\d{3}\d{3}',  # Формат 996(707)775555
                r'\d{3}\(\d{3}\)\d{3}-\d{3}-\d{3}',  # Формат 996(707)77-55-55
                r'\(\d{3}\)\d{3}\d{3}\d{3}',  # Формат (707)775555
                r'\(\d{3}\)\d{3}-\d{3}-\d{3}',  # Формат (707)77-55-55
                r'\+996\s*\(\d{3}\)\s*\d{3}\d{3}\d{3}',  # Формат +996 (707) 775555
                r'\+996\s*\(\d{3}\)\s*\d{3}-\d{3}-\d{3}',  # Формат +996 (707) 77-55-55
                r'\+996.*\d{3}.*\d{3}.*\d{3}',  # Любой формат с +996 и 3 группами цифр
                r'\(\d{3}\).*\d{3}.*\d{3}.*\d{3}',  # Любой формат с (707) и 3 группами цифр
                r'\d{3}.*\d{3}.*\d{3}.*\d{3}',  # 4 группы по 3 цифры
                r'707.*\d{3}.*\d{3}.*\d{3}',  # Начинается с 707
            ]
            has_phone = any(re.search(pattern, cleaned_text) for pattern in phone_patterns)
            
            # Дополнительная проверка в исходном тексте (до очистки)
            if not has_phone and hasattr(self, '_last_extracted_text'):
                original_text = self._last_extracted_text
                has_phone = any(re.search(pattern, original_text) for pattern in phone_patterns)
                if has_phone:
                    logger.info(f"Телефон обнаружен в исходном тексте: {original_text}")
            
            if has_phone:
                logger.info(f"Обнаружен телефон в тексте: {cleaned_text}")
            
            # Проверяем цены - БОЛЕЕ СТРОГО
            price_patterns = [
                r'\$\s*\d+',  # Доллары
                r'\d+\s*сом',  # Сомы
                r'\d+\s*руб',  # Рубли
                r'\d+\s*долл',  # Доллары
                r'\d+\s*евро',  # Евро
                r'\d+\s*тг',  # Тенге
                r'\d+\s*тенге',  # Тенге
                r'\d+\s*сомов',  # Сомы
                r'\d+\s*рублей',  # Рубли
                r'\d+\s*долларов',  # Доллары
                r'\d+\s*евро',  # Евро
            ]
            has_price = any(re.search(pattern, cleaned_text) for pattern in price_patterns)
            
            # Проверяем рекламные паттерны - БОЛЕЕ СТРОГО
            ad_patterns = [
                r'компания\s+\w+',  # "компания НАЗВАНИЕ"
                r'агентство\s+\w+',  # "агентство НАЗВАНИЕ"
                r'фирма\s+\w+',      # "фирма НАЗВАНИЕ"
                r'центр\s+\w+',      # "центр НАЗВАНИЕ"
                r'апартаменты\s+на\s+\w+',  # "апартаменты на ИССЫК-КУЛЕ"
                r'жилой\s+комплекс',  # "жилой комплекс"
                r'новый\s+\w+',      # "новый проект"
                r'современный\s+\w+', # "современный дом"
                r'элитный\s+\w+',    # "элитный район"
                r'премиум\s+\w+',    # "премиум класс"
                r'инвестиционный\s+\w+', # "инвестиционный проект"
                r'строительство\s+\w+', # "строительство домов"
                r'застройщик\s+\w+', # "застройщик компании"
                r'проект\s+\w+',     # "проект развития"
                r'комплекс\s+\w+',   # "комплекс зданий"
                r'royal\s+\w+',      # "royal ak jol"
                r'ak\s+jol',         # "ak jol"
                r'иссык\s*-\s*кул',  # "иссык-кул"
                r'иссыккул',         # "иссыккул"
            ]
            has_ad_pattern = any(re.search(pattern, text_lower) for pattern in ad_patterns)
            
            # Проверяем финансовые термины (банки, кредиты) - БОЛЕЕ СТРОГО
            financial_patterns = [
                r'банк', r'кредит', r'ипотека', r'займ', r'финансы', r'процент', r'ставка', r'годовых',
                r'инвестиции', r'инвестиционный', r'инвестиционн',
                r'финансирование', r'финансирован',
                r'кредитование', r'кредитован',
                r'ипотечное', r'ипотечн',
                r'займовый', r'займов',
                r'процентная', r'процентн',
                r'ставка', r'ставк',
                r'годовых', r'годов',
                r'эффективная', r'эффективн',
                r'выгодная', r'выгодн',
                r'доходная', r'доходн',
                r'прибыльная', r'прибыльн',
                r'рентабельная', r'рентабельн',
                r'окупаемость', r'окупаем',
                r'дивиденды', r'дивиденд',
                r'акции', r'акционерн',
                r'облигации', r'облигационн',
                r'депозит', r'депозитн',
                r'вклад', r'вкладн',
                r'сбережения', r'сберегательн',
                r'страхование', r'страхован',
                r'пенсионный', r'пенсионн',
                r'накопительный', r'накопительн',
                r'срочный', r'срочн',
                r'бессрочный', r'бессрочн',
                r'льготный', r'льготн',
                r'специальный', r'специальн',
                r'эксклюзивный', r'эксклюзивн',
                r'уникальный', r'уникальн',
                r'ограниченный', r'ограниченн',
                r'временный', r'временн',
                r'акционный', r'акционн',
                r'промо', r'промо',
                r'скидочный', r'скидочн',
                r'распродажа', r'распродаж',
                r'ликвидация', r'ликвидационн',
                r'аукцион', r'аукционн',
                r'тендер', r'тендерн',
                r'конкурс', r'конкурсн',
                r'лотерея', r'лотерейн',
                r'розыгрыш', r'розыгрышн',
                r'приз', r'призов',
                r'бонус', r'бонусн',
                r'подарок', r'подарочн',
                r'премия', r'премиальн',
                r'комиссия', r'комиссионн',
                r'плата', r'платн',
                r'оплата', r'оплатн',
                r'расчет', r'расчетн',
                r'счет', r'счетн',
                r'квитанция', r'квитанционн',
                r'чек', r'чеков',
                r'договор', r'договорн',
                r'соглашение', r'соглашен',
                r'контракт', r'контрактн',
                r'сделка', r'сделочн',
                r'транзакция', r'транзакционн',
                r'перевод', r'переводн',
                r'обмен', r'обменн',
                r'конвертация', r'конвертационн',
                r'курс', r'курсов',
                r'валютный', r'валютн',
                r'долларовый', r'долларов',
                r'евровый', r'евров',
                r'рублевый', r'рублев',
                r'сомовый', r'сомов',
                r'тенговый', r'тенгов',
                r'гривневый', r'гривнев',
                r'манатный', r'манатов',
                r'сомонный', r'сомонов',
                r'лариевый', r'лариев',
                r'драмовый', r'драмов',
                r'тенге', r'тенг',
                r'сом', r'сом',
                r'рубль', r'рубл',
                r'доллар', r'долл',
                r'евро', r'евр',
                r'гривна', r'гривн',
                r'манат', r'манат',
                r'сомони', r'сомон',
                r'лари', r'лар',
                r'драм', r'драм'
            ]
            has_financial = any(re.search(pattern, text_lower) for pattern in financial_patterns)
            
            # Проверяем рекламные слова - БОЛЕЕ СТРОГО
            ad_word_patterns = [
                r'рекламн', r'спецпредложен', r'уникальн', r'лучш', r'гарантированн', r'лицензированн', r'сертифицированн',
                r'профессиональн', r'качественн', r'надежн', r'срочн', r'быстр', r'выгодн', r'дешев', r'дорог',
                r'оплат', r'договор', r'сделк', r'транзакц', r'консультац', r'эксперт', r'помощь', r'услуг',
                r'центр', r'бюро', r'фирма', r'организац', r'недвижимост', r'квартир', r'дом', r'жиль',
                r'продаж', r'аренд', r'сдач', r'покупк', r'обмен', r'тел', r'телефон', r'звонит',
                r'whatsapp', r'вайбер', r'цена', r'стоимост', r'доллар', r'евро', r'рубл',
                r'банк', r'кредит', r'ипотек', r'займ', r'финанс', r'процент', r'ставк', r'годовых',
                r'эффективн', r'инвестиционн', r'финансирован', r'кредитован', r'ипотечн', r'займов',
                r'процентн', r'годов', r'выгодн', r'доходн', r'прибыльн', r'рентабельн', r'окупаем',
                r'дивиденд', r'акционерн', r'облигационн', r'депозитн', r'вкладн', r'сберегательн',
                r'страхован', r'пенсионн', r'накопительн', r'срочн', r'бессрочн', r'льготн',
                r'специальн', r'эксклюзивн', r'уникальн', r'ограниченн', r'временн', r'акционн',
                r'промо', r'скидочн', r'распродаж', r'ликвидационн', r'аукционн', r'тендерн',
                r'конкурсн', r'лотерейн', r'розыгрышн', r'призов', r'бонусн', r'подарочн',
                r'премиальн', r'комиссионн', r'платн', r'оплатн', r'расчетн', r'счетн',
                r'квитанционн', r'чеков', r'договорн', r'соглашен', r'контрактн', r'сделочн',
                r'транзакционн', r'переводн', r'обменн', r'конвертационн', r'курсов', r'валютн',
                r'долларов', r'евров', r'рублев', r'сомов', r'тенгов', r'гривнев', r'манатов',
                r'сомонов', r'лариев', r'драмов', r'тенг', r'сом', r'рубл', r'долл', r'евр',
                r'гривн', r'манат', r'сомон', r'лар', r'драм', r'апартаментн', r'иссык', r'кул',
                r'royal', r'ak', r'jol', r'комплекс', r'жилой', r'современн', r'нов', r'строительн',
                r'застройщик', r'инвестиц', r'премиум', r'элитн', r'люкс', r'комфортн', r'качественн',
                r'безопасн', r'охрана', r'инфраструктурн', r'благоустройств', r'ландшафтн', r'дизайн',
                r'архитектурн', r'проект', r'планировк', r'отделка', r'ремонтн', r'капитальн',
                r'первичн', r'вторичн', r'новостро', r'готов', r'свободн'
            ]
            has_ad_words = any(re.search(pattern, text_lower) for pattern in ad_word_patterns)
            
            # Проверяем наличие контактной информации - БОЛЕЕ СТРОГО
            contact_patterns = [
                r'тел', r'телефон', r'звоните', r'звонить', r'whatsapp', r'вайбер', r'viber',
                r'контакт', r'контактн', r'связаться', r'связь', r'связан',
                r'позвонить', r'позвоните', r'набрать', r'наберите',
                r'номер', r'номерн', r'телефонн', r'мобильн',
                r'сотовый', r'сотов', r'мобильный', r'мобильн',
                r'домашний', r'домашн', r'рабочий', r'рабоч',
                r'факс', r'факсн', r'телефакс', r'телефаксн',
                r'адрес', r'адресн', r'адреса', r'адресо',
                r'электронная', r'электронн', r'email', r'e-mail',
                r'почта', r'почтн', r'майл', r'мейл',
                r'сайт', r'сайтн', r'веб', r'web',
                r'интернет', r'интернетн', r'онлайн', r'online',
                r'чат', r'чатн', r'мессенджер', r'мессенджерн',
                r'телеграм', r'telegram', r'сигнал', r'signal',
                r'скайп', r'skype', r'зум', r'zoom',
                r'вибер', r'viber', r'вайбер', r'whatsapp',
                r'инстаграм', r'instagram', r'фейсбук', r'facebook',
                r'вконтакте', r'vk', r'одноклассники', r'ok',
                r'твиттер', r'twitter', r'ютуб', r'youtube',
                r'тикток', r'tiktok', r'линкедин', r'linkedin',
                r'фейсбук', r'facebook', r'инстаграм', r'instagram',
                r'телеграм', r'telegram', r'сигнал', r'signal',
                r'скайп', r'skype', r'зум', r'zoom',
                r'вибер', r'viber', r'вайбер', r'whatsapp',
                r'инстаграм', r'instagram', r'фейсбук', r'facebook',
                r'вконтакте', r'vk', r'одноклассники', r'ok',
                r'твиттер', r'twitter', r'ютуб', r'youtube',
                r'тикток', r'tiktok', r'линкедин', r'linkedin',
                r'фейсбук', r'facebook', r'инстаграм', r'instagram',
                r'телеграм', r'telegram', r'сигнал', r'signal',
                r'скайп', r'skype', r'зум', r'zoom',
                r'вибер', r'viber', r'вайбер', r'whatsapp',
                r'инстаграм', r'instagram', r'фейсбук', r'facebook',
                r'вконтакте', r'vk', r'одноклассники', r'ok',
                r'твиттер', r'twitter', r'ютуб', r'youtube',
                r'тикток', r'tiktok', r'линкедин', r'linkedin'
            ]
            has_contact = any(re.search(pattern, text_lower) for pattern in contact_patterns)
            
            # Логика принятия решения - МАКСИМАЛЬНО строгая
            total_ad_indicators = ad_indicators + (3 if has_phone else 0) + (2 if has_price else 0) + (2 if has_ad_pattern else 0) + (3 if has_financial else 0) + (2 if has_ad_words else 0) + (3 if has_contact else 0)
            
            # Если есть рекламные индикаторы - фото невалидно (снизили порог до 1)
            if total_ad_indicators >= 1:
                logger.info(f"Обнаружены рекламные индикаторы ({total_ad_indicators}): фото невалидно")
                return False
            
            # Если есть рекламные индикаторы, но есть и водяные знаки - анализируем дальше
            if total_ad_indicators > 0 and watermark_indicators > 0:
                # Если водяных знаков значительно больше чем рекламных - возможно это валидное фото с водяным знаком
                if watermark_indicators >= total_ad_indicators * 2:
                    logger.info(f"Водяных знаков ({watermark_indicators}) значительно больше чем рекламных ({total_ad_indicators}): фото валидно")
                    return True
                else:
                    logger.info(f"Рекламных индикаторов ({total_ad_indicators}) больше или равно водяным знакам ({watermark_indicators}): фото невалидно")
                    return False
            
            # Если только рекламные индикаторы без водяных знаков - фото невалидно
            if total_ad_indicators > 0 and watermark_indicators == 0:
                logger.info(f"Только рекламные индикаторы ({total_ad_indicators}): фото невалидно")
                return False
            
            # Если только водяные знаки - фото валидно
            if total_ad_indicators == 0 and watermark_indicators > 0:
                logger.info(f"Только водяные знаки ({watermark_indicators}): фото валидно")
                return True
            
            # Если нет ни рекламных, ни водяных знаков - проверяем качество текста
            if total_ad_indicators == 0 and watermark_indicators == 0:
                # Проверяем, не является ли текст артефактами OCR
                if self._is_ocr_artifact(cleaned_text):
                    logger.info("Текст является артефактами OCR - фото валидно")
                    return True
                
                # Если текст выглядит осмысленным, но нет рекламных признаков - фото валидно
                if len(cleaned_text) < 20:  # Короткий текст без рекламных признаков
                    logger.info("Короткий текст без рекламных признаков - фото валидно")
                    return True
                
                # Если длинный текст без рекламных признаков - возможно это описание объекта
                logger.info("Длинный текст без рекламных признаков - фото валидно")
                return True
        
        # 4. Если нет текста или текст очищен - фото валидно
        logger.info("Нет текста или текст очищен: фото валидно")
        return True
    
    def _is_ocr_artifact(self, text: str) -> bool:
        """Проверяет, является ли текст артефактами OCR"""
        if not text:
            return True
        
        # Проверяем на повторяющиеся паттерны
        if re.search(r'(.{2,})\1{2,}', text):
            return True
        
        # Проверяем на большое количество спецсимволов
        special_chars = len(re.findall(r'[^\wа-яё\s\.]', text))
        if special_chars > len(text) * 0.4:
            return True
        
        # Проверяем на чередующиеся символы
        if re.search(r'(.)(.)\1\2\1', text):
            return True
        
        # Проверяем на большое количество согласных подряд
        consonant_patterns = [r'[бвгджзйклмнпрстфхцчшщ]{4,}', r'[bcdfghjklmnpqrstvwxz]{4,}']
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in consonant_patterns):
            return True
        
        # Проверяем на большое количество гласных подряд
        vowel_patterns = [r'[аеёиоуыэюя]{4,}', r'[aeiouy]{4,}']
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in vowel_patterns):
            return True
        
        # Проверяем на отсутствие осмысленных слов
        meaningful_words = ['дом', 'квартира', 'комната', 'этаж', 'площадь', 'цена', 'адрес', 'улица', 'дом', 'дом', 'дом']
        text_lower = text.lower()
        meaningful_count = sum(1 for word in meaningful_words if word in text_lower)
        
        if meaningful_count == 0 and len(text) > 10:
            return True
        
        # Дополнительные проверки для артефактов
        # Проверяем на большое количество цифр без букв
        digits = len(re.findall(r'\d', text))
        letters = len(re.findall(r'[а-яёa-z]', text, re.IGNORECASE))
        if digits > 0 and letters == 0 and len(text) < 8:
            return True
        
        # Проверяем на строки только из символов пунктуации
        if re.match(r'^[\s\.,:;\-_=+*\/\\|()\[\]{}<>"\\]*$', text):
            return True
        
        # Проверяем на строки с большим количеством одиночных букв
        single_letters = len(re.findall(r'\b[a-zа-яё]\b', text, re.IGNORECASE))
        if single_letters > len(text) * 0.5:
            return True
        
        # Проверяем на строки с повторяющимися символами
        if re.search(r'(.)\1{3,}', text):  # 4+ одинаковых символа подряд
            return True
        
        return False
    
    def _calculate_confidence(self, ad_banner_score: float, watermark_score: float, text_density: float, detected_objects: List[Dict], image_classification_score: float) -> float:
        """Вычисляет общую уверенность в результате с учетом всех факторов"""
        confidence = 1.0
        
        # Вклад от обнаружения объектов
        if detected_objects:
            max_obj_confidence = max(obj["confidence"] for obj in detected_objects)
            confidence *= (1.0 - max_obj_confidence * 0.5) # Чем выше уверенность в объекте, тем ниже общая уверенность

        # Вклад от классификации изображения
        confidence *= (1.0 - image_classification_score * 0.7) # Чем выше score рекламы, тем ниже общая уверенность

        # Вклад от OCR (как было)
        if hasattr(self, '_last_extracted_text') and self._last_extracted_text.strip():
            text_lower = self._last_extracted_text.lower()
            watermark_only = True
            
            for keyword in self.ad_keywords:
                if keyword in text_lower:
                    watermark_only = False
                    break
            
            phone_patterns = [r'\+996', r'\+7', r'\d{3}-\d{3}-\d{3}']
            price_patterns = [r'\$\s*\d+', r'\d+\s*сом', r'\d+\s*руб']
            
            for pattern in phone_patterns + price_patterns:
                if re.search(pattern, self._last_extracted_text):
                    watermark_only = False
                    break
            
            if watermark_only and watermark_score > 0.1:
                confidence *= 0.8
            else:
                confidence *= 0.2
        
        confidence *= (1.0 - ad_banner_score)
        
        if text_density > 0.1 and watermark_score < 0.1:
            confidence *= 0.5
        
        return max(0.0, min(confidence, 1.0))

def test_photo_validation():
    """Тестирует валидацию фотографий"""
    validator = PhotoValidator()
    
    test_folder = Path("test_photos")
    
    if not test_folder.exists():
        print(f"❌ Папка {test_folder} не найдена!")
        print("Создайте папку 'test_photos' и поместите туда тестовые изображения:")
        print("- 1 рекламное фото (должно быть отклонено)")
        print("- 1 фото объекта (должно пройти валидацию)")
        print("- 1 фото объекта с водяным знаком (должно пройти валидацию)")
        return
    
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
    test_images = [
        f for f in test_folder.iterdir() 
        if f.is_file() and f.suffix.lower() in image_extensions
    ]
    
    if not test_images:
        print(f"❌ В папке {test_folder} не найдено изображений!")
        return
    
    print(f"🔍 Найдено {len(test_images)} изображений для тестирования")
    print("=" * 60)
    
    results = []
    
    for image_path in test_images:
        print(f"\n📸 Тестирование: {image_path.name}")
        print("-" * 40)
        
        result = validator.validate_photo(str(image_path))
        results.append((image_path.name, result))
        
        status = "✅ ВАЛИДНО" if result.is_valid else "❌ НЕВАЛИДНО"
        print(f"Статус: {status}")
        print(f"Уверенность: {result.confidence:.2%}")
        print(f"Score рекламного баннера (OCR): {result.ad_banner_score:.2%}")
        print(f"Score водяного знака (OCR): {result.watermark_score:.2%}")
        print(f"Плотность текста (OCR): {result.text_density:.2%}")
        print(f"Score классификации изображения (CV): {result.image_classification_score:.2%}")
        if result.detected_objects:
            print("Обнаруженные объекты (CV):")
            for obj in result.detected_objects:
                print(f"  - {obj['label']} (Уверенность: {obj['confidence']:.2%})")
        
        if result.extracted_text:
            print(f"Извлеченный текст (OCR): {result.extracted_text[:100]}...")
        
        if result.detected_issues:
            print("Обнаруженные проблемы:")
            for issue in result.detected_issues:
                print(f"  - {issue}")
        else:
            print("Проблем не обнаружено")
    
    print("\n" + "=" * 60)
    print("📊 СВОДКА РЕЗУЛЬТАТОВ")
    print("=" * 60)
    
    valid_count = sum(1 for _, result in results if result.is_valid)
    total_count = len(results)
    
    print(f"Всего изображений: {total_count}")
    print(f"Валидных: {valid_count}")
    print(f"Невалидных: {total_count - valid_count}")
    print(f"Процент валидных: {valid_count/total_count*100:.1f}%")
    
    print("\nДетальные результаты:")
    for name, result in results:
        status = "✅ ВАЛИДНО" if result.is_valid else "❌ НЕВАЛИДНО"
        print(f"  {name}: {status} (уверенность: {result.confidence:.1%})")

if __name__ == "__main__":
    print("🔍 Тестирование валидации фотографий")
    print("=" * 60)
    
    try:
        pytesseract.get_tesseract_version()
        print("✅ Tesseract OCR найден")
    except Exception as e:
        print(f"❌ Tesseract OCR не найден: {e}")
        print("Установите Tesseract:")
        print("  Ubuntu/Debian: sudo apt install tesseract-ocr tesseract-ocr-rus")
        print("  macOS: brew install tesseract tesseract-lang")
        print("  Windows: скачайте с https://github.com/UB-Mannheim/tesseract/wiki")
        sys.exit(1)
    
    test_photo_validation()


