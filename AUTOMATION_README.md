# 🤖 Сервис автоматизации парсинга и обработки

Единый Python-сервис, который автоматически управляет **последовательным выполнением** всех процессов парсинга и обработки данных.

## 🚀 Возможности

- **Последовательный пайплайн** - все процессы выполняются строго один за другим
- **Ожидание завершения** - каждый этап ждёт полного завершения предыдущего
- **Единое расписание** - настраивается только время запуска всего цикла
- **Автоматический порядок**: Парсинг → Обработка фото → Дубликаты → Риэлторы → Индексация
- **Гибкая настройка** этапов через переменные окружения
- **Подробное логирование** каждого этапа
- **Контроль времени** выполнения с таймаутами

## 📦 Установка

### 1. Добавьте сервис в docker-compose.yml

```yaml
  scheduler:
    build:
      context: .
      dockerfile: Dockerfile.scheduler
    environment:
      # Все настройки берутся из переменных окружения (.env файла)
      - API_BASE_URL=${API_BASE_URL}
      - PIPELINE_INTERVAL_HOURS=${PIPELINE_INTERVAL_HOURS}
      - RUN_IMMEDIATELY_ON_START=${RUN_IMMEDIATELY_ON_START}
      - SCRAPING_SOURCES=${SCRAPING_SOURCES}
      - ENABLE_SCRAPING=${ENABLE_SCRAPING}
      - ENABLE_PHOTO_PROCESSING=${ENABLE_PHOTO_PROCESSING}
      - ENABLE_DUPLICATE_PROCESSING=${ENABLE_DUPLICATE_PROCESSING}
      - ENABLE_REALTOR_DETECTION=${ENABLE_REALTOR_DETECTION}
      - ENABLE_ELASTICSEARCH_REINDEX=${ENABLE_ELASTICSEARCH_REINDEX}
      - SCRAPING_CHECK_INTERVAL_SECONDS=${SCRAPING_CHECK_INTERVAL_SECONDS}
      - PROCESSING_CHECK_INTERVAL_SECONDS=${PROCESSING_CHECK_INTERVAL_SECONDS}
      - MAX_WAIT_TIME_MINUTES=${MAX_WAIT_TIME_MINUTES}
      
    depends_on:
      - api
      - redis
    restart: unless-stopped
```

### 2. Настройте переменные окружения

```bash
# Создайте .env файл на основе примера
cp env.example .env

# Отредактируйте настройки под ваши нужды
nano .env
```

### 3. Запустите сервис

```bash
docker-compose up -d scheduler
```

## ⚙️ Настройка

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `API_BASE_URL` | Адрес FastAPI сервера | `http://app:8000` |
| `PIPELINE_INTERVAL_HOURS` | Интервал запуска всего пайплайна (часы) | `3` |
| `RUN_IMMEDIATELY_ON_START` | Запускать пайплайн сразу при старте | `true` |
| `SCRAPING_SOURCES` | Источники парсинга (через запятую) | `house,lalafo,stroka` |
| `ENABLE_SCRAPING` | Включить этап парсинга | `true` |
| `ENABLE_PHOTO_PROCESSING` | Включить этап обработки фото | `true` |
| `ENABLE_DUPLICATE_PROCESSING` | Включить этап обработки дубликатов | `true` |
| `ENABLE_REALTOR_DETECTION` | Включить этап определения риэлторов | `true` |
| `ENABLE_ELASTICSEARCH_REINDEX` | Включить этап переиндексации | `true` |
| `SCRAPING_CHECK_INTERVAL_SECONDS` | Интервал проверки статуса парсинга (сек) | `60` |
| `PROCESSING_CHECK_INTERVAL_SECONDS` | Интервал проверки статуса обработки (сек) | `30` |
| `MAX_WAIT_TIME_MINUTES` | Максимальное время ожидания этапа (мин) | `120` |

### Примеры конфигураций

Все настройки теперь управляются через файл `.env`. Создайте файл `.env` на основе `env.example` и настройте нужные параметры.

#### Только парсинг каждый час
```env
PIPELINE_INTERVAL_HOURS=1
ENABLE_PHOTO_PROCESSING=false
ENABLE_DUPLICATE_PROCESSING=false
ENABLE_REALTOR_DETECTION=false
ENABLE_ELASTICSEARCH_REINDEX=false
```

#### Парсинг только определённых источников
```env
SCRAPING_SOURCES=house,lalafo
PIPELINE_INTERVAL_HOURS=6
```

#### Быстрый цикл с минимальными ожиданиями
```env
PIPELINE_INTERVAL_HOURS=2
SCRAPING_CHECK_INTERVAL_SECONDS=30
PROCESSING_CHECK_INTERVAL_SECONDS=15
MAX_WAIT_TIME_MINUTES=60
```

## 📊 Мониторинг

### Просмотр логов
```bash
docker-compose logs -f scheduler
```

### Статус сервиса
```bash
docker-compose ps scheduler
```

## 🔄 Логика работы

**Последовательный пайплайн** (каждый этап ждёт завершения предыдущего):

1. **🕷️ Парсинг**: Запускает все источники из `SCRAPING_SOURCES` и ждёт их полного завершения
2. **📸 Обработка фотографий**: Обрабатывает ВСЕ фото без хешей в базе данных батчами до полного завершения
3. **🔄 Обработка дубликатов**: Обрабатывает ВСЕ необработанные объявления батчами до полного завершения
4. **🏢 Определение риэлторов**: Запускает алгоритм определения риэлторов для всех объявлений
5. **🔍 Переиндексация**: Запускает обновление поискового индекса (выполняется в фоне)

**Весь цикл повторяется каждые `PIPELINE_INTERVAL_HOURS` часов.**

## 🐛 Устранение неполадок

### Сервис не запускается
- Проверьте, что FastAPI сервер доступен по адресу `API_BASE_URL`
- Убедитесь, что Redis запущен

### Задачи не выполняются
- Проверьте логи: `docker-compose logs scheduler`
- Убедитесь, что соответствующие `ENABLE_*` переменные установлены в `true`

### Изменение настроек
После изменения переменных окружения перезапустите сервис:
```bash
docker-compose restart scheduler
```

## 🔧 Кастомизация

Если нужна более сложная логика, можно:

1. Отредактировать `scheduler_service.py`
2. Добавить новые методы обработки
3. Изменить интервалы и условия запуска
4. Добавить интеграции с внешними системами

## 📈 Преимущества перед cron

- ✅ **Один файл** для всей автоматизации
- ✅ **Гибкая настройка** через переменные окружения
- ✅ **Умные цепочки** - обработка после парсинга
- ✅ **Логирование** и мониторинг
- ✅ **Работа в Docker** без дополнительных настроек
- ✅ **Легко расширять** новыми задачами 