#!/usr/bin/env python3
"""
Скрипт для просмотра логов парсинга
"""

import os
import json
import glob
import sys
from datetime import datetime
import argparse

def list_log_files():
    """Показывает список всех файлов логов"""
    log_dir = "/app/logs/scraping"
    if not os.path.exists(log_dir):
        print(f"❌ Директория логов не найдена: {log_dir}")
        return []
    
    # Находим все файлы логов
    log_files = glob.glob(os.path.join(log_dir, "scraping_*"))
    if not log_files:
        print("📁 Логи парсинга не найдены")
        return []
    
    # Группируем по job_id
    jobs = {}
    for file_path in log_files:
        filename = os.path.basename(file_path)
        if filename.startswith("scraping_"):
            # Извлекаем job_id и config_name
            parts = filename.replace("scraping_", "").split("_")
            if len(parts) >= 2:
                job_id = parts[0]
                config_name = parts[1].split(".")[0]  # Убираем расширение
                
                if job_id not in jobs:
                    jobs[job_id] = {
                        'job_id': job_id,
                        'config_name': config_name,
                        'files': []
                    }
                jobs[job_id]['files'].append(file_path)
    
    return list(jobs.values())

def show_job_stats(job_id, config_name):
    """Показывает статистику конкретной задачи"""
    stats_file = f"/app/logs/scraping/scraping_{job_id}_{config_name}_stats.json"
    
    if not os.path.exists(stats_file):
        print(f"❌ Файл статистики не найден: {stats_file}")
        return False
    
    try:
        with open(stats_file, 'r', encoding='utf-8') as f:
            stats = json.load(f)
        
        print(f"\n📊 СТАТИСТИКА ЗАДАЧИ {job_id}")
        print("=" * 50)
        print(f"⚙️ Конфиг: {stats.get('config_name', 'N/A')}")
        print(f"🕐 Старт: {stats.get('started_at', 'N/A')}")
        print(f"🏁 Финиш: {stats.get('finished_at', 'N/A')}")
        print(f"🎯 Статус: {stats.get('status', 'N/A').upper()}")
        
        # Вычисляем длительность
        if stats.get('started_at') and stats.get('finished_at'):
            try:
                start = datetime.fromisoformat(stats['started_at'])
                end = datetime.fromisoformat(stats['finished_at'])
                duration = end - start
                print(f"⏱️ Длительность: {duration}")
            except:
                print(f"⏱️ Длительность: N/A")
        
        print(f"\n📈 РЕЗУЛЬТАТЫ:")
        print(f"   📄 Страниц обработано: {stats.get('pages_processed', 0)}")
        print(f"   🏠 Объявлений найдено: {stats.get('items_total', 0)}")
        print(f"   ✅ Успешно обработано: {stats.get('items_processed', 0)}")
        print(f"   ❌ Ошибок обработки: {stats.get('items_failed', 0)}")
        print(f"   📡 API вызовов успешных: {stats.get('api_calls_success', 0)}")
        print(f"   🚫 API вызовов неуспешных: {stats.get('api_calls_failed', 0)}")
        
        # Показываем ошибки
        errors = stats.get('errors', [])
        if errors:
            print(f"\n💥 ОШИБКИ ({len(errors)}):")
            for i, error in enumerate(errors[:5], 1):  # Показываем первые 5
                print(f"   {i}. {error.get('message', 'Unknown error')}")
                if error.get('context'):
                    print(f"      Контекст: {error['context']}")
        
        # Показываем предупреждения
        warnings = stats.get('warnings', [])
        if warnings:
            print(f"\n⚠️ ПРЕДУПРЕЖДЕНИЯ ({len(warnings)}):")
            for i, warning in enumerate(warnings[:5], 1):  # Показываем первые 5
                print(f"   {i}. {warning.get('message', 'Unknown warning')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка чтения статистики: {e}")
        return False

def show_log_content(job_id, config_name, log_type="main", lines=50):
    """Показывает содержимое лога"""
    log_files = {
        'main': f"/app/logs/scraping/scraping_{job_id}_{config_name}.log",
        'errors': f"/app/logs/scraping/scraping_{job_id}_{config_name}_errors.log",
        'stats': f"/app/logs/scraping/scraping_{job_id}_{config_name}_stats.json"
    }
    
    log_file = log_files.get(log_type)
    if not log_file or not os.path.exists(log_file):
        print(f"❌ Файл лога не найден: {log_file}")
        return False
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            content = f.readlines()
        
        print(f"\n📄 ЛОГ: {os.path.basename(log_file)}")
        print("=" * 50)
        
        if log_type == 'stats':
            # Для JSON форматируем красиво
            with open(log_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            # Показываем последние N строк
            start_line = max(0, len(content) - lines)
            for line_num, line in enumerate(content[start_line:], start_line + 1):
                print(f"{line_num:4d}: {line.rstrip()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка чтения лога: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Просмотр логов парсинга")
    parser.add_argument('--list', '-l', action='store_true', help='Показать список всех задач')
    parser.add_argument('--job', '-j', help='ID задачи для просмотра')
    parser.add_argument('--config', '-c', help='Название конфига (опционально)')
    parser.add_argument('--type', '-t', choices=['main', 'errors', 'stats'], default='main', 
                       help='Тип лога (main/errors/stats)')
    parser.add_argument('--lines', '-n', type=int, default=50, 
                       help='Количество строк для показа (по умолчанию: 50)')
    parser.add_argument('--stats', '-s', action='store_true', help='Показать только статистику')
    
    args = parser.parse_args()
    
    # Если нет аргументов - показываем список
    if len(sys.argv) == 1:
        args.list = True
    
    if args.list:
        print("📋 СПИСОК ЗАДАЧ ПАРСИНГА")
        print("=" * 50)
        
        jobs = list_log_files()
        if not jobs:
            return
        
        # Сортируем по времени создания файла
        for job in sorted(jobs, key=lambda x: os.path.getctime(x['files'][0]), reverse=True):
            job_id = job['job_id']
            config_name = job['config_name']
            
            # Пытаемся получить статистику
            stats_file = f"/app/logs/scraping/scraping_{job_id}_{config_name}_stats.json"
            status = "неизвестен"
            duration = "N/A"
            items_processed = "N/A"
            
            if os.path.exists(stats_file):
                try:
                    with open(stats_file, 'r', encoding='utf-8') as f:
                        stats = json.load(f)
                    status = stats.get('status', 'неизвестен')
                    items_processed = stats.get('items_processed', 0)
                    
                    # Вычисляем длительность
                    if stats.get('started_at') and stats.get('finished_at'):
                        try:
                            start = datetime.fromisoformat(stats['started_at'])
                            end = datetime.fromisoformat(stats['finished_at'])
                            duration = str(end - start).split('.')[0]  # Убираем микросекунды
                        except:
                            pass
                except:
                    pass
            
            print(f"🔹 {job_id} | {config_name} | {status} | {duration} | {items_processed} объявлений")
        
        print(f"\n💡 Для просмотра деталей: python {sys.argv[0]} -j <job_id>")
        return
    
    if args.job:
        # Ищем конфиг по job_id если не указан
        if not args.config:
            jobs = list_log_files()
            matching_jobs = [j for j in jobs if j['job_id'] == args.job]
            if not matching_jobs:
                print(f"❌ Задача с ID {args.job} не найдена")
                return
            args.config = matching_jobs[0]['config_name']
        
        if args.stats:
            show_job_stats(args.job, args.config)
        else:
            # Сначала показываем статистику
            show_job_stats(args.job, args.config)
            
            # Затем содержимое лога
            print(f"\n" + "=" * 50)
            show_log_content(args.job, args.config, args.type, args.lines)
    else:
        print("❌ Укажите ID задачи с помощью --job или используйте --list для списка задач")

if __name__ == "__main__":
    main() 