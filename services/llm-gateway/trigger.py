from fastapi import FastAPI, Request, BackgroundTasks
import json
import logging
from agents.swarm import app_swarm, HumanMessage

logger = logging.getLogger("eventarc_trigger")
trigger_app = FastAPI(title="Alti.Analytics Eventarc Webhook")

async def investigate_anomaly_background(payload: dict):
    """
    Asynchronously spins up the LangGraph Swarm when Eventarc hits the webhook.
    The swarm investigates the anomaly and determines if Actuation is necessary.
    """
    logger.warning(f"CRITICAL ANOMALY EVENT RECEIVED: {payload}")
    
    # Construct a high-priority synthetic prompt for the Supervisor Agent
    prompt = f"""
    [SYSTEM OVERRIDE]: CRITICAL LIVE ANOMALY DETECTED IN TELEMETRY STREAM.
    Details: {json.dumps(payload, indent=2)}
    
    Instructions:
    1. Immediately investigate the cause of this anomaly using your Data Engineer.
    2. If this requires real-world intervention (trade execution, tactical warning, emergency dispatch),
       you MUST use your Actuation Tool to resolve it immediately.
    """
    
    initial_state = {
        "messages": [HumanMessage(content=prompt)],
        "tactical_context": f"Active Emergency - Source: {payload.get('source_provider', 'Unknown')}",
        "data_analysis_complete": False,
        "vision_analysis_complete": True # Skip vision for pure data telemetry anomalies
    }
    
    # Hardcoded system thread ID for autonomous actions
    config = {"configurable": {"thread_id": "AUTONOMOUS_SYSTEM_THREAD"}}
    
    logger.info("Waking up Swarm for investigation...")
    # The swarm will load, run its graph, and potentially trigger the actuation tool autonomously.
    final_state = app_swarm.invoke(initial_state, config=config)
    
    logger.info(f"Swarm Investigation Concluded: {final_state['messages'][-1].content}")


@trigger_app.post("/v1/events/anomaly")
async def handle_anomaly_event(request: Request, background_tasks: BackgroundTasks):
    """
    Webhook target for Google Cloud Eventarc. 
    Eventarc listens to the 'tactical-anomalies' Pub/Sub topic and POSTs here.
    """
    try:
        # Eventarc passes PubSub messages encoded in the body
        body = await request.json()
        
        # Typically Eventarc wraps it in a CloudEvent standard format
        if "message" in body and "data" in body["message"]:
            import base64
            decoded_data = base64.b64decode(body["message"]["data"]).decode("utf-8")
            payload = json.loads(decoded_data)
        else:
            payload = body
            
        # Push Swarm execution to background so Eventarc gets an immediate 200 OK
        background_tasks.add_task(investigate_anomaly_background, payload)
        
        return {"status": "accepted", "message": "Anomaly handed off to Swarm."}
        
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON payload format."}
    except Exception as e:
        logger.error(f"Eventarc webhook error: {e}")
        return {"status": "error", "message": str(e)}
