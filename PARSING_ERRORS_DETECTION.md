# Система распознавания ошибок парсинга

## Обзор

Реализована система для автоматического распознавания ошибок парсинга в пауках и соответствующего обновления статуса задач в воркере.

## Изменения

### 1. Пауки (Spiders)

**Файлы:**
- `scraper/estate_scraper/real_estate_scraper/spiders/generic_show_more_simple_spider.py`
- `scraper/estate_scraper/real_estate_scraper/spiders/generic_api_spider.py`
- `scraper/estate_scraper/real_estate_scraper/spiders/generic_spider.py`

**Добавлено:**
- Флаг `has_parsing_errors` для отслеживания ошибок парсинга
- Установка флага при обнаружении ошибок извлечения данных
- Установка флага при сетевых ошибках (DNS, Connection, Timeout и т.д.)
- Логирование сигнала об ошибках парсинга в методе `closed()`

### 2. Воркер (Worker)

**Файл:** `scraper/estate_scraper/real_estate_scraper/worker.py`

**Добавлено:**
- Паттерны для распознавания ошибок парсинга в логах
- Паттерны для распознавания сетевых ошибок (DNS, Connection, Timeout и т.д.)
- Паттерны для распознавания успешного завершения
- Функции `detect_parsing_errors()` и `detect_success_signals()`
- Обновленная логика мониторинга процесса с анализом логов
- Новые статусы задач:
  - `завершено с ошибками парсинга`
  - `ошибка парсинга`

### 3. ScrapyManager

**Файл:** `backend/app/services/scrapy_manager.py`

**Добавлено:**
- Новые константы статусов:
  - `FINISHED_WITH_PARSING_ERRORS`
  - `FAILED_WITH_PARSING_ERRORS`
- Обновленная логика отправки WebSocket событий для новых статусов

### 4. AutomationService

**Файл:** `backend/app/services/automation_service.py`

**Обновлено:**
- Метод `_wait_for_scraping_completion()` для обработки новых статусов
- Логика подсчета успешных и неуспешных задач с учетом ошибок парсинга

### 5. Веб-интерфейс

**Файлы:**
- `backend/app/static/js/main.js`
- `backend/app/static/js/websocket.js`

**Добавлено:**
- Поддержка новых статусов в функциях отображения
- Улучшенная обработка ошибок парсинга в WebSocket событиях
- Специальные уведомления для разных типов ошибок

## Новые статусы задач

1. **`завершено с ошибками парсинга`** - задача завершилась успешно (returncode=0), но обнаружены ошибки при извлечении данных
2. **`ошибка парсинга`** - задача завершилась с ошибкой (returncode≠0) и обнаружены ошибки парсинга

## Паттерны распознавания

### Ошибки парсинга:
- `Spider finished with parsing errors`
- `has_parsing_errors.*True`
- `Error extracting field`
- `Error extracting item data`
- `Error extracting photos`
- `Error extracting phones`
- `Invalid JSON in response`
- `Required selectors.*not found`
- `No ads container found`
- `Error processing item`

### Сетевые ошибки:
- `DNS lookup failed`
- `Connection refused`
- `Connection timeout`
- `Network unreachable`
- `Host unreachable`
- `Request failed`
- `HTTP запрос неуспешен`
- `Gave up retrying`
- `Downloader/exception_count`

### Успешные сигналы:
- `Spider closed.*success`
- `Items scraped.*\d+`
- `✅.*successfully`
- `Successfully extracted`

## Логика определения статуса

```python
if was_stopped:
    status = "остановлено"
elif proc.returncode == 0:
    if parsing_errors_detected:
        status = "завершено с ошибками парсинга"
    else:
        status = "завершено"
else:
    if parsing_errors_detected:
        status = "ошибка парсинга"
    else:
        status = "ошибка"
```

## Преимущества

1. **Точная диагностика** - различение между техническими ошибками, ошибками парсинга и сетевыми проблемами
2. **Улучшенная отчетность** - более детальная информация о состоянии задач
3. **Лучший UX** - пользователи видят разницу между критическими ошибками и частичными проблемами
4. **Автоматизация** - система автоматически определяет тип проблем без ручного вмешательства
5. **Сетевая диагностика** - распознавание DNS, Connection, Timeout и других сетевых ошибок

## Тестирование

Система протестирована на различных сценариях:
- ✅ Успешное завершение
- ✅ Завершение с ошибками парсинга
- ✅ Ошибка процесса
- ✅ Ошибка процесса с ошибками парсинга
- ✅ Остановка пользователем

Все паттерны распознавания работают корректно. 