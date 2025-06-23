from elasticsearch import Elasticsearch
from elasticsearch_dsl import Document, Text, Integer, Float, Date, Boolean, GeoPoint, Keyword, Completion
from elasticsearch_dsl import analyzer, tokenizer
from elasticsearch_dsl import Search, Q
from typing import List, Dict, Optional, Any
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

# Кастомный анализатор для русского языка
russian_analyzer = analyzer(
    'russian_analyzer',
    tokenizer=tokenizer('standard'),
    filter=[
        'lowercase',
        'russian_stop',
        'russian_stemmer',
        'word_delimiter'
    ]
)

# Анализатор для точного поиска
exact_analyzer = analyzer(
    'exact_analyzer',
    tokenizer=tokenizer('keyword'),
    filter=['lowercase']
)

class RealEstateDocument(Document):
    """Elasticsearch документ для объявлений о недвижимости"""
    
    # Основные поля
    title = Text(
        analyzer=russian_analyzer,
        fields={
            'raw': Keyword(),
            'exact': Text(analyzer=exact_analyzer)
        }
    )
    description = Text(
        analyzer=russian_analyzer,
        fields={
            'raw': Text(analyzer=exact_analyzer)
        }
    )
    source_name = Keyword()
    source_url = Keyword()
    source_id = Keyword()
    
    # Ценовые поля
    price = Float()
    price_original = Text()
    currency = Keyword()
    
    # Характеристики недвижимости
    rooms = Integer()
    area_sqm = Float()
    floor = Integer()
    total_floors = Integer()
    series = Text(
        analyzer=russian_analyzer,
        fields={'raw': Keyword()}
    )
    building_type = Text(
        analyzer=russian_analyzer,
        fields={'raw': Keyword()}
    )
    condition = Text(
        analyzer=russian_analyzer,
        fields={'raw': Keyword()}
    )
    repair = Text(
        analyzer=russian_analyzer,
        fields={'raw': Keyword()}
    )
    furniture = Text(
        analyzer=russian_analyzer,
        fields={'raw': Keyword()}
    )
    heating = Text(
        analyzer=russian_analyzer,
        fields={'raw': Keyword()}
    )
    hot_water = Text(
        analyzer=russian_analyzer,
        fields={'raw': Keyword()}
    )
    gas = Text(
        analyzer=russian_analyzer,
        fields={'raw': Keyword()}
    )
    ceiling_height = Float()
    
    # Географические данные
    city = Text(
        analyzer=russian_analyzer,
        fields={'raw': Keyword()}
    )
    district = Text(
        analyzer=russian_analyzer,
        fields={'raw': Keyword()}
    )
    address = Text(
        analyzer=russian_analyzer,
        fields={
            'raw': Keyword(),
            'completion': Completion()
        }
    )
    location = GeoPoint()
    
    # Метаданные
    is_vip = Boolean()
    is_realtor = Boolean()
    realtor_score = Float()
    duplicates_count = Integer()
    published_at = Date()
    created_at = Date()
    
    # Агрегированные данные
    phone_numbers = Keyword(multi=True)
    photo_urls = Keyword(multi=True)
    
    # Дополнительные поля для поиска
    search_text = Text(analyzer=russian_analyzer)  # Объединенный текст для поиска
    
    class Index:
        name = 'real_estate_ads'
        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 0,
            'analysis': {
                'analyzer': {
                    'russian_analyzer': {
                        'type': 'custom',
                        'tokenizer': 'standard',
                        'filter': [
                            'lowercase',
                            'russian_stop',
                            'russian_stemmer',
                            'word_delimiter'
                        ]
                    },
                    'exact_analyzer': {
                        'type': 'custom',
                        'tokenizer': 'keyword',
                        'filter': ['lowercase']
                    }
                },
                'filter': {
                    'russian_stop': {
                        'type': 'stop',
                        'stopwords': '_russian_'
                    },
                    'russian_stemmer': {
                        'type': 'stemmer',
                        'language': 'russian'
                    }
                }
            }
        }

class ElasticsearchService:
    """Сервис для работы с Elasticsearch"""
    
    def __init__(self, hosts: List[str] = None, index_name: str = None):
        self.hosts = hosts or ['http://localhost:9200']
        self.index_name = index_name or 'real_estate_ads'
        
        # Настройка клиента
        self.client = Elasticsearch(
            self.hosts,
            timeout=30,
            max_retries=3,
            retry_on_timeout=True
        )
        
        logger.info(f"Elasticsearch client initialized with hosts: {self.hosts}")
        
    def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья Elasticsearch"""
        try:
            health = self.client.cluster.health()
            return {
                'status': health['status'],
                'number_of_nodes': health['number_of_nodes'],
                'active_primary_shards': health['active_primary_shards'],
                'active_shards': health['active_shards']
            }
        except Exception as e:
            logger.error(f"Elasticsearch health check failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def create_index(self) -> bool:
        """Создание индекса с маппингом"""
        try:
            if not self.client.indices.exists(index=self.index_name):
                self.client.indices.create(
                    index=self.index_name,
                    body={
                        'settings': {
                            'number_of_shards': 1,
                            'number_of_replicas': 0,
                            'analysis': {
                                'analyzer': {
                                    'russian_analyzer': {
                                        'type': 'custom',
                                        'tokenizer': 'standard',
                                        'filter': [
                                            'lowercase',
                                            'russian_stop',
                                            'russian_stemmer',
                                            'word_delimiter'
                                        ]
                                    },
                                    'exact_analyzer': {
                                        'type': 'custom',
                                        'tokenizer': 'keyword',
                                        'filter': ['lowercase']
                                    }
                                },
                                'filter': {
                                    'russian_stop': {
                                        'type': 'stop',
                                        'stopwords': '_russian_'
                                    },
                                    'russian_stemmer': {
                                        'type': 'stemmer',
                                        'language': 'russian'
                                    }
                                }
                            }
                        },
                        'mappings': {
                            'properties': {
                                'title': {
                                    'type': 'text',
                                    'analyzer': 'russian_analyzer',
                                    'fields': {'raw': {'type': 'keyword'}, 'exact': {'type': 'text', 'analyzer': 'exact_analyzer'}}
                                },
                                'description': {
                                    'type': 'text',
                                    'analyzer': 'russian_analyzer',
                                    'fields': {'raw': {'type': 'text', 'analyzer': 'exact_analyzer'}}
                                },
                                'source_name': {'type': 'keyword'},
                                'source_url': {'type': 'keyword'},
                                'source_id': {'type': 'keyword'},
                                'price': {'type': 'float'},
                                'price_original': {'type': 'text'},
                                'currency': {'type': 'keyword'},
                                'rooms': {'type': 'integer'},
                                'area_sqm': {'type': 'float'},
                                'floor': {'type': 'integer'},
                                'total_floors': {'type': 'integer'},
                                'series': {
                                    'type': 'text',
                                    'analyzer': 'russian_analyzer',
                                    'fields': {'raw': {'type': 'keyword'}}
                                },
                                'building_type': {
                                    'type': 'text',
                                    'analyzer': 'russian_analyzer',
                                    'fields': {'raw': {'type': 'keyword'}}
                                },
                                'condition': {
                                    'type': 'text',
                                    'analyzer': 'russian_analyzer',
                                    'fields': {'raw': {'type': 'keyword'}}
                                },
                                'repair': {
                                    'type': 'text',
                                    'analyzer': 'russian_analyzer',
                                    'fields': {'raw': {'type': 'keyword'}}
                                },
                                'furniture': {
                                    'type': 'text',
                                    'analyzer': 'russian_analyzer',
                                    'fields': {'raw': {'type': 'keyword'}}
                                },
                                'heating': {
                                    'type': 'text',
                                    'analyzer': 'russian_analyzer',
                                    'fields': {'raw': {'type': 'keyword'}}
                                },
                                'hot_water': {
                                    'type': 'text',
                                    'analyzer': 'russian_analyzer',
                                    'fields': {'raw': {'type': 'keyword'}}
                                },
                                'gas': {
                                    'type': 'text',
                                    'analyzer': 'russian_analyzer',
                                    'fields': {'raw': {'type': 'keyword'}}
                                },
                                'ceiling_height': {'type': 'float'},
                                'city': {
                                    'type': 'text',
                                    'analyzer': 'russian_analyzer',
                                    'fields': {'raw': {'type': 'keyword'}}
                                },
                                'district': {
                                    'type': 'text',
                                    'analyzer': 'russian_analyzer',
                                    'fields': {'raw': {'type': 'keyword'}}
                                },
                                'address': {
                                    'type': 'text',
                                    'analyzer': 'russian_analyzer',
                                    'fields': {
                                        'raw': {'type': 'keyword'},
                                        'completion': {'type': 'completion'}
                                    }
                                },
                                'location': {'type': 'geo_point'},
                                'is_vip': {'type': 'boolean'},
                                'is_realtor': {'type': 'boolean'},
                                'realtor_score': {'type': 'float'},
                                'duplicates_count': {'type': 'integer'},
                                'published_at': {'type': 'date'},
                                'created_at': {'type': 'date'},
                                'phone_numbers': {'type': 'keyword'},
                                'photo_urls': {'type': 'keyword'},
                                'search_text': {'type': 'text', 'analyzer': 'russian_analyzer'}
                            }
                        }
                    }
                )
                logger.info(f"Index {self.index_name} created successfully")
            else:
                logger.info(f"Index {self.index_name} already exists")
            return True
        except Exception as e:
            logger.error(f"Error creating index: {e}")
            return False
    
    def index_ad(self, ad_data: Dict) -> bool:
        """Индексация объявления"""
        try:
            # Подготовка данных для индексации
            search_text_parts = []
            
            # Добавляем основные текстовые поля в поисковый текст
            if ad_data.get('title'):
                search_text_parts.append(ad_data['title'])
            if ad_data.get('description'):
                search_text_parts.append(ad_data['description'])
            
            # Проверяем 'location' перед доступом к его полям
            location_data = ad_data.get('location')
            if location_data and location_data.get('address'):
                search_text_parts.append(location_data['address'])
            
            if ad_data.get('series'):
                search_text_parts.append(ad_data['series'])
            if ad_data.get('building_type'):
                search_text_parts.append(ad_data['building_type'])
            
            # Создаем документ для индексации
            doc_data = {
                'title': ad_data.get('title', ''),
                'description': ad_data.get('description', ''),
                'source_name': ad_data.get('source_name', ''),
                'source_url': ad_data.get('source_url', ''),
                'source_id': ad_data.get('source_id', ''),
                'price': ad_data.get('price'),
                'price_original': ad_data.get('price_original', ''),
                'currency': ad_data.get('currency', 'USD'),
                'rooms': ad_data.get('rooms'),
                'area_sqm': ad_data.get('area_sqm'),
                'floor': ad_data.get('floor'),
                'total_floors': ad_data.get('total_floors'),
                'series': ad_data.get('series', ''),
                'building_type': ad_data.get('building_type', ''),
                'condition': ad_data.get('condition', ''),
                'repair': ad_data.get('repair', ''),
                'furniture': ad_data.get('furniture', ''),
                'heating': ad_data.get('heating', ''),
                'hot_water': ad_data.get('hot_water', ''),
                'gas': ad_data.get('gas', ''),
                'ceiling_height': ad_data.get('ceiling_height'),
                'city': location_data.get('city', '') if location_data else '',
                'district': location_data.get('district', '') if location_data else '',
                'address': location_data.get('address', '') if location_data else '',
                'is_vip': ad_data.get('is_vip', False),
                'is_realtor': ad_data.get('is_realtor', False),
                'realtor_score': ad_data.get('realtor_score'),
                'duplicates_count': ad_data.get('duplicates_count', 0),
                'published_at': ad_data.get('published_at'),
                'created_at': ad_data.get('created_at'),
                'phone_numbers': ad_data.get('phone_numbers', []),
                'photo_urls': [photo['url'] for photo in ad_data.get('photos', []) if photo and 'url' in photo],
                'search_text': ' '.join(search_text_parts)
            }
            
            # Добавляем location только если есть данные для GeoPoint
            if location_data and location_data.get('lat') is not None and location_data.get('lon') is not None:
                doc_data['location'] = {
                    'lat': location_data['lat'],
                    'lon': location_data['lon']
                }
            else:
                doc_data['location'] = None # Устанавливаем None, если нет координат

            # Удаляем поля со значением None, чтобы Elasticsearch использовал значения по умолчанию или игнорировал их
            doc_data_cleaned = {k: v for k, v in doc_data.items() if v is not None}

            # Индексируем документ
            self.client.index(
                index=self.index_name,
                id=ad_data['id'],
                document=doc_data_cleaned
            )
            logger.info(f"Ad {ad_data['id']} indexed successfully")
            return True
        except Exception as e:
            logger.error(f"Error indexing ad {ad_data.get('id', 'N/A')}: {e}")
            return False

    def reindex_all(self, ads_data: List[Dict]) -> bool:
        """Переиндексация всех объявлений"""
        try:
            # Удаляем старый индекс, если он существует
            if self.client.indices.exists(index=self.index_name):
                self.client.indices.delete(index=self.index_name)
                logger.info(f"Old index {self.index_name} deleted")
            
            # Создаем новый индекс с актуальным маппингом
            self.create_index()
            
            # Индексируем каждое объявление
            success_count = 0
            for ad in ads_data:
                if self.index_ad(ad):
                    success_count += 1
            
            logger.info(f"Successfully reindexed {success_count} out of {len(ads_data)} ads")
            return success_count == len(ads_data)
        except Exception as e:
            logger.error(f"Error during reindexing all ads: {e}")
            return False

    def search_ads(self, query: str = None, filters: Dict = None, sort_by: str = "relevance", sort_order: str = "desc", page: int = 1, size: int = 10) -> Dict:
        """Поиск объявлений с поддержкой сортировки и пагинации"""
        s = Search(using=self.client, index=self.index_name)
        
        if query:
            s = s.query(
                Q(
                    'multi_match',
                    query=query,
                    fields=['title^3', 'description', 'search_text^2', 'address.raw^1.5', 'city.raw', 'district.raw'],
                    fuzziness='AUTO'
                )
            )
        
        # Обработка диапазона цены только по полю price
        price_range = {}
        if filters:
            if 'min_price' in filters:
                price_range['gte'] = filters['min_price']
            if 'max_price' in filters:
                price_range['lte'] = filters['max_price']
            # Удаляем min_price и max_price из filters, чтобы не было попытки фильтровать по несуществующим полям
            filters = {k: v for k, v in filters.items() if k not in ['min_price', 'max_price']}
        if price_range:
            s = s.filter('range', price=price_range)
        # Остальные фильтры только по существующим полям
        if filters:
            for key, value in filters.items():
                s = s.filter('term', **{key: value})
        
        # Сортировка
        if sort_by != "relevance":
            order = '-' if sort_order == 'desc' else ''
            s = s.sort(f"{order}{sort_by}")
        # Пагинация
        from_ = (page - 1) * size
        s = s.extra(from_=from_, size=size)
        
        response = s.execute()
        
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def get_aggregations(self) -> Dict:
        """Получение агрегаций по полям"""
        s = Search(using=self.client, index=self.index_name)
        
        s.aggs.bucket('cities', 'terms', field='city.raw', size=10)
        s.aggs.bucket('rooms', 'terms', field='rooms', size=5)
        s.aggs.bucket('building_types', 'terms', field='building_type.raw', size=10)
        
        response = s.execute()
        
        return {
            agg_name: [bucket.to_dict() for bucket in response.aggregations[agg_name].buckets]
            for agg_name in response.aggregations.keys()
        }

    def suggest_addresses(self, prefix: str, size: int = 5) -> List[str]:
        """Автодополнение адресов"""
        s = Search(using=self.client, index=self.index_name)
        s = s.suggest('address_suggest', prefix, completion={'field': 'address.completion', 'size': size})
        response = s.execute()
        
        suggestions = []
        for option in response.suggest.address_suggest[0].options:
            suggestions.append(option.text)
            
        return suggestions

    def get_stats(self) -> Dict:
        """Получение статистики по индексу"""
        try:
            stats = self.client.indices.stats(index=self.index_name)
            return stats['indices'][self.index_name]['total']
        except Exception as e:
            logger.error(f"Error getting index stats: {e}")
            return {}

    def delete_index(self) -> bool:
        """Удаление индекса"""
        try:
            if self.client.indices.exists(index=self.index_name):
                self.client.indices.delete(index=self.index_name)
                logger.info(f"Index {self.index_name} deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Error deleting index: {e}")
            return False

    def get_ad_by_id(self, ad_id: str) -> Optional[Dict]:
        """Получение объявления по ID"""
        try:
            response = self.client.get(index=self.index_name, id=ad_id)
            return response['_source']
        except Exception as e:
            logger.error(f"Error getting ad by ID {ad_id}: {e}")
            return None

    def update_ad(self, ad_id: str, update_data: Dict) -> bool:
        """Обновление объявления по ID"""
        try:
            self.client.update(index=self.index_name, id=ad_id, doc=update_data)
            logger.info(f"Ad {ad_id} updated successfully")
            return True
        except Exception as e:
            logger.error(f"Error updating ad {ad_id}: {e}")
            return False

    def delete_ad(self, ad_id: str) -> bool:
        """Удаление объявления по ID"""
        try:
            self.client.delete(index=self.index_name, id=ad_id)
            logger.info(f"Ad {ad_id} deleted successfully")
            return True
        except Exception as e:
            logger.error(f"Error deleting ad {ad_id}: {e}")
            return False

    def count_ads(self) -> int:
        """Подсчет количества объявлений в индексе"""
        try:
            response = self.client.count(index=self.index_name)
            return response['count']
        except Exception as e:
            logger.error(f"Error counting ads: {e}")
            return 0

    def bulk_index(self, actions: List[Dict]) -> bool:
        """Массовая индексация объявлений"""
        from elasticsearch.helpers import bulk
        try:
            success, failed = bulk(self.client, actions, index=self.index_name, raise_on_error=False)
            if failed:
                logger.error(f"Bulk indexing failed for {len(failed)} documents: {failed}")
            logger.info(f"Bulk indexing successful for {success} documents")
            return len(failed) == 0
        except Exception as e:
            logger.error(f"Error during bulk indexing: {e}")
            return False

    def get_all_ads(self, size: int = 10000) -> List[Dict]:
        """Получение всех объявлений из индекса (с пагинацией)"""
        s = Search(using=self.client, index=self.index_name).query("match_all").extra(size=size)
        response = s.execute()
        return [hit.to_dict() for hit in response.hits]

    def search_by_geo_distance(self, lat: float, lon: float, distance: str, size: int = 10) -> Dict:
        """Поиск объявлений по географическому расстоянию"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query(
            'geo_distance',
            distance=distance,
            location={'lat': lat, 'lon': lon}
        )
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_geo_bounding_box(self, top_left: Dict, bottom_right: Dict, size: int = 10) -> Dict:
        """Поиск объявлений по географическому прямоугольнику"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query(
            'geo_bounding_box',
            location={
                'top_left': top_left,
                'bottom_right': bottom_right
            }
        )
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_price_range(self, min_price: Optional[float] = None, max_price: Optional[float] = None, size: int = 10) -> Dict:
        """Поиск объявлений по диапазону цен"""
        s = Search(using=self.client, index=self.index_name)
        price_range = {}
        if min_price is not None:
            price_range['gte'] = min_price
        if max_price is not None:
            price_range['lte'] = max_price
        
        if price_range:
            s = s.query('range', price=price_range)
        
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_rooms(self, rooms: int, size: int = 10) -> Dict:
        """Поиск объявлений по количеству комнат"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', rooms=rooms)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_source_name(self, source_name: str, size: int = 10) -> Dict:
        """Поиск объявлений по названию источника"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', source_name=source_name)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_created_at_range(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, size: int = 10) -> Dict:
        """Поиск объявлений по диапазону дат создания"""
        s = Search(using=self.client, index=self.index_name)
        date_range = {}
        if start_date is not None:
            date_range['gte'] = start_date.isoformat()
        if end_date is not None:
            date_range['lte'] = end_date.isoformat()
        
        if date_range:
            s = s.query('range', created_at=date_range)
        
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_published_at_range(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, size: int = 10) -> Dict:
        """Поиск объявлений по диапазону дат публикации"""
        s = Search(using=self.client, index=self.index_name)
        date_range = {}
        if start_date is not None:
            date_range['gte'] = start_date.isoformat()
        if end_date is not None:
            date_range['lte'] = end_date.isoformat()
        
        if date_range:
            s = s.query('range', published_at=date_range)
        
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_is_vip(self, is_vip: bool, size: int = 10) -> Dict:
        """Поиск VIP объявлений"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', is_vip=is_vip)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_is_realtor(self, is_realtor: bool, size: int = 10) -> Dict:
        """Поиск объявлений от риелторов"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', is_realtor=is_realtor)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_realtor_score_range(self, min_score: Optional[float] = None, max_score: Optional[float] = None, size: int = 10) -> Dict:
        """Поиск объявлений по диапазону рейтинга риелтора"""
        s = Search(using=self.client, index=self.index_name)
        score_range = {}
        if min_score is not None:
            score_range['gte'] = min_score
        if max_score is not None:
            score_range['lte'] = max_score
        
        if score_range:
            s = s.query('range', realtor_score=score_range)
        
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_duplicates_count_range(self, min_count: Optional[int] = None, max_count: Optional[int] = None, size: int = 10) -> Dict:
        """Поиск объявлений по диапазону количества дубликатов"""
        s = Search(using=self.client, index=self.index_name)
        count_range = {}
        if min_count is not None:
            count_range['gte'] = min_count
        if max_count is not None:
            count_range['lte'] = max_count
        
        if count_range:
            s = s.query('range', duplicates_count=count_range)
        
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_area_range(self, min_area: Optional[float] = None, max_area: Optional[float] = None, size: int = 10) -> Dict:
        """Поиск объявлений по диапазону площади"""
        s = Search(using=self.client, index=self.index_name)
        area_range = {}
        if min_area is not None:
            area_range['gte'] = min_area
        if max_area is not None:
            area_range['lte'] = max_area
        
        if area_range:
            s = s.query('range', area_sqm=area_range)
        
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_floor_range(self, min_floor: Optional[int] = None, max_floor: Optional[int] = None, size: int = 10) -> Dict:
        """Поиск объявлений по диапазону этажей"""
        s = Search(using=self.client, index=self.index_name)
        floor_range = {}
        if min_floor is not None:
            floor_range['gte'] = min_floor
        if max_floor is not None:
            floor_range['lte'] = max_floor
        
        if floor_range:
            s = s.query('range', floor=floor_range)
        
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_total_floors_range(self, min_total_floors: Optional[int] = None, max_total_floors: Optional[int] = None, size: int = 10) -> Dict:
        """Поиск объявлений по диапазону общего количества этажей"""
        s = Search(using=self.client, index=self.index_name)
        total_floors_range = {}
        if min_total_floors is not None:
            total_floors_range['gte'] = min_total_floors
        if max_total_floors is not None:
            total_floors_range['lte'] = max_total_floors
        
        if total_floors_range:
            s = s.query('range', total_floors=total_floors_range)
        
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_ceiling_height_range(self, min_height: Optional[float] = None, max_height: Optional[float] = None, size: int = 10) -> Dict:
        """Поиск объявлений по диапазону высоты потолков"""
        s = Search(using=self.client, index=self.index_name)
        height_range = {}
        if min_height is not None:
            height_range['gte'] = min_height
        if max_height is not None:
            height_range['lte'] = max_height
        
        if height_range:
            s = s.query('range', ceiling_height=height_range)
        
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_condition(self, condition: str, size: int = 10) -> Dict:
        """Поиск объявлений по состоянию"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', condition=condition)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_repair(self, repair: str, size: int = 10) -> Dict:
        """Поиск объявлений по ремонту"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', repair=repair)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_furniture(self, furniture: str, size: int = 10) -> Dict:
        """Поиск объявлений по мебели"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', furniture=furniture)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_heating(self, heating: str, size: int = 10) -> Dict:
        """Поиск объявлений по отоплению"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', heating=heating)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_hot_water(self, hot_water: str, size: int = 10) -> Dict:
        """Поиск объявлений по горячей воде"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', hot_water=hot_water)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_gas(self, gas: str, size: int = 10) -> Dict:
        """Поиск объявлений по газу"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', gas=gas)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_city(self, city: str, size: int = 10) -> Dict:
        """Поиск объявлений по городу"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', city=city)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_district(self, district: str, size: int = 10) -> Dict:
        """Поиск объявлений по району"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', district=district)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_address(self, address: str, size: int = 10) -> Dict:
        """Поиск объявлений по адресу"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('match', address=address)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_phone_number(self, phone_number: str, size: int = 10) -> Dict:
        """Поиск объявлений по номеру телефона"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', phone_numbers=phone_number)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_photo_url(self, photo_url: str, size: int = 10) -> Dict:
        """Поиск объявлений по URL фотографии"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', photo_urls=photo_url)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_source_id(self, source_id: str, size: int = 10) -> Dict:
        """Поиск объявлений по ID источника"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', source_id=source_id)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_source_url(self, source_url: str, size: int = 10) -> Dict:
        """Поиск объявлений по URL источника"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', source_url=source_url)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_series(self, series: str, size: int = 10) -> Dict:
        """Поиск объявлений по серии"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', series=series)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_building_type(self, building_type: str, size: int = 10) -> Dict:
        """Поиск объявлений по типу здания"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', building_type=building_type)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_currency(self, currency: str, size: int = 10) -> Dict:
        """Поиск объявлений по валюте"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('term', currency=currency)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_price_original(self, price_original: str, size: int = 10) -> Dict:
        """Поиск объявлений по оригинальной цене"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('match', price_original=price_original)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }

    def search_by_search_text(self, search_text: str, size: int = 10) -> Dict:
        """Поиск объявлений по объединенному тексту для поиска"""
        s = Search(using=self.client, index=self.index_name)
        s = s.query('match', search_text=search_text)
        s = s.extra(size=size)
        response = s.execute()
        return {
            'total': response.hits.total.value,
            'hits': [hit.to_dict() for hit in response.hits]
        }


