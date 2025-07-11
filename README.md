# 🏠 Estate Parser - Парсер недвижимости

Современная система парсинга и анализа объявлений о недвижимости с использованием микросервисной архитектуры.

## 📁 Структура проекта

```
estate_parser/
├── backend/                    # Backend API сервис
│   ├── app/
│   │   ├── api/v1/            # API эндпоинты
│   │   ├── core/              # Конфигурация и ядро
│   │   ├── models/            # Pydantic модели
│   │   ├── services/          # Бизнес-логика
│   │   └── websocket/         # WebSocket обработчики
│   ├── tests/                 # Тесты backend
│   └── requirements.txt       # Зависимости backend
├── scraper/                   # Scraper сервис
│   ├── estate_scraper/        # Scrapy проект
│   │   ├── spiders/          # Пауки
│   │   ├── configs/          # Конфигурации
│   │   └── pipelines/        # Пайплайны обработки
│   ├── tests/                # Тесты scraper
│   └── requirements.txt      # Зависимости scraper
├── frontend/                  # Frontend (опционально)
│   ├── static/               # Статические файлы
│   └── templates/            # HTML шаблоны
├── infrastructure/            # Инфраструктура
│   ├── docker/              # Docker файлы
│   └── k8s/                 # Kubernetes манифесты
├── configs/                  # Конфигурации
│   ├── environments/         # Переменные окружения
│   ├── logging/             # Конфигурация логирования
│   └── monitoring/          # Мониторинг
├── scripts/                  # Скрипты развертывания
├── tools/                    # Утилиты
└── logs/                     # Логи
```

## 🚀 Быстрый старт

### 1. Клонирование и настройка
```bash
git clone <repository>
cd estate_parser
```

### 2. Запуск через Docker Compose
```bash
# Запуск всех сервисов
docker-compose -f infrastructure/docker-compose.yml up -d

# Проверка статуса
docker-compose -f infrastructure/docker-compose.yml ps
```

### 3. Доступ к сервисам
- **API**: http://localhost:8000
- **Frontend**: http://localhost:80
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
scrapy crawl generic_api -a config=lalafo
```

## 📊 Мониторинг

### Логи
```bash
# Логи API
docker logs estate_api

# Логи Scraper
docker logs estate_scraper

# Логи базы данных
docker logs estate_db
```

### Статус сервисов
```bash
# Проверка здоровья API
curl http://localhost:8000/api/status

# Проверка Elasticsearch
curl http://localhost:9200/_cluster/health
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

## 🛠️ Конфигурация

### Переменные окружения
Основные переменные находятся в `configs/environments/development.env`:

```env
# Database
DB_HOST=db
DB_PORT=5432
DB_NAME=estate_db
DB_USER=estate_user
DB_PASSWORD=admin123

# Redis
REDIS_URL=redis://redis:6379

# Elasticsearch
ELASTICSEARCH_HOSTS=http://elasticsearch:9200
ELASTICSEARCH_INDEX=real_estate_ads

# API
SCRAPY_API_URL=http://api:8000/api/ads

# Pipeline
PIPELINE_INTERVAL_HOURS=3
RUN_IMMEDIATELY_ON_START=false
SCRAPING_SOURCES=house,lalafo,stroka
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

## 📈 Производительность

### Оптимизация
- **Кэширование**: Redis для кэширования запросов
- **Поиск**: Elasticsearch для быстрого поиска
- **База данных**: PostgreSQL с индексами
- **Асинхронность**: FastAPI для высокопроизводительного API

### Мониторинг
- **Метрики**: Встроенные метрики в API
- **Логирование**: Структурированные логи
- **Трассировка**: Отслеживание запросов

## 🔒 Безопасность

### Рекомендации
- Используйте HTTPS в продакшене
- Настройте аутентификацию для API
- Ограничьте доступ к базе данных
- Регулярно обновляйте зависимости

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch
3. Внесите изменения
4. Добавьте тесты
5. Создайте Pull Request

## 📄 Лицензия

MIT License

