from typing import Annotated, Sequence, TypedDict
import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_google_vertexai import ChatVertexAI
from langgraph.graph import StateGraph, END
from pydantic import BaseModel

# 1. Define the State shared between Agents
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    tactical_context: str
    vision_analysis_complete: bool
    data_analysis_complete: bool

# 2. Define the Swarm Nodes (Agents)
llm = ChatVertexAI(model="gemini-1.5-pro", project="alti-analytics-prod", location="us-central1")

def supervisor_node(state: AgentState):
    """The Head Coach. Routes the query based on what is missing."""
    last_message = state["messages"][-1]
    
    # Simple routing logic for the scaffold
    if not state.get("data_analysis_complete"):
        return {"messages": [AIMessage(content="Routing to Data Engineer to fetch BigQuery telemetry.")]}
    elif not state.get("vision_analysis_complete") and "image" in last_message.content.lower():
        return {"messages": [AIMessage(content="Routing to Vision Analyst to review tactical game film.")]}
    else:
        # Synthesis
        prompt = f"Synthesize a final tactical plan based on the data and vision context. Previous messages: {state['messages']}"
        response = llm.invoke(prompt)
        return {"messages": [response]}

def data_engineer_node(state: AgentState):
    """Extracts historical BigQuery Load/Telemetry Data."""
    # Dummy tool execution
    analysis = "DATA ENG REPORT: Player_1 has an ACWR of 1.45 (High Risk). Team average sprint speed is down 8% compared to Q1."
    return {"messages": [AIMessage(content=analysis)], "data_analysis_complete": True}

def vision_analyst_node(state: AgentState):
    """Analyzes opponent formations via Gemini Multimodal."""
    # Continues from earlier Base64 pipeline
    analysis = "VISION REPORT: Opponent defensive block is playing a high line (45 meters from goal), leaving space behind the fullbacks."
    return {"messages": [AIMessage(content=analysis)], "vision_analysis_complete": True}

# 3. Define the StateGraph Routing (LangGraph)
def route_from_supervisor(state: AgentState) -> str:
    """Decides the next node based on state."""
    if not state.get("data_analysis_complete"):
        return "data_engineer"
    elif not state.get("vision_analysis_complete"):
        # We assume vision is wanted in this flow
        return "vision_analyst"
    return END

# 4. Build and Compile the Graph
workflow = StateGraph(AgentState)

workflow.add_node("supervisor", supervisor_node)
workflow.add_node("data_engineer", data_engineer_node)
workflow.add_node("vision_analyst", vision_analyst_node)

# Execution Flow
workflow.set_entry_point("supervisor")
workflow.add_conditional_edges(
    "supervisor",
    route_from_supervisor,
    {
        "data_engineer": "data_engineer",
        "vision_analyst": "vision_analyst",
        END: END
    }
)
# Workers always report back to the supervisor
workflow.add_edge("data_engineer", "supervisor")
workflow.add_edge("vision_analyst", "supervisor")

app_swarm = workflow.compile()

# Example Invocation Strategy for FastAPI endpoint
def execute_tactical_swarm(query: str, has_image: bool = False):
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "tactical_context": "Opponent: Team X",
        "data_analysis_complete": False,
        "vision_analysis_complete": not has_image # Skip vision if no image provided
    }
    
    # In reality, you'd iterate app_swarm.stream(initial_state) to yield progress to the frontend UI
    final_state = app_swarm.invoke(initial_state)
    return final_state["messages"][-1].content
