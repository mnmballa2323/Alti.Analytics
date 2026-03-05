import kfp
from kfp.v2 import compiler
from kfp.v2.dsl import component, Output, Dataset, Model
from google.cloud import aiplatform

@component(packages_to_install=["pandas", "google-cloud-bigquery", "db-dtypes"])
def extract_acwr_data(
    project_id: str,
    output_dataset: Output[Dataset]
):
    """
    Extracts Acute:Chronic Workload Ratios (ACWR) and player biometrics
    from BigQuery telemetry to predict tissue injury risk.
    """
    import pandas as pd
    from google.cloud import bigquery
    
    client = bigquery.Client(project=project_id)
    # Dummy Query matching the optical_telemetry structure
    query = """
        SELECT player_id, AVG(biometrics.heart_rate_bpm) as avg_hr, MAX(biometrics.speed_kmh) as top_speed
        FROM `alti_analytics_prod.live_market_data` 
        WHERE event_type = 'optical_telemetry'
        GROUP BY player_id LIMIT 1000
    """
    # df = client.query(query).to_dataframe()
    # Dummy dataframe for scaffolding
    df = pd.DataFrame({'player_id': ['Player_1', 'Player_2'], 'avg_hr': [160, 145], 'top_speed': [28.5, 30.1], 'injury_risk': [1, 0]})
    df.to_csv(output_dataset.path, index=False)

@component(packages_to_install=["pandas", "xgboost", "scikit-learn"])
def train_injury_model(
    dataset: kfp.v2.dsl.Input[Dataset],
    model_output: Output[Model]
):
    """Trains an XGBoost Classification model on biometric workloads."""
    import pandas as pd
    from xgboost import XGBClassifier
    from sklearn.model_selection import train_test_split
    
    df = pd.read_csv(dataset.path)
    X = df[['avg_hr', 'top_speed']]
    y = df['injury_risk']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
    
    model = XGBClassifier(n_estimators=100, max_depth=3)
    model.fit(X_train, y_train)
    
    # Save the model
    model.save_model(model_output.path + ".bst")
    
@kfp.v2.dsl.pipeline(
    name="alti-injury-prediction-pipeline",
    description="Vertex AI Pipeline for calculating ACWR and predicting sports soft-tissue injuries.",
    pipeline_root="gs://alti-analytics-dev-vertex-artifacts/injury-models"
)
def injury_prediction_pipeline(project_id: str = "alti-analytics-prod"):
    data_op = extract_acwr_data(project_id=project_id)
    train_op = train_injury_model(dataset=data_op.outputs["output_dataset"])

if __name__ == "__main__":
    compiler.Compiler().compile(
        pipeline_func=injury_prediction_pipeline,
        package_path="injury_prediction_pipeline.json"
    )
    # aiplatform.init(project="alti-analytics-prod", location="us-central1")
    # job = aiplatform.PipelineJob(display_name="injury-prediction-training", template_path="injury_prediction_pipeline.json", parameter_values={})
    # job.submit()
