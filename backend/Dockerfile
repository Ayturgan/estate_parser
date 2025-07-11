FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Установка uv
RUN pip install --upgrade pip && pip install uv

# Установка CPU-only PyTorch сначала (избегаем CUDA зависимости)
RUN uv pip install --system --index-url https://download.pytorch.org/whl/cpu \
    torch==2.6.0+cpu \
    torchvision==0.21.0+cpu \
    torchaudio==2.6.0+cpu

# Копирование файлов зависимостей ПЕРЕД копированием кода
# Это позволяет кэшировать установку зависимостей
COPY pyproject.toml uv.lock ./

# Установка зависимостей (будет кэшироваться если pyproject.toml и uv.lock не изменились)
RUN uv pip install --system .

# Копирование кода ПОСЛЕ установки зависимостей
# Это позволяет кэшировать установку зависимостей даже при изменении кода
COPY . .

# Установка PYTHONPATH для корректного импорта app.*
ENV PYTHONPATH=/app

# Создание директории для логов
RUN mkdir -p /app/logs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 