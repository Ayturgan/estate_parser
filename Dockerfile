FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Установка uv
RUN pip install --upgrade pip && pip install uv

COPY pyproject.toml uv.lock ./

# Установка зависимостей через uv
RUN uv pip install --system .

COPY . .

# Копирование entrypoint скриптов
COPY entrypoint.sh /entrypoint.sh
COPY entrypoint-scrapy.sh /entrypoint-scrapy.sh
RUN chmod +x /entrypoint.sh /entrypoint-scrapy.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
