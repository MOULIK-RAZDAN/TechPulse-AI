#!/usr/bin/env python3
"""
Minimal scraper test to isolate the issue
"""

import requests
import feedparser
import json
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
import time
import os

def test_kafka_connection():
    """Test Kafka connectivity"""
    print("🔍 Testing Kafka connection...")
    kafka_host = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
    
    try:
        producer = KafkaProducer(
            bootstrap_servers=[kafka_host],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            request_timeout_ms=10000
        )
        print(f"✅ Connected to Kafka at {kafka_host}")
        producer.close()
        return True
    except Exception as e:
        print(f"❌ Kafka connection failed: {e}")
        return False

def test_single_feed():
    """Test scraping a single RSS feed"""
    print("\n🔍 Testing single RSS feed...")
    
    try:
        # Use the fastest feed from our test
        url = 'https://www.theverge.com/rss/index.xml'
        print(f"Fetching: {url}")
        
        response = requests.get(url, timeout=10)
        feed = feedparser.parse(response.text)
        
        print(f"✅ Got {len(feed.entries)} entries")
        
        # Test parsing first entry
        if feed.entries:
            entry = feed.entries[0]
            article = {
                'title': entry.title,
                'url': entry.link,
                'content': entry.get('summary', '')[:200] + '...'
            }
            print(f"✅ Sample article: {article['title']}")
        
        return True
        
    except Exception as e:
        print(f"❌ RSS test failed: {e}")
        return False

def main():
    print("🧪 Minimal Scraper Test")
    print("=" * 40)
    
    # Test Kafka
    kafka_ok = test_kafka_connection()
    
    # Test RSS
    rss_ok = test_single_feed()
    
    print("\n" + "=" * 40)
    print("📊 Results:")
    print(f"Kafka: {'✅' if kafka_ok else '❌'}")
    print(f"RSS:   {'✅' if rss_ok else '❌'}")
    
    if kafka_ok and rss_ok:
        print("\n✅ All tests passed - issue might be in Scrapy configuration")
    else:
        print("\n❌ Found issues - need to fix connectivity first")

if __name__ == '__main__':
    main()