import os
import json
import logging
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions

# GCP Configuration
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "alti-analytics-prod")
INPUT_TOPIC = f"projects/{PROJECT_ID}/topics/live-telemetry"
BQ_TABLE = f"{PROJECT_ID}:alti_analytics_prod.live_market_data"
ANOMALY_TOPIC = f"projects/{PROJECT_ID}/topics/tactical-anomalies"

class AnomalyDetectorDoFn(beam.DoFn):
    """
    Simulates a streaming Vertex AI ML Model that scores incoming telemetry for anomalies.
    If the anomaly score is critical (> 0.90), it forks the payload.
    """
    def process(self, element):
        try:
            payload = json.loads(element.decode("utf-8"))
            
            # Simulated Anomaly detection logic. In a real Dataflow pipeline,
            # this would call a pre-loaded local model or a Vertex AI Endpoint.
            # Example: Universal Anomaly Detection (high heart rate, extreme voltage, flash crash in price)
            
            anomaly_score = 0.1 # Base baseline score
            
            # Universal Scaffolding Rules:
            if "heart_rate" in payload and payload["heart_rate"] > 185:
                 anomaly_score = 0.95
            if "price" in payload and payload["price"] < 1000: # Simulated Crypto flash crash
                 anomaly_score = 0.98
            if "voltage" in payload and payload["voltage"] > 240.0: # Simulated Smart Grid anomaly
                 anomaly_score = 0.92
                 
            payload["anomaly_score"] = anomaly_score
            
            # Return regular payload for BigQuery, and tag Critical anomalies for Eventarc
            yield beam.pvalue.TaggedOutput('bq_sink', payload)
            
            if anomaly_score > 0.90:
                payload["critical_alert"] = True
                yield beam.pvalue.TaggedOutput('anomaly_sink', json.dumps(payload).encode("utf-8"))
                
        except Exception as e:
            logging.error(f"Failed to process element: {e}")

def run():
    options = PipelineOptions()
    options.view_as(StandardOptions).streaming = True
    
    with beam.Pipeline(options=options) as p:
        
        # 1. Read from Universal Pub/Sub Topic
        messages = (
            p 
            | "ReadPubSub" >> beam.io.ReadFromPubSub(topic=INPUT_TOPIC)
        )
        
        # 2. Inject Streaming ML Anomaly Detection Model
        scored_stream = (
            messages
            | "DetectAnomalies" >> beam.ParDo(AnomalyDetectorDoFn()).with_outputs('bq_sink', 'anomaly_sink')
        )
        
        # 3. Main Data Fabric Destination: BigQuery
        scored_stream.bq_sink | "WriteToBigQuery" >> beam.io.WriteToBigQuery(
            table=BQ_TABLE,
            write_disposition=beam.io.BigQueryDisposition.WRITE_APPEND,
            create_disposition=beam.io.BigQueryDisposition.CREATE_IF_NEEDED
        )
        
        # 4. Critical Event Fork: Emit to Anomaly Topic (Triggers Eventarc -> Swarm)
        scored_stream.anomaly_sink | "EmitTacticalWarning" >> beam.io.WriteToPubSub(
            topic=ANOMALY_TOPIC
        )

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    run()
