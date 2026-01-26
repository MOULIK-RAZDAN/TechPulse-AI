import sys
import time
sys.stdout = sys.stderr

def run_scrapers():
    """Run spider directly with Python"""
    print("🔄 Starting scraper run...", flush=True)
    
    try:
        from scrapy.crawler import CrawlerRunner
        from scrapy.utils.log import configure_logging
        from scrapy.utils.project import get_project_settings
        from twisted.internet import reactor, defer
        
        configure_logging()
        settings = get_project_settings()
        runner = CrawlerRunner(settings)
        
        @defer.inlineCallbacks
        def crawl():
            from tech_scraper.spiders.rss_spider import RSSSpider
            yield runner.crawl(RSSSpider)
            reactor.stop()
        
        crawl()
        reactor.run()
        print("✓ Scraper completed", flush=True)
        
    except Exception as e:
        print(f"✗ Error: {e}", flush=True)
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("📡 Scraper Started", flush=True)
    
    # Run once on startup
    run_scrapers()