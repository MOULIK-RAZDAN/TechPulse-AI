from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import redis
import json
from qdrant_client import QdrantClient
import anthropic
import psycopg2
import hashlib
import os
import ollama
import logging
import logging.handlers
from logger import setup_logging
from realtime_search import RealtimeSearchService

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
    port=6333
)

# --------------------------------------------------
# Request models
# --------------------------------------------------

class QueryRequest(BaseModel):
    query: str
    date_filter: Optional[str] = "7d"

# --------------------------------------------------
# RAG Pipeline (REFINED VERSION)
# --------------------------------------------------

class RAGPipeline:
    def __init__(self, ollama_host: str = OLLAMA_HOST):
        self.ollama_host = ollama_host
        self.ollama_client = ollama.Client(host=self.ollama_host)

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

            if isinstance(response, dict):
                if "embeddings" in response:
                    return response["embeddings"][0]
                if "embedding" in response:
                    return response["embedding"]

            raise ValueError(f"Unexpected embedding response: {response}")

        except Exception as e:
            logger.error(f"Ollama embedding error: {e}")
            return [0.0] * 768

    # -------- Vector search --------
    def search_articles(self, query: str, limit: int = 10):
        vector = self.generate_embedding(query)

        try:
            return qdrant_client.search(
                collection_name="tech_articles",
                query_vector=vector,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Qdrant search error: {e}")
            return []

    # -------- Context building --------
    def build_context(self, results):
        context_parts = []
        sources = []
        
        for p in results:
            content = p.payload.get("text", "") or p.payload.get("content", "")
            source = p.payload.get("source", "Unknown Source")
            
            context_parts.append(content)
            sources.append(source)
            
        return "\n---\n".join(context_parts), list(set(sources))

    # -------- Answer generation (IMPROVED PROMPT) --------
    def generate_answer(self, query: str, context: str, sources: list):
        numbered_sources = "\n".join([f"[{i+1}] {s}" for i, s in enumerate(sources)])
        prompt = (
        "You are TechPulse AI. Answer the question using the context provided.\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. Use [1], [2], etc. inside your answer to cite the sources.\n"
        "2. At the end of your answer, create a section 'Sources:' and list the full source info provided below.\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"AVAILABLE SOURCES:\n{numbered_sources}\n\n"
        f"QUESTION: {query}\n\n"
        "ANSWER:"
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
        
        # 2. Tech topics that move fast
        recency_keywords = ['latest', 'today', 'recent', 'new', 'breaking', 'apple ai', '2026', 'openai']
        has_recency = any(k in query_lower for k in recency_keywords)
        
        # 3. Low data in database
        insufficient_data = len(qdrant_results) < 2
        
        return force_search or has_recency or insufficient_data
    
    # -------- Main query with HYBRID SEARCH --------
    def query(self, query_text: str):
        cache_key = f"query:{hashlib.sha256(query_text.encode()).hexdigest()}"

        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        # Initial check in vector DB
        qdrant_results = self.search_articles(query_text)
        
        # Determine if we should pivot to the web
        if self.should_use_realtime_search(query_text, qdrant_results):
            logger.info("🌐 Triggering REALTIME SEARCH")
            # We use a broader search query if the user said "find it elsewhere"
            search_query = query_text
            if "elsewhere" in query_text.lower():
                search_query = "latest news about " + query_text.replace("elsewhere", "").replace("find it", "").strip()

            realtime_articles = self.realtime_search.hybrid_search(search_query, max_results=5)
            
            if realtime_articles:
                context = self.realtime_search.build_context_from_search(realtime_articles)
                sources = [f"{a.get('source')} - {a.get('link')}" for a in realtime_articles]
            else:
                context, sources = self.build_context(qdrant_results)
        else:
            context, sources = self.build_context(qdrant_results)
        
        answer = self.generate_answer(query_text, context, sources)

        result = {
            "answer": answer, 
            "sources": sources,
            "used_realtime": self.should_use_realtime_search(query_text, qdrant_results)
        }
        redis_client.setex(cache_key, 3600, json.dumps(result))
        
        return result

# --------------------------------------------------
# Instantiate pipeline
# --------------------------------------------------

rag = RAGPipeline()

# --------------------------------------------------
# API routes
# --------------------------------------------------

@app.post("/api/query")
async def query(request: QueryRequest):
    return rag.query(request.query)

@app.get("/api/articles")
async def get_articles(limit: int = 20):
    conn = psycopg2.connect(
        host="postgres",
        database="techpulse",
        user="admin",
        password="changeme"
    )

    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM articles ORDER BY published_date DESC LIMIT %s",
        (limit,)
    )

    articles = cursor.fetchall()
    conn.close()

    return {"articles": articles}

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