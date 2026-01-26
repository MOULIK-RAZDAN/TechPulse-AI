#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "🔄 TechPulse AI - Data Reset Script"
echo ""
echo "This will:"
echo "  • Stop all containers"
echo "  • Delete all data volumes"
echo "  • Restart containers with fresh databases"
echo ""
echo -e "${YELLOW}⚠️  All articles, embeddings, and logs will be deleted${NC}"
echo -e "${GREEN}✓  Images and configurations will be preserved${NC}"
echo ""

read -p "Continue? (yes/no): " confirmation

if [ "$confirmation" != "yes" ]; then
    echo -e "${GREEN}✅ Reset cancelled${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}Starting data reset...${NC}"
echo ""

# Stop all services
echo -e "${YELLOW}[1/4] Stopping all services...${NC}"
podman-compose down
echo -e "${GREEN}  ✓ Services stopped${NC}"

# Remove data volumes only
echo -e "${YELLOW}[2/4] Removing data volumes...${NC}"
volumes_to_remove=(
    "techpulse-ai_zookeeper-data"
    "techpulse-ai_kafka-data"
    "techpulse-ai_postgres-data"
    "techpulse-ai_redis-data"
    "techpulse-ai_qdrant-data"
    "techpulse-ai_elasticsearch-data"
    "techpulse-ai_filebeat-data"
)

for volume in "${volumes_to_remove[@]}"; do
    if podman volume exists "$volume" 2>/dev/null; then
        podman volume rm "$volume" && echo "  ✓ Removed $volume"
    fi
done

echo -e "${GREEN}  ✓ All data volumes removed${NC}"

# Restart infrastructure
echo -e "${YELLOW}[3/4] Restarting infrastructure...${NC}"
podman-compose up -d zookeeper kafka postgres redis qdrant elasticsearch

echo "  ⏳ Waiting 45 seconds for services to initialize..."
sleep 45

# Wait for Elasticsearch health
echo "  🔍 Waiting for Elasticsearch..."
until podman exec techpulse-elasticsearch curl -f http://localhost:9200/_cluster/health 2>/dev/null | grep -q "yellow\|green"; do
    echo "     Still waiting..."
    sleep 5
done

echo -e "${GREEN}  ✓ Infrastructure ready${NC}"

# Start remaining services
echo -e "${YELLOW}[4/4] Starting application services...${NC}"
podman-compose up -d logstash kibana filebeat

sleep 10

# Recreate Kafka topics
echo "  📝 Creating Kafka topics..."
chmod +x kafka-config/create_topics.sh
podman exec techpulse-kafka bash /kafka-config/create_topics.sh

# Start application services
podman-compose up -d scraper dedup-service embedding-service indexer-service backend frontend

echo ""
echo "════════════════════════════════════════════════════════════"
echo -e "${GREEN}✅ Data reset complete!${NC}"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Fresh databases initialized:"
echo "  • PostgreSQL (empty articles table)"
echo "  • Redis (cache cleared)"
echo "  • Qdrant (no vectors)"
echo "  • Kafka (fresh topics)"
echo "  • Elasticsearch (no logs yet)"
echo ""
echo "Services:"
echo "  Frontend:    http://localhost:3000"
echo "  Backend:     http://localhost:8000/docs"
echo "  Kibana:      http://localhost:5601"
echo ""
echo "The scraper will start collecting articles in ~2 minutes"
echo "════════════════════════════════════════════════════════════"