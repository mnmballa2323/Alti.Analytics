# services/briefings/briefing_composer.py
"""
Epic 54: Daily AI Intelligence Briefings
Every morning at 6am (Cloud Scheduler), Gemini assembles a personalized
intelligence briefing for each user — narrating overnight changes,
ranked alerts, and recommended actions across their configured domains.
Delivered via Email (SendGrid), Slack Bot, and Microsoft Teams.
"""
import logging, json, time, uuid
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class BriefingSection:
    domain:    str
    headline:  str
    body:      str
    change:    Optional[str]   # "+14% vs yesterday" or "-3 accounts at risk"
    action:    Optional[str]   # Recommended action
    severity:  str             # INFO | WARN | ALERT

@dataclass
class DailyBriefing:
    briefing_id:  str
    generated_at: float
    recipient:    str
    date_label:   str
    opening:      str
    sections:     list[BriefingSection]
    closing:      str
    top_action:   str
    domain_count: int

class BriefingComposer:
    def __init__(self):
        self.logger = logging.getLogger("Briefing_Composer")
        logging.basicConfig(level=logging.INFO)
        self.logger.info("📰 Daily AI Intelligence Briefing Composer initialized.")

    def compose(self, recipient: str, tenant_id: str,
                preferences: dict | None = None) -> DailyBriefing:
        """
        Composes a full personalized briefing.
        In production:
        1. Queries BigQuery for each preferred domain's overnight delta
        2. Calls Gemini to narrate each section in the user's preferred language/tone
        3. Ranks sections by severity before assembly
        4. Delivers via configured channels
        """
        self.logger.info(f"📝 Composing briefing for {recipient} ({tenant_id})...")
        prefs = preferences or {"domains": ["revenue", "churn", "compliance", "anomalies"], "tone": "executive"}

        sections = []

        if "churn" in prefs.get("domains", []):
            sections.append(BriefingSection(
                domain="Customer Health", severity="ALERT",
                headline="⚠️ Churn Risk Spike in Manufacturing Segment",
                body="8 enterprise accounts in the Manufacturing vertical crossed the 80% churn risk threshold overnight. Combined at-risk ARR: $4.2M. The Churn Rescue Workflow has been automatically dispatched for 6 of these accounts.",
                change="+14% vs 7-day average",
                action="Review the 2 remaining accounts not yet actioned → app.alti.ai/churn"
            ))

        if "revenue" in prefs.get("domains", []):
            sections.append(BriefingSection(
                domain="Revenue", severity="INFO",
                headline="📈 Q2 Revenue Forecast Revised Upward",
                body="Vertex AI revenue model revised the Q2 projection to $48.2M, a 6% increase from last week's projection. Primary driver: expansion revenue from the Enterprise cohort added in January. New customer acquisition pace is 12% ahead of plan.",
                change="+$2.7M vs prior forecast",
                action="Share updated forecast with CFO → app.alti.ai/forecast"
            ))

        if "compliance" in prefs.get("domains", []):
            sections.append(BriefingSection(
                domain="Compliance", severity="INFO",
                headline="🛡️ All 9 Compliance Frameworks Nominal",
                body="Overnight compliance scan completed with no critical findings. 1,224 of 1,227 controls passing. FedRAMP remediation is 82% complete — on track for ATO by April 15. 3 GDPR erasure requests were auto-processed within SLA.",
                change="No new violations (7d clean)",
                action=None
            ))

        if "anomalies" in prefs.get("domains", []):
            sections.append(BriefingSection(
                domain="Data Quality", severity="WARN",
                headline="🔴 Anomaly Detected: stripe_charges Null Rate",
                body="The stripe_charges table showed a 3.2% null rate in the `customer_id` field between 02:00–03:45 UTC — above the 0.5% baseline. Likely caused by a Stripe Radar rule change. Auto-remediation quarantined affected rows; backfill job is scheduled.",
                change="Null rate: 3.2% (baseline: 0.5%)",
                action="Confirm backfill completed → app.alti.ai/data-quality"
            ))

        # Sort: ALERT first, WARN second, INFO last
        severity_order = {"ALERT": 0, "WARN": 1, "INFO": 2}
        sections.sort(key=lambda s: severity_order.get(s.severity, 99))

        top_action = next((s.action for s in sections if s.action and s.severity == "ALERT"),
                          next((s.action for s in sections if s.action), "No urgent actions today."))

        briefing = DailyBriefing(
            briefing_id=str(uuid.uuid4()),
            generated_at=time.time(),
            recipient=recipient,
            date_label=time.strftime("%A, %B %-d, %Y", time.gmtime()),
            opening=f"Good morning. Here's your Alti Intelligence Briefing for {time.strftime('%B %-d')}. Gemini monitored {len(sections)} domains overnight and surfaced {sum(1 for s in sections if s.severity in ['ALERT','WARN'])} items requiring attention.",
            sections=sections,
            closing="That's your full briefing. The platform is operating autonomously — alerts will reach you in real-time. See you tomorrow.",
            top_action=top_action,
            domain_count=len(sections)
        )
        self.logger.info(f"✅ Briefing composed: {len(sections)} sections, top severity={sections[0].severity if sections else 'N/A'}")
        return briefing

    def format_email_html(self, briefing: DailyBriefing) -> str:
        """Renders the briefing as a polished dark-mode HTML email."""
        sections_html = ""
        for s in briefing.sections:
            color = "#ef4444" if s.severity == "ALERT" else "#f59e0b" if s.severity == "WARN" else "#22c55e"
            sections_html += f"""
            <div style="border-left:3px solid {color};padding:12px 16px;margin:16px 0;background:#1e293b;border-radius:0 8px 8px 0">
              <div style="font-weight:700;color:#f1f5f9;margin-bottom:6px">{s.headline}</div>
              <div style="color:#94a3b8;font-size:14px;line-height:1.6">{s.body}</div>
              {"<div style='color:#60a5fa;font-size:13px;margin-top:8px'>→ " + s.change + "</div>" if s.change else ""}
              {"<div style='margin-top:10px'><a href='#' style='background:#3b82f6;color:white;padding:6px 14px;border-radius:6px;text-decoration:none;font-size:13px'>" + s.action + "</a></div>" if s.action else ""}
            </div>"""
        return f"""<!DOCTYPE html><html>
<body style="background:#0f172a;color:#f1f5f9;font-family:Inter,system-ui,sans-serif;padding:24px;max-width:680px;margin:0 auto">
  <div style="margin-bottom:24px">
    <div style="font-size:12px;color:#4b5563;text-transform:uppercase;letter-spacing:.1em">Alti Intelligence Briefing</div>
    <div style="font-size:24px;font-weight:800;margin-top:4px">{briefing.date_label}</div>
  </div>
  <div style="color:#94a3b8;margin-bottom:24px;line-height:1.6">{briefing.opening}</div>
  {sections_html}
  <div style="margin-top:24px;padding:16px;background:#1e3a5f;border-radius:8px;font-size:14px">
    <strong style="color:#60a5fa">🎯 Top Action:</strong> <span style="color:#f1f5f9">{briefing.top_action}</span>
  </div>
  <div style="margin-top:24px;color:#4b5563;font-size:13px">{briefing.closing}</div>
</body></html>"""

    def format_slack_blocks(self, briefing: DailyBriefing) -> list[dict]:
        """Formats the briefing as Slack Block Kit JSON for Slack Bot delivery."""
        blocks: list[dict] = [
            {"type": "header", "text": {"type": "plain_text", "text": f"📊 Alti Briefing — {briefing.date_label}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": briefing.opening}},
            {"type": "divider"},
        ]
        for s in briefing.sections:
            emoji = "🔴" if s.severity == "ALERT" else "🟡" if s.severity == "WARN" else "🟢"
            text = f"{emoji} *{s.headline}*\n{s.body}"
            if s.change: text += f"\n_Change: {s.change}_"
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})
            if s.action:
                blocks.append({"type": "actions", "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": s.action[:30]},
                     "style": "primary" if s.severity == "ALERT" else "default", "value": "action"}
                ]})
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"_{briefing.closing}_"}]})
        return blocks

    def deliver(self, briefing: DailyBriefing, channels: list[str]) -> dict:
        """
        Dispatches the briefing to all requested channels.
        channels: ["email", "slack", "teams"]
        In production: SendGrid (email), Slack Bolt (slack), MS Graph API (teams)
        """
        results = {}
        if "email" in channels:
            html = self.format_email_html(briefing)
            results["email"] = {"status": "DELIVERED", "to": briefing.recipient, "html_bytes": len(html)}
            self.logger.info(f"📧 Email delivered to {briefing.recipient}")
        if "slack" in channels:
            blocks = self.format_slack_blocks(briefing)
            results["slack"] = {"status": "DELIVERED", "blocks_count": len(blocks)}
            self.logger.info("💬 Slack briefing delivered.")
        if "teams" in channels:
            results["teams"] = {"status": "DELIVERED", "adaptive_card": "sent"}
            self.logger.info("🟣 Teams adaptive card delivered.")
        return {"briefing_id": briefing.briefing_id, "delivered_to": results}


if __name__ == "__main__":
    composer = BriefingComposer()
    briefing = composer.compose("ceo@acme.com", "ten-acme-corp",
                                preferences={"domains": ["churn","revenue","compliance","anomalies"]})
    print(f"Briefing: {briefing.date_label}")
    print(f"Sections: {briefing.domain_count} | Top action: {briefing.top_action}\n")
    for s in briefing.sections:
        print(f"[{s.severity}] {s.headline}")
    result = composer.deliver(briefing, ["email", "slack", "teams"])
    print(json.dumps(result, indent=2))
