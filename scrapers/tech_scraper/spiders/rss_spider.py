import scrapy
import os
from kafka import KafkaProducer
import json
from datetime import datetime
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
import uuid

class RSSSpider(scrapy.Spider):
    name = 'rss_spider'
    
    RSS_FEEDS = [
        'https://techcrunch.com/feed/',
        'https://www.theverge.com/rss/index.xml',
        'https://arstechnica.com/feed/',
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        kafka_host = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
        self.producer = KafkaProducer(
            bootstrap_servers=[kafka_host],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print("✓ Scraper initialized")
    
    def start_requests(self):
        for feed_url in self.RSS_FEEDS:
            yield scrapy.Request(url=feed_url, callback=self.parse_feed)
    
    def parse_feed(self, response):
        feed = feedparser.parse(response.text)
        source = response.url.split('/')[2].replace('www.', '').split('.')[0].title()
        
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
            
            # Send ONLY the article to embedded_articles topic
            # No chunks, no embeddings - embedding service handles that
            self.producer.send(
                'raw_articles',
                key=source.encode(),
                value=article
            )
            
            print(f"→ Scraped: {article['title']}")
            yield article
    
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
        self.logger.info("Closing Kafka producer...")
        self.producer.flush()
        self.producer.close()