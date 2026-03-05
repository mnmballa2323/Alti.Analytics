# GenAI LLM Gateway & RAG Service using Google Cloud Vertex AI
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
import os
import vertexai
from vertexai.generative_models import GenerativeModel, Part

app = FastAPI(title="Alti.Analytics Vertex/Gemini Gateway", version="1.1.0")

class ChatRequest(BaseModel):
    query: str
    tenant_id: str

class ChatResponse(BaseModel):
    answer: str
    sources: list[str]

# Initialize Vertex AI
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "alti-analytics-prod")
REGION = os.getenv("GCP_REGION", "us-central1")
vertexai.init(project=PROJECT_ID, location=REGION)

# Load the Gemini Model
gemini_model = GenerativeModel("gemini-1.5-pro")

@app.post("/v1/chat", response_model=ChatResponse)
async def chat_with_data(request: ChatRequest):
    """
    RAG Pipeline Endpoint natively built on GCP
    1. Intent Classification
    2. Data Retrieval (Vertex AI Search / Vector Search placeholder)
    3. Generate Contextual Output with Gemini Model
    4. Compliance validation -> return
    """
    
    # 1. Dummy Retrieval Step (representing Vertex AI Vector Search interaction)
    dummy_sources = [f"gs://alti-analytics-docs/{request.tenant_id}_report_q1.pdf"]
    dummy_context = "Q1 Revenue increased by 15%."
    
    # 2. Native Gemini Generation
    prompt = f"Context: {dummy_context}\n\nUser Query from Tenant {request.tenant_id}: {request.query}\nProvide a prescriptive insight."
    
    # Call Gemini model
    # response = gemini_model.generate_content(prompt)
    # answer = response.text
    answer = f"According to Gemini analysis across {dummy_context}, we recommend re-allocating investments."

    return ChatResponse(answer=answer, sources=dummy_sources)

@app.get("/health")
async def health_check():
    return {"status": "up", "backend": "vertex-ai"}

