# services/llm-gateway/tracing.py
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.cloud_trace_propagator import CloudTraceFormatPropagator

def setup_cloud_trace(app):
    """
    Instruments the FastAPI LLM Gateway to export distributed traces directly 
    to Google Cloud Trace (part of Google Cloud Operations / Stackdriver).
    Allows us to visualize the exact latency breakdown of caching vs Gemini invocation.
    """
    
    # In a local/mock environment without GCP credentials, fallback to console or disable
    project_id = os.getenv("GCP_PROJECT_ID", "alti-analytics-prod")
    enable_tracing = os.getenv("ENABLE_GCP_TRACING", "false").lower() == "true"
    
    if not enable_tracing:
        print("ℹ️ GCP Cloud Trace is disabled (ENABLE_GCP_TRACING=false). Skipping OpenTelemetry setup.")
        return

    try:
        # Set up Google Cloud Trace Propagator to continue traces from the Next.js Frontend
        set_global_textmap(CloudTraceFormatPropagator())

        # Initialize Tracer Provider
        tracer_provider = TracerProvider()
        trace.set_tracer_provider(tracer_provider)
        
        # Configure the Google Cloud Trace Exporter
        cloud_trace_exporter = CloudTraceSpanExporter(project_id=project_id)
        
        # Add the exporter to the provider (batches spans for efficiency)
        tracer_provider.add_span_processor(BatchSpanProcessor(cloud_trace_exporter))
        
        # Instrument the FastAPI app automatically
        FastAPIInstrumentor.instrument_app(app)
        
        print(f"✅ OpenTelemetry Cloud Trace instrumented successfully for project {project_id}.")
        
    except Exception as e:
        print(f"⚠️ Failed to instrument OpenTelemetry Cloud Trace: {e}")
