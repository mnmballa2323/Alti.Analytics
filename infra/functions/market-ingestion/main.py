import functions_framework
import json
import os
from google.cloud import pubsub_v1

# Epic 17: High-Frequency Market Ingestion
# A Serverless Cloud Function triggered by HTTP to ingest FIX protocol or REST market tick data
# into the Alti.Analytics Pub/Sub stream for immediate Edge/Wasm arbitrage evaluation.

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "alti-analytics-prod")
TOPIC_ID = os.getenv("MARKET_TICK_TOPIC", "market-ticks-live")

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

@functions_framework.http
def ingest_market_tick(request):
    """HTTP Cloud Function for ultra-low latency tick ingestion."""
    try:
        request_json = request.get_json(silent=True)
        if not request_json or 'symbol' not in request_json:
            return ("Invalid direct tick payload.", 400)

        # Structure the standardized tick event for the Swarm
        tick_event = {
            "source": "NYSE_BATS",
            "symbol": request_json['symbol'],
            "price": request_json['price'],
            "volume": request_json.get('volume', 0),
            "timestamp_ms": request_json.get('timestamp_ms')
        }

        # Publish rapidly to Google Cloud Pub/Sub
        data_str = json.dumps(tick_event)
        data_bytes = data_str.encode("utf-8")
        
        future = publisher.publish(topic_path, data_bytes)
        message_id = future.result()
        
        return (f"Tick ingested [Message ID: {message_id}]", 200)
    
    except Exception as e:
        print(f"Ingestion Error: {e}")
        return ("Internal Server Error", 500)
