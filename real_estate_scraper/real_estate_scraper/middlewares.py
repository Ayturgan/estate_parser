# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals
import random
from .user_agents import USER_AGENTS
# from .proxy_config import proxy_config
from scrapy.downloadermiddlewares.useragent import UserAgentMiddleware


class ParserSpiderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(self, response, result, spider):
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, or item objects.
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Request or item objects.
        pass

    async def process_start(self, start):
        # Called with an async iterator over the spider start() method or the
        # maching method of an earlier spider middleware.
        async for item_or_request in start:
            yield item_or_request

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class ParserDownloaderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the downloader middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        # Called for each request that goes through the downloader
        # middleware.

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        request.headers['User-Agent'] = random.choice(USER_AGENTS)
        return None

    def process_response(self, request, response, spider):
        # Called with the response returned from the downloader.

        # Must either;
        # - return a Response object
        # - return a Request object
        # - or raise IgnoreRequest
        return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class ProxyMiddleware:
    def process_request(self, request, spider):
        # Получаем случайный прокси из конфигурации
        # proxy = proxy_config.get_random_proxy()
        # if proxy:
        #     request.meta['proxy'] = proxy['http']
        #     # Добавляем заголовки для прокси
        #     request.headers['Proxy-Authorization'] = f'Basic {proxy.get("auth", "")}'
        #     spider.logger.info(f'Using proxy: {proxy["http"]}')
        pass


class RetryMiddleware:
    def process_response(self, request, response, spider):
        if response.status in [500, 502, 503, 504, 522, 524, 408, 429]:
            retry_count = request.meta.get('retry_count', 0)
            if retry_count < 3:  
                request.meta['retry_count'] = retry_count + 1
                request.meta['download_timeout'] = 30 * (retry_count + 1)
                return request
        return response


class RandomUserAgentMiddleware(UserAgentMiddleware):
    """
    Middleware для случайной смены User-Agent при каждом запросе
    """
    
    def __init__(self, user_agent_list):
        super().__init__()
        self.user_agent_list = user_agent_list

    @classmethod
    def from_crawler(cls, crawler):
        user_agent_list = crawler.settings.get('USER_AGENT_LIST', USER_AGENTS)
        return cls(user_agent_list)

    def process_request(self, request, spider):
        user_agent = random.choice(self.user_agent_list)
        request.headers['User-Agent'] = user_agent
