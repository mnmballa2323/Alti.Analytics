import datetime
from airflow import DAG
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.providers.google.cloud.operators.dataproc import DataprocInstantiateInlineWorkflowTemplateOperator

# DAG Defaults
default_args = {
    'owner': 'alti-data-eng',
    'depends_on_past': False,
    'email_on_failure': True,
    'retries': 2,
    'retry_delay': datetime.timedelta(minutes=5),
}

# GCP Variables
PROJECT_ID = "alti-analytics-prod"
REGION = "us-central1"

# Dataproc Serverless PySpark Template Configuration
dataproc_pyspark_job = {
    "placement": {
        "managed_cluster": {
            "cluster_name": "serverless-spark-cluster",
            "config": {
                "temp_bucket": "alti-analytics-dev-dataproc-temp"
            }
        }
    },
    "jobs": [
        {
            "step_id": "flatten_raw_sports_json",
            "pyspark_job": {
                "main_python_file_uri": "gs://alti-analytics-dev-artifacts/pyspark/spark_etl.py",
                "args": [
                    "gs://alti-analytics-dev-bronze/raw_stats/external_api/dt=*/",
                    "alti-analytics-prod.alti_analytics_prod.silver_game_logs",
                    "alti-analytics-dev-dataproc-temp"
                ]
            }
        }
    ]
}

with DAG(
    'ingest_external_apis_to_bq_silver',
    default_args=default_args,
    description='Nightly Batch ETL: Scrape 3rd Party Sports APIs (Cloud Run) into Bronze, then structure and load to BigQuery (Dataproc).',
    schedule_interval='0 2 * * *',  # Run at 2 AM every day
    start_date=datetime.datetime(2026, 3, 5),
    catchup=False,
    tags=['batch', 'elt', 'dataproc', 'api-ingestion'],
) as dag:

    # 1. Trigger the Cloud Run scraper container
    # Assuming Cloud Run is fronted by an internal endpoint or API Gateway
    trigger_api_scraper = SimpleHttpOperator(
        task_id='trigger_cloud_run_api_ingestion',
        http_conn_id='cloud_run_batch_scraper',
        endpoint='/trigger_nightly_batch',
        method='POST',
        headers={"Content-Type": "application/json"},
        # Cloud Run typically responds immediately and processes asynchronously, 
        # or we wait for simple small batch responses.
        response_check=lambda response: response.status_code == 200,
    )

    # 2. Trigger the Dataproc PySpark Job to flatten the new GCS contents
    run_dataproc_etl = DataprocInstantiateInlineWorkflowTemplateOperator(
        task_id="flatten_bronze_json_to_bq",
        project_id=PROJECT_ID,
        region=REGION,
        template=dataproc_pyspark_job,
    )

    # 3. Execution Graph
    trigger_api_scraper >> run_dataproc_etl
