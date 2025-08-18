# Используем официальный Playwright образ с Python 3.11
FROM mcr.microsoft.com/playwright/python:latest

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей отдельно для кэширования
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаем директорию для логов
RUN mkdir -p /app/logs

# Настройка PYTHONPATH для модулей backend
ENV PYTHONPATH=/app:/app/backend

# Переход в директорию Scrapy проекта
WORKDIR /app/estate_scraper

# Команда по умолчанию для запуска worker
CMD ["python", "real_estate_scraper/worker.py"]

