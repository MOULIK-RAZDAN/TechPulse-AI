from kafka import KafkaConsumer
import json
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import psycopg2
import uuid
import logging
import os
from logger import setup_logging

logger = setup_logging(
    service_name="indexer",
    logstash_host=os.getenv('LOGSTASH_HOST'),
    logstash_port=int(os.getenv('LOGSTASH_PORT', 5000))
)
class IndexerService:
    def __init__(self):
        self.consumer = KafkaConsumer(
            'indexer_queue',
            bootstrap_servers=['kafka:9092'],
            group_id='indexer-group-v6',
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        self.qdrant = QdrantClient(host='qdrant', port=6333)
        self.ensure_collection()
        
        self.pg_conn = psycopg2.connect(
            host='postgres',
            database='techpulse',
            user='admin',
            password='changeme'
        )
        
        logger.info("✓ Indexer service initialized")
    
    def ensure_collection(self):
        """Create Qdrant collection if it doesn't exist"""
        collections = [c.name for c in self.qdrant.get_collections().collections]
        
        if 'tech_articles' not in collections:
            self.qdrant.create_collection(
                collection_name='tech_articles',
                vectors_config=VectorParams(
                    size=768,  # nomic-embed-text dimension
                    distance=Distance.COSINE
                )
            )
            logger.info("✓ Created Qdrant collection with 768 dimensions")
        else:
            logger.info("✓ Qdrant collection already exists")
    
    # Replace your entire index_article method with this:
    def index_article(self, data):
        # data is now {'article': {...}, 'chunks': [{...}]}
        article = data.get('article')
        chunks = data.get('chunks', [])
        
        if not article:
            return

        title = article.get('title', 'Unknown Title')
        logger.info(f"→ Indexing into DB & Vector Store: {title}")

        # 1. PostgreSQL
        try:
            with self.pg_conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO articles (id, url, title, source, author, published_date, content, word_count, categories)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO NOTHING
                """, (
                    article.get('article_id'), article.get('url'), title,
                    article.get('source'), article.get('author'), article.get('published_date'),
                    article.get('content'), article.get('metadata', {}).get('word_count', 0),
                    article.get('categories', [])
                ))
                self.pg_conn.commit()
                logger.info(f"  [1/2] Postgres: OK")
        except Exception as e:
            logger.error(f"  ❌ Postgres error: {e}")

        # 2. Qdrant
        try:
            points = []
            for chunk in chunks:
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector=chunk['embedding'],
                    payload={
                        'text': chunk['text'],
                        'article_id': article.get('article_id'),
                        'title': title,
                        'url': article.get('url')
                    }
                ))
            
            if points:
                self.qdrant.upsert(collection_name='tech_articles', points=points)
                logger.info(f"  [2/2] Qdrant: Indexed {len(points)} chunks")
        except Exception as e:
            logger.error(f"  ❌ Qdrant error: {e}")
    
    def run(self):
        logger.info("Indexer waiting for messages...")
        
        for message in self.consumer:
            try:
                # This inner try-except protects the loop
                data = message.value
                
                # Basic validation
                if not data:
                    continue
                    
                # Use a helper to normalize the data structure
                article_data = data.get('article', data) 
                title = article_data.get('title', 'Unknown Title')
                
                logger.info(f"→ Indexing: {title}")
                self.index_article(data)
                logger.info(f"✓ Successfully indexed: {title}")

            except KeyError as e:
                logger.error(f"⚠️ Data format error (missing key {e}). Skipping message.")
                continue # Move to the next message
                
            except Exception as e:
                # This catches DB timeouts, Embedding errors, etc.
                logger.error(f"❌ Error processing message: {str(e)}")
                # Optional: import traceback; traceback.print_exc()
                continue

if __name__ == '__main__':
    service = IndexerService()
    service.run()