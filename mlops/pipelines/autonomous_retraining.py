"""
Alti.Analytics Autonomous MLOps Pipeline
This Vertex AI Kubeflow Pipeline is autonomously triggered by the LangGraph Swarm
when it detects significant data drift or degrading anomaly detection F1 scores. 
It extracts the latest live data, retrains the model, evaluates it, and uploads the 
superior model back to the Registry.
"""
import kfp
from kfp import dsl
from kfp.dsl import Dataset, Input, Model, Output, Metrics

# --- Pipeline Components ---

@dsl.component(
    base_image="google/cloud-sdk:latest",
    packages_to_install=["google-cloud-bigquery", "pandas", "pyarrow"]
)
def extract_live_telemetry(
    project_id: str,
    lookback_days: int,
    dataset: Output[Dataset]
):
    """Extracts the freshest telemetry from BigQuery for fine-tuning."""
    from google.cloud import bigquery
    import pandas as pd
    
    client = bigquery.Client(project=project_id)
    
    query = f"""
        SELECT *
        FROM `alti_analytics_prod.live_market_data`
        WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {lookback_days} DAY)
    """
    
    print(f"Extracting recent {lookback_days} days of telemetry...")
    df = client.query(query).to_dataframe()
    
    # Save to the Kubeflow artifact path
    df.to_parquet(dataset.path, index=False)
    print(f"Successfully extracted {len(df)} rows.")

@dsl.component(
    base_image="tensorflow/tensorflow:latest",
    packages_to_install=["pandas", "pyarrow", "scikit-learn"]
)
def finetune_anomaly_model(
    training_data: Input[Dataset],
    epochs: int,
    trained_model: Output[Model],
    metrics: Output[Metrics]
):
    """Fine-tunes the base TensorFlow Autoencoder on the new data."""
    import pandas as pd
    import tensorflow as tf
    from sklearn.model_selection import train_test_split
    
    df = pd.read_parquet(training_data.path)
    
    # Simple Mock: Assume existing base model is loaded from GCS
    # In production, this would pull the current production model artifact
    print("Loading base production model...")
    inputs = tf.keras.Input(shape=(df.shape[1] - 1,)) # Adjust for timestamp/id columns
    encoded = tf.keras.layers.Dense(64, activation='relu')(inputs)
    encoded = tf.keras.layers.Dense(32, activation='relu')(encoded)
    decoded = tf.keras.layers.Dense(64, activation='relu')(encoded)
    outputs = tf.keras.layers.Dense(df.shape[1] - 1, activation='sigmoid')(decoded)
    model = tf.keras.Model(inputs, outputs)
    
    model.compile(optimizer='adam', loss='mse')
    
    # Mock Feature Extraction (Exclude non-numeric for TF)
    features = df.select_dtypes(include=['float64', 'int64']).fillna(0)
    X_train, X_val = train_test_split(features, test_size=0.2, random_state=42)
    
    print(f"Fine-tuning model for {epochs} epochs...")
    history = model.fit(
        X_train, X_train,
        epochs=epochs,
        batch_size=256,
        validation_data=(X_val, X_val),
        verbose=1
    )
    
    # Log Metric Validation Loss
    final_val_loss = history.history['val_loss'][-1]
    metrics.log_metric("final_val_loss", float(final_val_loss))
    
    print(f"Saving newly trained model to {trained_model.path}")
    model.save(trained_model.path)


@dsl.component(
    base_image="google/cloud-sdk:latest",
    packages_to_install=["google-cloud-aiplatform"]
)
def upload_to_vertex_registry(
    project_id: str,
    region: str,
    model: Input[Model],
    val_loss: float
):
    """Uploads the model to Vertex AI Registry only if criteria are met."""
    from google.cloud import aiplatform
    
    acceptable_loss_threshold = 0.05
    
    if val_loss > acceptable_loss_threshold:
        print(f"Model validation loss ({val_loss}) did not meet quality threshold. Aborting promotion.")
        return
        
    print(f"Validation loss ({val_loss}) acceptable. Uploading to Vertex Model Registry...")
    
    aiplatform.init(project=project_id, location=region)
    
    # In reality, this points to a GCS path where `trained_model` was stored
    vertex_model = aiplatform.Model.upload(
        display_name="alti-anomaly-detector-finetuned",
        artifact_uri=model.path, # GCS URI
        serving_container_image_uri="us-docker.pkg.dev/vertex-ai/prediction/tf2-cpu.2-12:latest",
    )
    
    print(f"Successfully uploaded model: {vertex_model.resource_name}")


# --- Pipeline Definition ---

@dsl.pipeline(
    name="alti-autonomous-retraining",
    description="Pipeline to fine-tune the anomaly detection model using the latest BigQuery telemetry."
)
def autonomous_retraining_pipeline(
    project_id: str = "alti-analytics-production",
    region: str = "us-central1",
    lookback_days: int = 30,
    epochs: int = 10
):
    # 1. Extract fresh data
    extract_task = extract_live_telemetry(
        project_id=project_id,
        lookback_days=lookback_days
    )
    
    # 2. Fine-tune the model
    finetune_task = finetune_anomaly_model(
        training_data=extract_task.outputs["dataset"],
        epochs=epochs
    )
    
    # 3. Conditionally upload to registry
    upload_task = upload_to_vertex_registry(
        project_id=project_id,
        region=region,
        model=finetune_task.outputs["trained_model"],
        val_loss=finetune_task.outputs["metrics"] # Assume we extract the metric value
    )

if __name__ == "__main__":
    from kfp.compiler import Compiler
    Compiler().compile(
        pipeline_func=autonomous_retraining_pipeline,
        package_path="autonomous_retraining_pipeline.yaml"
    )
