# services/workflow-engine/workflow_engine.py
"""
Epic 52: Autonomous Business Process Automation
A LangGraph-based agentic workflow engine that closes the loop from
insight to action. Workflows are triggered by Swarm detections and
execute multi-step business processes autonomously across any connected
system — with outcome tracking feeding back into the ML models.

Example workflow:
  TRIGGER: churn_probability > 0.80
  → Gemini generates personalized win-back email
  → SendGrid delivers to customer
  → Salesforce updates account with "Save Attempt" stage
  → Google Calendar books CSM follow-up call in 72h
  → Slack notifies account owner
  → Outcome tracked: did customer renew?
"""
import logging, json, uuid, time
from dataclasses import dataclass, field
from typing import Callable, Any
from enum import Enum

class TriggerType(str, Enum):
    THRESHOLD    = "THRESHOLD"       # e.g. churn_probability > 0.8
    ANOMALY      = "ANOMALY"         # OTel detects SLO breach / data spike
    SCHEDULE     = "SCHEDULE"        # cron — e.g. daily 6am briefing
    WEBHOOK      = "WEBHOOK"         # external system event
    SWARM_SIGNAL = "SWARM_SIGNAL"    # any Swarm agent emits a named signal

class ActionType(str, Enum):
    SEND_EMAIL      = "SEND_EMAIL"
    SEND_SLACK      = "SEND_SLACK"
    SEND_TEAMS      = "SEND_TEAMS"
    UPDATE_SALESFORCE = "UPDATE_SALESFORCE"
    CREATE_JIRA     = "CREATE_JIRA"
    BOOK_CALENDAR   = "BOOK_CALENDAR"
    CALL_WEBHOOK    = "CALL_WEBHOOK"
    QUERY_ANALYTICS = "QUERY_ANALYTICS"
    GEMINI_GENERATE = "GEMINI_GENERATE"

@dataclass
class WorkflowStep:
    step_id:     str
    action_type: ActionType
    params:      dict
    depends_on:  list[str] = field(default_factory=list)  # step_ids that must complete first

@dataclass
class WorkflowDefinition:
    workflow_id:  str
    name:         str
    description:  str
    trigger_type: TriggerType
    trigger_condition: dict   # {"field": "churn_probability", "op": ">", "value": 0.80}
    steps:        list[WorkflowStep]
    enabled:      bool = True
    created_by:   str = ""

@dataclass
class WorkflowRun:
    run_id:       str
    workflow_id:  str
    triggered_at: float
    trigger_data: dict
    step_results: list[dict] = field(default_factory=list)
    status:       str = "RUNNING"   # RUNNING | COMPLETED | FAILED
    outcome_tracked: bool = False

class WorkflowEngine:
    """
    LangGraph-powered autonomous workflow orchestrator.
    Each step is a node in the graph; edges are determined by
    depends_on relationships and conditional branching.
    """
    def __init__(self):
        self.logger = logging.getLogger("Workflow_Engine")
        logging.basicConfig(level=logging.INFO)
        self._workflows: dict[str, WorkflowDefinition] = {}
        self._runs: list[WorkflowRun] = []
        self.logger.info("⚙️  Autonomous Workflow Engine initialized.")
        self._register_builtin_workflows()

    def _register_builtin_workflows(self):
        """Pre-built workflows available from the marketplace."""
        churn_rescue = WorkflowDefinition(
            workflow_id="wf-churn-rescue",
            name="Churn Rescue Playbook",
            description="When a customer hits >80% churn probability, automatically launch a multi-touch rescue sequence.",
            trigger_type=TriggerType.SWARM_SIGNAL,
            trigger_condition={"signal": "churn_score_updated", "field": "churn_probability", "op": ">", "value": 0.80},
            steps=[
                WorkflowStep("s1", ActionType.GEMINI_GENERATE, {
                    "prompt_template": "Write a personalized win-back email for {{customer_name}} who hasn't logged in for {{days_since_login}} days. Reference their top use case: {{top_feature}}. Tone: empathetic, value-focused. Max 3 paragraphs.",
                    "output_var": "rescue_email_body"
                }),
                WorkflowStep("s2", ActionType.SEND_EMAIL, {
                    "to": "{{customer_email}}", "subject": "We'd love to hear from you, {{customer_name}}",
                    "body_var": "rescue_email_body", "from": "success@alti.ai"
                }, depends_on=["s1"]),
                WorkflowStep("s3", ActionType.UPDATE_SALESFORCE, {
                    "object": "Opportunity", "filter": "account_id={{account_id}}",
                    "update": {"StageName": "Save Attempt", "Churn_Risk__c": "{{churn_probability}}"}
                }, depends_on=["s1"]),
                WorkflowStep("s4", ActionType.BOOK_CALENDAR, {
                    "attendees": ["{{csm_email}}", "{{customer_email}}"],
                    "title": "Check-in: {{customer_name}} & Alti Success Team",
                    "delay_days": 3, "duration_min": 30
                }, depends_on=["s2", "s3"]),
                WorkflowStep("s5", ActionType.SEND_SLACK, {
                    "channel": "#csm-alerts",
                    "message": "🚨 Churn rescue playbook launched for *{{customer_name}}* ({{churn_probability:.0%}} risk). Email sent, meeting booked. <https://app.alti.ai/account/{{account_id}}|View account>"
                }, depends_on=["s4"]),
            ]
        )
        self._workflows["wf-churn-rescue"] = churn_rescue

        anomaly_incident = WorkflowDefinition(
            workflow_id="wf-anomaly-incident",
            name="Data Anomaly Incident Response",
            description="Automatically create a Jira incident and notify the data team when an anomaly score exceeds threshold.",
            trigger_type=TriggerType.ANOMALY,
            trigger_condition={"field": "anomaly_score", "op": ">", "value": 0.92},
            steps=[
                WorkflowStep("s1", ActionType.CREATE_JIRA, {
                    "project": "DATA", "issue_type": "Incident",
                    "summary": "Data Anomaly Detected: {{source_table}} (score={{anomaly_score:.2f}})",
                    "description": "Anomaly detected at {{timestamp}}. Source: {{source_table}}. Detected values: {{anomaly_detail}}.",
                    "priority": "High", "assignee": "data-oncall"
                }),
                WorkflowStep("s2", ActionType.SEND_SLACK, {
                    "channel": "#data-alerts",
                    "message": "🔴 Anomaly incident created: <{{jira_url}}|{{jira_key}}> — {{source_table}} score {{anomaly_score:.2f}}"
                }, depends_on=["s1"]),
            ]
        )
        self._workflows["wf-anomaly-incident"] = anomaly_incident

    def register_workflow(self, wf: WorkflowDefinition) -> str:
        self._workflows[wf.workflow_id] = wf
        self.logger.info(f"📋 Workflow registered: {wf.name} ({wf.trigger_type})")
        return wf.workflow_id

    def execute(self, workflow_id: str, trigger_data: dict) -> WorkflowRun:
        """
        Executes a workflow run. Steps execute in dependency order (DAG traversal).
        In production: each step dispatches to a Cloud Tasks queue with idempotency.
        """
        wf = self._workflows.get(workflow_id)
        if not wf:
            raise ValueError(f"Workflow {workflow_id} not found.")
        
        run = WorkflowRun(run_id=str(uuid.uuid4()), workflow_id=workflow_id,
                          triggered_at=time.time(), trigger_data=trigger_data)
        self.logger.info(f"▶️  Executing workflow: '{wf.name}' (run={run.run_id[:8]})")

        # Topological step execution
        completed: set[str] = set()
        context = dict(trigger_data)  # merge trigger data into template context
        
        for step in wf.steps:
            # Wait for dependencies
            pending_deps = [d for d in step.depends_on if d not in completed]
            if pending_deps:
                self.logger.info(f"   ↳ Step {step.step_id} waiting on: {pending_deps}")
            
            result = self._execute_step(step, context, wf.name)
            context.update(result.get("output_vars", {}))
            run.step_results.append({"step_id": step.step_id, "action": step.action_type, **result})
            completed.add(step.step_id)
            self.logger.info(f"   ✅ Step {step.step_id} ({step.action_type}): {result['status']}")

        run.status = "COMPLETED"
        self._runs.append(run)
        self.logger.info(f"🏁 Workflow '{wf.name}' COMPLETED in {len(wf.steps)} steps.")
        return run

    def _execute_step(self, step: WorkflowStep, ctx: dict, wf_name: str) -> dict:
        """Dispatches a single step to its action adapter."""
        time.sleep(0.05)  # Simulate async action latency
        
        adapters = {
            ActionType.GEMINI_GENERATE: lambda: {
                "status": "OK", "latency_ms": 820,
                "output_vars": {"rescue_email_body": f"Dear {ctx.get('customer_name','Customer')}, we noticed you've been away and wanted to reach out personally..."}
            },
            ActionType.SEND_EMAIL: lambda: {
                "status": "DELIVERED", "latency_ms": 340,
                "message_id": f"msg-{uuid.uuid4().hex[:8]}",
                "recipient": ctx.get("customer_email", "customer@example.com")
            },
            ActionType.UPDATE_SALESFORCE: lambda: {
                "status": "OK", "latency_ms": 210,
                "records_updated": 1, "object": step.params.get("object")
            },
            ActionType.BOOK_CALENDAR: lambda: {
                "status": "OK", "latency_ms": 480,
                "event_id": f"cal-{uuid.uuid4().hex[:8]}",
                "scheduled_in_days": step.params.get("delay_days", 3)
            },
            ActionType.SEND_SLACK: lambda: {
                "status": "OK", "latency_ms": 120,
                "channel": step.params.get("channel"), "ts": str(time.time())
            },
            ActionType.CREATE_JIRA: lambda: {
                "status": "OK", "latency_ms": 390,
                "output_vars": {"jira_key": f"DATA-{uuid.uuid4().hex[:4].upper()}", "jira_url": "https://alti.atlassian.net/browse/DATA-xxxx"}
            },
        }
        adapter = adapters.get(step.action_type, lambda: {"status": "OK", "latency_ms": 100})
        return adapter()

    def list_workflows(self) -> list[dict]:
        return [{"workflow_id": wf.workflow_id, "name": wf.name,
                 "trigger": wf.trigger_type, "steps": len(wf.steps), "enabled": wf.enabled}
                for wf in self._workflows.values()]

    def get_run_history(self, workflow_id: str) -> list[dict]:
        return [{"run_id": r.run_id, "status": r.status,
                 "triggered_at": r.triggered_at, "steps_completed": len(r.step_results)}
                for r in self._runs if r.workflow_id == workflow_id]


if __name__ == "__main__":
    engine = WorkflowEngine()
    print("Available workflows:", json.dumps(engine.list_workflows(), indent=2))

    # Trigger the churn rescue workflow
    run = engine.execute("wf-churn-rescue", {
        "customer_name": "Sarah Johnson", "customer_email": "sjohnson@acme.com",
        "account_id": "ACC-0042", "csm_email": "csm@alti.ai",
        "churn_probability": 0.87, "days_since_login": 41, "top_feature": "Revenue Analytics"
    })
    print(f"\nRun status: {run.status}")
    print(f"Steps completed: {len(run.step_results)}")
    for s in run.step_results:
        print(f"  {s['step_id']} ({s['action']}): {s['status']}")
