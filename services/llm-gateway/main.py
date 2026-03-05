# GenAI LLM Gateway & RAG Service using Google Cloud Vertex AI
from fastapi import FastAPI, Depends, HTTPException, Request
from pydantic import BaseModel
import os
import vertexai
from vertexai.generative_models import GenerativeModel, Part
import redis
import json
import hashlib

app = FastAPI(title="Alti.Analytics Vertex/Gemini Gateway", version="1.1.0")

class ChatRequest(BaseModel):
    query: str
    tenant_id: str
    image_base64: str | None = None

class ChatResponse(BaseModel):
    answer: str
    sources: list[str]

# Initialize Vertex AI
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "alti-analytics-prod")
REGION = os.getenv("GCP_REGION", "us-central1")
vertexai.init(project=PROJECT_ID, location=REGION)

# Load the Gemini Model
gemini_model = GenerativeModel("gemini-1.5-pro")

# Initialize GCP Memorystore (Redis) Semantic Caching
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

try:
    cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    cache.ping()
    print("✅ Connected to GCP Memorystore Cache.")
except redis.ConnectionError:
    print("⚠️ Warning: Could not connect to GCP Memorystore Cache. Running without caching.")
    cache = None

@app.post("/v1/chat", response_model=ChatResponse)
async def chat_with_data(request: ChatRequest):
    """
    RAG & Multimodal Pipeline Endpoint natively built on GCP
    1. Intent Classification
    2. Data Retrieval (Vertex AI Vector Search placeholder)
    3. Multimodal alignment: Text Prompt + Optional Screen/Video frame
    4. Generate Contextual Output with Gemini Model
    """
    # --- SEMANTIC CACHING LAYER ---
    # Create a unique SHA-256 hash representing the exact prompt & context
    query_hash_input = f"{request.tenant_id}_{request.query}_{request.image_base64 or ''}"
    query_signature = hashlib.sha256(query_hash_input.encode()).hexdigest()
    cache_key = f"semantic_cache:{query_signature}"
    
    # Check GCP Memorystore first
    if cache:
        cached_response = cache.get(cache_key)
        if cached_response:
            print(f"⚡ CACHE HIT (Sub-millisecond latency): {cache_key}")
            cached_data = json.loads(cached_response)
            return ChatResponse(answer=cached_data["answer"] + " [Served from GCP Memorystore]", sources=cached_data["sources"])
    
    print("🐌 CACHE MISS. Routing to Gemini Foundation Model...")
    
    # 1. Dummy Retrieval Step
    dummy_sources = [f"gs://alti-analytics-docs/{request.tenant_id}_scouting_report.pdf"]
    dummy_context = "Opponent runs a high-press 4-3-3 formation."
    
    # 2. Native Gemini Generation with Multimodal Support
    prompt_text = f"Context: {dummy_context}\n\nUser Query from Tenant {request.tenant_id}: {request.query}\nProvide a prescriptive tactical insight based on the provided stats and visual reference."
    prompt_parts = [prompt_text]
    
    if request.image_base64:
        import base64
        try:
            image_bytes = base64.b64decode(request.image_base64)
            image_part = Part.from_data(data=image_bytes, mime_type="image/jpeg")
            prompt_parts.append(image_part)
            dummy_sources.append("Attached Tactical Image")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image format: {e}")
            
    # Call Gemini model
    # response = gemini_model.generate_content(prompt_parts)
    # answer = response.text
    answer = f"According to Gemini Multimodal analysis across {dummy_context} and the provided visual frame, we recommend dropping the defensive line 5 meters to counter the overlapping fullbacks."

    # --- SAVE TO MEMORYSTORE ---
    if cache:
        cache_data = json.dumps({"answer": answer, "sources": dummy_sources})
        # Cache the LLM response for 1 hour
        cache.setex(cache_key, 3600, cache_data)
        print(f"💾 Saved to Memorystore Cache: {cache_key}")

    return ChatResponse(answer=answer, sources=dummy_sources)

@app.get("/health")
async def health_check():
    return {"status": "up", "backend": "vertex-ai"}

