# infra/functions/leo-ingestion/main.py
import json
import os
import time
import random

# Epic 23: Extra-Planetary Ingestion & Space Domain Awareness
# Simulates a high-frequency WebSocket connection to a Low Earth Orbit (LEO) 
# satellite constellation (e.g., Starlink / Planet Labs), ingesting spatial 
# telemetry into Google Cloud Pub/Sub for anomaly detection by the Alti Swarm.

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "alti-analytics-prod")
TOPIC_ID = os.getenv("LEO_TELEMETRY_TOPIC", "leo-orb-telemetry-live")

def simulate_leo_websocket_ingestion():
    print("🛰️ [LEO INGESTION] Establishing WebSocket connection to Orbital Relay...")
    time.sleep(1)
    print("✅ Connection Established. Streaming spatial telemetry to Google Cloud Pub/Sub.")
    
    # Simulate orbital stream
    while True:
        try:
            # Orbital Vectors (Simplified TLE - Two-Line Element sets)
            telemetry = {
                "satellite_id": f"ALTI-SAT-{random.randint(100, 999)}",
                "altitude_km": random.uniform(500.0, 550.0),
                "velocity_kms": 7.66,
                "inclination_deg": 53.0,
                "timestamp_utc": time.time()
            }
            
            # In production: publisher.publish(topic_path, json.dumps(telemetry).encode("utf-8"))
            print(f"📡 Ingested: {json.dumps(telemetry)}")
            
            # Artificial throttle for demonstration
            time.sleep(2)
            break # Exit after one loop for the walkthrough simulation
            
        except KeyboardInterrupt:
            print("Terminating LEO Stream.")
            break

if __name__ == "__main__":
    simulate_leo_websocket_ingestion()
