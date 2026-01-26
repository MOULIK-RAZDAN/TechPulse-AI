import feedparser
from duckduckgo_search import DDGS
from newspaper import Article
import logging
from typing import List, Dict
from datetime import datetime
import urllib.parse

logger = logging.getLogger(__name__)

class RealtimeSearchService:
    """Fallback search when Qdrant has insufficient results"""
    
    def __init__(self):
        self.ddgs = DDGS()
    
    def search_google_news(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search Google News RSS for a topic"""
        try:
            safe_query = urllib.parse.quote_plus(query)
            url = f"https://news.google.com/rss/search?q={safe_query}&hl=en&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            
            articles = []
            for entry in feed.entries[:max_results]:
                articles.append({
                    'title': entry.title,
                    'link': entry.link,
                    'source': entry.get('source', {}).get('title', 'Google News'),
                    'published': entry.get('published', datetime.utcnow().isoformat()),
                    'summary': entry.get('summary', '')
                })
            
            logger.info(f"📰 Google News: Found {len(articles)} articles for '{query}'")
            return articles
            
        except Exception as e:
            logger.error(f"Google News error: {e}")
            return []
    
    def search_duckduckgo(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search DuckDuckGo for current info"""
        try:
            results = list(self.ddgs.text(query, max_results=max_results))
            
            articles = []
            for r in results:
                articles.append({
                    'title': r.get('title', ''),
                    'link': r.get('href', ''),
                    'source': 'DuckDuckGo',
                    'summary': r.get('body', '')
                })
            
            logger.info(f"🔍 DuckDuckGo: Found {len(articles)} results for '{query}'")
            return articles
            
        except Exception as e:
            logger.error(f"DuckDuckGo error: {e}")
            return []
    
    def extract_article_content(self, url: str) -> str:
        """Extract full text from article URL using Newspaper4k"""
        try:
            article = Article(url)
            article.download()
            article.parse()
            
            # Return full text (limit to 2000 chars to avoid context overload)
            return article.text[:2000]
            
        except Exception as e:
            logger.warning(f"Failed to extract {url}: {e}")
            return ""
    
    def hybrid_search(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        Combines Google News + DuckDuckGo + full article extraction
        Returns enriched articles with full content
        """
        # Step 1: Get initial results
        google_articles = self.search_google_news(query, max_results=3)
        ddg_articles = self.search_duckduckgo(query, max_results=2)
        
        all_articles = google_articles + ddg_articles
        
        # Step 2: Enrich with full content
        enriched = []
        for article in all_articles[:max_results]:
            full_text = self.extract_article_content(article['link'])
            
            if full_text:
                article['content'] = full_text
                enriched.append(article)
            else:
                # Fallback to summary if extraction fails
                article['content'] = article.get('summary', '')
                enriched.append(article)
        
        logger.info(f"✅ Hybrid search complete: {len(enriched)} articles with content")
        return enriched
    
    def build_context_from_search(self, articles: List[Dict]) -> str:
        """Convert search results into LLM context"""
        context_parts = []
        
        for i, article in enumerate(articles, 1):
            context_parts.append(
                f"[Article {i}]\n"
                f"Title: {article['title']}\n"
                f"Source: {article['source']}\n"
                f"Link: {article['link']}\n"
                f"Content: {article['content'][:1000]}...\n"
            )
        
        return "\n---\n".join(context_parts)