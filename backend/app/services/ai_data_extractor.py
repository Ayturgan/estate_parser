import re
import logging
from typing import Dict, Optional, List, Any, Tuple
from dataclasses import dataclass
import numpy as np
from datetime import datetime
from collections import defaultdict
import json

# Основные импорты для E5-Large
from sentence_transformers import SentenceTransformer  
from sklearn.metrics.pairwise import cosine_similarity

# Опциональный импорт GLiNER
try:
    from gliner import GLiNER
    GLINER_AVAILABLE = True
except ImportError:
    logging.warning("GLiNER not available, falling back to sentence-transformers only")
    GLINER_AVAILABLE = False

logger = logging.getLogger(__name__)

# УЛУЧШЕННАЯ СИСТЕМА КЛЮЧЕВЫХ СЛОВ С ВЕСАМИ И ПРИОРИТЕТАМИ
class KeywordSystem:
    """Многоуровневая система ключевых слов с весами"""
    
    # ПРОДАЖА - Критически важные паттерны (вес: 10)
    SALE_CRITICAL = [
        'продаю', 'продается', 'продаётся', 'продам', 'продажа',
        'сатылат', 'сатам', 'сатабыз',  # кыргызские
        'от собственника продаю', 'срочно продаю', 'продаю срочно',
        'хозяин продает', 'владелец продает'
    ]
    
    # ПРОДАЖА - Сильные индикаторы (вес: 7)
    SALE_STRONG = [
        'купить', 'покупка', 'приобрести', 'приобретение',
        'инвестиция', 'выгодная покупка', 'для покупки',
        'покупателю', 'покупателей', 'инвестору'
    ]
    
    # ПРОДАЖА - Средние индикаторы (вес: 5)
    SALE_MEDIUM = [
        'выгодно', 'торг', 'рассрочка', 'кредит', 'ипотека',
        'документы готовы', 'чистые документы', 'без долгов',
        'срочная продажа', 'семейные обстоятельства',
        'переезд', 'смена города', 'быстрая продажа'
    ]
    
    # ПРОДАЖА - Слабые индикаторы (вес: 3)
    SALE_WEAK = [
        'собственность', 'в собственности', 'приватизирован',
        'свидетельство', 'техпаспорт', 'оценка', 'нотариус'
    ]
    
    # АРЕНДА - Критически важные паттерны (вес: 10)
    RENTAL_CRITICAL = [
        'сдаю', 'сдается', 'сдаётся', 'сдам', 'сдается в аренду',
        'берилет', 'берем', 'берип берет',  # кыргызские
        'в аренду', 'арендую', 'для аренды',
        'снимаю', 'снять', 'найму', 'наем'
    ]
    
    # АРЕНДА - Сильные индикаторы (вес: 7)
    RENTAL_STRONG = [
        'аренда', 'арендовать', 'арендатор', 'арендодатель',
        'съемщик', 'квартиросъемщик', 'жильцу', 'жильцов',
        'временное проживание', 'на время'
    ]
    
    # АРЕНДА - Временные периоды (вес: 8)
    RENTAL_PERIODS = [
        'сутки', 'суточно', 'посуточно', 'сутка', 'за сутки',
        'час', 'часов', 'почасовая', 'на час', 'за час',
        'ночь', 'ночью', 'за ночь', 'ноч', 'ночная',
        'месяц', 'в месяц', 'за месяц', 'помесячно', 'месячная',
        'неделя', 'на неделю', 'за неделю', 'понедельно',
        'долгосрочно', 'краткосрочно', 'длительно'
    ]
    
    # АРЕНДА - Средние индикаторы (вес: 5)
    RENTAL_MEDIUM = [
        'командировочным', 'командировка', 'студентам', 'рабочим',
        'семейным', 'парам', 'девушкам', 'молодым людям',
        'с мебелью', 'меблированная', 'обставленная',
        'коммунальные включены', 'все включено', 'коммуналка включена'
    ]
    
    # ИСКЛЮЧАЮЩИЕ ПРАВИЛА - максимальный приоритет
    EXCLUSION_RULES = {
        'always_rental': [
            'цена за сутки', 'стоимость за ночь', 'плата за день',
            'посуточная аренда', 'почасовая оплата', 'суточная стоимость'
        ],
        'always_sale': [
            'общая стоимость', 'полная цена', 'итоговая сумма',
            'ипотечный кредит', 'первоначальный взнос', 'рассрочка платежа'
        ]
    }
    
    # КЫРГЫЗСКИЕ РЕГИОНАЛЬНЫЕ ТЕРМИНЫ
    KYRGYZ_TERMS = {
        'сатылат': ('продается', 'sale'),
        'сатабыз': ('продаем', 'sale'),
        'сатам': ('продаю', 'sale'),
        'берилет': ('сдается', 'rental'),
        'берип берет': ('сдается', 'rental'),
        'берем': ('сдаем', 'rental'),
        'мкр': ('микрорайон', 'location'),
        'көчө': ('улица', 'location'),
        'борбор': ('центр', 'location'),
        'шаар': ('город', 'location'),
        'үй': ('дом', 'property'),
        'батир': ('квартира', 'property'),
        'жер': ('земля', 'property'),
        'офис': ('офис', 'property')
    }
    
    @classmethod
    def calculate_listing_type_score(cls, text: str) -> Tuple[str, float, Dict]:
        """Вычисляет тип объявления с детальным анализом"""
        text_lower = text.lower()
        
        # Инициализация счетчиков
        sale_score = 0
        rental_score = 0
        details = {'reasons': []}
        
        # 1. ПРОВЕРКА ИСКЛЮЧАЮЩИХ ПРАВИЛ (максимальный приоритет)
        for rule_type, patterns in cls.EXCLUSION_RULES.items():
            for pattern in patterns:
                if pattern in text_lower:
                    if rule_type == 'always_rental':
                        details['reasons'].append(f"Исключающее правило аренды: '{pattern}'")
                        return 'Аренда', 1.0, details
                    elif rule_type == 'always_sale':
                        details['reasons'].append(f"Исключающее правило продажи: '{pattern}'")
                        return 'Продажа', 1.0, details
        
        # 2. АНАЛИЗ КЫРГЫЗСКИХ ТЕРМИНОВ
        for kyrgyz_term, (russian_term, category) in cls.KYRGYZ_TERMS.items():
            if kyrgyz_term in text_lower:
                if category == 'sale':
                    sale_score += 10
                    details['reasons'].append(f"Кыргызский термин продажи: '{kyrgyz_term}' → '{russian_term}'")
                elif category == 'rental':
                    rental_score += 10
                    details['reasons'].append(f"Кыргызский термин аренды: '{kyrgyz_term}' → '{russian_term}'")
        
        # 3. АНАЛИЗ ПРОДАЖИ ПО УРОВНЯМ
        for pattern in cls.SALE_CRITICAL:
            if pattern in text_lower:
                sale_score += 10
                details['reasons'].append(f"Критический паттерн продажи: '{pattern}'")
        
        for pattern in cls.SALE_STRONG:
            if pattern in text_lower:
                sale_score += 7
                details['reasons'].append(f"Сильный паттерн продажи: '{pattern}'")
        
        for pattern in cls.SALE_MEDIUM:
            if pattern in text_lower:
                sale_score += 5
                details['reasons'].append(f"Средний паттерн продажи: '{pattern}'")
        
        for pattern in cls.SALE_WEAK:
            if pattern in text_lower:
                sale_score += 3
                details['reasons'].append(f"Слабый паттерн продажи: '{pattern}'")
        
        # 4. АНАЛИЗ АРЕНДЫ ПО УРОВНЯМ  
        for pattern in cls.RENTAL_CRITICAL:
            if pattern in text_lower:
                rental_score += 10
                details['reasons'].append(f"Критический паттерн аренды: '{pattern}'")
        
        for pattern in cls.RENTAL_STRONG:
            if pattern in text_lower:
                rental_score += 7
                details['reasons'].append(f"Сильный паттерн аренды: '{pattern}'")
        
        for pattern in cls.RENTAL_PERIODS:
            if pattern in text_lower:
                rental_score += 8
                details['reasons'].append(f"Временной период аренды: '{pattern}'")
        
        for pattern in cls.RENTAL_MEDIUM:
            if pattern in text_lower:
                rental_score += 5
                details['reasons'].append(f"Средний паттерн аренды: '{pattern}'")
        
        # 5. УМНЫЙ АНАЛИЗ ЦЕН
        price_analysis = cls._analyze_price_context(text_lower)
        if price_analysis['type'] == 'sale':
            sale_score += price_analysis['confidence']
            details['reasons'].append(f"Ценовой анализ: продажа ({price_analysis['reason']})")
        elif price_analysis['type'] == 'rental':
            rental_score += price_analysis['confidence']
            details['reasons'].append(f"Ценовой анализ: аренда ({price_analysis['reason']})")
        
        # 6. КОНТЕКСТНЫЙ АНАЛИЗ
        context_analysis = cls._analyze_context(text_lower)
        sale_score += context_analysis['sale_context']
        rental_score += context_analysis['rental_context']
        details['reasons'].extend(context_analysis['reasons'])
        
        # 7. ФИНАЛЬНОЕ РЕШЕНИЕ
        total_sale = max(sale_score, 0)
        total_rental = max(rental_score, 0)
        
        details['scores'] = {'sale': total_sale, 'rental': total_rental}
        
        if total_sale == 0 and total_rental == 0:
            # Анализ по умолчанию
            default_analysis = cls._default_analysis(text_lower)
            details['reasons'].append(f"Анализ по умолчанию: {default_analysis['reason']}")
            return default_analysis['type'], default_analysis['confidence'], details
        
        # Определение результата
        if total_sale > total_rental:
            confidence = min(total_sale / (total_sale + total_rental + 1), 1.0)
            return 'Продажа', confidence, details
        elif total_rental > total_sale:
            confidence = min(total_rental / (total_sale + total_rental + 1), 1.0)
            return 'Аренда', confidence, details
        else:
            # Равные баллы - используем дополнительную логику
            tie_breaker = cls._tie_breaker_analysis(text_lower)
            details['reasons'].append(f"Равные баллы, дополнительный анализ: {tie_breaker['reason']}")
            return tie_breaker['type'], 0.5, details
    
    @classmethod
    def _analyze_price_context(cls, text: str) -> Dict:
        """Умный анализ ценового контекста"""
        # Паттерны валют и цен
        usd_matches = re.findall(r'(\$\s*)?(\d+(?:\s*\d+)*)\s*(?:\$|долл|USD)', text)
        som_matches = re.findall(r'(\d+(?:\s*\d+)*)\s*(?:сом|c)', text)
        
        max_price = 0
        currency = None
        
        # Найти максимальную цену
        for match in usd_matches:
            price_str = match[1] if match[1] else match[0]
            try:
                price = int(price_str.replace(' ', ''))
                if price > max_price:
                    max_price = price
                    currency = 'USD'
            except ValueError:
                continue
        
        for match in som_matches:
            try:
                price = int(match.replace(' ', ''))
                if price > max_price:
                    max_price = price
                    currency = 'SOM'
            except ValueError:
                continue
        
        # Анализ цены
        if max_price == 0:
            return {'type': None, 'confidence': 0, 'reason': 'Цена не найдена'}
        
        # Логика определения по цене
        if currency == 'USD':
            if max_price > 50000:
                return {'type': 'sale', 'confidence': 6, 'reason': f'Высокая цена в долларах: ${max_price}'}
            elif max_price < 500:
                return {'type': 'rental', 'confidence': 6, 'reason': f'Низкая цена в долларах: ${max_price}'}
        elif currency == 'SOM':
            if max_price > 3000000:  # > 3 млн сом
                return {'type': 'sale', 'confidence': 6, 'reason': f'Высокая цена в сомах: {max_price} сом'}
            elif max_price < 100000:  # < 100k сом
                return {'type': 'rental', 'confidence': 6, 'reason': f'Низкая цена в сомах: {max_price} сом'}
        
        return {'type': None, 'confidence': 0, 'reason': f'Цена неопределенная: {max_price} {currency}'}
    
    @classmethod
    def _analyze_context(cls, text: str) -> Dict:
        """Контекстный анализ текста"""
        sale_context = 0
        rental_context = 0
        reasons = []
        
        # Контекстные паттерны продажи
        sale_contexts = [
            'документы в порядке', 'свободная продажа', 'торг уместен',
            'срочный переезд', 'смена места жительства', 'семейные обстоятельства',
            'вложение денег', 'хорошая инвестиция', 'растет в цене'
        ]
        
        # Контекстные паттерны аренды
        rental_contexts = [
            'для проживания', 'временное жилье', 'на длительный срок',
            'предоплата', 'залог', 'коммунальные платежи',
            'правила проживания', 'без животных', 'некурящим'
        ]
        
        for context in sale_contexts:
            if context in text:
                sale_context += 2
                reasons.append(f"Контекст продажи: '{context}'")
        
        for context in rental_contexts:
            if context in text:
                rental_context += 2
                reasons.append(f"Контекст аренды: '{context}'")
        
        return {
            'sale_context': sale_context,
            'rental_context': rental_context,
            'reasons': reasons
        }
    
    @classmethod
    def _default_analysis(cls, text: str) -> Dict:
        """Анализ по умолчанию когда нет явных индикаторов"""
        # Если есть упоминание о документах - скорее продажа
        if any(word in text for word in ['документ', 'паспорт', 'свидетельство']):
            return {'type': 'Продажа', 'confidence': 0.3, 'reason': 'Упоминание документов'}
        
        # Если есть мебель или удобства - скорее аренда
        if any(word in text for word in ['мебель', 'холодильник', 'стиральная', 'посуда']):
            return {'type': 'Аренда', 'confidence': 0.3, 'reason': 'Упоминание мебели/удобств'}
        
        # По умолчанию продажа (консервативный подход)
        return {'type': 'Продажа', 'confidence': 0.2, 'reason': 'Значение по умолчанию'}
    
    @classmethod
    def _tie_breaker_analysis(cls, text: str) -> Dict:
        """Дополнительный анализ при равных баллах"""
        # Анализ длины текста
        if len(text) > 500:
            return {'type': 'Продажа', 'reason': 'Длинное описание (обычно продажа)'}
        
        # Анализ наличия контактов
        if re.search(r'\+996|0\d{9}', text):
            return {'type': 'Аренда', 'reason': 'Много контактов (обычно аренда)'}
        
        return {'type': 'Продажа', 'reason': 'Случай неопределенности'}

# РАСШИРЕННАЯ СИСТЕМА ТИПОВ НЕДВИЖИМОСТИ  
class PropertyTypeSystem:
    """Улучшенная система классификации типов недвижимости"""
    
    PROPERTY_TYPES = {
        'Квартира': {
            'primary': [
                'квартир', 'квартира', 'квартиру', 'квартире', 'квартиры',
                'комнат', 'комната', 'комнату', 'комнаты', 'комнате',
                'кв.', 'кв', 'кв,', 'квартир.', # Важно для заголовков типа "1-комн. кв."
                'батир'  # кыргызский
            ],
            'secondary': [
                'студи', 'студия', 'студию', 'пентхаус', 'пентхауз', 'лофт',
                'малосемейка', 'малогабаритная', 'хрущевка', 'брежневка',
                'новостройка квартира', 'элитная квартира', 'евродвушка',
                'жк', 'жилой комплекс', 'жилком'
            ],
            'context': [
                'жилая площадь', 'жилых комнат', 'спальн', 'гостин', 'прихожая',
                'балкон', 'лоджия', 'санузел', 'ванная комната', 'кухня',
                'этаж', 'подъезд', 'лифт', 'панорамные окна'
            ],
            'modifiers': [
                'однокомнат', '1-комнат', '1к', '1-к', 'одно комнат', '1 комн',
                'двухкомнат', '2-комнат', '2к', '2-к', 'двух комнат', '2 комн', 
                'трехкомнат', '3-комнат', '3к', '3-к', 'трех комнат', '3 комн',
                'четырехкомнат', '4-комнат', '4к', '4-к', 'четырех комнат', '4 комн',
                'пятикомнат', '5-комнат', '5к', '5-к', 'пяти комнат', '5 комн'
            ],
            'weight': 1.0
        },
        
        'Частный дом': {
            'primary': [
                'дом', 'дома', 'домом', 'доме', 'коттедж', 'коттеджа', 'коттеджем',
                'үй', 'үйдү'  # кыргызский
            ],
            'secondary': [
                'особняк', 'особняка', 'усадьба', 'усадьбу', 'усадьбой',
                'дача', 'дачу', 'дачей', 'дачный дом', 'загородный дом',
                'таунхаус', 'таунхауз', 'вилла', 'виллу', 'коттеджный поселок'
            ],
            'context': [
                'участок', 'двор', 'сад', 'огород', 'теплица', 'гараж',
                'баня', 'сауна', 'бассейн', 'забор', 'ворота', 'калитка',
                'этажа', 'этажный', 'мансарда', 'подвал', 'цоколь'
            ],
            'modifiers': [
                'одноэтажный', '1-этажный', 'двухэтажный', '2-этажный',
                'трехэтажный', '3-этажный', 'кирпичный', 'деревянный',
                'блочный', 'панельный', 'монолитный'
            ],
            'weight': 1.0
        },
        
        'Земельный участок': {
            'primary': [
                'участок', 'участка', 'участком', 'участке', 'земля', 'земли', 'землей',
                'жер', 'жерди'  # кыргызский
            ],
            'secondary': [
                'земельный участок', 'земельный надел', 'надел', 'делянка',
                'сотка', 'сотки', 'соток', 'гектар', 'гектара', 'га'
            ],
            'context': [
                'под строительство', 'под застройку', 'строительный участок',
                'коммуникации', 'электричество', 'газ', 'вода', 'канализация',
                'огорожен', 'ровный', 'с уклоном', 'плодородная'
            ],
            'modifiers': [
                'ИЖС', 'ЛПХ', 'садовый', 'дачный', 'сельхоз', 'коммерческий',
                'промышленный', 'под бизнес'
            ],
            'weight': 1.2  # Больше вес для точного определения
        },
        
        'Офис': {
            'primary': [
                'офис', 'офиса', 'офисом', 'офисе', 'офисы', 'офисов',
                'кабинет', 'кабинета', 'кабинетом'
            ],
            'secondary': [
                'офисное помещение', 'рабочее место', 'рабочее помещение',
                'деловой центр', 'бизнес центр', 'бизнес-центр',
                'административное помещение'
            ],
            'context': [
                'переговорная', 'конференц-зал', 'приемная', 'open space',
                'опен спейс', 'кондиционер', 'интернет', 'парковка',
                'охрана', 'лифт', 'центр города'
            ],
            'modifiers': [
                'представительский', 'класса А', 'класса В', 'класса С',
                'элитный', 'премиум', 'стандарт', 'эконом'
            ],
            'weight': 1.1
        },
        
        'Коммерческая недвижимость': {
            'primary': [
                'магазин', 'магазина', 'магазином', 'торговое помещение',
                'торговая площадь', 'торговый зал'
            ],
            'secondary': [
                'склад', 'складом', 'складское помещение', 'ангар', 'ангара',
                'производственное помещение', 'цех', 'мастерская',
                'ресторан', 'ресторана', 'кафе', 'кафем', 'столовая',
                'салон', 'салона', 'студия', 'ателье', 'мини-гостиница'
            ],
            'context': [
                'торговля', 'бизнес', 'коммерция', 'аренда коммерческая',
                'проходимость', 'витрина', 'вывеска', 'парковка клиентов',
                'отдельный вход', 'первая линия', 'красная линия'
            ],
            'modifiers': [
                'стрит-ритейл', 'фуд-корт', 'торговый центр', 'ТЦ',
                'торговый комплекс', 'рынок', 'павильон', 'киоск'
            ],
            'weight': 1.0
        },
        
        'Гараж': {
            'primary': [
                'гараж', 'гаража', 'гаражом', 'гараже', 'гаражи',
                'бокс', 'бокса', 'боксом', 'боксе'
            ],
            'secondary': [
                'машино-место', 'машиноместо', 'парковочное место',
                'стоянка', 'паркинг', 'подземный гараж'
            ],
            'context': [
                'охраняемый', 'кооператив', 'гаражный кооператив',
                'смотровая яма', 'электричество', 'отопление', 'вентиляция'
            ],
            'modifiers': [
                'кирпичный', 'металлический', 'железный', 'капитальный',
                'временный', 'разборный'
            ],
            'weight': 1.1
        }
    }
    
    @classmethod
    def classify_property_type(cls, text: str) -> Tuple[Optional[str], float, Dict]:
        """Классифицирует тип недвижимости с детальным анализом"""
        text_lower = text.lower()
        scores = {}
        details = {'matches': [], 'reasons': []}
        
        # Подсчет баллов для каждого типа
        for prop_type, config in cls.PROPERTY_TYPES.items():
            score = 0
            matches = []
            
            # Основные термины (вес: 10)
            for term in config['primary']:
                if term in text_lower:
                    score += 10 * config['weight']
                    matches.append(f"Основной термин: '{term}'")
            
            # Вторичные термины (вес: 7)
            for term in config['secondary']:
                if term in text_lower:
                    score += 7 * config['weight']
                    matches.append(f"Вторичный термин: '{term}'")
            
            # Контекстные термины (вес: 3)
            for term in config['context']:
                if term in text_lower:
                    score += 3 * config['weight']
                    matches.append(f"Контекст: '{term}'")
            
            # Модификаторы (вес: 2)
            for term in config['modifiers']:
                if term in text_lower:
                    score += 2 * config['weight']
                    matches.append(f"Модификатор: '{term}'")
            
            if score > 0:
                scores[prop_type] = score
                details['matches'].extend([f"{prop_type}: {match}" for match in matches])
        
        # Дополнительные правила
        cls._apply_additional_rules(text_lower, scores, details)
        
        if not scores:
            # Fallback анализ
            fallback = cls._fallback_analysis(text_lower)
            details['reasons'].append(f"Fallback анализ: {fallback['reason']}")
            return fallback['type'], fallback['confidence'], details
        
        # Определение лучшего типа
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        
        # Улучшенная формула уверенности
        if best_score >= 40:  # Критические правила
            confidence = 0.95
        elif best_score >= 20:  # Сильные индикаторы
            confidence = 0.85
        elif best_score >= 10:  # Средние индикаторы
            confidence = 0.75
        else:
            # Пропорциональная уверенность для низких баллов
            total_score = sum(scores.values())
            confidence = min(best_score / (total_score + 5), 0.65)
        
        details['scores'] = scores
        details['reasons'].append(f"Выбран '{best_type}' с баллом {best_score}")
        
        return best_type, confidence, details
    
    @classmethod
    def _apply_additional_rules(cls, text: str, scores: Dict, details: Dict):
        """Применяет дополнительные правила классификации"""
        
        # КРИТИЧЕСКИ ВАЖНО: Заголовки с квартирами - это всегда квартира
        # Улучшенные паттерны для различных форматов
        apartment_patterns = [
            r'\d+\s*-?\s*комн\.\s*кв\.',  # "1-комн. кв."
            r'\d+\s*-?\s*к\.\s*кв\.',     # "1-к. кв."  
            r'\d+\s*-?\s*к\.кв\.',        # "1-к.кв."
            r'\d+\s*-?\s*к\.кв',          # "1-к.кв" (без финальной точки)
            r'\d+\s*-?\s*к\s+кв\.',       # "1-к кв."
            r'\d+\s*-?\s*к\s+студи',      # "2-к студию"
            r'студи[ияюе]',               # "студия", "студию" и т.д.
        ]
        
        for pattern in apartment_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                scores['Квартира'] = 50  # Максимальный балл
                details['reasons'].append(f"КРИТИЧЕСКОЕ ПРАВИЛО: найден паттерн '{pattern}' → квартира")
                # Убираем баллы у других типов если это заголовок квартиры
                for other_type in ['Земельный участок', 'Частный дом', 'Офис', 'Коммерческая недвижимость']:
                    scores.pop(other_type, None)
                break
        
        # Правило: если есть "сотки" или "гектары" - это точно участок
        if any(term in text for term in ['сотк', 'гектар', 'га ', ' га']):
            if 'Земельный участок' in scores:
                scores['Земельный участок'] *= 2
            else:
                scores['Земельный участок'] = 20
            details['reasons'].append("Правило: упоминание соток/гектаров → участок")
        
        # Правило: если есть номер квартиры - это квартира
        apt_number = re.search(r'кв\.?\s*\d+|квартира\s*\d+|№\s*\d+', text)
        if apt_number:
            if 'Квартира' in scores:
                scores['Квартира'] += 15
            else:
                scores['Квартира'] = 20
            details['reasons'].append(f"Правило: номер квартиры '{apt_number.group()}' → квартира")
        
        # Правило: если есть этажи (разные форматы) - скорее квартира
        floor_patterns = [
            r'\d+\s*этаж\s*из\s*\d+',      # "11 этаж из 15"
            r'этаж\s*\d+\s*из\s*\d+',      # "Этаж 11 из 15"  
            r'этаж\s*\d+/\d+',             # "Этаж 11/14"
            r'\d+/\d+\s*этаж',             # "11/14 этаж"
        ]
        
        floor_found = False
        for pattern in floor_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                if 'Квартира' in scores:
                    scores['Квартира'] += 15
                else:
                    scores['Квартира'] = 18
                details['reasons'].append(f"Правило: найден паттерн этажей '{pattern}' → квартира")
                floor_found = True
                break
        
        # Правило: если есть "этаж" без "дом" - скорее квартира
        if not floor_found and 'этаж' in text.lower() and 'дом' not in text.lower():
            if 'Квартира' in scores:
                scores['Квартира'] += 8
            else:
                scores['Квартира'] = 10
            details['reasons'].append("Правило: этаж без дома → квартира")
        
        # Правило: если есть "двор" с "домом" - точно дом
        if 'двор' in text and any(term in text for term in ['дом', 'коттедж']):
            if 'Частный дом' in scores:
                scores['Частный дом'] += 8
            else:
                scores['Частный дом'] = 12
            details['reasons'].append("Правило: двор + дом → частный дом")
        
        # Правило: площадь в м2 + этаж + без участка/соток - скорее квартира
        if (re.search(r'\d+\.?\d*\s*м2', text) and 'этаж' in text and 
            not any(term in text for term in ['участок', 'сотк', 'двор', 'коттедж'])):
            if 'Квартира' in scores:
                scores['Квартира'] += 5
            else:
                scores['Квартира'] = 8
            details['reasons'].append("Правило: м2 + этаж без участка → квартира")
    
    @classmethod
    def _fallback_analysis(cls, text: str) -> Dict:
        """Анализ по умолчанию"""
        
        # Приоритет: различные форматы квартир
        apartment_patterns = [
            (r'\d+\s*-?\s*комн\.\s*кв\.', 'Заголовок с "комн. кв."'),
            (r'\d+\s*-?\s*к\.\s*кв\.', 'Заголовок с "к. кв."'),
            (r'\d+\s*-?\s*к\.кв\.', 'Заголовок с "к.кв"'),
            (r'\d+\s*-?\s*к\s+студи', 'Заголовок со студией'),
            (r'студи[ияюе]', 'Упоминание студии'),
        ]
        
        for pattern, reason in apartment_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return {'type': 'Квартира', 'confidence': 0.9, 'reason': reason}
        
        # Простые ключевые слова с повышенной уверенностью
        if any(word in text.lower() for word in ['1к', '2к', '3к', '4к', '5к', '1-к', '2-к', '3-к', '4-к', '5-к']):
            return {'type': 'Квартира', 'confidence': 0.85, 'reason': 'Упоминание количества комнат'}
            
        if 'комн' in text and 'этаж' in text:
            return {'type': 'Квартира', 'confidence': 0.85, 'reason': 'Комнаты + этаж'}
        
        if any(word in text for word in ['участок', 'сотк', 'земл']):
            return {'type': 'Земельный участок', 'confidence': 0.8, 'reason': 'Упоминание участка/земли'}
        
        if any(word in text for word in ['дом', 'коттедж']) and 'двор' in text:
            return {'type': 'Частный дом', 'confidence': 0.8, 'reason': 'Дом с двором'}
        
        if any(word in text for word in ['дом', 'коттедж']) and not 'этаж' in text:
            return {'type': 'Частный дом', 'confidence': 0.7, 'reason': 'Упоминание дома'}
        
        if any(word in text for word in ['офис', 'кабинет', 'бизнес']):
            return {'type': 'Офис', 'confidence': 0.7, 'reason': 'Упоминание офиса'}
        
        if any(word in text for word in ['магазин', 'торговое', 'коммерческ']):
            return {'type': 'Коммерческая недвижимость', 'confidence': 0.7, 'reason': 'Упоминание торговли'}
        
        # По умолчанию квартира с низкой уверенностью
        return {'type': 'Квартира', 'confidence': 0.4, 'reason': 'Тип по умолчанию'}

# СИСТЕМА ВАЛИДАЦИИ И КАЧЕСТВА
class DataValidator:
    """Валидатор извлеченных данных"""
    
    @staticmethod
    def validate_area(area: float) -> bool:
        """Валидация площади"""
        return 5 <= area <= 10000
    
    @staticmethod
    def validate_floor(floor: int, total_floors: Optional[int] = None) -> bool:
        """Валидация этажа"""
        if not (1 <= floor <= 50):
            return False
        if total_floors and floor > total_floors:
            return False
        return True
    
    @staticmethod
    def validate_rooms(rooms: int) -> bool:
        """Валидация количества комнат"""
        return 1 <= rooms <= 20
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Валидация телефона"""
        # Кыргызский формат +996XXXXXXXXX
        pattern = r'^\+996[0-9]{9}$'
        return bool(re.match(pattern, phone))
    
    @staticmethod
    def calculate_quality_score(extracted_data: Dict) -> float:
        """Вычисляет оценку качества извлечения"""
        quality_factors = {}
        total_weight = 0
        weighted_score = 0
        
        # Оценка типа недвижимости (вес: 3)
        if extracted_data.get('property_type_confidence'):
            quality_factors['property_type'] = extracted_data['property_type_confidence']
            weighted_score += extracted_data['property_type_confidence'] * 3
            total_weight += 3
        
        # Оценка типа объявления (вес: 3)
        if extracted_data.get('listing_type_confidence'):
            quality_factors['listing_type'] = extracted_data['listing_type_confidence']
            weighted_score += extracted_data['listing_type_confidence'] * 3
            total_weight += 3
        
        # Наличие ключевых данных (вес: по 1)
        key_fields = ['area_sqm', 'rooms', 'phones', 'location']
        for field in key_fields:
            if extracted_data.get(field):
                quality_factors[field] = 1.0
                weighted_score += 1.0
                total_weight += 1
            else:
                quality_factors[field] = 0.0
        
        # Валидность данных (вес: 2)
        validation_score = DataValidator._validate_extracted_data(extracted_data)
        quality_factors['validation'] = validation_score
        weighted_score += validation_score * 2
        total_weight += 2
        
        final_score = weighted_score / total_weight if total_weight > 0 else 0
        
        return min(final_score, 1.0)
    
    @staticmethod
    def _validate_extracted_data(data: Dict) -> float:
        """Валидация всех извлеченных данных"""
        validations = []
        
        # Валидация площади
        if data.get('area_sqm'):
            validations.append(DataValidator.validate_area(data['area_sqm']))
        
        # Валидация этажа
        if data.get('floor'):
            validations.append(DataValidator.validate_floor(
                data['floor'], data.get('total_floors')
            ))
        
        # Валидация комнат
        if data.get('rooms'):
            validations.append(DataValidator.validate_rooms(data['rooms']))
        
        # Валидация телефонов
        if data.get('phones'):
            phone_validations = [DataValidator.validate_phone(phone) for phone in data['phones']]
            validations.extend(phone_validations)
        
        if not validations:
            return 0.8  # Нет данных для валидации
        
        return sum(validations) / len(validations)

@dataclass
class RealEstateData:
    """Расширенная структура данных о недвижимости"""
    property_type: Optional[str] = None
    property_type_confidence: Optional[float] = None
    property_origin: Optional[str] = None
    listing_type: Optional[str] = None
    listing_type_confidence: Optional[float] = None
    rooms: Optional[int] = None
    area_sqm: Optional[float] = None
    living_area: Optional[float] = None
    kitchen_area: Optional[float] = None
    land_area_sotka: Optional[float] = None
    floor: Optional[int] = None
    total_floors: Optional[int] = None
    phones: Optional[List[str]] = None
    location: Optional[Dict] = None
    heating: Optional[str] = None
    furniture: Optional[str] = None
    condition: Optional[str] = None
    amenities: Optional[Dict] = None
    extraction_quality: Optional[float] = None
    extraction_details: Optional[Dict] = None

class PropertyTypeClassifier:
    """Улучшенный классификатор типов недвижимости"""
    
    def __init__(self, model, model_type='e5large'):
        self.model = model
        self.model_type = model_type
        self.confidence_threshold = 0.25
        self.property_system = PropertyTypeSystem()
        self.keyword_system = KeywordSystem()
        
    def classify_property_type(self, text: str) -> Tuple[Optional[str], float]:
        """Классифицирует тип недвижимости с новой системой"""
        try:
            # Используем новую систему классификации
            prop_type, confidence, details = self.property_system.classify_property_type(text)
            
            # Логируем детали для анализа
            logger.debug(f"🏠 Классификация недвижимости: {prop_type} (уверенность: {confidence:.2f})")
            logger.debug(f"📊 Детали: {details.get('reasons', [])}")
            
            return prop_type, confidence
            
        except Exception as e:
            logger.error(f"Error in property type classification: {e}")
            # Fallback к старой системе
            return self._fallback_classification(text)
    
    def _fallback_classification(self, text: str) -> Tuple[Optional[str], float]:
        """Резервная классификация при ошибках"""
        try:
            if self.model_type == 'gliner':
                return self._classify_with_gliner(text)
            else:
                return self._classify_with_e5large(text)
        except Exception as e:
            logger.error(f"Fallback classification failed: {e}")
            return None, 0.0
    
    def _classify_with_gliner(self, text: str) -> Tuple[Optional[str], float]:
        """Классификация с помощью GLiNER"""
        # Улучшенные метки для GLiNER
        labels = [
            "apartment", "квартира", "комната", "студия",
            "house", "частный дом", "дом", "коттедж", 
            "land", "земельный участок", "участок", "земля",
            "office", "офис", "коммерческая недвижимость",
            "commercial", "магазин", "помещение"
        ]
        
        entities = self.model.predict_entities(text.lower(), labels)
        
        if not entities:
            # Fallback на ключевые слова
            return self._classify_by_keywords(text)
        
        # Группируем и ранжируем результаты
        type_scores = {}
        for entity in entities:
            entity_text = entity['text'].lower()
            score = entity['score']
            
            # Определяем тип недвижимости по извлеченной сущности
            if any(word in entity_text for word in ['квартир', 'комнат', 'студи']):
                type_scores['Квартира'] = max(type_scores.get('Квартира', 0), score)
            elif any(word in entity_text for word in ['дом', 'коттедж', 'house']):
                type_scores['Частный дом'] = max(type_scores.get('Частный дом', 0), score)
            elif any(word in entity_text for word in ['участок', 'земл', 'land']):
                type_scores['Земельный участок'] = max(type_scores.get('Земельный участок', 0), score)
            elif any(word in entity_text for word in ['офис', 'office']):
                type_scores['Офис'] = max(type_scores.get('Офис', 0), score)
            elif any(word in entity_text for word in ['магазин', 'помещен', 'commercial']):
                type_scores['Коммерческая недвижимость'] = max(type_scores.get('Коммерческая недвижимость', 0), score)
        
        if type_scores:
            best_type = max(type_scores.items(), key=lambda x: x[1])
            if best_type[1] >= self.confidence_threshold:
                return best_type[0], best_type[1]
        
        # Fallback на ключевые слова
        return self._classify_by_keywords(text)
    
    def _classify_with_e5large(self, text: str) -> Tuple[Optional[str], float]:
        """Классификация с помощью E5-Large модели"""
        try:
            # Эталонные примеры для классификации типов недвижимости
            property_examples = {
                'Квартира': [
                    "1-комнатная квартира в новостройке",
                    "Продается трехкомнатная квартира",
                    "Сдается однокомнатная квартира",
                    "Студия с ремонтом"
                ],
                'Частный дом': [
                    "Продается частный дом",
                    "Коттедж с участком",
                    "Двухэтажный дом"
                ],
                'Земельный участок': [
                    "Земельный участок под строительство",
                    "Участок 10 соток"
                ],
                'Офис': [
                    "Офисное помещение в центре",
                    "Сдается офис"
                ],
                'Коммерческая недвижимость': [
                    "Торговое помещение",
                    "Магазин на первом этаже"
                ]
            }
            
            # Получаем эмбеддинг входного текста
            input_embedding = self.model.encode([text])[0]
            
            best_type = None
            best_score = 0.0
            
            # Сравниваем с эталонными примерами
            for prop_type, examples in property_examples.items():
                example_embeddings = self.model.encode(examples)
                
                # Вычисляем максимальное сходство с примерами этого типа
                similarities = cosine_similarity([input_embedding], example_embeddings)[0]
                max_similarity = max(similarities)
                
                if max_similarity > best_score:
                    best_score = max_similarity
                    best_type = prop_type
            
            if best_score >= self.confidence_threshold:
                return best_type, best_score
            else:
                # Fallback на ключевые слова
                return self._classify_by_keywords(text)
                
        except Exception as e:
            logger.error(f"Error in E5-Large classification: {e}")
            return self._classify_by_keywords(text)
    
    def _classify_by_keywords(self, text: str) -> Tuple[Optional[str], float]:
        """Классификация по ключевым словам как fallback"""
        text_lower = text.lower()
        
        # Улучшенные паттерны ключевых слов
        patterns = {
            'Земельный участок': [
                'земельный участок', 'участок', 'земля', 'сотк', 'гектар', 
                'под строительство', 'под застройку'
            ],
            'Частный дом': [
                'частный дом', 'дом', 'коттедж', 'особняк', 'усадьба',
                'двухэтажный', 'одноэтажный', 'загородный дом'
            ],
            'Офис': [
                'офис', 'офисное помещение', 'бизнес-центр', 'деловой центр'
            ],
            'Коммерческая недвижимость': [
                'магазин', 'торговое помещение', 'склад', 'производственное помещение',
                'ресторан', 'кафе', 'салон'
            ],
            'Квартира': [
                'квартир', 'комнат', 'студи', 'однокомнат', 'двухкомнат', 
                'трехкомнат', 'четырехкомнат', 'малосемейка'
            ]
        }
        
        # Приоритет: сначала специфичные типы, потом общие
        for prop_type in ['Земельный участок', 'Частный дом', 'Офис', 'Коммерческая недвижимость', 'Квартира']:
            for pattern in patterns[prop_type]:
                if pattern in text_lower:
                    return prop_type, 0.8  # Высокая уверенность для ключевых слов
        
        return 'Квартира', 0.3  # Значение по умолчанию
    
    def classify_property_origin(self, text: str) -> str:
        """Классификация происхождения недвижимости"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in [
            'новостройка', 'новое строительство', 'от застройщика', 
            'первичн', 'новый дом', 'сдача в'
        ]):
            return "Новостройка"
        elif any(word in text_lower for word in [
            'вторичка', 'вторичн', 'б/у', 'бывш', 'старый фонд'
        ]):
            return "Вторичная"
        
        return "Неизвестно"
    
    def classify_listing_type(self, text: str) -> str:
        """Классификация типа объявления"""
        text_lower = text.lower()
        
        # Усиленные ключевые слова аренды - проверяем ПЕРВЫМИ
        rental_keywords = [
            'сдается', 'сдаётся', 'сдам', 'сдаю', 'аренда', 'снять', 'арендовать',
            'найм', 'посуточн', 'на месяц', 'долгосрочн', 'краткосрочн'
        ]
        
        if any(word in text_lower for word in rental_keywords):
            return "Аренда"
        
        # Ключевые слова продажи
        sale_keywords = [
            'продается', 'продаётся', 'продам', 'продаю', 'на продажу', 'купить',
            'продажа', 'реализ', 'продаж'
        ]
        
        if any(word in text_lower for word in sale_keywords):
            return "Продажа"
        
        # Fallback - если есть цена в долларах и большая сумма, вероятно продажа
        if re.search(r'(\$|долл|USD).*(\d{4,})', text_lower):
            return "Продажа"
        
        return "Продажа"  # По умолчанию

class AreaExtractor:
    """Извлекатель площадей"""
    
    def extract_areas(self, text: str) -> Dict[str, Optional[float]]:
        """Извлекает все типы площадей"""
        areas = {
            'area_sqm': None,
            'living_area': None,
            'kitchen_area': None,
            'land_area_sotka': None
        }
        
        # Общая площадь - улучшенные паттерны
        total_patterns = [
            r'(?:общая\s+)?площадь[:\s]*(\d+(?:[.,]\d+)?)',
            r'(\d+(?:[.,]\d+)?)\s*м²?\s*(?:общ|кв\.?м)',
            r'(\d+(?:[.,]\d+)?)\s*м²',  # "34 м²"
            r'(\d+(?:[.,]\d+)?)\s*кв\.?m',  # "94 кв.м"
            r'(\d+(?:[.,]\d+)?)\s*квадрат',  # "220 квадратных метров"
            r'(\d+(?:[.,]\d+)?)\s*кв\s*м',  # "94 кв м"
            r'(\d+(?:[.,]\d+)?)\s*м2',  # "172м2"
            r'(\d+(?:[.,]\d+)?)\s*м\^2',  # "172м^2"
            r'(\d+(?:[.,]\d+)?)\s*кв\.?м',  # "94 кв.м"
            r'S[:\s]*(\d+(?:[.,]\d+)?)',
            r'(\d+(?:[.,]\d+)?)\s*квадратных\s+метров',  # "220 квадратных метров"
            r'(\d+(?:[.,]\d+)?)\s*кв\.?\s*метров',  # "94 кв. метров"
        ]
        
        for pattern in total_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                areas['area_sqm'] = self._parse_area(match.group(1))
                break
        
        # Жилая площадь
        living_patterns = [
            r'жилая\s+площадь[:\s]*(\d+(?:[.,]\d+)?)',
            r'(\d+(?:[.,]\d+)?)\s*м²?\s*жил',
            r'жилая[:\s]*(\d+(?:[.,]\d+)?)'
        ]
        
        for pattern in living_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                areas['living_area'] = self._parse_area(match.group(1))
                break
        
        # Площадь кухни
        kitchen_patterns = [
            r'кухня[:\s]*(\d+(?:[.,]\d+)?)',
            r'площадь\s+кухни[:\s]*(\d+(?:[.,]\d+)?)',
            r'кух[:\s]*(\d+(?:[.,]\d+)?)\s*м'
        ]
        
        for pattern in kitchen_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                areas['kitchen_area'] = self._parse_area(match.group(1))
                break
        
        # Площадь участка в сотках
        land_patterns = [
            r'участок[:\s]*(\d+(?:[.,]\d+)?)\s*(?:сот|сотк)',
            r'(\d+(?:[.,]\d+)?)\s*сот(?:ок|ка|ки)?',
            r'земельный\s+участок[:\s]*(\d+(?:[.,]\d+)?)',
            r'площадь\s+участка[:\s]*(\d+(?:[.,]\d+)?)',
            r'(\d+(?:[.,]\d+)?)\s*сотки',
            r'земля[:\s]*(\d+(?:[.,]\d+)?)\s*сот'
        ]
        
        for pattern in land_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                sotka_value = self._parse_land_area(match.group(1))
                if sotka_value:
                    areas['land_area_sotka'] = sotka_value
                    break
        
        return areas
    
    def _parse_area(self, area_str: str) -> Optional[float]:
        """Парсинг строки площади"""
        try:
            area = float(area_str.replace(',', '.'))
            return area if 10 <= area <= 10000 else None
        except (ValueError, AttributeError):
            return None
    
    def _parse_land_area(self, area_str: str) -> Optional[float]:
        """Парсинг площади участка в сотках"""
        try:
            area = float(area_str.replace(',', '.'))
            return area if 0.1 <= area <= 1000 else None  # От 0.1 до 1000 соток
        except (ValueError, AttributeError):
            return None

class LocationExtractor:
    """Извлекатель географических данных"""
    
    def __init__(self):
        self.cities = [
            "Бишкек", "Токмок", "Кара-Балта", "Кант", "Ош", "Кызыл-Кия", 
            "Сулюкта", "Баткен", "Исфана", "Джалал-Абад", "Таш-Кумыр", 
            "Кара-Куль", "Каракол", "Балыкчы", "Чолпон-Ата", "Талас", "Нарын"
        ]
        
        self.districts = [
            "Аламединский", "Сокулукский", "Ысык-Атинский", "Московский",
            "Жайылский", "Панфиловский", "Кеминский", "Чуйский",
            "Кара-Сууйский", "Ноокатский", "Араванский", "Узгенский"
        ]
    
    def extract_location(self, text: str, existing_data: Dict) -> Dict:
        """Извлекает географическую информацию"""
        location_data = {}
        current_location = existing_data.get('location', {})
        text_lower = text.lower()
        
        # Город (только если не указан)
        if not current_location.get('city'):
            for city in self.cities:
                if city.lower() in text_lower:
                    if 'location' not in location_data:
                        location_data['location'] = {}
                    location_data['location']['city'] = city
                    logger.debug(f"🏙️ Найден город: {city}")
                    break
        
        # Район
        if not current_location.get('district'):
            for district in self.districts:
                variations = [district, district.replace("ский", ""), district + " район"]
                for variation in variations:
                    if variation.lower() in text_lower:
                        if 'location' not in location_data:
                            location_data['location'] = {}
                        location_data['location']['district'] = district
                        logger.debug(f"🏘️ Найден район: {district}")
                        break
                if location_data.get('location', {}).get('district'):
                    break
        
        # Адрес (строгая валидация)
        if not current_location.get('address'):
            address = self._extract_address(text)
            if address:
                if 'location' not in location_data:
                    location_data['location'] = {}
                location_data['location']['address'] = address
                logger.debug(f"📍 Извлечен адрес: {address}")
        
        return location_data
    
    def _extract_address(self, text: str) -> Optional[str]:
        """Извлекает качественные адреса"""
        # Улицы с названиями - улучшенные паттерны
        street_patterns = [
            r'ул\.?\s*([А-Яа-яёЁ][А-Яа-яёЁ\s\-]{3,25})',
            r'улица\s+([А-Яа-яёЁ][А-Яа-яёЁ\s\-]{3,25})',
            r'проспект\s+([А-Яа-яёЁ][А-Яа-яёЁ\s\-]{3,25})',
            r'пр\.?\s*([А-Яа-яёЁ][А-Яа-яёЁ\s\-]{3,25})',
            r'([А-Яа-яёЁ][А-Яа-яёЁ\s\-]{3,25})\s*/\s*([А-Яа-яёЁ][А-Яа-яёЁ\s\-]{3,25})',  # "Чынгыз Айтматова / Масалиева"
            r'рядом\s+с\s+([А-Яа-яёЁ][А-Яа-яёЁ\s\-]{3,25})',  # "рядом с Филармонией"
            r'([А-Яа-яёЁ][А-Яа-яёЁ\s\-]{3,25})\s*[0-9]+',  # "Ахунбаева 28"
        ]
        
        # Микрорайоны
        micro_patterns = [
            r'(\d+)\s*мкр',
            r'мкр\.?\s*([А-Яа-яёЁ0-9\s\-]{1,15})',
            r'микрорайон\s+([А-Яа-яёЁ0-9\s\-]{1,15})'
        ]
        
        potential_addresses = []
        
        # Ищем улицы
        for pattern in street_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                street_name = match.group(1).strip()
                if len(street_name) > 3 and street_name.count(' ') <= 3:
                    potential_addresses.append(f"ул. {street_name}")
        
        # Ищем микрорайоны
        for pattern in micro_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                micro_name = match.group(1).strip()
                if len(micro_name) <= 15:
                    if micro_name.isdigit():
                        potential_addresses.append(f"{micro_name} мкр")
                    else:
                        potential_addresses.append(f"мкр {micro_name}")
        
        if potential_addresses:
            # Выбираем первый качественный адрес
            best_address = potential_addresses[0]
            # Проверяем качество
            if (len(best_address) > 5 and len(best_address) < 50 and
                not any(word in best_address.lower() for word in ['одается', 'одаю', 'емимум'])):
                return best_address
        
        return None
    
    def extract_location_info(self, text: str, current_location: dict) -> dict:
        """Извлекает информацию о локации из текста"""
        return self.extract_location(text, current_location)

class ContactExtractor:
    """Извлекатель контактной информации"""
    
    def extract_phones(self, text: str) -> List[str]:
        """Извлекает телефонные номера"""
        phones = set()  # Используем set для избежания дублирования
        
        # Улучшенные паттерны телефонов
        patterns = [
            r'\+996[\s\-]?([0-9\s\-]{9,12})',  # +996 с кодом
            r'0([0-9\s\-]{8,11})',  # Начинается с 0
            r'([5-7][0-9\s\-]{8,9})',  # Мобильные 5xx, 6xx, 7xx
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # Очищаем от пробелов и дефисов
                clean_number = re.sub(r'[\s\-]', '', match)
                
                # Нормализуем номер
                if len(clean_number) == 9:  # 555123456
                    normalized = f"+996{clean_number}"
                elif len(clean_number) == 10 and clean_number.startswith('0'):  # 0555123456
                    normalized = f"+996{clean_number[1:]}"
                else:
                    continue
                
                # Проверяем валидность (9 цифр после +996)
                if len(normalized) == 13 and normalized.startswith('+996'):
                    phones.add(normalized)
        
        return list(phones)
    
    def extract_phone_numbers(self, text: str) -> dict:
        """Извлекает телефонные номера и возвращает в формате словаря"""
        phones = self.extract_phones(text)
        return {'phones': phones} if phones else {}

class AmenitiesExtractor:
    """Извлекатель детальных удобств и характеристик"""
    
    def __init__(self):
        self.heating_types = {
            "Центральное": ['центральное отопление', 'централизованное', 'цо'],
            "Автономное": ['автономное', 'индивидуальное', 'котел'],
            "Газовое": ['газовое отопление', 'газ', 'газовый котел'],
            "Электрическое": ['электрическое', 'электро', 'электрокотел']
        }
        
        self.furniture_types = {
            "С мебелью": ['с мебелью', 'меблирован', 'обставлен', 'мебель есть'],
            "Без мебели": ['без мебели', 'не меблирован', 'пустая'],
            "Частично меблированная": ['частично', 'немного мебели', 'кое-что есть']
        }
        
        self.condition_types = {
            "Евроремонт": ['евроремонт', 'дизайнерский', 'элитный ремонт', 'премиум'],
            "Хорошее": ['хороший ремонт', 'отличный ремонт', 'хорошее состояние'],
            "Среднее": ['среднее состояние', 'жилое состояние', 'нормальное'],
            "Требует ремонта": ['требует ремонт', 'под ремонт', 'черновая']
        }
        
        # Детальные удобства
        self.amenities_categories = {
            'bathroom': {
                'separate': ['раздельный санузел', 'раздельный с/у', 'туалет отдельно'],
                'combined': ['совмещенный санузел', 'совмещенный с/у', 'санузел совмещен'],
                'multiple': ['два санузла', '2 санузла', 'несколько санузлов']
            },
            'balcony': {
                'balcony': ['балкон'],
                'loggia': ['лоджия'],
                'multiple': ['два балкона', '2 балкона', 'балкон и лоджия']
            },
            'parking': {
                'garage': ['гараж', 'с гаражом'],
                'parking_space': ['парковочное место', 'паркинг', 'стоянка'],
                'yard': ['во дворе', 'парковка во дворе']
            },
            'security': {
                'intercom': ['домофон'],
                'security': ['охрана', 'консьерж'],
                'video': ['видеонаблюдение', 'камеры']
            },
            'internet': {
                'internet': ['интернет', 'wi-fi', 'wifi', 'вай-фай'],
                'cable': ['кабельное тв', 'телевидение']
            },
            'appliances': {
                'kitchen': ['кухонная техника', 'плита', 'холодильник', 'духовка'],
                'washing': ['стиральная машина', 'стиралка'],
                'dishwasher': ['посудомойка', 'посудомоечная']
            }
        }
    
    def extract_amenities(self, text: str) -> Dict:
        """Извлекает все удобства и характеристики"""
        result = {}
        text_lower = text.lower()
        
        # Отопление
        result['heating'] = self._classify_by_keywords(text_lower, self.heating_types)
        
        # Мебель
        result['furniture'] = self._classify_by_keywords(text_lower, self.furniture_types)
        
        # Состояние
        result['condition'] = self._classify_by_keywords(text_lower, self.condition_types)
        
        # Детальные удобства
        amenities = {}
        for category, subcategories in self.amenities_categories.items():
            for amenity_type, keywords in subcategories.items():
                if any(keyword in text_lower for keyword in keywords):
                    if category not in amenities:
                        amenities[category] = []
                    amenities[category].append(amenity_type)
        
        if amenities:
            result['amenities'] = amenities
        
        return result
    
    def _classify_by_keywords(self, text: str, categories: Dict) -> Optional[str]:
        """Классификация по ключевым словам"""
        for category, keywords in categories.items():
            if any(keyword in text for keyword in keywords):
                return category
        return None
    
    def _classify_amenity_type(self, text: str) -> Optional[str]:
        """Классифицирует тип удобства по тексту"""
        text_lower = text.lower()
        
        # Проверяем все категории удобств
        for category, subcategories in self.amenities_categories.items():
            for amenity_type, keywords in subcategories.items():
                if any(keyword in text_lower for keyword in keywords):
                    return category
                    
        # Проверяем основные характеристики
        all_categories = {**self.heating_types, **self.furniture_types, **self.condition_types}
        for amenity_type, keywords in all_categories.items():
            if any(keyword in text_lower for keyword in keywords):
                return amenity_type.lower().replace(' ', '_')
                
        return None

# Глобальные кэши для моделей
_gliner_model = None
_e5_model = None
_extractor_instance = None

def get_cached_gliner_model():
    """Возвращает кэшированную модель GLiNER"""
    global _gliner_model
    if _gliner_model is None:
        try:
            logger.info("Loading GLiNER model for detailed data extraction...")
            from gliner import GLiNER
            _gliner_model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")
            logger.info("✅ GLiNER model loaded successfully")
        except Exception as e:
            logger.warning(f"GLiNER not available: {e}")
            _gliner_model = None
    return _gliner_model

def get_cached_e5_model():
    """Возвращает кэшированную модель E5-Large"""
    global _e5_model
    if _e5_model is None:
        try:
            logger.info("Loading E5-Large model for property type classification...")
            from sentence_transformers import SentenceTransformer
            _e5_model = SentenceTransformer('intfloat/multilingual-e5-large')
            logger.info("✅ E5-Large model loaded successfully")
        except Exception as e:
            logger.warning(f"E5-Large not available: {e}")
            _e5_model = None
    return _e5_model

def get_cached_extractor():
    """Возвращает кэшированный экземпляр экстрактора"""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = RealEstateDataExtractor()
    return _extractor_instance

class RealEstateDataExtractor:
    """Главный класс для извлечения данных недвижимости"""
    
    def __init__(self):
        """Инициализация экстрактора"""
        self.gliner_model = None
        self.e5_model = None
        self.gliner_available = False
        self.e5_available = False
        
        self._initialize_models()
        
        # Инициализируем улучшенные системы
        self.keyword_system = KeywordSystem()
        self.property_system = PropertyTypeSystem()
        self.data_validator = DataValidator()
        
        # Инициализируем модули с подходящими моделями
        # PropertyTypeClassifier всегда использует E5-Large для точности
        self.property_classifier = PropertyTypeClassifier(
            self.e5_model if self.e5_available else self.gliner_model, 
            'e5large' if self.e5_available else 'gliner'
        )
        
        # Остальные модули
        self.area_extractor = AreaExtractor()
        self.location_extractor = LocationExtractor()
        self.contact_extractor = ContactExtractor()
        self.amenities_extractor = AmenitiesExtractor()
        
        # Статистика инициализации
        system_type = "GLiNER + E5-Large + Enhanced Keywords" if self.gliner_available and self.e5_available else \
                     "GLiNER + Enhanced Keywords" if self.gliner_available else "E5-Large + Enhanced Keywords"
        
        logger.info(f"🚀 RealEstateDataExtractor инициализирован с системой: {system_type}")
        logger.info(f"📊 Ключевых слов продажи: {len(self.keyword_system.SALE_CRITICAL + self.keyword_system.SALE_STRONG)}")
        logger.info(f"📊 Ключевых слов аренды: {len(self.keyword_system.RENTAL_CRITICAL + self.keyword_system.RENTAL_STRONG)}")
        logger.info(f"📊 Типов недвижимости: {len(self.property_system.PROPERTY_TYPES)}")
        logger.info(f"📊 Кыргызских терминов: {len(self.keyword_system.KYRGYZ_TERMS)}")
        
    def _initialize_models(self):
        """Инициализация обеих моделей для гибридного подхода с кэшированием"""
        # Используем кэшированные модели
        self.gliner_model = get_cached_gliner_model()
        self.gliner_available = self.gliner_model is not None
        
        self.e5_model = get_cached_e5_model()
        self.e5_available = self.e5_model is not None
            
        # Если ни одна модель не загрузилась
        if not self.gliner_available and not self.e5_available:
            raise RuntimeError("Neither GLiNER nor E5-Large models could be loaded")
            
    def extract_comprehensive_data(self, text: str, item_data: dict = None) -> dict:
        """Комплексное извлечение данных с улучшенной системой (без типа, сделки и телефонов)"""
        try:
            result = {'original_text': text}  # Сохраняем оригинальный текст для валидации
            extraction_start = datetime.now()
            logger.info(f"🔍 Начинаем комплексное извлечение данных (текст: {len(text)} символов)")

            # 1. Извлечение площадей с улучшенными паттернами
            if self.area_extractor:
                areas = self.area_extractor.extract_areas(text)
                result.update(areas)
                if areas.get('area_sqm'):
                    logger.debug(f"📐 Площадь: {areas['area_sqm']} м²")
                if areas.get('land_area_sotka'):
                    logger.debug(f"🌿 Участок: {areas['land_area_sotka']} сот.")

            # 2. Извлечение комнат и этажей с GLiNER
            rooms_floors = self._extract_rooms_floors_with_gliner(text)
            result.update(rooms_floors)
            if rooms_floors.get('rooms'):
                logger.debug(f"🏠 Комнат: {rooms_floors['rooms']}")
            if rooms_floors.get('floor'):
                floor_info = f"Этаж: {rooms_floors['floor']}"
                if rooms_floors.get('total_floors'):
                    floor_info += f"/{rooms_floors['total_floors']}"
                logger.debug(f"🏢 {floor_info}")

            # 3. Извлечение удобств и характеристик
            if self.amenities_extractor:
                amenities = self._extract_amenities_with_gliner(text)
                result.update(amenities)
                # Извлекаем основные характеристики в отдельные поля
                if 'amenities' in amenities:
                    amenities_dict = amenities['amenities']
                    if 'heating' in amenities_dict and amenities_dict['heating']:
                        result['heating'] = amenities_dict['heating']
                        logger.debug(f"🔥 Отопление: {amenities_dict['heating']}")
                    if 'furniture' in amenities_dict and amenities_dict['furniture']:
                        result['furniture'] = amenities_dict['furniture']
                        logger.debug(f"🪑 Мебель: {amenities_dict['furniture']}")
                    if 'condition' in amenities_dict and amenities_dict['condition']:
                        result['condition'] = amenities_dict['condition']
                        logger.debug(f"🔧 Состояние: {amenities_dict['condition']}")

            # 4. Обновление локации
            if self.location_extractor and item_data:
                current_location = item_data.get('location', {})
                location_updates = self._extract_location_with_gliner(text, current_location)
                if location_updates:
                    result['location'] = location_updates
                    logger.debug(f"📍 Локация обновлена: {location_updates}")

            # 5. ВАЛИДАЦИЯ И КАЧЕСТВО
            self._validate_and_fix_data(result)
            # 6. Вычисление общего качества извлечения
            quality_score = DataValidator.calculate_quality_score(result)
            result['extraction_quality'] = quality_score
            # 7. Детали извлечения для анализа
            extraction_time = (datetime.now() - extraction_start).total_seconds()
            result['extraction_details'] = {
                'extraction_time_seconds': extraction_time,
                'text_length': len(text),
                'quality_score': quality_score,
                'timestamp': datetime.now().isoformat()
            }
            # Итоговая статистика
            extracted_fields = [k for k, v in result.items() if v is not None and k not in ['extraction_quality', 'extraction_details', 'original_text']]
            logger.info(f"✅ Извлечение завершено за {extraction_time:.2f}с. Качество: {quality_score:.2f}. Полей: {len(extracted_fields)}")
            # Удаляем служебные поля перед возвратом
            result.pop('original_text', None)
            return result
        except Exception as e:
            logger.error(f"❌ Ошибка в комплексном извлечении данных: {e}")
            return {'extraction_quality': 0.0, 'extraction_details': {'error': str(e)}}

    def extract_and_classify(self, title: str, description: str, existing_data: Dict) -> Dict:
        """Объединяет заголовок и описание и вызывает extract_comprehensive_data"""
        text = f"{title or ''} {description or ''}".strip()
        return self.extract_comprehensive_data(text, existing_data)

    def _extract_contacts_with_gliner(self, text: str) -> dict:
        """Извлечение контактов с помощью GLiNER"""
        if not self.gliner_available:
            return {}
            
        try:
            # Используем GLiNER для извлечения контактной информации
            entities = self.gliner_model.predict_entities(
                text, 
                ["телефон", "номер телефона", "контакт", "phone", "мобильный"]
            )
            
            contacts = {}
            for entity in entities:
                if entity['label'] in ['телефон', 'номер телефона', 'контакт', 'phone', 'мобильный']:
                    # Дополнительная обработка телефонных номеров
                    phone = self.contact_extractor.extract_phone_numbers(entity['text'])
                    if phone:
                        contacts.update(phone)
                        
            return contacts
            
        except Exception as e:
            logger.error(f"Error extracting contacts with GLiNER: {e}")
            return {}
            
    def _extract_amenities_with_gliner(self, text: str) -> dict:
        """Извлечение удобств с помощью GLiNER"""
        if not self.gliner_available:
            return self.amenities_extractor.extract_amenities(text)
            
        try:
            # Используем GLiNER для поиска удобств
            amenity_labels = [
                "отопление", "мебель", "состояние", "ремонт", "балкон", "лоджия",
                "парковка", "гараж", "интернет", "кондиционер", "техника"
            ]
            
            entities = self.gliner_model.predict_entities(text, amenity_labels)
            
            # Комбинируем GLiNER результаты с regex подходом
            gliner_amenities = {}
            for entity in entities:
                amenity_type = self.amenities_extractor._classify_amenity_type(entity['text'])
                if amenity_type:
                    if amenity_type not in gliner_amenities:
                        gliner_amenities[amenity_type] = []
                    gliner_amenities[amenity_type].append(entity['text'])
                    
            # Объединяем с regex результатами
            regex_amenities = self.amenities_extractor.extract_amenities(text)
            
            # Объединяем результаты
            combined_amenities = regex_amenities.copy()
            for amenity_type, values in gliner_amenities.items():
                if amenity_type in combined_amenities:
                    combined_amenities[amenity_type].extend(values)
                    combined_amenities[amenity_type] = list(set(combined_amenities[amenity_type]))
                else:
                    combined_amenities[amenity_type] = values
                    
            return {'amenities': combined_amenities} if combined_amenities else {}
            
        except Exception as e:
            logger.error(f"Error extracting amenities with GLiNER: {e}")
            return self.amenities_extractor.extract_amenities(text)
            
    def _extract_location_with_gliner(self, text: str, current_location: dict) -> dict:
        """Извлечение локации с помощью GLiNER"""
        if not self.gliner_available:
            return self.location_extractor.extract_location_info(text, current_location)
            
        try:
            # Используем GLiNER для поиска географических объектов
            location_labels = [
                "город", "район", "микрорайон", "улица", "адрес", 
                "локация", "местоположение", "где находится"
            ]
            
            entities = self.gliner_model.predict_entities(text, location_labels)
            
            # Комбинируем с regex подходом
            gliner_location = current_location.copy()
            
            for entity in entities:
                location_text = entity['text']
                # Используем существующую логику для классификации
                location_update = self.location_extractor.extract_location_info(location_text, gliner_location)
                if location_update:
                    gliner_location.update(location_update)
                    
            return gliner_location if gliner_location != current_location else {}
            
        except Exception as e:
            logger.error(f"Error extracting location with GLiNER: {e}")
            return self.location_extractor.extract_location_info(text, current_location)
            
    def _extract_rooms_floors_with_gliner(self, text: str) -> dict:
        """Извлечение комнат и этажей с помощью GLiNER"""
        result = {}
        
        try:
            if self.gliner_available:
                # Используем GLiNER для поиска комнат и этажей
                entities = self.gliner_model.predict_entities(
                    text, 
                    ["комнаты", "этаж", "комната", "этажность", "количество комнат"]
                )
                
                for entity in entities:
                    entity_text = entity['text'].lower()
                    
                    # Извлекаем количество комнат
                    rooms_match = re.search(r'(\d+)\s*комн', entity_text)
                    if rooms_match:
                        result['rooms'] = int(rooms_match.group(1))
                        
                    # Извлекаем этаж
                    floor_match = re.search(r'(\d+)\s*этаж', entity_text)
                    if floor_match:
                        result['floor'] = int(floor_match.group(1))
            
            # Дополнительное извлечение regex паттернами
            # Комнаты
            if 'rooms' not in result:
                rooms_patterns = [
                    r'(\d+)\s*комн(?:ат)?',
                    r'(\d+)-?комнатн',
                    r'(\d+)\s*к(?:омн)?\.?'
                ]
                
                for pattern in rooms_patterns:
                    match = re.search(pattern, text.lower())
                    if match:
                        rooms = int(match.group(1))
                        if 1 <= rooms <= 10:  # Разумные пределы
                            result['rooms'] = rooms
                            break
            
            # Этажи
            if 'floor' not in result:
                floor_patterns = [
                    r'(\d+)\s*этаж',
                    r'(\d+)/(\d+)',  # этаж/всего этажей
                    r'этаж\s*(\d+)'
                ]
                
                for pattern in floor_patterns:
                    match = re.search(pattern, text.lower())
                    if match:
                        if '/' in pattern:  # Формат этаж/всего
                            floor = int(match.group(1))
                            total_floors = int(match.group(2))
                            if 1 <= floor <= total_floors <= 50:
                                result['floor'] = floor
                                result['total_floors'] = total_floors
                        else:
                            floor = int(match.group(1))
                            if 1 <= floor <= 50:
                                result['floor'] = floor
                        break
                        
            return result
            
        except Exception as e:
            logger.error(f"Error extracting rooms/floors with GLiNER: {e}")
            return {}
            
    def _classify_property_origin(self, text: str) -> Optional[str]:
        """Классификация происхождения недвижимости (используется E5-Large если доступна)"""
        if not self.e5_available:
            return None
            
        try:
            # Используем E5-Large для точной классификации
            patterns = {
                'Новостройка': ['новостройка', 'от застройщика', 'первая сдача', 'сдача объекта', 'пso'],
                'Вторичная': ['вторичная', 'вторичный рынок', 'б/у', 'жилая', 'обжитая']
            }
            
            text_lower = text.lower()
            for origin, keywords in patterns.items():
                if any(keyword in text_lower for keyword in keywords):
                    return origin
                    
            return None
            
        except Exception as e:
            logger.error(f"Error classifying property origin: {e}")
            return None
    
    def _classify_listing_type(self, text: str) -> Tuple[str, float, Dict]:
        """Точная классификация типа сделки с новой системой"""
        try:
            # Используем новую систему ключевых слов
            listing_type, confidence, details = self.keyword_system.calculate_listing_type_score(text)
            
            # Логируем детали для анализа  
            logger.debug(f"📋 Классификация объявления: {listing_type} (уверенность: {confidence:.2f})")
            logger.debug(f"📊 Причины: {details.get('reasons', [])[:3]}")  # Показываем первые 3 причины
            
            return listing_type, confidence, details
            
        except Exception as e:
            logger.error(f"Error classifying listing type: {e}")
            # Fallback к простому определению
            return self._fallback_listing_type(text), 0.3, {'reasons': ['Fallback анализ']}
    
    def _fallback_listing_type(self, text: str) -> str:
        """Fallback классификация типа объявления"""
        text_lower = text.lower()
        
        # Простые ключевые слова
        if any(word in text_lower for word in ['сдаю', 'сдается', 'аренда', 'снять']):
            return "Аренда"
        elif any(word in text_lower for word in ['продаю', 'продается', 'купить', 'продажа']):
            return "Продажа"
        else:
            return "Продажа"  # По умолчанию
    
    def _validate_and_fix_data(self, result: Dict) -> None:
        """Валидация и исправление извлеченных данных"""
        issues_fixed = []
        
        # ПРИОРИТЕТ: Проверка противоречий в заголовке vs данных
        original_text = result.get('original_text', '')
        if original_text:
            # Проверка количества комнат из заголовка
            title_match = re.search(r'(\d+)\s*-?\s*комн', original_text.lower())
            if title_match:
                title_rooms = int(title_match.group(1))
                extracted_rooms = result.get('rooms')
                if extracted_rooms and extracted_rooms != title_rooms:
                    logger.warning(f"❌ Противоречие в комнатах: заголовок={title_rooms}, извлечено={extracted_rooms}")
                    result['rooms'] = title_rooms  # Приоритет заголовку
                    issues_fixed.append(f"Исправлено количество комнат: {extracted_rooms} → {title_rooms}")
            
            # Проверка типа недвижимости из заголовка
            if re.search(r'\d+\s*-?\s*комн\.\s*кв\.', original_text.lower()):
                if result.get('property_type') != 'Квартира':
                    old_type = result.get('property_type', 'None')
                    result['property_type'] = 'Квартира'
                    result['property_type_confidence'] = 0.95
                    logger.warning(f"❌ Исправлен тип недвижимости: {old_type} → Квартира")
                    issues_fixed.append(f"Исправлен тип недвижимости: {old_type} → Квартира")
        
        # Валидация и исправление площади
        if result.get('area_sqm'):
            if not self.data_validator.validate_area(result['area_sqm']):
                logger.warning(f"⚠️ Некорректная площадь: {result['area_sqm']} м²")
                if result['area_sqm'] < 5:
                    result['area_sqm'] = None
                    issues_fixed.append("Удалена слишком маленькая площадь")
                elif result['area_sqm'] > 10000:
                    result['area_sqm'] = None
                    issues_fixed.append("Удалена слишком большая площадь")
        
        # Валидация этажей
        if result.get('floor') and result.get('total_floors'):
            if result['floor'] > result['total_floors']:
                logger.warning(f"⚠️ Этаж {result['floor']} больше общего количества {result['total_floors']}")
                # Меняем местами если возможно
                if result['total_floors'] <= 50:
                    result['floor'], result['total_floors'] = result['total_floors'], result['floor']
                    issues_fixed.append("Исправлен порядок этажей")
                else:
                    result['total_floors'] = None
                    issues_fixed.append("Удалено некорректное общее количество этажей")
        
        # Валидация количества комнат
        if result.get('rooms'):
            if not self.data_validator.validate_rooms(result['rooms']):
                logger.warning(f"⚠️ Некорректное количество комнат: {result['rooms']}")
                if result['rooms'] < 1 or result['rooms'] > 20:
                    result['rooms'] = None
                    issues_fixed.append("Удалено некорректное количество комнат")
        
        # Валидация телефонов
        if result.get('phones'):
            valid_phones = []
            for phone in result['phones']:
                if self.data_validator.validate_phone(phone):
                    valid_phones.append(phone)
                else:
                    logger.warning(f"⚠️ Некорректный телефон: {phone}")
                    issues_fixed.append(f"Удален некорректный телефон: {phone}")
            
            result['phones'] = valid_phones if valid_phones else None
        
        # Логическая валидация типа недвижимости и характеристик
        self._validate_property_logic(result, issues_fixed)
        
        # Лог исправлений
        if issues_fixed:
            logger.info(f"🔧 Исправлено проблем: {len(issues_fixed)}")
            for issue in issues_fixed[:3]:  # Показываем первые 3
                logger.debug(f"   • {issue}")
    
    def _validate_property_logic(self, result: Dict, issues_fixed: List[str]) -> None:
        """Логическая валидация связей между данными"""
        
        # Правило: участок не может иметь этажи
        if result.get('property_type') == 'Земельный участок':
            if result.get('floor') or result.get('total_floors'):
                result['floor'] = None
                result['total_floors'] = None
                issues_fixed.append("Удалены этажи для земельного участка")
            
            if result.get('rooms'):
                result['rooms'] = None
                issues_fixed.append("Удалены комнаты для земельного участка")
        
        # Правило: квартира обычно имеет этаж
        if result.get('property_type') == 'Квартира':
            if result.get('total_floors') and not result.get('floor'):
                # Если указано общее количество этажей, но не указан этаж квартиры
                logger.debug("🏢 Квартира без указания этажа при известной этажности здания")
        
        # Правило: дом обычно не имеет большой этажности
        if result.get('property_type') == 'Частный дом':
            if result.get('total_floors') and result['total_floors'] > 5:
                logger.warning(f"⚠️ Частный дом с {result['total_floors']} этажами - проверить")
        
        # Правило: согласованность площадей
        if result.get('area_sqm') and result.get('living_area'):
            if result['living_area'] > result['area_sqm']:
                logger.warning(f"⚠️ Жилая площадь ({result['living_area']}) больше общей ({result['area_sqm']})")
                # Меняем местами если разница небольшая
                if result['living_area'] - result['area_sqm'] < 20:
                    result['area_sqm'], result['living_area'] = result['living_area'], result['area_sqm']
                    issues_fixed.append("Исправлен порядок площадей")
                else:
                    result['living_area'] = None
                    issues_fixed.append("Удалена некорректная жилая площадь")

# Создаем экземпляр для обратной совместимости
class AIDataExtractor(RealEstateDataExtractor):
    """Обратная совместимость с старым интерфейсом"""
    
    def extract_and_classify(self, title: str, description: str, existing_data: Dict) -> Dict:
        """Метод для обратной совместимости"""
        # Передаем existing_data как item_data для доступа к данным из конфигов
        return self.extract_comprehensive_data(f"{title} {description}".strip(), item_data=existing_data) 