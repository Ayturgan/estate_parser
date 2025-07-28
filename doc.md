# 🏠 Estate Parser - Парсер недвижимости

Современная система парсинга и анализа объявлений о недвижимости с использованием микросервисной архитектуры на FastAPI и Scrapy.

## 📁 Структура проекта

```
estate_parser/
├── backend/                    # Backend API сервис (FastAPI)
│   ├── app/
│   │   ├── core/              # Конфигурация и ядро
│   │   ├── database/          # Модели БД и миграции
│   │   ├── services/          # Бизнес-логика сервисов
│   │   ├── static/            # Статические файлы (CSS, JS)
│   │   ├── templates/         # HTML шаблоны
│   │   ├── utils/             # Утилиты
│   │   ├── websocket/         # WebSocket обработчики
│   │   ├── main.py            # Основной файл FastAPI приложения
│   │   ├── web_routes.py      # Веб-маршруты
│   │   └── alembic.ini        # Конфигурация миграций
│   ├── Dockerfile             # Docker образ для backend
│   ├── requirements.txt       # Зависимости backend
│   └── pyproject.toml        # Конфигурация проекта
├── scraper/                   # Scraper сервис (Scrapy)
│   ├── estate_scraper/
│   │   ├── real_estate_scraper/
│   │   │   ├── spiders/       # Пауки для парсинга
│   │   │   ├── configs/       # Конфигурации сайтов
│   │   │   ├── services/      # Сервисы парсера
│   │   │   ├── parsers/       # Парсеры данных
│   │   │   ├── pipelines.py   # Пайплайны обработки
│   │   │   ├── worker.py      # Основной воркер
│   │   │   └── settings.py    # Настройки Scrapy
│   │   ├── scrapy.cfg         # Конфигурация Scrapy
│   │   └── ADD_NEW_SITE_GUIDE.md
│   ├── Dockerfile             # Docker образ для scraper
│   └── requirements.txt       # Зависимости scraper
├── tools/                     # Утилиты
│   ├── create_admin.py        # Создание администратора
│   ├── reset_db_simple.py     # Сброс базы данных
│   └── monitor_logs.py        # Мониторинг логов
├── scripts/                   # Скрипты развертывания
│   ├── dev_setup.sh          # Настройка разработки
│   ├── quick_test.sh         # Быстрые тесты
│   └── migrate_to_new_structure.sh
├── photo_validation_test/     # Тесты валидации фото
├── logs/                      # Логи парсинга и системы
├── docker-compose.yml         # Docker Compose конфигурация
├── env.example               # Пример переменных окружения
├── nginx.conf                # Конфигурация Nginx
└── doc.md                    # Документация
```

## 🚀 Быстрый старт

### 1. Клонирование и настройка
```bash
git clone <repository>
cd estate_parser
cp env.example .env
# Отредактируйте .env файл при необходимости
```

### 2. Запуск через Docker Compose
```bash
# Запуск всех сервисов
docker-compose up -d

# Проверка статуса
docker-compose ps
```

### 3. Доступ к сервисам
- **API**: http://localhost:8000
- **Веб-интерфейс**: http://localhost:8000 (встроенный в API)
- **PgAdmin**: http://localhost:5050
- **Elasticsearch**: http://localhost:9200

## 🔧 Разработка

### Backend разработка
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Scraper разработка
```bash
cd scraper
pip install -r requirements.txt
cd estate_scraper
python real_estate_scraper/worker.py --config lalafo
```

## 📊 Основные возможности

### API Endpoints
- `GET /api/ads/unique` - Получение уникальных объявлений с фильтрацией
- `GET /api/ads/unique/{id}` - Детали уникального объявления
- `GET /api/elasticsearch/search` - Поиск через Elasticsearch
- `POST /api/ads` - Добавление нового объявления
- `POST /api/process/duplicates` - Обработка дубликатов
- `POST /api/scraping/start/{config}` - Запуск парсинга
- `GET /api/automation/status` - Статус автоматизации

### Веб-интерфейс
- **Dashboard** - Главная панель с статистикой
- **Объявления** - Просмотр и фильтрация объявлений
- **Автоматизация** - Управление автоматическим парсингом
- **Настройки** - Конфигурация системы
- **Пользователи** - Управление пользователями

### Парсинг сайтов
Поддерживаемые источники:
- **Lalafo** - Объявления о недвижимости
- **House.kg** - Недвижимость в Кыргызстане
- **Agency** - Агентства недвижимости
- **AN** - Агентства недвижимости
- **Stroka** - Строительные компании

## 🛠️ Конфигурация

### Переменные окружения
Основные переменные в `.env`:

```env
# Database
DB_HOST=db
DB_PORT=5432
DB_NAME=estate_db
DB_USER=estate_user
DB_PASSWORD=admin123

# Redis
REDIS_URL=redis://redis:6379
REDIS_HOST=redis
REDIS_PORT=6379

# Elasticsearch
ELASTICSEARCH_HOSTS=http://elasticsearch:9200
ELASTICSEARCH_INDEX=real_estate_ads
ES_JAVA_OPTS=-Xms512m -Xmx512m

# API
API_HOST=0.0.0.0
API_PORT=8000
SCRAPY_API_URL=http://api:8000/api/ads

# PgAdmin
PGADMIN_DEFAULT_EMAIL=admin@admin.com
PGADMIN_DEFAULT_PASSWORD=admin123
PGADMIN_PORT=5050

# Default Admin
DEFAULT_ADMIN_USERNAME=Adminn
DEFAULT_ADMIN_PASSWORD=admin2025
DEFAULT_ADMIN_FULL_NAME=Administrator
CREATE_DEFAULT_ADMIN=true
```

## 📈 Мониторинг и логи

### Логи
```bash
# Логи API
docker logs estate_api

# Логи Scraper
docker logs estate_scraper

# Логи базы данных
docker logs estate_db

# Просмотр логов парсинга
ls logs/scraping/
```

### Статус сервисов
```bash
# Проверка здоровья API
curl http://localhost:8000/api/status

# Проверка Elasticsearch
curl http://localhost:9200/_cluster/health

# Статус автоматизации
curl http://localhost:8000/api/automation/status
```

## 🔄 Миграция данных

### База данных
```bash
# Создание миграций
cd backend
alembic revision --autogenerate -m "Initial migration"

# Применение миграций
alembic upgrade head
```

### Elasticsearch
```bash
# Переиндексация
curl -X POST http://localhost:8000/api/elasticsearch/reindex
```

## 🧪 Тестирование

### Backend тесты
```bash
cd backend
python -m pytest tests/
```

### Scraper тесты
```bash
cd scraper
python -m pytest tests/
```

### Тесты валидации фото
```bash
cd photo_validation_test
python photo_validator.py
```

## 🛠️ Утилиты

### Создание администратора
```bash
cd tools
python create_admin.py --username admin --password admin123 --full-name "Administrator"
```

### Сброс базы данных
```bash
cd tools
python reset_db_simple.py
```

### Мониторинг логов
```bash
cd tools
python monitor_logs.py --container estate_api
```

## 📈 Производительность

### Оптимизация
- **Кэширование**: Redis для кэширования запросов
- **Поиск**: Elasticsearch для быстрого поиска
- **База данных**: PostgreSQL с индексами
- **Асинхронность**: FastAPI для высокопроизводительного API
- **WebSocket**: Реальное время обновлений

### Мониторинг
- **Метрики**: Встроенные метрики в API
- **Логирование**: Структурированные логи
- **Трассировка**: Отслеживание запросов
- **Автоматизация**: Планировщик задач

## 🔒 Безопасность

### Рекомендации
- Используйте HTTPS в продакшене
- Настройте аутентификацию для API
- Ограничьте доступ к базе данных
- Регулярно обновляйте зависимости
- Используйте сильные пароли для админов

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

## 📄 Лицензия

MIT License

