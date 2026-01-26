#!/usr/bin/env python3
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(host='qdrant', port=6333)

# Delete old collection if exists
try:
    client.delete_collection('tech_articles')
except:
    pass

# Create with 768 dimensions (nomic-embed-text)
client.create_collection(
    collection_name='tech_articles',
    vectors_config=VectorParams(
        size=768,  # Changed from 3072
        distance=Distance.COSINE
    )
)

print("Qdrant collection created with 768 dimensions")