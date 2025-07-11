#!/usr/bin/env python3
"""
Скрипт для создания конфигурации нового сайта-источника
Использование: python create_site_config.py site_name site_url
"""

import sys
import os
from pathlib import Path

def create_html_config(site_name, site_url):
    """Создает конфигурацию для HTML сайта"""
    config = f"""name: "{site_name}"
source_name: "{site_name}.com"
spider_type: "html"
parse_all_listings: false
max_items_limit: 10

base_url: "{site_url}"

# Категории недвижимости - НАСТРОЙТЕ ПОД ВАШ САЙТ
categories:
  - url: "/buy/apartments"
    property_type: "Квартира"
    listing_type: "Продажа"
    name: "квартиры_продажа"
    
  - url: "/rent/apartments"
    property_type: "Квартира"
    listing_type: "Аренда"
    name: "квартиры_аренда"

# Настройки пагинации - НАСТРОЙТЕ ПОД ВАШ САЙТ
pagination:
  start_page: 1
  page_url_format: "{{base_url}}{{category_url}}?page={{page}}"

# Селекторы для парсинга - НАСТРОЙТЕ ПОД ВАШ САЙТ
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
"""
    return config

def create_api_config(site_name, site_url):
    """Создает конфигурацию для API сайта"""
    config = f"""name: "{site_name}_api"
source_name: "{site_name}.com"
spider_type: "api"
parse_all_listings: false
max_items_limit: 10

base_url: "{site_url}/api/search"

# API настройки - НАСТРОЙТЕ ПОД ВАШ САЙТ
api_settings:
  url_format: "{{base_url}}?category_id={{category_id}}&page={{page}}&per_page={{per_page}}"
  start_page: 1
  per_page: 20

# Категории с ID - НАСТРОЙТЕ ПОД ВАШ САЙТ
categories:
  - name: "Продажа квартир"
    category_id: 1001
    property_type: "Квартира"
    listing_type: "Продажа"
    referer: "{site_url}/buy/apartments"
    
  - name: "Аренда квартир"
    category_id: 1002
    property_type: "Квартира"
    listing_type: "Аренда"
    referer: "{site_url}/rent/apartments"

# Поля API ответа - НАСТРОЙТЕ ПОД ВАШ САЙТ
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

# Обработка данных
data_processing:
  clean_html: true
  validate_required_fields: ["title", "price"]
"""
    return config

def create_show_more_config(site_name, site_url):
    """Создает конфигурацию для сайта с кнопкой 'Показать еще'"""
    config = f"""name: "{site_name}_show_more"
source_name: "{site_name}.com"
spider_type: "html"
parse_all_listings: false
max_items_limit: 10

base_url: "{site_url}"

# Категории недвижимости - НАСТРОЙТЕ ПОД ВАШ САЙТ
categories:
  - url: "/buy/apartments"
    property_type: "Квартира"
    listing_type: "Продажа"
    name: "квартиры_продажа"
    
  - url: "/rent/apartments"
    property_type: "Квартира"
    listing_type: "Аренда"
    name: "квартиры_аренда"

# Настройки кнопки "Показать еще" - НАСТРОЙТЕ ПОД ВАШ САЙТ
show_more_settings:
  enabled: true
  button_selector: ".load-more-button"  # CSS селектор кнопки
  button_text: "Показать еще"          # Текст кнопки (опционально)
  max_clicks: 5                        # Максимум кликов
  wait_time: 3                         # Время ожидания после клика
  scroll_before_click: true            # Прокрутить к кнопке

# Селекторы для парсинга - НАСТРОЙТЕ ПОД ВАШ САЙТ
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
"""
    return config

def create_show_more_simple_config(site_name, site_url):
    """Создает упрощенную конфигурацию для сайта с кнопкой 'Показать еще'"""
    config = f"""name: "{site_name}_show_more_simple"
source_name: "{site_name}.com"
spider_type: "html"
parse_all_listings: false
max_items_limit: 10

base_url: "{site_url}"

# Прямые настройки типа недвижимости и сделки
property_type: "Квартира"      # Тип недвижимости: Квартира, Дом, Коммерческая недвижимость, и т.д.
listing_type: "Продажа"        # Тип сделки: Продажа, Аренда

# URL страницы для парсинга
start_url: "/buy/apartments"   # URL страницы с объявлениями

# Настройки кнопки "Показать еще" - НАСТРОЙТЕ ПОД ВАШ САЙТ
show_more_settings:
  enabled: true
  button_selector: ".load-more-button"  # CSS селектор кнопки
  button_text: "Показать еще"          # Текст кнопки (опционально)
  max_clicks: 5                        # Максимум кликов
  wait_time: 3                         # Время ожидания после клика
  scroll_before_click: true            # Прокрутить к кнопке

# Селекторы для парсинга - НАСТРОЙТЕ ПОД ВАШ САЙТ
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
"""
    return config

def main():
    if len(sys.argv) < 3:
        print("Использование: python create_site_config.py site_name site_url [type]")
        print("Примеры:")
        print("  python create_site_config.py my_site https://my-site.com")
        print("  python create_site_config.py my_api_site https://my-api-site.com api")
        print("  python create_site_config.py my_show_more_site https://my-show-more-site.com show_more")
        sys.exit(1)
    
    site_name = sys.argv[1]
    site_url = sys.argv[2]
    config_type = sys.argv[3] if len(sys.argv) > 3 else "html"
    
    # Создаем директорию configs если её нет
    configs_dir = Path("scraper/estate_scraper/real_estate_scraper/configs")
    configs_dir.mkdir(parents=True, exist_ok=True)
    
    # Создаем конфигурацию в зависимости от типа
    if config_type == "api":
        config_content = create_api_config(site_name, site_url)
        config_filename = f"{site_name}_api.yml"
    elif config_type == "show_more":
        config_content = create_show_more_config(site_name, site_url)
        config_filename = f"{site_name}_show_more.yml"
    elif config_type == "show_more_simple":
        config_content = create_show_more_simple_config(site_name, site_url)
        config_filename = f"{site_name}_show_more_simple.yml"
    else:
        config_content = create_html_config(site_name, site_url)
        config_filename = f"{site_name}.yml"
    
    # Записываем конфигурацию в файл
    config_path = configs_dir / config_filename
    
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    print(f"✅ Создана конфигурация: {config_path}")
    print(f"📝 Тип конфигурации: {config_type}")
    print(f"🌐 Сайт: {site_url}")
    print()
    print("📋 Следующие шаги:")
    print("1. Отредактируйте селекторы в конфигурации под ваш сайт")
    print("2. Настройте категории и URL")
    print("3. Протестируйте конфигурацию:")
    print(f"   python test_new_site.py {site_name} {config_type}")
    print("4. После успешного тестирования запустите парсинг через веб-интерфейс")

if __name__ == "__main__":
    main() 