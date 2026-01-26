#!/bin/bash
set -e

echo "🚀 TechPulse AI - Setup Script"
echo ""

if ! command -v podman &> /dev/null; then
    echo "❌ Podman not installed"
    echo "Install: sudo apt-get install podman podman-compose"
    exit 1
fi

if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  Edit .env and add API keys, then run again!"
    exit 1
fi

source .env

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ API keys not set in .env!"
    exit 1
fi

echo "📦 Pulling base images..."
podman pull docker.io/postgres:16-alpine
podman pull docker.io/redis:7-alpine
podman pull docker.io/qdrant/qdrant:v1.7.4
podman pull docker.io/confluentinc/cp-zookeeper:7.5.0
podman pull docker.io/confluentinc/cp-kafka:7.5.0

# NEW: Pull ELK Stack images
echo ""
echo "📦 Pulling ELK Stack images..."
podman pull docker.io/elasticsearch:8.11.0
podman pull docker.io/logstash:8.11.0
podman pull docker.io/kibana:8.11.0
podman pull docker.io/elastic/filebeat:8.11.0

echo ""
echo "🔨 Building application images..."
podman build -t techpulse-scraper -f Containerfile.scraper scrapers
podman build -t techpulse-dedup -f Containerfile.dedup services/deduplication
podman build -t techpulse-embedding -f Containerfile.embedding services/embedding
podman build -t techpulse-indexer -f Containerfile.indexer services/indexer
podman build -t techpulse-backend -f Containerfile.backend backend
podman build -t techpulse-frontend -f Containerfile.frontend frontend

echo ""
echo "🚀 Starting infrastructure (Phase 1: Core Services)..."
podman-compose up -d zookeeper kafka postgres redis qdrant

echo "⏳ Waiting 30 seconds for core services..."
sleep 30

echo ""
echo "🚀 Starting infrastructure (Phase 2: ELK Stack)..."
podman-compose up -d elasticsearch

echo "⏳ Waiting 25 seconds for Elasticsearch to become healthy..."
sleep 25

# Wait for Elasticsearch health check
echo "🔍 Checking Elasticsearch health..."
until podman exec techpulse-elasticsearch curl -f http://localhost:9200/_cluster/health 2>/dev/null; do
    echo "   Waiting for Elasticsearch..."
    sleep 10
done

echo ""
echo "🚀 Starting Logstash, Kibana"
podman-compose up -d logstash kibana

echo "🚀 Starting Filebeat (optional)..."
podman-compose up -d filebeat 2>/dev/null || echo "  ⚠️  Filebeat skipped (not critical for development)"

echo "⏳ Waiting 30 seconds for ELK services..."
sleep 30

echo ""
echo "💾 Creating Kafka topics..."
chmod +x kafka-config/create_topics.sh
podman exec techpulse-kafka bash /kafka-config/create_topics.sh

echo ""
echo "🚀 Starting all application services..."
podman-compose up -d

echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ TechPulse AI is ready!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Access URLs:"
echo "  Frontend:       http://localhost:3000"
echo "  Backend API:    http://localhost:8000/docs"
echo "  Qdrant:         http://localhost:6333/dashboard"
echo "  Kibana (Logs):  http://localhost:5601"
echo "  Elasticsearch:  http://localhost:9200"
echo ""
echo "Commands:"
echo "  View logs:      podman-compose logs -f backend"
echo "  All logs:       podman-compose logs -f"
echo "  Stop all:       podman-compose down"
echo "  Restart:        podman-compose restart <service-name>"
echo ""
echo "ELK Stack:"
echo "  • Kibana will be available in ~2 minutes at http://localhost:5601"
echo "  • Create index pattern: 'logstash-*' in Kibana to view logs"
echo ""
echo "Note: Initial scraping takes 30+ minutes"
echo "════════════════════════════════════════════════════════════"