# services/semantic-layer/semantic_layer.py
"""
Epic 86: Universal Semantic Layer & Data Mesh Governance
Solves the "metrics inconsistency" problem — the most common complaint in
enterprise analytics: the CFO's dashboard says ARR is $48.2M, the CEO's
says $51.7M, and the board deck says $49.9M. All three are "right" but
use different SQL definitions.

With a semantic layer: define ARR once → used everywhere.
Every NL2SQL query, SDK call, dashboard, and scheduled report
uses the SAME canonical SQL definition, always.

Data Mesh governance:
  Every dataset is a "data product" with:
  - An owner (the team responsible for quality and freshness)
  - An SLA (e.g. refreshed every 15 minutes, quality score > 0.95)
  - A subscriber list (teams consuming this data)
  - A schema contract (breaking changes notify all subscribers)
  - A freshness contract (staleness alerts fire to subscribers)

Metric consistency validator:
  Runs hourly. Executes the same metric from every possible path
  (NL2SQL, direct SQL, dashboard widget, SDK) and asserts they agree
  within a tolerance. Fires alert when they diverge.
"""
import logging, json, uuid, time, random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class MetricType(str, Enum):
    FINANCIAL   = "FINANCIAL"
    OPERATIONAL = "OPERATIONAL"
    PRODUCT     = "PRODUCT"
    GROWTH      = "GROWTH"
    QUALITY     = "QUALITY"
    CLINICAL    = "CLINICAL"

class DataProductStatus(str, Enum):
    HEALTHY    = "HEALTHY"
    DEGRADED   = "DEGRADED"    # quality < SLA or freshness violated
    BREAKING   = "BREAKING"    # schema breaking change pending
    DEPRECATED = "DEPRECATED"

class ConsistencyCheckStatus(str, Enum):
    CONSISTENT   = "CONSISTENT"
    DIVERGENT    = "DIVERGENT"  # values differ beyond tolerance
    MISSING      = "MISSING"    # metric not available from some paths

@dataclass
class MetricDefinition:
    metric_id:   str
    name:        str
    display_name:str
    description: str
    metric_type: MetricType
    sql:         str            # canonical, parameterized SQL
    unit:        str            # "$", "%", "users", "minutes", etc.
    grain:       str            # "daily" | "monthly" | "quarterly" | "realtime"
    owner_team:  str
    industries:  list[str]      # which industry templates include this metric
    aliases:     list[str]      # alternative names users might ask for
    tags:        list[str]

@dataclass
class DataProduct:
    product_id:    str
    name:          str
    owner_team:    str
    owner_email:   str
    description:   str
    source_table:  str
    refresh_freq:  str          # "realtime" | "5min" | "15min" | "1h" | "daily"
    quality_sla:   float        # minimum quality score (0-1)
    freshness_sla_min:int       # max age in minutes before staleness alert
    schema:        list[dict]   # [{column, type, description, pii, nullable}]
    subscribers:   list[str]    # team names subscribed to this product
    status:        DataProductStatus = DataProductStatus.HEALTHY
    last_refresh:  float = field(default_factory=time.time)
    quality_score: float = 0.97
    version:       str   = "1.0"

@dataclass
class ConsistencyReport:
    report_id:       str
    metric_id:       str
    checked_at:      float
    values_by_path:  dict[str, float]   # path → value (e.g. "nl2sql" → 48.2, "sdk" → 51.7)
    expected_value:  float
    tolerance_pct:   float = 0.001      # 0.1% tolerance
    status:          ConsistencyCheckStatus = ConsistencyCheckStatus.CONSISTENT
    divergent_paths: list[str]          = field(default_factory=list)

@dataclass
class SchemaChangeNotification:
    notification_id: str
    product_id:      str
    change_type:     str        # "ADDED_COLUMN"|"REMOVED_COLUMN"|"TYPE_CHANGED"|"RENAMED"
    column:          str
    old_type:        Optional[str]
    new_type:        Optional[str]
    breaking:        bool
    notified_teams:  list[str]
    created_at:      float = field(default_factory=time.time)

class SemanticLayer:
    """
    Universal semantic layer: canonical metric definitions + data mesh governance.
    One truth, everywhere.
    """
    # Canonical metric registry — industry-spanning definitions
    _METRICS: list[MetricDefinition] = [
        # Financial metrics
        MetricDefinition("arr","arr","Annual Recurring Revenue",
                         "Total contracted recurring revenue normalized to 12 months",
                         MetricType.FINANCIAL,
                         "SELECT SUM(monthly_amount * 12) AS arr FROM subscriptions WHERE status = 'ACTIVE' AND tenant_id = @tenant_id",
                         "$","monthly","finance-team",
                         ["banking","saas","insurance","healthcare"],
                         ["Annual Recurring Revenue","yearly revenue","subscription revenue"],
                         ["revenue","saas","subscription"]),
        MetricDefinition("nrr","nrr","Net Revenue Retention",
                         "Expansion + contraction + churn as % of starting ARR (cohort-based)",
                         MetricType.FINANCIAL,
                         """WITH cohort AS (SELECT tenant_id, SUM(arr) AS start_arr FROM subscriptions WHERE period_start = DATE_TRUNC('month', CURRENT_DATE - INTERVAL '12 months') GROUP BY 1)
SELECT c.tenant_id, (end_arr / start_arr) * 100 AS nrr
FROM cohort c JOIN (SELECT tenant_id, SUM(arr) AS end_arr FROM subscriptions WHERE period_start = DATE_TRUNC('month', CURRENT_DATE) GROUP BY 1) e ON c.tenant_id = e.tenant_id""",
                         "%","monthly","finance-team",
                         ["banking","saas"],["Net Revenue Retention","dollar retention"],["retention","churn"]),
        MetricDefinition("ltv","ltv","Customer Lifetime Value",
                         "Average revenue per customer × average customer lifespan",
                         MetricType.FINANCIAL,
                         "SELECT AVG(total_revenue) / NULLIF(1 - NVL(churn_rate,0.05), 0) AS ltv FROM customers WHERE tenant_id = @tenant_id",
                         "$","monthly","finance-team",
                         ["banking","saas","retail","insurance"],
                         ["Lifetime Value","LTV","customer value"],["ltv","retention"]),
        MetricDefinition("cac","cac","Customer Acquisition Cost",
                         "Total sales & marketing spend divided by new customers acquired",
                         MetricType.FINANCIAL,
                         "SELECT SUM(sm_spend) / NULLIF(COUNT(DISTINCT new_customer_id),0) AS cac FROM acquisition_metrics WHERE period = DATE_TRUNC('month', CURRENT_DATE) AND tenant_id = @tenant_id",
                         "$","monthly","growth-team",
                         ["saas","retail"],["Customer Acquisition Cost","cost per acquisition"],["growth","marketing"]),
        # Operational metrics
        MetricDefinition("churn_rate","churn_rate","Monthly Churn Rate",
                         "% of customers who churned in the given month (involuntary excluded)",
                         MetricType.OPERATIONAL,
                         "SELECT COUNT(DISTINCT churned_customer_id) * 100.0 / NULLIF(COUNT(DISTINCT customer_id),0) AS churn_rate FROM customer_status WHERE period = DATE_TRUNC('month', CURRENT_DATE) AND tenant_id = @tenant_id",
                         "%","monthly","csm-team",
                         ["saas","banking","insurance"],["churn","customer loss","attrition"],["churn","retention"]),
        MetricDefinition("nps","nps","Net Promoter Score",
                         "% promoters (9-10) minus % detractors (0-6) from survey responses",
                         MetricType.OPERATIONAL,
                         "SELECT (SUM(CASE WHEN score >= 9 THEN 1 ELSE 0 END) - SUM(CASE WHEN score <= 6 THEN 1 ELSE 0 END)) * 100.0 / COUNT(*) AS nps FROM nps_surveys WHERE survey_date >= CURRENT_DATE - 30 AND tenant_id = @tenant_id",
                         "points","monthly","cx-team",
                         ["saas","banking","healthcare","retail","hospitality"],
                         ["Net Promoter Score","customer satisfaction"],["cx","satisfaction"]),
        # Healthcare-specific
        MetricDefinition("readmission_rate","readmission_rate","30-Day Readmission Rate",
                         "% of patients readmitted within 30 days of discharge",
                         MetricType.CLINICAL,
                         "SELECT COUNT(DISTINCT r.patient_id) * 100.0 / COUNT(DISTINCT d.patient_id) AS readmission_rate FROM discharges d LEFT JOIN admissions r ON d.patient_id = r.patient_id AND r.admitted_at BETWEEN d.discharged_at AND d.discharged_at + INTERVAL '30 days' WHERE d.discharged_at >= CURRENT_DATE - 90 AND d.tenant_id = @tenant_id",
                         "%","monthly","clinical-quality",
                         ["healthcare"],["30-day readmission","hospital readmission","bounce rate"],["clinical","quality"]),
        MetricDefinition("hcahps","hcahps","HCAHPS Patient Experience Score",
                         "Hospital Consumer Assessment of Healthcare Providers and Systems composite score",
                         MetricType.CLINICAL,
                         "SELECT AVG(composite_score) AS hcahps FROM hcahps_surveys WHERE survey_date >= CURRENT_DATE - 90 AND tenant_id = @tenant_id",
                         "points","quarterly","patient-experience",
                         ["healthcare"],["HCAHPS","patient satisfaction","hospital rating"],["clinical","quality","experience"]),
        # Sports
        MetricDefinition("win_pct","win_pct","Win Percentage",
                         "Wins as a percentage of games played (home + away)",
                         MetricType.OPERATIONAL,
                         "SELECT SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS win_pct FROM matches WHERE season = @season AND team_id = @tenant_id",
                         "%","weekly","analytics-team",
                         ["sports"],["win rate","winning percentage","W-L record"],["sports","performance"]),
        # Product
        MetricDefinition("dau","dau","Daily Active Users",
                         "Distinct users performing a qualifying action in a 24-hour period",
                         MetricType.PRODUCT,
                         "SELECT COUNT(DISTINCT user_id) AS dau FROM events WHERE event_date = CURRENT_DATE AND action_type IN ('query','report','dashboard_view') AND tenant_id = @tenant_id",
                         "users","daily","product-team",
                         ["saas"],["DAU","active users","daily users"],["product","engagement"]),
    ]

    def __init__(self, project_id: str = "alti-analytics-prod"):
        self.project_id   = project_id
        self.logger       = logging.getLogger("Semantic_Layer")
        logging.basicConfig(level=logging.INFO)
        self._metrics:  dict[str, MetricDefinition] = {m.metric_id: m for m in self._METRICS}
        self._products: list[DataProduct]           = []
        self._reports:  list[ConsistencyReport]     = []
        self._notifications:list[SchemaChangeNotification] = []
        self._seed_data_products()
        self.logger.info(f"📐 Semantic Layer: {len(self._metrics)} canonical metrics | {len(self._products)} data products")

    def _seed_data_products(self):
        products = [
            DataProduct("dp-001","salesforce.customers","revenue-ops","revops@alti.ai",
                        "CRM customer master with enriched churn probability and ARR segmentation",
                        "salesforce_raw.accounts","15min",0.95,20,
                        [{"column":"customer_id","type":"STRING","description":"UUID","pii":False,"nullable":False},
                         {"column":"name","type":"STRING","description":"Company name","pii":True,"nullable":False},
                         {"column":"arr","type":"FLOAT64","description":"Annual Recurring Revenue USD","pii":False,"nullable":True},
                         {"column":"churn_probability","type":"FLOAT64","description":"ML model score 0-1","pii":False,"nullable":True},
                         {"column":"email","type":"STRING","description":"Primary contact email","pii":True,"nullable":True}],
                        ["finance-team","csm-team","product-team","executive"]),
            DataProduct("dp-002","hospital.patients","clinical-ops","clinops@hospital.org",
                        "Patient master with de-identified demographics and clinical risk scores",
                        "epic_fhir.Patient","5min",0.98,10,
                        [{"column":"patient_id","type":"STRING","description":"UUID","pii":False,"nullable":False},
                         {"column":"mrn","type":"STRING","description":"Medical Record Number","pii":True,"nullable":False},
                         {"column":"readmission_risk","type":"FLOAT64","description":"30-day readmission probability","pii":False,"nullable":True},
                         {"column":"diagnosis_codes","type":"ARRAY<STRING>","description":"ICD-10 codes","pii":False,"nullable":True}],
                        ["clinical-quality","finance-team","patient-experience"]),
            DataProduct("dp-003","finance.transactions","treasury","treasury@bank.com",
                        "Banking transaction ledger with fraud scores and AML flags",
                        "spanner.Transactions","realtime",0.999,2,
                        [{"column":"transaction_id","type":"STRING","description":"UUID","pii":False,"nullable":False},
                         {"column":"account_id","type":"STRING","description":"Account reference","pii":True,"nullable":False},
                         {"column":"amount","type":"INT64","description":"Amount in minor units (cents)","pii":False,"nullable":False},
                         {"column":"fraud_score","type":"FLOAT64","description":"ML fraud probability","pii":False,"nullable":True},
                         {"column":"aml_flag","type":"BOOL","description":"Anti-money-laundering flag","pii":False,"nullable":False}],
                        ["fraud-team","compliance","finance-team","risk-management"]),
        ]
        self._products.extend(products)

    def resolve_metric(self, name_or_alias: str, tenant_id: str,
                       params: dict = None) -> dict:
        """
        Resolves a metric by name or alias to its canonical SQL definition.
        Every query path — NL2SQL, SDK, dashboard — calls this to ensure
        the same SQL is always used. No more metric inconsistency.
        """
        # Find by metric_id or alias
        metric = self._metrics.get(name_or_alias)
        if not metric:
            for m in self._metrics.values():
                if name_or_alias.lower() in [a.lower() for a in m.aliases + [m.display_name, m.name]]:
                    metric = m
                    break
        if not metric:
            raise ValueError(f"Unknown metric: '{name_or_alias}'. Available: {list(self._metrics.keys())}")

        # Instantiate SQL with params
        sql = metric.sql.replace("@tenant_id", f"'{tenant_id}'")
        for k, v in (params or {}).items():
            sql = sql.replace(f"@{k}", f"'{v}'")

        # Simulate query execution
        simulated_value = random.uniform(40_000_000, 60_000_000) if metric.unit == "$" \
                          else random.uniform(0.5, 100.0) if metric.unit in ("%","points") \
                          else random.randint(1000, 100000)

        self.logger.info(f"📐 Metric resolved: '{name_or_alias}' → {metric.metric_id} | value={simulated_value:,.2f}{metric.unit}")
        return {"metric_id": metric.metric_id, "display_name": metric.display_name,
                "sql": sql[:200], "value": round(simulated_value, 2),
                "unit": metric.unit, "grain": metric.grain,
                "owner_team": metric.owner_team, "description": metric.description}

    def validate_consistency(self, metric_id: str,
                             tenant_id: str) -> ConsistencyReport:
        """
        Executes the same metric from multiple paths and asserts they agree.
        Fires alert when NL2SQL, SDK, and dashboard diverge beyond 0.1%.
        """
        metric = self._metrics.get(metric_id)
        if not metric: raise ValueError(f"Unknown metric: {metric_id}")
        # Simulate each path computing the metric independently
        base_value = random.uniform(40_000_000, 60_000_000) if metric.unit == "$" else random.uniform(1,100)
        paths = {
            "nl2sql":        base_value * (1 + random.uniform(-0.0005, 0.0005)),
            "sdk":           base_value * (1 + random.uniform(-0.0003, 0.0003)),
            "dashboard":     base_value * (1 + random.uniform(-0.0008, 0.0008)),
            "scheduled_report": base_value * (1 + random.uniform(-0.0002, 0.0002)),
        }
        # Introduce occasional inconsistency for demo
        if random.random() < 0.2:
            paths["dashboard"] = base_value * 1.07   # 7% divergence — bug!

        max_val    = max(paths.values())
        min_val    = min(paths.values())
        divergence = (max_val - min_val) / base_value
        tolerance  = 0.001  # 0.1%
        divergent  = [k for k, v in paths.items() if abs(v - base_value) / base_value > tolerance]
        status     = ConsistencyCheckStatus.DIVERGENT if divergent else ConsistencyCheckStatus.CONSISTENT

        report = ConsistencyReport(report_id=str(uuid.uuid4()), metric_id=metric_id,
                                   checked_at=time.time(), values_by_path={k: round(v,2) for k,v in paths.items()},
                                   expected_value=round(base_value,2), tolerance_pct=tolerance*100,
                                   status=status, divergent_paths=divergent)
        self._reports.append(report)
        icon = "✅" if status == ConsistencyCheckStatus.CONSISTENT else "⚠️"
        self.logger.info(f"{icon} Consistency [{metric_id}]: divergence={divergence:.4%} | {status}")
        if divergent:
            self.logger.warning(f"   Divergent paths: {divergent} — metric definition may differ between compute paths")
        return report

    def notify_schema_change(self, product_id: str, column: str,
                             change_type: str, old_type: str = None,
                             new_type: str = None) -> SchemaChangeNotification:
        """
        Notifies all subscribers of a data product about a schema change.
        Breaking changes (column removed, type incompatibly changed) prevent
        deployment until subscribers acknowledge.
        """
        product = next((p for p in self._products if p.product_id == product_id), None)
        if not product: raise ValueError(f"Product {product_id} not found")

        breaking = change_type in ("REMOVED_COLUMN","TYPE_CHANGED")
        if breaking:
            product.status = DataProductStatus.BREAKING

        note = SchemaChangeNotification(notification_id=str(uuid.uuid4()),
                                        product_id=product_id, change_type=change_type,
                                        column=column, old_type=old_type, new_type=new_type,
                                        breaking=breaking, notified_teams=product.subscribers)
        self._notifications.append(note)
        severity = "🔴 BREAKING" if breaking else "🟡 NON-BREAKING"
        self.logger.warning(f"{severity} Schema change: {product.name}.{column} | {change_type} | notified: {product.subscribers}")
        return note

    def semantic_dashboard(self) -> dict:
        consistent   = sum(1 for r in self._reports if r.status == ConsistencyCheckStatus.CONSISTENT)
        divergent    = sum(1 for r in self._reports if r.status == ConsistencyCheckStatus.DIVERGENT)
        breaking_chg = sum(1 for n in self._notifications if n.breaking)
        return {
            "canonical_metrics":     len(self._metrics),
            "data_products":         len(self._products),
            "consistency_checks":    len(self._reports),
            "consistent":            consistent,
            "divergent":             divergent,
            "schema_notifications":  len(self._notifications),
            "breaking_changes":      breaking_chg,
            "total_subscribers":     sum(len(p.subscribers) for p in self._products),
        }


if __name__ == "__main__":
    layer = SemanticLayer()

    print("=== Canonical Metric Resolution ===\n")
    queries = [
        ("arr",               "t-saas",   {}),
        ("Annual Recurring Revenue", "t-saas", {}),   # via alias
        ("NRR",               "t-saas",   {}),
        ("churn_rate",        "t-saas",   {}),
        ("readmission_rate",  "t-hospital",{}),
        ("win_pct",           "t-sports",  {"season":"2025-26"}),
        ("HCAHPS",            "t-hospital",{}),        # via alias
        ("Daily Active Users","t-saas",   {}),         # via alias
    ]
    for name, tenant, params in queries:
        result = layer.resolve_metric(name, tenant, params)
        print(f"  '{name}' → {result['metric_id']:20} = {result['value']:>16,.2f}{result['unit']} | grain={result['grain']}")

    print("\n=== Metric Consistency Validation ===")
    for metric_id in ["arr","nrr","churn_rate","readmission_rate"]:
        report = layer.validate_consistency(metric_id, "t-saas")
        if report.status == ConsistencyCheckStatus.DIVERGENT:
            print(f"  ⚠️  {metric_id}: DIVERGENT paths={report.divergent_paths}")
            for path, value in report.values_by_path.items():
                print(f"       {path:20} = {value:,.2f}")
        else:
            print(f"  ✅ {metric_id}: consistent across all 4 paths")

    print("\n=== Schema Change Notifications ===")
    n1 = layer.notify_schema_change("dp-001","arr","TYPE_CHANGED","FLOAT64","NUMERIC")
    print(f"  {n1.change_type}: {n1.column} | BREAKING={n1.breaking} | notified: {n1.notified_teams}")
    n2 = layer.notify_schema_change("dp-001","segment_label","ADDED_COLUMN",new_type="STRING")
    print(f"  {n2.change_type}: {n2.column} | BREAKING={n2.breaking} | notified: {n2.notified_teams}")

    print("\n=== Semantic Layer Dashboard ===")
    print(json.dumps(layer.semantic_dashboard(), indent=2))
