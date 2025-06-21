# Real Estate Parser & Aggregator

Современная система для парсинга, агрегации и дедупликации объявлений о недвижимости с поддержкой множественных источников данных.

## 🏗️ Архитектура

Проект состоит из двух основных компонентов:

### 1. **Scrapy Parser** (`real_estate_scraper/`)
- Универсальный парсер на базе Scrapy с поддержкой Playwright
- Поддержка API и HTML парсинга
- Конфигурируемые селекторы для разных сайтов
- Автоматическое определение дубликатов

### 2. **FastAPI Backend** (`app/`)
- REST API для управления данными
- Система дедупликации с ML-алгоритмами
- Определение риэлторов
- Кэширование и оптимизация запросов

## 🚀 Возможности

### Парсинг
- **Множественные источники**: house.kg, lalafo.kg, stroka.kg
- **Гибкая конфигурация**: YAML-файлы для каждого сайта
- **Playwright поддержка**: для динамического контента
- **API и HTML парсинг**: универсальные спайдеры

### Дедупликация
- **Фото-сравнение**: perceptual hashing изображений
- **Текстовый анализ**: sentence transformers для сравнения описаний
- **Контактная информация**: анализ телефонных номеров
- **Географические данные**: сравнение адресов
- **ML-алгоритмы**: комплексная оценка схожести

### API
- **RESTful интерфейс**: полный CRUD для объявлений
- **Фильтрация и поиск**: по цене, площади, району, риэлторам
- **Пагинация**: эффективная работа с большими объемами
- **Кэширование**: Redis + in-memory кэш
- **Статистика**: детальная аналитика по данным

### Определение риэлторов
- **Автоматическое определение**: на основе паттернов в объявлениях
- **Scoring система**: оценка вероятности
- **Фильтрация**: отдельные эндпоинты для риэлторов/собственников

## 🛠️ Технологии

### Backend
- **FastAPI** - современный веб-фреймворк
- **SQLAlchemy** - ORM для работы с БД
- **PostgreSQL** - основная база данных
- **Redis** - кэширование и очереди
- **Pydantic** - валидация данных

### Парсинг
- **Scrapy** - фреймворк для парсинга
- **Playwright** - автоматизация браузера
- **Pillow** - обработка изображений
- **imagehash** - хэширование фото

### ML & AI
- **sentence-transformers** - векторные представления текста
- **numpy** - численные вычисления
- **scikit-learn** - машинное обучение

### DevOps
- **Docker & Docker Compose** - контейнеризация
- **PostgreSQL** - база данных
- **pgAdmin** - веб-интерфейс для БД

## 📦 Установка

### Предварительные требования
- Python 3.10+
- Docker & Docker Compose
- Git

### Быстрый старт

1. **Клонирование репозитория**
```bash
git clone <repository-url>
cd real_estate_parser
```

2. **Запуск через Docker Compose**
```bash
docker-compose up -d
```

3. **Создание таблиц БД**
```bash
python create_db_tables.py
```

4. **Запуск API сервера**
```bash
cd app
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Ручная установка

1. **Установка зависимостей**
```bash
pip install -r requirements.txt
```

2. **Настройка переменных окружения**
```bash
cp .env.example .env
# Отредактируйте .env файл
```

3. **Запуск PostgreSQL и Redis**
```bash
docker-compose up db redis -d
```

## 🔧 Конфигурация

### Переменные окружения (.env)
```env
# База данных
DB_HOST=localhost
DB_PORT=5432
DB_NAME=real_estate_db
DB_USER=real_estate_user
DB_PASSWORD=your_password

# Redis
REDIS_URL=redis://localhost:6379

# API
API_HOST=0.0.0.0
API_PORT=8000

# Парсинг
TARGET_SITE_URL=https://example.com
PARSING_INTERVAL=3600

# Прокси (опционально)
USE_PROXY=false
PROXY_URL=

# Настройки дедупликации
IMAGE_HASH_THRESHOLD=5
TEXT_SIMILARITY_THRESHOLD=0.8
```

### Конфигурация парсеров

Каждый сайт имеет свой YAML-конфиг в `real_estate_scraper/real_estate_scraper/configs/`:

```yaml
# Пример: lalafo.yml
api_url: "https://lalafo.kg/api/search/v3/feed/search"
field_mapping:
  title: "title"
  description: "description"
  price: "price"
  # ... другие поля
```

## 🚀 Использование

### Запуск парсера

```bash
# Парсинг конкретного сайта
cd real_estate_scraper
scrapy crawl generic_api -a config=lalafo

# Парсинг HTML сайта
scrapy crawl generic_spider -a config=house
```

### API Endpoints

#### Основные эндпоинты
- `GET /` - информация о сервисе
- `GET /status` - статус системы
- `GET /stats` - статистика

#### Управление объявлениями
- `POST /ads` - создание объявления
- `GET /ads/unique` - список уникальных объявлений
- `GET /ads/unique/{id}` - детали уникального объявления
- `GET /ads/unique/{id}/sources` - источники объявления

#### Обработка дубликатов
- `POST /duplicates/process` - запуск обработки дубликатов
- `POST /realtors/detect` - определение риэлторов

### Примеры запросов

```bash
# Получение уникальных объявлений
curl "http://localhost:8000/ads/unique?city=Бишкек&min_price=50000&max_price=100000"

# Создание объявления
curl -X POST "http://localhost:8000/ads" \
  -H "Content-Type: application/json" \
  -d '{
    "source_url": "https://example.com/ad/123",
    "source_name": "lalafo.kg",
    "title": "2-комнатная квартира",
    "price": 75000,
    "currency": "USD"
  }'

# Запуск обработки дубликатов
curl -X POST "http://localhost:8000/duplicates/process"
```

## 📊 Структура базы данных

### Основные таблицы
- `ads` - исходные объявления
- `unique_ads` - уникальные объявления (после дедупликации)
- `locations` - географические данные
- `photos` - фотографии объявлений
- `ad_duplicates` - связи между дубликатами

### Ключевые поля
- `is_vip` - VIP-статус объявления
- `is_realtor` - флаг риэлтора
- `realtor_score` - оценка вероятности риэлтора
- `duplicates_count` - количество дубликатов
- `confidence_score` - уверенность в уникальности

## 🔍 Система дедупликации

### Алгоритм работы
1. **Извлечение признаков**:
   - Хэширование фотографий (perceptual hash)
   - Векторизация текста (sentence transformers)
   - Нормализация контактов и адресов

2. **Сравнение объявлений**:
   - Фото-схожесть (Hamming distance)
   - Текстовая схожесть (cosine similarity)
   - Контактная схожесть
   - Адресная схожесть

3. **Объединение дубликатов**:
   - Создание уникального объявления
   - Связывание с исходными объявлениями
   - Сохранение метрик схожести

### Настройка порогов
```env
IMAGE_HASH_THRESHOLD=5      # Порог схожести фото (0-64)
TEXT_SIMILARITY_THRESHOLD=0.8  # Порог текстовой схожести (0-1)
```

## 🧪 Тестирование

```bash
# Запуск тестового паука
cd real_estate_scraper
scrapy crawl test

# Проверка API
curl http://localhost:8000/status
```

## 📈 Мониторинг

### Логи
- Scrapy логи: `real_estate_scraper/logs/`
- API логи: консоль uvicorn
- База данных: pgAdmin (http://localhost:5050)

### Метрики
- Количество объявлений
- Процент дедупликации
- Время обработки
- Количество риэлторов

## 🔧 Разработка

### Структура проекта
```
real_estate_parser/
├── app/                    # FastAPI приложение
│   ├── main.py            # Основной API
│   ├── models.py          # Pydantic модели
│   ├── db_models.py       # SQLAlchemy модели
│   ├── services/          # Бизнес-логика
│   └── utils/             # Утилиты
├── real_estate_scraper/   # Scrapy парсер
│   ├── spiders/           # Пауки
│   ├── configs/           # Конфигурации сайтов
│   └── pipelines.py       # Обработка данных
├── docker-compose.yml     # Docker конфигурация
└── config.py             # Настройки приложения
```

### Добавление нового сайта
1. Создайте конфиг в `configs/`
2. Настройте селекторы полей
3. Протестируйте парсинг
4. При необходимости добавьте новые поля в модели

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

## 📄 Лицензия

MIT License

## 📞 Поддержка

- Issues: GitHub Issues
- Документация: встроенная Swagger UI (http://localhost:8000/docs)
- API Reference: http://localhost:8000/redoc

---

**Версия**: 1.0.0  
**Python**: 3.10+  
**Статус**: Production Ready
