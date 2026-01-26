#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🧹 TechPulse AI - Cleanup Script"
echo ""
echo "This will remove:"
echo "  • All containers"
echo "  • All volumes (ALL DATA WILL BE LOST)"
echo "  • All built images"
echo "  • All networks"
echo ""
echo -e "${YELLOW}⚠️  WARNING: This action cannot be undone!${NC}"
echo ""

# Ask for confirmation
read -p "Are you sure you want to continue? (yes/no): " confirmation

if [ "$confirmation" != "yes" ]; then
    echo -e "${GREEN}✅ Cleanup cancelled${NC}"
    exit 0
fi

echo ""
echo "Starting cleanup..."
echo ""

# Stop all containers
echo -e "${YELLOW}[1/5] Stopping all containers...${NC}"
podman-compose down 2>/dev/null || echo "  No running containers"

# Remove all containers (force)
echo -e "${YELLOW}[2/5] Removing containers...${NC}"
containers=$(podman ps -a --filter "name=techpulse" -q)
if [ -n "$containers" ]; then
    podman rm -f $containers
    echo -e "${GREEN}  ✓ Removed containers${NC}"
else
    echo "  No containers to remove"
fi

# Remove all volumes
echo -e "${YELLOW}[3/5] Removing volumes (DATA WILL BE DELETED)...${NC}"
volumes=$(podman volume ls --filter "name=techpulse" -q)
if [ -n "$volumes" ]; then
    podman volume rm -f $volumes
    echo -e "${GREEN}  ✓ Removed volumes:${NC}"
    echo "    - zookeeper-data"
    echo "    - kafka-data"
    echo "    - postgres-data"
    echo "    - redis-data"
    echo "    - qdrant-data"
    echo "    - elasticsearch-data"
    echo "    - filebeat-data"
else
    echo "  No volumes to remove"
fi

# Remove built images
echo -e "${YELLOW}[4/5] Removing built images...${NC}"
images=$(podman images --filter "reference=techpulse-*" -q)
if [ -n "$images" ]; then
    podman rmi -f $images
    echo -e "${GREEN}  ✓ Removed images:${NC}"
    echo "    - techpulse-scraper"
    echo "    - techpulse-dedup"
    echo "    - techpulse-embedding"
    echo "    - techpulse-indexer"
    echo "    - techpulse-backend"
    echo "    - techpulse-frontend"
else
    echo "  No images to remove"
fi

# Remove network
echo -e "${YELLOW}[5/5] Removing networks...${NC}"
networks=$(podman network ls --filter "name=techpulse" -q)
if [ -n "$networks" ]; then
    podman network rm $networks 2>/dev/null || echo "  Network in use or already removed"
    echo -e "${GREEN}  ✓ Removed networks${NC}"
else
    echo "  No networks to remove"
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo -e "${GREEN}✅ Cleanup complete!${NC}"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "System is now clean. To rebuild:"
echo "  ./setup.sh"
echo ""
echo "Optional: Remove base images to free more space"
echo "  podman rmi docker.io/postgres:16-alpine"
echo "  podman rmi docker.io/redis:7-alpine"
echo "  podman rmi docker.io/qdrant/qdrant:v1.7.4"
echo "  podman rmi docker.io/confluentinc/cp-zookeeper:7.5.0"
echo "  podman rmi docker.io/confluentinc/cp-kafka:7.5.0"
echo "  podman rmi docker.io/elasticsearch:8.11.0"
echo "  podman rmi docker.io/logstash:8.11.0"
echo "  podman rmi docker.io/kibana:8.11.0"
echo "  podman rmi docker.io/elastic/filebeat:8.11.0"
echo ""
echo "To remove ALL unused images, containers, and volumes:"
echo "  podman system prune -a --volumes"
echo "════════════════════════════════════════════════════════════"