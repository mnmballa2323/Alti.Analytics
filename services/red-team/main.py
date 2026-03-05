from fastapi import FastAPI, BackgroundTasks, Request
import logging
from agents.attacker import red_team_swarm, HumanMessage

logger = logging.getLogger("red-team")
app = FastAPI(title="Alti.Analytics Autonomous Red Team (Gemini SecOps)")

async def execute_offensive_campaign():
    """
    Spins up the Red Team to autonomously hunt for vulnerabilities 
    across the deployed infrastructure.
    """
    logger.warning("INITIATING OFFENSIVE SECURITY CAMPAIGN...")
    
    prompt = """
    [DIRECTIVE]: Execute a black-box penetration test against the Alti.Analytics production infrastructure.
    
    Targets:
    1. Scan the active IAM policy bindings for overly broad permissions (e.g., roles/editor assigned to service accounts).
    2. Analyze the latest Terraform state file for misconfigured public buckets or unencrypted disks.
    3. Attempt to discover open ports or un-IAP-protected endpoints on the cluster.
    
    If you find a critical vulnerability, you MUST report it immediately so the Defense Swarm can actuate a fix.
    """
    
    initial_state = {
        "messages": [HumanMessage(content=prompt)],
        "campaign_active": True,
        "vulnerabilities_found": []
    }
    
    # Execute the offensive LangGraph
    final_state = red_team_swarm.invoke(initial_state)
    
    logger.warning(f"Offensive Campaign Concluded. Findings: {final_state['vulnerabilities_found']}")
    
    # In a full deployment, these findings are published back to the SCC Pub/Sub topic
    # to trigger the Defense Swarm (Epic 7/8).

@app.post("/v1/trigger_campaign")
async def trigger_campaign(background_tasks: BackgroundTasks):
    """
    Manual override endpoint. Typically, this campaign is invoked 
    automatically via Cloud Scheduler cron job (e.g., every 6 hours).
    """
    background_tasks.add_task(execute_offensive_campaign)
    return {"status": "accepted", "message": "Red Team campaign launched in background."}
