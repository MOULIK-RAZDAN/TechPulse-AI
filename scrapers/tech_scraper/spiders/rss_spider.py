import scrapy
import os
from kafka import KafkaProducer
import json
from datetime import datetime
from kafka.errors import NoBrokersAvailable, KafkaError
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
import uuid
import time

class RSSSpider(scrapy.Spider):
    name = 'rss_spider'
    
    RSS_FEEDS = [
        # High-reliability feeds (tested and fast)
        'https://techcrunch.com/feed/',
        'https://www.theverge.com/rss/index.xml',
        'https://arstechnica.com/feed/',
        
        # Developer & Engineer Focused
        'https://news.ycombinator.com/rss',           # Hacker News - very reliable
        'https://dev.to/rss',                         # Community dev posts
        
        # AI & Research Primary Sources (most important for our use case)
        'https://openai.com/news/rss.xml',
        'https://googleblog.blogspot.com/atom.xml',
        
        # Industry Specific (reliable sources)
        'https://www.technologyreview.com/feed/'      # MIT Tech Review
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        kafka_host = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
        
        # Retry connection to Kafka with exponential backoff
        max_retries = 10
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"🔄 Connecting to Kafka (attempt {attempt + 1}/{max_retries})...")
                self.producer = KafkaProducer(
                    bootstrap_servers=[kafka_host],
                    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                    request_timeout_ms=30000,  # 30 seconds
                    api_version_auto_timeout_ms=30000
                )
                self.logger.info("✓ Connected to Kafka successfully")
                break
                
            except (NoBrokersAvailable, KafkaError) as e:  # ← Fixed: Catch both error types
                if attempt < max_retries - 1:
                    self.logger.warning(f"⚠ Kafka connection failed: {e}")
                    self.logger.info(f"Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60)  # Cap at 60 seconds
                else:
                    self.logger.error("Failed to connect to Kafka after all retries")
                    raise
            except Exception as e:  # ← Fixed: Catch unexpected errors
                self.logger.error(f"Unexpected error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60)
                else:
                    raise
    
    def start_requests(self):
        for feed_url in self.RSS_FEEDS:
            yield scrapy.Request(url=feed_url, callback=self.parse_feed)
    
    def parse_feed(self, response):
        feed = feedparser.parse(response.text)
        source = response.url.split('/')[2].replace('www.', '').split('.')[0].title()
        article_count = 0  # Initialize counter
        
        for entry in feed.entries:
            # Create article with UUID5 (deterministic)
            article = {
                'article_id': str(uuid.uuid5(uuid.NAMESPACE_URL, entry.link)),
                'url': entry.link,
                'title': entry.title,
                'content': self.clean_html(entry.get('summary', '')),
                'source': source,
                'author': entry.get('author', 'Unknown'),
                'published_date': self.parse_date(entry.get('published')),
                'scraped_at': datetime.utcnow().isoformat(),
                'categories': self.get_categories(entry),
                'metadata': {'word_count': len(entry.get('summary', '').split())}
            }
            
            # Send to Kafka with error handling
            try:
                self.producer.send(
                    'raw_articles',
                    key=source.encode(),
                    value=article
                )
                self.logger.info(f"→ Scraped: {article['title']}")
                article_count += 1
                yield article
            except Exception as e:
                self.logger.error(f"❌ Failed to send article to Kafka: {e}")
        
        self.logger.info(f"✓ {source}: Scraped {article_count} articles")
    
    def clean_html(self, html):
        return BeautifulSoup(html, 'html.parser').get_text(separator=' ', strip=True)
    
    def parse_date(self, date_str):
        try:
            return date_parser.parse(date_str).isoformat()
        except:
            return datetime.utcnow().isoformat()
    
    def get_categories(self, entry):
        if 'tags' in entry:
            return [tag.term for tag in entry.tags]
        return ['General']
    
    def closed(self, reason):
        """Clean shutdown of Kafka producer"""
        self.logger.info(f"Spider closing: {reason}")
        try:
            self.logger.info("Flushing Kafka producer...")
            self.producer.flush(timeout=10)
            self.producer.close(timeout=10)
            self.logger.info("✓ Kafka producer closed cleanly")
        except Exception as e:
            self.logger.error(f"Error closing Kafka producer: {e}")