# services/customer-360/customer_360.py
"""
Epic 88: Customer 360 & Identity Resolution CDP
The "who is this customer" layer — resolving a single person across
every data source the tenant has connected.

Problem:
  CRM has "John Smith, john.smith@meridian.com, Acct #AA-10928"
  Web analytics has "jsmith-ext, IP 192.168.1.1, device: iPhone 14"
  Payments has "J. Smith, card ending 4291, billing: 42 Park Ave, Boston"
  Support has "johnsmith@meridian.com, 617-555-0192, 14 open tickets"
  Are these the same person? 98.7% confidence: YES.

Solution: Probabilistic Identity Resolution using:
  - Deterministic matching: exact email, phone, customer_id
  - Probabilistic matching: name similarity + location + device fingerprint
  - Confidence scoring: each signal weighted by reliability
  - Identity graph: resolved identities stored as a Spanner graph

Customer 360 profile:
  One unified record per resolved identity, aggregating:
  - CRM: account tier, ARR, CSM, health score
  - Behavioral: DAU/WAU, feature adoption, NPS, last activity
  - Financial: invoice history, payment terms, overdue amounts
  - Clinical (healthcare): patient risk scores, recent visits
  - Support: open tickets, CSAT, resolution time
  - Journey: current journey stage, next best action

Behavioral cohort analysis:
  "Users who activated Feature X in their first 7 days
   are 3.2× more likely to reach $100k ARR by month 12"
  → Build automated playbooks for the winning journey pattern

Customer Journey Intelligence:
  Maps the exact event sequence from signup to expansion vs churn
  Identifies "golden path" and off-ramp signals
  Triggers autonomous workflows at the right journey moment
"""
import logging, json, uuid, time, random, math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class MatchSignal(str, Enum):
    EMAIL_EXACT     = "EMAIL_EXACT"
    PHONE_EXACT     = "PHONE_EXACT"
    CUSTOMER_ID     = "CUSTOMER_ID"
    NAME_FUZZY      = "NAME_FUZZY"
    ADDRESS_PARTIAL = "ADDRESS_PARTIAL"
    DEVICE_FINGERPRINT="DEVICE_FINGERPRINT"
    IP_CLUSTER      = "IP_CLUSTER"
    PAYMENT_CARD    = "PAYMENT_CARD"

class JourneyStage(str, Enum):
    SIGNUP         = "SIGNUP"
    ONBOARDING     = "ONBOARDING"
    ACTIVATION     = "ACTIVATION"          # first value moment
    ADOPTION       = "ADOPTION"            # regular product use
    EXPANSION      = "EXPANSION"           # upsell/cross-sell
    ADVOCACY       = "ADVOCACY"            # NPS 9-10, referrals
    AT_RISK        = "AT_RISK"             # churn signals detected
    CHURNED        = "CHURNED"

class NextBestAction(str, Enum):
    SCHEDULE_QBR       = "SCHEDULE_QBR"
    SEND_CASE_STUDY    = "SEND_CASE_STUDY"
    TRIGGER_EXPANSION  = "TRIGGER_EXPANSION"
    ASSIGN_CSM         = "ASSIGN_CSM"
    OFFER_TRAINING     = "OFFER_TRAINING"
    EXECUTIVE_SPONSOR  = "EXECUTIVE_SPONSOR"
    CHURN_RESCUE       = "CHURN_RESCUE"
    RENEWAL_OUTREACH   = "RENEWAL_OUTREACH"

@dataclass
class IdentitySignal:
    signal_type:  MatchSignal
    source:       str            # "crm" | "web" | "payments" | "support"
    value:        str            # the matched value
    confidence:   float          # 0-1 signal reliability

@dataclass
class ResolvedIdentity:
    identity_id:   str
    tenant_id:     str
    canonical_name:str
    canonical_email:str
    confidence:    float          # overall resolution confidence 0-1
    signals:       list[IdentitySignal]
    source_records:dict[str,str]  # source → source_record_id
    created_at:    float = field(default_factory=time.time)
    updated_at:    float = field(default_factory=time.time)

@dataclass
class Customer360Profile:
    identity_id:      str
    tenant_id:        str
    # CRM
    account_name:     str
    account_tier:     str         # "ENTERPRISE"|"GROWTH"|"STARTER"
    arr:              float        # USD
    csm_name:         str
    health_score:     float        # 0-100
    # Behavioral
    dau_streak:       int          # consecutive days active
    feature_adoption: float        # % of features used (0-1)
    last_activity:    float
    nps_score:        Optional[int]
    # Financial
    invoice_overdue:  bool
    days_overdue:     int
    ltv:              float
    # Support
    open_tickets:     int
    csat_score:       float        # 0-5
    avg_resolution_days:float
    # AI-derived
    churn_probability:float        # 0-1
    expansion_probability:float   # 0-1
    journey_stage:    JourneyStage
    next_best_action: NextBestAction
    predicted_arr_90d:float
    # Journey events
    journey_events:   list[dict]  = field(default_factory=list)

@dataclass
class BehavioralCohort:
    cohort_id:          str
    name:               str
    definition:         str           # human description
    filter_sql:         str           # BigQuery SQL filter
    tenant_id:          str
    members:            int           # count of users matching
    outcome_metric:     str           # what we're measuring
    outcome_value:      float         # cohort outcome
    baseline_value:     float         # overall population outcome
    lift_factor:        float         # outcome / baseline
    p_value:            float         # statistical significance
    significant:        bool
    recommended_action: str

@dataclass
class JourneyPath:
    path_id:       str
    name:          str               # "Golden Path to Expansion"
    event_sequence:list[str]         # ordered event types
    avg_duration_days:int
    member_count:  int
    outcome:       str               # "EXPANSION"|"CHURN"|"STABLE"
    outcome_rate:  float             # % achieving this outcome
    median_arr_impact:float          # $ change in ARR

class CustomerCDP:
    """
    Customer Data Platform: identity resolution, 360-degree profiles,
    behavioral cohort analysis, and customer journey intelligence.
    """

    # Signal reliability weights (deterministic > probabilistic)
    _SIGNAL_WEIGHTS = {
        MatchSignal.EMAIL_EXACT:      1.00,
        MatchSignal.PHONE_EXACT:      0.98,
        MatchSignal.CUSTOMER_ID:      1.00,
        MatchSignal.PAYMENT_CARD:     0.95,
        MatchSignal.NAME_FUZZY:       0.65,
        MatchSignal.ADDRESS_PARTIAL:  0.70,
        MatchSignal.DEVICE_FINGERPRINT:0.80,
        MatchSignal.IP_CLUSTER:       0.45,
    }

    # Journey stage transition rules (what signals trigger each stage)
    _STAGE_RULES = {
        JourneyStage.ACTIVATION:  lambda p: p.dau_streak >= 7 and p.feature_adoption >= 0.30,
        JourneyStage.ADOPTION:    lambda p: p.dau_streak >= 30 and p.feature_adoption >= 0.50,
        JourneyStage.EXPANSION:   lambda p: p.expansion_probability >= 0.70,
        JourneyStage.ADVOCACY:    lambda p: (p.nps_score or 0) >= 9 and p.churn_probability < 0.10,
        JourneyStage.AT_RISK:     lambda p: p.churn_probability >= 0.60 or p.health_score < 40,
        JourneyStage.CHURNED:     lambda p: p.churn_probability >= 0.90,
    }

    # Next best action decision matrix
    _NBA_RULES = [
        (lambda p: p.journey_stage == JourneyStage.CHURNED,           NextBestAction.CHURN_RESCUE),
        (lambda p: p.journey_stage == JourneyStage.AT_RISK,            NextBestAction.EXECUTIVE_SPONSOR),
        (lambda p: p.invoice_overdue and p.days_overdue > 30,           NextBestAction.ASSIGN_CSM),
        (lambda p: p.journey_stage == JourneyStage.EXPANSION,           NextBestAction.TRIGGER_EXPANSION),
        (lambda p: p.feature_adoption < 0.30 and p.dau_streak < 14,    NextBestAction.OFFER_TRAINING),
        (lambda p: (p.nps_score or 0) >= 9,                             NextBestAction.SEND_CASE_STUDY),
        (lambda p: p.health_score > 75 and p.arr > 100_000,             NextBestAction.SCHEDULE_QBR),
        (lambda p: True,                                                 NextBestAction.RENEWAL_OUTREACH),
    ]

    def __init__(self, project_id: str = "alti-analytics-prod"):
        self.project_id  = project_id
        self.logger      = logging.getLogger("CustomerCDP")
        logging.basicConfig(level=logging.INFO)
        self._identities: list[ResolvedIdentity]   = []
        self._profiles:   dict[str, Customer360Profile] = {}
        self._cohorts:    list[BehavioralCohort]   = []
        self._journeys:   list[JourneyPath]         = []
        self._seed_demo_data()
        self.logger.info(f"👤 Customer CDP: {len(self._identities)} resolved identities | {len(self._profiles)} C360 profiles")

    def resolve_identity(self, tenant_id: str,
                         records: dict[str, dict]) -> ResolvedIdentity:
        """
        Probabilistic identity resolution across multiple source records.
        Combines deterministic (email, phone, ID) and fuzzy signals.
        Confidence = 1 - Π(1 - signal_weight_i) for independent signals.

        records: {"crm": {...}, "web": {...}, "payments": {...}, "support": {...}}
        """
        signals = []
        # Extract signals from each source
        email_match = set()
        for source, rec in records.items():
            if rec.get("email"):
                email_match.add(rec["email"].lower())
                signals.append(IdentitySignal(MatchSignal.EMAIL_EXACT, source, rec["email"], 1.0))
            if rec.get("phone"):
                signals.append(IdentitySignal(MatchSignal.PHONE_EXACT, source, rec["phone"], 0.98))
            if rec.get("customer_id"):
                signals.append(IdentitySignal(MatchSignal.CUSTOMER_ID, source, rec["customer_id"], 1.0))
            if rec.get("card_last4"):
                signals.append(IdentitySignal(MatchSignal.PAYMENT_CARD, source, rec["card_last4"], 0.95))
            if rec.get("name") and len(records) > 1:
                signals.append(IdentitySignal(MatchSignal.NAME_FUZZY, source, rec["name"], 0.65))
            if rec.get("device_id"):
                signals.append(IdentitySignal(MatchSignal.DEVICE_FINGERPRINT, source, rec["device_id"], 0.80))
            if rec.get("ip_cluster"):
                signals.append(IdentitySignal(MatchSignal.IP_CLUSTER, source, rec["ip_cluster"], 0.45))

        # Confidence: 1 - product of (1 - weight) for each independent signal type
        seen_types = {}
        for sig in signals:
            w = self._SIGNAL_WEIGHTS[sig.signal_type]
            seen_types[sig.signal_type] = max(seen_types.get(sig.signal_type, 0), w)
        prob_not_match = math.prod(1 - w for w in seen_types.values())
        confidence     = round(1 - prob_not_match, 4)

        # Build canonical identity
        names  = [r.get("name","") for r in records.values() if r.get("name")]
        emails = [r.get("email","") for r in records.values() if r.get("email")]
        identity = ResolvedIdentity(
            identity_id=str(uuid.uuid4()), tenant_id=tenant_id,
            canonical_name=max(names, key=len) if names else "Unknown",
            canonical_email=min(emails) if emails else "",
            confidence=confidence, signals=signals,
            source_records={s: r.get("id","") for s,r in records.items()}
        )
        self._identities.append(identity)
        self.logger.info(f"  🔗 Identity resolved: {identity.canonical_name} | confidence={confidence:.1%} | {len(signals)} signals from {len(records)} sources")
        return identity

    def build_360_profile(self, identity: ResolvedIdentity,
                          raw_data: dict = None) -> Customer360Profile:
        """
        Assembles a complete Customer 360 profile from all connected data sources.
        Computes: churn probability, expansion probability, journey stage, next best action.
        """
        raw = raw_data or self._simulate_raw_data(identity)
        # Compute AI scores
        churn_prob = round(random.uniform(0.05, 0.85), 3)
        exp_prob   = round(max(0, random.uniform(-0.2, 0.9)), 3)
        health     = round(100 - churn_prob * 70 + exp_prob * 30 - (5 if raw["invoice_overdue"] else 0), 1)

        profile = Customer360Profile(
            identity_id=identity.identity_id, tenant_id=identity.tenant_id,
            account_name=identity.canonical_name, account_tier=raw["tier"],
            arr=raw["arr"], csm_name=raw["csm"],
            health_score=max(0, min(100, health)),
            dau_streak=raw["dau_streak"], feature_adoption=raw["feature_adoption"],
            last_activity=time.time() - raw["days_inactive"]*86400,
            nps_score=raw.get("nps"),
            invoice_overdue=raw["invoice_overdue"], days_overdue=raw["days_overdue"],
            ltv=raw["arr"] * random.uniform(3, 8),
            open_tickets=raw["open_tickets"], csat_score=raw["csat"],
            avg_resolution_days=raw["avg_res_days"],
            churn_probability=churn_prob, expansion_probability=exp_prob,
            journey_stage=JourneyStage.ONBOARDING,  # will be updated below
            next_best_action=NextBestAction.RENEWAL_OUTREACH,
            predicted_arr_90d=raw["arr"] * (1 + exp_prob * 0.3 - churn_prob * 0.2),
            journey_events=self._generate_journey_events(raw["arr"])
        )
        # Apply journey stage rules
        for stage, rule in self._STAGE_RULES.items():
            if rule(profile):
                profile.journey_stage = stage
                break
        # Apply NBA rules
        for condition, action in self._NBA_RULES:
            if condition(profile):
                profile.next_best_action = action
                break

        self._profiles[identity.identity_id] = profile
        self.logger.info(f"  📊 C360 built: {profile.account_name} | ARR=${profile.arr:,.0f} | health={profile.health_score:.0f} | stage={profile.journey_stage} | NBA={profile.next_best_action}")
        return profile

    def _simulate_raw_data(self, identity: ResolvedIdentity) -> dict:
        arr = random.choice([12000, 48000, 120000, 350000, 1200000])
        return {"tier":"ENTERPRISE" if arr>200000 else ("GROWTH" if arr>50000 else "STARTER"),
                "arr":arr, "csm":random.choice(["Sarah Chen","Marcus Webb","Priya Nair","Tom Ellis"]),
                "dau_streak":random.randint(0,90), "feature_adoption":random.uniform(0,1),
                "days_inactive":random.randint(0,45), "nps":random.choice([None,3,7,8,9,10]),
                "invoice_overdue":random.random()<0.15, "days_overdue":random.randint(0,60),
                "open_tickets":random.randint(0,12), "csat":round(random.uniform(2.5,5.0),1),
                "avg_res_days":round(random.uniform(0.5,8),1)}

    def _generate_journey_events(self, arr: float) -> list[dict]:
        events = [
            {"event":"signup",          "day":0,   "label":"Account created"},
            {"event":"first_query",     "day":2,   "label":"First NL2SQL query"},
            {"event":"invite_team",     "day":5,   "label":"Team members invited (3)"},
            {"event":"dashboard_create","day":8,   "label":"First custom dashboard"},
            {"event":"connector_active","day":12,  "label":"Salesforce connector activated"},
        ]
        if arr > 50000:
            events += [{"event":"qbr_completed","day":30,"label":"Quarterly Business Review held"},
                       {"event":"expansion_talk","day":45,"label":"Expansion conversation initiated"}]
        if arr > 200000:
            events += [{"event":"exec_sponsor","day":60,"label":"Executive sponsor meeting"},
                       {"event":"renewal_signed","day":90,"label":"Renewal signed +27% ARR"}]
        return events

    def analyze_cohort(self, tenant_id: str, cohort_name: str, definition: str,
                       filter_sql: str, outcome_metric: str) -> BehavioralCohort:
        """
        Behavioral cohort analysis: measure outcome lift for users sharing a common trait.
        Runs BigQuery cohort query and computes statistical significance (t-test approximation).
        """
        # Simulate cohort members and outcomes
        cohort_size        = random.randint(80, 800)
        overall_population = cohort_size * random.randint(3, 10)
        cohort_outcome     = random.uniform(0.20, 0.85)
        baseline_outcome   = random.uniform(0.12, 0.35)
        lift               = round(cohort_outcome / max(baseline_outcome, 0.01), 2)
        # Simplified p-value (real implementation uses scipy.stats.ttest_ind)
        effect_size = abs(cohort_outcome - baseline_outcome) / 0.15
        p_value     = round(max(0.001, 0.05 / (1 + effect_size * math.sqrt(cohort_size / 100))), 4)
        significant = p_value < 0.05

        action = (
            f"Replicate activation pattern: ensure all new users complete '{definition.split('who')[0].strip()}' "
            f"within first 7 days. Expected outcome improvement: +{(lift-1)*100:.0f}% on {outcome_metric}."
            if significant else "Cohort not statistically significant. Collect more data."
        )
        cohort = BehavioralCohort(
            cohort_id=str(uuid.uuid4()), name=cohort_name, definition=definition,
            filter_sql=filter_sql, tenant_id=tenant_id, members=cohort_size,
            outcome_metric=outcome_metric, outcome_value=round(cohort_outcome,3),
            baseline_value=round(baseline_outcome,3), lift_factor=lift,
            p_value=p_value, significant=significant, recommended_action=action
        )
        self._cohorts.append(cohort)
        sig_icon = "✅" if significant else "⚠️"
        self.logger.info(f"  {sig_icon} Cohort [{cohort_name}]: n={cohort_size} | lift={lift:.1f}x | p={p_value:.4f} | {'significant' if significant else 'not significant'}")
        return cohort

    def build_journey_paths(self, tenant_id: str) -> list[JourneyPath]:
        """
        Discovers common event sequence patterns from user journey data.
        Identifies the 'Golden Path' (expansion) vs off-ramps (churn signals).
        In production: sequence mining on BigQuery event tables using BigQuery ML.
        """
        paths = [
            JourneyPath(f"jp-{uuid.uuid4().hex[:6]}","Golden Path → Expansion",
                        ["signup","first_query","invite_team","dashboard_create","connector_active","qbr_completed","renewal_signed"],
                        72, 284, "EXPANSION", 0.78, +48_000),
            JourneyPath(f"jp-{uuid.uuid4().hex[:6]}","Early Churn Risk",
                        ["signup","first_query","inactive_7d","support_ticket","inactive_30d"],
                        28, 91, "CHURN", 0.61, -22_000),
            JourneyPath(f"jp-{uuid.uuid4().hex[:6]}","Slow Adoption → Stable",
                        ["signup","first_query","dashboard_create","training_attended","regular_use"],
                        45, 162, "STABLE", 0.89, +8_000),
            JourneyPath(f"jp-{uuid.uuid4().hex[:6]}","Power Adoption → Advocacy",
                        ["signup","first_query","invite_team","connector_active","ai_agent_enabled","nps_9","referral_given"],
                        55, 48, "EXPANSION", 0.91, +125_000),
        ]
        self._journeys.extend(paths)
        for p in paths:
            self.logger.info(f"  🗺️  Journey path: {p.name} | n={p.member_count} | outcome={p.outcome} ({p.outcome_rate:.0%}) | ARR impact={p.median_arr_impact:+,.0f}")
        return paths

    def get_360_api_response(self, identity_id: str) -> dict:
        """Customer 360 API endpoint response — the unified profile."""
        profile = self._profiles.get(identity_id)
        if not profile: raise ValueError(f"Profile {identity_id} not found")
        identity = next((i for i in self._identities if i.identity_id == identity_id), None)
        return {
            "identity_id":   identity_id,
            "canonical_name":profile.account_name,
            "confidence":    identity.confidence if identity else None,
            "sources":       list(identity.source_records.keys()) if identity else [],
            "crm":           {"tier":profile.account_tier,"arr":profile.arr,"csm":profile.csm_name,"health":profile.health_score},
            "behavioral":    {"dau_streak":profile.dau_streak,"feature_adoption":f"{profile.feature_adoption:.0%}","nps":profile.nps_score},
            "financial":     {"invoice_overdue":profile.invoice_overdue,"days_overdue":profile.days_overdue,"ltv":round(profile.ltv)},
            "support":       {"open_tickets":profile.open_tickets,"csat":profile.csat_score,"avg_resolution_days":profile.avg_resolution_days},
            "ai_insights":   {"churn_probability":profile.churn_probability,"expansion_probability":profile.expansion_probability,
                              "predicted_arr_90d":round(profile.predicted_arr_90d),"journey_stage":profile.journey_stage,
                              "next_best_action":profile.next_best_action},
            "journey_events":profile.journey_events[-5:],
        }

    def cdp_dashboard(self) -> dict:
        profiles   = list(self._profiles.values())
        at_risk    = sum(1 for p in profiles if p.journey_stage == JourneyStage.AT_RISK)
        expanding  = sum(1 for p in profiles if p.journey_stage == JourneyStage.EXPANSION)
        sig_cohorts= sum(1 for c in self._cohorts if c.significant)
        return {
            "resolved_identities":      len(self._identities),
            "c360_profiles":            len(profiles),
            "at_risk":                  at_risk,
            "expanding":                expanding,
            "behavioral_cohorts":       len(self._cohorts),
            "significant_cohorts":      sig_cohorts,
            "journey_paths_discovered": len(self._journeys),
            "avg_identity_confidence":  round(sum(i.confidence for i in self._identities)/max(1,len(self._identities))*100,1),
        }

    def _seed_demo_data(self):
        demo_records = [
            ("t-bank", {"crm":{"id":"crm-001","name":"Jennifer Whitmore","email":"j.whitmore@meridian.com","customer_id":"CUST-10928"},
                        "web":{"id":"web-029","name":"jwhitmore","email":"j.whitmore@meridian.com","device_id":"dev-f9a21"},
                        "payments":{"id":"pay-441","name":"J. Whitmore","card_last4":"4291","ip_cluster":"cluster-boston-1"},
                        "support":{"id":"sup-882","name":"Jennifer W.","email":"j.whitmore@meridian.com","phone":"+1-617-555-0192"}}),
            ("t-hosp", {"crm":{"id":"crm-002","name":"Dr. Marcus Chen","email":"m.chen@stgrace.nhs.uk","customer_id":"CUST-20041"},
                        "web":{"id":"web-093","name":"dr.mchen","ip_cluster":"cluster-london-3"},
                        "support":{"id":"sup-441","name":"Marcus Chen","email":"m.chen@stgrace.nhs.uk"}}),
            ("t-sports",{"crm":{"id":"crm-003","name":"Kenji Tanaka","email":"k.tanaka@tokyofc.jp","customer_id":"CUST-30012"},
                         "web":{"id":"web-201","name":"kenji.t","email":"kenji.t@tokyofc.jp","device_id":"dev-a8b92"},
                         "payments":{"id":"pay-881","name":"K Tanaka","card_last4":"7731"}}),
        ]
        for tenant_id, records in demo_records:
            identity = self.resolve_identity(tenant_id, records)
            self.build_360_profile(identity)


if __name__ == "__main__":
    cdp = CustomerCDP()

    print("\n=== Identity Resolution ===")
    new_identity = cdp.resolve_identity("t-retail", {
        "crm":      {"id":"crm-new","name":"Sophie Laurent","email":"s.laurent@galerie.fr","customer_id":"CUST-40091"},
        "web":      {"id":"web-new","name":"slaurent","email":"s.laurent@galerie.fr","device_id":"dev-9dcc1"},
        "payments": {"id":"pay-new","name":"S. Laurent","card_last4":"9812","ip_cluster":"cluster-paris-2"},
    })
    print(f"  Canonical: {new_identity.canonical_name} <{new_identity.canonical_email}>")
    print(f"  Confidence: {new_identity.confidence:.1%} from {len(new_identity.signals)} signals")
    print(f"  Sources: {list(new_identity.source_records.keys())}")

    print("\n=== Customer 360 Profile ===")
    profile = cdp.build_360_profile(new_identity)
    c360 = cdp.get_360_api_response(new_identity.identity_id)
    print(f"  Account:    {c360['canonical_name']} [{c360['crm']['tier']}] ARR=${c360['crm']['arr']:,.0f}")
    print(f"  Health:     {c360['crm']['health']:.0f}/100 | DAU streak: {c360['behavioral']['dau_streak']}d | Adoption: {c360['behavioral']['feature_adoption']}")
    print(f"  AI Insights: churn={c360['ai_insights']['churn_probability']:.0%} | expand={c360['ai_insights']['expansion_probability']:.0%}")
    print(f"  Journey:    {c360['ai_insights']['journey_stage']} → next action: {c360['ai_insights']['next_best_action']}")
    print(f"  Predicted ARR (90d): ${c360['ai_insights']['predicted_arr_90d']:,.0f}")

    print("\n=== Behavioral Cohort Analysis ===")
    cohorts = [
        ("Power Adopters","Users who activated 5+ features in their first 14 days",
         "dau_streak >= 14 AND feature_count_d14 >= 5","arr_at_month_12"),
        ("Connector Users","Users who connected at least one external data source in first 30 days",
         "connector_activated_d30 = TRUE","expansion_rate_6m"),
        ("Early Churners","Users with no activity within first 7 days after signup",
         "dau_streak_d7 = 0","churn_rate_90d"),
        ("NPS Promoters","Users who gave 9-10 NPS within first 90 days",
         "nps_score >= 9 AND nps_days_since_signup <= 90","referral_conversion"),
    ]
    for name, defn, sql, outcome in cohorts:
        c = cdp.analyze_cohort("t-bank", name, defn, sql, outcome)
        sig = "✅ SIGNIFICANT" if c.significant else "⚠️  not sig."
        print(f"  {name:30} lift={c.lift_factor:.1f}x | p={c.p_value:.4f} | {sig}")
        if c.significant:
            print(f"    → {c.recommended_action[:100]}")

    print("\n=== Customer Journey Paths ===")
    paths = cdp.build_journey_paths("t-bank")
    print(f"\n{'Path':40} {'Users':6} {'Outcome':10} {'Rate':6} {'ARR Δ':12}")
    print("─"*78)
    for p in paths:
        icon = "🟢" if p.outcome == "EXPANSION" else ("🔴" if p.outcome == "CHURN" else "🟡")
        print(f" {icon} {p.name:38} {p.member_count:5} {p.outcome:10} {p.outcome_rate:5.0%}  {p.median_arr_impact:+>10,.0f}")

    print("\n=== CDP Dashboard ===")
    print(json.dumps(cdp.cdp_dashboard(), indent=2))
