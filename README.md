# 🏠 Real Estate Parser

Полнофункциональная система парсинга и анализа объявлений о недвижимости с использованием **Scrapy**, **FastAPI** и **Elasticsearch**.

## 🚀 Возможности

### 📊 Парсинг и сбор данных
- **Мультисайтовый парсинг**: Поддержка lalafo.kg, house.kg, stroka.kg
- **API-интеграция**: Отправка данных через REST API
- **Асинхронная обработка**: Высокая производительность парсинга

### 🔍 Система дедупликации
- **Хэширование фото**: Определение дублей по изображениям (imagehash)
- **NLP-анализ**: Семантическое сравнение текста (sentence-transformers)
- **Географическая привязка**: Сравнение адресов

### 🎯 Определение риэлторов
- **Автоматическое определение**: Анализ паттернов поведения
- **Scoring система**: Оценка вероятности риэлторства

### 🔎 Полнотекстовый поиск (Elasticsearch)
- **Русскоязычный поиск**: Поддержка морфологии и стемминга
- **Фильтрация**: По цене, площади, району, типу недвижимости
- **Сортировка**: По релевантности, цене, дате, количеству дублей

## 🛠 Технологии

### Backend
- **FastAPI** - Современный веб-фреймворк
- **SQLAlchemy** - ORM для работы с базой данных
- **PostgreSQL** - Основная база данных
- **Redis** - Кэширование и очереди
- **Elasticsearch** - Полнотекстовый поиск

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
git clone https://github.com/Ayturgan/estate_parser
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
docker-compose up --build -d

# Проверка статуса
docker ps
```

### 4. Инициализация базы данных
```bash
# Создание таблиц
python create_db_tables.py

## 🔧 Конфигурация

### Переменные окружения (.env)
```env
# База данных
DB_HOST=db
DB_PORT=5432
DB_NAME=real_estate_db
DB_USER=real_estate_user
DB_PASSWORD=your_secure_password

# Redis
REDIS_URL=redis://redis:6379

# Elasticsearch
ELASTICSEARCH_HOSTS=http://elasticsearch:9200
ELASTICSEARCH_INDEX=real_estate_ads

# API
API_HOST=0.0.0.0
API_PORT=8000

```

### Конфигурация парсеров
Каждый сайт имеет свой конфигурационный файл в `real_estate_scraper/real_estate_scraper/configs/`:

- `lalafo.yml` - Настройки для lalafo.kg
- `house.yml` - Настройки для house.kg  
- `stroka.yml` - Настройки для stroka.kg


### Добавление нового сайта
1. Создать конфигурацию в `configs/` (примеры: example_api.yml и example.yml)
2. Добавить селекторы для полей
3. Настроить пагинацию и фильтры
4. Протестировать парсинг


## 🚀 Использование

### Запуск парсеров
```bash
# Парсинг lalafo.kg
cd real_estate_scraper
scrapy crawl generic_api -a config=lalafo

# Парсинг house.kg
scrapy crawl generic_scraper -a config=house

# Парсинг stroka.kg
scrapy crawl generic_scraper -a config=stroka

```

### Запуск API
```bash
# Запуск FastAPI сервера
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Или через Docker
docker-compose up api
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

### Ключевые поля
- `is_duplicate` - Флаг дубликата
- `is_realtor` - Флаг риэлтора
- `realtor_score` - Оценка риэлторства
- `duplicates_count` - Количество дублей
- `base_ad_id` - ID базового объявления

## 🔍 Система дедупликации

### Алгоритм определения дублей
1. **Хэширование фото** - Сравнение изображений через imagehash
2. **NLP-анализ** - Семантическое сравнение текста
4. **Географическая привязка** - Сравнение адресов


### Метрики
- Количество обработанных объявлений
- Время обработки дубликатов
- Статистика поиска
- Производительность Elasticsearch

## 🔧 Разработка

### Структура проекта
```
real_estate_parser/
├── app/                                    # FastAPI приложение
│   ├── services/                           # Бизнес-логика
│   │   ├── duplicate_service.py
│   │   ├── elasticsearch_service.py
│   │   └── photo_service.py
│   ├── utils/                              # Утилиты
│   │   ├── duplicate_processor.py
│   │   └── transform.py
│   ├── migrations/                         # Миграции базы данных
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   ├── __init__.py
│   ├── alembic.ini
│   ├── database.py
│   ├── db_models.py
│   ├── main.py
│   └── models.py
├── real_estate_scraper/                    # Scrapy парсеры
│   ├── real_estate_scraper/
│   │   ├── configs/                        # Конфигурации сайтов
│   │   │   ├── example_api.yml
│   │   │   ├── house.yml
│   │   │   ├── lalafo.yml
│   │   │   └── stroka.yml
│   │   ├── parsers/                        # Парсеры
│   │   │   └── loader.py
│   │   ├── spiders/                        # Пауки
│   │   │   ├── generic_api_spider.py
│   │   │   ├── generic_spider.py
│   │   │   └── test.py
│   │   ├── __init__.py
│   │   ├── items.py
│   │   ├── middlewares.py
│   │   ├── pipelines.py
│   │   ├── proxy_config.py
│   │   ├── settings.py
│   │   └── user_agents.py
│   └── scrapy.cfg
├── config.py                 # Конфигурация приложения
├── docker-compose.yml        # Docker конфигурация
├── Dockerfile                # Docker образ
├── env.example               # Пример переменных окружения
├── pyproject.toml            # Зависимости Python
├── uv.lock                   # Lock файл зависимостей
└── README.md                 # Документация
```

## 📄 Лицензия

MIT License - см. файл LICENSE для деталей.