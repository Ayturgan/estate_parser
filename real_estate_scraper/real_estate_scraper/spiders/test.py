import scrapy
from scrapy_playwright.page import PageMethod

class HouseTestSpider(scrapy.Spider):
   name = 'house_test'
   
   def start_requests(self):
       # Тестируем на одном объявлении
       yield scrapy.Request(
           url='https://www.house.kg/kupit-kvartiru?page=1',
           callback=self.parse,
           meta={
               'playwright': True,
               'playwright_page_methods': [
                   PageMethod('wait_for_load_state', 'networkidle'),
               ]
           }
       )
   
   def parse(self, response):
       # Берем первое объявление для теста
       first_listing = response.css('div.listing').get()
       if first_listing:
           link = response.css('div.listing div.top-info p.title a::attr(href)').get()
           if link:
               full_url = response.urljoin(link)
               yield scrapy.Request(
                   url=full_url,
                   callback=self.parse_detail,
                   meta={
                       'playwright': True,
                       'playwright_page_methods': [
                           PageMethod('wait_for_load_state', 'networkidle'),
                           PageMethod('wait_for_timeout', 2000),  # Ждем загрузки
                       ]
                   }
               )

   def parse_detail(self, response):
       # Извлекаем основные данные + телефон
       item = {
           'url': response.url,
           'title': response.css('h1::text').get(),
           'price': response.css('div.price::text').get(),
           
           # Тестируем разные варианты селекторов для телефона
           'phone_css': response.css('.show-number .number::text').get(),
           'phone_xpath': response.xpath('normalize-space(//a[contains(@class, "show-number")]//div[@class="number"]/text())').get(),
           'phone_alt': response.css('a.show-number div.number::text').get(),
           
           # Проверим, есть ли элемент вообще
           'has_show_number': bool(response.css('.show-number').get()),
           'has_number_div': bool(response.css('.number').get()),
           
           # Посмотрим на HTML кнопки
           'phone_button_html': response.css('.show-number').get(),
       }
       
       # Логируем результат
       self.logger.info(f"=== PHONE TEST RESULTS ===")
       self.logger.info(f"URL: {item['url']}")
       self.logger.info(f"Phone CSS: {item['phone_css']}")
       self.logger.info(f"Phone XPath: {item['phone_xpath']}")
       self.logger.info(f"Phone Alt: {item['phone_alt']}")
       self.logger.info(f"Has show-number: {item['has_show_number']}")
       self.logger.info(f"Has number div: {item['has_number_div']}")
       self.logger.info(f"Button HTML: {item['phone_button_html']}")
       
       yield item