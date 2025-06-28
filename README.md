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

### 📊 Веб-интерфейс управления
- **Дашборд с аналитикой** - графики, статистика, метрики в реальном времени
- **Управление автоматизацией** - настройка и мониторинг автоматических процессов
- **Просмотр объявлений** - поиск и фильтрация с удобным интерфейсом
- **Управление дубликатами** - визуализация групп и анализ эффективности


## 🛠 Технологии

### Backend
- **FastAPI** - Современный веб-фреймворк
- **SQLAlchemy** - ORM для работы с базой данных
- **Alembic** - Миграции базы данных
- **PostgreSQL** - Основная база данных
- **Redis** - Кэширование и очереди
- **Elasticsearch** - Полнотекстовый поиск

### Frontend:
- **Bootstrap 5** - UI фреймворк
- **Chart.js** - графики
- **Jinja2** - шаблоны
- **Vanilla JavaScript** - интерактивность


### Парсинг
- **Scrapy** - Фреймворк для веб-скрапинга
- **Scrapy-Playwright** - Интеграция браузера для сложных сайтов
- **Fake UserAgent** - Ротация User-Agent

### AI/ML
- **Sentence Transformers** - Семантический анализ текста
- **ImageHash** - Хэширование изображений
- **NumPy** - Математические вычисления

### Инфраструктура
- **Docker & Docker Compose** - Контейнеризация
- **Uvicorn** - ASGI сервер
- **Pydantic** - Валидация данных



## 🌐 Веб-интерфейс

Откройте браузер и перейдите по адресу `http://localhost:8000`

### 📱 Страницы интерфейса:

**🏠 Дашборд** (`/`)
- Общая статистика системы
- Графики по источникам и активности
- Последние объявления
- Эффективность дедупликации

**🤖 Автоматизация** (`/automation`)
- Управление автоматическими процессами
- Мониторинг пайплайнов
- Настройка расписания
- Статус выполнения задач

**📋 Объявления** (`/ads`)
- Поиск и фильтрация объявлений
- Детальный просмотр
- Информация о дубликатах
- Пагинация результатов


## 📦 Установка

### 1. Клонирование репозитория
```bash
git clone https://github.com/Ayturgan/estate_parser
cd real_estate_parser
```

### 2. Настройка окружения
```bash
# Создание .env файла
cp env.example .env

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

В проекте используются следующие сервисы:
- **api** — FastAPI-приложение
- **db** — PostgreSQL
- **pgadmin** — pgAdmin для управления БД
- **redis** — Redis
- **elasticsearch** — Elasticsearch
- **scrapy** — сервис для запуска парсеров

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

# Автоматизация
PIPELINE_INTERVAL_HOURS=3
SCRAPING_SOURCES=house,lalafo,stroka
ENABLE_SCRAPING=true
ENABLE_PHOTO_PROCESSING=true
ENABLE_DUPLICATE_PROCESSING=true
ENABLE_AUTOMATION=true
```

# API
API_HOST=0.0.0.0
API_PORT=8000
```

### Конфигурация парсеров
Каждый сайт имеет свой конфигурационный файл в `real_estate_scraper/real_estate_scraper/configs/`:

- `lalafo.yml` - Настройки для lalafo.kg
- `house.yml` - Настройки для house.kg
- `stroka.yml` - Настройки для stroka.kg
- `example_api.yml`, `example.yml` - Примеры для новых сайтов

### Добавление нового сайта
1. Создать конфигурацию в `configs/` (см. примеры)
2. Добавить селекторы для полей
3. Настроить пагинацию и фильтры
4. Протестировать парсинг

## 📡 API Endpoints

### 🔍 Основные API
- `GET /elasticsearch/search` - Полнотекстовый поиск с фильтрацией
- `GET /ads/unique` - Получение уникальных объявлений  
- `GET /stats` - Общая статистика системы
- `POST /ads` - Создание нового объявления

### 🔄 Обработка данных
- `POST /process/duplicates` - Запуск поиска дубликатов
- `POST /process/photos` - Обработка фотографий
- `POST /process/realtors/detect` - Определение риэлторов
- `POST /elasticsearch/reindex` - Переиндексация поиска

### 🤖 Автоматизация  
- `GET /automation/status` - Статус автоматических процессов
- `POST /automation/start` - Запуск пайплайна
- `POST /automation/stop` - Остановка пайплайна


## 📈 Мониторинг

- **Веб-интерфейс**: `http://localhost:8000`
- **API документация**: `http://localhost:8000/docs`
- **Системные метрики**: доступны через дашборд
- **Логи**: в веб-интерфейсе или через Docker logs


## 🗄 Структура базы данных

### Основные таблицы
- `ads` - Все объявления
- `unique_ads` - Уникальные объявления (после дедупликации)
- `locations` - Географические данные
- `photos` - Фотографии объявлений
- `unique_photos` - Фотографии уникальных объявлений
- `ad_duplicates` - Связки дублей

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
3. **Географическая привязка** - Сравнение адресов

### Метрики
- Количество обработанных объявлений
- Время обработки дубликатов
- Статистика поиска
- Производительность Elasticsearch

## 🔧 Разработка

### Структура проекта
```
real_estate_parser/
├── app/   
│   ├── __init__.py                              
│   ├── services/                           # Бизнес-логика
│   │   ├── automation_service.py           # Автоматизация процессов
│   │   ├── duplicate_service.py
│   │   ├── elasticsearch_service.py
│   │   ├── photo_service.py
│   │   └── scrapy_manager.py
│   ├── utils/                              # Утилиты
│   │   ├── duplicate_processor.py
│   │   └── transform.py
│   ├── migrations/                         # Миграции базы данных
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   ├── static/                  
│   │   ├── css/style.css        # Стили
│   │   └── js/                  # JavaScript файлы
│   ├── templates/               
│   │   ├── base.html            # Базовый шаблон
│   │   ├── dashboard.html       # Дашборд
│   │   ├── automation.html      # Автоматизация
│   │   └── ads.html             # Объявления
│   ├── alembic.ini
│   ├── main.py                  # FastAPI приложение
│   ├── database.py            
│   ├── db_models.py             
│   ├── web_routes.py            # Маршруты веб-интерфейса
│   └── models.py                # Pydantic модели
│
│             
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
│   │   │   └── __init__.py
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

