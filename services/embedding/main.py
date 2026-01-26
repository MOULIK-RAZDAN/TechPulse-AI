from kafka import KafkaConsumer, KafkaProducer
import json
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
import ollama
from ollama._types import EmbedResponse
import logging
import os
from logger import setup_logging

logger = setup_logging(
    service_name="embedding",
    logstash_host=os.getenv('LOGSTASH_HOST'),
    logstash_port=int(os.getenv('LOGSTASH_PORT', 5000))
)

class EmbeddingService:
    def __init__(self):
        self.consumer = KafkaConsumer(
            'raw_articles',
            bootstrap_servers=['kafka:9092'],
            group_id='embedding-group-v4',
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        self.producer = KafkaProducer(
            bootstrap_servers=['kafka:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        self.ollama_host = os.getenv('OLLAMA_HOST', 'http://host.containers.internal:11434')
        self.ollama_client = ollama.Client(host=self.ollama_host)
        
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=100
        )
        
        logger.info(f"✓ Embedding service initialized with Ollama at {self.ollama_host}")
    
    def generate_embeddings(self, texts):
        """Generate embeddings using Ollama (nomic-embed-text → 768 dims)"""
        embeddings = []
        
        for text in texts:
            try:
                resp = self.ollama_client.embed(
                    model="nomic-embed-text",
                    input=text
                )
                
                # The 'resp' is an EmbedResponse object. 
                # We access the embeddings list from its attributes.
                if hasattr(resp, 'embeddings') and resp.embeddings:
                    # resp.embeddings is a list of lists (one per input)
                    embedding = resp.embeddings[0]
                elif isinstance(resp, dict) and "embeddings" in resp:
                    embedding = resp["embeddings"][0]
                else:
                    raise RuntimeError(f"Could not parse Ollama response: {type(resp)}")
                
                # Validate dimension
                if not embedding or len(embedding) != 768:
                    raise RuntimeError(
                        f"Invalid embedding size: expected 768, got {len(embedding) if embedding else 0}"
                    )
                
                embeddings.append(embedding)
                
            except Exception as e:
                logger.error(f"❌ Error generating embedding: {e}")
                raise
        
        return embeddings

    
    def process_article(self, article):
        """Split article into chunks and generate embeddings"""
        # Split content into chunks
        chunks_text = self.splitter.split_text(article['content'])
        
        if not chunks_text:
            logger.info(f"Warning: No chunks for article {article['title']}")
            return None
        
        # Generate embeddings for all chunks
        embeddings = self.generate_embeddings(chunks_text)
        
        # Build embedded chunks
        embedded_chunks = []
        for i, (chunk_text, embedding) in enumerate(zip(chunks_text, embeddings)):
            embedded_chunks.append({
                'chunk_id': i,
                'text': chunk_text,
                'embedding': embedding
            })
        
        return {
            'article': article,
            'chunks': embedded_chunks
        }
    
    def run(self):
        logger.info("Embedding service started, waiting for articles on 'embedded_articles' topic...")
        
        for message in self.consumer:
            article = message.value
            
            try:
                logger.info(f"→ Processing: {article['title']}")
                result = self.process_article(article)
                
                if result:
                    # Send to indexer_queue
                    self.producer.send('indexer_queue', value=result)
                    logger.info(f"✓ Embedded and sent to indexer: {article['title']} ({len(result['chunks'])} chunks)")
                
            except Exception as e:
                logger.error(f"ERROR processing {article.get('title', 'unknown')}: {e}")
                import traceback
                traceback.print_exc()

if __name__ == '__main__':
    service = EmbeddingService()
    service.run()