# Исправление проблемы с отображением этапа валидации ссылок

## Проблема
Этап "Валидация ссылок" появлялся в интерфейсе, но потом пропадал через некоторое время.

## Причина
В коде automation_service.py была логика, которая сбрасывала статусы этапов в "idle" когда пользователи офлайн, но эта логика не учитывала новый этап `LINK_VALIDATION`.

## Исправления

### 1. Добавлен этап в список сбрасываемых статусов
**Файл**: `backend/app/services/automation_service.py`
**Строка**: ~855
```python
# Было:
for stage_enum in [PipelineStage.DUPLICATE_PROCESSING, PipelineStage.PHOTO_PROCESSING, PipelineStage.REALTOR_DETECTION]:

# Стало:
for stage_enum in [PipelineStage.LINK_VALIDATION, PipelineStage.DUPLICATE_PROCESSING, PipelineStage.PHOTO_PROCESSING, PipelineStage.REALTOR_DETECTION]:
```

### 2. Добавлен метод обновления статуса валидации ссылок
**Файл**: `backend/app/services/automation_service.py`
**Добавлен метод**: `_update_link_validation_status()`

### 3. Добавлен вызов обновления статуса валидации
**Файл**: `backend/app/services/automation_service.py`
**Строка**: ~840
```python
# Добавлен вызов:
await self._update_link_validation_status()
```

### 4. Добавлено отображение названия этапа в HTML
**Файл**: `backend/app/templates/automation.html`
**Строка**: ~156
```html
{% set stage_names = {
    'link_validation': 'Валидация ссылок',
    'scraping': 'Парсинг',
    ...
} %}
```

### 5. Добавлено отображение названия этапа в JavaScript
**Файл**: `backend/app/static/js/automation.js`
**Строка**: ~210
```javascript
const stageNames = {
    'link_validation': 'Валидация ссылок',
    'scraping': 'Парсинг',
    ...
};
```

## Результат
Теперь этап "Валидация ссылок" будет:
- ✅ Правильно отображаться в интерфейсе
- ✅ Не пропадать через время
- ✅ Обновлять свой статус в реальном времени
- ✅ Показывать прогресс выполнения

## Проверка
После внесения изменений:
1. Перезапустите контейнеры
2. Откройте страницу Автоматизация
3. Убедитесь, что этап "Валидация ссылок" отображается в списке включенных этапов
4. Запустите пайплайн и проверьте, что этап выполняется корректно 