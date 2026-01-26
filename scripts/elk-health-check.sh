#!/bin/bash

echo "🔍 TechPulse AI - ELK Stack Health Check"
echo ""

# Check Elasticsearch
echo -n "Elasticsearch: "
if curl -s http://localhost:9200/_cluster/health | grep -q "yellow\|green"; then
    echo "✅ Healthy"
else
    echo "❌ Not responding"
fi

# Check Logstash
echo -n "Logstash:      "
if curl -s http://localhost:9600/_node/stats | grep -q "pipelines"; then
    echo "✅ Running"
else
    echo "❌ Not responding"
fi

# Check Kibana
echo -n "Kibana:        "
if curl -s http://localhost:5601/api/status | grep -q "available"; then
    echo "✅ Available"
else
    echo "⚠️  Still starting (wait 2-3 minutes)"
fi

# Check Filebeat
echo -n "Filebeat:      "
if podman ps | grep -q techpulse-filebeat; then
    echo "✅ Running"
else
    echo "❌ Not running"
fi

echo ""
echo "Elasticsearch indices:"
curl -s http://localhost:9200/_cat/indices?v | grep -E "health|logstash" || echo "  No indices yet"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Next Steps:"
echo "  1. Open Kibana: http://localhost:5601"
echo "  2. Go to: Management → Stack Management → Index Patterns"
echo "  3. Create pattern: 'logstash-*'"
echo "  4. Select timestamp field: '@timestamp'"
echo "  5. View logs: Analytics → Discover"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"