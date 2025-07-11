from typing import List, Dict
import random
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
# load_dotenv()

class ProxyConfig:
    def __init__(self):
        # Список прокси в формате:
        # {
        #     'http': 'http://user:pass@host:port',
        #     'https': 'http://user:pass@host:port'
        # }
        self.proxies: List[Dict[str, str]] = []
        
    def add_proxy(self, host: str, port: int, username: str = None, password: str = None):
        """Добавить прокси в пул"""
        proxy = {
            'http': f'http://{host}:{port}',
            'https': f'http://{host}:{port}'
        }
        
        if username and password:
            auth = f'{username}:{password}@'
            proxy['http'] = f'http://{auth}{host}:{port}'
            proxy['https'] = f'http://{auth}{host}:{port}'
            
        self.proxies.append(proxy)
    
    def get_random_proxy(self) -> Dict[str, str]:
        """Получить случайный прокси из пула"""
        return random.choice(self.proxies) if self.proxies else None

# Создаем конфигурацию
proxy_config = ProxyConfig()

# Добавляем прокси из переменных окружения 
# BRIGHT_DATA_USERNAME = os.getenv('BRIGHT_DATA_USERNAME')
# BRIGHT_DATA_PASSWORD = os.getenv('BRIGHT_DATA_PASSWORD')
# OXYLABS_USERNAME = os.getenv('OXYLABS_USERNAME')
# OXYLABS_PASSWORD = os.getenv('OXYLABS_PASSWORD')

# if BRIGHT_DATA_USERNAME and BRIGHT_DATA_PASSWORD:
#     proxy_config.add_proxy(
#         host='brd.superproxy.io',
#         port=22225,
#         username=BRIGHT_DATA_USERNAME,
#         password=BRIGHT_DATA_PASSWORD
#     )

# if OXYLABS_USERNAME and OXYLABS_PASSWORD:
#     proxy_config.add_proxy(
#         host='pr.oxylabs.io',
#         port=7777,
#         username=OXYLABS_USERNAME,
#         password=OXYLABS_PASSWORD
#     )

# Добавляем локальный прокси для тестирования 
# proxy_config.add_proxy(
#     host='127.0.0.1',
#     port=8080
# ) 