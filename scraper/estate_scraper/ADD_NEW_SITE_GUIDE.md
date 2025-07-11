# Руководство по добавлению нового сайта-источника

## Обзор

В вашем парсере недвижимости есть три типа спайдеров для разных сайтов:

1. **HTML спайдер** (`generic_spider.py`) - для обычных сайтов с пагинацией
2. **API спайдер** (`generic_api_spider.py`) - для сайтов с JSON API
3. **Show More спайдер** (`generic_show_more_spider.py`) - для сайтов с кнопкой "Показать еще"

## Шаг 1: Анализ сайта

### Определите тип сайта:

1. **Обычный HTML сайт** - имеет пагинацию (страницы 1, 2, 3...)
2. **API сайт** - использует JSON API для загрузки данных
3. **Сайт с "Показать еще"** - имеет кнопку для подгрузки контента

### Найдите селекторы:

Откройте сайт в браузере и используйте Developer Tools (F12):

```javascript
// Примеры поиска селекторов
document.querySelector('.listing-card')  // Карточка объявления
document.querySelector('.title a')       // Заголовок и ссылка
document.querySelector('.price')         // Цена
document.querySelector('.location')      // Местоположение
```

## Шаг 2: Создание конфигурации

### Для обычного HTML сайта:

Создайте файл `configs/your_site.yml`:

```yaml
name: "your_site"
source_name: "your-site.com"
spider_type: "html"
parse_all_listings: false
max_items_limit: 10

base_url: "https://your-site.com"

# Категории недвижимости
categories:
  - url: "/buy/apartments"
    property_type: "Квартира"
    listing_type: "Продажа"
    name: "квартиры_продажа"
    
  - url: "/rent/apartments"
    property_type: "Квартира"
    listing_type: "Аренда"
    name: "квартиры_аренда"

# Настройки пагинации
pagination:
  start_page: 1
  page_url_format: "{base_url}{category_url}?page={page}"

# Селекторы для парсинга
selectors:
  ads_list: ".listings-container"      # Контейнер со всеми объявлениями
  ad_card: ".listing-card"            # Карточка одного объявления
  
  title: ".title a::text"             # Заголовок
  url: ".title a::attr(href)"         # Ссылка на объявление
  price: ".price::text"               # Цена
  location: ".location::text"         # Местоположение
  description: ".description::text"   # Описание
  image: ".image img::attr(src)"      # Изображение
  
  # Детальная информация (опционально)
  details:
    rooms: ".details .rooms::text"
    area: ".details .area::text"
    floor: ".details .floor::text"

# Настройки запросов
request_settings:
  delay: 2
  timeout: 30
  retries: 3
  user_agent_rotation: true

# Обработка данных
data_processing:
  ai_extraction: true
  ai_classification: false
  price_cleaning: true
  description_cleaning: true
```

### Для API сайта:

```yaml
name: "your_api_site"
source_name: "your-api-site.com"
spider_type: "api"
parse_all_listings: false
max_items_limit: 10

base_url: "https://your-api-site.com/api/search"

# API настройки
api_settings:
  url_format: "{base_url}?category_id={category_id}&page={page}&per_page={per_page}"
  start_page: 1
  per_page: 20

# Категории с ID
categories:
  - name: "Продажа квартир"
    category_id: 1001
    property_type: "Квартира"
    listing_type: "Продажа"
    referer: "https://your-api-site.com/buy/apartments"
    
  - name: "Аренда квартир"
    category_id: 1002
    property_type: "Квартира"
    listing_type: "Аренда"
    referer: "https://your-api-site.com/rent/apartments"

# Поля API ответа
api_fields:
  items_key: "data"  # Ключ массива объявлений
  item_fields:
    title: "title"
    price: "price"
    description: "description"
    url: "url"
    images: "images"
    phone: "contact.phone"
    created_at: "created_at"

# Настройки Playwright (если нужны куки)
use_playwright: true
playwright:
  headless: true
  sleep_time: 3
```

### Для сайта с кнопкой "Показать еще":

```yaml
name: "your_show_more_site"
source_name: "your-show-more-site.com"
spider_type: "html"
parse_all_listings: false
max_items_limit: 10

base_url: "https://your-show-more-site.com"

# Категории недвижимости
categories:
  - url: "/buy/apartments"
    property_type: "Квартира"
    listing_type: "Продажа"
    name: "квартиры_продажа"
    
  - url: "/rent/apartments"
    property_type: "Квартира"
    listing_type: "Аренда"
    name: "квартиры_аренда"

# Настройки кнопки "Показать еще"
show_more_settings:
  enabled: true
  button_selector: ".load-more-button"  # CSS селектор кнопки
  button_text: "Показать еще"          # Текст кнопки (опционально)
  max_clicks: 5                        # Максимум кликов
  wait_time: 3                         # Время ожидания после клика
  scroll_before_click: true            # Прокрутить к кнопке

# Селекторы для парсинга
selectors:
  ads_list: ".listings-container"
  ad_card: ".listing-card"
  
  title: ".title a::text"
  url: ".title a::attr(href)"
  price: ".price::text"
  location: ".location::text"
  description: ".description::text"
  image: ".image img::attr(src)"
  
  details:
    rooms: ".details .rooms::text"
    area: ".details .area::text"
    floor: ".details .floor::text"

# Настройки запросов
request_settings:
  delay: 2
  timeout: 30
  retries: 3
  user_agent_rotation: true

# Обработка данных
data_processing:
  ai_extraction: true
  ai_classification: false
  price_cleaning: true
  description_cleaning: true
```

## Шаг 3: Тестирование конфигурации

### Запуск тестового парсинга:

```bash
# Для HTML сайта
cd scraper/estate_scraper
scrapy crawl generic_scraper -a config=your_site -s LOG_LEVEL=INFO

# Для API сайта
scrapy crawl generic_api -a config=your_api_site -s LOG_LEVEL=INFO

# Для сайта с "Показать еще"
scrapy crawl generic_show_more -a config=your_show_more_site -s LOG_LEVEL=INFO
```

### Проверка результатов:

1. Проверьте логи на наличие ошибок
2. Убедитесь, что данные извлекаются корректно
3. Проверьте, что все поля заполняются правильно

## Шаг 4: Настройка в веб-интерфейсе

После создания конфигурации:

1. Перезапустите Docker контейнеры
2. В веб-интерфейсе выберите ваш новый конфиг
3. Настройте параметры парсинга
4. Запустите парсинг

## Частые проблемы и решения

### Проблема: Не находятся объявления
**Решение:**
- Проверьте селекторы `ads_list` и `ad_card`
- Убедитесь, что селекторы уникальны
- Проверьте, что страница полностью загружена

### Проблема: Не работает пагинация
**Решение:**
- Проверьте формат URL в `page_url_format`
- Убедитесь, что параметр страницы правильный
- Проверьте, что следующая страница существует

### Проблема: API возвращает ошибки
**Решение:**
- Проверьте заголовки запросов
- Убедитесь, что нужны куки (включите `use_playwright: true`)
- Проверьте формат API URL

### Проблема: Кнопка "Показать еще" не кликается
**Решение:**
- Проверьте селектор кнопки
- Увеличьте `wait_time`
- Включите `scroll_before_click: true`

## Примеры селекторов

### CSS селекторы:
```css
.title a::text          /* Текст ссылки */
.price::text            /* Текст элемента */
.image img::attr(src)   /* Атрибут src */
```

### XPath селекторы:
```xpath
xpath://div[@class='title']/a/text()           /* Текст ссылки */
xpath://span[@class='price']/text()            /* Текст элемента */
xpath://img[@class='image']/@src               /* Атрибут src */
```

### Сложные селекторы:
```yaml
# Для элементов с условиями
title: "xpath://div[contains(@class, 'listing')]//a[contains(@class, 'title')]/text()"

# Для элементов с родительскими условиями
price: "xpath://div[@class='card']//span[@class='price']/text()"
```

## Советы по оптимизации

1. **Начните с малого** - установите `max_items_limit: 1` для тестирования
2. **Используйте логирование** - `LOG_LEVEL=DEBUG` для детальной отладки
3. **Проверяйте селекторы** - используйте браузерные инструменты
4. **Тестируйте постепенно** - сначала базовые поля, потом детали
5. **Обрабатывайте ошибки** - настройте `retries` и `timeout`

## Структура данных

Все объявления сохраняются со следующими полями:

```python
{
    'source_name': 'your-site.com',
    'property_type': 'Квартира',
    'listing_type': 'Продажа',
    'title': 'Заголовок объявления',
    'url': 'https://site.com/ad/123',
    'price': '50000',
    'location': 'Бишкек, Октябрьский район',
    'description': 'Описание объявления',
    'image': 'https://site.com/image.jpg',
    # ... дополнительные поля из details
}
``` 