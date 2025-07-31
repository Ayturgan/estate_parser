import requests
import asyncio
import aiohttp
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from concurrent.futures import ThreadPoolExecutor
import time
from collections import defaultdict
import re
from datetime import datetime

# Подключение к базе данных
DATABASE_URL = "postgresql://estate_user:admin123@localhost:5432/estate_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        db.close()
        raise e

def check_url_status(url):
    """Синхронная проверка статуса URL"""
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        code = response.status_code
        if code == 200:
            return "✅ OK"
        elif code == 404:
            return "❌ Not Found"
        elif code == 410:
            return "☠️ Gone"
        elif code == 302:
            return f"↪️ Redirect → {response.headers.get('Location', '')}"
        else:
            return f"⚠️ {code}"
    except Exception as e:
        return f"🔥 Error: {str(e)}"

async def check_url_status_async(session, url):
    """Асинхронная проверка статуса URL"""
    try:
        async with session.head(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)) as response:
            code = response.status
            if code == 200:
                return url, "✅ OK"
            elif code == 404:
                return url, "❌ Not Found"
            elif code == 410:
                return url, "☠️ Gone"
            elif code == 302:
                location = response.headers.get('Location', '')
                return url, f"↪️ Redirect → {location}"
            else:
                return url, f"⚠️ {code}"
    except Exception as e:
        return url, f"🔥 Error: {str(e)}"

def check_urls_batch(urls, batch_size=50, max_workers=10):
    """Проверка ссылок батчами с использованием ThreadPoolExecutor"""
    results = []
    
    def check_batch(url_batch):
        batch_results = []
        for url in url_batch:
            status = check_url_status(url)
            batch_results.append((url, status))
        return batch_results
    
    # Разбиваем URLs на батчи
    batches = [urls[i:i + batch_size] for i in range(0, len(urls), batch_size)]
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        batch_results = list(executor.map(check_batch, batches))
        
    # Объединяем результаты
    for batch in batch_results:
        results.extend(batch)
    
    return results

async def check_urls_async(urls, batch_size=100):
    """Асинхронная проверка ссылок батчами"""
    results = []
    
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=50)) as session:
        # Разбиваем на батчи для контроля нагрузки
        for i in range(0, len(urls), batch_size):
            batch_urls = urls[i:i + batch_size]
            tasks = [check_url_status_async(session, url) for url in batch_urls]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            results.extend(batch_results)
    
    return results

def analyze_results(results):
    """Анализ результатов проверки"""
    stats = defaultdict(int)
    domain_stats = defaultdict(int)
    
    for url, status in results:
        stats[status] += 1
        
        # Извлекаем домен для статистики
        try:
            domain = url.split('/')[2]
            domain_stats[domain] += 1
        except:
            pass
    
    analysis = []
    analysis.append("📊 СТАТИСТИКА:")
    analysis.append(f"Всего проверено: {len(results)}")
    for status, count in stats.items():
        analysis.append(f"{status}: {count}")
    
    analysis.append("\n🌐 ПО ДОМЕНАМ:")
    for domain, count in domain_stats.items():
        analysis.append(f"{domain}: {count}")
    
    return "\n".join(analysis)

def save_results_to_file(results, analysis, filename=None):
    """Сохранение результатов в файл"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"link_validation_results_{timestamp}.txt"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("🔍 РЕЗУЛЬТАТЫ ПРОВЕРКИ ССЫЛОК\n")
        f.write("=" * 50 + "\n\n")
        
        # Анализ
        f.write(analysis)
        f.write("\n\n" + "=" * 50 + "\n\n")
        
        # Детальные результаты
        f.write("📋 ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ:\n\n")
        for url, status in results:
            f.write(f"{url} → {status}\n")
    
    return filename

# Подключение к БД и получение ссылок
try:
    db = get_db()
    
    # Получаем source_url из уникальных объявлений через связь с основной таблицей
    unique_ads_query = text("""
        SELECT a.source_url 
        FROM unique_ads ua 
        JOIN ads a ON ua.base_ad_id = a.id 
        WHERE a.source_url IS NOT NULL
    """)
    unique_ads_result = db.execute(unique_ads_query)
    unique_ads = unique_ads_result.fetchall()
    
    # Извлекаем URLs в список
    urls = [source_url for (source_url,) in unique_ads]
    
    print(f"🔍 Найдено {len(urls)} ссылок для проверки")
    
    # Выбираем метод проверки
    if len(urls) > 1000:
        print("⚡ Используем асинхронную проверку для большого количества ссылок...")
        start_time = time.time()
        results = asyncio.run(check_urls_async(urls))
        end_time = time.time()
        print(f"⏱️ Время выполнения: {end_time - start_time:.2f} секунд")
    else:
        print("⚡ Используем многопоточную проверку...")
        start_time = time.time()
        results = check_urls_batch(urls)
        end_time = time.time()
        print(f"⏱️ Время выполнения: {end_time - start_time:.2f} секунд")
    
    # Анализируем результаты
    analysis = analyze_results(results)
    
    # Сохраняем в файл
    filename = save_results_to_file(results, analysis)
    print(f"\n💾 Результаты сохранены в файл: {filename}")
    
    # Выводим только краткую статистику в консоль
    print("\n" + analysis)
    
    db.close()
except Exception as e:
    print(f"❌ Ошибка подключения к БД: {e}")
