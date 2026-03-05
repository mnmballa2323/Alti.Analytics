import json
from google.cloud import aiplatform

class MLOpsTools:
    """
    Tools that grant the LangGraph Swarm direct control over the MLOps lifecycle.
    The Swarm autonomously decides when to retrain and when to promote models to production.
    """
    
    def __init__(self, project_id: str = "alti-analytics-production", region: str = "us-central1"):
        self.project_id = project_id
        self.region = region
        aiplatform.init(project=project_id, location=region)

    def trigger_retraining_pipeline(self, lookback_days: int = 30, epochs: int = 10) -> str:
        """
        Swarm Tool: Triggers the Vertex AI Kubeflow Pipeline to retrain the underlying anomaly detection 
        model using the freshest BigQuery data.
        
        Args:
            lookback_days (int): How many days of live telemetry to extract for fine-tuning.
            epochs (int): Number of training epochs.
        """
        try:
            # Load the compiled KFP JSON/YAML spec
            pipeline_job = aiplatform.PipelineJob(
                display_name="swarm-triggered-autonomous-retraining",
                template_path="gs://alti-mlops-artifacts/pipelines/autonomous_retraining_pipeline.yaml", # Mock GCS location
                parameter_values={
                    "project_id": self.project_id,
                    "region": self.region,
                    "lookback_days": lookback_days,
                    "epochs": epochs
                },
                enable_caching=False
            )
            
            # Submit asynchronously so the Swarm isn't blocked for hours
            pipeline_job.submit()
            return f"SUCCESS: Autonomous retraining pipeline initiated. Job ID: {pipeline_job.name}. The Swarm will receive a Pub/Sub alert when the pipeline completes with eval metrics."
            
        except Exception as e:
            return f"ERROR: Failed to trigger retraining pipeline: {str(e)}"

    def promote_vertex_model(self, model_resource_name: str, traffic_split: int = 100) -> str:
        """
        Swarm Tool: Promotes a trained model from the Vertex AI Registry to the live Endpoint.
        The Swarm invokes this after evaluating the new model's loss metrics outputted by the pipeline.
        
        Args:
            model_resource_name (str): The Vertex AI Registry Model ID (e.g., projects/.../models/...).
            traffic_split (int): Percentage of production traffic to shift to this new model.
        """
        try:
            # Assume a single omni-endpoint for anomaly detection
            endpoint_name = "alti-live-anomaly-endpoint"
            
            # Get the endpoint
            endpoints = aiplatform.Endpoint.list(filter=f'display_name="{endpoint_name}"')
            if not endpoints:
                return f"ERROR: Live Endpoint '{endpoint_name}' not found."
            
            endpoint = endpoints[0]
            
            # Identify the specific model version to deploy
            model = aiplatform.Model(model_name=model_resource_name)
            
            print(f"Swarm Command Executing: Deploying Model {model_resource_name} to Endpoint {endpoint_name} with {traffic_split}% traffic split.")
            
            # The deploy command updates the endpoint. If traffic_split is 100, the old model is replaced.
            endpoint.deploy(
                model=model,
                traffic_split={"0": traffic_split}, # '0' denotes the newly deployed deployed_model
                sync=True # Or False for async
            )
            
            # Note: In a real scenario, we would cleanly undeploy the old model if split is 100.
            
            return f"SUCCESS: Semantic Model {model_resource_name} has been successfully promoted to production Endpoint {endpoint.name}. System intelligence has been autonomously upgraded."
            
        except Exception as e:
            return f"ERROR: Failed to promote model to Endpoint: {str(e)}"

# Instantiate the tools for the LangGraph framework
mlops = MLOpsTools()

swarm_mlops_tools = [
    mlops.trigger_retraining_pipeline,
    mlops.promote_vertex_model
]
