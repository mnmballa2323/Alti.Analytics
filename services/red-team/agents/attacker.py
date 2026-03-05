from typing import Annotated, Sequence, TypedDict
import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain_google_vertexai import ChatVertexAI
from langgraph.graph import StateGraph, END

class AttackerState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    campaign_active: bool
    vulnerabilities_found: list[str]

# Gemini 1.5 Pro acts as the Lead Penetration Tester
llm = ChatVertexAI(model="gemini-1.5-pro", project="alti-analytics-prod", location="us-central1")

# --- Offensive Tooling ---
@tool
def scan_iam_bindings() -> str:
    """Simulates checking active GCP IAM policies for privilege escalation risks."""
    return "VULNERABILITY FOUND: Service Account 'alti-eventarc-invoker' has editor access instead of specific event receiver roles."

@tool
def analyze_terraform_state() -> str:
    """Simulates parsing the raw tfstate for hardcoded secrets or misconfigurations."""
    return "SAFE: All buckets ensure uniform bucket level access. No hardcoded secrets found."

@tool
def nmap_internal_cluster() -> str:
    """Simulates scanning the internal Kubernetes overlay network for exposed services."""
    return "SAFE: Network policies are properly enforcing namespace isolation. Istio STRICT mTLS verified."

llm_with_tools = llm.bind_tools([scan_iam_bindings, analyze_terraform_state, nmap_internal_cluster])

# --- Swarm Node ---
def offensive_node(state: AttackerState):
    """The central intelligence of the Red Team. It decides which tools to fire."""
    prompt = f"Executing offensive campaign. Current state messages: {state['messages']}"
    
    response = llm_with_tools.invoke(prompt)
    
    # Simulated extraction of what the LLM found (in reality, parsed from tool blocks)
    new_vulns = []
    if "VULNERABILITY FOUND" in response.content:
        new_vulns.append(response.content)
        
    return {
        "messages": [response], 
        "vulnerabilities_found": state["vulnerabilities_found"] + new_vulns,
        "campaign_active": False # Terminate after one pass for scaffolding
    }

# --- Graph Definition ---
workflow = StateGraph(AttackerState)
workflow.add_node("attacker", offensive_node)
workflow.set_entry_point("attacker")
workflow.add_edge("attacker", END)

red_team_swarm = workflow.compile()
