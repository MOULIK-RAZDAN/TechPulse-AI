from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import redis
import json
from qdrant_client import QdrantClient, models
from flashrank import Ranker, RerankRequest
import anthropic
import psycopg2
import psycopg2.pool
import hashlib
import os
import ollama
import logging
import logging.handlers
from logger import setup_logging
from realtime_search import RealtimeSearchService
from fastapi.responses import StreamingResponse
import asyncio

# Setup structured logging
logger = setup_logging(
    service_name="backend",
    logstash_host=os.getenv('LOGSTASH_HOST'),
    logstash_port=int(os.getenv('LOGSTASH_PORT', 5000))
)

# --------------------------------------------------
# App setup
# --------------------------------------------------

app = FastAPI(title="TechPulse AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# Environment flags
# --------------------------------------------------

USE_MOCK_EMBEDDINGS = os.getenv("MOCK_EMBEDDINGS", "true").lower() == "true"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.containers.internal:11434")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# --------------------------------------------------
# Clients
# --------------------------------------------------

redis_client = redis.Redis(
    host="redis",
    port=6379,
    password="changeme",
    decode_responses=True
)

qdrant_client = QdrantClient(
    host="qdrant",
    port=6333,
    check_compatibility=False
)

# --------------------------------------------------
# Request models
# --------------------------------------------------

class QueryRequest(BaseModel):
    query: str
    date_filter: Optional[str] = "7d"

# --------------------------------------------------
# RAG Pipeline
# --------------------------------------------------
class RAGPipeline:
    def __init__(self, ollama_host: str = OLLAMA_HOST):
        self.ollama_host = ollama_host
        self.ollama_client = ollama.Client(host=self.ollama_host)
        self.async_ollama = ollama.AsyncClient(host=self.ollama_host)
        self.realtime_search = RealtimeSearchService()

        self.pg_pool = psycopg2.pool.SimpleConnectionPool(
        1, 10, # min/max connections
        host="postgres",
        database="techpulse",
        user="admin",
        password="changeme")

        # Initialize FlashRank (Stage 2) - The Librarian for picking best results
        try:
            # Use the correct model name with hyphens, not underscores
            self.ranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2", cache_dir="/opt/models")
            logger.info("FlashRank Reranker initialized successfully")
        except Exception as e:
            logger.warning(f"FlashRank initialization failed: {e}")
            logger.info("Falling back to simpler reranking based on scores")
            self.ranker = None

        self.anthropic_client = (
            anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            if ANTHROPIC_API_KEY
            else None
        )
        self.realtime_search = RealtimeSearchService()
        logger.info(f"RAG Pipeline initialized with Ollama at {self.ollama_host}")

    # -------- Embeddings --------
    def generate_embedding(self, query: str):
        if USE_MOCK_EMBEDDINGS:
            return [0.0] * 768

        try:
            response = self.ollama_client.embed(
                model="nomic-embed-text",
                input=query
            )

            # Handle different response formats
            if isinstance(response, dict):
                if "embeddings" in response:
                    return response["embeddings"][0]
                if "embedding" in response:
                    return response["embedding"]
            
            # Handle EmbedResponse object from ollama library
            if hasattr(response, 'embeddings') and response.embeddings:
                return response.embeddings[0]
            if hasattr(response, 'embedding'):
                return response.embedding

            logger.warning(f"Unexpected embedding response format, using mock embeddings")
            return [0.0] * 768

        except Exception as e:
            logger.error(f"Ollama embedding error: {e}")
            return [0.0] * 768

    # -------- Vector search --------
    def search_articles(self, query: str, limit: int = 10):
        vector = self.generate_embedding(query)

        try:
            # Check if collection exists first
            collections = qdrant_client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if "tech_articles" not in collection_names:
                logger.warning("Collection 'tech_articles' not found. Creating empty collection.")
                # Create collection if it doesn't exist
                qdrant_client.create_collection(
                    collection_name="tech_articles",
                    vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
                )
                return []  # Return empty results for now
            
            # This performs Hybrid Search using RRF (Reciprocal Rank Fusion)
            result = qdrant_client.query_points(
                collection_name="tech_articles",
                prefetch=[
                    # 1. The Semantic/Vector part
                    models.Prefetch(query=vector, limit=limit),
                    # 2. The Keyword part (Full Text Search)
                    models.Prefetch(query=query, using="text", limit=limit) 
                ],
                # RRF merges the two lists, putting the best matches from both at the top
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=limit
            )
            return result.points
        except Exception as e:
            logger.error(f"Hybrid search error: {e}")
            try:
                # Fallback to simple vector search if hybrid fails
                result = qdrant_client.search(
                    collection_name="tech_articles",
                    query_vector=vector,
                    limit=limit
                )
                return result
            except Exception as e2:
                logger.error(f"Fallback search also failed: {e2}")
                return []

    # -------- Context building --------
    def build_context(self, results):
        context_parts = []
        sources = []
        
        for p in results:
            # Handle both ScoredPoint and regular point objects
            if hasattr(p, 'payload'):
                # This is a ScoredPoint from search
                payload = p.payload
            elif hasattr(p, 'point') and hasattr(p.point, 'payload'):
                # This might be from query_points
                payload = p.point.payload
            else:
                # Fallback - treat as dict
                payload = p if isinstance(p, dict) else {}
            
            content = payload.get("text", "") or payload.get("content", "")
            source = payload.get("source", "Unknown Source")
            
            if content:  # Only add if we have content
                context_parts.append(content)
                sources.append(source)
            
        return "\n---\n".join(context_parts), list(set(sources))
    
    def get_hybrid_context(self, query: str, limit: int = 15):
        """
        Stage 1: Retrieve candidates using Hybrid Search (Semantic + Keywords)
        """
        query_vector = self.generate_embedding(query)
        
        # query_points is the new standard for Hybrid Search in 2026
        search_result = self.qdrant.query_points(
            collection_name="tech_articles",
            prefetch=[
                # Search 1: Semantic (Dense Vector)
                models.Prefetch(query=query_vector, limit=limit),
                # Search 2: Keywords (Full-Text Search on the 'text' field)
                models.Prefetch(query=query, using="text", limit=limit)
            ],
            # Combine them using RRF (Reciprocal Rank Fusion)
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit
        )
        return search_result.points
    
    def rerank_results(self, query: str, points: list, top_n: int = 5):
        """Stage 2: Use FlashRank to pick the absolute best context chunks"""
        if not points:
            return []
            
        if self.ranker is None:
            # If ranker is disabled, return top results based on score
            logger.info("🔄 Reranker disabled, using original order")
            return points[:top_n]

        try:
            # Convert Qdrant points to FlashRank format
            passages = []
            for i, p in enumerate(points):
                try:
                    if hasattr(p, 'payload'):
                        payload = p.payload
                        point_id = getattr(p, 'id', i)
                    elif hasattr(p, 'point') and hasattr(p.point, 'payload'):
                        payload = p.point.payload
                        point_id = getattr(p.point, 'id', i)
                    else:
                        payload = p if isinstance(p, dict) else {}
                        point_id = i
                    
                    text = payload.get("text", "") or payload.get("content", "")
                    if text:  # Only add if we have text
                        passages.append({
                            "id": point_id,
                            "text": text,
                            "meta": payload.get("metadata", {})
                        })
                except Exception as e:
                    logger.warning(f"Error processing point {i}: {e}")
                    continue

            if not passages:
                logger.warning("No valid passages for reranking")
                return points[:top_n]

            # Perform the rerank
            rerank_request = RerankRequest(query=query, passages=passages)
            results = self.ranker.rerank(rerank_request)
            
            # FlashRank returns a list of dicts; we return the top_n
            return results[:top_n]
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            # Fallback to original order
            return points[:top_n]

    # -------- Answer generation (IMPROVED PROMPT) --------
    def generate_answer(self, query: str, context: str, sources: list):
        numbered_sources = "\n".join([f"[{i+1}] {s}" for i, s in enumerate(sources)])
        prompt = (
        f"""
            You are TechPulse AI, an expert analyst in the 2026 technology and AI industry.

            STRICT RULES (MUST FOLLOW):

            1. Use ONLY the information provided in the CONTEXT.
            2. Do NOT use prior knowledge.
            3. Do NOT speculate or infer beyond the context.
            4. Every factual claim MUST include a citation using [number].
            5. Use ONLY the citation numbers from AVAILABLE SOURCES.
            6. If the context does not contain enough information, respond exactly with:
            "The provided context does not contain sufficient information to answer this question."
            7. Do NOT mention the word "context" in your answer.
            8. Do NOT mention that you are an AI model.

            RESPONSE STRUCTURE:

            - Brief Summary (2-4 sentences)
            - Key Details (bullet points with citations)
            - Final Insight (1 concise analytical sentence)
            - Sources section (formatted exactly as shown below)

            CITATION RULES:

            - Place citations immediately after the supporting sentence.
            - Example: OpenAI released a new model in 2026 [1].
            - Do not group citations at the end of paragraphs.

            -------------------------
            CONTEXT:
            {context}
            -------------------------

            AVAILABLE SOURCES:
            {numbered_sources}

            -------------------------
            QUESTION:
            {query}
            -------------------------

            ANSWER:
            """
    )

        # 1. Attempt Anthropic
        if self.anthropic_client:
            try:
                response = self.anthropic_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1500,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            except Exception as e:
                logger.error(f"Anthropic unavailable: {e}")

        # 2. Fallback to Local Ollama
        logger.info(f"Attempting local fallback to Ollama...")
        return self._generate_answer_ollama(prompt)

    def _generate_answer_ollama(self, prompt: str) -> str:
        try:
            response = self.ollama_client.generate(
                model="llama3.2",
                prompt=prompt,
                stream=False
            )
            return response['response']
        except Exception as e:
            logger.error(f"Ollama connection failed: {e}")
            raise HTTPException(
                status_code=503,
                detail="AI generation failed. Ensure Ollama is running."
            )

    # -------- Logic to decide if we need Web Search --------
    def should_use_realtime_search(self, query: str, qdrant_results: list) -> bool:
        query_lower = query.lower()
        
        # 1. Force search if user asks explicitly or context looks like a command
        force_keywords = ['elsewhere', 'search the web', 'google it', 'look online', 'find info']
        force_search = any(k in query_lower for k in force_keywords)
        
        # 2. Tech topics that move fast or are likely to be missing
        recency_keywords = ['latest', 'today', 'recent', 'new', 'breaking', 'apple ai', '2026', 'openai', 'anthropic', 'claude']
        has_recency = any(k in query_lower for k in recency_keywords)
        
        # 3. Low data in database (most important fix)
        insufficient_data = len(qdrant_results) < 2
        
        # 4. Low quality results (check if results have actual content)
        if qdrant_results:
            has_meaningful_content = False
            for result in qdrant_results:
                try:
                    if hasattr(result, 'payload'):
                        payload = result.payload
                    elif hasattr(result, 'point') and hasattr(result.point, 'payload'):
                        payload = result.point.payload
                    else:
                        payload = result if isinstance(result, dict) else {}
                    
                    content = payload.get("text", "") or payload.get("content", "")
                    if content and len(content.strip()) > 50:  # Meaningful content threshold
                        has_meaningful_content = True
                        break
                except:
                    continue
            
            if not has_meaningful_content:
                insufficient_data = True
        
        # 5. Handle typos and fuzzy matching - if query looks like it might be a typo
        # Common AI company names and tech terms
        tech_terms = ['anthropic', 'openai', 'claude', 'chatgpt', 'llama', 'mistral', 'cohere']
        might_be_typo = False
        
        # Simple fuzzy matching for common terms
        for term in tech_terms:
            if self._fuzzy_match(query_lower, term):
                might_be_typo = True
                break
        
        decision = force_search or has_recency or insufficient_data or might_be_typo
        
        if decision:
            reason = []
            if force_search: reason.append("explicit request")
            if has_recency: reason.append("recency keywords")
            if insufficient_data: reason.append("insufficient local data")
            if might_be_typo: reason.append("possible typo/fuzzy match")
            
            logger.info(f"🌐 Using realtime search for '{query}' - Reasons: {', '.join(reason)}")
        
        return decision
    
    def _fuzzy_match(self, query: str, target: str, threshold: float = 0.6) -> bool:
        """Improved fuzzy matching for typos using Levenshtein distance"""
        if not query or not target:
            return False
            
        # Remove spaces and convert to lowercase
        query = query.replace(" ", "").lower()
        target = target.lower()
        
        # If query is contained in target or vice versa
        if query in target or target in query:
            return True
        
        # Use Levenshtein distance for better fuzzy matching
        try:
            from Levenshtein import ratio
            similarity = ratio(query, target)
            return similarity >= threshold
        except ImportError:
            # Fallback to simple character-based similarity
            if len(query) == 0:
                return False
                
            # Count matching characters in order
            matches = 0
            target_idx = 0
            
            for char in query:
                while target_idx < len(target) and target[target_idx] != char:
                    target_idx += 1
                if target_idx < len(target):
                    matches += 1
                    target_idx += 1
            
            similarity = matches / len(query)
            return similarity >= threshold
    
    # -------- Main query with HYBRID SEARCH --------
    async def query(self, query_text: str):
        # 1. Check Redis Cache
        cache_key = f"query:{hashlib.sha256(query_text.encode()).hexdigest()}"
        cached = redis_client.get(cache_key)
        if cached:
            logger.info("Serving from Redis cache")
            return json.loads(cached)

        # 2. STAGE 1: Hybrid Search (Semantic + Keyword)
        # We retrieve more results (limit=15) than we need so the reranker has room to work
        raw_candidates = self.search_articles(query_text, limit=15)
        
        # Determine if we should pivot to the web
        should_use_web = self.should_use_realtime_search(query_text, raw_candidates)
        
        if should_use_web:
            logger.info("Triggering REALTIME SEARCH")
            search_query = query_text
            if "elsewhere" in query_text.lower():
                search_query = "latest news about " + query_text.replace("elsewhere", "").replace("find it", "").strip()

            realtime_articles = await self.realtime_search.hybrid_search(search_query, max_results=5)
            
            if realtime_articles:
                context = await self.realtime_search.build_context_from_search(realtime_articles)
                sources = [f"{a.get('source', 'Unknown')} - {a.get('link', '')}" for a in realtime_articles]
                used_realtime = True
                reranked = False
            else:
                # Fallback to local if web search fails
                if raw_candidates:
                    context, sources = self.build_context(raw_candidates)
                    used_realtime = False
                    reranked = False
                else:
                    # No data anywhere
                    context = "I don't have information about this topic in my database, and I wasn't able to find current information online."
                    sources = []
                    used_realtime = True
                    reranked = False
        else:
            # 3. STAGE 2: Reranking (FlashRank) - only if we have local results
            if raw_candidates:
                if self.ranker is not None:
                    # We re-evaluate the 15 raw candidates to pick the absolute top 5
                    reranked_results = self.rerank_results(query_text, raw_candidates, top_n=5)
                    
                    # Build context from the high-precision reranked results
                    if reranked_results and isinstance(reranked_results[0], dict):
                        # FlashRank results format
                        context_parts = [r["text"] for r in reranked_results if r.get("text")]
                        sources = [r.get("meta", {}).get("source", "Unknown Source") for r in reranked_results]
                        context = "\n---\n".join(context_parts) if context_parts else ""
                        sources = list(set(sources))
                    else:
                        # Fallback to original format
                        context, sources = self.build_context(reranked_results)
                    
                    reranked = True
                else:
                    # No reranking, use original results
                    context, sources = self.build_context(raw_candidates)
                    reranked = False
                
                used_realtime = False
            else:
                # No local results, should have triggered web search but didn't
                context = "I don't have information about this topic in my database."
                sources = []
                used_realtime = False
                reranked = False

        # 4. Generate Answer
        if context and context.strip():
            answer = self.generate_answer(query_text, context, sources)
        else:
            answer = "I apologize, but I don't have enough information to answer your question about this topic. You might want to try rephrasing your question or asking about a different aspect of the topic."

        # 5. Cache and Return
        result = {
            "answer": answer, 
            "sources": sources,
            "used_realtime": used_realtime,
            "reranked": reranked,
            "local_results_count": len(raw_candidates),
            "query_processed": query_text
        }
        
        # Only cache successful results
        if context and context.strip():
            redis_client.setex(cache_key, 3600, json.dumps(result))
        
        return result
    async def search_articles_async(self, query: str, limit: int = 10):
        """Bridge sync Qdrant calls to the async stream loop"""
        return await asyncio.to_thread(self.search_articles, query, limit)    

    async def stream_query(self, query_text: str):
        # Parallel Fetch: Start local search, web search, and arXiv search at once
        tasks = [
            self.search_articles_async(query_text),  # Local Qdrant
            self.arxiv_service.fetch_papers(query_text), # New service
            self.realtime_search.search(query_text)  # Web Search
        ]
        
        # Wait for all to finish concurrently (slashes wait time by up to 60%)
        local_results, arxiv_results, web_results = await asyncio.gather(*tasks)
        context = self.build_context(local_results, arxiv_results, web_results)

        # Stream from Ollama using the AsyncClient
        async for part in await self.ollama_client.chat(
            model='llama3.2',
            messages=[{'role': 'user', 'content': f"Context: {context}\n\nQuery: {query_text}"}],
            stream=True,):
            # Format as Server-Sent Events (SSE)
            yield f"data: {json.dumps({'token': part['message']['content']})}\n\n"    

    async def get_parallel_context(self, query: str):
        """
        PERFORMANCE OPTIMIZATION: 
        Fires all retrieval tasks in parallel using asyncio.gather.
        """
        tasks = [
            # Wrap sync Qdrant call in a thread to prevent blocking
            asyncio.to_thread(self.search_articles, query, limit=8),
            # New async search services
            self.realtime_search.search_google_news(query, max_results=2),
            self.realtime_search.search_duckduckgo(query, max_results=2),
            self.realtime_search.fetch_arxiv_papers(query, limit=3)
        ]
        
        # Parallel execution: Total wait time = slowest single task
        local_pts, g_news, ddg, arxiv = await asyncio.gather(*tasks)
        
        # Combine local context
        local_text, local_sources = self.build_context(local_pts)
        
        # Format Web/Arxiv contexts
        web_results = g_news + ddg
        web_text = "\n".join([f"Source: {a['source']} | Content: {a.get('content', a['summary'])}" for a in web_results])
        arxiv_text = "\n".join([f"Paper: {p['title']} | Summary: {p['summary']}" for p in arxiv])
        
        full_context = f"{local_text}\n\n{web_text}\n\n{arxiv_text}"
        
        # Collect all source URLs for the frontend UI cards
        web_urls = [{"title": a['title'], "url": a['link'], "source": a['source']} for a in web_results]
        arxiv_urls = [{"title": p['title'], "url": p['link'], "source": "arXiv"} for p in arxiv]
        
        return full_context, web_urls + arxiv_urls
    
# --------------------------------------------------
# Instantiate pipeline
# --------------------------------------------------

rag = RAGPipeline()

def detect_intent(query: str) -> str:
    """
    Classify user intent before running RAG.
    Returns: 'smalltalk' | 'factual'
    """
    if not query:
        return "smalltalk"

    q = query.lower().strip()

    # Simple greeting / conversational detection
    greetings = {
        "hi", "hello", "hey",
        "hi techpulse", "hello techpulse",
        "good morning", "good evening", "good afternoon"
    }

    # Very short conversational inputs
    if q in greetings:
        return "smalltalk"

    if len(q.split()) <= 2 and not any(char.isdigit() for char in q):
        # Likely conversational and not factual
        return "smalltalk"

    return "factual"

# --------------------------------------------------
# API routes
# --------------------------------------------------

@app.post("/api/query")
async def query(request: QueryRequest):
    intent = detect_intent(request.query)

    if intent == "smalltalk":
        return {
            "answer": "Hi! I'm TechPulse AI 👋 Ask me anything about AI, technology, startups, or software engineering.",
            "sources": [],
            "used_realtime": False,
            "reranked": False,
            "local_results_count": 0,
            "query_processed": request.query
        }
    return await rag.query(request.query)

@app.get("/api/articles")
async def get_articles(limit: int = 20):
    conn = rag.pg_pool.getconn()
    try:

        cursor = conn.cursor()
        cursor.execute("SELECT * FROM articles ORDER BY published_date DESC LIMIT %s",(limit,))
        articles = cursor.fetchall()
        return {"articles": articles}
    finally:
        rag.pg_pool.putconn(conn)    

@app.get("/health")
async def health():
    ollama_status = "disconnected"
    models = []

    try:
        result = rag.ollama_client.list()
        ollama_status = "connected"
        models = [m["name"] for m in result.get("models", [])]
    except Exception:
        pass

    return {
        "status": "healthy",
        "mock_embeddings": USE_MOCK_EMBEDDINGS,
        "ollama_status": ollama_status,
        "ollama_models": models,
        "anthropic_enabled": bool(ANTHROPIC_API_KEY),
        "realtime_search_enabled": True
    }
@app.post("/api/query/stream")
async def query_stream(request: QueryRequest):

    intent = detect_intent(request.query)

    if intent == "smalltalk":
        async def generate_smalltalk():
            yield f"data: {json.dumps({'token': 'Hi! I’m TechPulse AI 👋 Ask me anything about technology or AI.'})}\n\n"
        return StreamingResponse(generate_smalltalk(), media_type="text/event-stream")

    async def generate():
        context, sources = await rag.get_parallel_context(request.query)
        yield f"data: {json.dumps({'sources': sources})}\n\n"

        chunks = await rag.async_ollama.chat(
            model='llama3.2',
            messages=[{'role': 'user', 'content': f"Context: {context}\n\nQuery: {request.query}"}],
            stream=True
        )

        async for chunk in chunks:
            if 'message' in chunk and 'content' in chunk['message']:
                content = chunk['message']['content']
                yield f"data: {json.dumps({'token': content})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")