# 🏠 Real Estate Parser

Полнофункциональная система парсинга и анализа объявлений о недвижимости с использованием **Scrapy**, **FastAPI** и **Elasticsearch**.

## 🚀 Возможности

### 📊 Парсинг и сбор данных
- **Мультисайтовый парсинг**: Поддержка lalafo.kg, house.kg, stroka.kg
- **API-интеграция**: Отправка данных через REST API
- **Асинхронная обработка**: Высокая производительность парсинга
- **Прокси-поддержка**: Ротация прокси для обхода блокировок

### 🔍 Система дедупликации
- **Хэширование фото**: Определение дублей по изображениям (imagehash)
- **NLP-анализ**: Семантическое сравнение текста (sentence-transformers)
- **Проверка контактов**: Анализ телефонных номеров
- **Географическая привязка**: Сравнение адресов

### 🎯 Определение риэлторов
- **Автоматическое определение**: Анализ паттернов поведения
- **Scoring система**: Оценка вероятности риэлторства
- **Статистика**: Детальная аналитика по риэлторам

### 🔎 Полнотекстовый поиск (Elasticsearch)
- **Русскоязычный поиск**: Поддержка морфологии и стемминга
- **Фильтрация**: По цене, площади, району, типу недвижимости
- **Сортировка**: По релевантности, цене, дате, количеству дублей
- **Автодополнение**: Умные подсказки адресов
- **Агрегации**: Статистика для фильтров
- **Геопоиск**: Поиск по координатам

## 🛠 Технологии

### Backend
- **FastAPI** - Современный веб-фреймворк
- **SQLAlchemy** - ORM для работы с базой данных
- **PostgreSQL** - Основная база данных
- **Redis** - Кэширование и очереди
- **Elasticsearch** - Полнотекстовый поиск
- **Kibana** - Визуализация данных Elasticsearch

### Парсинг
- **Scrapy** - Фреймворк для веб-скрапинга
- **Playwright** - Автоматизация браузера
- **Fake UserAgent** - Ротация User-Agent

### AI/ML
- **Sentence Transformers** - Семантический анализ текста
- **ImageHash** - Хэширование изображений
- **NumPy** - Математические вычисления

### Инфраструктура
- **Docker & Docker Compose** - Контейнеризация
- **Uvicorn** - ASGI сервер
- **Pydantic** - Валидация данных

## 📦 Установка

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd real_estate_parser
```

### 2. Настройка окружения
```bash
# Создание .env файла
cp .env.example .env

# Редактирование настроек
nano .env
```

### 3. Запуск через Docker Compose
```bash
# Запуск всех сервисов
docker-compose up -d

# Проверка статуса
docker-compose ps
```

### 4. Инициализация базы данных
```bash
# Создание таблиц
python create_db_tables.py

# Переиндексация Elasticsearch (после накопления данных)
python reindex_elasticsearch.py
```

## 🔧 Конфигурация

### Переменные окружения (.env)
```env
# База данных
DB_HOST=localhost
DB_PORT=5432
DB_NAME=real_estate_db
DB_USER=real_estate_user
DB_PASSWORD=your_secure_password

# Redis
REDIS_URL=redis://localhost:6379

# Elasticsearch
ELASTICSEARCH_HOSTS=http://localhost:9200
ELASTICSEARCH_INDEX=real_estate_ads

# API
API_HOST=0.0.0.0
API_PORT=8000

# Парсинг
TARGET_SITE_URL=https://lalafo.kg
PARSING_INTERVAL=3600
USE_PROXY=false
PROXY_URL=

# Дедупликация
IMAGE_HASH_THRESHOLD=5
TEXT_SIMILARITY_THRESHOLD=0.8
```

### Конфигурация парсеров
Каждый сайт имеет свой конфигурационный файл в `real_estate_scraper/real_estate_scraper/configs/`:

- `lalafo.yml` - Настройки для lalafo.kg
- `house.yml` - Настройки для house.kg  
- `stroka.yml` - Настройки для stroka.kg

## 🚀 Использование

### Запуск парсеров
```bash
# Парсинг lalafo.kg
cd real_estate_scraper
scrapy crawl lalafo

# Парсинг house.kg
scrapy crawl house

# Парсинг stroka.kg
scrapy crawl stroka

# Парсинг всех сайтов
scrapy list | xargs -n 1 scrapy crawl
```

### Запуск API
```bash
# Запуск FastAPI сервера
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Или через Docker
docker-compose up api
```

### Управление данными
```bash
# Обработка дубликатов
curl -X POST http://localhost:8000/duplicates/process

# Определение риэлторов
curl -X POST http://localhost:8000/realtors/detect

# Переиндексация Elasticsearch
curl -X POST http://localhost:8000/elasticsearch/reindex
```

## 📡 API Endpoints

### 🔍 Поиск и фильтрация (Elasticsearch)

#### Полнотекстовый поиск
```http
GET /search?q=квартира&city=Бишкек&min_price=50000&max_price=200000
```

**Параметры:**
- `q` - Поисковый запрос
- `city` - Город
- `district` - Район
- `min_price`/`max_price` - Диапазон цен
- `min_area`/`max_area` - Диапазон площади
- `rooms` - Количество комнат
- `is_realtor` - Фильтр по риэлторам
- `is_vip` - Фильтр по VIP
- `source_name` - Источник объявления
- `sort_by` - Сортировка (relevance, price, area_sqm, created_at, published_at, duplicates_count)
- `sort_order` - Порядок сортировки (asc, desc)
- `page` - Номер страницы
- `size` - Размер страницы

#### Автодополнение адресов
```http
GET /search/suggest?q=Бишкек&size=5
```

#### Агрегации для фильтров
```http
GET /search/aggregations
```

### 📊 Управление объявлениями

#### Создание объявления
```http
POST /ads
Content-Type: application/json

{
  "source_url": "https://lalafo.kg/...",
  "source_name": "lalafo",
  "title": "Продается квартира",
  "description": "Описание...",
  "price": 150000,
  "rooms": 3,
  "area_sqm": 75.5,
  "location": {
    "city": "Бишкек",
    "district": "Октябрьский",
    "address": "ул. Ленина, 1"
  }
}
```

#### Получение уникальных объявлений
```http
GET /ads/unique?city=Бишкек&is_realtor=false&limit=20
```

#### Детали объявления с дублями
```http
GET /ads/unique/{unique_ad_id}
```

### 📈 Статистика

#### Общая статистика
```http
GET /stats
```

#### Статистика Elasticsearch
```http
GET /elasticsearch/stats
```

#### Здоровье Elasticsearch
```http
GET /elasticsearch/health
```

### 🔄 Управление системой

#### Обработка дубликатов
```http
POST /duplicates/process?batch_size=100
```

#### Определение риэлторов
```http
POST /realtors/detect
```

#### Переиндексация Elasticsearch
```http
POST /elasticsearch/reindex
```

## 🗄 Структура базы данных

### Основные таблицы
- `ads` - Все объявления
- `unique_ads` - Уникальные объявления (после дедупликации)
- `locations` - Географические данные
- `photos` - Фотографии объявлений
- `duplicate_groups` - Группы дубликатов

### Ключевые поля
- `is_duplicate` - Флаг дубликата
- `is_realtor` - Флаг риэлтора
- `realtor_score` - Оценка риэлторства
- `duplicates_count` - Количество дублей
- `base_ad_id` - ID базового объявления
- `is_vip` - VIP статус

## 🔍 Система дедупликации

### Алгоритм определения дублей
1. **Хэширование фото** - Сравнение изображений через imagehash
2. **NLP-анализ** - Семантическое сравнение текста
3. **Проверка контактов** - Анализ телефонных номеров
4. **Географическая привязка** - Сравнение адресов

### Настройки порогов
- `IMAGE_HASH_THRESHOLD=5` - Порог для хэшей фото
- `TEXT_SIMILARITY_THRESHOLD=0.8` - Порог семантического сходства

## 🔎 Elasticsearch интеграция

### Возможности поиска
- **Полнотекстовый поиск** с поддержкой русского языка
- **Fuzzy matching** для опечаток
- **Фильтрация** по всем характеристикам недвижимости
- **Геопоиск** по координатам
- **Автодополнение** адресов
- **Агрегации** для построения фильтров

### Маппинг индекса
```json
{
  "title": "text (russian_analyzer)",
  "description": "text (russian_analyzer)", 
  "price": "float",
  "area_sqm": "float",
  "city": "text + keyword",
  "location": "geo_point",
  "is_realtor": "boolean",
  "duplicates_count": "integer"
}
```

### Мониторинг
- **Kibana** доступен на http://localhost:5601
- **Elasticsearch** API на http://localhost:9200
- **Статистика индекса** через `/elasticsearch/stats`

## 📊 Мониторинг и логи

### Логирование
- **API логи** - В консоли и файлах
- **Парсер логи** - В папке logs/
- **Elasticsearch логи** - В Docker контейнере

### Метрики
- Количество обработанных объявлений
- Время обработки дубликатов
- Статистика поиска
- Производительность Elasticsearch

## 🚀 Производительность

### Оптимизации
- **Асинхронная обработка** фото и дубликатов
- **Кэширование** результатов поиска
- **Батчевая обработка** дубликатов
- **Индексация** в Elasticsearch

### Масштабирование
- **Горизонтальное масштабирование** через Docker
- **Балансировка нагрузки** для API
- **Кластеризация** Elasticsearch
- **Репликация** PostgreSQL

## 🔧 Разработка

### Структура проекта
```
real_estate_parser/
├── app/                    # FastAPI приложение
│   ├── services/          # Бизнес-логика
│   ├── utils/             # Утилиты
│   └── main.py           # Основной API
├── real_estate_scraper/   # Scrapy парсеры
│   ├── configs/          # Конфигурации сайтов
│   └── spiders/          # Пауки
├── docker-compose.yml    # Docker конфигурация
└── README.md            # Документация
```

### Добавление нового сайта
1. Создать конфигурацию в `configs/`
2. Добавить селекторы для полей
3. Настроить пагинацию и фильтры
4. Протестировать парсинг

### Расширение API
1. Добавить новые модели в `models.py`
2. Создать эндпоинты в `main.py`
3. Добавить валидацию через Pydantic
4. Обновить документацию

## 🤝 Вклад в проект

1. Fork репозитория
2. Создать feature branch
3. Внести изменения
4. Добавить тесты
5. Создать Pull Request

## 📄 Лицензия

MIT License - см. файл LICENSE для деталей.

## 🆘 Поддержка

- **Issues** - Для багов и предложений
- **Discussions** - Для вопросов и обсуждений
- **Wiki** - Дополнительная документация

---

**🎉 Проект готов к использованию! Наслаждайтесь мощным поиском недвижимости!**
