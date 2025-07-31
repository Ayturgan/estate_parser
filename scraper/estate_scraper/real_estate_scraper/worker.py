import redis
import subprocess
import json
import uuid
from datetime import datetime
import os
import select
import signal
import time
import re
from logger import get_scraping_logger, remove_scraping_logger

REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

JOBS_KEY = "scrapy_jobs"
LOG_PREFIX = "scrapy_log:"

# Паттерны для распознавания ошибок парсинга
PARSING_ERROR_PATTERNS = [
    r"Spider finished with parsing errors",
    r"has_parsing_errors.*True",
    r"Error extracting field",
    r"Error extracting item data",
    r"Error extracting photos",
    r"Error extracting phones",
    r"Invalid JSON in response",
    r"Required selectors.*not found",
    r"No ads container found",
    r"Error processing item",
    # Критические сетевые ошибки
    r"DNS lookup failed",
    r"Connection refused",
    r"Network unreachable",
    r"Host unreachable",
    r"Request failed",
    r"HTTP запрос неуспешен",
    r"Gave up retrying",
    # Исключаем небольшие ошибки загрузки - они нормальны
    # r"Downloader/exception_count"  # Убираем этот паттерн
]

# Паттерны для распознавания успешного завершения
SUCCESS_PATTERNS = [
    r"Spider closed.*success",
    r"Items scraped.*\d+",
    r"✅.*successfully",
    r"Successfully extracted",
    r"item_scraped_count.*\d+",  # Добавляем проверку статистики
    r"finish_reason.*finished"    # Добавляем проверку причины завершения
]


def update_status(job_id, **kwargs):
    job = r.hget(JOBS_KEY, job_id)
    job = json.loads(job) if job else {}
    job.update(kwargs)
    r.hset(JOBS_KEY, job_id, json.dumps(job))

def append_log(job_id, line):
    r.rpush(f"{LOG_PREFIX}{job_id}", line)

def check_job_status(job_id):
    """Проверяет статус задачи в Redis"""
    try:
        job = r.hget(JOBS_KEY, job_id)
        if job:
            job_data = json.loads(job)
            return job_data.get('status')
    except Exception as e:
        print(f"[Worker] Ошибка проверки статуса задачи {job_id}: {e}")
    return None

def detect_parsing_errors(log_line):
    """Определяет наличие ошибок парсинга в логе"""
    for pattern in PARSING_ERROR_PATTERNS:
        if re.search(pattern, log_line, re.IGNORECASE):
            return True
    return False

def detect_success_signals(log_line):
    """Определяет наличие сигналов успешного завершения"""
    for pattern in SUCCESS_PATTERNS:
        if re.search(pattern, log_line, re.IGNORECASE):
            return True
    return False

def monitor_process_with_stop_check(proc, job_id):
    """Мониторинг процесса с проверкой остановки и ошибок парсинга"""
    import fcntl
    
    # Делаем stdout неблокирующим
    fd = proc.stdout.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    
    last_check_time = time.time()
    check_interval = 5  # Проверяем каждые 5 секунд
    
    # Флаги для отслеживания состояния
    parsing_errors_detected = False
    success_signals_detected = False
    
    while proc.poll() is None:  # Пока процесс работает
        current_time = time.time()
        
        # Проверяем остановку каждые 5 секунд
        if current_time - last_check_time >= check_interval:
            status = check_job_status(job_id)
            if status == "остановлено":
                print(f"[Worker] 🛑 Получен сигнал остановки для задачи {job_id}")
                append_log(job_id, "[Worker] 🛑 Задача остановлена по запросу пользователя")
                
                # Останавливаем процесс
                try:
                    proc.terminate()  # Мягкая остановка
                    time.sleep(3)
                    if proc.poll() is None:
                        proc.kill()  # Принудительная остановка
                        print(f"[Worker] ⚡ Принудительная остановка процесса {job_id}")
                except Exception as e:
                    print(f"[Worker] Ошибка остановки процесса {job_id}: {e}")
                
                return (True, False, False)  # Задача была остановлена
            
            last_check_time = current_time
        
        # Читаем доступные строки из stdout
        try:
            ready, _, _ = select.select([proc.stdout], [], [], 0.1)
            if ready:
                line = proc.stdout.readline()
                if line:
                    line = line.rstrip()
                    append_log(job_id, line)
                    
                    # Анализируем лог на наличие ошибок парсинга
                    if not parsing_errors_detected and detect_parsing_errors(line):
                        parsing_errors_detected = True
                        print(f"[Worker] ⚠️ Обнаружены ошибки парсинга в задаче {job_id}")
                        append_log(job_id, "[Worker] ⚠️ Обнаружены ошибки парсинга")
                    
                    # Анализируем лог на наличие сигналов успеха
                    if not success_signals_detected and detect_success_signals(line):
                        success_signals_detected = True
                        print(f"[Worker] ✅ Обнаружены сигналы успешного парсинга в задаче {job_id}")
                        append_log(job_id, "[Worker] ✅ Обнаружены сигналы успешного парсинга")
                        
        except Exception as e:
            print(f"[Worker] Ошибка чтения stdout: {e}")
            time.sleep(0.1)
    
    # Читаем оставшиеся строки после завершения процесса
    try:
        for line in proc.stdout:
            line = line.rstrip()
            append_log(job_id, line)
            
            # Анализируем оставшиеся логи
            if not parsing_errors_detected and detect_parsing_errors(line):
                parsing_errors_detected = True
                print(f"[Worker] ⚠️ Обнаружены ошибки парсинга в задаче {job_id}")
                append_log(job_id, "[Worker] ⚠️ Обнаружены ошибки парсинга")
            
            if not success_signals_detected and detect_success_signals(line):
                success_signals_detected = True
                print(f"[Worker] ✅ Обнаружены сигналы успешного парсинга в задаче {job_id}")
                append_log(job_id, "[Worker] ✅ Обнаружены сигналы успешного парсинга")
                
    except Exception:
        pass
    
    # Возвращаем информацию о состоянии парсинга
    return False, parsing_errors_detected, success_signals_detected

print("[Scrapy Worker] Старт воркера. Ожидание задач...")

try:
    subprocess.run(["playwright", "install", "--with-deps"], check=True)
except Exception as e:
    print(f"[Scrapy Worker] Не удалось установить браузеры Playwright: {e}")

while True:
    task = r.brpop("scrapy_tasks")[1]
    task = json.loads(task)
    job_id = task["job_id"]
    config = task["config"]
    spider = task["spider"]
    
    # Создаем детальный логгер для задачи
    scraping_logger = get_scraping_logger(job_id, config)
    scraping_logger.log_job_start()
    
    update_status(job_id, status="выполняется", started_at=datetime.utcnow().isoformat())
    os.chdir("/app/estate_scraper/real_estate_scraper")
    
    # Передаем job_id в переменных окружения для пауков
    env = os.environ.copy()
    env['SCRAPY_JOB_ID'] = job_id
    env['SCRAPY_CONFIG_NAME'] = config
    
    cmd = ["scrapy", "crawl", spider, "-a", f"config={config}", "-a", f"job_id={job_id}"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    
    print(f"[Worker] 🚀 Запущен процесс парсинга {config} (job_id: {job_id}, pid: {proc.pid})")
    
    # Мониторинг процесса с проверкой остановки и ошибок парсинга
    was_stopped, parsing_errors_detected, success_signals_detected = monitor_process_with_stop_check(proc, job_id)
    
    proc.wait()
    
    # Определяем статус завершения с учетом ошибок парсинга
    if was_stopped:
        status = "остановлено"
        scraping_logger.log_job_end("stopped", "Задача была остановлена пользователем")
        print(f"[Worker] 🛑 Задача {job_id} остановлена")
    elif proc.returncode == 0:
        if parsing_errors_detected:
            status = "завершено с ошибками парсинга"
            scraping_logger.log_job_end("completed_with_parsing_errors", "Задача завершена, но обнаружены ошибки парсинга")
            print(f"[Worker] ⚠️ Задача {job_id} завершена с ошибками парсинга")
        else:
            status = "завершено"
            scraping_logger.log_job_end("completed")
            print(f"[Worker] ✅ Задача {job_id} завершена успешно")
    else:
        if parsing_errors_detected:
            status = "ошибка парсинга"
            scraping_logger.log_job_end("failed_with_parsing_errors", f"Process returned code {proc.returncode} and parsing errors detected")
            print(f"[Worker] ❌ Задача {job_id} завершена с ошибкой парсинга")
        else:
            status = "ошибка"
            scraping_logger.log_job_end("failed", f"Process returned code {proc.returncode}")
            print(f"[Worker] ❌ Задача {job_id} завершена с ошибкой")
    
    # Добавляем информацию об ошибках парсинга в статус
    status_data = {
        'status': status, 
        'finished_at': datetime.utcnow().isoformat(), 
        'returncode': proc.returncode,
        'parsing_errors_detected': parsing_errors_detected,
        'success_signals_detected': success_signals_detected
    }
    
    update_status(job_id, **status_data)
    
    # Очищаем логгер после завершения задачи
    remove_scraping_logger(job_id, config) 