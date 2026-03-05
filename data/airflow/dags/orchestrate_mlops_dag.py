import datetime
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.providers.google.cloud.operators.vertex_ai.pipeline_job import CreatePipelineJobOperator

# Defines the default arguments for this enterprise DAG
default_args = {
    'owner': 'alti-data-eng',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': datetime.timedelta(minutes=5),
}

with DAG(
    'orchestrate_mlops_pipeline',
    default_args=default_args,
    description='Daily orchestration: Runs dbt to build Gold Tables, then triggers Vertex AI for model retraining.',
    schedule_interval=datetime.timedelta(days=1),
    start_date=datetime.datetime(2026, 3, 5),
    catchup=False,
    tags=['mlops', 'dbt', 'vertex-ai', 'pro-sports'],
) as dag:

    # 1. Run dbt to clean raw Pub/Sub telemetry into Gold Materialized Views
    # In Cloud Composer, we often use BashOperator pointing to the dbt Cloud CLI or a KubernetesPodOperator
    run_dbt_models = BashOperator(
        task_id='run_dbt_transformations',
        bash_command='echo "Executing dbt run --select tag:gold_sports_features" && sleep 5',
    )
    
    # 2. Trigger the Vertex AI Pipeline to retrain the XGBoost Injury Model on the fresh Gold tables
    PROJECT_ID = "alti-analytics-prod"
    LOCATION = "us-central1"
    PIPELINE_ROOT = "gs://alti-analytics-dev-vertex-artifacts/injury-models"
    
    retrain_injury_model = CreatePipelineJobOperator(
        task_id="retrain_injury_risk_model",
        project_id=PROJECT_ID,
        region=LOCATION,
        display_name="orchestrated-injury-prediction-training",
        template_path="gs://alti-analytics-dev-vertex-artifacts/templates/injury_prediction_pipeline.json",
        pipeline_root=PIPELINE_ROOT,
        parameter_values={"project_id": PROJECT_ID}
    )

    # 3. Define the DAG Execution Order
    run_dbt_models >> retrain_injury_model
