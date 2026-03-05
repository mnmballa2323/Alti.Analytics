import asyncio
import json
import os
import random
import time
from datetime import datetime, timezone
from google.cloud import pubsub_v1

# GCP Configuration
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "alti-analytics-prod")
TOPIC_ID = os.getenv("PUBSUB_TOPIC_ID", "sports-telemetry")

try:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
except Exception as e:
    print(f"Pub/Sub init warning (running in dev mode): {e}")

async def simulate_optical_tracking():
    """
    Simulates high-frequency (10Hz) spatial and biometric tracking data
    for 11 players on a pitch (e.g. Soccer/Football).
    Generates X, Y coordinates, Speed, and Heart Rate.
    """
    print("Initializing Pro Sports IoT Telemetry Stream (10Hz)...")
    
    players = [f"Player_{i}" for i in range(1, 12)]
    
    while True:
        batch_events = []
        current_time = datetime.now(timezone.utc).isoformat()
        
        for player in players:
            # Simulate tactical movement and biometric load
            x_pos = round(random.uniform(0, 105), 2) # Pitch length (meters)
            y_pos = round(random.uniform(0, 68), 2)  # Pitch width (meters)
            speed_kmh = round(random.uniform(0, 32), 1) # Sprint speeds
            heart_rate = int(random.uniform(120, 195))
            
            event = {
                "event_type": "optical_telemetry",
                "player_id": player,
                "team_id": "HOME_TEAM",
                "timestamp": current_time,
                "spatial": {"x": x_pos, "y": y_pos},
                "biometrics": {"speed_kmh": speed_kmh, "heart_rate_bpm": heart_rate}
            }
            batch_events.append(event)
        
        # In a real environment, publish the batch to Cloud Pub/Sub
        for event in batch_events:
            data_bytes = json.dumps(event).encode("utf-8")
            try:
                # publisher.publish(topic_path, data=data_bytes)
                pass # Committing payload...
            except Exception:
                pass
        
        # Print a sample frame locally
        print(f"[{current_time}] Broadcasted spatial frame for 11 players. Sample: {batch_events[0]}")
        
        # 10Hz transmission loop (0.1 seconds)
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    try:
        asyncio.run(simulate_optical_tracking())
    except KeyboardInterrupt:
        print("Telemetry stream terminated.")
