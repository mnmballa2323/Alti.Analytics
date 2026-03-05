from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator

default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'el_gcs_to_bq_daily',
    default_args=default_args,
    description='Load Silver layer data from GCS to BigQuery Data Warehouse',
    schedule_interval=timedelta(days=1),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['elt', 'bigquery', 'core'],
) as dag:

    load_users = GCSToBigQueryOperator(
        task_id='gcs_to_bq_users',
        bucket='alti-analytics-silver-lake',
        source_objects=['users/dt={{ ds }}/*.parquet'],
        destination_project_dataset_table='alti_analytics_prod.users',
        source_format='PARQUET',
        write_disposition='WRITE_TRUNCATE',
        autodetect=True,
    )

    load_billing = GCSToBigQueryOperator(
        task_id='gcs_to_bq_billing',
        bucket='alti-analytics-silver-lake',
        source_objects=['billing/dt={{ ds }}/*.parquet'],
        destination_project_dataset_table='alti_analytics_prod.billing',
        source_format='PARQUET',
        write_disposition='WRITE_APPEND',
        autodetect=True,
    )

    load_users >> load_billing
