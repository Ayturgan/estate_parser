import redis
import subprocess
import json
import uuid
from datetime import datetime
import os

REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

JOBS_KEY = "scrapy_jobs"
LOG_PREFIX = "scrapy_log:"


def update_status(job_id, **kwargs):
    job = r.hget(JOBS_KEY, job_id)
    job = json.loads(job) if job else {}
    job.update(kwargs)
    r.hset(JOBS_KEY, job_id, json.dumps(job))

def append_log(job_id, line):
    r.rpush(f"{LOG_PREFIX}{job_id}", line)

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
    update_status(job_id, status="выполняется", started_at=datetime.utcnow().isoformat())
    os.chdir("/app/real_estate_scraper/real_estate_scraper")
    cmd = ["scrapy", "crawl", spider, "-a", f"config={config}"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:
        append_log(job_id, line)
    proc.wait()
    status = "завершено" if proc.returncode == 0 else "ошибка"
    update_status(job_id, status=status, finished_at=datetime.utcnow().isoformat(), returncode=proc.returncode) 