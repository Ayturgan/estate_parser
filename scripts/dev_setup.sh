#!/bin/bash

# Скрипт для локальной разработки
# Запускает backend и scraper локально без Docker

echo "🚀 Настройка локальной среды разработки..."

# Проверяем, что мы в корневой директории проекта
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Запустите скрипт из корневой директории проекта"
    exit 1
fi

# Устанавливаем переменные окружения
export PYTHONPATH=/home/aetheriw/Downloads/estate_parser/backend:/home/aetheriw/Downloads/estate_parser/scraper

# Функция для проверки зависимостей
check_dependencies() {
    echo "🔍 Проверяем зависимости..."
    
    # Проверяем Python
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python3 не найден"
        exit 1
    fi
    
    # Проверяем pip
    if ! command -v pip3 &> /dev/null; then
        echo "❌ pip3 не найден"
        exit 1
    fi
    
    echo "✅ Зависимости в порядке"
}

# Функция для установки зависимостей backend
install_backend_deps() {
    echo "📦 Устанавливаем зависимости backend..."
    cd backend
    pip3 install -r requirements.txt
    cd ..
}

# Функция для установки зависимостей scraper
install_scraper_deps() {
    echo "📦 Устанавливаем зависимости scraper..."
    cd scraper
    pip3 install -r requirements.txt
    cd ..
}

# Функция для запуска backend
start_backend() {
    echo "🌐 Запускаем backend локально..."
    cd backend
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
    BACKEND_PID=$!
    echo "✅ Backend запущен (PID: $BACKEND_PID)"
    cd ..
}

# Функция для запуска scraper
start_scraper() {
    echo "🕷️ Запускаем scraper локально..."
    cd scraper/estate_scraper
    
    # Проверяем AI модуль
    echo "🔍 Проверяем AI модуль..."
    python3 -c "
import sys
sys.path.append('/home/aetheriw/Downloads/estate_parser/backend')
try:
    from app.services.ai_data_extractor import AIDataExtractor
    print('✅ AI Data Extractor доступен!')
except ImportError as e:
    print(f'❌ Ошибка импорта AI модуля: {e}')
"
    
    # Запускаем worker
    python3 real_estate_scraper/worker.py &
    SCRAPER_PID=$!
    echo "✅ Scraper запущен (PID: $SCRAPER_PID)"
    cd ../..
}

# Функция для остановки всех процессов
cleanup() {
    echo "🛑 Останавливаем процессы..."
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null
        echo "✅ Backend остановлен"
    fi
    if [ ! -z "$SCRAPER_PID" ]; then
        kill $SCRAPER_PID 2>/dev/null
        echo "✅ Scraper остановлен"
    fi
    exit 0
}

# Обработчик сигналов для корректного завершения
trap cleanup SIGINT SIGTERM

# Основная логика
case "${1:-all}" in
    "backend")
        check_dependencies
        install_backend_deps
        start_backend
        echo "🌐 Backend запущен на http://localhost:8000"
        echo "📚 API документация: http://localhost:8000/docs"
        wait
        ;;
    "scraper")
        check_dependencies
        install_scraper_deps
        start_scraper
        echo "🕷️ Scraper запущен"
        wait
        ;;
    "all"|*)
        check_dependencies
        install_backend_deps
        install_scraper_deps
        start_backend
        sleep 3  # Даем backend время запуститься
        start_scraper
        echo "🎉 Все сервисы запущены!"
        echo "🌐 Backend: http://localhost:8000"
        echo "📚 API документация: http://localhost:8000/docs"
        echo "🕷️ Scraper: работает в фоне"
        echo "💡 Для остановки нажмите Ctrl+C"
        wait
        ;;
esac 