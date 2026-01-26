# TechPulse AI - Setup Instructions

## Quick Start

1. **Install Podman**
   ```bash
   sudo apt-get install podman podman-compose
   ```

2. **Configure Environment**
   ```bash
   cd techpulse-ai
   cp .env.example .env
   nano .env  # Add API keys
   ```

3. **Run Setup**
   ```bash
   chmod +x scripts/setup-podman.sh
   ./scripts/setup-podman.sh
   ```

4. **Access Application**
   - Frontend: http://localhost:3000
   - Backend: http://localhost:8000/docs

## Architecture

- Scrapers fetch from 50+ tech blogs
- Kafka for message brokering
- Deduplication with MinHash
- OpenAI for embeddings
- Qdrant for vector storage
- PostgreSQL for metadata
- Claude Sonnet 4 for answers
- Next.js frontend

## Management

```bash
# View logs
podman-compose logs -f [service]

# Stop all
podman-compose down

# Restart
podman-compose restart [service]
```

## Troubleshooting

- **Services won't start**: Check `podman-compose logs`
- **Permission errors**: Run `sudo chcon -Rt svirt_sandbox_file_t ./volumes`
- **No articles**: Wait 30+ minutes for initial scraping

## To Restart a Service

# Restarting Scrapers service
podman stop techpulse-scraper
podman rm techpulse-scraper
podman build --no-cache -t techpulse-scraper -f Containerfile.scraper scrapers
podman-compose up -d scraper
podman logs -f techpulse-scraper

# Restarting Indexer service
podman stop techpulse-indexer
podman rm techpulse-indexer
podman build --no-cache -t techpulse-indexer -f Containerfile.indexer services/indexer
podman-compose up -d indexer-service
podman logs -f techpulse-indexer

# Restarting Embedding service
podman stop techpulse-ai_embedding-service_1
podman rm techpulse-ai_embedding-service_1
podman build --no-cache -t techpulse-ai_embedding-service_1 -f Containerfile.embedding services/embedding
podman-compose up -d embedding-service
podman logs -f techpulse-ai_embedding-service_1

## To see all process
podman ps -a

