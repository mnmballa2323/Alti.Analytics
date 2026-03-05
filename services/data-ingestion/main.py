import asyncio
import websockets
import json
import os
from google.cloud import pubsub_v1

# GCP Configuration
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "alti-analytics-prod")
TOPIC_ID = os.getenv("PUBSUB_TOPIC_ID", "live-events")

# Initialize Pub/Sub Publisher
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

async def binance_trade_stream():
    """
    Connects to Binance WebSocket for live BTC/USDT and ETH/USDT trades
    and streams them to Google Cloud Pub/Sub.
    """
    uri = "wss://stream.binance.com:9443/ws/btcusdt@trade/ethusdt@trade"
    
    async with websockets.connect(uri) as websocket:
        print(f"Connected to {uri}. Streaming live events to Pub/Sub topic: {topic_path}...")
        try:
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                
                # Normalize payload
                event = {
                    "event_type": "trade",
                    "symbol": data.get("s"),
                    "price": data.get("p"),
                    "quantity": data.get("q"),
                    "timestamp": data.get("T")
                }
                
                # Publish to Pub/Sub
                data_str = json.dumps(event)
                data_bytes = data_str.encode("utf-8")
                future = publisher.publish(topic_path, data=data_bytes)
                
                print(f"Published message ID: {future.result()} | Data: {event['symbol']} at {event['price']}")
                
        except websockets.ConnectionClosed:
            print("WebSocket connection closed. Attempting to reconnect...")
        except Exception as e:
            print(f"Error during streaming: {e}")

if __name__ == "__main__":
    asyncio.run(binance_trade_stream())
