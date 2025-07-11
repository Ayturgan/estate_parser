#!/usr/bin/env python3
"""
Утилита для мониторинга логов парсинга в реальном времени
"""

import os
import time
import argparse
import glob
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Цветовая схема для терминала
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    ENDC = '\033[0m'  # Сброс цвета

class LogMonitor(FileSystemEventHandler):
    """Мониторинг логов парсинга"""
    
    def __init__(self, log_dir="logs/scraping", follow_new=True, show_errors_only=False):
        self.log_dir = log_dir
        self.follow_new = follow_new
        self.show_errors_only = show_errors_only
        self.watched_files = {}
        self.last_positions = {}
        
        print(f"{Colors.CYAN}📡 Запуск мониторинга логов в: {log_dir}{Colors.ENDC}")
        print(f"{Colors.YELLOW}⚙️ Режим: {'только ошибки' if show_errors_only else 'все логи'}{Colors.ENDC}")
        print("-" * 70)
    
    def start_monitoring(self):
        """Запуск мониторинга"""
        # Проверяем существующие логи
        self.check_existing_logs()
        
        if self.follow_new:
            # Следим за новыми файлами
            observer = Observer()
            observer.schedule(self, self.log_dir, recursive=True)
            observer.start()
            
            try:
                print(f"{Colors.GREEN}✅ Мониторинг запущен. Нажмите Ctrl+C для остановки{Colors.ENDC}")
                while True:
                    time.sleep(1)
                    self.check_file_updates()
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}🛑 Остановка мониторинга...{Colors.ENDC}")
                observer.stop()
            observer.join()
        else:
            # Однократная проверка
            self.check_file_updates()
    
    def check_existing_logs(self):
        """Проверка существующих логов"""
        if not os.path.exists(self.log_dir):
            print(f"{Colors.RED}❌ Папка логов не найдена: {self.log_dir}{Colors.ENDC}")
            print(f"{Colors.YELLOW}💡 Возможно, парсинг еще не запускался или нужно запустить Docker контейнеры{Colors.ENDC}")
            return
        
        log_files = glob.glob(f"{self.log_dir}/*.log")
        if not log_files:
            print(f"{Colors.YELLOW}⚠️ Файлы логов не найдены в {self.log_dir}{Colors.ENDC}")
            print(f"{Colors.CYAN}💡 Логи появятся после запуска задач парсинга{Colors.ENDC}")
        else:
            print(f"{Colors.GREEN}📁 Найдено файлов логов: {len(log_files)}{Colors.ENDC}")
            for log_file in sorted(log_files):
                filename = os.path.basename(log_file)
                size = os.path.getsize(log_file)
                mtime = datetime.fromtimestamp(os.path.getmtime(log_file))
                print(f"   📄 {filename} ({size} байт, изменен: {mtime.strftime('%H:%M:%S')})")
                
                # Добавляем в отслеживаемые
                self.watched_files[log_file] = True
                self.last_positions[log_file] = 0
    
    def check_file_updates(self):
        """Проверка обновлений в файлах"""
        for log_file in list(self.watched_files.keys()):
            if os.path.exists(log_file):
                self.read_new_lines(log_file)
    
    def read_new_lines(self, filepath):
        """Читает новые строки из файла"""
        try:
            current_size = os.path.getsize(filepath)
            last_pos = self.last_positions.get(filepath, 0)
            
            if current_size > last_pos:
                with open(filepath, 'r', encoding='utf-8') as f:
                    f.seek(last_pos)
                    new_lines = f.readlines()
                    
                    for line in new_lines:
                        line = line.strip()
                        if line:
                            self.format_and_print_line(line, filepath)
                    
                    self.last_positions[filepath] = f.tell()
                    
        except Exception as e:
            print(f"{Colors.RED}❌ Ошибка чтения файла {filepath}: {e}{Colors.ENDC}")
    
    def format_and_print_line(self, line, filepath):
        """Форматирует и выводит строку лога"""
        filename = os.path.basename(filepath)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Фильтрация по уровню если нужно
        if self.show_errors_only:
            if not any(level in line for level in ['ERROR', 'CRITICAL', '❌', '🚫', '💥']):
                return
        
        # Цветовое кодирование по типу сообщения
        color = Colors.WHITE
        prefix = "📝"
        
        if any(keyword in line for keyword in ['ERROR', 'CRITICAL', '❌', '🚫', '💥']):
            color = Colors.RED
            prefix = "🚨"
        elif any(keyword in line for keyword in ['WARNING', '⚠️']):
            color = Colors.YELLOW
            prefix = "⚠️"
        elif any(keyword in line for keyword in ['SUCCESS', '✅', '🎉']):
            color = Colors.GREEN
            prefix = "✅"
        elif any(keyword in line for keyword in ['INFO', '🚀', '📊', '📋']):
            color = Colors.CYAN
            prefix = "ℹ️"
        elif any(keyword in line for keyword in ['DEBUG', '🔍']):
            color = Colors.PURPLE
            prefix = "🔍"
        
        # Выводим с цветом и меткой файла
        print(f"{Colors.BLUE}[{timestamp}]{Colors.ENDC} {Colors.BOLD}[{filename}]{Colors.ENDC} {prefix} {color}{line}{Colors.ENDC}")
    
    def on_created(self, event):
        """Обработка создания новых файлов"""
        if event.is_directory:
            return
        
        if event.src_path.endswith('.log'):
            print(f"{Colors.GREEN}📁 Новый лог файл: {os.path.basename(event.src_path)}{Colors.ENDC}")
            self.watched_files[event.src_path] = True
            self.last_positions[event.src_path] = 0
    
    def on_modified(self, event):
        """Обработка изменения файлов"""
        if event.is_directory:
            return
        
        if event.src_path.endswith('.log') and event.src_path in self.watched_files:
            self.read_new_lines(event.src_path)

def main():
    parser = argparse.ArgumentParser(description="Мониторинг логов парсинга недвижимости")
    parser.add_argument(
        "--dir", 
        default="logs/scraping", 
        help="Папка с логами (по умолчанию: logs/scraping)"
    )
    parser.add_argument(
        "--errors-only", 
        action="store_true", 
        help="Показывать только ошибки и предупреждения"
    )
    parser.add_argument(
        "--no-follow", 
        action="store_true", 
        help="Не следить за новыми файлами (одноразовая проверка)"
    )
    
    args = parser.parse_args()
    
    print(f"{Colors.BOLD}{Colors.CYAN}🔍 Мониторинг логов парсинга недвижимости{Colors.ENDC}")
    print(f"{Colors.CYAN}════════════════════════════════════════{Colors.ENDC}")
    
    monitor = LogMonitor(
        log_dir=args.dir,
        follow_new=not args.no_follow,
        show_errors_only=args.errors_only
    )
    
    monitor.start_monitoring()

if __name__ == "__main__":
    main() 