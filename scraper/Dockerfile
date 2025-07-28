FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements ПЕРЕД копированием кода
# Это позволяет кэшировать установку зависимостей
COPY requirements.txt .

# Установка зависимостей (будет кэшироваться если requirements.txt не изменился)
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода ПОСЛЕ установки зависимостей
# Это позволяет кэшировать установку зависимостей даже при изменении кода
COPY . .

# Создание директории для логов
RUN mkdir -p /app/logs

# Установка PYTHONPATH для backend модулей
ENV PYTHONPATH=/app:/app/backend

# Переход в директорию проекта scrapy
WORKDIR /app/estate_scraper

# Запуск worker процесса
CMD ["python", "real_estate_scraper/worker.py"] 