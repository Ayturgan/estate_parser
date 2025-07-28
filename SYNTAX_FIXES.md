# Исправление синтаксических ошибок

## Проблема

Обнаружены синтаксические ошибки в f-строках в файлах пауков, которые приводили к сбою при запуске парсинга.

## Исправленные файлы

### 1. `generic_api_spider.py`
**Строка 341:**
```python
# Было:
self.logger.warning(f"Error processing field \'{output_field}\'": {e})

# Стало:
self.logger.warning(f"Error processing field '{output_field}': {e}")
```

### 2. `generic_spider.py`
**Строка 232:**
```python
# Было:
self.logger.warning(f"Error extracting field with selector \'{selector}\': {e}")

# Стало:
self.logger.warning(f"Error extracting field with selector '{selector}': {e}")
```

## Причина ошибки

Неправильное экранирование кавычек в f-строках. Использование `\'` вместо простых одинарных кавычек `'` приводило к синтаксической ошибке.

## Результат

✅ Все файлы пауков теперь компилируются без ошибок
✅ Воркер также прошел проверку синтаксиса
✅ Система распознавания ошибок парсинга готова к работе

## Проверка

Выполнена проверка синтаксиса всех затронутых файлов:
- `generic_api_spider.py` ✅
- `generic_spider.py` ✅  
- `generic_show_more_simple_spider.py` ✅
- `worker.py` ✅

Теперь парсинг должен запускаться без синтаксических ошибок. 