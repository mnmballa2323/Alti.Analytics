from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import vertexai
from vertexai.generative_models import GenerativeModel, Tool, FunctionDeclaration
from google.cloud import bigquery

app = FastAPI(title="Alti.Analytics Autonomous Query Agent", version="2.0.0")

# GCP Init
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "alti-analytics-prod")
REGION = os.getenv("GCP_REGION", "us-central1")
vertexai.init(project=PROJECT_ID, location=REGION)
bq_client = bigquery.Client(project=PROJECT_ID)

# Define BigQuery Tool for Gemini
execute_sql_func = FunctionDeclaration(
    name="execute_bigquery_sql",
    description="Executes a Standard SQL query against the Alti.Analytics BigQuery database and returns the results as a JSON string.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The entirely valid BigQuery SQL string to execute. Do not include markdown formatting like ```sql."
            }
        },
        "required": ["query"]
    }
)
bq_tool = Tool(function_declarations=[execute_sql_func])

# Initialize Gemini 1.5 Pro with Tools
model = GenerativeModel(
    "gemini-1.5-pro",
    tools=[bq_tool],
    system_instruction=["You are an expert Data Analyst working on the Alti.Analytics platform. You have access to a tool that executes SQL on our BigQuery data warehouse. Our primary table is `alti_analytics_prod.live_market_data` which contains `symbol`, `price`, `quantity`, and `timestamp`. Whenever a user asks a question, generate the required SQL, call the tool to fetch the exact data, and then provide a prescriptive business insight."]
)

class AnalyzeRequest(BaseModel):
    natural_language_query: str

class AnalyzeResponse(BaseModel):
    insight: str
    executed_sql: str | None = None

def run_query(sql: str) -> str:
    """Helper function bound to the Gemini tool definition."""
    try:
        query_job = bq_client.query(sql)
        results = [dict(row) for row in query_job]
        return str(results)
    except Exception as e:
        return f"Error executing SQL: {e}"

@app.post("/v1/agent/analyze", response_model=AnalyzeResponse)
async def autonomous_analysis(request: AnalyzeRequest):
    """
    Agentic Workflow:
    1. Send user query to Gemini.
    2. Gemini decides if it requires the `execute_bigquery_sql` function.
    3. If yes, extract the SQL, execute it locally, and feed the result back to Gemini.
    4. Gemini returns the final natural language insight.
    """
    chat = model.start_chat()
    try:
        response = chat.send_message(request.natural_language_query)
        
        executed_sql = None
        # Handle Function Calling
        if response.function_call:
            func_call = response.function_call
            if func_call.name == "execute_bigquery_sql":
                executed_sql = func_call.args["query"]
                print(f"Agent generated SQL: {executed_sql}")
                
                # Execute the SQL tool locally
                # bq_result = run_query(executed_sql) 
                bq_result = "[{'avg_price': 65000.50}]" # Dummy result for scaffolding without active BQ instance
                
                # Feed the data back into the chat
                response = chat.send_message(
                    vertexai.generative_models.Part.from_function_response(
                        name="execute_bigquery_sql",
                        response={"result": bq_result}
                    )
                )
        
        return AnalyzeResponse(insight=response.text, executed_sql=executed_sql)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "up", "agent": "gemini-autonomous"}
