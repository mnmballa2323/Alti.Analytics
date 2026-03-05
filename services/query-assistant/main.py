from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
import httpx
import os

app = FastAPI(title="Alti.Analytics Query Assistant", version="1.0.0")

LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm-gateway-service:8000")

class AnalyzeRequest(BaseModel):
    natural_language_query: str
    tenant_id: str

class AnalyzeResponse(BaseModel):
    generated_sql: str
    explanation: str

@app.post("/v1/queries/generate-insights", response_model=AnalyzeResponse)
async def generate_sql_and_insights(request: AnalyzeRequest):
    """
    Translates Natural Language to SQL and generates prescriptive insights
    using the LLM Gateway. Focuses heavily on Business/Sports/Crypto datasets.
    """
    
    # In a full flow, we send the prompt to LLM Gateway -> Pinecone schema lookup -> generated SQL
    # async with httpx.AsyncClient() as client:
    #     response = await client.post(f"{LLM_GATEWAY_URL}/v1/chat", json={
    #         "query": request.natural_language_query,
    #         "tenant_id": request.tenant_id
    #     })
    
    dummy_sql = f"SELECT * FROM alti_analytics_prod.finance_data WHERE condition = 'true'"
    dummy_insight = "The data indicates an anomaly in recent transactions corresponding to the user query."
    
    return AnalyzeResponse(generated_sql=dummy_sql, explanation=dummy_insight)

@app.get("/health")
async def health_check():
    return {"status": "up"}
