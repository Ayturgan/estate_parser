FROM python:3.11-slim

WORKDIR /app

# Установка uv
RUN pip install --upgrade pip && pip install uv

COPY pyproject.toml uv.lock ./

# Установка зависимостей через uv
RUN uv pip install --system .

COPY . .

EXPOSE 8000
