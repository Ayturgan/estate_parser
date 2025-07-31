#!/usr/bin/env python3
"""
Тестовый файл для проверки двух подходов к дедупликации изображений ПО ОТДЕЛЬНОСТИ:
1. Перцептивное хеширование (pHash, dHash, aHash) - ОТДЕЛЬНО
2. Эмбеддинги изображений с использованием современных моделей - ОТДЕЛЬНО

Использование:
python image_deduplication_test_separate.py
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

class PerceptualHashTester:
    """Тестер только для перцептивного хеширования"""
    
    def __init__(self):
        self.hash_types = ['pHash', 'dHash', 'aHash', 'wHash', 'cHash']
        self.thresholds = {
            'pHash': 0.8,    # Порог для перцептивного хеша
            'dHash': 0.8,    # Порог для разностного хеша
            'aHash': 0.8,    # Порог для среднего хеша
            'wHash': 0.8,    # Порог для вейвлет хеша
            'cHash': 0.8,    # Порог для цветового хеша
        }
    
    def calculate_perceptual_hashes(self, image_path: str) -> Dict[str, str]:
        """Вычисляет различные типы перцептивных хешей для изображения"""
        try:
            with Image.open(image_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                hashes = {
                    'pHash': str(imagehash.phash(img)),
                    'dHash': str(imagehash.dhash(img)),
                    'aHash': str(imagehash.average_hash(img)),
                    'wHash': str(imagehash.whash(img)),
                    'cHash': str(imagehash.colorhash(img)),
                }
                
                logger.info(f"Вычислены хеши для {image_path}: {list(hashes.keys())}")
                return hashes
                
        except Exception as e:
            logger.error(f"Ошибка вычисления хешей для {image_path}: {e}")
            return {}
    
    def calculate_hamming_distance(self, hash1: str, hash2: str) -> int:
        """Вычисляет расстояние Хэмминга между двумя хешами"""
        if len(hash1) != len(hash2):
            return max(len(hash1), len(hash2))
        
        distance = 0
        for i in range(len(hash1)):
            if hash1[i] != hash2[i]:
                distance += 1
        return distance
    
    def calculate_perceptual_similarity(self, hashes1: Dict[str, str], hashes2: Dict[str, str]) -> Dict[str, float]:
        """Вычисляет схожесть на основе перцептивных хешей"""
        similarities = {}
        
        for hash_type in self.hash_types:
            if hash_type in hashes1 and hash_type in hashes2:
                distance = self.calculate_hamming_distance(hashes1[hash_type], hashes2[hash_type])
                
                max_distances = {
                    'pHash': 64,
                    'dHash': 64,
                    'aHash': 64,
                    'wHash': 64,
                    'cHash': 42,
                }
                
                max_distance = max_distances.get(hash_type, 64)
                similarity = 1.0 - (distance / max_distance)
                similarities[hash_type] = max(0.0, similarity)
            else:
                similarities[hash_type] = 0.0
        
        return similarities
    
    def is_duplicate_by_perceptual_hash(self, image1_path: str, image2_path: str) -> Dict:
        """Определяет дубликат ТОЛЬКО по перцептивным хешам"""
        logger.info(f"🔍 Анализ перцептивными хешами: {image1_path} vs {image2_path}")
        
        hashes1 = self.calculate_perceptual_hashes(image1_path)
        hashes2 = self.calculate_perceptual_hashes(image2_path)
        
        if not hashes1 or not hashes2:
            return {'is_duplicate': False, 'similarity': 0.0, 'method': 'perceptual_hash'}
        
        similarities = self.calculate_perceptual_similarity(hashes1, hashes2)
        avg_similarity = np.mean(list(similarities.values()))
        
        # Проверяем каждый тип хеша отдельно
        hash_results = {}
        for hash_type in self.hash_types:
            similarity = similarities.get(hash_type, 0.0)
            threshold = self.thresholds.get(hash_type, 0.8)
            hash_results[hash_type] = {
                'similarity': similarity,
                'is_duplicate': similarity > threshold,
                'threshold': threshold
            }
        
        # Общий результат по среднему значению
        overall_is_duplicate = avg_similarity > 0.8
        
        return {
            'is_duplicate': overall_is_duplicate,
            'similarity': avg_similarity,
            'method': 'perceptual_hash',
            'hash_results': hash_results,
            'hashes1': hashes1,
            'hashes2': hashes2
        }


class CLIPEmbeddingTester:
    """Тестер только для CLIP эмбеддингов"""
    
    def __init__(self):
        self.clip_model = None
        self.clip_processor = None
        self.threshold = 0.8  # Порог для CLIP эмбеддингов
        self._load_models()
    
    def _load_models(self):
        """Загрузка CLIP модели"""
        try:
            logger.info("Загружаем CLIP модель...")
            self.clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            logger.info("CLIP модель загружена успешно")
        except Exception as e:
            logger.error(f"Ошибка загрузки CLIP модели: {e}")
            self.clip_model = None
            self.clip_processor = None
    
    def get_image_embeddings(self, image_path: str) -> Optional[np.ndarray]:
        """Получает эмбеддинги изображения с помощью CLIP модели"""
        if self.clip_model is None or self.clip_processor is None:
            logger.warning("CLIP модель не загружена")
            return None
            
        try:
            image = Image.open(image_path).convert('RGB')
            inputs = self.clip_processor(images=image, return_tensors="pt")
            
            with torch.no_grad():
                image_features = self.clip_model.get_image_features(**inputs)
                
            embeddings = image_features.cpu().numpy()
            embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
            
            logger.info(f"Получены CLIP эмбеддинги для {image_path}: {embeddings.shape}")
            return embeddings[0]
            
        except Exception as e:
            logger.error(f"Ошибка получения CLIP эмбеддингов для {image_path}: {e}")
            return None
    
    def calculate_embedding_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Вычисляет косинусное сходство между эмбеддингами"""
        if embedding1 is None or embedding2 is None:
            return 0.0
            
        try:
            embedding1_norm = embedding1 / np.linalg.norm(embedding1)
            embedding2_norm = embedding2 / np.linalg.norm(embedding2)
            similarity = np.dot(embedding1_norm, embedding2_norm)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Ошибка вычисления сходства CLIP эмбеддингов: {e}")
            return 0.0
    
    def is_duplicate_by_clip_embedding(self, image1_path: str, image2_path: str) -> Dict:
        """Определяет дубликат ТОЛЬКО по CLIP эмбеддингам"""
        logger.info(f"🔍 Анализ CLIP эмбеддингами: {image1_path} vs {image2_path}")
        
        embedding1 = self.get_image_embeddings(image1_path)
        embedding2 = self.get_image_embeddings(image2_path)
        
        if embedding1 is None or embedding2 is None:
            return {'is_duplicate': False, 'similarity': 0.0, 'method': 'clip_embedding'}
        
        similarity = self.calculate_embedding_similarity(embedding1, embedding2)
        is_duplicate = similarity > self.threshold
        
        return {
            'is_duplicate': is_duplicate,
            'similarity': similarity,
            'method': 'clip_embedding',
            'threshold': self.threshold
        }


class SeparateImageDeduplicationTester:
    """Тестер для отдельного тестирования каждого подхода"""
    
    def __init__(self):
        self.perceptual_tester = PerceptualHashTester()
        self.clip_tester = CLIPEmbeddingTester()
    
    def test_perceptual_hash_only(self, image1_path: str, image2_path: str) -> Dict:
        """Тестирует ТОЛЬКО перцептивное хеширование"""
        print(f"\n{'='*60}")
        print(f"🔍 ТЕСТ: ТОЛЬКО ПЕРЦЕПТИВНОЕ ХЕШИРОВАНИЕ")
        print(f"{'='*60}")
        
        result = self.perceptual_tester.is_duplicate_by_perceptual_hash(image1_path, image2_path)
        self._print_perceptual_result(result, image1_path, image2_path)
        return result
    
    def test_clip_embedding_only(self, image1_path: str, image2_path: str) -> Dict:
        """Тестирует ТОЛЬКО CLIP эмбеддинги"""
        print(f"\n{'='*60}")
        print(f"🔍 ТЕСТ: ТОЛЬКО CLIP ЭМБЕДДИНГИ")
        print(f"{'='*60}")
        
        result = self.clip_tester.is_duplicate_by_clip_embedding(image1_path, image2_path)
        self._print_clip_result(result, image1_path, image2_path)
        return result
    
    def test_both_methods_separately(self, image1_path: str, image2_path: str):
        """Тестирует оба метода ОТДЕЛЬНО"""
        print(f"\n{'='*80}")
        print(f"🧪 СРАВНЕНИЕ ДВУХ ПОДХОДОВ ОТДЕЛЬНО")
        print(f"{'='*80}")
        print(f"Изображение 1: {Path(image1_path).name}")
        print(f"Изображение 2: {Path(image2_path).name}")
        print(f"{'='*80}")
        
        # Тест перцептивного хеширования
        perceptual_result = self.test_perceptual_hash_only(image1_path, image2_path)
        
        # Тест CLIP эмбеддингов
        clip_result = self.test_clip_embedding_only(image1_path, image2_path)
        
        # Сравнение результатов
        self._print_comparison(perceptual_result, clip_result)
    
    def _print_perceptual_result(self, result: Dict, image1_path: str, image2_path: str):
        """Выводит результат перцептивного хеширования"""
        print(f"Изображение 1: {Path(image1_path).name}")
        print(f"Изображение 2: {Path(image2_path).name}")
        print(f"{'-'*40}")
        
        if 'hash_results' in result:
            print(f"РЕЗУЛЬТАТЫ ПО ТИПАМ ХЕШЕЙ:")
            for hash_type, hash_result in result['hash_results'].items():
                status = "✅ ДУБЛИКАТ" if hash_result['is_duplicate'] else "❌ НЕ ДУБЛИКАТ"
                print(f"{hash_type:8}: {hash_result['similarity']:.3f} (порог: {hash_result['threshold']:.1f}) - {status}")
        
        print(f"\nОБЩИЙ РЕЗУЛЬТАТ:")
        print(f"Средняя схожесть: {result['similarity']:.3f}")
        status = "✅ ДУБЛИКАТ" if result['is_duplicate'] else "❌ НЕ ДУБЛИКАТ"
        print(f"Решение: {status}")
    
    def _print_clip_result(self, result: Dict, image1_path: str, image2_path: str):
        """Выводит результат CLIP эмбеддингов"""
        print(f"Изображение 1: {Path(image1_path).name}")
        print(f"Изображение 2: {Path(image2_path).name}")
        print(f"{'-'*40}")
        
        print(f"CLIP ЭМБЕДДИНГИ:")
        print(f"Схожесть: {result['similarity']:.3f}")
        print(f"Порог: {result['threshold']:.1f}")
        status = "✅ ДУБЛИКАТ" if result['is_duplicate'] else "❌ НЕ ДУБЛИКАТ"
        print(f"Решение: {status}")
    
    def _print_comparison(self, perceptual_result: Dict, clip_result: Dict):
        """Выводит сравнение результатов двух методов"""
        print(f"\n{'='*60}")
        print(f"СРАВНЕНИЕ РЕЗУЛЬТАТОВ")
        print(f"{'='*60}")
        
        print(f"ПЕРЦЕПТИВНЫЕ ХЕШИ:")
        print(f"  Схожесть: {perceptual_result['similarity']:.3f}")
        print(f"  Решение: {'✅ ДУБЛИКАТ' if perceptual_result['is_duplicate'] else '❌ НЕ ДУБЛИКАТ'}")
        
        print(f"\nCLIP ЭМБЕДДИНГИ:")
        print(f"  Схожесть: {clip_result['similarity']:.3f}")
        print(f"  Решение: {'✅ ДУБЛИКАТ' if clip_result['is_duplicate'] else '❌ НЕ ДУБЛИКАТ'}")
        
        # Анализ согласованности
        agreement = perceptual_result['is_duplicate'] == clip_result['is_duplicate']
        print(f"\nСОГЛАСОВАННОСТЬ МЕТОДОВ:")
        if agreement:
            print(f"  ✅ Методы согласны: {'оба определили как дубликат' if perceptual_result['is_duplicate'] else 'оба определили как НЕ дубликат'}")
        else:
            print(f"  ⚠️ Методы НЕ согласны:")
            print(f"    - Перцептивные хеши: {'дубликат' if perceptual_result['is_duplicate'] else 'НЕ дубликат'}")
            print(f"    - CLIP эмбеддинги: {'дубликат' if clip_result['is_duplicate'] else 'НЕ дубликат'}")
    
    def test_with_sample_images(self, test_dir: str = "test_images"):
        """Тестирует оба метода отдельно на всех парах изображений"""
        test_path = Path(test_dir)
        if not test_path.exists():
            logger.error(f"Директория {test_dir} не существует")
            return
        
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
                
                # Тестируем оба метода отдельно
                self.test_both_methods_separately(str(image1), str(image2))
                
                # Сохраняем результаты для сводного отчета
                perceptual_result = self.perceptual_tester.is_duplicate_by_perceptual_hash(str(image1), str(image2))
                clip_result = self.clip_tester.is_duplicate_by_clip_embedding(str(image1), str(image2))
                
                results.append({
                    'image1': image1.name,
                    'image2': image2.name,
                    'perceptual': perceptual_result,
                    'clip': clip_result
                })
        
        # Сводный отчет
        self._print_summary_report(results)
    
    def _print_summary_report(self, results: List[Dict]):
        """Выводит сводный отчет по всем результатам"""
        print(f"\n{'='*80}")
        print(f"СВОДНЫЙ ОТЧЕТ ПО ОТДЕЛЬНЫМ МЕТОДАМ")
        print(f"{'='*80}")
        
        total_pairs = len(results)
        
        # Статистика по перцептивным хешам
        perceptual_duplicates = sum(1 for r in results if r['perceptual']['is_duplicate'])
        perceptual_sims = [r['perceptual']['similarity'] for r in results]
        avg_perceptual_sim = np.mean(perceptual_sims) if perceptual_sims else 0
        
        # Статистика по CLIP эмбеддингам
        clip_duplicates = sum(1 for r in results if r['clip']['is_duplicate'])
        clip_sims = [r['clip']['similarity'] for r in results]
        avg_clip_sim = np.mean(clip_sims) if clip_sims else 0
        
        # Согласованность методов
        agreements = sum(1 for r in results if r['perceptual']['is_duplicate'] == r['clip']['is_duplicate'])
        
        print(f"Всего пар изображений: {total_pairs}")
        print(f"\nПЕРЦЕПТИВНЫЕ ХЕШИ:")
        print(f"  Найдено дубликатов: {perceptual_duplicates}")
        print(f"  Процент дубликатов: {(perceptual_duplicates/total_pairs)*100:.1f}%")
        print(f"  Средняя схожесть: {avg_perceptual_sim:.3f}")
        
        print(f"\nCLIP ЭМБЕДДИНГИ:")
        print(f"  Найдено дубликатов: {clip_duplicates}")
        print(f"  Процент дубликатов: {(clip_duplicates/total_pairs)*100:.1f}%")
        print(f"  Средняя схожесть: {avg_clip_sim:.3f}")
        
        print(f"\nСОГЛАСОВАННОСТЬ МЕТОДОВ:")
        print(f"  Согласных решений: {agreements}/{total_pairs}")
        print(f"  Процент согласованности: {(agreements/total_pairs)*100:.1f}%")


def main():
    """Основная функция для запуска тестов"""
    print("🧪 ТЕСТ ДЕДУПЛИКАЦИИ ИЗОБРАЖЕНИЙ (ОТДЕЛЬНЫЕ МЕТОДЫ)")
    print("="*60)
    print("Этот тест проверяет два подхода к дедупликации изображений ОТДЕЛЬНО:")
    print("1. Перцептивное хеширование (pHash, dHash, aHash, wHash, cHash)")
    print("2. Эмбеддинги изображений с помощью CLIP модели")
    print("="*60)
    
    # Создаем тестер
    tester = SeparateImageDeduplicationTester()
    
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