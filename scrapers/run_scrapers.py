#!/usr/bin/env python3
"""
Scheduled Scrapy RSS scraper
Runs immediately, then every 30 minutes
"""

import sys
import logging
import time
import schedule
import subprocess
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def run_scraper_once():
    """
    Run spider using subprocess to avoid reactor issues
    Each run gets a fresh Python process
    """
    logger.info("🕷️ Starting RSS scraper...")
    
    try:
        # Run spider in a separate process
        result = subprocess.run(
            ['scrapy', 'crawl', 'rss_spider'],
            cwd='/app',
            capture_output=True,
            text=True,
            timeout=180  # 3 minute timeout for sequential processing
        )
        
        # Log output
        if result.stdout:
            for line in result.stdout.split('\n'):
                if line.strip():
                    logger.info(line)
        
        if result.returncode == 0:
            logger.info("✅ Scraping complete")
        else:
            logger.error(f"❌ Scraper failed with code {result.returncode}")
            if result.stderr:
                logger.error(result.stderr)
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        logger.error("❌ Scraper timeout (3 minutes)")
        return False
    except Exception as e:
        logger.error(f"❌ Error running scraper: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main scheduler loop"""
    logger.info("TechPulse Scraper Service Started")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Kafka servers: {os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')}")
    
    # Run immediately on startup
    logger.info("Waiting 30 seconds for Kafka to initialize...")
    time.sleep(30)
    logger.info("Running Initial Scrape")
    success = run_scraper_once()
    
    if success:
        logger.info("✓ Initial scrape successful")
    else:
        logger.warning("⚠ Initial scrape had issues, will retry on schedule")
    
    # Schedule to run every 30 minutes
    schedule.every(30).minutes.do(run_scraper_once)
    logger.info("📅 Scheduler active - next run in 30 minutes")
    
    # Keep running
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("👋 Shutting down scraper service")
            break
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            time.sleep(60)

if __name__ == '__main__':
    main()