#!/bin/bash

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "📊 TechPulse AI - System Status"
echo ""

# Function to check if service is running
check_service() {
    local service_name=$1
    local container_name=$2
    
    if podman ps --filter "name=$container_name" --format "{{.Names}}" | grep -q "$container_name"; then
        echo -e "  ${GREEN}✓${NC} $service_name"
    else
        echo -e "  ${RED}✗${NC} $service_name ${YELLOW}(not running)${NC}"
    fi
}

# Infrastructure Services
echo -e "${BLUE}Infrastructure:${NC}"
check_service "Zookeeper       " "techpulse-zookeeper"
check_service "Kafka           " "techpulse-kafka"
check_service "PostgreSQL      " "techpulse-postgres"
check_service "Redis           " "techpulse-redis"
check_service "Qdrant          " "techpulse-qdrant"

echo ""
echo -e "${BLUE}ELK Stack:${NC}"
check_service "Elasticsearch   " "techpulse-elasticsearch"
check_service "Logstash        " "techpulse-logstash"
check_service "Kibana          " "techpulse-kibana"
check_service "Filebeat        " "techpulse-filebeat"

echo ""
echo -e "${BLUE}Application Services:${NC}"
check_service "Scraper         " "techpulse-scraper"
check_service "Deduplication   " "techpulse-dedup"
check_service "Embedding       " "techpulse-ai-embedding-service"
check_service "Indexer         " "techpulse-indexer"
check_service "Backend         " "techpulse-backend"
check_service "Frontend        " "techpulse-frontend"

# Health Checks
echo ""
echo -e "${BLUE}Health Checks:${NC}"

# Postgres
if PGPASSWORD=changeme psql -h localhost -U admin -d techpulse -c "SELECT COUNT(*) FROM articles;" 2>/dev/null | grep -q "row"; then
    article_count=$(PGPASSWORD=changeme psql -h localhost -U admin -d techpulse -t -c "SELECT COUNT(*) FROM articles;" 2>/dev/null | xargs)
    echo -e "  ${GREEN}✓${NC} PostgreSQL: ${article_count} articles indexed"
else
    echo -e "  ${YELLOW}⚠${NC} PostgreSQL: Connection failed (psql not installed?)"
fi

# Redis
if redis-cli -h localhost -p 6379 -a changeme PING 2>/dev/null | grep -q "PONG"; then
    key_count=$(redis-cli -h localhost -p 6379 -a changeme DBSIZE 2>/dev/null | awk '{print $2}')
    echo -e "  ${GREEN}✓${NC} Redis: ${key_count} cached queries"
else
    echo -e "  ${YELLOW}⚠${NC} Redis: Connection failed (redis-cli not installed?)"
fi

# Qdrant
if curl -s http://localhost:6333/collections/tech_articles 2>/dev/null | grep -q "points_count"; then
    vector_count=$(curl -s http://localhost:6333/collections/tech_articles 2>/dev/null | grep -oP '"points_count":\K\d+')
    echo -e "  ${GREEN}✓${NC} Qdrant: ${vector_count} vector chunks"
else
    echo -e "  ${YELLOW}⚠${NC} Qdrant: Collection not initialized"
fi

# Elasticsearch
if curl -s http://localhost:9200/_cluster/health 2>/dev/null | grep -q "yellow\|green"; then
    health=$(curl -s http://localhost:9200/_cluster/health 2>/dev/null | grep -oP '"status":"\K[^"]+')
    doc_count=$(curl -s http://localhost:9200/_cat/count/logstash-*?h=count 2>/dev/null | xargs)
    if [ -z "$doc_count" ]; then
        doc_count="0"
    fi
    echo -e "  ${GREEN}✓${NC} Elasticsearch: ${health} (${doc_count} log entries)"
else
    echo -e "  ${RED}✗${NC} Elasticsearch: Not responding"
fi

# Kibana
if curl -s http://localhost:5601/api/status 2>/dev/null | grep -q "available"; then
    echo -e "  ${GREEN}✓${NC} Kibana: Available"
else
    echo -e "  ${YELLOW}⚠${NC} Kibana: Not ready yet"
fi

# Backend
if curl -s http://localhost:8000/health 2>/dev/null | grep -q "healthy"; then
    echo -e "  ${GREEN}✓${NC} Backend API: Responding"
else
    echo -e "  ${RED}✗${NC} Backend API: Not responding"
fi

# Resource Usage
echo ""
echo -e "${BLUE}Resource Usage:${NC}"
echo "  Containers: $(podman ps --filter 'name=techpulse' --format '{{.Names}}' | wc -l) running"
echo "  Volumes:    $(podman volume ls --filter 'name=techpulse' --format '{{.Name}}' | wc -l) active"

total_size=$(podman volume ls --filter 'name=techpulse' --format '{{.Name}}' | while read vol; do
    podman volume inspect "$vol" --format '{{.Mountpoint}}' | xargs du -sh 2>/dev/null | cut -f1
done | grep -oP '\d+' | awk '{s+=$1} END {print s}')

if [ -n "$total_size" ]; then
    echo "  Disk Usage: ~${total_size}MB"
fi

# Access URLs
echo ""
echo -e "${BLUE}Access URLs:${NC}"
echo "  Frontend:      http://localhost:3000"
echo "  Backend API:   http://localhost:8000/docs"
echo "  Kibana:        http://localhost:5601"
echo "  Qdrant:        http://localhost:6333/dashboard"
echo "  Elasticsearch: http://localhost:9200"

# Quick Actions
echo ""
echo -e "${BLUE}Quick Actions:${NC}"
echo "  View logs:     podman-compose logs -f backend"
echo "  Restart all:   podman-compose restart"
echo "  Stop all:      podman-compose down"
echo "  Full cleanup:  ./cleanup.sh"
echo "  Reset data:    ./reset-data.sh"

echo ""