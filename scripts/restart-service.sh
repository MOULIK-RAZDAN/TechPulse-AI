#!/bin/bash

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SERVICE=$1

if [ -z "$SERVICE" ]; then
    echo "🔄 TechPulse AI - Service Restart Tool"
    echo ""
    echo "Usage: ./restart-service.sh <service-name>"
    echo ""
    echo -e "${BLUE}Available services:${NC}"
    echo "  backend           - FastAPI backend (code changes)"
    echo "  frontend          - Next.js frontend"
    echo "  scraper           - RSS scraper"
    echo "  dedup-service     - Deduplication service"
    echo "  embedding-service - Embedding service"
    echo "  indexer-service   - Indexer service"
    echo "  kafka             - Kafka broker"
    echo "  postgres          - PostgreSQL database"
    echo "  redis             - Redis cache"
    echo "  qdrant            - Qdrant vector store"
    echo "  elasticsearch     - Elasticsearch"
    echo "  logstash          - Logstash"
    echo "  kibana            - Kibana"
    echo "  filebeat          - Filebeat"
    echo "  zookeeper         - Zookeeper"
    echo ""
    echo -e "${BLUE}Special commands:${NC}"
    echo "  all               - Restart all services"
    echo "  app               - Restart only application services"
    echo "  elk               - Restart ELK stack"
    echo "  infra             - Restart infrastructure (Kafka, Postgres, etc.)"
    echo ""
    echo "Example: ./restart-service.sh backend"
    exit 1
fi

restart_service() {
    local service=$1
    echo -e "${YELLOW}🔄 Restarting $service...${NC}"
    
    # Stop the service first
    echo "  ⏸️  Stopping..."
    podman-compose stop $service 2>/dev/null
    
    # Rebuild if it's an app service
    case $service in
        backend|frontend|scraper|dedup-service|embedding-service|indexer-service)
            echo "  📦 Rebuilding image..."
            podman-compose build $service
            if [ $? -ne 0 ]; then
                echo -e "${RED}❌ Build failed for $service${NC}"
                return 1
            fi
            ;;
    esac
    
    # Start the service
    echo "  ▶️  Starting..."
    podman-compose up -d $service
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $service restarted successfully${NC}"
    else
        echo -e "${RED}❌ Failed to restart $service${NC}"
        return 1
    fi
    
    # Wait a moment for service to initialize
    sleep 3
    
    # Show logs for verification
    echo ""
    echo -e "${BLUE}📋 Recent logs:${NC}"
    podman-compose logs --tail=15 $service
}

case $SERVICE in
    all)
        echo -e "${YELLOW}🔄 Restarting ALL services...${NC}"
        echo ""
        podman-compose down
        sleep 2
        podman-compose up -d
        echo ""
        echo -e "${GREEN}✅ All services restarted${NC}"
        echo "⏳ Wait 60 seconds for all services to initialize"
        ;;
    
    app)
        echo -e "${YELLOW}🔄 Restarting application services...${NC}"
        echo ""
        services=("scraper" "dedup-service" "embedding-service" "indexer-service" "backend" "frontend")
        for svc in "${services[@]}"; do
            restart_service $svc
            echo ""
        done
        echo -e "${GREEN}✅ All application services restarted${NC}"
        ;;
    
    elk)
        echo -e "${YELLOW}🔄 Restarting ELK stack...${NC}"
        echo ""
        
        # Stop all ELK services
        podman-compose stop filebeat kibana logstash elasticsearch
        sleep 3
        
        # Start in correct order
        echo "  Starting Elasticsearch..."
        podman-compose up -d elasticsearch
        
        echo "  ⏳ Waiting 30 seconds for Elasticsearch..."
        sleep 30
        
        echo "  Starting Logstash and Kibana..."
        podman-compose up -d logstash kibana
        sleep 10
        
        echo "  Starting Filebeat..."
        podman-compose up -d filebeat
        
        echo ""
        echo -e "${GREEN}✅ ELK stack restarted${NC}"
        echo "⏳ Kibana will be available in ~2 minutes at http://localhost:5601"
        ;;
    
    infra)
        echo -e "${YELLOW}🔄 Restarting infrastructure services...${NC}"
        echo ""
        
        # Stop services
        podman-compose stop zookeeper kafka postgres redis qdrant
        sleep 3
        
        # Start in correct order
        echo "  Starting Zookeeper..."
        podman-compose up -d zookeeper
        sleep 10
        
        echo "  Starting Kafka, Postgres, Redis, Qdrant..."
        podman-compose up -d kafka postgres redis qdrant
        sleep 15
        
        echo ""
        echo -e "${GREEN}✅ Infrastructure restarted${NC}"
        echo "⏳ Wait 30 seconds before starting application services"
        ;;
    
    backend|frontend|scraper|dedup-service|embedding-service|indexer-service|kafka|postgres|redis|qdrant|elasticsearch|logstash|kibana|filebeat|zookeeper)
        restart_service $SERVICE
        ;;
    
    *)
        echo -e "${RED}❌ Unknown service: $SERVICE${NC}"
        echo ""
        echo "Run './restart-service.sh' to see available services"
        exit 1
        ;;
esac

echo ""