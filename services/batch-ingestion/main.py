import os
import requests
import json
from datetime import datetime, timezone
from google.cloud import storage

# GCP Configuration
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "alti-analytics-prod")
BUCKET_NAME = os.getenv("GCS_BRONZE_BUCKET", "alti-analytics-dev-bronze")

def fetch_sports_api_data(endpoint_url: str) -> dict:
    """
    Simulates fetching paginated sport/crypto data from a third-party REST API.
    e.g., https://api.sportradar.us/soccer/trial/v4/en/schedules/2026-03-05/schedule.json
    """
    print(f"Fetching data from external provider: {endpoint_url}")
    # In a real scenario, requests.get() with pagination handling
    # response = requests.get(endpoint_url, headers={"Authorization": f"Bearer {API_KEY}"})
    # return response.json()
    
    # Scaffolding mock massive nested JSON payload
    return {
        "metadata": {
            "provider": "MockRadarApi",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "records_extracted": 2
        },
        "events": [
            {
                "match_id": "M_1001",
                "home_team": "Team_A",
                "away_team": "Team_B",
                "play_by_play": [
                    {"minute": 12, "action": "shot_on_target", "player": "Player_9"},
                    {"minute": 45, "action": "yellow_card", "player": "Player_4"}
                ]
            },
            {
                "match_id": "M_1002",
                "home_team": "Team_C",
                "away_team": "Team_D",
                "play_by_play": [
                    {"minute": 88, "action": "goal", "player": "Player_10"}
                ]
            }
        ]
    }

def upload_to_gcs_bronze(data: dict):
    """
    Sinks the raw JSON payload into the GCS Bronze Data Lake.
    """
    try:
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        
        # Partition the raw data by date
        current_date = datetime.now(timezone.utc).strftime("%Y%m%d")
        blob_name = f"raw_stats/external_api/dt={current_date}/batch_{datetime.now(timezone.utc).timestamp()}.json"
        
        blob = bucket.blob(blob_name)
        blob.upload_from_string(
            data=json.dumps(data),
            content_type='application/json'
        )
        print(f"Successfully uploaded {len(data['events'])} events to gs://{BUCKET_NAME}/{blob_name}")
        
    except Exception as e:
        print(f"GCS Upload Failed (Ensure running locally with GCP Auth or in Cloud Run): {e}")
        # Saving locally for scaffold verification if GCS auth is missing
        with open("local_bronze_dump.json", "w") as f:
            json.dump(data, f)
        print("Saved payload locally to local_bronze_dump.json")


def run_batch_ingestion():
    url = os.getenv("EXTERNAL_API_URL", "https://api.mock-provider.com/v1/historical_stats")
    raw_data = fetch_sports_api_data(url)
    upload_to_gcs_bronze(raw_data)

if __name__ == "__main__":
    # Cloud Run will execute this entrypoint on a scheduled Cloud Scheduler trigger
    run_batch_ingestion()
