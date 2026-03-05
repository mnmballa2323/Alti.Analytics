from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import logging
from datetime import datetime, timezone

logger = logging.getLogger("actuation-engine")
app = FastAPI(title="Alti.Analytics Universal Actuation Engine")

class ActuationRequest(BaseModel):
    action_type: str        # e.g., "TRADE_EXECUTION", "EMERGENCY_DISPATCH", "TACTICAL_WARNING"
    target_entity: str      # e.g., "BTC_USD", "Ambulance_Unit_4", "Head_Coach_Device"
    parameters: dict        # e.g., {"amount": 1.5, "side": "BUY"}
    justification: str      # Swarm's reasoning for this autonomous action

@app.post("/v1/execute_action")
async def execute_autonomous_action(req: ActuationRequest, request: Request):
    """
    Called by the LangGraph Swarm when it determines an intervention is required.
    In a real system, this securely interfaces with external brokers, dispatch systems, etc.
    """
    logger.warning(f"AUTONOMOUS ACTUATION REQUESTED: {req.action_type} for {req.target_entity}")
    
    # 1. Security Authorization & Risk Checks (Scaffolded)
    # Ensure the Swarm isn't requesting something outside of allowed bounds
    if req.action_type == "TRADE_EXECUTION":
        if req.parameters.get("amount", 0) > 1000000:
            raise HTTPException(status_code=403, detail="Trade size exceeds autonomous threshold.")
    
    # 2. Execute Real-World Action (Simulated)
    execution_receipt = f"ACT_{int(datetime.now(timezone.utc).timestamp())}"
    
    logger.info(f"Execution Successful. Receipt: {execution_receipt}")
    logger.info(f"Justification logged: {req.justification}")
    
    # 3. Webhook broadcast to Frontend (Next.js Edge Config)
    # This triggers the "⚠️ AUTONOMOUS ACTUATION IN PROGRESS" global alert
    await push_edge_alert_to_frontend(req.dict(), execution_receipt)
    
    return {
        "status": "SUCCESS",
        "receipt_id": execution_receipt,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": f"Successfully executed {req.action_type} on {req.target_entity}."
    }

async def push_edge_alert_to_frontend(action_details: dict, receipt: str):
    """
    Simulates sending a server-sent event or Vercel Edge Config update 
    so the Frontend React dashboard flashes instantly.
    """
    try:
        import requests
        # In reality, this would hit the Next.js API route we will build next
        # requests.post("http://alti-web-portal/api/actuation", json={"action": action_details, "receipt": receipt})
        logger.info("Edge Alert pushed to Web Portal.")
    except Exception as e:
        logger.error(f"Failed to push Edge Alert: {e}")
