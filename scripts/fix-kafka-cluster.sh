#!/bin/bash
# Fix Kafka cluster ID mismatch issue

echo "🔧 Fixing Kafka cluster ID mismatch..."

# Stop all services
echo "Stopping services..."
podman-compose down

# Remove Kafka and Zookeeper data volumes to clear cluster ID conflict
echo "Clearing Kafka/Zookeeper data..."
podman volume rm techpulse-ai_kafka-data techpulse-ai_zookeeper-data 2>/dev/null || true

# Restart core services
echo "Starting fresh Kafka cluster..."
podman-compose up -d zookeeper kafka

# Wait for Kafka to be ready
echo "Waiting for Kafka to initialize..."
sleep 30

# Create required topics
echo "Creating Kafka topics..."
podman exec techpulse-kafka kafka-topics --create --topic raw_articles --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 2>/dev/null || true
podman exec techpulse-kafka kafka-topics --create --topic processed_articles --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 2>/dev/null || true
podman exec techpulse-kafka kafka-topics --create --topic embeddings --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 2>/dev/null || true

echo "✅ Kafka cluster fixed! You can now start the scraper."