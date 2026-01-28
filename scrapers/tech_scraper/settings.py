# Scrapy settings for tech_scraper project

BOT_NAME = 'techpulse_scraper'

SPIDER_MODULES = ['tech_scraper.spiders']
NEWSPIDER_MODULE = 'tech_scraper.spiders'

# Obey robots.txt rules
ROBOTSTXT_OBEY = True

# Configure concurrent requests
CONCURRENT_REQUESTS = 1  # Sequential processing to avoid timeouts
DOWNLOAD_DELAY = 2  # Longer delay between requests

# Timeout settings
DOWNLOAD_TIMEOUT = 20  # 20 seconds per request
DOWNLOAD_MAXSIZE = 5242880  # 5MB max file size (RSS feeds are small)

# Retry settings
RETRY_ENABLED = True
RETRY_TIMES = 2
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Disable cookies
COOKIES_ENABLED = False

# Override the default request headers
DEFAULT_REQUEST_HEADERS = {
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'en',
  'User-Agent': 'TechPulse-Bot/1.0 (+https://techpulse.ai/bot)'
}

# Configure item pipelines
ITEM_PIPELINES = {}

# Enable logging
LOG_LEVEL = 'INFO'
LOG_STDOUT = True

# AutoThrottle settings for adaptive delays
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
