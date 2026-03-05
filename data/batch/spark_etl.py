import os
import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, explode, current_timestamp, to_timestamp

def create_spark_session() -> SparkSession:
    """Initializes a Spark session configured for Google Cloud Storage and BigQuery."""
    # Dataproc Serverless injects the required bigquery/gcs connectors automatically
    return SparkSession.builder \
        .appName("AltiAnalytics-Sports-Batch-ETL") \
        .getOrCreate()

def run_etl(spark: SparkSession, input_path: str, output_table: str, temp_gcs_bucket: str):
    """
    Reads raw nested JSON from GCS Bronze, flattens it, and writes cleanly to BigQuery Silver.
    """
    print(f"Reading raw data from: {input_path}")
    
    # 1. Extract: Read Bronze JSON
    raw_df = spark.read.json(input_path)
    
    # 2. Transform: Flatten out the JSON schema
    # Example raw structure matches our Cloud Run scraper schema
    # raw_df schema: metadata (struct), events (array of structs)
    
    # Explode the array of matches/events
    exploded_df = raw_df.select(
        col("metadata.provider").alias("source_provider"),
        to_timestamp(col("metadata.timestamp")).alias("ingestion_timestamp"),
        explode(col("events")).alias("match_event")
    )
    
    # Flatten inner match details and the play-by-play actions
    flattened_df = exploded_df.select(
        col("source_provider"),
        col("ingestion_timestamp"),
        col("match_event.match_id").alias("match_id"),
        col("match_event.home_team").alias("home_team"),
        col("match_event.away_team").alias("away_team"),
        explode(col("match_event.play_by_play")).alias("action_detail")
    ).select(
        col("source_provider"),
        col("ingestion_timestamp"),
        col("match_id"),
        col("home_team"),
        col("away_team"),
        col("action_detail.minute").cast("integer").alias("game_minute"),
        col("action_detail.action").alias("event_type"),
        col("action_detail.player").alias("player_id"),
        current_timestamp().alias("etl_processed_at")
    )
    
    flattened_df.printSchema()
    
    # 3. Load: Write the flattened, optimized data directly to BigQuery Silver layer
    print(f"Writing transformed data to BigQuery Table: {output_table}")
    flattened_df.write \
        .format("bigquery") \
        .option("table", output_table) \
        .option("temporaryGcsBucket", temp_gcs_bucket) \
        .mode("append") \
        .save()
        
    print("ETL Batch Load Complete.")

if __name__ == "__main__":
    # In Dataproc, arguments are passed via the job submisssion
    input_path = sys.argv[1] if len(sys.argv) > 1 else "gs://alti-analytics-dev-bronze/raw_stats/external_api/dt=*/"
    output_table = sys.argv[2] if len(sys.argv) > 2 else "alti-analytics-prod.alti_analytics_prod.silver_game_logs"
    temp_bucket = sys.argv[3] if len(sys.argv) > 3 else "alti-analytics-dev-dataproc-temp"
    
    spark_session = create_spark_session()
    run_etl(spark_session, input_path, output_table, temp_bucket)
    spark_session.stop()
