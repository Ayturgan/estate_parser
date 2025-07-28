#!/bin/bash

echo "🚀 Установка зависимостей для системы валидации фотографий"
echo "=" * 60

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Установите Python 3.8+"
    exit 1
fi

echo "✅ Python найден: $(python3 --version)"

# Обновляем pip
echo "📦 Обновление pip..."
python3 -m pip install --upgrade pip

# Устанавливаем зависимости
echo "📦 Установка Python зависимостей..."
pip install -r requirements.txt

# Проверяем установку Tesseract
echo "🔍 Проверка Tesseract OCR..."
if ! command -v tesseract &> /dev/null; then
    echo "⚠️ Tesseract не найден. Установите Tesseract:"
    echo "  Ubuntu/Debian: sudo apt install tesseract-ocr tesseract-ocr-rus"
    echo "  macOS: brew install tesseract tesseract-lang"
    echo "  Windows: скачайте с https://github.com/UB-Mannheim/tesseract/wiki"
else
    echo "✅ Tesseract найден: $(tesseract --version | head -n 1)"
fi

# Проверяем установку CUDA (опционально)
echo "🔍 Проверка CUDA..."
if command -v nvidia-smi &> /dev/null; then
    echo "✅ CUDA доступна: $(nvidia-smi --query-gpu=name --format=csv,noheader,nounits)"
else
    echo "ℹ️ CUDA не найдена. PyTorch будет использовать CPU"
fi

echo ""
echo "🎉 Установка завершена!"
echo "Теперь можно запустить: python photo_validator.py" 