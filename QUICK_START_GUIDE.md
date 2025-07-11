# 🚀 Быстрый старт: Добавление нового сайта-источника

## Шаг 1: Анализ сайта

Откройте сайт в браузере и определите:

1. **Тип сайта:**
   - Обычный HTML с пагинацией → используйте `html`
   - Сайт с JSON API → используйте `api`
   - Сайт с кнопкой "Показать еще" → используйте `show_more`
   - Сайт с кнопкой "Показать еще" (упрощенный) → используйте `show_more_simple`

2. **Найдите селекторы:**
   - Откройте Developer Tools (F12)
   - Найдите карточки объявлений
   - Скопируйте CSS селекторы для заголовка, цены, ссылки

## Шаг 2: Создание конфигурации

### Автоматическое создание:
```bash
# Для обычного HTML сайта
python tools/create_site_config.py my_site https://my-site.com

# Для API сайта
python tools/create_site_config.py my_api_site https://my-api-site.com api

# Для сайта с "Показать еще"
python tools/create_site_config.py my_show_more_site https://my-show-more-site.com show_more

# Для сайта с "Показать еще" (упрощенный)
python tools/create_site_config.py my_show_more_simple_site https://my-show-more-simple-site.com show_more_simple
```

### Ручное создание:
Создайте файл `scraper/estate_scraper/real_estate_scraper/configs/my_site.yml`:

```yaml
name: "my_site"
source_name: "my-site.com"
spider_type: "html"
parse_all_listings: false
max_items_limit: 10

base_url: "https://my-site.com"

categories:
  - url: "/buy/apartments"
    property_type: "Квартира"
    listing_type: "Продажа"
    name: "квартиры_продажа"

pagination:
  start_page: 1
  page_url_format: "{base_url}{category_url}?page={page}"

selectors:
  ads_list: ".listings-container"      # Контейнер объявлений
  ad_card: ".listing-card"            # Карточка объявления
  title: ".title a::text"             # Заголовок
  url: ".title a::attr(href)"         # Ссылка
  price: ".price::text"               # Цена
  location: ".location::text"         # Местоположение
```

## Шаг 3: Тестирование

```bash
# Тестируем конфигурацию
python tools/test_new_site.py my_site html

# Для API сайта
python tools/test_new_site.py my_api_site api

# Для сайта с "Показать еще"
python tools/test_new_site.py my_show_more_site show_more

# Для сайта с "Показать еще" (упрощенный)
python tools/test_new_site.py my_show_more_simple_site show_more_simple
```

## Шаг 4: Запуск парсинга

1. Перезапустите Docker контейнеры
2. Откройте веб-интерфейс
3. Выберите ваш конфиг
4. Настройте параметры и запустите

## 🔧 Частые проблемы

### Не находятся объявления
- Проверьте селекторы `ads_list` и `ad_card`
- Убедитесь, что страница полностью загружена

### Не работает пагинация
- Проверьте формат URL в `page_url_format`
- Убедитесь, что параметр страницы правильный

### API возвращает ошибки
- Включите `use_playwright: true` для получения кук
- Проверьте заголовки запросов

### Кнопка "Показать еще" не кликается
- Проверьте селектор кнопки
- Увеличьте `wait_time`
- Включите `scroll_before_click: true`

## 📋 Примеры селекторов

```css
/* CSS селекторы */
.title a::text          /* Текст ссылки */
.price::text            /* Текст элемента */
.image img::attr(src)   /* Атрибут src */
```

```xpath
/* XPath селекторы */
xpath://div[@class='title']/a/text()    /* Текст ссылки */
xpath://span[@class='price']/text()     /* Текст элемента */
xpath://div[@class='grid-item']//a/@href  /* Все ссылки на изображения */
```

## 🎯 Советы

1. **Начните с малого** - `max_items_limit: 1` для тестирования
2. **Используйте логирование** - `LOG_LEVEL=DEBUG` для отладки
3. **Проверяйте селекторы** - используйте браузерные инструменты
4. **Тестируйте постепенно** - сначала базовые поля, потом детали

## 📚 Подробная документация

См. `scraper/estate_scraper/ADD_NEW_SITE_GUIDE.md` для полного руководства. 