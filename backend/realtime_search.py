import feedparser
from newspaper import Article
import logging
from typing import List, Dict
from datetime import datetime
import urllib.parse
import arxiv
import asyncio
from asyncddgs import aDDGS as AsyncDDGS

logger = logging.getLogger(__name__)

class RealtimeSearchService:
    """Fallback search when Qdrant has insufficient results"""
    
    def __init__(self):
        """Initialize the realtime search service"""
        self.logger = logging.getLogger(__name__)
    
    async def search_google_news(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search Google News RSS for a topic"""
        try:
            safe_query = urllib.parse.quote_plus(query)
            url = f"https://news.google.com/rss/search?q={safe_query}&hl=en&gl=US&ceid=US:en"
            loop = asyncio.get_event_loop()
            feed = await loop.run_in_executor(None, feedparser.parse, url)
            
            articles = []
            for entry in feed.entries[:max_results]:
                articles.append({
                    'title': entry.title,
                    'link': entry.link,
                    'source': entry.get('source', {}).get('title', 'Google News'),
                    'published': entry.get('published', datetime.utcnow().isoformat()),
                    'summary': entry.get('summary', '')
                })
            
            logger.info(f"Google News: Found {len(articles)} articles for '{query}'")
            return articles
            
        except Exception as e:
            logger.error(f"Google News error: {e}")
            return []
    
    async def search_duckduckgo(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search DuckDuckGo using AsyncDDGS context manager"""
        try:
            async with AsyncDDGS() as ddgs:
                # Note: In recent versions, text() returns a list directly when awaited
                results = await ddgs.text(query, max_results=max_results)
                
            return [{
                'title': r.get('title', ''),
                'link': r.get('href', ''),
                'source': 'DuckDuckGo',
                'summary': r.get('body', '')
            } for r in results]
        except Exception as e:
            logger.error(f"DuckDuckGo error: {e}")
            return []
    
    async def fetch_arxiv_papers(self, query: str, limit: int = 3):
        """Integrated Arxiv logic into the main service"""
        try:
            # arxiv library is sync, so we run in executor
            def _search():
                client = arxiv.Client()
                search = arxiv.Search(query=query, max_results=limit, sort_by=arxiv.SortCriterion.Relevance)
                return list(client.results(search))

            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, _search)

            return [{
                "title": r.title,
                "summary": r.summary,
                "link": r.pdf_url,
                "source": "arXiv Research"
            } for r in results]
        except Exception as e:
            logger.error(f"Arxiv error: {e}")
            return []

    async def extract_content(self, url: str) -> str:
        """Async-wrapped article extraction"""
        try:
            def _extract():
                article = Article(url)
                article.download()
                article.parse()
                return article.text[:2000]

            loop = asyncio.get_event_loop()
            return await asyncio.wait_for(loop.run_in_executor(None, _extract), timeout=10.0)
        except Exception:
            return ""

    async def hybrid_search(self, query: str, max_results: int = 5) -> List[Dict]:
        """
        THE KEY CHANGE: Executes all searches in PARALLEL using asyncio.gather.
        """
        # Step 1: Fire all searches at once
        tasks = [
            self.search_google_news(query, max_results=3),
            self.search_duckduckgo(query, max_results=2),
            self.fetch_arxiv_papers(query, limit=2)
        ]
        
        # results will be a list of lists: [[google], [ddg], [arxiv]]
        results = await asyncio.gather(*tasks)
        all_articles = [item for sublist in results for item in sublist]
        
        # Step 2: Parallelize content extraction for the top hits
        extraction_tasks = [self.extract_content(a['link']) for a in all_articles[:max_results]]
        contents = await asyncio.gather(*extraction_tasks)
        
        enriched = []
        for i, article in enumerate(all_articles[:max_results]):
            article['content'] = contents[i] if contents[i] else article.get('summary', '')
            enriched.append(article)
            
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