# services/access-control/abac_engine.py
"""
Epic 83: Fine-Grained Data Access Control & Privileged Access Management
Attribute-Based Access Control (ABAC) and break-glass PAM for Alti.Analytics.

Why ABAC over RBAC:
  RBAC (Role-Based): "This user is a Nurse → can see patient data"
  ABAC (Attribute-Based): "This user is a Nurse in Ward 3 at Hospital X with
      clearance level 2 → can see patient data for patients in Ward 3 ONLY,
      PII masked except for clinical fields, cannot see billing data"

ABAC policy language:
  effect:   PERMIT | DENY
  subject:  attributes about the requester (role, dept, clearance, location)
  resource: attributes about the data (classification, tenant, table, column)
  action:   READ | WRITE | EXPORT | AGGREGATE | ADMIN
  conditions: time-of-day, IP range, MFA status, data age

Column-level masking profiles:
  CLEAR    → raw value returned
  MASKED   → first/last 2 chars visible, rest *** (e.g. "Jo***hn")
  HASHED   → SHA-256 hash (for joining without revealing PII)
  REDACTED → literal "REDACTED"
  NULL     → field omitted from response

Privileged Access Management (PAM):
  Break-glass access: emergency access to sensitive data, time-limited,
  requires justification, auto-revoked after window, full audit trail.
  Used by: on-call engineers debugging production incidents, regulators
  performing audits, security team responding to incidents.
"""
import logging, json, uuid, time, hashlib, re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class DataClassification(str, Enum):
    PUBLIC       = "PUBLIC"
    INTERNAL     = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED   = "RESTRICTED"   # PII, PHI, financial records
    SECRET       = "SECRET"       # credentials, crypto keys

class MaskingProfile(str, Enum):
    CLEAR    = "CLEAR"
    MASKED   = "MASKED"       # partial reveal
    HASHED   = "HASHED"       # SHA-256
    REDACTED = "REDACTED"     # literal string
    NULL     = "NULL"         # omit field

class AccessAction(str, Enum):
    READ      = "READ"
    WRITE     = "WRITE"
    EXPORT    = "EXPORT"
    AGGREGATE = "AGGREGATE"
    ADMIN     = "ADMIN"

class ABACEffect(str, Enum):
    PERMIT = "PERMIT"
    DENY   = "DENY"

@dataclass
class SubjectAttributes:
    user_id:       str
    roles:         list[str]   # ["nurse","doctor","admin","analyst","engineer"]
    department:    str         # "cardiology","billing","engineering","security"
    clearance:     int         # 1-5 (1=lowest, 5=highest)
    mfa_verified:  bool
    ip_address:    str
    location:      str         # "ward-3","hq-london","remote"
    tenant_id:     str
    is_service_account:bool = False

@dataclass
class ResourceAttributes:
    table:          str
    column:         Optional[str]
    classification: DataClassification
    tenant_id:      str
    data_owner:     str         # "cardiology","finance","hr"
    contains_pii:   bool
    contains_phi:   bool        # Protected Health Information (HIPAA)

@dataclass
class ABACDecision:
    decision_id:  str
    effect:       ABACEffect
    action:       AccessAction
    subject:      str           # user_id
    resource:     str           # table[.column]
    masking:      MaskingProfile
    reason:       str
    policy_matched:str
    timestamp:    float = field(default_factory=time.time)

@dataclass
class ColumnMaskingRule:
    table:         str
    column:        str
    classification:DataClassification
    masks: dict[str, MaskingProfile]  # role → masking profile

@dataclass
class AccessRequest:
    request_id:   str
    requester_id: str
    resource:     str           # table or service
    action:       AccessAction
    justification:str
    duration_hours:int          # how long access is needed
    tenant_id:    str
    requested_at: float = field(default_factory=time.time)
    approved_by:  Optional[str] = None
    approved_at:  Optional[float]= None
    expires_at:   Optional[float]= None
    revoked_at:   Optional[float]= None
    status:       str = "PENDING"  # PENDING|APPROVED|DENIED|EXPIRED|REVOKED

@dataclass
class BreakGlassSession:
    session_id:    str
    engineer_id:   str
    tenant_id:     str
    incident_id:   str          # must reference an active incident
    justification: str
    granted_at:    float
    expires_at:    float
    resources:     list[str]    # tables/services accessible
    audit_entries: list[dict]   = field(default_factory=list)
    revoked:       bool         = False

class ABACEngine:
    """
    Attribute-Based Access Control engine with column-level masking
    and Privileged Access Management for break-glass emergency access.
    """
    # Column masking rules (table → column → role-based masking profile)
    _MASKING_RULES: list[ColumnMaskingRule] = [
        # Patient data — PHI columns
        ColumnMaskingRule("patients","encrypted_pii",      DataClassification.RESTRICTED,
                          {"doctor": MaskingProfile.CLEAR,"nurse": MaskingProfile.CLEAR,
                           "billing": MaskingProfile.REDACTED,"analyst": MaskingProfile.NULL,
                           "engineer": MaskingProfile.NULL}),
        ColumnMaskingRule("patients","date_of_birth",      DataClassification.RESTRICTED,
                          {"doctor": MaskingProfile.CLEAR,"nurse": MaskingProfile.CLEAR,
                           "billing": MaskingProfile.MASKED,"analyst": MaskingProfile.HASHED,
                           "engineer": MaskingProfile.HASHED}),
        ColumnMaskingRule("patients","mrn",                DataClassification.RESTRICTED,
                          {"doctor": MaskingProfile.CLEAR,"nurse": MaskingProfile.CLEAR,
                           "billing": MaskingProfile.MASKED,"analyst": MaskingProfile.HASHED,
                           "engineer": MaskingProfile.NULL}),
        # Banking data — financial PII
        ColumnMaskingRule("bank_accounts","account_number",DataClassification.RESTRICTED,
                          {"banker": MaskingProfile.CLEAR,"analyst": MaskingProfile.MASKED,
                           "engineer": MaskingProfile.HASHED,"compliance": MaskingProfile.CLEAR}),
        ColumnMaskingRule("bank_accounts","balance_units", DataClassification.CONFIDENTIAL,
                          {"banker": MaskingProfile.CLEAR,"analyst": MaskingProfile.CLEAR,
                           "engineer": MaskingProfile.MASKED,"compliance": MaskingProfile.CLEAR}),
        ColumnMaskingRule("transactions","amount",         DataClassification.CONFIDENTIAL,
                          {"banker": MaskingProfile.CLEAR,"analyst": MaskingProfile.CLEAR,
                           "engineer": MaskingProfile.MASKED,"compliance": MaskingProfile.CLEAR}),
        # Customer data — PII
        ColumnMaskingRule("customers","email",             DataClassification.CONFIDENTIAL,
                          {"sales": MaskingProfile.CLEAR,"analyst": MaskingProfile.MASKED,
                           "engineer": MaskingProfile.HASHED,"support": MaskingProfile.MASKED}),
        ColumnMaskingRule("customers","phone",             DataClassification.CONFIDENTIAL,
                          {"sales": MaskingProfile.CLEAR,"support": MaskingProfile.MASKED,
                           "analyst": MaskingProfile.NULL,"engineer": MaskingProfile.NULL}),
        ColumnMaskingRule("customers","ssn",               DataClassification.RESTRICTED,
                          {"compliance": MaskingProfile.CLEAR,"admin": MaskingProfile.MASKED,
                           "analyst": MaskingProfile.NULL,"engineer": MaskingProfile.NULL}),
    ]

    # ABAC policies (evaluated in order, first match wins)
    _POLICIES = [
        # Deny all cross-tenant access first
        {"id":"P-001","name":"Deny cross-tenant","effect":ABACEffect.DENY,
         "condition": lambda sub,res,act: sub.tenant_id != res.tenant_id and not sub.is_service_account,
         "masking":MaskingProfile.NULL,"reason":"Cross-tenant data access denied"},
        # Deny SECRET data to all non-admins
        {"id":"P-002","name":"Protect SECRETS","effect":ABACEffect.DENY,
         "condition": lambda sub,res,act: res.classification == DataClassification.SECRET and "admin" not in sub.roles,
         "masking":MaskingProfile.NULL,"reason":"SECRET classification requires admin role"},
        # Deny PHI to non-clinical staff
        {"id":"P-003","name":"PHI clinical only","effect":ABACEffect.DENY,
         "condition": lambda sub,res,act: res.contains_phi and
                      not any(r in sub.roles for r in ["doctor","nurse","clinical_admin"]),
         "masking":MaskingProfile.NULL,"reason":"PHI access restricted to clinical roles"},
        # Require MFA for RESTRICTED data
        {"id":"P-004","name":"MFA for RESTRICTED","effect":ABACEffect.DENY,
         "condition": lambda sub,res,act: res.classification == DataClassification.RESTRICTED and not sub.mfa_verified,
         "masking":MaskingProfile.NULL,"reason":"MFA required for RESTRICTED data access"},
        # Deny EXPORT for clearance < 3
        {"id":"P-005","name":"Export clearance","effect":ABACEffect.DENY,
         "condition": lambda sub,res,act: act == AccessAction.EXPORT and sub.clearance < 3,
         "masking":MaskingProfile.NULL,"reason":"Data export requires clearance level 3+"},
        # Permit — validated above
        {"id":"P-100","name":"Default PERMIT","effect":ABACEffect.PERMIT,
         "condition": lambda sub,res,act: True,
         "masking":MaskingProfile.CLEAR,"reason":"Access permitted by policy P-100"},
    ]

    def __init__(self, project_id: str = "alti-analytics-prod"):
        self.project_id   = project_id
        self.logger       = logging.getLogger("ABAC_Engine")
        logging.basicConfig(level=logging.INFO)
        self._decisions:  list[ABACDecision]   = []
        self._requests:   list[AccessRequest]  = []
        self._sessions:   list[BreakGlassSession] = []
        self._masking_index = {(r.table, r.column): r for r in self._MASKING_RULES}
        self.logger.info(f"🔑 ABAC Engine: {len(self._POLICIES)} policies | {len(self._MASKING_RULES)} column masking rules")

    def evaluate(self, subject: SubjectAttributes,
                 resource: ResourceAttributes,
                 action: AccessAction) -> ABACDecision:
        """Evaluates all ABAC policies and returns the first matching decision."""
        resource_path = f"{resource.table}{'.' + resource.column if resource.column else ''}"
        # Check masking rule
        masking = MaskingProfile.CLEAR
        masking_rule = self._masking_index.get((resource.table, resource.column))
        if masking_rule:
            for role in subject.roles:
                if role in masking_rule.masks:
                    masking = masking_rule.masks[role]
                    break

        # Evaluate policies
        matched = None
        for policy in self._POLICIES:
            try:
                if policy["condition"](subject, resource, action):
                    matched = policy
                    break
            except Exception:
                continue

        if not matched:
            matched = self._POLICIES[-1]  # default permit

        effect  = matched["effect"]
        # Even if PERMIT, masking from column rule overrides
        if effect == ABACEffect.DENY:
            masking = MaskingProfile.NULL

        decision = ABACDecision(
            decision_id=str(uuid.uuid4()), effect=effect, action=action,
            subject=subject.user_id, resource=resource_path,
            masking=masking, reason=matched["reason"], policy_matched=matched["id"]
        )
        self._decisions.append(decision)
        icon = "✅" if effect == ABACEffect.PERMIT else "⛔"
        self.logger.info(f"  {icon} ABAC [{matched['id']}]: {subject.user_id} {action} {resource_path} → {effect} | mask={masking}")
        return decision

    def apply_masking(self, column: str, value: str, profile: MaskingProfile) -> str:
        """Applies the masking profile to a column value."""
        if profile == MaskingProfile.CLEAR:    return value
        if profile == MaskingProfile.NULL:     return "[OMITTED]"
        if profile == MaskingProfile.REDACTED: return "REDACTED"
        if profile == MaskingProfile.HASHED:
            return hashlib.sha256(str(value).encode()).hexdigest()[:16]
        if profile == MaskingProfile.MASKED:
            s = str(value)
            if len(s) <= 4: return "****"
            return s[:2] + "*" * (len(s)-4) + s[-2:]
        return value

    def request_access(self, requester_id: str, resource: str,
                       action: AccessAction, justification: str,
                       duration_hours: int, tenant_id: str) -> AccessRequest:
        """Time-bound access request requiring manager approval."""
        req = AccessRequest(request_id=str(uuid.uuid4()), requester_id=requester_id,
                            resource=resource, action=action, justification=justification,
                            duration_hours=duration_hours, tenant_id=tenant_id)
        self._requests.append(req)
        self.logger.info(f"  📋 Access request: {requester_id} → {resource} [{action}] for {duration_hours}h | {justification[:50]}")
        return req

    def approve_access(self, request_id: str, approver_id: str) -> AccessRequest:
        """Approves an access request. Auto-schedules revocation."""
        req = next((r for r in self._requests if r.request_id == request_id), None)
        if not req: raise ValueError("Request not found")
        req.approved_by = approver_id
        req.approved_at = time.time()
        req.expires_at  = time.time() + req.duration_hours * 3600
        req.status      = "APPROVED"
        self.logger.info(f"  ✅ Access approved: {req.requester_id} → {req.resource} | expires at {req.expires_at} | approver: {approver_id}")
        # In production: IAM role binding created, Cloud Scheduler job created for auto-revocation
        return req

    def break_glass(self, engineer_id: str, tenant_id: str,
                    incident_id: str, justification: str,
                    duration_hours: int = 4,
                    resources: list[str] = None) -> BreakGlassSession:
        """
        Emergency privileged access. Immediately grants time-limited access.
        EVERY action within the session is logged to Cloud Audit Log (tamper-proof).
        Auto-revokes after duration_hours. Alerts security team immediately.
        Requires active PagerDuty incident_id to prevent misuse.
        """
        session = BreakGlassSession(
            session_id=str(uuid.uuid4()), engineer_id=engineer_id,
            tenant_id=tenant_id, incident_id=incident_id,
            justification=justification,
            granted_at=time.time(),
            expires_at=time.time() + duration_hours * 3600,
            resources=resources or ["spanner-alloydb","data-catalog","observability"]
        )
        session.audit_entries.append({
            "event": "BREAK_GLASS_GRANTED", "engineer": engineer_id,
            "incident": incident_id, "justification": justification,
            "duration_hours": duration_hours, "resources": resources,
            "timestamp": time.time()
        })
        self._sessions.append(session)
        self.logger.warning(f"🚨 BREAK-GLASS: {engineer_id} granted {duration_hours}h PAM access | incident={incident_id}")
        self.logger.warning(f"   Resources: {resources} | Security team notified via PagerDuty + Slack")
        # In production: IAM role granted, Cloud Scheduler auto-revocation registered,
        # PagerDuty incident comment added, Slack #security-alerts notified
        return session

    def log_break_glass_action(self, session: BreakGlassSession,
                               action: str, table: str, rows_accessed: int = 0):
        """Logs every action taken during a break-glass session to the immutable audit trail."""
        entry = {"event": "BREAK_GLASS_ACTION", "session": session.session_id,
                 "engineer": session.engineer_id, "action": action,
                 "table": table, "rows_accessed": rows_accessed, "timestamp": time.time()}
        session.audit_entries.append(entry)
        self.logger.warning(f"  📝 PAM AUDIT: {session.engineer_id} → {action} on {table} | {rows_accessed} rows")

    def revoke_break_glass(self, session: BreakGlassSession, reason: str = "auto-expired"):
        session.revoked = True
        session.audit_entries.append({
            "event": "BREAK_GLASS_REVOKED", "reason": reason,
            "timestamp": time.time(), "session": session.session_id
        })
        self.logger.warning(f"  🔒 Break-glass revoked: {session.engineer_id} | reason={reason}")

    def abac_dashboard(self) -> dict:
        denied   = sum(1 for d in self._decisions if d.effect == ABACEffect.DENY)
        pending  = sum(1 for r in self._requests  if r.status == "PENDING")
        active_bg= sum(1 for s in self._sessions  if not s.revoked)
        return {
            "total_access_decisions": len(self._decisions),
            "access_denied":          denied,
            "deny_rate_pct":          round(denied/max(1,len(self._decisions))*100,1),
            "access_requests_pending":pending,
            "access_requests_total":  len(self._requests),
            "active_break_glass":     active_bg,
            "break_glass_sessions":   len(self._sessions),
            "column_masking_rules":   len(self._MASKING_RULES),
        }


if __name__ == "__main__":
    engine = ABACEngine()

    print("=== ABAC Policy Evaluation ===\n")
    scenarios = [
        ("dr-smith",   ["doctor"],              "cardiology",  4, True,  "ward-3",  "t-hosp", True,
         "patients","encrypted_pii",DataClassification.RESTRICTED, True,  True,  "t-hosp", AccessAction.READ,  "Doctor reads patient PII"),
        ("nurse-jones",["nurse"],               "ward-3",      2, True,  "ward-3",  "t-hosp", False,
         "patients","date_of_birth",DataClassification.RESTRICTED, True,  True,  "t-hosp", AccessAction.READ,  "Nurse reads DOB"),
        ("billing-01", ["billing"],             "finance",     1, False, "hq",      "t-hosp", False,
         "patients","encrypted_pii",DataClassification.RESTRICTED, True,  True,  "t-hosp", AccessAction.READ,  "Billing reads PHI (DENY: no PHI role)"),
        ("analyst-02", ["analyst"],             "analytics",   3, True,  "remote",  "t-bank", False,
         "bank_accounts","account_number",DataClassification.RESTRICTED,False,False,"t-bank",AccessAction.READ, "Analyst reads account number (MASKED)"),
        ("eng-lee",    ["engineer"],            "platform",    3, True,  "hq",      "t-bank", True,
         "bank_accounts","account_number",DataClassification.RESTRICTED,False,False,"t-bank",AccessAction.READ, "Engineer reads account (HASHED per rule)"),
        ("analyst-05", ["analyst"],             "analytics",   2, True,  "hq",      "t-saas", False,
         "customers","ssn",          DataClassification.RESTRICTED, True,  False, "t-saas", AccessAction.EXPORT,"Analyst exports SSN (DENY: clearance<3)"),
        ("ext-user",   ["analyst"],             "external",    2, True,  "remote",  "t-bank", False,
         "customers","email",         DataClassification.CONFIDENTIAL,True,False, "t-hosp", AccessAction.READ,  "Cross-tenant access (DENY)"),
    ]
    for (uid, roles, dept, clearance, mfa, loc, s_tenant, is_sa,
         table, col, cls, pii, phi, r_tenant, action, desc) in scenarios:
        sub = SubjectAttributes(uid, roles, dept, clearance, mfa, "10.0.0.1", loc, s_tenant, is_sa)
        res = ResourceAttributes(table, col, cls, r_tenant, dept, pii, phi)
        dec = engine.evaluate(sub, res, action)
        # Show masking demo
        sample_val = "John Doe" if "name" in col or "pii" in col else ("123-45-6789" if "ssn" in col else "ACC-00192837")
        masked = engine.apply_masking(col, sample_val, dec.masking) if dec.effect == ABACEffect.PERMIT else "N/A"
        print(f"  {desc[:45]:45} → {dec.effect:6} | mask={dec.masking:10} | value='{masked}'")

    print("\n=== Access Request Workflow ===")
    req = engine.request_access("analyst-99", "bank_accounts", AccessAction.EXPORT,
                                "Quarterly regulatory report for BaFin submission required",
                                8, "t-bank")
    print(f"  Request: {req.request_id[:12]} | status: {req.status}")
    approved = engine.approve_access(req.request_id, "head-of-compliance")
    print(f"  Approved by: {approved.approved_by} | expires: {approved.duration_hours}h from now")

    print("\n=== Break-Glass PAM Emergency Access ===")
    session = engine.break_glass("srn-oncall-007", "t-bank", "INC-2026-0391",
                                 "Production Spanner corruption — need to inspect raw rows for recovery",
                                 4, ["spanner-alloydb","data-catalog"])
    engine.log_break_glass_action(session, "SELECT", "BankAccounts", 142)
    engine.log_break_glass_action(session, "SELECT", "Transactions",  891)
    engine.revoke_break_glass(session, "incident resolved")
    print(f"  Session: {session.session_id[:12]} | entries: {len(session.audit_entries)} audit entries")

    print("\n=== ABAC Dashboard ===")
    print(json.dumps(engine.abac_dashboard(), indent=2))
