#!/usr/bin/env python3
"""
Тестовый файл для проверки двух подходов к дедупликации изображений:
1. Перцептивное хеширование (pHash, dHash, aHash)
2. Эмбеддинги изображений с использованием современных моделей

Использование:
python image_deduplication_test.py
"""

import os
import sys
import logging
import numpy as np
from typing import List, Tuple, Dict, Optional
from pathlib import Path
import cv2
from PIL import Image
import imagehash
from sentence_transformers import SentenceTransformer
import torch
from transformers import CLIPProcessor, CLIPModel
import requests
from io import BytesIO

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ImageDeduplicationTester:
    def __init__(self):
        """Инициализация тестера с современными моделями 2025 года"""
        self.clip_model = None
        self.clip_processor = None
        self.text_model = None
        self._load_models()
        
    def _load_models(self):
        """Загрузка современных моделей для обработки изображений"""
        try:
            # Загружаем CLIP модель для эмбеддингов изображений
            logger.info("Загружаем CLIP модель...")
            self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            logger.info("CLIP модель загружена успешно")
        except Exception as e:
            logger.error(f"Ошибка загрузки CLIP модели: {e}")
            self.clip_model = None
            self.clip_processor = None
            
        try:
            # Загружаем текстовую модель для сравнения описаний
            logger.info("Загружаем текстовую модель...")
            self.text_model = SentenceTransformer("BAAI/bge-m3")
            logger.info("Текстовая модель загружена успешно")
        except Exception as e:
            logger.error(f"Ошибка загрузки текстовой модели: {e}")
            self.text_model = None
    
    def calculate_perceptual_hashes(self, image_path: str) -> Dict[str, str]:
        """
        Вычисляет различные типы перцептивных хешей для изображения
        
        Args:
            image_path: Путь к изображению
            
        Returns:
            Словарь с различными типами хешей
        """
        try:
            # Загружаем изображение
            with Image.open(image_path) as img:
                # Конвертируем в RGB если нужно
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Вычисляем различные типы перцептивных хешей
                hashes = {
                    'pHash': str(imagehash.phash(img)),      # Перцептивный хеш
                    'dHash': str(imagehash.dhash(img)),      # Разностный хеш
                    'aHash': str(imagehash.average_hash(img)), # Средний хеш
                    'wHash': str(imagehash.whash(img)),      # Вейвлет хеш
                    'cHash': str(imagehash.colorhash(img)),  # Цветовой хеш
                }
                
                logger.info(f"Вычислены хеши для {image_path}: {list(hashes.keys())}")
                return hashes
                
        except Exception as e:
            logger.error(f"Ошибка вычисления хешей для {image_path}: {e}")
            return {}
    
    def calculate_hamming_distance(self, hash1: str, hash2: str) -> int:
        """
        Вычисляет расстояние Хэмминга между двумя хешами
        
        Args:
            hash1: Первый хеш
            hash2: Второй хеш
            
        Returns:
            Расстояние Хэмминга (количество отличающихся битов)
        """
        if len(hash1) != len(hash2):
            return max(len(hash1), len(hash2))
        
        distance = 0
        for i in range(len(hash1)):
            if hash1[i] != hash2[i]:
                distance += 1
        return distance
    
    def calculate_perceptual_similarity(self, hashes1: Dict[str, str], hashes2: Dict[str, str]) -> Dict[str, float]:
        """
        Вычисляет схожесть на основе перцептивных хешей
        
        Args:
            hashes1: Хеши первого изображения
            hashes2: Хеши второго изображения
            
        Returns:
            Словарь с оценками схожести для каждого типа хеша
        """
        similarities = {}
        
        for hash_type in ['pHash', 'dHash', 'aHash', 'wHash', 'cHash']:
            if hash_type in hashes1 and hash_type in hashes2:
                distance = self.calculate_hamming_distance(hashes1[hash_type], hashes2[hash_type])
                
                # Максимальное расстояние для каждого типа хеша
                max_distances = {
                    'pHash': 64,   # 64 бита
                    'dHash': 64,   # 64 бита
                    'aHash': 64,   # 64 бита
                    'wHash': 64,   # 64 бита
                    'cHash': 42,   # 42 бита для цветового хеша
                }
                
                max_distance = max_distances.get(hash_type, 64)
                # Нормализуем расстояние и конвертируем в схожесть
                similarity = 1.0 - (distance / max_distance)
                similarities[hash_type] = max(0.0, similarity)
            else:
                similarities[hash_type] = 0.0
        
        return similarities
    
    def get_image_embeddings(self, image_path: str) -> Optional[np.ndarray]:
        """
        Получает эмбеддинги изображения с помощью CLIP модели
        
        Args:
            image_path: Путь к изображению
            
        Returns:
            Эмбеддинг изображения или None в случае ошибки
        """
        if self.clip_model is None or self.clip_processor is None:
            logger.warning("CLIP модель не загружена")
            return None
            
        try:
            # Загружаем изображение
            image = Image.open(image_path).convert('RGB')
            
            # Обрабатываем изображение через CLIP
            inputs = self.clip_processor(images=image, return_tensors="pt")
            
            # Получаем эмбеддинги
            with torch.no_grad():
                image_features = self.clip_model.get_image_features(**inputs)
                
            # Конвертируем в numpy и нормализуем
            embeddings = image_features.cpu().numpy()
            embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
            
            logger.info(f"Получены эмбеддинги для {image_path}: {embeddings.shape}")
            return embeddings[0]  # Возвращаем первый (и единственный) эмбеддинг
            
        except Exception as e:
            logger.error(f"Ошибка получения эмбеддингов для {image_path}: {e}")
            return None
    
    def calculate_embedding_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Вычисляет косинусное сходство между эмбеддингами
        
        Args:
            embedding1: Эмбеддинг первого изображения
            embedding2: Эмбеддинг второго изображения
            
        Returns:
            Косинусное сходство (от 0 до 1)
        """
        if embedding1 is None or embedding2 is None:
            return 0.0
            
        try:
            # Нормализуем эмбеддинги
            embedding1_norm = embedding1 / np.linalg.norm(embedding1)
            embedding2_norm = embedding2 / np.linalg.norm(embedding2)
            
            # Вычисляем косинусное сходство
            similarity = np.dot(embedding1_norm, embedding2_norm)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Ошибка вычисления сходства эмбеддингов: {e}")
            return 0.0
    
    def analyze_image_pair(self, image1_path: str, image2_path: str, description1: str = "", description2: str = "") -> Dict:
        """
        Анализирует пару изображений с помощью обоих подходов
        
        Args:
            image1_path: Путь к первому изображению
            image2_path: Путь ко второму изображению
            description1: Описание первого изображения
            description2: Описание второго изображения
            
        Returns:
            Словарь с результатами анализа
        """
        logger.info(f"Анализируем пару изображений: {image1_path} vs {image2_path}")
        
        results = {
            'image1_path': image1_path,
            'image2_path': image2_path,
            'perceptual_hashes': {},
            'embedding_similarity': 0.0,
            'text_similarity': 0.0,
            'overall_similarity': 0.0,
            'is_duplicate': False
        }
        
        # 1. Перцептивное хеширование
        logger.info("Вычисляем перцептивные хеши...")
        hashes1 = self.calculate_perceptual_hashes(image1_path)
        hashes2 = self.calculate_perceptual_hashes(image2_path)
        
        if hashes1 and hashes2:
            perceptual_similarities = self.calculate_perceptual_similarity(hashes1, hashes2)
            results['perceptual_hashes'] = {
                'hashes1': hashes1,
                'hashes2': hashes2,
                'similarities': perceptual_similarities
            }
            
            # Средняя схожесть по всем типам хешей
            avg_perceptual_sim = np.mean(list(perceptual_similarities.values()))
            logger.info(f"Средняя схожесть по перцептивным хешам: {avg_perceptual_sim:.3f}")
        
        # 2. Эмбеддинги изображений
        logger.info("Вычисляем эмбеддинги изображений...")
        embedding1 = self.get_image_embeddings(image1_path)
        embedding2 = self.get_image_embeddings(image2_path)
        
        if embedding1 is not None and embedding2 is not None:
            embedding_sim = self.calculate_embedding_similarity(embedding1, embedding2)
            results['embedding_similarity'] = embedding_sim
            logger.info(f"Схожесть по эмбеддингам: {embedding_sim:.3f}")
        
        # 3. Текстовое сходство (если есть описания)
        if description1 and description2 and self.text_model:
            logger.info("Вычисляем текстовое сходство...")
            try:
                embeddings1 = self.text_model.encode(description1)
                embeddings2 = self.text_model.encode(description2)
                text_sim = self.calculate_embedding_similarity(embeddings1, embeddings2)
                results['text_similarity'] = text_sim
                logger.info(f"Текстовое сходство: {text_sim:.3f}")
            except Exception as e:
                logger.error(f"Ошибка вычисления текстового сходства: {e}")
        
        # 4. Общая оценка схожести
        weights = {
            'perceptual': 0.4,
            'embedding': 0.5,
            'text': 0.1
        }
        
        overall_sim = 0.0
        total_weight = 0.0
        
        # Перцептивные хеши
        if results['perceptual_hashes']:
            avg_perceptual = np.mean(list(results['perceptual_hashes']['similarities'].values()))
            overall_sim += avg_perceptual * weights['perceptual']
            total_weight += weights['perceptual']
        
        # Эмбеддинги
        if results['embedding_similarity'] > 0:
            overall_sim += results['embedding_similarity'] * weights['embedding']
            total_weight += weights['embedding']
        
        # Текстовое сходство
        if results['text_similarity'] > 0:
            overall_sim += results['text_similarity'] * weights['text']
            total_weight += weights['text']
        
        if total_weight > 0:
            results['overall_similarity'] = overall_sim / total_weight
            results['is_duplicate'] = results['overall_similarity'] > 0.8  # Порог для дубликата
        
        logger.info(f"Общая схожесть: {results['overall_similarity']:.3f}")
        logger.info(f"Дубликат: {results['is_duplicate']}")
        
        return results
    
    def test_with_sample_images(self, test_dir: str = "test_images"):
        """
        Тестирует алгоритмы на примере изображений
        
        Args:
            test_dir: Директория с тестовыми изображениями
        """
        test_path = Path(test_dir)
        if not test_path.exists():
            logger.error(f"Директория {test_dir} не существует")
            return
        
        # Ищем изображения
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
        image_files = [f for f in test_path.iterdir() if f.suffix.lower() in image_extensions]
        
        if len(image_files) < 2:
            logger.error(f"Недостаточно изображений в {test_dir}. Нужно минимум 2.")
            return
        
        logger.info(f"Найдено {len(image_files)} изображений для тестирования")
        
        # Создаем все возможные пары
        results = []
        for i in range(len(image_files)):
            for j in range(i + 1, len(image_files)):
                image1 = image_files[i]
                image2 = image_files[j]
                
                logger.info(f"\n{'='*50}")
                logger.info(f"Тестируем пару: {image1.name} vs {image2.name}")
                
                result = self.analyze_image_pair(str(image1), str(image2))
                results.append(result)
                
                # Выводим детальный отчет
                self._print_detailed_report(result)
        
        # Сводный отчет
        self._print_summary_report(results)
    
    def _print_detailed_report(self, result: Dict):
        """Выводит детальный отчет по результатам анализа"""
        print(f"\n{'='*60}")
        print(f"ДЕТАЛЬНЫЙ ОТЧЕТ")
        print(f"{'='*60}")
        print(f"Изображение 1: {Path(result['image1_path']).name}")
        print(f"Изображение 2: {Path(result['image2_path']).name}")
        print(f"{'='*60}")
        
        # Перцептивные хеши
        if result['perceptual_hashes']:
            print(f"\nПЕРЦЕПТИВНЫЕ ХЕШИ:")
            print(f"{'-'*30}")
            similarities = result['perceptual_hashes']['similarities']
            for hash_type, similarity in similarities.items():
                print(f"{hash_type:8}: {similarity:.3f}")
            
            avg_perceptual = np.mean(list(similarities.values()))
            print(f"{'Среднее':8}: {avg_perceptual:.3f}")
        
        # Эмбеддинги
        print(f"\nЭМБЕДДИНГИ ИЗОБРАЖЕНИЙ:")
        print(f"{'-'*30}")
        print(f"Схожесть: {result['embedding_similarity']:.3f}")
        
        # Текстовое сходство
        if result['text_similarity'] > 0:
            print(f"\nТЕКСТОВОЕ СХОДСТВО:")
            print(f"{'-'*30}")
            print(f"Схожесть: {result['text_similarity']:.3f}")
        
        # Общий результат
        print(f"\nОБЩИЙ РЕЗУЛЬТАТ:")
        print(f"{'-'*30}")
        print(f"Общая схожесть: {result['overall_similarity']:.3f}")
        print(f"Дубликат: {'ДА' if result['is_duplicate'] else 'НЕТ'}")
        
        # Рекомендация
        if result['is_duplicate']:
            print(f"✅ РЕКОМЕНДАЦИЯ: Изображения являются дубликатами")
        else:
            print(f"❌ РЕКОМЕНДАЦИЯ: Изображения НЕ являются дубликатами")
    
    def _print_summary_report(self, results: List[Dict]):
        """Выводит сводный отчет по всем результатам"""
        print(f"\n{'='*80}")
        print(f"СВОДНЫЙ ОТЧЕТ")
        print(f"{'='*80}")
        
        total_pairs = len(results)
        duplicates_found = sum(1 for r in results if r['is_duplicate'])
        
        print(f"Всего пар изображений: {total_pairs}")
        print(f"Найдено дубликатов: {duplicates_found}")
        print(f"Процент дубликатов: {(duplicates_found/total_pairs)*100:.1f}%")
        
        if results:
            avg_overall_sim = np.mean([r['overall_similarity'] for r in results])
            avg_embedding_sim = np.mean([r['embedding_similarity'] for r in results])
            
            print(f"\nСредние показатели:")
            print(f"Общая схожесть: {avg_overall_sim:.3f}")
            print(f"Схожесть по эмбеддингам: {avg_embedding_sim:.3f}")
            
            # Анализ перцептивных хешей
            perceptual_sims = []
            for r in results:
                if r['perceptual_hashes']:
                    avg_perceptual = np.mean(list(r['perceptual_hashes']['similarities'].values()))
                    perceptual_sims.append(avg_perceptual)
            
            if perceptual_sims:
                avg_perceptual_sim = np.mean(perceptual_sims)
                print(f"Схожесть по перцептивным хешам: {avg_perceptual_sim:.3f}")


def main():
    """Основная функция для запуска тестов"""
    print("🧪 ТЕСТ ДЕДУПЛИКАЦИИ ИЗОБРАЖЕНИЙ")
    print("="*50)
    print("Этот тест проверяет два подхода к дедупликации изображений:")
    print("1. Перцептивное хеширование (pHash, dHash, aHash, wHash, cHash)")
    print("2. Эмбеддинги изображений с помощью CLIP модели")
    print("="*50)
    
    # Создаем тестер
    tester = ImageDeduplicationTester()
    
    # Проверяем наличие тестовых изображений
    test_dir = "test_images"
    if not os.path.exists(test_dir):
        print(f"\n❌ Директория {test_dir} не найдена!")
        print(f"Создайте директорию {test_dir} и поместите туда тестовые изображения.")
        print(f"Рекомендуется: 2 похожих изображения + 1 совершенно другое")
        return
    
    # Запускаем тест
    print(f"\n🔍 Запускаем тест с изображениями из {test_dir}...")
    tester.test_with_sample_images(test_dir)
    
    print(f"\n✅ Тест завершен!")


if __name__ == "__main__":
    main() 