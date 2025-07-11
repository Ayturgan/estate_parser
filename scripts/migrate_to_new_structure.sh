#!/bin/bash

# 🚀 Скрипт миграции на новую структуру проекта
# Автор: AI Assistant
# Дата: $(date)

set -e

echo "🏠 Начинаем миграцию на новую структуру проекта..."

# Проверяем, что мы в корне проекта
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Ошибка: Запустите скрипт из корня проекта"
    exit 1
fi

# Создаем резервную копию
echo "📦 Создаем резервную копию..."
backup_dir="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$backup_dir"
cp -r app "$backup_dir/"
cp -r real_estate_scraper "$backup_dir/"
cp docker-compose.yml "$backup_dir/"
cp requirements.txt "$backup_dir/"
echo "✅ Резервная копия создана: $backup_dir"

# Останавливаем контейнеры если запущены
echo "🛑 Останавливаем контейнеры..."
docker-compose down 2>/dev/null || true

# Создаем новую структуру
echo "📁 Создаем новую структуру..."

# Backend
mkdir -p backend/app/{api/v1,core,models,services,websocket} backend/tests
cp -r app/* backend/app/
cp requirements.txt backend/
cp pyproject.toml backend/

# Scraper
mkdir -p scraper/estate_scraper/{spiders,configs,pipelines} scraper/tests
cp -r real_estate_scraper/* scraper/estate_scraper/

# Frontend
mkdir -p frontend/{static,templates}
cp -r app/static/* frontend/static/
cp -r app/templates/* frontend/templates/

# Infrastructure
mkdir -p infrastructure/{docker,k8s}
cp Dockerfile infrastructure/docker/backend.Dockerfile
cp docker-compose.yml infrastructure/

# Configs
mkdir -p configs/{environments,logging,monitoring}
cp .env configs/environments/development.env

# Tools
mkdir -p tools
cp create_admin.py tools/
cp monitor_logs.py tools/
cp view_scraping_logs.py tools/
cp start_test_scraping.py tools/

# Scripts
mkdir -p scripts
mkdir -p docs/{api,deployment,development}

echo "✅ Новая структура создана"

# Обновляем импорты
echo "🔧 Обновляем импорты..."

# Backend импорты
sed -i 's/from config import/from app.core.config import/g' backend/app/main.py
sed -i 's/from config import/from app.core.config import/g' backend/app/database.py

# Scraper импорты
sed -i 's/from app.services.ai_data_extractor/from backend.app.services.ai_data_extractor/g' scraper/estate_scraper/real_estate_scraper/pipelines.py

echo "✅ Импорты обновлены"

# Создаем новые Dockerfile'ы
echo "🐳 Создаем новые Dockerfile'ы..."

cat > infrastructure/docker/scraper.Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копирование requirements
COPY scraper/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода scraper
COPY scraper/ ./scraper/

# Копирование AI модуля
COPY backend/app/services/ai_data_extractor.py ./backend/app/services/

# Установка рабочей директории
WORKDIR /app/scraper

# Запуск
CMD ["scrapy", "crawl", "generic_api", "-a", "config=lalafo"]
EOF

cat > infrastructure/docker/frontend.Dockerfile << 'EOF'
FROM nginx:alpine

# Копирование статических файлов
COPY frontend/static/ /usr/share/nginx/html/static/
COPY frontend/templates/ /usr/share/nginx/html/templates/

# Конфигурация nginx
COPY infrastructure/nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
EOF

echo "✅ Dockerfile'ы созданы"

# Создаем requirements для scraper
cat > scraper/requirements.txt << 'EOF'
scrapy==2.11.0
requests==2.31.0
itemadapter==0.8.0
python-dotenv==1.0.0
EOF

echo "✅ Requirements для scraper созданы"

# Создаем nginx конфигурацию
cat > infrastructure/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    sendfile        on;
    keepalive_timeout  65;

    server {
        listen 80;
        server_name localhost;

        root /usr/share/nginx/html;
        index index.html;

        # Статические файлы
        location /static/ {
            alias /usr/share/nginx/html/static/;
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # API проксирование
        location /api/ {
            proxy_pass http://api:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # WebSocket проксирование
        location /ws/ {
            proxy_pass http://api:8000;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Все остальные запросы к frontend
        location / {
            try_files $uri $uri/ /index.html;
        }
    }
}
EOF

echo "✅ Nginx конфигурация создана"

# Обновляем docker-compose
echo "🐳 Обновляем docker-compose.yml..."

cat > infrastructure/docker-compose.yml << 'EOF'
version: '3.8'

services:
  # База данных PostgreSQL
  db:
    image: postgres:15
    container_name: estate_db
    environment:
      POSTGRES_DB: estate_db
      POSTGRES_USER: estate_user
      POSTGRES_PASSWORD: admin123
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    networks:
      - estate_network

  # Redis для кэширования и очередей
  redis:
    image: redis:7-alpine
    container_name: estate_redis
    ports:
      - "6379:6379"
    networks:
      - estate_network

  # Elasticsearch для поиска
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: estate_elasticsearch
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data
    ports:
      - "9200:9200"
      - "9300:9300"
    networks:
      - estate_network

  # PgAdmin для управления БД
  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: estate_pgadmin
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@admin.com
      PGADMIN_DEFAULT_PASSWORD: admin123
    ports:
      - "5050:80"
    depends_on:
      - db
    networks:
      - estate_network

  # Backend API
  api:
    build:
      context: .
      dockerfile: infrastructure/docker/backend.Dockerfile
    container_name: estate_api
    environment:
      - DB_HOST=db
      - DB_PORT=5432
      - DB_NAME=estate_db
      - DB_USER=estate_user
      - DB_PASSWORD=admin123
      - REDIS_URL=redis://redis:6379
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
      - ELASTICSEARCH_INDEX=real_estate_ads
      - SCRAPY_API_URL=http://api:8000/api/ads
      - PIPELINE_INTERVAL_HOURS=3
      - RUN_IMMEDIATELY_ON_START=false
      - SCRAPING_SOURCES=house,lalafo,stroka
      - ENABLE_SCRAPING=true
      - ENABLE_PHOTO_PROCESSING=true
      - ENABLE_DUPLICATE_PROCESSING=true
      - ENABLE_REALTOR_DETECTION=true
      - ENABLE_ELASTICSEARCH_REINDEX=true
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
      - elasticsearch
    volumes:
      - ./logs:/app/logs
    networks:
      - estate_network

  # Scraper сервис
  scraper:
    build:
      context: .
      dockerfile: infrastructure/docker/scraper.Dockerfile
    container_name: estate_scraper
    environment:
      - SCRAPY_API_URL=http://api:8000/api/ads
    depends_on:
      - api
    volumes:
      - ./logs:/app/logs
    networks:
      - estate_network

  # Frontend (опционально)
  frontend:
    build:
      context: .
      dockerfile: infrastructure/docker/frontend.Dockerfile
    container_name: estate_frontend
    ports:
      - "80:80"
    depends_on:
      - api
    networks:
      - estate_network

volumes:
  postgres_data:
  elasticsearch_data:

networks:
  estate_network:
    driver: bridge
EOF

echo "✅ Docker-compose обновлен"

# Тестируем импорты
echo "🧪 Тестируем импорты..."

cd backend
python -c "from app.core.config import *; print('✅ Backend config imports work')" || echo "❌ Backend config imports failed"
python -c "from app.services.automation_service import automation_service; print('✅ Automation service imports work')" || echo "❌ Automation service imports failed"
cd ..

cd scraper
python -c "import sys; sys.path.append('..'); from estate_scraper.real_estate_scraper.pipelines import DatabasePipeline; print('✅ Scraper pipelines imports work')" || echo "❌ Scraper pipelines imports failed"
cd ..

echo "✅ Миграция завершена!"

echo ""
echo "🎉 Миграция на новую структуру завершена!"
echo ""
echo "📁 Новая структура:"
echo "├── backend/          # Backend API"
echo "├── scraper/          # Scraper сервис"
echo "├── frontend/         # Frontend (опционально)"
echo "├── infrastructure/   # Docker и K8s"
echo "├── configs/          # Конфигурации"
echo "├── scripts/          # Скрипты"
echo "├── docs/             # Документация"
echo "└── tools/            # Утилиты"
echo ""
echo "🚀 Для запуска используйте:"
echo "docker-compose -f infrastructure/docker-compose.yml up -d"
echo ""
echo "📋 Доступные сервисы:"
echo "- API: http://localhost:8000"
echo "- Frontend: http://localhost:80"
echo "- PgAdmin: http://localhost:5050"
echo "- Elasticsearch: http://localhost:9200"
echo ""
echo "💾 Резервная копия сохранена в: $backup_dir" 