#!/bin/bash
BROKER="kafka:9092"
kafka-topics --create --bootstrap-server $BROKER --topic raw_articles --partitions 10 --if-not-exists
#kafka-topics --create --bootstrap-server $BROKER --topic embedded_articles --partitions 5 --if-not-exists
kafka-topics --create --bootstrap-server $BROKER --topic indexer_queue --partitions 10 --if-not-exists
echo "Topics created!"
