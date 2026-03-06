# services/global-compliance/global_compliance.py
"""
Epic 70: Global Regulatory Compliance Engine
Jurisdiction-aware privacy law enforcement across 15+ countries.
Auto-applies the correct rules based on where the data subject lives —
no per-tenant configuration, no manual compliance team involvement.

Laws covered:
  GDPR    (EU/EEA)    - 90-day breach notification, 30-day erasure
  LGPD    (Brazil)    - 15-day erasure, 72-hour breach notification
  PIPL    (China)     - Local storage required, 10-day erasure
  PDPA    (Thailand)  - 72-hour breach, 30-day erasure
  APPI    (Japan)     - 3-5 day breach, 2-week erasure
  POPIA   (South Africa) - 72-hour breach, 30-day erasure
  DPDP    (India)     - 72-hour breach, 7-day erasure
  PDPL    (Saudi Arabia) - 72-hour breach, 30-day erasure
  PIPEDA  (Canada)    - "as soon as feasible" breach, 30-day erasure
  CCPA    (California) - No erasure SLA, 45-day opt-out response
  KVKK    (Turkey)    - 72-hour breach, 30-day erasure
  PDPA_TH (Thailand)  - duplicate shorthand alias
  PIPA    (South Korea) - 24-hour breach, 10-day erasure
  nFADP   (Switzerland) - 72-hour breach, 30-day erasure
  PDPA_SG (Singapore) - 3-day breach, 10-day erasure
"""
import logging, json, uuid, time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class LegalBasis(str, Enum):
    CONSENT          = "CONSENT"
    CONTRACT         = "CONTRACT"
    LEGAL_OBLIGATION = "LEGAL_OBLIGATION"
    VITAL_INTEREST   = "VITAL_INTEREST"
    PUBLIC_TASK      = "PUBLIC_TASK"
    LEGITIMATE_INT   = "LEGITIMATE_INTERESTS"

class ConsentStatus(str, Enum):
    GRANTED   = "GRANTED"
    DENIED    = "DENIED"
    WITHDRAWN = "WITHDRAWN"
    PENDING   = "PENDING"

class TransferMechanism(str, Enum):
    ADEQUACY_DECISION  = "ADEQUACY_DECISION"
    SCC                = "STANDARD_CONTRACTUAL_CLAUSES"
    BCR                = "BINDING_CORPORATE_RULES"
    DEROGATION         = "DEROGATION"
    PROHIBITED         = "PROHIBITED"

@dataclass
class PrivacyLaw:
    law_id:                 str
    name:                   str
    jurisdiction:           str          # ISO 3166-1 alpha-2, or "EU"
    territory:              list[str]    # list of country codes covered
    regulator:              str
    erasure_sla_days:       int
    breach_notification_hrs:int          # max hours to notify regulator
    consent_required:       bool
    data_localization:      bool         # must data stay in-country?
    cross_border_mechanism: TransferMechanism
    penalty_max_pct_revenue:float        # max fine as % of global turnover
    penalty_max_fixed:      Optional[float]  # max fixed fine in EUR/USD
    requires_dpo:           bool
    children_age_threshold: int          # age below which parental consent needed
    right_to_erasure:       bool
    right_to_portability:   bool
    right_to_explanation:   bool         # AI decision explanations required

@dataclass
class ConsentRecord:
    consent_id:   str
    subject_id:   str
    tenant_id:    str
    law_id:       str
    purpose:      str
    legal_basis:  LegalBasis
    status:       ConsentStatus
    granted_at:   Optional[float]
    withdrawn_at: Optional[float] = None
    expiry:       Optional[float] = None
    evidence_uri: str = ""    # GCS URI of consent proof document

@dataclass
class BreachIncident:
    breach_id:         str
    tenant_id:         str
    detected_at:       float
    affected_subjects: int
    affected_countries:list[str]
    data_types:        list[str]  # "EMAIL", "SSN", "HEALTH", "FINANCIAL" etc
    notifications:     list[dict]  # one per applicable law
    status:            str        # "DETECTED" | "NOTIFIED" | "RESOLVED"

@dataclass
class ComplianceAssessment:
    subject_country:    str
    applicable_laws:    list[str]
    legal_basis:        LegalBasis
    consent_required:   bool
    consent_status:     Optional[ConsentStatus]
    processing_allowed: bool
    conditions:         list[str]  # conditions to be met
    max_retention_days: int
    erasure_sla_days:   int

class GlobalComplianceEngine:
    """
    Jurisdiction-aware compliance enforcement.
    Given a data subject's country, automatically determines:
    - Which privacy laws apply
    - Whether processing is lawful
    - What consent signals are needed
    - What rights the subject has
    - What breach notification timelines apply
    """
    def __init__(self):
        self.logger  = logging.getLogger("Global_Compliance")
        logging.basicConfig(level=logging.INFO)
        self._laws:    dict[str, PrivacyLaw]    = {}
        self._consent: dict[str, ConsentRecord] = {}   # consent_id → record
        self._breaches:list[BreachIncident]     = []
        self._build_law_registry()
        self.logger.info(f"⚖️  Global Compliance Engine: {len(self._laws)} privacy laws loaded.")

    def _build_law_registry(self):
        laws = [
            PrivacyLaw("GDPR","General Data Protection Regulation","EU",
                       ["AT","BE","BG","HR","CY","CZ","DK","EE","FI","FR","DE","GR",
                        "HU","IE","IT","LV","LT","LU","MT","NL","PL","PT","RO","SK",
                        "SI","ES","SE","IS","LI","NO"],
                       "European Data Protection Board",30,72,True,False,
                       TransferMechanism.ADEQUACY_DECISION,4.0,20_000_000,True,16,True,True,True),
            PrivacyLaw("LGPD","Lei Geral de Proteção de Dados","BR",["BR"],
                       "ANPD",15,72,True,False,TransferMechanism.SCC,2.0,50_000_000,True,12,True,True,False),
            PrivacyLaw("PIPL","Personal Information Protection Law","CN",["CN"],
                       "CAC / SAMR",10,24,True,True,TransferMechanism.PROHIBITED,
                       5.0,50_000_000,True,14,True,True,True),
            PrivacyLaw("PDPA","Personal Data Protection Act","TH",["TH"],
                       "PDPC Thailand",30,72,True,False,TransferMechanism.ADEQUACY_DECISION,
                       0,5_000_000,True,10,True,False,False),
            PrivacyLaw("APPI","Act on Protection of Personal Information","JP",["JP"],
                       "PPC Japan",14,72,True,False,TransferMechanism.ADEQUACY_DECISION,
                       0,100_000_000,False,18,True,True,False),
            PrivacyLaw("POPIA","Protection of Personal Information Act","ZA",["ZA"],
                       "ICLR South Africa",30,72,True,False,TransferMechanism.SCC,
                       0,10_000_000,True,18,True,False,False),
            PrivacyLaw("DPDP","Digital Personal Data Protection Act","IN",["IN"],
                       "Data Protection Board of India",7,72,True,False,
                       TransferMechanism.ADEQUACY_DECISION,0,250_000_000,False,18,True,False,False),
            PrivacyLaw("PDPL","Personal Data Protection Law","SA",["SA"],
                       "SDAIA",30,72,True,False,TransferMechanism.SCC,3.0,5_000_000,True,18,True,False,False),
            PrivacyLaw("PIPEDA","Personal Information Protection and Electronic Documents Act","CA",["CA"],
                       "OPC Canada",30,9999,True,False,TransferMechanism.ADEQUACY_DECISION,
                       0,100_000,False,13,True,True,False),
            PrivacyLaw("CCPA","California Consumer Privacy Act","US-CA",["US"],
                       "California AG",45,9999,False,False,TransferMechanism.DEROGATION,
                       0,7_500,False,16,True,True,False),
            PrivacyLaw("KVKK","Kişisel Verilerin Korunması Kanunu","TR",["TR"],
                       "KVKK Turkey",30,72,True,False,TransferMechanism.SCC,
                       0,1_000_000,True,18,True,False,False),
            PrivacyLaw("PIPA","Personal Information Protection Act","KR",["KR"],
                       "PIPC South Korea",10,24,True,False,TransferMechanism.ADEQUACY_DECISION,
                       3.0,50_000_000,True,14,True,True,False),
            PrivacyLaw("nFADP","new Federal Act on Data Protection","CH",["CH"],
                       "FDPIC Switzerland",30,72,True,False,TransferMechanism.SCC,
                       0,250_000,True,16,True,True,True),
            PrivacyLaw("PDPA_SG","Personal Data Protection Act","SG",["SG"],
                       "PDPC Singapore",10,72,True,False,TransferMechanism.ADEQUACY_DECISION,
                       0,1_000_000,False,13,True,True,False),
            PrivacyLaw("UK_GDPR","UK GDPR","GB",["GB"],
                       "ICO",30,72,True,False,TransferMechanism.SCC,4.0,17_500_000,True,13,True,True,True),
        ]
        for law in laws:
            self._laws[law.law_id] = law

    def assess(self, subject_country: str, purpose: str,
               legal_basis: LegalBasis = LegalBasis.LEGITIMATE_INT,
               consent_id: Optional[str] = None) -> ComplianceAssessment:
        """
        Given a data subject's country code, returns the full compliance
        assessment: which laws apply, whether processing is lawful, and
        what conditions must be met.
        """
        applicable = [law for law in self._laws.values()
                      if subject_country in law.territory]
        if not applicable:
            return ComplianceAssessment(
                subject_country=subject_country, applicable_laws=[],
                legal_basis=legal_basis, consent_required=False,
                consent_status=None, processing_allowed=True,
                conditions=["No specific privacy law identified for this jurisdiction — follow GDPR as best practice."],
                max_retention_days=365*7, erasure_sla_days=30
            )

        consent_required = any(law.consent_required for law in applicable)
        consent_status   = None
        if consent_required and consent_id:
            record = self._consent.get(consent_id)
            consent_status = record.status if record else ConsentStatus.PENDING

        processing_allowed = (not consent_required) or (
            legal_basis != LegalBasis.CONSENT or
            (consent_status == ConsentStatus.GRANTED)
        )

        conditions = []
        max_erasure = max(law.erasure_sla_days for law in applicable)
        min_erasure = min(law.erasure_sla_days for law in applicable)
        if any(law.data_localization for law in applicable):
            conditions.append(f"⚠️ Data localization required — data must remain in {subject_country}")
        if consent_required and consent_status != ConsentStatus.GRANTED:
            conditions.append("Obtain explicit consent before processing")
        if any(law.requires_dpo for law in applicable):
            conditions.append("Data Protection Officer required for this tenant")

        self.logger.info(f"⚖️  Assessment for {subject_country}: {[l.law_id for l in applicable]} — {'✅ ALLOWED' if processing_allowed else '❌ BLOCKED'}")
        return ComplianceAssessment(
            subject_country=subject_country,
            applicable_laws=[l.law_id for l in applicable],
            legal_basis=legal_basis, consent_required=consent_required,
            consent_status=consent_status, processing_allowed=processing_allowed,
            conditions=conditions, max_retention_days=365*7,
            erasure_sla_days=min_erasure
        )

    def record_consent(self, subject_id: str, tenant_id: str,
                       law_id: str, purpose: str,
                       legal_basis: LegalBasis,
                       status: ConsentStatus = ConsentStatus.GRANTED) -> ConsentRecord:
        record = ConsentRecord(
            consent_id=str(uuid.uuid4()), subject_id=subject_id,
            tenant_id=tenant_id, law_id=law_id, purpose=purpose,
            legal_basis=legal_basis, status=status,
            granted_at=time.time() if status == ConsentStatus.GRANTED else None,
            expiry=time.time() + 365*86400   # 1-year consent expiry
        )
        self._consent[record.consent_id] = record
        self.logger.info(f"✍️  Consent {status} for subject {subject_id[:8]}... law={law_id}")
        return record

    def withdraw_consent(self, consent_id: str) -> ConsentRecord:
        record = self._consent.get(consent_id)
        if not record: raise ValueError(f"Consent {consent_id} not found")
        record.status = ConsentStatus.WITHDRAWN
        record.withdrawn_at = time.time()
        self.logger.info(f"❌ Consent withdrawn: {consent_id[:12]}...")
        return record

    def handle_erasure_request(self, subject_id: str, subject_country: str) -> dict:
        """
        Right to Erasure ("Right to be Forgotten").
        Returns the SLA deadline based on the strictest applicable law.
        In production: dispatches Cloud Tasks job to purge subject's records
        from BigQuery, GCS, Firestore, and all cache layers.
        """
        assessment = self.assess(subject_country, "erasure")
        sla_days   = assessment.erasure_sla_days
        deadline   = time.time() + sla_days * 86400
        self.logger.info(f"🗑️  Erasure request: subject={subject_id[:8]}... country={subject_country} SLA={sla_days}d")
        return {
            "request_id":  str(uuid.uuid4()),
            "subject_id":  subject_id,
            "country":     subject_country,
            "applicable_laws": assessment.applicable_laws,
            "sla_days":    sla_days,
            "deadline":    time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(deadline)),
            "status":      "QUEUED",
            "action":      f"Purge all records for {subject_id} from BigQuery, GCS, and all caches by {time.strftime('%Y-%m-%d', time.gmtime(deadline))}"
        }

    def report_breach(self, tenant_id: str, affected_subjects: int,
                      affected_countries: list[str], data_types: list[str]) -> BreachIncident:
        """
        Breach detected. Auto-computes required notifications for each
        applicable jurisdiction with exact deadlines.
        """
        notifications = []
        for country in affected_countries:
            for law in self._laws.values():
                if country in law.territory:
                    deadline_ts = time.time() + law.breach_notification_hrs * 3600
                    notifications.append({
                        "law_id":    law.law_id,
                        "country":   country,
                        "regulator": law.regulator,
                        "deadline_hrs": law.breach_notification_hrs,
                        "deadline":  time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(deadline_ts)),
                        "status":    "PENDING"
                    })

        breach = BreachIncident(breach_id=str(uuid.uuid4()), tenant_id=tenant_id,
                                detected_at=time.time(), affected_subjects=affected_subjects,
                                affected_countries=affected_countries, data_types=data_types,
                                notifications=notifications, status="DETECTED")
        self._breaches.append(breach)
        self.logger.warning(f"🚨 Breach reported: {affected_subjects} subjects, {len(affected_countries)} countries, {len(notifications)} regulators to notify")
        return breach

    def compliance_dashboard(self) -> dict:
        active_consents   = sum(1 for c in self._consent.values() if c.status == ConsentStatus.GRANTED)
        withdrawn         = sum(1 for c in self._consent.values() if c.status == ConsentStatus.WITHDRAWN)
        open_breaches     = sum(1 for b in self._breaches if b.status != "RESOLVED")
        pending_notifs    = sum(len([n for n in b.notifications if n["status"]=="PENDING"]) for b in self._breaches)
        return {
            "laws_loaded":        len(self._laws),
            "active_consents":    active_consents,
            "withdrawn_consents": withdrawn,
            "open_breaches":      open_breaches,
            "pending_notifications": pending_notifs,
            "laws":               [{"id": l.law_id, "jurisdiction": l.jurisdiction,
                                    "erasure_sla": l.erasure_sla_days,
                                    "breach_notif_hrs": l.breach_notification_hrs,
                                    "data_localization": l.data_localization}
                                   for l in self._laws.values()],
        }


if __name__ == "__main__":
    engine = GlobalComplianceEngine()

    # Assess processing for subjects in different countries
    print("=== Compliance Assessments ===")
    for country in ["DE","JP","CN","BR","IN","SA","US","KR"]:
        assessment = engine.assess(country, "analytics_processing")
        laws = ",".join(assessment.applicable_laws)
        allowed = "✅" if assessment.processing_allowed else "❌"
        print(f"  {country}: [{laws}] {allowed} | erasure SLA: {assessment.erasure_sla_days}d | conditions: {len(assessment.conditions)}")
        for c in assessment.conditions:
            print(f"      ⚠️  {c}")

    # Consent lifecycle
    print("\n=== Consent Lifecycle ===")
    consent = engine.record_consent("user-42","tenant-bank","GDPR","marketing_analytics",LegalBasis.CONSENT)
    print(f"  Granted: {consent.consent_id[:12]}... expires {time.strftime('%Y-%m-%d', time.gmtime(consent.expiry))}")
    engine.withdraw_consent(consent.consent_id)
    print(f"  Withdrawn: {consent.status}")

    # Erasure request
    print("\n=== Erasure Request (PIPL - China, 10-day SLA) ===")
    req = engine.handle_erasure_request("user-cn-007","CN")
    print(f"  Deadline: {req['deadline']} (SLA={req['sla_days']}d)")

    # Breach scenario
    print("\n=== Breach Scenario: EU + JP + BR ===")
    breach = engine.report_breach("tenant-x", 48_200, ["DE","FR","JP","BR"], ["EMAIL","FINANCIAL"])
    print(f"  Breach ID: {breach.breach_id[:12]}")
    print(f"  Notifications required: {len(breach.notifications)}")
    for n in sorted(breach.notifications, key=lambda x: x["deadline_hrs"]):
        print(f"  → {n['law_id']:10} ({n['regulator']:35}) → notify by {n['deadline']} ({n['deadline_hrs']}h)")

    print("\n=== Dashboard ===")
    print(json.dumps(engine.compliance_dashboard(), indent=2))
