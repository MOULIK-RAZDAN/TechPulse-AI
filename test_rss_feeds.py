#!/usr/bin/env python3
"""
Test individual RSS feeds to identify problematic ones
"""

import requests
import feedparser
import time
from datetime import datetime

RSS_FEEDS = [
    'https://techcrunch.com/feed/',
    'https://www.theverge.com/rss/index.xml',
    'https://arstechnica.com/feed/',
    'https://news.ycombinator.com/rss',
    'https://dev.to/rss',
    'https://openai.com/news/rss.xml',
    'https://googleblog.blogspot.com/atom.xml',
    'https://www.technologyreview.com/feed/'
]

def test_feed(url, timeout=10):
    """Test a single RSS feed"""
    print(f"\n🔍 Testing: {url}")
    start_time = time.time()
    
    try:
        # Test HTTP request first
        response = requests.get(url, timeout=timeout, headers={
            'User-Agent': 'TechPulse-Bot/1.0 (+https://techpulse.ai/bot)'
        })
        
        if response.status_code != 200:
            print(f"❌ HTTP {response.status_code}")
            return False
            
        # Test feedparser
        feed = feedparser.parse(response.text)
        
        if feed.bozo:
            print(f"⚠️  Feed has issues: {feed.bozo_exception}")
        
        entry_count = len(feed.entries)
        elapsed = time.time() - start_time
        
        print(f"✅ Success: {entry_count} entries in {elapsed:.2f}s")
        return True
        
    except requests.exceptions.Timeout:
        elapsed = time.time() - start_time
        print(f"⏰ Timeout after {elapsed:.2f}s")
        return False
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ Error after {elapsed:.2f}s: {e}")
        return False

def main():
    print("🧪 Testing RSS Feeds for TechPulse AI")
    print("=" * 50)
    
    working_feeds = []
    problematic_feeds = []
    
    for feed_url in RSS_FEEDS:
        if test_feed(feed_url, timeout=15):
            working_feeds.append(feed_url)
        else:
            problematic_feeds.append(feed_url)
        
        time.sleep(1)  # Be respectful
    
    print("\n" + "=" * 50)
    print("📊 RESULTS")
    print("=" * 50)
    
    print(f"\n✅ Working feeds ({len(working_feeds)}):")
    for feed in working_feeds:
        print(f"  - {feed}")
    
    print(f"\n❌ Problematic feeds ({len(problematic_feeds)}):")
    for feed in problematic_feeds:
        print(f"  - {feed}")
    
    print(f"\n📈 Success rate: {len(working_feeds)}/{len(RSS_FEEDS)} ({len(working_feeds)/len(RSS_FEEDS)*100:.1f}%)")

if __name__ == '__main__':
    main()